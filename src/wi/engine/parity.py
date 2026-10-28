"""Parity vectors for Foundry (docs/SPEC.md section 14), written by the engine, read with vm.parseJson.

Exact integer equality on every field. Never regenerate these from Solidity (that would be a mirror).
Every expected value comes from the engine's own functions / reducer handlers (auction.settle_book,
units.L, pool/staking/oracle handlers on a small state, policy.bind_amounts, eip712 + eth_account).

File names: SPEC 14 lists auction, payoff, pool, bind, haircut and eip712 cases; the 08 plan names
AuctionParity / PayoffParity / WaterfallParity / OracleParity. Both sets are written:
`waterfall_cases.json` is byte-identical to `pool_cases.json`, and `oracle_cases.json` carries the
report-acceptance / finalize / void timing cases (EIP-712 report digests live in eip712_cases.json).

JSON conventions for Foundry: keys sorted (struct decoding is alphabetical), no nulls (empty string /
0 instead), integers as JSON numbers (values above 2**53 appear in payoff_cases as exact integers).
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from . import oracle, pool, staking
from .auction import settle_book
from .eip712 import (QUOTE_FIELDS, QUOTE_TYPE, REPORT_FIELDS, REPORT_TYPE, RFQ_FIELDS, RFQ_TYPE, digest,
                     domain_separator, hx, index_id, keccak_text, sign_digest, struct_hash, type_hash)
from .policy import bind_amounts
from .state import DEFAULT_PARAMS, Revert, new_state
from .units import DAY_S, UNIT, L

SEED = 20260930
ANVIL_MNEMONIC = "test test test test test test test test test test test junk"  # public dev mnemonic
U = ["0x" + f"{i:040x}" for i in range(0x1001, 0x1010)]  # neutral test owners


def _meta(what: str, spec: str, **extra) -> dict:
    return {"generator": "wi.engine.parity (scripts/engine_fixture_run.py)", "spec": spec, "what": what,
            "tolerance": "exact integer equality", "doNotRegenerateFromSolidity": True, **extra}


# ============================================================================================ auction
def _curves(orders):
    bid, off = [0] * 101, [0] * 101
    for o in orders:
        (bid if o["isBid"] else off)[o["tick"]] += o["qty"]
    D, S = [0] * 102, [0] * 101
    for t in range(99, 0, -1):
        D[t] = D[t + 1] + bid[t]
    for t in range(1, 100):
        S[t] = S[t - 1] + off[t]
    return D, S


def _tie_range(orders) -> int:
    D, S = _curves(orders)
    best = None
    lo = hi = 0
    for t in range(1, 100):
        v, i = min(D[t], S[t]), abs(D[t] - S[t])
        if v == 0:
            continue
        if best is None or v > best[0] or (v == best[0] and i < best[1]):
            best, lo, hi = (v, i), t, t
        elif (v, i) == best:
            hi = t
    return 0 if best is None else hi - lo + 1


def _auction_case(name: str, orders: list[dict], fee: int) -> dict:
    r = settle_book(orders, fee)
    tags = []
    if r["qStar"] == 0:
        tags.append("noCross")
    if all(o["isBid"] for o in orders) or not any(o["isBid"] for o in orders):
        tags.append("oneSided")
    if len({o["tick"] for o in orders}) == 1:
        tags.append("oneTick")
    tr = _tie_range(orders)
    if tr > 1:
        tags.append("tieOdd" if tr % 2 else "tieEven")
    for o in r["orders"]:
        if o["ahead"] > 0 and 0 < o["fill"] < o["qty"]:
            tags.append("splitBidAhead" if o["isBid"] else "splitOfferAhead")
        if o["ahead"] > 0 and o["fill"] == 0 and (o["tick"] == r["tb"] if o["isBid"] else o["tick"] == r["to"]):
            tags.append("marginalZeroAhead")
    if any(o["tick"] == 1 for o in orders):
        tags.append("tick1")
    if any(o["tick"] == 99 for o in orders):
        tags.append("tick99")
    if len(orders) == 200:
        tags.append("maxOrders")
    if fee:
        tags.append("fee")
    exp_orders = [{k: o[k] for k in ("ahead", "escrow", "fill", "cost", "fee", "refund")} for o in r["orders"]]
    return {"name": name, "auctionFeePerUnit": fee, "tags": sorted(set(tags)),
            "orders": [{"isBid": o["isBid"], "tick": o["tick"], "qty": o["qty"]} for o in orders],
            "expected": {k: r[k] for k in ("pStar", "qStar", "tb", "to", "mb", "mo")} | {"orders": exp_orders,
                                                                                    "tieRangeLen": tr}}


def auction_cases() -> dict:
    b = lambda t, q: {"isBid": True, "tick": t, "qty": q}  # noqa: E731
    s = lambda t, q: {"isBid": False, "tick": t, "qty": q}  # noqa: E731
    hand = [
        ("spec_6_order_example", [b(72, 40), b(70, 30), b(64, 20), s(60, 35), s(66, 20), s(66, 30)], 0),
        ("spec_6_order_example_fee", [b(72, 40), b(70, 30), b(64, 20), s(60, 35), s(66, 20), s(66, 30)], 2_500),
        ("no_cross", [b(40, 10), s(60, 10)], 0),
        ("empty_book", [], 0),
        ("bids_only", [b(50, 10), b(60, 5)], 0),
        ("offers_only", [s(50, 10), s(40, 5)], 0),
        ("all_one_tick", [b(55, 10), s(55, 4), b(55, 3), s(55, 9)], 0),
        ("tie_even_range", [b(60, 10), s(40, 10)], 0),
        ("tie_odd_range", [b(62, 10), s(40, 10)], 0),
        ("imbalance_tie", [b(70, 10), b(50, 10), s(30, 10), s(60, 10)], 0),
        ("split_both_sides_ahead", [b(60, 5), b(60, 5), b(60, 5), s(55, 4), s(55, 4), s(55, 4), s(50, 2)], 0),
        ("tick_1_and_99", [b(99, 7), s(1, 3), b(1, 2), s(99, 9)], 0),
        ("extreme_ticks_cross", [b(99, 100), s(1, 100)], 0),
        ("fee_split", [b(58, 9), b(58, 9), s(52, 5), s(52, 5), s(52, 5)], 7_000),
        ("self_cross_house_pair", [b(60, 6), s(60, 6)], 0),
        ("big_qty", [b(80, 10**12), s(20, 3 * 10**11), s(50, 10**12)], 0),
    ]
    rng = random.Random(SEED)
    cases = [_auction_case(n, o, f) for n, o, f in hand]
    # 200 orders, marginal splits on both sides with ahead > 0 and a fee
    big = [{"isBid": i % 2 == 0, "tick": 45 + rng.randint(0, 10), "qty": rng.randint(1, 50)} for i in range(200)]
    cases.append(_auction_case("max_orders_200", big, 1_000))
    big0 = [{"isBid": i % 3 != 0, "tick": rng.randint(1, 99), "qty": rng.randint(1, 1000)} for i in range(200)]
    cases.append(_auction_case("max_orders_200_wide", big0, 0))
    i = 0
    while len(cases) < 64:
        n = rng.randint(2, 30)
        c = rng.randint(10, 90)
        orders = [{"isBid": rng.random() < 0.5, "tick": max(1, min(99, c + rng.randint(-4, 4))),
                   "qty": rng.choice([1, 2, 3, 5, 10, rng.randint(1, 500)])} for _ in range(n)]
        cases.append(_auction_case(f"random_{i:02d}", orders, rng.choice([0, 0, 0, 1_000, 10_000])))
        i += 1
    need = {"noCross", "oneSided", "oneTick", "tieOdd", "tieEven", "splitBidAhead", "splitOfferAhead", "tick1",
            "tick99", "maxOrders", "fee"}
    have = set().union(*(set(c["tags"]) for c in cases))
    if not need <= have:
        raise AssertionError(f"auction fixture misses SPEC 14 categories: {sorted(need - have)}")
    return {"_meta": _meta("uniform-price call auction: clearing summary and per-order ahead/escrow/fill/cost/fee/refund",
                           "SPEC 5, 14", orderFields="placement order; orderId = index + 1"), "cases": cases}


# ============================================================================================ payoff
def payoff_cases() -> dict:
    MAXQ = 2**128 - 1
    markets = [(880, 940), (650, 700), (0, 1), (-1, 1), (-50, 50), (-50, 49), (0, 7), (-3, 4), (100, 103),
               (-9_223_372_036_854_775_808, 9_223_372_036_854_775_807), (1, 2)]
    cases = []
    for lo, hi in markets:
        span = hi - lo
        xs = sorted({lo - 1, lo, lo + 1, hi - 1, hi, hi + 1, lo + span // 3, lo + span // 2}) if span < 2**62 else \
            [lo, lo + 1, 0, hi - 1, hi]
        for x in xs:
            if not -2**63 <= x < 2**63:
                continue
            for qty in (1, 6, 10**6, MAXQ) if (lo, hi) in ((880, 940), (-50, 50), (-50, 49)) else (1, 37):
                lx = L(x, lo, hi)
                cases.append({"lo": lo, "hi": hi, "x": x, "qty": qty, "L": lx, "longPayout": qty * lx,
                              "shortPayout": qty * (UNIT - lx), "sum": qty * UNIT})
    return {"_meta": _meta("scalar unit payout L(x) and position payouts; long + short == qty * UNIT",
                           "SPEC 2, 14", note="qty up to 2**128-1: payouts fit uint256"), "cases": cases}


# ============================================================================================ pool
POOL_KEYS = ("senior", "junior", "reserved", "deployed", "cash", "seniorSupply", "juniorSupply")
HOUSE, OWNER_ = U[0], U[1]


def _pool_state(params: dict) -> dict:
    world = {"roles": {"owner": OWNER_, "house": HOUSE, "quoter": HOUSE, "reporters": [], "keeper": OWNER_,
                       "juniorDepositors": [HOUSE], "rfqMakers": []}, "wiSupply": 0, "wiBalances": {}}
    st = new_state(world)
    st["params"].update(params)
    for a in U[:8]:
        st["bal"][a] = 10**15
    st["house"]["free"] = 10**15
    return st


def _step(op: str, ts: int, actor: str = U[2], day: int = 0, amount: int = 0, released: int = 0, loss: int = 0,
          tranche: str = "", shares: int = 0, request_id: int = 0) -> dict:
    return {"op": op, "ts": ts, "actor": actor, "day": day, "amount": amount, "released": released, "loss": loss,
            "tranche": tranche, "shares": shares, "requestId": request_id}


def _run_pool_step(st: dict, s: dict) -> tuple[str, int]:
    """Apply one vault-level step through the engine's handlers / pool functions. Returns (revert, result)."""
    op, ts, a = s["op"], s["ts"], s["actor"]
    p = st["pool"]
    try:
        if op == "depositJunior":
            sh = pool.shares_for(s["amount"], p["juniorSupply"], p["junior"])
            pool.h_junior_deposited(st, ts, {"owner": a, "amount": s["amount"], "shares": sh})
            return "", sh
        if op == "depositSenior":
            sh = pool.shares_for(s["amount"], p["seniorSupply"], p["senior"])
            pool.h_senior_deposited(st, ts, {"owner": a, "amount": s["amount"], "shares": sh})
            return "", sh
        if op == "reserve":
            pool.reserve(st, s["day"], s["amount"])
            return "", 0
        if op == "release":
            pool.release(st, s["day"], s["amount"])
            return "", 0
        if op == "creditPremium":
            sen, _ = pool.credit_premium(st, s["day"], s["amount"])
            return "", sen
        if op == "absorbLoss":
            pool.check_absorb(st, s["day"], s["released"], s["loss"])
            j, _ = pool.absorb_loss(st, s["day"], s["released"], s["loss"], a)
            return "", j
        if op == "fundHouse":
            pool.h_house_funded(st, ts, {"day": s["day"], "amount": s["amount"]})
            return "", 0
        if op == "returnFromHouse":
            d = str(s["day"])
            # vault-level parity: the house returns `amount` (its off-chain P&L is whatever makes it so)
            led = st["house"]["ledger"]
            st["bal"][HOUSE] += s["amount"] - led.get(d, 0)
            led[d] = s["amount"]
            dep = p["deployedByDay"].get(d, 0)
            pool.h_house_returned(st, ts, {"day": s["day"], "amount": s["amount"], "deployed": dep,
                                           "pnl": s["amount"] - dep})
            return "", s["amount"] - dep
        if op == "writeOffHouse":
            dep = p["deployedByDay"].get(str(s["day"]), 0)
            pool.h_house_written_off(st, ts, {"day": s["day"], "deployed": dep})
            return "", dep
        if op == "requestWithdraw":
            rid = p["nextWithdrawId"]
            pool.h_withdraw_requested(st, ts, {"requestId": rid, "owner": a, "tranche": s["tranche"],
                                               "shares": s["shares"], "claimableAt": ts + st["params"]["withdrawDelay"]})
            return "", rid
        if op == "claimWithdraw":
            amt = pool.check_withdraw(st, ts, s["requestId"])
            owner = p["withdrawals"][str(s["requestId"])]["owner"]
            pool.h_withdraw_claimed(st, ts, {"requestId": s["requestId"], "owner": owner, "amount": amt})
            return "", amt
        if op == "cancelWithdraw":
            req = pool.check_cancel(st, ts, s["requestId"], a)
            pool.h_withdraw_cancelled(st, ts, {"requestId": s["requestId"], "owner": a, "shares": req["shares"]})
            return "", 0
        if op == "lapseWithdraw":
            req = pool.check_lapse(st, ts, s["requestId"])
            pool.h_withdraw_lapsed(st, ts, {"requestId": s["requestId"], "owner": req["owner"],
                                            "shares": req["shares"]})
            return "", 0
        if op == "closeDay":
            pool.check_close(st, ts, s["day"])
            bps = pool.haircut_bps(st, s["day"])
            pool.h_day_closed(st, ts, {"day": s["day"], "juniorPnl": p["dayPnl"].get(str(s["day"]), 0),
                                       "haircutBps": bps})
            return "", bps
        raise ValueError(op)
    except Revert as e:
        return e.name, 0


