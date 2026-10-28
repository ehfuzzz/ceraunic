"""Replay property and log corruption.

How this could silently corrupt data: a snapshot that does not reproduce the state it claims (the API
restarts from snapshots), a reducer whose result depends on something outside the log, or a log line
edited after the fact - with or without the attacker re-chaining the hashes - that replays into a
different ledger without anyone noticing.
"""
import copy
import random

import pytest

from wi.engine import auction, house_mm, oracle, policy, pool, staking
from wi.engine.log import LogError
from wi.engine.markets import create_market, register_index
from wi.engine.reducer import Ledger, replay, replay_from_snapshot
from wi.engine.scenario import ANVIL, default_world
from wi.engine.state import Revert
from wi.engine.units import DAY_S, TICK, UNIT, at_utc, event_hash

HOUSE, TRADERS, BUYER = ANVIL[1], ANVIL[5:9], ANVIL[9]


def random_stream(seed: int) -> Ledger:
    """A seeded random life of a small world: deposits, staking, markets, open orders from any wallet,
    house legs, policies (quote -> buy -> bind -> settle/void), reports, finalize, returns, day closes."""
    rng = random.Random(seed)
    w = default_world()
    led = Ledger(w, keep_snapshots=True)
    st = led.state
    t0 = at_utc(100, 12)
    for a, usd in [(HOUSE, 50_000), (ANVIL[4], 50_000), (BUYER, 5_000)] + [(t, 5_000) for t in TRADERS]:
        led.emit(t0, "AccountFunded", {"account": a, "amount": usd * UNIT})
    loc = register_index(led, t0, "CLI:LGA:TMAX:v1", kind="CLI", scale=10, station="NYC", metro="NYC", inputs=["x"])
    bas = register_index(led, t0, "PAIR:LGA-NYC:TMAX:v1", kind="PAIR", scale=10, station="NYC", metro="NYC",
                         inputs=["x", "y"])
    pool.deposit_junior(led, t0, HOUSE, rng.randint(5_000, 20_000) * UNIT)
    pool.deposit_senior(led, t0, ANVIL[4], rng.randint(5_000, 40_000) * UNIT)
    staking.stake(led, t0, ANVIL[0], 500_000 * 10**18)
    staking.stake(led, t0, ANVIL[4], 200_000 * 10**18)
    days = list(range(102, 110))
    nonce = 1
    sched = []
    for D in days:
        sched.append((at_utc(D - 1, 14), 0, D, "open"))
        sched.append((at_utc(D, 3), 1, D, "clear"))
        sched.append((at_utc(D + 1, 12), 2, D, "report"))
        sched.append((at_utc(D + 2, 12), 3, D, "settle"))
        sched.append((at_utc(D + 5, 12), 4, D, "void"))
    for d in range(101, 118):
        sched.append((at_utc(d, 12, 30), 5, d, "epoch"))
    sched.append((at_utc(103, 13), 6, 0, "withdraw"))
    sched.append((at_utc(104, 13), 6, 0, "unstake"))
    mk: dict[int, tuple[str, str]] = {}
    void_day = rng.choice(days)
    for ts, _, D, what in sorted(sched):
        if what == "open":
            lo = rng.choice([800, 850, 880])
            m_loc = create_market(led, ts, loc, D, lo, lo + 60, False)
            m_bas = create_market(led, ts, bas, D, -50, 50, True)
            mk[D] = (m_loc, m_bas)
            for _ in range(rng.randint(0, 2)):
                is_long = rng.random() < 0.5
                h, tick, units = rng.randint(0, 8), rng.randint(20, 80), rng.randint(1, 12)
                dg = policy.issue_quote(led, ts, {
                    "market": m_loc, "buyer": BUYER, "isLong": is_long, "units": units,
                    "expiry": st["markets"][m_loc]["saleCutoff"], "nonce": nonce,
                    "stationLeg": rng.randint(0, units * UNIT // 3), "residualLeg": rng.randint(-units * UNIT // 10,
                                                                                               units * UNIT // 10),
                    "tail": rng.randint(0, 10**5), "residualMarket": m_bas,
                    "residualQty": h, "residualTick": tick, "deltaPpm": rng.randint(0, 10**6), "dataAsOf": ts})
                nonce += 1
                policy.buy_policy(led, ts, dg)
            house_mm.book(led, ts + 60, D, [], None)  # residual legs only (no schedule here)
            for t in TRADERS:
                for _ in range(rng.randint(0, 4)):
                    is_bid, tick, qty = rng.random() < 0.5, rng.randint(30, 70), rng.randint(1, 30)
                    side = tick if is_bid else 100 - tick
                    qty = max(qty, -(-UNIT // (side * TICK)))  # public orders carry >= 1 USDC escrow
                    auction.place_order(led, ts + 120, m_bas, t, is_bid, tick, qty)
        elif what == "clear":
            house_mm.bind(led, ts, D, [mk[D][1]])
        elif what == "report" and D != void_day:
            x = rng.randint(820, 960)
            b = rng.randint(-80, 80)
            oracle.post_report(led, ts, loc, D, x, vintage_hash="0x" + f"{D:064x}")
            oracle.post_report(led, ts, bas, D, b, vintage_hash="0x" + f"{D + 1:064x}")
        elif what == "settle" and D != void_day:
            oracle.finalize(led, ts, loc, D)
            oracle.finalize(led, ts, bas, D)
            for pid, p in house_mm.day_policies(st, D):
                if p["status"] == "Bound":
                    policy.settle_policy(led, ts, pid)
            policy.settle_positions(led, ts, mk[D][1])
            house_mm.ret(led, ts, D)
        elif what == "void" and D == void_day:
            oracle.void_day(led, ts, loc, D)
            oracle.void_day(led, ts, bas, D)
            for pid, p in house_mm.day_policies(st, D):
                if p["status"] in ("Bought", "Bound"):
                    policy.void_policy(led, ts, pid)
            policy.settle_positions(led, ts, mk[D][1])
            house_mm.ret(led, ts, D)
        elif what == "epoch":
            led.emit(ts, "PoolEpoch", {})
            for rid, r in list(st["pool"]["withdrawals"].items()):
                if not r["claimed"] and ts >= r["claimableAt"]:
                    try:
                        pool.claim_withdraw(led, ts, int(rid))
                    except Revert:
                        pass
            for rid, r in list(st["wi"]["unstakes"].items()):
                if not r["claimed"] and ts >= r["claimableAt"]:
                    staking.claim_unstake(led, ts, int(rid))
            for d in sorted({int(x) for x in st["pool"]["openPolicies"]} | {int(x) for x in st["pool"]["deployedByDay"]}):
                try:
                    pool.close_day(led, ts, d)
                except Revert:
                    pass
        elif what == "withdraw":
            pool.request_withdraw(led, ts, ANVIL[4], "senior", st["pool"]["seniorShares"][ANVIL[4]] // 3)
        elif what == "unstake":
            staking.request_unstake(led, ts, ANVIL[4], st["wi"]["shares"][ANVIL[4]] // 2)
    return led


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_snapshot_plus_tail_equals_full_replay(seed):
    led = random_stream(seed)
    assert len(led.lines) > 150 and len(led.snapshots) >= 10
    final = led.hash()
    assert replay(led.world, led.lines).hash() == final
    rng = random.Random(seed)
    for snap in rng.sample(led.snapshots, 4):
        assert replay_from_snapshot(snap, led.lines).hash() == final


def test_edited_log_line_is_caught_even_when_rechained():
    led = random_stream(4)
    lines = copy.deepcopy(led.lines)
    i = next(n for n, ln in enumerate(lines) if ln["type"] == "OrderClaimed" and ln["payload"]["refund"] > 0)
    # 1. naive edit: refused (the reducer recomputes the line; the next line's prev no longer matches)
    bad = copy.deepcopy(lines)
    bad[i]["payload"]["refund"] += 1
    with pytest.raises((LogError, Revert)):
        replay(led.world, bad)
    # an edit the reducer cannot see (a later timestamp on a scheduler tick) still breaks the chain
    j = next(n for n, ln in enumerate(lines) if ln["type"] == "PoolEpoch" and n + 1 < len(lines))
    bad2 = copy.deepcopy(lines)
    bad2[j]["ts"] += 1
    with pytest.raises(LogError):
        replay(led.world, bad2)
    # 2. edit + recomputed prev hashes: the chain is valid again, but the reducer recomputes the refund
    for n in range(i + 1, len(bad)):
        bad[n]["prev"] = event_hash(bad[n - 1])
    with pytest.raises(Revert) as e:
        replay(led.world, bad)
    assert e.value.name == "BadClaim"
