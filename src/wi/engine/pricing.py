"""Pricing: residual fair value and half-spread, the house residual tick, the house quote schedule and
the itemised policy premium (docs/SPEC.md sections 6.2, 6.6, 7).

Integers throughout (no floats reach an event). Fair value is E[L(basis)] over the trailing
`historyDays` (60) FINALISED days of the basis index, all finalised at or before the quote time
(no look-ahead) - a recent window, never long climatology (Phase 4: long climatology produced a
+$1,062/day artefact at NYC). The half-spread floor is `minHalfTicks` (1 tick): Phase 4 found the
15 % cost-of-capital charge is under one tick, so the spread is tick-bound.
"""
from __future__ import annotations

from math import isqrt

from . import hedge
from .oracle import finalized_before
from .state import P
from .units import BPS, PPM, TICK, UNIT, L, ceil_div, clamp, mul_div, round_half_away


def floor_div(a: int, b: int) -> int:
    """floor(a / b) for b > 0, explicit for negative a (pricing only; never on a money transfer)."""
    return -ceil_div(-a, b) if a < 0 else a // b


def ceil_signed(a: int, b: int) -> int:
    return ceil_div(a, b) if a >= 0 else -((-a) // b)


# ---------------------------------------------------------------- basis history and fair value
def basis_history(st: dict, index_id: str, ts: int, prehistory: list[list[int]] | None = None) -> list[tuple]:
    """Trailing finalised values (day, value) with finalisation at or before ts. prehistory rows are
    [day, value, finalizedTs] from before the engine run (fixture input)."""
    rows = {d: v for d, v, fts in (prehistory or []) if fts <= ts}
    for d, v in finalized_before(st, index_id, ts):
        rows[d] = v
    n = P(st, "historyDays")
    return sorted(rows.items())[-n:]


def fair_stats(values: list[int], R: int, rng: tuple[int, int] | None = None) -> dict:
    """S1 = sum L, n, and the standard error of the mean of L(basis) in base units (isqrt floor).
    rng = (lo, hi) prices another market on the same rule (the rain market [0, 1], 13-RAIN); default [-R, +R]."""
    lo, hi = rng if rng is not None else (-R, R)
    Ls = [L(v, lo, hi) for v in values]
    n = len(Ls)
    if n < 2:
        raise ValueError("need at least 2 finalised basis days")
    s1, s2 = sum(Ls), sum(x * x for x in Ls)
    var_num = n * s2 - s1 * s1
    se = isqrt(max(0, var_num) // (n * n * (n - 1)))
    return {"n": n, "s1": s1, "se": se}


def half_spread_e6(st: dict, se: int) -> int:
    return max(P(st, "minHalfTicks") * TICK, P(st, "zBps") * se // BPS + P(st, "bufferTicks") * TICK)


def residual_ticks(st: dict, fs: dict, inventory: int = 0) -> dict:
    """House residual ticks: bid legs ceil(fair + h), offer legs floor(fair - h), clamped to 1..99, and the
    schedule base ticks with the inventory skew k (ppm of a tick per unit)."""
    n, s1 = fs["n"], fs["s1"]
    hs = half_spread_e6(st, fs["se"])
    skew = P(st, "kInvPpm") * inventory * TICK // PPM if inventory >= 0 else -(P(st, "kInvPpm") * -inventory * TICK // PPM)
    bid_leg = clamp(ceil_signed(s1 + hs * n, n * TICK), 1, 99)
    offer_leg = clamp(floor_div(s1 - hs * n, n * TICK), 1, 99)
    sched_bid = floor_div(s1 - (hs + skew) * n, n * TICK)
    sched_ask = ceil_signed(s1 + (hs - skew) * n, n * TICK)
    return {"bidLeg": bid_leg, "offerLeg": offer_leg, "schedBid": sched_bid, "schedAsk": sched_ask,
            "fairE6": s1 // n, "halfSpreadE6": hs}


def schedule_levels(st: dict, rt: dict) -> list[tuple[bool, int]]:
    """(isBid, tick) of the house schedule: bid - {0,1,2} steps, ask + {0,1,2} steps; ticks outside 1..99 dropped."""
    step, n = P(st, "levelStepTicks"), P(st, "houseLevels")
    out = []
    for i in range(n):
        tb, ta = rt["schedBid"] - i * step, rt["schedAsk"] + i * step
        if 1 <= tb <= 99:
            out.append((True, tb))
        if 1 <= ta <= 99:
            out.append((False, ta))
    return out


# ---------------------------------------------------------------- policy premium
def station_basis_windows(st: dict, index_id: str, ts: int, prehistories: dict[str, list]) -> list[list[int]]:
    """Trailing finalised windows (values only) of every PAIR index settling on `index_id`'s station, for a
    policy with no residual leg of its own (a business AT the settlement station). Same window rule as the
    residual fair value (basis_history: 60 days, finalised at or before ts)."""
    sta = st["indices"][index_id]["station"]
    out = []
    for iid in sorted(st["indices"]):
        ix = st["indices"][iid]
        if ix["kind"] == "PAIR" and ix["station"] == sta:
            vals = [v for _, v in basis_history(st, iid, ts, prehistories.get(iid))]
            if len(vals) >= 2:
                out.append(vals)
    return out


def tail_spreads(windows: list[list[int]]) -> list[int]:
    """Distances (index scale) of each finalised basis value from its own window mean, floor(|n.v - S| / n).
    Centred per window, so a pair's average offset is not counted as spread."""
    out = []
    for w in windows:
        n, s = len(w), sum(w)
        out += [abs(n * v - s) // n for v in w]
    return out


def tail_charge(*, units: int, is_long: bool, lo: int, hi: int, v_edge: int, p_edge_ppm: int,
                spreads: list[int] | None) -> int:
    """tailE6 (SPEC 6.6, 7.3; strike-dependent beyond the ladder per SPEC 18, 2026-09-30).

    v0 charge: units x (unhedged share at the end rung's v) x p_end / 2. When the whole policy range lies
    beyond the end rung's v (a put with hi <= v_bot, a call with lo >= v_top) the ladder hedges nothing and the
    v0 charge is the same at every line. There the charge is the pool's expected loss with the index landing
    y beyond v_edge, y drawn from the trailing-window basis spreads: units x p_end x mean_i u(y_i), with
    u(y) = L(v_edge) - L(v_edge - y) for puts and L(v_edge + y) - L(v_edge) for calls; never above the v0
    charge, never below one tick per unit."""
    if is_long:
        crude = mul_div(units * (UNIT - L(v_edge, lo, hi)), p_edge_ppm, 2 * PPM)
        beyond = lo >= v_edge
    else:
        crude = mul_div(units * L(v_edge, lo, hi), p_edge_ppm, 2 * PPM)
        beyond = hi <= v_edge
    if not beyond or not spreads:
        return crude
    if is_long:
        loss = sum(L(v_edge + y, lo, hi) - L(v_edge, lo, hi) for y in spreads)
    else:
        loss = sum(L(v_edge, lo, hi) - L(v_edge - y, lo, hi) for y in spreads)
    est = mul_div(units * loss, p_edge_ppm, len(spreads) * PPM)
    return max(units * TICK, min(crude, est))


def price_policy(st: dict, ts: int, *, market: str, buyer: str, is_long: bool, units: int, rungs: list[dict],
                 basis_market: str | None, prehistory: list | None, nonce: int, expiry: int,
                 tail_windows: list[list[int]] | None = None) -> dict | None:
    """Itemised quote components for issue_quote, or None if the ladder cannot be priced at ts.
    tail_windows: finalised basis windows for the beyond-the-ladder tail when there is no basis market
    (station_basis_windows); with a basis market its own window is used."""
    m = st["markets"][market]
    lo, hi = m["lo"], m["hi"]
    quotes = hedge.quotes_at(rungs, ts)
    if quotes is None:
        return None
    q = hedge.replicate(units, lo, hi, is_long, rungs)
    for tk, need in q.items():
        if need and not hedge.offer_ok(quotes[tk]):
            return None  # a needed rung has no offer: no quote (the business is told why)
    slip = P(st, "slipBufferCents")
    station = 0
    for tk, need in q.items():
        if need:
            ask = quotes[tk][0]
            station += need * ask * 100 + hedge.fee_cents([(need, ask)]) * 10_000 + need * slip * 100
    delta = hedge.delta_ppm(lo, hi, rungs, quotes)
    data_ts = max(v[2] for v in quotes.values())

    # residual leg
    h, t_res, resid, bm = 0, 0, 0, None
    if basis_market is not None:
        bmk = st["markets"][basis_market]
        R = bmk["hi"]
        hist = basis_history(st, bmk["indexId"], ts, prehistory)
        tail_windows = [[v for _, v in hist]]
        fs = fair_stats([v for _, v in hist], R)
        rt = residual_ticks(st, fs)
        h = round_half_away(units * delta * 2 * R, (hi - lo) * PPM)
        if h:
            bm = basis_market
            if is_long:
                t_res = rt["bidLeg"]
                resid = h * (t_res * TICK - UNIT // 2)
            else:
                t_res = rt["offerLeg"]
                resid = h * (UNIT // 2 - t_res * TICK)
        fin = [fts for d, v, fts in (prehistory or []) if fts <= ts]
        fin += [st["obs"][f"{bmk['indexId']}:{d}"]["finalAt"] for d, _ in finalized_before(st, bmk["indexId"], ts)]
        if fin:
            data_ts = max(data_ts, max(fin))

    # tail beyond the ladder's end rung (SPEC 6.6 / 7.3)
    rb, rt_, v_bot, v_top = hedge.top_bottom(rungs)
    edge, v_edge = (rt_, v_top) if is_long else (rb, v_bot)
    tail = tail_charge(units=units, is_long=is_long, lo=lo, hi=hi, v_edge=v_edge,
                       p_edge_ppm=hedge.rung_prob_ppm(edge["ticker"], rungs, quotes),
                       spreads=tail_spreads(tail_windows) if tail_windows else None)
    return {"market": market, "buyer": buyer, "isLong": is_long, "units": units, "expiry": expiry, "nonce": nonce,
            "stationLeg": station, "residualLeg": resid, "tail": tail, "residualMarket": bm or "0x" + "00" * 32,
            "residualQty": h, "residualTick": t_res, "deltaPpm": delta, "dataAsOf": data_ts, "replication": q}


# ---------------------------------------------------------------- rain cover (13-RAIN; SPEC 2 example (c), 7.1)
def finalized_rows(st: dict, index_id: str, ts: int, prehistory: list[list[int]] | None = None) -> list[tuple]:
    """(day, value, finalizedTs) of the trailing `historyDays` finalised values with finalisation <= ts (no look-ahead);
    the basis_history window rule, keeping the finalisation time for the quote's dataAsOf."""
    rows = {d: (v, fts) for d, v, fts in (prehistory or []) if fts <= ts}
    for d, v in finalized_before(st, index_id, ts):
        rows[d] = (v, st["obs"][f"{index_id}:{d}"]["finalAt"])
    n = P(st, "historyDays")
    return [(d, v, f) for d, (v, f) in sorted(rows.items())[-n:]]


def price_rain_policy(st: dict, ts: int, *, market: str, buyer: str, units: int, rungs: list[dict] | None,
                      history: list[tuple], nonce: int, expiry: int) -> dict | None:
    """Itemised components of a wet-day cover (market [0, 1] on CLI:<S>:WET, business long `units`) for issue_quote.

    Station leg = one Kalshi "> 0 in" contract per unit (SPEC 7.1), costed at tick t per contract plus the Kalshi taker
    fee (SPEC 7.5, rounded up once per order) plus the slip buffer, the SPEC 6.6 station-leg formula:
      the day's market quotable at ts  -> t = its ask (= mid + half-spread at Kalshi); source "kalshi"
      no market open yet at ts         -> t = ceil(fair + halfSpread), fair = mean wet-day indicator over the trailing
                                          `historyDays` finalised days (finalised <= ts), halfSpread by the SPEC 6.6
                                          residual rule (max(minHalfTicks, z x se + buffer)); source "history"
    No residual leg (none is listed for rain; RFQ only) and no tail: the cover settles on the same measurable-rain rule
    as the Kalshi contract (a trace is dry for both), so a one-contract binary leaves nothing unhedged by design.
    Returns None when the day's market is open but has no offer (SPEC 7.2), or there is no history to price from."""
    m = st["markets"][market]
    if (m["lo"], m["hi"]) != (0, 1):
        raise ValueError("rain cover is the [0, 1] market on a precipitation index")
    need = hedge.replicate_rain(units)
    quotes = hedge.quotes_at(rungs, ts) if rungs else None
    if quotes is not None:
        (tk, q), = quotes.items()
        if not hedge.offer_ok(q):
            return None
        tick, source, data_ts = q[0], "kalshi", q[2]
        fair_e6, half_e6 = (q[0] + (q[1] or 0)) * TICK // 2, (q[0] - (q[1] or 0)) * TICK // 2
        replication = {tk: need}
    else:
        if len(history) < 2:
            return None
        fs = fair_stats([v for _, v, _ in history], 0, rng=(0, 1))
        rt = residual_ticks(st, fs)
        tick, source, data_ts = rt["bidLeg"], "history", max(f for _, _, f in history)
        fair_e6, half_e6 = rt["fairE6"], rt["halfSpreadE6"]
        replication = {(rungs or [{}])[0].get("ticker", ""): need}
    slip = P(st, "slipBufferCents")
    station = need * tick * 100 + hedge.fee_cents([(need, tick)]) * 10_000 + need * slip * 100
    return {"market": market, "buyer": buyer, "isLong": True, "units": units, "expiry": expiry, "nonce": nonce,
            "stationLeg": station, "residualLeg": 0, "tail": 0, "residualMarket": "0x" + "00" * 32, "residualQty": 0,
            "residualTick": 0, "deltaPpm": mul_div(PPM, fair_e6, UNIT), "dataAsOf": data_ts,
            "replication": replication, "rainSource": source, "rainTick": tick, "fairE6": fair_e6, "halfE6": half_e6}