def _snap(st: dict, s: dict, revert: str, result: int) -> dict:
    p = st["pool"]
    d = str(s["day"])
    return {"revert": revert, "result": result, **{k: p[k] for k in POOL_KEYS},
            "actorSeniorShares": p["seniorShares"].get(s["actor"], 0),
            "actorJuniorShares": p["juniorShares"].get(s["actor"], 0),
            "dayPnl": p["dayPnl"].get(d, 0), "openPolicies": p["openPolicies"].get(d, 0),
            "deployedByDay": p["deployedByDay"].get(d, 0)}


def pool_cases() -> dict:
    E = UNIT
    D = 20_000  # a climate day
    t0 = D * DAY_S
    base = {k: DEFAULT_PARAMS[k] for k in ("capBps", "jMinBps", "seniorPremiumBps", "minJuniorForSenior",
                                           "withdrawDelay", "houseReturnWindow", "haircutCapBps")}
    J, S1, S2 = HOUSE, U[2], U[3]
    WD = base["withdrawDelay"]  # claim times are relative to the delay, so a delay change needs no edit here
    HRW = base["houseReturnWindow"]
    CW = DEFAULT_PARAMS["withdrawClaimWindow"]  # PoolVault.CLAIM_WINDOW (a constant on chain)
    seed = [_step("depositJunior", t0, J, amount=10_000 * E), _step("depositSenior", t0, S1, amount=40_000 * E)]
    seqs = {
        "first_deposit_junior_then_senior": seed,
        "senior_closed_without_junior": [_step("depositSenior", t0, S1, amount=1_000 * E)],
        "senior_closed_below_min_junior": [_step("depositJunior", t0, J, amount=999 * E),
                                           _step("depositSenior", t0, S1, amount=1_000 * E)],
        "only_junior_depositor": [_step("depositJunior", t0, S1, amount=1_000 * E)],
        "zero_amount": [_step("depositJunior", t0, J, amount=0)],
        "virtual_offset_rounding": [_step("depositJunior", t0, J, amount=1), _step("depositJunior", t0, J, amount=3),
                                    _step("depositJunior", t0, J, amount=1_000 * E + 7),
                                    _step("depositSenior", t0, S1, amount=1), _step("depositSenior", t0, S2, amount=13)],
        "spec_worked_premium_then_loss_then_redeem": seed + [
            _step("reserve", t0, day=D, amount=6 * E), _step("creditPremium", t0, day=D, amount=3_900_000),
            _step("absorbLoss", t0 + 3 * DAY_S, S2, day=D, released=6 * E, loss=3 * E),
            _step("requestWithdraw", t0 + 3 * DAY_S, S1, tranche="senior", shares=4 * 10**15),
            _step("claimWithdraw", t0 + 3 * DAY_S + WD, S1, request_id=1)],
        "premium_split_odd_amount": seed + [_step("creditPremium", t0, day=D, amount=1_234_567)],
        "loss_below_junior": seed + [_step("reserve", t0, day=D, amount=5_000 * E),
                                     _step("absorbLoss", t0, S2, day=D, released=5_000 * E, loss=4_000 * E)],
        "loss_above_junior_hits_senior": [_step("depositJunior", t0, J, amount=2_000 * E),
                                          _step("depositSenior", t0, S1, amount=8_000 * E),
                                          _step("reserve", t0, day=D, amount=3_000 * E),
                                          _step("absorbLoss", t0, S2, day=D, released=3_000 * E, loss=2_500 * E)],
        "loss_exceeds_release": seed + [_step("reserve", t0, day=D, amount=10 * E),
                                        _step("absorbLoss", t0, S2, day=D, released=10 * E, loss=11 * E)],
        "house_return_with_gain": seed + [_step("fundHouse", t0, day=D, amount=500 * E),
                                          _step("returnFromHouse", t0 + DAY_S, day=D, amount=650 * E),
                                          _step("returnFromHouse", t0 + DAY_S, day=D, amount=1 * E)],
        "house_return_with_loss": seed + [_step("fundHouse", t0, day=D, amount=500 * E),
                                          _step("fundHouse", t0, day=D, amount=100 * E),
                                          _step("returnFromHouse", t0 + DAY_S, day=D, amount=120 * E),
                                          _step("closeDay", t0 + DAY_S, day=D)],
        "house_write_off": seed + [_step("fundHouse", t0, day=D, amount=700 * E),
                                   _step("writeOffHouse", t0 + HRW - DAY_S, day=D),
                                   _step("writeOffHouse", t0 + HRW, day=D),
                                   _step("writeOffHouse", t0 + HRW, day=D),
                                   _step("fundHouse", t0 + HRW, day=D, amount=1 * E)],
        "fund_house_day_window": seed + [_step("fundHouse", t0, day=D + 3, amount=1 * E),
                                         _step("fundHouse", t0, day=D - 2, amount=1 * E),
                                         _step("fundHouse", t0, day=D - 1, amount=1 * E),
                                         _step("fundHouse", t0, day=D + 2, amount=1 * E)],
        "cap_c1_reserve_revert": seed + [_step("reserve", t0, day=D, amount=40_000 * E),
                                         _step("reserve", t0, day=D, amount=1)],
        "cap_c1_fund_house_revert": seed + [_step("reserve", t0, day=D, amount=30_000 * E),
                                            _step("fundHouse", t0, day=D, amount=10_000 * E + 1)],
        "jmin_c2_senior_deposit_revert": seed + [_step("depositSenior", t0, S2, amount=10_000 * E + 1)],
        "jmin_c2_new_risk_after_loss": seed + [_step("reserve", t0, day=D, amount=5_000 * E),
                                               _step("absorbLoss", t0, S2, day=D, released=5_000 * E, loss=5_000 * E),
                                               _step("reserve", t0, day=D + 1, amount=1 * E)],
        "no_junior_after_wipeout": [_step("depositJunior", t0, J, amount=1_000 * E),
                                    _step("depositSenior", t0, S1, amount=4_000 * E),
                                    _step("reserve", t0, day=D, amount=2_000 * E),
                                    _step("absorbLoss", t0, S2, day=D, released=2_000 * E, loss=1_500 * E),
                                    _step("reserve", t0, day=D + 1, amount=1)],
        "withdrawal_after_loss": seed + [
            _step("requestWithdraw", t0, S1, tranche="senior", shares=10**16),
            _step("reserve", t0, day=D, amount=12_000 * E),
            _step("absorbLoss", t0 + DAY_S, S2, day=D, released=12_000 * E, loss=12_000 * E),
            _step("claimWithdraw", t0 + WD - DAY_S, S1, request_id=1),
            _step("claimWithdraw", t0 + WD, S1, request_id=1),
            _step("claimWithdraw", t0 + WD, S1, request_id=1)],
        "junior_withdraw_jmin_revert": seed + [
            _step("requestWithdraw", t0, J, tranche="junior", shares=9_000 * 10**12 * 1),
            _step("claimWithdraw", t0 + WD, J, request_id=1)],
        "withdraw_cap_c1_revert": seed + [
            _step("requestWithdraw", t0, S1, tranche="senior", shares=30_000 * 10**12),
            _step("reserve", t0, day=D, amount=39_000 * E),
            _step("claimWithdraw", t0 + WD, S1, request_id=1)],
        "withdraw_claim_last_second_of_window": seed + [
            _step("requestWithdraw", t0, S1, tranche="senior", shares=10**15),
            _step("claimWithdraw", t0 + WD + CW - 1, S1, request_id=1)],
        "withdraw_lapse_after_window": seed + [
            _step("requestWithdraw", t0, S1, tranche="senior", shares=10**15),
            _step("creditPremium", t0 + DAY_S, day=D, amount=1_234_567),
            _step("claimWithdraw", t0 + WD + CW, S1, request_id=1),
            _step("lapseWithdraw", t0 + WD + CW - 1, S1, request_id=1),
            _step("lapseWithdraw", t0 + WD + CW, S1, request_id=1),
            _step("claimWithdraw", t0 + WD + CW, S1, request_id=1),
            _step("lapseWithdraw", t0 + WD + CW, S1, request_id=1)],
        "withdraw_lapse_junior": seed + [
            _step("requestWithdraw", t0, J, tranche="junior", shares=10**15),
            _step("lapseWithdraw", t0 + WD + CW, J, request_id=1)],
        "withdraw_cancel_before_maturity": seed + [
            _step("requestWithdraw", t0, S1, tranche="senior", shares=10**15),
            _step("cancelWithdraw", t0 + 1, S2, request_id=1),
            _step("cancelWithdraw", t0 + WD - 1, S1, request_id=1),
            _step("claimWithdraw", t0 + WD, S1, request_id=1),
            _step("requestWithdraw", t0 + WD, S1, tranche="senior", shares=10**15),
            _step("cancelWithdraw", t0 + 2 * WD, S1, request_id=2),
            _step("claimWithdraw", t0 + 2 * WD, S1, request_id=2)],
        "close_day_rules": seed + [_step("reserve", t0, day=D, amount=10 * E),
                                   _step("closeDay", t0 + DAY_S, day=D),
                                   _step("absorbLoss", t0 + DAY_S, S2, day=D, released=10 * E, loss=4 * E),
                                   _step("closeDay", t0 + DAY_S - 1, day=D),
                                   _step("closeDay", t0 + DAY_S, day=D),
                                   _step("closeDay", t0 + DAY_S, day=D),
                                   _step("reserve", t0 + DAY_S, day=D, amount=1 * E)],
    }
    cases = []
    for name, steps in seqs.items():
        st = _pool_state(base)
        exp = []
        for s in steps:
            rv, res = _run_pool_step(st, s)
            exp.append(_snap(st, s, rv, res))
        cases.append({"name": name, "params": base, "steps": steps, "expected": exp})
    return {"_meta": _meta("pool vault step sequences: ledgers, shares, reserved, deployed, cash, revert names "
                           "(names from contracts/src/PoolVault.sol)", "SPEC 8, 14",
                           result="depositX: shares minted; creditPremium: senior part; absorbLoss: junior hit; "
                                  "returnFromHouse: pnl; writeOffHouse: written off; requestWithdraw: request id; "
                                  "claimWithdraw: assets paid; closeDay: haircutBps; else 0 (cancelWithdraw and "
                                  "lapseWithdraw return shares, no assets)",
                           virtualOffset=pool.OFFSET), "cases": cases}


