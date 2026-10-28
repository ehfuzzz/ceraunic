"""The SPEC worked examples, reproduced by the engine (plan 07-ENGINE verify step). The numbers were
worked out in docs/SPEC.md independently of this code; a mismatch means the engine and the spec (and
so the contracts that follow the spec) disagree on money.
"""
from wi.engine import hedge, pool, staking
from wi.engine.auction import settle_book
from wi.engine.policy import bind_amounts
from wi.engine.reducer import Ledger
from wi.engine.scenario import ANVIL, default_world
from wi.engine.state import new_state
from wi.engine.units import UNIT, L, round_half_away, tick_to_index


def test_auction_six_order_example():
    b = lambda t, q: {"isBid": True, "tick": t, "qty": q}  # noqa: E731
    s = lambda t, q: {"isBid": False, "tick": t, "qty": q}  # noqa: E731
    r = settle_book([b(72, 40), b(70, 30), b(64, 20), s(60, 35), s(66, 20), s(66, 30)])
    assert (r["pStar"], r["qStar"], r["tb"], r["mb"], r["to"], r["mo"]) == (68, 70, 70, 30, 66, 35)
    got = [(o["escrow"], o["fill"], o["cost"], o["refund"]) for o in r["orders"]]
    assert got == [(28_800_000, 40, 27_200_000, 1_600_000), (21_000_000, 30, 20_400_000, 600_000),
                   (12_800_000, 0, 0, 12_800_000), (14_000_000, 35, 11_200_000, 2_800_000),
                   (6_800_000, 20, 6_400_000, 400_000), (10_200_000, 15, 4_800_000, 5_400_000)]


def test_payout_examples_a_to_d():
    assert [6 * L(x, 880, 940) for x in (870, 890, 910, 930, 950)] == [0, 999_996, 3_000_000, 4_999_998, 6_000_000]
    assert 10 * (UNIT - L(670, 650, 700)) == 6_000_000  # (b) $2/F cool cover, high 67 F
    assert (50 * L(0, 0, 1), 50 * L(1, 0, 1)) == (0, 50_000_000)  # (c) rain digital
    assert tick_to_index(68, -50, 50) == 18 and L(30, -50, 50) == 800_000 and L(-70, -50, 50) == 0  # (d)


def test_replication_and_residual_size_examples():
    rungs = [{"ticker": "L86", "strike_type": "less", "floor_strike": None, "cap_strike": 86},
             {"ticker": "B86", "strike_type": "between", "floor_strike": 86, "cap_strike": 87},
             {"ticker": "B88", "strike_type": "between", "floor_strike": 88, "cap_strike": 89},
             {"ticker": "B90", "strike_type": "between", "floor_strike": 90, "cap_strike": 91},
             {"ticker": "B92", "strike_type": "between", "floor_strike": 92, "cap_strike": 93},
             {"ticker": "G93", "strike_type": "greater", "floor_strike": 93, "cap_strike": None}]
    q = hedge.replicate(6, 880, 940, True, rungs)
    assert [q[t] for t in ("L86", "B86", "B88", "B90", "B92", "G93")] == [0, 0, 50, 250, 450, 600]
    assert round_half_away(6 * 550_000 * 100, 60 * 10**6) == 6  # h for call (a) at LGA, delta 0.55, R = 50
    assert hedge.fee_cents([(100, 30)]) == 2 and hedge.fee_cents([(300, 45)]) == 6  # SPEC 7.5 fee examples


def test_waterfall_and_haircut_examples():
    led = Ledger(default_world())
    st = led.state
    st["params"]["seniorPremiumBps"] = 2000  # SPEC §8.3 illustration is at 2000; v0 default is 30 (SPEC §18 2026-09-30)
    for a in (ANVIL[1], ANVIL[4]):
        led.emit(0, "AccountFunded", {"account": a, "amount": 10**12})
    pool.deposit_junior(led, 0, ANVIL[1], 10_000 * UNIT)
    pool.deposit_senior(led, 0, ANVIL[4], 40_000 * UNIT)
    a = bind_amounts(1, 4_200_000, 300_000, 0, 0, 2000)
    assert (a["toPool"], a["seniorPremium"], a["juniorPremium"]) == (3_900_000, 780_000, 3_120_000)
    pool.reserve(st, 5, 3 * UNIT)
    st["bal"][ANVIL[4]] -= a["toPool"]
    pool.credit_premium(st, 5, a["toPool"])
    pool.absorb_loss(st, 5, 3 * UNIT, 3 * UNIT, ANVIL[5])
    assert (st["pool"]["junior"], st["pool"]["senior"]) == (10_000_120_000, 40_000_780_000)
    supply = st["pool"]["seniorSupply"]
    assert pool.assets_for(supply // 10, supply, st["pool"]["senior"]) == 4_000_077_999

    s2 = new_state({"roles": default_world()["roles"], "wiSupply": 10**6, "wiBalances": {ANVIL[0]: 10**6}})
    staking.h_wi_staked(s2, 0, {"owner": ANVIL[0], "amount": 10**6, "shares": staking.stake_shares(s2["wi"], 10**6)})
    s2["pool"]["junior"], s2["pool"]["dayPnl"]["7"] = 9_500 * UNIT, -500 * UNIT
    bps = pool.haircut_bps(s2, 7)
    assert bps == 500 and staking.burn_for(s2["wi"], bps) == 50_000
