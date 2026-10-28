"""Pool waterfall money failures, on random step sequences through the reducer handlers.

How this could silently lose money: senior capital absorbing a loss while junior still has money,
tranche NAVs that stop summing to capital or to cash + deployed, share rounding that lets a
redeemer take more than the tranche holds, reserves or house deployment growing past C1, or new
risk accepted while junior is below jMin.
"""
import random

from wi.engine import pool
from wi.engine.reducer import Ledger
from wi.engine.scenario import ANVIL, default_world
from wi.engine.state import P, Revert
from wi.engine.units import BPS, DAY_S, UNIT

HOUSE, LPS = ANVIL[1], ANVIL[4:8]


def _run(seed: int) -> tuple[Ledger, list[str]]:
    rng = random.Random(seed)
    led = Ledger(default_world())
    st = led.state
    ts = 10 * DAY_S
    led.emit(ts, "AccountFunded", {"account": HOUSE, "amount": 10**15})
    for a in LPS:
        led.emit(ts, "AccountFunded", {"account": a, "amount": 10**15})
    pool.deposit_junior(led, ts, HOUSE, rng.randint(1_000, 20_000) * UNIT)
    kinds = []
    for _ in range(400):
        ts += rng.randint(0, DAY_S)
        day = ts // DAY_S
        pre = dict(st["pool"])
        k = rng.choice(["senior", "junior", "reserve_loss", "premium", "house", "withdraw", "claim", "lapse"])
        try:
            if k == "senior":
                pool.deposit_senior(led, ts, rng.choice(LPS), rng.randint(1, 10**10))
            elif k == "junior":
                pool.deposit_junior(led, ts, HOUSE, rng.randint(1, 10**9))
            elif k == "reserve_loss":
                amt = rng.randint(1, max(1, pool.capital(st["pool"]) // 5))
                pool.reserve(st, day, amt)  # PM-side call; followed by its settlement in the same step
                loss = rng.randint(0, amt)
                pool.absorb_loss(st, day, amt, loss, rng.choice(LPS))
            elif k == "premium":
                amt = rng.randint(1, 10**9)
                st["bal"][LPS[0]] -= amt
                pool.credit_premium(st, day, amt)
            elif k == "house":
                amt = rng.randint(1, max(1, pool.capital(st["pool"]) // 10))
                if st["pool"]["houseDone"].get(str(day)):
                    continue
                pool.fund_house(led, ts, day, amt)
                pnl = rng.randint(-amt, amt)  # house P&L of the day, settled against a counterparty
                st["bal"][HOUSE] += pnl
                st["bal"]["@kalshi"] = st["bal"].get("@kalshi", 0) - pnl
                st["house"]["ledger"][str(day)] += pnl
                pool.return_from_house(led, ts, day)
            elif k == "withdraw":
                a = rng.choice(LPS + [HOUSE])
                tr = "junior" if a == HOUSE else "senior"
                have = st["pool"]["juniorShares" if tr == "junior" else "seniorShares"].get(a, 0)
                if have:
                    pool.request_withdraw(led, ts, a, tr, rng.randint(1, have))
            elif k == "claim":
                for rid, req in list(st["pool"]["withdrawals"].items()):
                    if not req["claimed"] and ts >= req["claimableAt"]:
                        pool.claim_withdraw(led, ts, int(rid))
            elif k == "lapse":  # the reducer's I15 check: a lapse hands shares back and moves no money
                for rid, req in list(st["pool"]["withdrawals"].items()):
                    if not req["claimed"] and ts >= req["claimableAt"] + P(st, "withdrawClaimWindow"):
                        pool.lapse_withdraw(led, ts, int(rid))
                        kinds.append("lapsed")
        except Revert as e:
            kinds.append(e.name)
            continue
        kinds.append(k)
        p = st["pool"]
        # junior first: a loss step never cuts senior while junior is left
        if k in ("reserve_loss", "house") and p["senior"] < pre["senior"]:
            assert p["junior"] == 0
        assert p["cash"] == p["senior"] + p["junior"] - p["deployed"]
        assert (p["reserved"] + p["deployed"]) * BPS <= P(st, "capBps") * pool.capital(p)  # C1 survives losses
    return led, kinds


def test_random_pool_sequences_keep_junior_first_and_nav_identity():
    seen = set()
    for seed in range(40):
        led, kinds = _run(seed)
        seen.update(kinds)
        p = led.state["pool"]
        # redeeming every share of a tranche can never pay out more than the tranche holds
        for tr, supply, assets in (("s", p["seniorSupply"], p["senior"]), ("j", p["juniorSupply"], p["junior"])):
            assert pool.assets_for(supply, supply, assets) <= assets
    # the sequences reached the paths that matter, including cap / jMin / no-junior reverts
    assert {"reserve_loss", "house", "claim", "premium", "lapsed"} <= seen
    assert {"ExposureCap", "JuniorMinimum"} & seen


def test_reserve_and_fund_house_never_exceed_c1():
    """Every accepted reserve / fundHouse leaves (reserved + deployed) <= capBps x capital; the one that
    would cross is refused with ExposureCap and changes nothing."""
    led = Ledger(default_world())
    st = led.state
    led.emit(0, "AccountFunded", {"account": HOUSE, "amount": 10**15})
    led.emit(0, "AccountFunded", {"account": LPS[0], "amount": 10**15})
    pool.deposit_junior(led, 0, HOUSE, 5_000 * UNIT)
    pool.deposit_senior(led, 0, LPS[0], 15_000 * UNIT)
    rng = random.Random(3)
    refused = 0
    for i in range(500):
        snap = dict(st["pool"])
        try:
            if rng.random() < 0.5:
                pool.reserve(st, 100 + i % 7, rng.randint(1, 2_000 * UNIT))
            else:
                pool.fund_house(led, 100 * DAY_S, 100 + i % 3, rng.randint(1, 2_000 * UNIT))  # days today..+2
        except Revert as e:
            assert e.name in ("ExposureCap", "HouseDayDone")
            assert st["pool"] == snap
            refused += 1
        p = st["pool"]
        assert (p["reserved"] + p["deployed"]) * BPS <= P(st, "capBps") * pool.capital(p)
        assert p["cash"] >= p["reserved"]  # every reserved payout is payable from cash
    assert refused > 100
