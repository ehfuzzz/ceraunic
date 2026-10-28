"""RFQ for bespoke residuals: one-way request, firm signed maker quotes, best price wins, no last look,
maker margin pays the complement (docs/SPEC.md section 10.1).
"""
from __future__ import annotations

from eth_abi import encode as abi_encode
from eth_utils import keccak

from .auction import record_fill
from .eip712 import b32, hx, rfq_digest
from .policy import policy_domain_args
from .state import P, Revert, add, dkey, is_house
from .units import TICK, UNIT


def request_id(requester: str, market: str, requester_long: bool, qty: int, window_end: int, n: int) -> str:
    return hx(keccak(abi_encode(["address", "bytes32", "bool", "uint128", "uint64", "uint256"],
                                [requester, b32(market), requester_long, qty, window_end, n])))


def best_quote(st: dict, rid: str) -> str | None:
    """Winning digest at windowEnd: taker long -> lowest tick, taker short -> highest; ties -> earlier response."""
    req = st["rfq"]["requests"][rid]
    qs = [(d, q) for d, q in st["rfq"]["quotes"].items() if q["requestId"] == rid]
    if not qs:
        return None
    key = (lambda dq: (dq[1]["tick"], dq[1]["seq"])) if req["requesterLong"] else \
        (lambda dq: (-dq[1]["tick"], dq[1]["seq"]))
    return min(qs, key=key)[0]


def h_rfq_requested(st: dict, ts: int, p: dict) -> None:
    m = st["markets"].get(p["market"])
    if m is None or p["qty"] < 1 or p["windowEnd"] < ts or p["windowEnd"] >= m["cutoff"]:
        raise Revert("BadRfq")
    if p["requestId"] in st["rfq"]["requests"]:
        raise Revert("RfqExists")
    if p["requestId"] != request_id(p["requester"], p["market"], p["requesterLong"], p["qty"], p["windowEnd"],
                                    st["rfq"]["count"]):
        raise Revert("BadRequestId")
    st["rfq"]["count"] += 1
    st["rfq"]["requests"][p["requestId"]] = {k: v for k, v in p.items() if k != "requestId"} | {"at": ts}


def h_rfq_quoted(st: dict, ts: int, p: dict) -> None:
    req = st["rfq"]["requests"].get(p["requestId"])
    if req is None:
        raise Revert("NoRfq")
    if ts > req["windowEnd"]:
        raise Revert("WindowClosed")
    if p["maker"] not in st["world"]["roles"]["rfqMakers"]:
        raise Revert("NotMaker")
    if not 1 <= p["tick"] <= 99 or p["maxQty"] < 1 or p["validUntil"] < req["windowEnd"]:
        raise Revert("BadRfqQuote")
    cid, vc = policy_domain_args(st)
    d = rfq_digest({"requestId": p["requestId"], "market": req["market"], "maker": p["maker"],
                    "taker": req["requester"], "takerLong": req["requesterLong"], "tick": p["tick"],
                    "maxQty": p["maxQty"], "validUntil": p["validUntil"], "nonce": p["nonce"]}, cid, vc)
    if d != p["digest"] or d in st["rfq"]["quotes"]:
        raise Revert("BadDigest")
    st["rfq"]["quotes"][d] = {k: v for k, v in p.items() if k != "digest"} | {
        "market": req["market"], "taker": req["requester"], "takerLong": req["requesterLong"],
        "seq": len(st["rfq"]["quotes"]), "at": ts}


def h_margin_deposited(st: dict, ts: int, p: dict) -> None:
    if p["amount"] == 0:
        raise Revert("ZeroAmount")
    if st["bal"].get(p["maker"], 0) < p["amount"]:
        raise Revert("InsufficientBalance")
    if is_house(st, p["maker"]) and st["house"]["free"] < p["amount"]:
        raise Revert("HouseFloat")
    st["bal"][p["maker"]] -= p["amount"]
    if is_house(st, p["maker"]):
        st["house"]["free"] -= p["amount"]
    add(st["pm"]["margin"], p["maker"], p["amount"])


def h_margin_withdrawn(st: dict, ts: int, p: dict) -> None:
    if p["amount"] == 0 or st["pm"]["margin"].get(p["maker"], 0) < p["amount"]:
        raise Revert("InsufficientMargin")
    st["pm"]["margin"][p["maker"]] -= p["amount"]
    add(st["bal"], p["maker"], p["amount"])
    if is_house(st, p["maker"]):
        st["house"]["free"] += p["amount"]


