"""House station leg on the Kalshi ladder: replication, delta, paper fills at recorded books or
candles, Kalshi fees, settlement from Kalshi `result` (docs/SPEC.md section 7).

Reuses the Phase 2 code rather than forking it: `wi.eval.ladder` (Bracket parsing and ordering,
representative values, YES asks from a NO-bid book, the no-offer rule) and `wi.eval.fees.TAKER_RATE`.
Those modules work in float dollars; every value that leaves this module is an int (cents,
centi-contracts, base units) converted with an explicit rule. `wi.eval.ladder` imports numpy, so it
is imported lazily here: the reducer and the API bundle never load it unless a hedge is priced.

Ladder input (engine format, ints only), one dict per rung:
  {"ticker", "strike_type", "floor_strike", "cap_strike", "close_ts", "settle_ts", "result",
   "candles": [[end_ts, ask_cents|None, bid_cents|None], ...],
   "books": [[ts, {"orderbook_fp": {"no_dollars": [[price_str, qty_str], ...]}}], ...]}
"""
from __future__ import annotations

from decimal import Decimal

from .state import P, Revert, add
from .units import PPM, UNIT, L, ceil_div, f_to_tenths, mul_div, round_half_away


def _ladder_mod():
    from wi.eval import ladder  # lazy: numpy

    return ladder


def fee_rate_num() -> int:
    """Kalshi taker rate as an integer numerator over 100 (0.07 -> 7), from wi.eval.fees."""
    from wi.eval.fees import TAKER_RATE

    n = round_half_away(int(Decimal(repr(TAKER_RATE)) * 10_000), 100)
    return n


def fee_cents(levels: list[tuple[int, int]]) -> int:
    """SPEC 7.5: ceil_div(sum over levels of rate x q_centi x P x (100 - P), 1e6), once per rung order."""
    tot = sum(fee_rate_num() * q * px * (100 - px) for q, px in levels)
    return ceil_div(tot, 1_000_000) if tot else 0


# ---------------------------------------------------------------- ladder geometry
def brackets(rungs: list[dict]):
    """wi.eval.ladder Brackets sorted low -> high, paired with the rung dicts."""
    lad = _ladder_mod()
    by = {}
    for r in rungs:
        b = lad.bracket_from_market({"ticker": r["ticker"], "strike_type": r["strike_type"],
                                     "floor_strike": r["floor_strike"], "cap_strike": r["cap_strike"]})
        if b is None:
            raise ValueError(f"unusable rung {r['ticker']}")
        by[b.ticker] = (b, r)
    ladder = lad.Ladder([b for b, _ in by.values()])
    return [(b, by[b.ticker][1]) for b in ladder.brackets]


def rep_tenths(b) -> int:
    """v_b in tenths: between 5(f+c), greater 10(f+1), less 10(c-1) (wi.eval.ladder Bracket.rep x 10)."""
    return f_to_tenths(b.rep)


def replicate(units: int, lo: int, hi: int, business_long: bool, rungs: list[dict]) -> dict[str, int]:
    """Per-policy centi-contracts per rung (SPEC 7.1), before aggregation and step rounding."""
    out = {}
    for b, r in brackets(rungs):
        lx = L(rep_tenths(b), lo, hi)
        v = lx if business_long else UNIT - lx
        out[r["ticker"]] = round_half_away(units * v * 100, UNIT)
    return out


def replicate_rain(units: int) -> int:
    """Rain digital: units x 100 centi YES (DIGITAL_ABOVE) or NO (DIGITAL_BELOW) on the >0 in market."""
    return units * 100


def is_rain_index(idx: dict) -> bool:
    """A wet-day indicator on CLI daily precipitation (`CLI:<SITE>:WET:v<n>`, scale 1; 13-RAIN, SPEC 18)."""
    parts = idx["name"].split(":")
    return len(parts) == 4 and parts[2] == "WET" and idx["scale"] == 1


def rain_needs(units: int, business_long: bool, rungs: list[dict]) -> dict[str, int]:
    """SPEC 7.1 rain: one contract per unit on the day's single "> 0 in" market. v0 sells wet-day cover only
    (DIGITAL_ABOVE on [0, 1] -> YES); the NO leg of a dry-day cover is not offered, so it is refused here."""
    if len(rungs) != 1 or rungs[0]["strike_type"] != "greater" or rungs[0]["floor_strike"] != 0:
        raise ValueError("rain hedge needs exactly one '> 0 in' market")
    if not business_long:
        raise ValueError("dry-day cover (the NO leg) is not offered in v0")
    return {rungs[0]["ticker"]: replicate_rain(units)}


