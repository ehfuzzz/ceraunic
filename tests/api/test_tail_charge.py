"""Money failure mode: overcharging a cover the ladder cannot hedge (SPEC 18, 2026-09-30, tail charge made
strike-dependent).

Case: an NYC cool-day cover (capped put, 10 F cap) quoted at 2026-07-15 20:00Z for 2026-07-16, in the heat wave.
The lowest KXHIGHNY rung is "<89 F", so every line from 70 to 88 F lies beyond the ladder and the station leg
is $0. The v0 charge was the same at every line; a line further below the ladder edge is less likely to pay,
so it must cost strictly less until the one-tick-per-unit floor, and never more than the v0 charge.
"""
from __future__ import annotations

from wi.api import catalog as cat
from wi.api import clock, quoting
from wi.api import snapshot_data as sd
from wi.api.world import genesis
from wi.engine import hedge
from wi.engine.units import PPM, TICK, UNIT, date_to_day, mul_div

UNITS = 360


def test_cool_put_beyond_the_ladder_costs_less_further_from_the_edge_down_to_the_floor():
    w = genesis("tail-test")
    clock.advance(w, cat.START_TS)
    day = date_to_day("2026-07-16")
    biz = {"locationSite": "NYC", "owner": cat.DEMO_USERS[0], "businessId": "biz_tail"}
    rungs = sd.ladder("KXHIGHNY", day)
    quotes = hedge.quotes_at(rungs, w.now)
    bottom, _, v_bot, _ = hedge.top_bottom(rungs)
    assert v_bot == 880  # "<89 F": the case this test is about (whole range beyond the ladder for K <= 88)
    v0_charge = mul_div(UNITS * UNIT, hedge.rung_prob_ppm(bottom["ticker"], rungs, quotes), 2 * PPM)
    floor = UNITS * TICK

    lines = list(range(88, 69, -1))  # moving away from the ladder edge
    tails, prems = [], []
    for k in lines:
        rec = quoting.build(w, biz=biz, peril="cold", strike=k * 10, cap=100, units=UNITS, days=[day],
                            path="house-hedge", nonce0=1, emit=False)
        assert rec["station"] == 0 and rec["residual"] == 0
        tails.append(rec["tail"])
        prems.append(rec["premium"])

    assert all(floor <= t <= v0_charge for t in tails), (floor, v0_charge, tails)
    for i in range(1, len(lines)):
        assert prems[i] <= prems[i - 1], (lines[i], prems[i], prems[i - 1])
        if tails[i - 1] > floor:
            assert tails[i] < tails[i - 1], (lines[i], tails)
    assert tails[0] > floor  # at the edge the pool's exposure is priced above the floor
    assert tails[lines.index(75)] == floor  # 13 F below the edge: only the one-tick floor is charged
