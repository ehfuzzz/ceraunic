"""PolicyManager mirror: signed quotes, purchase, bind + downsizing, settlement, void, strips, and
position settlement / refund (docs/SPEC.md sections 6, 10.2, 10.3).
"""
from __future__ import annotations

from . import pool as poolmod
from .eip712 import quote_digest
from .oracle import get_final, is_void
from .state import P, Revert, add, dkey, is_house, pos_key
from .units import BPS, UNIT, L, bps, mul_div

ZERO32 = "0x" + "00" * 32


def policy_domain_args(st: dict) -> tuple[int, str]:
    d = st["world"].get("policyDomain", {})
    from .eip712 import SIM_CHAIN_ID, SIM_POLICY

    return d.get("chainId", SIM_CHAIN_ID), d.get("verifyingContract", SIM_POLICY)


# ---------------------------------------------------------------- pure math (shared with fixtures)
def bind_amounts(units: int, premium: int, fee: int, h: int, fill: int, senior_bps: int) -> dict:
    """SPEC 6.3 binding and downsizing. h = 0 means no residual leg (residualOrderId = 0)."""
    bound = units if h == 0 else mul_div(units, fill, h)
    if bound > units:
        bound = units  # a fill never exceeds h, so this cannot trigger; kept as a hard bound (I10)
    kept_premium = mul_div(premium, bound, units)
    refund = premium - kept_premium
    kept_fee = mul_div(fee, bound, units)
    to_pool = kept_premium - kept_fee
    senior = mul_div(to_pool, senior_bps, BPS)
    return {"boundUnits": bound, "refund": refund, "keptFee": kept_fee, "toPool": to_pool,
            "seniorPremium": senior, "juniorPremium": to_pool - senior}


def policy_payout(bound_units: int, is_long: bool, x: int, lo: int, hi: int) -> int:
    lx = L(x, lo, hi)
    return bound_units * (lx if is_long else UNIT - lx)


def quote_identity(st: dict, units: int, station_leg: int, residual_leg: int, tail: int) -> dict:
    """Premium and fee from the itemised components (SPEC 6.6)."""
    notional = units * UNIT
    risk = bps(notional, P(st, "riskLoadBps"))
    nfee = bps(notional, P(st, "feeNotionalBps"))
    fee = nfee + bps(risk, P(st, "feeMarginBps"))
    premium = max(station_leg + residual_leg + tail + risk + nfee, fee + P(st, "minPremiumE6"))
    return {"riskMargin": risk, "notionalFee": nfee, "fee": fee, "premium": premium}


# ---------------------------------------------------------------- handlers
def h_quote_issued(st: dict, ts: int, p: dict) -> None:
    m = st["markets"].get(p["market"])
    if m is None:
        raise Revert("NoMarket")
    if p["digest"] in st["quotes"]:
        raise Revert("QuoteExists")
    cid, vc = policy_domain_args(st)
    q = {k: p[k] for k in ("market", "buyer", "isLong", "units", "premium", "fee", "expiry", "nonce")}
    if quote_digest(q, cid, vc) != p["digest"]:
        raise Revert("BadDigest")
    if p["units"] < 1 or not (p["fee"] <= p["premium"] <= p["units"] * UNIT):
        raise Revert("BadQuote")
    if not (ts <= p["expiry"] <= m["saleCutoff"]):
        raise Revert("BadExpiry")
    if p["dataAsOf"] > ts:
        raise Revert("LookAhead")  # I13
    ident = quote_identity(st, p["units"], p["stationLeg"], p["residualLeg"], p["tail"])
    for k, v in ident.items():
        if p[k] != v:
            raise Revert("QuoteIdentity", k)
    if p["residualQty"]:
        rm = st["markets"].get(p["residualMarket"])
        if rm is None or not rm["auctioned"] or rm["day"] != m["day"] or not 1 <= p["residualTick"] <= 99:
            raise Revert("BadResidualLeg")
    elif p["residualTick"] != 0:
        raise Revert("BadResidualLeg")
    st["quotes"][p["digest"]] = {k: v for k, v in p.items() if k != "digest"} | {"issuedAt": ts, "used": False}


