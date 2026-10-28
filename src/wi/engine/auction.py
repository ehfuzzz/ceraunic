"""Residual batch auction (docs/SPEC.md section 5): placement + escrow, clear, O(1) claim.

The clearing rule is imported from `wi.auction.clear` (Phase 4). It was read on 2026-09-30 and is the
SPEC 5 rule line for line (V max -> I min -> lower midpoint, D[100] = S[0] = 0, tb/mb/to/mo), so it is
used as-is, not forked. The engine adds what that function leaves out: per-order `ahead`, the
per-unit auction fee (escrowed at placement, charged on fills at claim), and the O(1) fill formula
that the chain uses at claim. At clear time the O(1) fills are checked against clear()'s fills.
"""
from __future__ import annotations

from wi.auction.clear import Order as ClearOrder
from wi.auction.clear import clear as clear_book

from .state import P, Revert, add, is_house, pos_key
from .units import TICK, UNIT, check_tick

MAX_ORDER_QTY = 2**64 - 1  # BatchAuction.MAX_ORDER_QTY


# ---------------------------------------------------------------- pure math (shared with fixtures)
def escrow_for(is_bid: bool, tick: int, qty: int, fee_per_unit: int) -> int:
    check_tick(tick)
    return qty * ((tick if is_bid else 100 - tick) * TICK + fee_per_unit)


def slice_fill(m: int, ahead: int, qty: int) -> int:
    return 0 if m <= ahead else min(m - ahead, qty)


def fill_o1(is_bid: bool, tick: int, qty: int, ahead: int, c: dict) -> int:
    """SPEC 5 fill per order, O(1), from the cleared (tb, mb, to, mo)."""
    if c["qStar"] == 0:
        return 0
    if is_bid:
        return qty if tick > c["tb"] else slice_fill(c["mb"], ahead, qty) if tick == c["tb"] else 0
    return qty if tick < c["to"] else slice_fill(c["mo"], ahead, qty) if tick == c["to"] else 0


def claim_amounts(is_bid: bool, tick: int, qty: int, ahead: int, escrow: int, fee_per_unit: int,
                  c: dict) -> dict:
    f = fill_o1(is_bid, tick, qty, ahead, c)
    cost = f * (c["pStar"] if is_bid else 100 - c["pStar"]) * TICK
    fee = f * fee_per_unit
    refund = escrow - cost - fee
    if refund < 0:
        raise AssertionError("escrow does not cover cost + fee")
    return {"fill": f, "cost": cost, "fee": fee, "refund": refund}


def settle_book(orders: list[dict], fee_per_unit: int = 0) -> dict:
    """Whole book in placement order -> clearing summary and per-order amounts.

    orders: [{"isBid", "tick", "qty"}]. Used by the parity fixtures and by the tests; the reducer runs
    the same functions one event at a time."""
    queued: dict[tuple[bool, int], int] = {}
    rows = []
    for o in orders:
        k = (o["isBid"], o["tick"])
        ahead = queued.get(k, 0)
        queued[k] = ahead + o["qty"]
        rows.append({**o, "ahead": ahead, "escrow": escrow_for(o["isBid"], o["tick"], o["qty"], fee_per_unit)})
    c = clear_summary(rows)
    for r in rows:
        r.update(claim_amounts(r["isBid"], r["tick"], r["qty"], r["ahead"], r["escrow"], fee_per_unit, c))
    return {**c, "orders": rows}


def clear_summary(rows: list[dict]) -> dict:
    """Run wi.auction.clear.clear and cross-check its fills with the O(1) claim formula."""
    r = clear_book([ClearOrder(i + 1, o["isBid"], o["tick"], o["qty"]) for i, o in enumerate(rows)])
    c = {"pStar": r.p_star, "qStar": r.q_star, "tb": r.tb, "to": r.to, "mb": r.mb, "mo": r.mo}
    for o, f in zip(rows, r.fills):
        if fill_o1(o["isBid"], o["tick"], o["qty"], o["ahead"], c) != f:
            raise AssertionError("O(1) fill disagrees with wi.auction.clear")
    return c


