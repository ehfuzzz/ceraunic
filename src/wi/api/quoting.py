"""Quote construction for both hedge-leg paths (SPEC 6.1, 6.2, 6.5, 6.6) on top of wi.engine.pricing.

House-hedge path (default): one engine policy per covered day on the business's location index
(CLI:<site>), priced by `pricing.price_policy` (station leg on the settlement ladder + residual leg on the
pair's auction + tail + risk margin + fee). Business-ladder path (overlay, SPEC 6.5): the venue sells only
the basis unit, as a policy on the pair's basis market sized h = round(units x delta x 2R / (hi - lo)),
priced at the house residual tick; the business is shown the Kalshi rung list and buys it itself.

Multi-day windows: Kalshi opens day D's ladder at D-1 14:00Z, so at quote time only the next day's ladder
exists. Every day in the window is priced NOW from the latest ladder open at the quote time (the next
day's), point in time, and sold as a firm daily policy. That is a term price with forecast risk carried by
the pool; SPEC 6.5 sells only floating day-ahead strips in v0, so this is a recorded deviation (09-SUMMARY).
"""
from __future__ import annotations

from wi.engine import hedge, margin, markets, policy, pricing
from wi.engine.eip712 import index_id
from wi.engine.state import P
from wi.engine.units import PPM, TICK, UNIT, day_to_iso, mul_div, round_half_away, tick_to_index, ts_to_iso

from . import catalog as cat
from . import snapshot_data as sd
from .envelope import ApiError
from .world import SimWorld

ZERO32 = "0x" + "00" * 32


def family(peril: str, strike: int, cap: int) -> tuple[int, int, bool]:
    if peril == "heat":
        return markets.family_market("CAPPED_CALL", strike, cap)
    if peril == "cold":
        return markets.family_market("CAPPED_PUT", strike, cap)
    raise ApiError(422, "VALIDATION", "Peril not priced", f"unknown peril {peril!r}")