# ============================================================================================ bind
def bind_cases() -> dict:
    rows = [
        (6, 4_200_000, 300_000, 0, 0, 2000),        # h = 0 -> full units
        (6, 4_200_000, 300_000, 6, 6, 2000),        # full fill
        (6, 4_200_000, 300_000, 6, 3, 2000),        # partial
        (6, 4_200_000, 300_000, 6, 0, 2000),        # zero fill -> closes the policy
        (7, 1_000_001, 12_345, 5, 2, 2000),         # premium not divisible by units
        (60, 35_090_001, 180_000, 58, 57, 2000),
        (60, 35_090_001, 180_000, 58, 1, 2000),
        (3, 2, 1, 7, 5, 2000),                      # tiny premium, rounding to the buyer
        (1, 999_999, 999_999, 1, 1, 2000),          # fee == premium
        (25, 5_465_475, 75_000, 0, 0, 0),           # senior share 0
        (25, 5_465_475, 75_000, 40, 13, 10_000),    # senior share 100 %
        (10, 6_000_000, 18_000, 11, 10, 2000),
        (10**6, 123_456_789_012, 1_000_003, 999_999, 333_333, 2000),
        (13, 13, 0, 3, 2, 2000),
        (2**64, 2**100 + 12_345, 2**90 + 1, 2**60, 2**59 + 1, 3333),
        (5, 5 * UNIT, 5_000, 4, 3, 2000),           # premium at max payout
    ]
    cases = []
    for units, prem, fee, h, fill, sbps in rows:
        cases.append({"units": units, "premium": prem, "fee": fee, "h": h, "fill": fill, "seniorPremiumBps": sbps,
                      "expected": bind_amounts(units, prem, fee, h, fill, sbps)})
    return {"_meta": _meta("bind/downsizing: boundUnits = h ? mulDiv(units, fill, h) : units; keptPremium, refund, "
                           "keptFee, toPool, senior/junior split", "SPEC 6.3, 14"), "cases": cases}