def aggregate(needs: list[dict[str, int]], step: int) -> dict[str, int]:
    """Sum per-policy quantities per rung, then round once to CONTRACT_STEP (half away from zero)."""
    tot: dict[str, int] = {}
    for n in needs:
        for k, v in n.items():
            tot[k] = tot.get(k, 0) + v
    return {k: round_half_away(v, step) * step for k, v in sorted(tot.items())}


def covered_ints(b, lo: int, hi: int) -> int:
    """k_b of SPEC 7.4: integers t the rung counts (between {f, c}; greater {f+1}; less {c-1}) with lo < 10t <= hi."""
    if b.strike_type == "between":
        ts = {int(b.floor), int(b.cap)}
    elif b.strike_type == "greater":
        ts = {int(b.floor) + 1}
    else:
        ts = {int(b.cap) - 1}
    return sum(1 for t in ts if lo < 10 * t <= hi)


def delta_ppm(lo: int, hi: int, rungs: list[dict], quotes: dict[str, tuple]) -> int:
    """Mid-implied P(lo < X <= hi), normalised by the sum of mids (SPEC 7.4). quotes: ticker -> (ask, bid, ts)."""
    num = den = 0
    for b, r in brackets(rungs):
        ask, bid, _ = quotes[r["ticker"]]
        m = ask + (bid or 0)  # half-cents
        n_b = 2 if b.strike_type == "between" else 1
        num += m * covered_ints(b, lo, hi) * (2 // n_b)
        den += m
    if den == 0:
        return 0
    return min(PPM, mul_div(PPM, num, 2 * den))


def rung_prob_ppm(ticker: str, rungs: list[dict], quotes: dict[str, tuple]) -> int:
    """Mid-implied probability of one rung, normalised by the sum of mids (used for the tail charge)."""
    den = sum(quotes[r["ticker"]][0] + (quotes[r["ticker"]][1] or 0) for r in rungs)
    a, b, _ = quotes[ticker]
    return mul_div(PPM, a + (b or 0), den) if den else 0


def top_bottom(rungs: list[dict]) -> tuple[dict, dict, int, int]:
    bs = brackets(rungs)
    (bb, rb), (bt, rt) = bs[0], bs[-1]
    return rb, rt, rep_tenths(bb), rep_tenths(bt)


# ---------------------------------------------------------------- point-in-time quotes
def candle_at(rung: dict, t: int) -> tuple[int, int | None, int] | None:
    """(ask_cents, bid_cents, candle_end) of the last candle ending at or before t; None if none or no ask.
    Candles after t are never read (I13)."""
    best = None
    for c in rung["candles"]:
        if c[0] <= t and (best is None or c[0] > best[0]):
            best = c
    if best is None or best[1] is None:
        return None
    return best[1], best[2], best[0]


def offer_ok(q: tuple | None) -> bool:
    """wi.eval.ladder.offer_status on the cent values: no ask, or ask >= 99 with bid < 90 -> no offer."""
    if q is None:
        return False
    ask, bid, ts = q
    return _ladder_mod().offer_status((ask / 100, float("nan") if bid is None else bid / 100, ts)) == "ok"


def quotes_at(rungs: list[dict], t: int) -> dict[str, tuple] | None:
    """Ask/bid for every rung at time t, or None if any rung has no quote (the ladder cannot be priced)."""
    out = {}
    for r in rungs:
        q = candle_at(r, t)
        if q is None:
            return None
        out[r["ticker"]] = q
    return out


def book_at(rung: dict, t: int, max_age: int) -> tuple[int, list[tuple[int, int]]] | None:
    """Recorded snapshot with the largest ts <= t and t - ts <= max_age -> (ts, [(ask_cents, qty_centi)])."""
    best = None
    for ts, ob in rung.get("books", []):
        if ts <= t and t - ts <= max_age and (best is None or ts > best[0]):
            best = (ts, ob)
    if best is None:
        return None
    asks = _ladder_mod().book_yes_asks(best[1])  # YES ask = 1 - NO bid, sorted best first
    lv = []
    for px, q in asks:
        cents = round_half_away(int(Decimal(repr(px)) * 10_000), 100)
        centi = int(Decimal(repr(q)) * 100)  # floor to whole centi
        if 1 <= cents <= 99 and centi > 0:
            lv.append((cents, centi))
    return best[0], sorted(lv)


def fill_rung(need: int, rung: dict, t: int, st_params: dict) -> dict:
    """Paper fill for one rung at decision time t. Returns source, snapshotTs, filled, costCents, feeCents,
    depthCenti, askCents. Book levels are floored to CONTRACT_STEP (fractional contracts unconfirmed)."""
    step, band = st_params["step"], st_params["band"]
    bk = book_at(rung, t, st_params["maxAge"])
    if bk is not None:
        snap_ts, lv = bk
        if not lv:
            return {"source": "book", "snapshotTs": snap_ts, "filled": 0, "costCents": 0, "feeCents": 0,
                    "depthCenti": 0, "askCents": 0}
        best = lv[0][0]
        band_lv = [(px, (q // step) * step) for px, q in lv if px <= best + band]
        depth = sum(q for _, q in band_lv)
        got, cost, used = 0, 0, []
        for px, q in band_lv:
            if got >= need:
                break
            take = min(q, need - got)
            if take:
                got += take
                cost += take * px // 100  # take is a multiple of 100 centi, so exact cents
                used.append((take, px))
        return {"source": "book", "snapshotTs": snap_ts, "filled": got, "costCents": cost,
                "feeCents": fee_cents(used), "depthCenti": depth, "askCents": best}
    q = candle_at(rung, t)
    if not offer_ok(q):
        return {"source": "candle", "snapshotTs": q[2] if q else 0, "filled": 0, "costCents": 0, "feeCents": 0,
                "depthCenti": 0, "askCents": q[0] if q else 0}
    ask, _, cts = q
    cap = (st_params["candleCap"] // step) * step
    got = min(need, cap)
    return {"source": "candle", "snapshotTs": cts, "filled": got, "costCents": got * ask // 100,
            "feeCents": fee_cents([(got, ask)]) if got else 0, "depthCenti": cap, "askCents": ask}


# ---------------------------------------------------------------- handlers
def hkey(series: str, day: int) -> str:
    return f"{series}:{day}"


def h_hedge_decision(st: dict, ts: int, p: dict) -> None:
    k = hkey(p["series"], p["day"])
    if k in st["hedges"]:
        raise Revert("HedgeExists")
    if p["decisionTs"] != p["closeTs"] - P(st, "hedgeLeadS"):
        raise Revert("BadDecisionTs")
    if ts < p["decisionTs"]:
        raise Revert("TooEarly")
    if p["source"] not in ("book", "candle", "mixed"):
        raise Revert("BadSource")
    if p["snapshotTs"] > p["decisionTs"]:
        raise Revert("LookAhead")  # I13
    step = P(st, "contractStepCenti")
    for r in p["rungs"]:
        if r["needCenti"] < 0 or r["needCenti"] % step or r["depthCenti"] < 0:
            raise Revert("BadNeed", r["ticker"])
    st["hedges"][k] = {"decision": p, "fill": None, "settled": None, "decidedAt": ts}


def h_hedge_filled(st: dict, ts: int, p: dict) -> None:
    hd = st["hedges"].get(hkey(p["series"], p["day"]))
    if hd is None or hd["fill"] is not None:
        raise Revert("NoDecision")
    dec = hd["decision"]["rungs"]
    if [r["ticker"] for r in p["rungs"]] != [r["ticker"] for r in dec]:
        raise Revert("RungMismatch")
    cost = short = 0
    for f, d in zip(p["rungs"], dec):
        if f["filledCenti"] < 0 or f["filledCenti"] > d["needCenti"] or f["filledCenti"] > d["depthCenti"]:
            raise Revert("FillBeyondDepth", f["ticker"])  # I14 / C6
        cost += (f["costCents"] + f["feeCents"]) * 10_000
        short += d["needCenti"] - f["filledCenti"]
    if cost != p["costE6"] or short != p["shortfallCenti"]:
        raise Revert("BadHedgeCost")
    house = st["world"]["roles"]["house"]
    d = str(p["day"])
    if st["house"]["ledger"].get(d, 0) < cost:
        raise Revert("HouseUnfunded", f"day {d}")
    st["bal"][house] -= cost
    st["house"]["ledger"][d] -= cost
    add(st["bal"], "@kalshi", cost)
    hd["fill"] = p


def h_hedge_settled(st: dict, ts: int, p: dict) -> None:
    hd = st["hedges"].get(hkey(p["series"], p["day"]))
    if hd is None or hd["fill"] is None or hd["settled"] is not None:
        raise Revert("NotFilled")
    if ts < hd["decision"]["closeTs"]:
        raise Revert("TooEarly")
    fills = hd["fill"]["rungs"]
    if [(r["ticker"], r["filledCenti"]) for r in p["rungs"]] != [(r["ticker"], r["filledCenti"]) for r in fills]:
        raise Revert("RungMismatch")
    pay = 0
    for r in p["rungs"]:
        if r["result"] not in ("yes", "no"):
            raise Revert("BadResult")
        if r["result"] == "yes":
            pay += r["filledCenti"] * 10_000
    if pay != p["payoutE6"]:
        raise Revert("BadHedgePayout")
    house = st["world"]["roles"]["house"]
    st["bal"]["@kalshi"] = st["bal"].get("@kalshi", 0) - pay
    add(st["bal"], house, pay)
    add(st["house"]["ledger"], str(p["day"]), pay)
    hd["settled"] = p


# ---------------------------------------------------------------- commands
def hedge_params(st: dict) -> dict:
    return {"step": P(st, "contractStepCenti"), "band": P(st, "bookBandCents"), "maxAge": P(st, "bookMaxAgeS"),
            "candleCap": P(st, "candleCapCenti")}


def plan_hedge(st: dict, series: str, day: int, rungs: list[dict], needs: dict[str, int]) -> dict:
    """Decision + fills for one (series, day) at T = close_time - 24 h, reading nothing after T."""
    close_ts = max(r["close_ts"] for r in rungs)
    t = close_ts - P(st, "hedgeLeadS")
    prm = hedge_params(st)
    rows = []
    for b, r in brackets(rungs):
        need = needs.get(r["ticker"], 0)
        f = fill_rung(need, r, t, prm) if need else {"source": "none", "snapshotTs": 0, "filled": 0, "costCents": 0,
                                                     "feeCents": 0, "depthCenti": 0, "askCents": 0}
        rows.append((r, need, f))
    srcs = {f["source"] for _, n, f in rows if n}
    source = srcs.pop() if len(srcs) == 1 else ("mixed" if srcs else "candle")
    snap = max([f["snapshotTs"] for _, n, f in rows if n] or [0])
    decision = {"series": series, "day": day, "decisionTs": t, "closeTs": close_ts, "source": source,
                "snapshotTs": snap,
                "rungs": [{"ticker": r["ticker"], "needCenti": n, "depthCenti": f["depthCenti"],
                           "askCents": f["askCents"]} for r, n, f in rows]}
    fill = {"series": series, "day": day,
            "rungs": [{"ticker": r["ticker"], "filledCenti": f["filled"], "costCents": f["costCents"],
                       "feeCents": f["feeCents"]} for r, n, f in rows],
            "costE6": sum((f["costCents"] + f["feeCents"]) * 10_000 for _, _, f in rows),
            "shortfallCenti": sum(n - f["filled"] for _, n, f in rows)}
    return {"decision": decision, "fill": fill, "decisionTs": t}


def execute_hedge(led, ts: int, plan: dict) -> None:
    led.emit(ts, "HedgeDecision", plan["decision"])
    led.emit(ts, "HedgeFilled", plan["fill"])


def settle_hedge(led, ts: int, series: str, day: int, rungs: list[dict]) -> int:
    hd = led.state["hedges"][hkey(series, day)]
    res = {r["ticker"]: r["result"] for r in rungs}
    out = [{"ticker": f["ticker"], "result": res[f["ticker"]], "filledCenti": f["filledCenti"]}
           for f in hd["fill"]["rungs"]]
    pay = sum(r["filledCenti"] * 10_000 for r in out if r["result"] == "yes")
    led.emit(ts, "HedgeSettled", {"series": series, "day": day, "rungs": out, "payoutE6": pay})
    return pay
