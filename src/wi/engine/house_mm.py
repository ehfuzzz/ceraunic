"""House market-maker, acting as the pool's agent (docs/SPEC.md sections 6.2, 6.3, 6.6, 8.6).

Every step is idempotent per tick key (day, step): it inspects the state for what it already did and
does only the rest, so a retried or duplicated scheduler tick never places a second order, a second
funding or a second hedge (that would deploy pool capital twice).

Steps for climate day D:
  book(D)    before houseCutoff: fund + place one residual-leg order per house-path policy, then the
             quote schedule (<= houseLevels per side) on each basis market, sized by cap headroom
  bind(D)    after clear, before bindBy: claim every order on the day's basis markets, bind each policy
             to its residual-leg order (downsizing) or to 0
  hedge(D)   at T = close_time - 24 h: aggregate bound station legs per series, paper-fill, fund, record
  settle(D)  after Kalshi result: HedgeSettled
  ret(D)     after settlement: return everything the day left with the house (HouseReturned)
"""
from __future__ import annotations

from . import auction, hedge, margin, pool, pricing
from .state import P, dkey, is_house, pos_key
from .units import TICK


def _house(st: dict) -> str:
    return st["world"]["roles"]["house"]


def day_policies(st: dict, day: int) -> list[tuple[int, dict]]:
    return sorted(((int(k), v) for k, v in st["policies"].items() if v["day"] == day), key=lambda kv: kv[0])


def _house_orders(st: dict, market: str) -> list[dict]:
    return [st["orders"][str(i)] for i in st["markets"][market]["orderIds"]
            if is_house(st, st["orders"][str(i)]["trader"])]


def residual_leg_order(st: dict, policy_id: int) -> int:
    for k, o in st["orders"].items():
        if o["policyId"] == policy_id:
            return int(k)
    return 0


# ---------------------------------------------------------------- book(D)
def book(led, ts: int, day: int, basis_markets: list[str], prehistory: dict[str, list] | None = None) -> None:
    st = led.state
    house = _house(st)
    # 1. residual legs for bought policies that carry one and have no order yet
    legs = []
    for pid, pol in day_policies(st, day):
        if pol["status"] == "Bought" and pol["residualQty"] and not residual_leg_order(st, pid):
            is_bid = pol["isLong"]  # call (business long) -> house bids h; put -> house offers h
            legs.append((pid, pol["residualMarket"], is_bid, pol["residualTick"], pol["residualQty"]))
    need = sum(auction.escrow_for(b, t, q, P(st, "auctionFeePerUnit")) for _, _, b, t, q in legs)
    pool.fund_house(led, ts, day, need)
    for pid, mk, b, t, q in legs:
        auction.place_order(led, ts, mk, house, b, t, q, policy_id=pid)
    # 2. quote schedule per basis market, once
    plan = []
    exp = margin.exposures(st)
    for mk in basis_markets:
        if any(o["policyId"] == 0 for o in _house_orders(st, mk)):
            continue
        m = st["markets"][mk]
        hist = pricing.basis_history(st, m["indexId"], ts, (prehistory or {}).get(m["indexId"]))
        rt = pricing.residual_ticks(st, pricing.fair_stats([v for _, v in hist], m["hi"]))
        levels = pricing.schedule_levels(st, rt)
        room = margin.headroom(st, m["indexId"], m["day"], exp)
        share = room // max(1, len(levels))
        for is_bid, t in levels:
            worst = (t if is_bid else 100 - t) * TICK
            qty = min(P(st, "houseLevelMaxQty"), share // worst)
            if qty > 0:
                plan.append((mk, is_bid, t, qty))
                esc = auction.escrow_for(is_bid, t, qty, P(st, "auctionFeePerUnit"))
                for g in margin._groups(st, m["indexId"], m["day"]):  # later markets see this exposure
                    exp[g] = exp.get(g, 0) + esc
    need = sum(auction.escrow_for(b, t, q, P(st, "auctionFeePerUnit")) for _, b, t, q in plan)
    pool.fund_house(led, ts, day, need)
    for mk, b, t, q in plan:
        auction.place_order(led, ts, mk, house, b, t, q)


# ---------------------------------------------------------------- bind(D)
def bind(led, ts: int, day: int, basis_markets: list[str]) -> None:
    from . import policy

    st = led.state
    for mk in basis_markets:
        m = st["markets"][mk]
        if m["cleared"] is None:
            auction.clear_market(led, ts, mk)
        auction.claim_all(led, ts, mk)
    for pid, pol in day_policies(st, day):
        if pol["status"] == "Bought":
            policy.bind(led, ts, pid, residual_leg_order(st, pid))


# ---------------------------------------------------------------- hedge(D)
def station_series(st: dict, market: str) -> str | None:
    """Kalshi series that hedges the market's station leg: the temperature ladder of the settlement station, or for
    a CLI precipitation index the station's daily rain binary (world `rainSeries`, 13-RAIN)."""
    idx = st["indices"][st["markets"][market]["indexId"]]
    key = "rainSeries" if hedge.is_rain_index(idx) else "hedgeableSeries"
    return st["world"].get(key, {}).get(idx["station"])


def hedge_day(led, ts: int, day: int, series: str, rungs: list[dict]) -> dict | None:
    st = led.state
    if f"{series}:{day}" in st["hedges"]:
        return None
    needs = []
    for pid, pol in day_policies(st, day):
        if pol["status"] == "Bound" and pol["boundUnits"] and station_series(st, pol["market"]) == series:
            m = st["markets"][pol["market"]]
            if hedge.is_rain_index(st["indices"][m["indexId"]]):
                needs.append(hedge.rain_needs(pol["boundUnits"], pol["isLong"], rungs))
            else:
                needs.append(hedge.replicate(pol["boundUnits"], m["lo"], m["hi"], pol["isLong"], rungs))
    if not needs:
        return None
    agg = hedge.aggregate(needs, P(st, "contractStepCenti"))
    plan = hedge.plan_hedge(st, series, day, rungs, agg)
    if ts < plan["decisionTs"]:
        raise ValueError("hedge called before its decision time")
    pool.fund_house(led, ts, day, plan["fill"]["costE6"])
    hedge.execute_hedge(led, ts, plan)
    return plan


def settle_hedge(led, ts: int, day: int, series: str, rungs: list[dict]) -> int | None:
    hd = led.state["hedges"].get(f"{series}:{day}")
    if hd is None or hd["settled"] is not None:
        return None
    return hedge.settle_hedge(led, ts, series, day, rungs)


# ---------------------------------------------------------------- ret(D)
def ready_to_return(st: dict, day: int) -> bool:
    house = _house(st)
    d = dkey(day)
    if st["pool"]["houseDone"].get(d):
        return False
    if st["pool"]["deployedByDay"].get(d, 0) == 0 and st["house"]["ledger"].get(d, 0) == 0:
        return False
    for mk, m in st["markets"].items():
        if m["day"] != day:
            continue
        if any(not st["orders"][str(i)]["claimed"] for i in m["orderIds"]):
            return False
        ps = st["pos"].get(pos_key(mk, house))
        if ps and not ps["done"]:
            return False
    for k, h in st["hedges"].items():
        if h["decision"]["day"] == day and h["settled"] is None:
            return False
    return True


def ret(led, ts: int, day: int) -> int | None:
    if not ready_to_return(led.state, day):
        return None
    return pool.return_from_house(led, ts, day)