def ladder_day(now: int, series: str, first_day: int) -> int:
    """Latest climate day whose ladder is quotable at `now` (the next day's, normally)."""
    for D in (first_day, now // 86_400 + 1, now // 86_400 + 2):
        rungs = sd.ladder(series, D)
        if rungs and hedge.quotes_at(rungs, now) is not None:
            return D
    raise ApiError(409, "NO_PRICE", "No ladder to price from",
                   f"no {series} ladder is quotable at {ts_to_iso(now)} (Kalshi opens day D at D-1 14:00Z)")


def _hist(w: SimWorld, site: str, ts: int):
    bm_idx = index_id(cat.pair_index(site))
    pre = w.prehistory()[bm_idx]
    return pricing.basis_history(w.st, bm_idx, ts, pre), pre


def build(w: SimWorld, *, biz: dict, peril: str, strike: int, cap: int, units: int, days: list[int], path: str,
          nonce0: int, emit: bool) -> dict:
    """Price every day; with emit=True create the markets and issue one engine quote per day.
    Returns the API quote record (digests, per-day premiums, wire fields)."""
    if peril == "rain":
        return build_rain(w, biz=biz, units=units, days=days, path=path, nonce0=nonce0, emit=emit)
    st, now = w.st, w.now
    site = biz["locationSite"]
    settle = cat.SITES[site][5]
    series = cat.HEDGE_SERIES[settle]
    lo, hi, is_long = family(peril, strike, cap)
    buyer = biz["owner"]
    if not days:
        raise ApiError(422, "VALIDATION", "Empty window", "pick at least one day")
    sale0 = markets.market_times(st, days[0])["saleCutoff"]
    if now >= sale0:
        raise ApiError(409, "QUOTE_EXPIRED", "Sales closed", f"sales for {day_to_iso(days[0])} closed at {ts_to_iso(sale0)}")
    if days[-1] > cat.LAST_DAY:
        raise ApiError(409, "OUT_OF_WINDOW", "Past the replay window",
                       f"the demo world replays climate days up to {day_to_iso(cat.LAST_DAY)}")
    dl = ladder_day(now, series, days[0])
    base_rungs = sd.ladder(series, dl)
    quotes_now = hedge.quotes_at(base_rungs, now)
    has_resid = site != settle
    R = P(st, "basisRangeTenths")
    rec = {"digests": [], "perDay": [], "days": [day_to_iso(D) for D in days], "path": path, "peril": peril,
           "strike": strike, "cap": cap, "units": units, "businessId": biz["businessId"], "buyer": buyer,
           "indexName": cat.cli_index(site) if path == "house-hedge" else cat.pair_index(site),
           "pricedWith": day_to_iso(dl), "expiry": sale0, "station": 0, "residual": 0, "tail": 0, "risk": 0,
           "nfee": 0, "fee": 0, "premium": 0, "maxPayout": 0, "note": None}
    nonce = nonce0
    first_comps = None
    for D in days:
        rungs = sd.ladder(series, D) if D == dl else base_rungs
        if rungs is None or hedge.quotes_at(rungs, now) is None:
            rungs = base_rungs
        loc_idx = index_id(cat.cli_index(site))
        bm = None
        if has_resid:
            bm = w.basis_market_id(site, D)
            if emit and bm not in st["markets"]:
                w.ensure_basis_market(now, site, D)
        if path == "house-hedge":
            mk = markets.create_market(w.led, now, loc_idx, D, lo, hi, False) if emit else \
                _virtual_market(st, loc_idx, D, lo, hi)
            if not emit and bm and bm not in st["markets"]:
                bm = _virtual_basis(st, site, D, R)
            tail_w = None if bm else pricing.station_basis_windows(st, loc_idx, now, w.prehistory())
            comps = pricing.price_policy(st, now, market=mk, buyer=buyer, is_long=is_long, units=units, rungs=rungs,
                                         basis_market=bm, prehistory=_hist(w, site, now)[1] if bm else None,
                                         nonce=nonce, expiry=sale0, tail_windows=tail_w)
            _cleanup(st)
            if comps is None:
                raise ApiError(409, "NO_PRICE", "Ladder cannot be priced",
                               "a rung this cover needs has no offer at the quote time (SPEC 7.2 no-offer rule)")
            extra = units * UNIT
            if comps["residualQty"]:
                from wi.engine.auction import escrow_for

                extra += escrow_for(is_long, comps["residualTick"], comps["residualQty"], 0)
            idx_for_caps = loc_idx
            max_pay = units * UNIT
        else:
            if not has_resid:
                rec["note"] = ("At the settlement station the Kalshi ladder is the whole hedge: buy the rungs below "
                               "yourself. The venue has no residual to sell here.")
                rec["ladder"] = _rungs_view(hedge.replicate(units, lo, hi, is_long, base_rungs), quotes_now)
                rec["digests"], rec["perDay"] = [], []
                return rec
            quotes = hedge.quotes_at(rungs, now)
            delta = hedge.delta_ppm(lo, hi, rungs, quotes)
            h = round_half_away(units * delta * 2 * R, (hi - lo) * PPM)
            if h == 0:
                rec["note"] = "The ladder implies no chance of a payout in this range: nothing to sell on the residual."
                rec["ladder"] = _rungs_view(hedge.replicate(units, lo, hi, is_long, base_rungs), quotes_now)
                return rec
            if not emit and bm not in st["markets"]:
                bm = _virtual_basis(st, site, D, R)
            hist, _ = _hist(w, site, now)
            rt = pricing.residual_ticks(st, pricing.fair_stats([v for _, v in hist], R))
            _cleanup(st)
            t = rt["bidLeg"] if is_long else rt["offerLeg"]
            resid = h * t * TICK if is_long else h * (100 - t) * TICK
            fin = [st["obs"][f"{index_id(cat.pair_index(site))}:{d}"]["finalAt"]
                   for d, _ in pricing.finalized_before(st, index_id(cat.pair_index(site)), now)]
            fin += [fts for _, _, fts in _hist(w, site, now)[1] if fts <= now]
            comps = {"market": bm, "buyer": buyer, "isLong": is_long, "units": h, "expiry": sale0, "nonce": nonce,
                     "stationLeg": 0, "residualLeg": resid, "tail": 0, "residualMarket": ZERO32, "residualQty": 0,
                     "residualTick": 0, "deltaPpm": delta,
                     "dataAsOf": max([q[2] for q in quotes.values()] + fin),
                     "replication": hedge.replicate(units, lo, hi, is_long, rungs), "overlayTick": t, "rt": rt}
            idx_for_caps = index_id(cat.pair_index(site))
            extra = h * UNIT
            max_pay = h * UNIT
        ident = policy.quote_identity(st, comps["units"], comps["stationLeg"], comps["residualLeg"], comps["tail"])
        if ident["premium"] > comps["units"] * UNIT:
            raise ApiError(409, "NO_PRICE", "Priced above the maximum payout",
                           f"{day_to_iso(D)} would cost {ident['premium']} for at most {comps['units'] * UNIT}")
        b = margin.breaches(st, idx_for_caps, D, extra)
        if b:
            raise ApiError(409, "CAP_EXCEEDED", "Exposure cap", f"{day_to_iso(D)}: {','.join(b)} would be breached")
        if emit:
            if path == "business-ladder" and comps["market"] not in st["markets"]:
                w.ensure_basis_market(now, site, D)
            rec["digests"].append(policy.issue_quote(w.led, now, comps))
        nonce += 1
        rec["perDay"].append(ident["premium"])
        rec["station"] += comps["stationLeg"]
        rec["residual"] += comps["residualLeg"]
        rec["tail"] += comps["tail"]
        rec["risk"] += ident["riskMargin"]
        rec["nfee"] += ident["notionalFee"]
        rec["fee"] += ident["fee"]
        rec["premium"] += ident["premium"]
        rec["maxPayout"] += max_pay
        if first_comps is None:
            first_comps = comps
    c = first_comps
    rec["nonceNext"] = nonce
    rec["asOf"] = c["dataAsOf"]
    rec["replication"] = c["replication"]
    rec["ladder"] = _rungs_view(c["replication"], quotes_now) if path == "business-ladder" else None
    rec["rungs"] = _rungs_view(c["replication"], hedge.quotes_at(sd.ladder(series, dl), now)) \
        if path == "house-hedge" else []
    rec["overround"] = (sum(q[0] for q in quotes_now.values()) - 100) * 100
    rec["series"] = series
    if path == "house-hedge":
        rec["residualQty"] = c["residualQty"]
        rec["residualTick"] = c["residualTick"] or None
        if c["residualQty"]:
            hist, _ = _hist(w, site, now)
            rt = pricing.residual_ticks(st, pricing.fair_stats([v for _, v in hist], R))
            rec["fair"], rec["half"] = rt["fairE6"], rt["halfSpreadE6"]
        else:
            rec["fair"], rec["half"] = 0, 0
    else:
        rec["residualQty"] = c["units"]
        rec["residualTick"] = c["overlayTick"]
        rec["fair"], rec["half"] = c["rt"]["fairE6"], c["rt"]["halfSpreadE6"]
    rec["basis"] = tick_to_index(rec["residualTick"], -R, R) if rec["residualTick"] else None
    rec["contractId"] = cat.contract_id(site) if has_resid else ""
    return rec


# ---------------------------------------------------------------- rain cover (13-RAIN)
MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")


def rain_ticker(series: str, day: int) -> str:
    """Kalshi's daily rain ticker for a climate day, e.g. KXRAIN-26JUL23-CHI (the market may not be listed yet)."""
    iso = day_to_iso(day)
    return f"KXRAIN-{iso[2:4]}{MONTHS[int(iso[5:7]) - 1]}{iso[8:10]}-{series.split('-', 1)[1]}"


def rain_station(biz: dict) -> str:
    """The Kalshi rain station of the business's metro (CLINYC, CLIORD, CLIMIA): the rain cover settles there."""
    return cat.RAIN_SITE[cat.SITES[biz["locationSite"]][4]]


def build_rain(w: SimWorld, *, biz: dict, units: int, days: list[int], path: str, nonce0: int, emit: bool) -> dict:
    """Wet-day cover: pays `units` dollars for each covered day the metro's rain station reports a wet day on its NWS
    CLI (0.01 in or more; a trace is dry, the same as Kalshi). One engine policy per day on the [0, 1] market
    of CLI:<S>:WET:v1, business long. House-hedge path: the house buys one KXRAIN contract per unit per day at
    T - 24 h. Business-ladder path: nothing to sell (no rain residual is listed; the local difference between the
    business and the station is RFQ-only), so the quote only lists the Kalshi contracts to place."""
    st, now = w.st, w.now
    rs = rain_station(biz)
    series, name = cat.RAIN_SERIES[rs], cat.rain_index(rs)
    iid = index_id(name)
    if iid not in st["indices"]:
        raise ApiError(409, "NO_PRICE", "Rain cover is not in this world",
                       "this demo world was created before rain cover existed; start a fresh demo world")
    if not days:
        raise ApiError(422, "VALIDATION", "Empty window", "pick at least one day")
    sale0 = markets.market_times(st, days[0])["saleCutoff"]
    if now >= sale0:
        raise ApiError(409, "QUOTE_EXPIRED", "Sales closed", f"sales for {day_to_iso(days[0])} closed at {ts_to_iso(sale0)}")
    if days[-1] > cat.LAST_DAY:
        raise ApiError(409, "OUT_OF_WINDOW", "Past the replay window",
                       f"the demo world replays climate days up to {day_to_iso(cat.LAST_DAY)}")
    station_name = cat.SITES[rs][1]
    local = cat.SITES[biz["locationSite"]][1]
    rec = {"digests": [], "perDay": [], "days": [day_to_iso(D) for D in days], "path": path, "peril": "rain",
           "strike": 0, "cap": 1, "units": units, "businessId": biz["businessId"], "buyer": biz["owner"],
           "indexName": name, "expiry": sale0, "station": 0, "residual": 0, "tail": 0, "risk": 0, "nfee": 0, "fee": 0,
           "premium": 0, "maxPayout": 0, "series": series, "contractId": "", "residualQty": 0, "residualTick": None,
           "basis": None, "rungs": [], "ladder": None, "overround": 0, "fair": 0, "half": 0, "asOf": now,
           "pricedWith": None, "note": None, "replication": {}}
    rows = []
    for D in days:
        rungs = sd.rain_ladder(series, D)
        q = hedge.quotes_at(rungs, now) if rungs else None
        tk = rungs[0]["ticker"] if rungs else rain_ticker(series, D)
        rows.append({"ticker": tk, "qty": units, "qtyCenti": hedge.replicate_rain(units),
                     "askCents": q[tk][0] if q else 0, "day": day_to_iso(D),
                     "source": "kalshi-ask" if q else "not-open"})
    if path == "business-ladder":
        rec["ladder"] = rows
        rec["note"] = (f"Rain cover settles on the {station_name} report, the same station the Kalshi rain market uses, so "
                       f"the Kalshi contracts below are the whole hedge: buy one per dollar per day yourself. We sell no "
                       f"rain local-difference contract yet: it would settle weekly on PRISM rainfall cells, and today "
                       f"it is by request only. Kalshi's rain contract counts a trace as no rain: it pays on 0.01 in or more.")
        return rec
    history = pricing.finalized_rows(st, iid, now, sd.rain_prehistory(rs, cat.FIRST_DAY))
    nonce, first = nonce0, None
    for D, row in zip(days, rows):
        mk = markets.create_market(w.led, now, iid, D, 0, 1, False) if emit else _virtual_market(st, iid, D, 0, 1)
        comps = pricing.price_rain_policy(st, now, market=mk, buyer=biz["owner"], units=units,
                                          rungs=sd.rain_ladder(series, D), history=history, nonce=nonce, expiry=sale0)
        _cleanup(st)
        if comps is None:
            raise ApiError(409, "NO_PRICE", "Rain market has no offer",
                           f"the Kalshi rain market for {day_to_iso(D)} is open but has no offer (SPEC 7.2 no-offer rule)")
        ident = policy.quote_identity(st, units, comps["stationLeg"], 0, comps["tail"])
        if ident["premium"] > units * UNIT:
            raise ApiError(409, "NO_PRICE", "Priced above the maximum payout",
                           f"{day_to_iso(D)} would cost {ident['premium']} for at most {units * UNIT}: Kalshi already "
                           f"expects rain that day")
        b = margin.breaches(st, iid, D, units * UNIT)
        if b:
            raise ApiError(409, "CAP_EXCEEDED", "Exposure cap", f"{day_to_iso(D)}: {','.join(b)} would be breached")
        if emit:
            rec["digests"].append(policy.issue_quote(w.led, now, comps))
        nonce += 1
        if comps["rainSource"] == "history":
            row["askCents"], row["source"] = comps["rainTick"], "wet-day-rate"
        rec["perDay"].append(ident["premium"])
        for k, v in (("station", comps["stationLeg"]), ("tail", comps["tail"]), ("risk", ident["riskMargin"]),
                     ("nfee", ident["notionalFee"]), ("fee", ident["fee"]), ("premium", ident["premium"]),
                     ("maxPayout", units * UNIT)):
            rec[k] += v
        rec["asOf"] = max(rec["asOf"] if first else 0, comps["dataAsOf"])
        if first is None:
            first = comps
    rec["nonceNext"] = nonce
    rec["rungs"] = rows
    rec["fair"], rec["half"] = first["fairE6"], first["halfE6"]
    rec["replication"] = first["replication"]
    kal = next((r for r in rows if r["source"] == "kalshi-ask"), None)
    rec["pricedWith"] = kal["day"] if kal else None
    wet_rate = mul_div(100, sum(v for _, v, _ in history), len(history)) if history else 0
    rec["note"] = (f"Pays ${units} for each covered day the National Weather Service daily report for {station_name} shows "
                   f"rain. Kalshi's rain contract counts a trace as no rain, and so does this cover: it pays on 0.01 in or more. Days whose Kalshi market is open are priced at its ask; later "
                   f"days at the last {len(history)} days' wet-day rate at {station_name} ({wet_rate}%) plus a spread. "
                   + (f"Your shop is near {local}, not {station_name}: the rain local-difference contract, which would "
                      f"settle weekly on PRISM rainfall cells, is by request only, so this cover pays on {station_name}'s "
                      f"rain." if biz["locationSite"] != rs else ""))
    return rec


def _rungs_view(q: dict[str, int], quotes: dict | None) -> list[dict]:
    out = []
    for tk, centi in q.items():
        if centi:
            out.append({"ticker": tk, "qty": round_half_away(centi, 100), "qtyCenti": centi,
                        "askCents": (quotes or {}).get(tk, (0,))[0]})
    return out


# pricing without events (GET /recommendation): price against temporary market entries, removed after
_VIRTUAL = "__virtual__"


def _virtual_market(st: dict, iid: str, day: int, lo: int, hi: int) -> str:
    from wi.engine.eip712 import market_id

    mk = market_id(iid, day, lo, hi)
    if mk not in st["markets"]:
        st["markets"][mk] = {"indexId": iid, "day": day, "lo": lo, "hi": hi, _VIRTUAL: True}
    return mk


def _virtual_basis(st: dict, site: str, day: int, R: int) -> str:
    return _virtual_market(st, index_id(cat.pair_index(site)), day, -R, R)


def _cleanup(st: dict) -> None:
    for k in [k for k, m in st["markets"].items() if m.get(_VIRTUAL)]:
        del st["markets"][k]