def h_policy_bought(st: dict, ts: int, p: dict) -> None:
    q = st["quotes"].get(p["digest"])
    if q is None:
        raise Revert("BadSignature")
    for k in ("market", "buyer", "isLong", "units", "premium", "fee"):
        if q[k] != p[k]:
            raise Revert("QuoteMismatch", k)
    if q["used"]:
        raise Revert("NonceUsed")
    quoter = st["world"]["roles"]["quoter"]
    nk = f"{quoter}:{q['nonce']}"
    if st["nonces"].get(nk):
        raise Revert("NonceUsed")
    if ts > q["expiry"]:
        raise Revert("QuoteExpired")
    m = st["markets"][p["market"]]
    if ts >= m["saleCutoff"]:
        raise Revert("SalesClosed")
    if p["policyId"] != st["nextPolicyId"]:
        raise Revert("BadPolicyId")
    if st["bal"].get(p["buyer"], 0) < p["premium"]:
        raise Revert("InsufficientBalance")
    poolmod.check_reserve(st, m["day"], p["units"] * UNIT)
    # effects
    st["bal"][p["buyer"]] -= p["premium"]
    st["pm"]["escrow"] += p["premium"]
    poolmod.reserve(st, m["day"], p["units"] * UNIT)
    q["used"] = True
    st["nonces"][nk] = True
    st["nextPolicyId"] += 1
    st["policies"][str(p["policyId"])] = {
        "buyer": p["buyer"], "market": p["market"], "isLong": p["isLong"], "units": p["units"], "boundUnits": 0,
        "premium": p["premium"], "fee": p["fee"], "status": "Bought", "day": m["day"], "digest": p["digest"],
        "residualMarket": q["residualMarket"], "residualQty": q["residualQty"], "residualTick": q["residualTick"],
        "boughtAt": ts,
    }


def h_policy_bound(st: dict, ts: int, p: dict) -> None:
    pol = st["policies"].get(str(p["policyId"]))
    if pol is None or pol["status"] != "Bought":
        raise Revert("NotBindable")
    m = st["markets"][pol["market"]]
    if is_void(st, m["indexId"], m["day"]):
        raise Revert("DayVoid")  # PolicyManager 08-HARDEN #4: an unbound policy on a void day refunds in full
    rid = p["residualOrderId"]
    if rid:
        o = st["orders"].get(str(rid))
        if o is None or not is_house(st, o["trader"]):
            raise Revert("NotHouseOrder")
        om = st["markets"][o["market"]]
        if om["cleared"] is None:
            raise Revert("NotCleared")
        if o["bound"]:
            raise Revert("OrderUsed")
        if om["day"] != pol["day"]:
            raise Revert("WrongDay")
        if ts >= m["bindBy"]:
            raise Revert("BindWindowClosed")
        from .auction import fill_o1

        h, fill = o["qty"], fill_o1(o["isBid"], o["tick"], o["qty"], o["ahead"], om["cleared"])
    else:
        h, fill = 0, 0
    a = bind_amounts(pol["units"], pol["premium"], pol["fee"], h, fill, P(st, "seniorPremiumBps"))
    for k, v in a.items():
        if p[k] != v:
            raise Revert("BadBind", k)
    # effects
    if rid:
        st["orders"][str(rid)]["bound"] = True
    day = pol["day"]
    st["pm"]["escrow"] -= pol["premium"]
    add(st["bal"], pol["buyer"], a["refund"])
    add(st["bal"], "@treasury", a["keptFee"])
    if a["toPool"]:
        poolmod.credit_premium(st, day, a["toPool"])
    pol.update({"boundUnits": a["boundUnits"], "keptFee": a["keptFee"], "toPool": a["toPool"],
                "residualOrderId": rid, "boundAt": ts})
    if a["boundUnits"] > 0:
        poolmod.release(st, day, (pol["units"] - a["boundUnits"]) * UNIT)
        pol["status"] = "Bound"
    else:
        poolmod.absorb_loss(st, day, pol["units"] * UNIT, 0, pol["buyer"])
        pol["status"] = "Settled"
        pol["payout"] = 0


def h_policy_settled(st: dict, ts: int, p: dict) -> None:
    pol = st["policies"].get(str(p["policyId"]))
    if pol is None or pol["status"] != "Bound":
        raise Revert("NotSettleable")
    m = st["markets"][pol["market"]]
    x = get_final(st, m["indexId"], m["day"])  # reverts NotFinal (I11)
    if p["x"] != x:
        raise Revert("BadX")
    payout = policy_payout(pol["boundUnits"], pol["isLong"], x, m["lo"], m["hi"])
    if p["payout"] != payout or payout > pol["boundUnits"] * UNIT:
        raise Revert("BadPayout")
    poolmod.check_absorb(st, pol["day"], pol["boundUnits"] * UNIT, payout)
    poolmod.absorb_loss(st, pol["day"], pol["boundUnits"] * UNIT, payout, pol["buyer"])
    pol.update({"status": "Settled", "payout": payout, "x": x, "settledAt": ts})