def h_rfq_accepted(st: dict, ts: int, p: dict) -> None:
    q = st["rfq"]["quotes"].get(p["digest"])
    if q is None:
        raise Revert("BadSignature")
    req = st["rfq"]["requests"][q["requestId"]]
    if (p["market"], p["taker"], p["maker"], p["takerLong"], p["tick"]) != (q["market"], q["taker"], q["maker"],
                                                                         q["takerLong"], q["tick"]):
        raise Revert("QuoteMismatch")
    m = st["markets"][p["market"]]
    if ts < req["windowEnd"]:
        raise Revert("WindowOpen")
    if best_quote(st, q["requestId"]) != p["digest"]:
        raise Revert("NotBestQuote")
    if ts > q["validUntil"] or ts >= m["cutoff"]:
        raise Revert("QuoteExpired")
    if q["nonce"] < st["rfq"]["nonceFloor"].get(q["maker"], 0):
        raise Revert("NonceCancelled")
    filled = st["rfq"]["filled"].get(p["digest"], 0)
    if p["qty"] < 1 or filled + p["qty"] > q["maxQty"]:
        raise Revert("OverFill")
    taker_pays = p["qty"] * (p["tick"] if p["takerLong"] else 100 - p["tick"]) * TICK
    maker_pays = p["qty"] * UNIT - taker_pays
    fee = p["qty"] * P(st, "rfqFeePerUnit")
    if st["bal"].get(p["taker"], 0) < taker_pays + fee:
        raise Revert("InsufficientBalance")
    if st["pm"]["margin"].get(p["maker"], 0) < maker_pays:
        raise Revert("InsufficientMargin")
    day = dkey(m["day"])
    if is_house(st, p["maker"]) and st["house"]["ledger"].get(day, 0) < maker_pays:
        raise Revert("HouseUnfunded")
    # effects
    st["bal"][p["taker"]] -= taker_pays + fee
    add(st["bal"], "@treasury", fee)
    st["pm"]["margin"][p["maker"]] -= maker_pays
    if is_house(st, p["maker"]):  # the day reimburses the house float it used as margin
        st["house"]["ledger"][day] -= maker_pays
        st["house"]["free"] += maker_pays
    m["collateral"] += p["qty"] * UNIT
    m["collateralIn"] += p["qty"] * UNIT
    record_fill(st, p["market"], p["taker"], p["takerLong"], p["qty"], taker_pays)
    record_fill(st, p["market"], p["maker"], not p["takerLong"], p["qty"], maker_pays)
    st["rfq"]["filled"][p["digest"]] = filled + p["qty"]


# ---------------------------------------------------------------- commands
def request(led, ts: int, requester: str, market: str, requester_long: bool, qty: int, window_end: int) -> str:
    st = led.state
    rid = request_id(requester, market, requester_long, qty, window_end, st["rfq"]["count"])
    led.emit(ts, "RfqRequested", {"requestId": rid, "requester": requester, "market": market,
                                  "requesterLong": requester_long, "qty": qty, "windowEnd": window_end})
    return rid


def respond(led, ts: int, rid: str, maker: str, tick: int, max_qty: int, valid_until: int, nonce: int) -> str:
    st = led.state
    req = st["rfq"]["requests"][rid]
    cid, vc = policy_domain_args(st)
    d = rfq_digest({"requestId": rid, "market": req["market"], "maker": maker, "taker": req["requester"],
                    "takerLong": req["requesterLong"], "tick": tick, "maxQty": max_qty, "validUntil": valid_until,
                    "nonce": nonce}, cid, vc)
    led.emit(ts, "RfqQuoted", {"requestId": rid, "digest": d, "maker": maker, "tick": tick, "maxQty": max_qty,
                               "validUntil": valid_until, "nonce": nonce})
    return d


def accept(led, ts: int, digest: str, qty: int) -> None:
    q = led.state["rfq"]["quotes"][digest]
    led.emit(ts, "RfqAccepted", {"digest": digest, "market": q["market"], "taker": q["taker"], "maker": q["maker"],
                                 "takerLong": q["takerLong"], "tick": q["tick"], "qty": qty})


def deposit_margin(led, ts: int, maker: str, amount: int) -> None:
    led.emit(ts, "MarginDeposited", {"maker": maker, "amount": amount})


def withdraw_margin(led, ts: int, maker: str, amount: int) -> None:
    if amount:
        led.emit(ts, "MarginWithdrawn", {"maker": maker, "amount": amount})


def venue_label(st: dict, rid: str) -> str:
    """SPEC 10.1 step 5: 'single-responder' while only the house has quoted this request."""
    house = st["world"]["roles"]["house"]
    makers = {q["maker"] for q in st["rfq"]["quotes"].values() if q["requestId"] == rid}
    return "single-responder" if makers <= {house} else "multi-responder"