# ============================================================================================ haircut
def haircut_cases() -> dict:
    W = 10**18
    E = UNIT
    D = 20_000
    t0 = D * DAY_S
    specs = [
        ("below_cap", 9_500 * E, -500 * E, [(U[2], 600_000), (U[3], 400_000)], [], 3000),
        ("spec_example_500bps", 9_500 * E, -500 * E, [(U[2], 1_000_000)], [], 3000),
        ("at_cap", 7_000 * E, -3_000 * E, [(U[2], 1_000_000)], [], 3000),
        ("above_cap", 1_000 * E, -9_000 * E, [(U[2], 700_000), (U[3], 300_000)], [], 3000),
        ("junior_wiped", 0, -10_000 * E, [(U[2], 1_000_000)], [], 3000),
        ("cooldown_shares_cut", 9_000 * E, -1_000 * E, [(U[2], 500_000), (U[3], 500_000)], [(U[3], 2)], 3000),
        ("all_in_cooldown", 9_000 * E, -1_000 * E, [(U[2], 1_000_000)], [(U[2], 1)], 3000),
        ("day_with_net_gain", 10_500 * E, 500 * E, [(U[2], 1_000_000)], [], 3000),
        ("zero_pnl", 10_000 * E, 0, [(U[2], 1_000_000)], [], 3000),
        ("tiny_loss_rounds_to_zero", 10**12, -1, [(U[2], 3)], [], 3000),
        ("odd_stakes", 12_345 * E, -678 * E, [(U[2], 333_333), (U[3], 1), (U[4], 666_666)], [(U[4], 3)], 1500),
    ]
    cases = []
    for name, junior_after, pnl, stakes, cooldowns, cap in specs:
        world = {"roles": {"owner": U[1], "house": HOUSE, "quoter": HOUSE, "reporters": [], "keeper": U[1],
                           "juniorDepositors": [HOUSE], "rfqMakers": []},
                 "wiSupply": sum(a for _, a in stakes) * W, "wiBalances": {o: a * W for o, a in stakes}}
        st = new_state(world)
        st["params"]["haircutCapBps"] = cap
        for o, a in stakes:
            staking.h_wi_staked(st, t0, {"owner": o, "amount": a * W, "shares": staking.stake_shares(st["wi"], a * W)})
        for o, div in cooldowns:
            sh = st["wi"]["shares"][o] // div
            rid = st["wi"]["nextUnstakeId"]
            staking.h_wi_unstake_requested(st, t0, {"requestId": rid, "owner": o, "shares": sh,
                                                    "claimableAt": t0 + DEFAULT_PARAMS["unstakeCooldown"]})
        st["pool"]["junior"] = junior_after
        st["pool"]["cash"] = junior_after
        st["pool"]["dayPnl"][str(D)] = pnl
        bps = pool.haircut_bps(st, D)
        pool.h_day_closed(st, t0 + DAY_S, {"day": D, "juniorPnl": pnl, "haircutBps": bps})
        staked_before = st["wi"]["totalStaked"]
        burned = 0
        if bps:
            burned = staking.burn_for(st["wi"], bps)
            staking.h_wi_haircut(st, t0 + DAY_S, {"day": D, "bps": bps, "burned": burned})
        positions = []
        for o, _ in stakes:
            active = st["wi"]["shares"].get(o, 0)
            cool = sum(r["shares"] for r in st["wi"]["unstakes"].values() if r["owner"] == o)
            positions.append({"owner": o, "activeShares": active, "cooldownShares": cool,
                              "activeValue": staking.unstake_amount(st["wi"], active),
                              "cooldownValue": staking.unstake_amount(st["wi"], cool)})
        cases.append({"name": name, "haircutCapBps": cap, "juniorAssetsAtClose": junior_after, "dayPnl": pnl,
                      "stakes": [{"owner": o, "amount": a * W} for o, a in stakes],
                      "cooldowns": [{"owner": o, "shareDivisor": d} for o, d in cooldowns],
                      "expected": {"haircutBps": bps, "burned": burned, "totalStakedBefore": staked_before,
                                   "totalStakedAfter": st["wi"]["totalStaked"], "totalShares": st["wi"]["totalShares"],
                                   "positions": positions}})
    return {"_meta": _meta("WI staking haircut on a closed day's net junior loss: bps = min(mulDiv(l, 1e4, junior + l), "
                           "cap); burned = mulDiv(totalStaked, bps, 1e4); cooldown shares stay cuttable",
                           "SPEC 8.7, 14", positionValue="mulDiv(shares, totalStaked + 1, totalShares + 1e6)"),
            "cases": cases}