def h_policy_voided(st: dict, ts: int, p: dict) -> None:
    pol = st["policies"].get(str(p["policyId"]))
    if pol is None or pol["status"] not in ("Bought", "Bound"):
        raise Revert("NotVoidable")
    m = st["markets"][pol["market"]]
    if not is_void(st, m["indexId"], m["day"]):
        raise Revert("NotVoid")
    if pol["status"] == "Bound":
        refund = pol["toPool"]  # keptPremium - keptFee; the treasury fee is not refunded
        if p["refund"] != refund:
            raise Revert("BadRefund")
        poolmod.check_absorb(st, pol["day"], pol["boundUnits"] * UNIT, refund)
        poolmod.absorb_loss(st, pol["day"], pol["boundUnits"] * UNIT, refund, pol["buyer"])
    else:
        refund = pol["premium"]
        if p["refund"] != refund:
            raise Revert("BadRefund")
        poolmod.check_absorb(st, pol["day"], pol["units"] * UNIT, 0)
        st["pm"]["escrow"] -= refund
        add(st["bal"], pol["buyer"], refund)
        poolmod.absorb_loss(st, pol["day"], pol["units"] * UNIT, 0, pol["buyer"])
    pol.update({"status": "Voided", "refundOnVoid": refund, "voidedAt": ts})


def h_strip_opened(st: dict, ts: int, p: dict) -> None:
    if p["stripId"] != st["nextStripId"]:
        raise Revert("BadStripId")
    if p["indexId"] not in st["indices"] or p["lo"] >= p["hi"] or p["units"] < 1 or p["startDay"] > p["endDay"]:
        raise Revert("BadStrip")
    st["nextStripId"] += 1
    st["strips"][str(p["stripId"])] = {k: v for k, v in p.items() if k != "stripId"} | {"open": True}


def h_strip_closed(st: dict, ts: int, p: dict) -> None:
    s = st["strips"].get(str(p["stripId"]))
    if s is None or not s["open"]:
        raise Revert("NoStrip")
    s["open"] = False


def h_position_settled(st: dict, ts: int, p: dict) -> None:
    m = st["markets"].get(p["market"])
    if m is None:
        raise Revert("NoMarket")
    x = get_final(st, m["indexId"], m["day"])
    if m["unclaimed"]:
        raise Revert("OrdersUnclaimed")
    ps = st["pos"].get(pos_key(p["market"], p["trader"]))
    if ps is None or ps["done"]:
        raise Revert("NoPosition")
    lx = L(x, m["lo"], m["hi"])
    payout = ps["long"] * lx + ps["short"] * (UNIT - lx)
    if (p["x"], p["longQty"], p["shortQty"], p["payout"]) != (x, ps["long"], ps["short"], payout):
        raise Revert("BadPositionSettle")
    if payout > m["collateral"]:
        raise AssertionError("position payout exceeds market collateral (I5)")
    ps["done"] = True
    ps["payout"] = payout
    m["collateral"] -= payout
    m["paidOut"] += payout
    add(st["bal"], p["trader"], payout)
    if is_house(st, p["trader"]):
        add(st["house"]["ledger"], dkey(m["day"]), payout)


def h_position_refunded(st: dict, ts: int, p: dict) -> None:
    m = st["markets"].get(p["market"])
    if m is None or not is_void(st, m["indexId"], m["day"]):
        raise Revert("NotVoid")
    if m["unclaimed"]:
        raise Revert("OrdersUnclaimed")
    ps = st["pos"].get(pos_key(p["market"], p["trader"]))
    if ps is None or ps["done"]:
        raise Revert("NoPosition")
    if p["refund"] != ps["paid"] or ps["paid"] > m["collateral"]:
        raise Revert("BadRefund")
    ps["done"] = True
    ps["payout"] = ps["paid"]
    m["collateral"] -= ps["paid"]
    m["paidOut"] += ps["paid"]
    add(st["bal"], p["trader"], ps["paid"])
    if is_house(st, p["trader"]):
        add(st["house"]["ledger"], dkey(m["day"]), ps["paid"])


# ---------------------------------------------------------------- commands
def issue_quote(led, ts: int, comps: dict) -> str:
    """comps: market, buyer, isLong, units, expiry, nonce, stationLeg, residualLeg, tail, residualMarket,
    residualQty, residualTick, deltaPpm, dataAsOf (from pricing.price_policy)."""
    st = led.state
    ident = quote_identity(st, comps["units"], comps["stationLeg"], comps["residualLeg"], comps["tail"])
    q = {"market": comps["market"], "buyer": comps["buyer"], "isLong": comps["isLong"], "units": comps["units"],
         "premium": ident["premium"], "fee": ident["fee"], "expiry": comps["expiry"], "nonce": comps["nonce"]}
    cid, vc = policy_domain_args(st)
    dg = quote_digest(q, cid, vc)
    payload = {"digest": dg, **q, "stationLeg": comps["stationLeg"], "residualLeg": comps["residualLeg"],
               "tail": comps["tail"], "riskMargin": ident["riskMargin"], "notionalFee": ident["notionalFee"],
               "residualMarket": comps["residualMarket"] if comps["residualQty"] else ZERO32,
               "residualQty": comps["residualQty"], "residualTick": comps["residualTick"] if comps["residualQty"] else 0,
               "deltaPpm": comps["deltaPpm"], "dataAsOf": comps["dataAsOf"]}
    led.emit(ts, "QuoteIssued", payload)
    return dg