# ---------------------------------------------------------------- handlers
def h_order_placed(st: dict, ts: int, p: dict) -> None:
    m = st["markets"].get(p["market"])
    if m is None or not m["auctioned"]:
        raise Revert("NoBook", p["market"])
    if ts >= m["cutoff"]:
        raise Revert("AuctionClosed")
    house = is_house(st, p["trader"])
    if house and ts >= m["houseCutoff"]:
        raise Revert("HouseCutoff")
    check_tick(p["tick"])
    if p["qty"] < 1:
        raise Revert("ZeroQty")
    if p["qty"] > MAX_ORDER_QTY:
        raise Revert("BadOrder")  # BatchAuction 08-HARDEN #3: keeps Q* and level totals inside uint128
    if not house:  # BatchAuction 08-HARDEN #2: min escrow, public cap, per-address cap; house exempt
        if escrow_for(p["isBid"], p["tick"], p["qty"], P(st, "auctionFeePerUnit")) < P(st, "minOrderEscrowE6"):
            raise Revert("BelowMinEscrow")
        placed = [st["orders"][str(i)]["trader"] for i in m["orderIds"]]
        if sum(1 for t in placed if not is_house(st, t)) >= P(st, "maxOrders"):
            raise Revert("BookFull")
        if placed.count(p["trader"]) >= P(st, "maxOrdersPerTrader"):
            raise Revert("TraderOrderCap")
    if p["orderId"] != st["nextOrderId"]:
        raise Revert("BadOrderId")
    side = "b" if p["isBid"] else "o"
    t = str(p["tick"])
    if p["ahead"] != m["levels"][side].get(t, 0):
        raise Revert("BadAhead")
    fee = P(st, "auctionFeePerUnit")
    if p["escrow"] != escrow_for(p["isBid"], p["tick"], p["qty"], fee):
        raise Revert("BadEscrow")
    if p["policyId"]:
        pol = st["policies"].get(str(p["policyId"]))
        if pol is None or not house:
            raise Revert("BadPolicyLeg")
    if st["bal"].get(p["trader"], 0) < p["escrow"]:
        raise Revert("InsufficientBalance", p["trader"])
    day = str(m["day"])
    if house and st["house"]["ledger"].get(day, 0) < p["escrow"]:
        raise Revert("HouseUnfunded", f"day {day}")
    # effects
    st["bal"][p["trader"]] -= p["escrow"]
    if house:
        st["house"]["ledger"][day] -= p["escrow"]
    m["escrow"] += p["escrow"]
    add(m["levels"][side], t, p["qty"])
    m["orderIds"].append(p["orderId"])
    m["unclaimed"] += 1
    st["nextOrderId"] += 1
    st["orders"][str(p["orderId"])] = {
        "market": p["market"], "trader": p["trader"], "isBid": p["isBid"], "tick": p["tick"], "qty": p["qty"],
        "ahead": p["ahead"], "escrow": p["escrow"], "feePerUnit": fee, "policyId": p["policyId"],
        "claimed": False, "bound": False, "placedAt": ts,
    }


def h_auction_cleared(st: dict, ts: int, p: dict) -> None:
    m = st["markets"].get(p["market"])
    if m is None or not m["auctioned"]:
        raise Revert("NoBook")
    if ts < m["cutoff"]:
        raise Revert("TooEarly")
    if m["cleared"] is not None:
        raise Revert("AlreadyCleared")
    rows = [st["orders"][str(i)] for i in m["orderIds"]]
    c = clear_summary(rows)
    for k, v in c.items():
        if p[k] != v:
            raise Revert("BadClear", k)
    moved = c["qStar"] * UNIT
    if m["escrow"] < moved:
        raise AssertionError("escrow below Q* x UNIT")
    m["escrow"] -= moved
    m["collateral"] += moved
    m["collateralIn"] += moved
    m["cleared"] = dict(c) | {"at": ts}