# ============================================================================================ eip712
def _anvil_key(i: int) -> str:
    from eth_account import Account

    Account.enable_unaudited_hdwallet_features()
    return Account.from_mnemonic(ANVIL_MNEMONIC, account_path=f"m/44'/60'/0'/0/{i}").key.hex()


def _eth_account_digest(domain: dict, types: dict, primary: str, msg: dict) -> str:
    """Independent digest via eth_account.encode_typed_data (cross-check of eip712.py)."""
    from eth_account.messages import encode_typed_data
    from eth_utils import keccak

    full = {"types": {"EIP712Domain": [{"name": "name", "type": "string"}, {"name": "version", "type": "string"},
                                       {"name": "chainId", "type": "uint256"},
                                       {"name": "verifyingContract", "type": "address"}], **types},
            "primaryType": primary, "domain": domain, "message": msg}
    sm = encode_typed_data(full_message=full)
    return hx(keccak(b"\x19" + sm.version + sm.header + sm.body))


def eip712_cases() -> dict:
    k_quoter, k_reporter = _anvil_key(1), _anvil_key(2)
    iid = index_id("PAIR:LGA-NYC:TMAX:v1")
    mkt = keccak_text("example-market")
    rid = keccak_text("example-request")
    specs = {
        "Report": ("wi-oracle", REPORT_TYPE, REPORT_FIELDS, k_reporter, [
            {"indexId": iid, "day": 20_674, "value": 30, "revision": 0, "asOf": 1_786_190_400},
            {"indexId": index_id("CLI:NYC:TMAX:v1"), "day": 20_674, "value": 910, "revision": 1, "asOf": 1_786_190_400},
            {"indexId": iid, "day": 20_675, "value": -70, "revision": 65_535, "asOf": 2**64 - 1},
        ]),
        "Quote": ("wi-policy", QUOTE_TYPE, QUOTE_FIELDS, k_quoter, [
            {"market": mkt, "buyer": "0x9965507d1a55bcc2695c58ba16fb37d819b0a4dc", "isLong": True, "units": 6,
             "premium": 4_200_000, "fee": 300_000, "expiry": 1_786_155_300, "nonce": 1},
            {"market": mkt, "buyer": "0x976ea74026e726554db657fa54763abd0c3a0aa9", "isLong": False, "units": 10,
             "premium": 6_000_000, "fee": 18_000, "expiry": 1_786_155_300, "nonce": 2**255},
            {"market": mkt, "buyer": "0x14dc79964da2c08b23698b3d3cc7ca32193d9955", "isLong": True, "units": 2**128 - 1,
             "premium": 0, "fee": 0, "expiry": 0, "nonce": 0},
        ]),
        "RfqQuote": ("wi-policy", RFQ_TYPE, RFQ_FIELDS, k_quoter, [
            {"requestId": rid, "market": mkt, "maker": "0x70997970c51812dc3a010c7d01b50e0d17dc79c8",
             "taker": "0xa0ee7a142d267c1f36714e4a8f75612f20a79720", "takerLong": True, "tick": 68, "maxQty": 25,
             "validUntil": 1_786_146_000, "nonce": 7},
            {"requestId": rid, "market": mkt, "maker": "0x70997970c51812dc3a010c7d01b50e0d17dc79c8",
             "taker": "0xa0ee7a142d267c1f36714e4a8f75612f20a79720", "takerLong": False, "tick": 1, "maxQty": 1,
             "validUntil": 1, "nonce": 0},
            {"requestId": rid, "market": mkt, "maker": "0x70997970c51812dc3a010c7d01b50e0d17dc79c8",
             "taker": "0x15d34aaf54267db7d7c367839aaf71a00a2c6a65", "takerLong": True, "tick": 99,
             "maxQty": 2**128 - 1, "validUntil": 2**64 - 1, "nonce": 2**256 - 1},
        ]),
    }
    verifying = {31337: {"wi-oracle": "0x00000000000000000000000000000000000000a1",
                         "wi-policy": "0x00000000000000000000000000000000000000a2"},
                 998: {"wi-oracle": "0x5fbdb2315678afecb367f032d93f642f64180aa3",
                       "wi-policy": "0xe7f1725e7734ce288f8367e1bb143e90bb3f0512"}}
    cases = []
    for primary, (dname, tstr, fields, key, msgs) in specs.items():
        for chain in (31337, 998):
            vc = verifying[chain][dname]
            ds = domain_separator(dname, "1", chain, vc)
            for msg in msgs:
                sh = struct_hash(tstr, fields, msg)
                dg = hx(digest(ds, sh))
                cross = _eth_account_digest({"name": dname, "version": "1", "chainId": chain,
                                             "verifyingContract": vc},
                                            {primary: [{"name": n, "type": t} for n, t in fields]}, primary,
                                            {n: (bytes.fromhex(msg[n][2:]) if t == "bytes32" else msg[n])
                                             for n, t in fields})
                if cross != dg:
                    raise AssertionError(f"eip712 digest mismatch vs eth_account for {primary}")
                sig = sign_digest(key, dg)
                cases.append({"type": primary, "typeString": tstr, "domain": {"name": dname, "version": "1",
                                                                              "chainId": chain,
                                                                              "verifyingContract": vc},
                              "message": msg, "expected": {"typeHash": hx(type_hash(tstr)), "domainSeparator": hx(ds),
                                                           "structHash": hx(sh), "digest": dg, "v": sig["v"],
                                                           "r": sig["r"], "s": sig["s"],
                                                           "signature": sig["signature"], "signer": sig["signer"]}})
    return {"_meta": _meta("EIP-712 typeHash / domainSeparator / structHash / digest / signature for Report, Quote, "
                           "RfqQuote; signer = anvil key #2 (Report) or #1 (Quote, RfqQuote), public dev mnemonic",
                           "SPEC 6.1, 9.1, 10.1, 14",
                           crossCheck="digest recomputed with eth_account.encode_typed_data and asserted equal",
                           verifyingContracts=verifying), "cases": cases}