def buy_policy(led, ts: int, digest: str) -> int:
    st = led.state
    q = st["quotes"][digest]
    pid = st["nextPolicyId"]
    led.emit(ts, "PolicyBought", {"policyId": pid, "digest": digest, "market": q["market"], "buyer": q["buyer"],
                                  "isLong": q["isLong"], "units": q["units"], "premium": q["premium"],
                                  "fee": q["fee"]})
    return pid


def buy_strip_day(led, ts: int, strip_id: int, digest: str) -> int | None:
    """buyStripDay: the quote must match the strip template for its day; a day priced above the max is
    skipped (never partially filled). Returns the policy id or None when skipped."""
    st = led.state
    s = st["strips"][str(strip_id)]
    q = st["quotes"][digest]
    m = st["markets"][q["market"]]
    if not s["open"] or not (s["startDay"] <= m["day"] <= s["endDay"]):
        raise Revert("StripClosed")
    if (m["indexId"], m["lo"], m["hi"], q["isLong"], q["buyer"]) != (s["indexId"], s["lo"], s["hi"], s["isLong"],
                                                                     s["owner"]) or q["units"] > s["units"]:
        raise Revert("StripMismatch")
    if q["premium"] > s["maxDailyPremium"]:
        return None
    return buy_policy(led, ts, digest)


def bind(led, ts: int, policy_id: int, residual_order_id: int = 0) -> dict:
    st = led.state
    pol = st["policies"][str(policy_id)]
    if residual_order_id:
        from .auction import order_fill_view

        o = st["orders"][str(residual_order_id)]
        h, fill = o["qty"], order_fill_view(st, residual_order_id)
    else:
        h, fill = 0, 0
    a = bind_amounts(pol["units"], pol["premium"], pol["fee"], h, fill, P(st, "seniorPremiumBps"))
    led.emit(ts, "PolicyBound", {"policyId": policy_id, "residualOrderId": residual_order_id, **a})
    return a


def settle_policy(led, ts: int, policy_id: int) -> int:
    st = led.state
    pol = st["policies"][str(policy_id)]
    m = st["markets"][pol["market"]]
    x = get_final(st, m["indexId"], m["day"])
    pay = policy_payout(pol["boundUnits"], pol["isLong"], x, m["lo"], m["hi"])
    led.emit(ts, "PolicySettled", {"policyId": policy_id, "x": x, "payout": pay})
    return pay


def void_policy(led, ts: int, policy_id: int) -> int:
    pol = led.state["policies"][str(policy_id)]
    refund = pol["toPool"] if pol["status"] == "Bound" else pol["premium"]
    led.emit(ts, "PolicyVoided", {"policyId": policy_id, "refund": refund})
    return refund


def settle_positions(led, ts: int, market: str) -> None:
    """claimPosition for every trader of a market (final -> payout, void -> refund `paid`)."""
    st = led.state
    m = st["markets"][market]
    void = is_void(st, m["indexId"], m["day"])
    x = None if void else get_final(st, m["indexId"], m["day"])
    for trader in list(m["traders"]):
        ps = st["pos"][pos_key(market, trader)]
        if ps["done"]:
            continue
        if void:
            led.emit(ts, "PositionRefunded", {"market": market, "trader": trader, "refund": ps["paid"]})
        else:
            lx = L(x, m["lo"], m["hi"])
            led.emit(ts, "PositionSettled", {"market": market, "trader": trader, "longQty": ps["long"],
                                             "shortQty": ps["short"], "x": x,
                                             "payout": ps["long"] * lx + ps["short"] * (UNIT - lx)})


def open_strip(led, ts: int, owner: str, index_id: str, lo: int, hi: int, is_long: bool, units: int,
               max_daily_premium: int, start_day: int, end_day: int) -> int:
    sid = led.state["nextStripId"]
    led.emit(ts, "StripOpened", {"stripId": sid, "owner": owner, "indexId": index_id, "lo": lo, "hi": hi,
                                 "isLong": is_long, "units": units, "maxDailyPremium": max_daily_premium,
                                 "startDay": start_day, "endDay": end_day})
    return sid