def h_order_claimed(st: dict, ts: int, p: dict) -> None:
    o = st["orders"].get(str(p["orderId"]))
    if o is None:
        raise Revert("NoOrder")
    m = st["markets"][o["market"]]
    if m["cleared"] is None:
        raise Revert("NotCleared")
    if o["claimed"]:
        raise Revert("AlreadyClaimed")
    a = claim_amounts(o["isBid"], o["tick"], o["qty"], o["ahead"], o["escrow"], o["feePerUnit"], m["cleared"])
    for k, v in a.items():
        if p[k] != v:
            raise Revert("BadClaim", k)
    # effects
    o["claimed"] = True
    o["fill"] = a["fill"]
    m["unclaimed"] -= 1
    m["escrow"] -= a["refund"] + a["fee"]
    add(st["bal"], o["trader"], a["refund"])
    add(st["bal"], "@treasury", a["fee"])
    if is_house(st, o["trader"]):
        add(st["house"]["ledger"], str(m["day"]), a["refund"])
    if a["fill"]:
        record_fill(st, o["market"], o["trader"], o["isBid"], a["fill"], a["cost"])


def record_fill(st: dict, market: str, trader: str, is_long: bool, qty: int, cost: int) -> None:
    """PolicyManager.recordFill: long += fill or short += fill, paid += cost."""
    k = pos_key(market, trader)
    ps = st["pos"].get(k)
    if ps is None:
        ps = st["pos"][k] = {"long": 0, "short": 0, "paid": 0, "done": False}
        st["markets"][market]["traders"].append(trader)
    if ps["done"]:
        raise Revert("PositionClosed")
    ps["long" if is_long else "short"] += qty
    ps["paid"] += cost


# ---------------------------------------------------------------- commands
def place_order(led, ts: int, market: str, trader: str, is_bid: bool, tick: int, qty: int,
                policy_id: int = 0) -> int:
    st = led.state
    m = st["markets"][market]
    oid = st["nextOrderId"]
    side = "b" if is_bid else "o"
    led.emit(ts, "OrderPlaced", {"orderId": oid, "market": market, "trader": trader, "isBid": is_bid, "tick": tick,
                                 "qty": qty, "ahead": m["levels"][side].get(str(tick), 0),
                                 "escrow": escrow_for(is_bid, tick, qty, P(st, "auctionFeePerUnit")),
                                 "policyId": policy_id})
    return oid


def clear_market(led, ts: int, market: str) -> dict:
    st = led.state
    m = st["markets"][market]
    c = clear_summary([st["orders"][str(i)] for i in m["orderIds"]])
    led.emit(ts, "AuctionCleared", {"market": market, **c})
    return c


def claim_order(led, ts: int, order_id: int) -> dict:
    st = led.state
    o = st["orders"][str(order_id)]
    m = st["markets"][o["market"]]
    a = claim_amounts(o["isBid"], o["tick"], o["qty"], o["ahead"], o["escrow"], o["feePerUnit"], m["cleared"])
    led.emit(ts, "OrderClaimed", {"orderId": order_id, **a})
    return a


def claim_all(led, ts: int, market: str) -> None:
    for oid in list(led.state["markets"][market]["orderIds"]):
        if not led.state["orders"][str(oid)]["claimed"]:
            claim_order(led, ts, oid)


def order_fill_view(st: dict, order_id: int) -> int:
    """BatchAuction.fillOf: the O(1) fill of a cleared order, claimed or not."""
    o = st["orders"][str(order_id)]
    c = st["markets"][o["market"]]["cleared"]
    if c is None:
        raise Revert("NotCleared")
    return fill_o1(o["isBid"], o["tick"], o["qty"], o["ahead"], c)