# ============================================================================================ oracle
def oracle_cases() -> dict:
    D = 20_674
    fetch = (D + 1) * DAY_S + 12 * 3600
    fin = fetch + 24 * 3600
    void_at = fin + 72 * 3600
    rep, bad = "0x3c44cdddb6a900fa2b585dd299e03d12fa4293bc", U[5]
    v0, v1 = "0x" + "11" * 32, "0x" + "22" * 32

    def post(ts, value=30, revision=0, as_of=fetch, signer=rep, vintage=v0, active=True):
        return {"op": "post", "ts": ts, "value": value, "revision": revision, "asOf": as_of, "signer": signer,
                "vintageHash": vintage, "active": active}

    def op(name, ts):
        return {"op": name, "ts": ts, "value": 0, "revision": 0, "asOf": 0, "signer": U[0], "vintageHash": "0x" + "00" * 32,
                "active": True}

    seqs = {
        "post_at_fetch_then_finalize": [post(fetch), op("finalize", fin - 1), op("finalize", fin), op("finalize", fin)],
        "P1_inactive_index": [post(fetch, active=False)],
        "P3_asof_before_fetch": [post(fetch, as_of=fetch - 1)],
        "P4_asof_in_future": [post(fetch, as_of=fetch + 1)],
        "P5_report_stale": [post(fetch + 24 * 3600 - 1, as_of=fetch), post(fetch + 12 * 3600 + 24 * 3600 + 1, as_of=fetch + 12 * 3600, revision=1)],
        "P6_window_closed": [post(fin, as_of=fetch + 3600)],
        "P7_revision_not_newer": [post(fetch), post(fetch + 60, revision=0, value=31), post(fetch + 60, revision=2, value=31),
                                  post(fetch + 120, revision=1, value=32)],
        "P8_bad_signer": [post(fetch, signer=bad)],
        "revision_corrects_transcription": [post(fetch, value=50), post(fetch + 3 * 3600, value=30, revision=1),
                                            op("finalize", fin)],
        "revision_with_new_vintage_rejected_engine_only": [post(fetch, value=30),
                                                           post(fetch + 3600, value=33, revision=1, vintage=v1)],
        "negative_value_basis": [post(fetch, value=-70), op("finalize", fin)],
        "P2_post_after_final": [post(fetch), op("finalize", fin), post(fin + 1, revision=1, as_of=fin)],
        "finalize_nothing_posted": [op("finalize", fin)],
        "void_rules": [op("void", void_at - 1), op("void", void_at), op("void", void_at), post(void_at + 1, as_of=void_at)],
        "void_refused_after_post": [post(fetch), op("void", void_at)],
    }
    cases = []
    for name, steps in seqs.items():
        world = {"roles": {"owner": U[0], "house": U[1], "quoter": U[1], "reporters": [rep], "keeper": U[0],
                           "juniorDepositors": [], "rfqMakers": []}, "wiSupply": 0, "wiBalances": {}}
        st = new_state(world)
        name_ = "PAIR:LGA-NYC:TMAX:v1"
        iid = index_id(name_)
        st["indices"][iid] = {"name": name_, "kind": "PAIR", "scale": 10, "station": "NYC", "metro": "NYC",
                              "inputs": [], "quorumBps": 10_000, "fetchLag": 12 * 3600, "disputeWindow": 24 * 3600,
                              "voidGrace": 72 * 3600, "listedAt": 0, "active": True}
        exp = []
        for s in steps:
            st["indices"][iid]["active"] = s["active"]
            rv = ""
            try:
                if s["op"] == "post":
                    oracle.h_report_posted(st, s["ts"], {"indexId": iid, "day": D, "value": s["value"],
                                                         "revision": s["revision"], "asOf": s["asOf"],
                                                         "signer": s["signer"], "vintageHash": s["vintageHash"]})
                elif s["op"] == "finalize":
                    ob = st["obs"].get(f"{iid}:{D}")
                    oracle.h_index_finalized(st, s["ts"], {"indexId": iid, "day": D,
                                                           "value": ob["value"] if ob and "value" in ob else 0})
                elif s["op"] == "void":
                    oracle.h_index_voided(st, s["ts"], {"indexId": iid, "day": D})
            except Revert as e:
                rv = e.name
            ob = st["obs"].get(f"{iid}:{D}", {})
            exp.append({"revert": rv, "status": ob.get("status", "none"), "value": ob.get("value", 0),
                        "revision": ob.get("revision", -1)})
        cases.append({"name": name, "indexId": iid, "day": D, "maxReportAge": DEFAULT_PARAMS["maxReportAge"],
                      "config": {"fetchLag": 12 * 3600, "disputeWindow": 24 * 3600, "voidGrace": 72 * 3600},
                      "windows": {"fetchAt": fetch, "finalizeAt": fin, "voidAt": void_at},
                      "engineOnly": name.endswith("engine_only"), "steps": steps, "expected": exp})
    return {"_meta": _meta("oracle acceptance predicates P1-P8, finalize and void timing (CLI windows 12h/24h/72h); "
                           "revert names from contracts/src/OracleAdapter.sol; engineOnly cases are checks the chain "
                           "cannot make (vintageHash is not signed) and Foundry should skip", "SPEC 9, 14"),
            "cases": cases}


# ============================================================================================ writer
def write_all(out_dir: str | Path) -> list[tuple[Path, int]]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pc = pool_cases()
    files = {"auction_cases.json": auction_cases(), "payoff_cases.json": payoff_cases(), "pool_cases.json": pc,
             "waterfall_cases.json": pc, "bind_cases.json": bind_cases(), "haircut_cases.json": haircut_cases(),
             "eip712_cases.json": eip712_cases(), "oracle_cases.json": oracle_cases()}
    written = []
    for name, obj in files.items():
        p = out / name
        p.write_bytes(json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False).encode() + b"\n")
        written.append((p, len(obj["cases"])))
    return written
