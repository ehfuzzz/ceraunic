"""Phase 2 tests, only the failure modes that silently corrupt a hedge number:
(a) the ladder mapper must reproduce ins1's contract count and payout on a real day, and must not repeat
    ins1's bottom-bracket off-by-one when the bottom rung matters (puts);
(b) the ask at t never comes from a candle that ends after t (look-ahead);
(c) fee rounding: per order, up to the next cent, no phantom cent from float noise.
"""
import math

import numpy as np

from wi.eval.fees import kalshi_fee
from wi.eval.ladder import (Ladder, QuoteSeries, bracket_from_market, call_payout, ladder_payout,
                            normalize_candle, offer_status, put_payout, quantities)

# KXHIGHNY-26SEP18 as listed by Kalshi (ins1 row: K 80, winner 80-81, ladder_pay 0.5, 19.5 contracts)
NY_26SEP18 = [
    {"ticker": "KXHIGHNY-26SEP18-B80.5", "strike_type": "between", "floor_strike": 80.0, "cap_strike": 81.0},
    {"ticker": "KXHIGHNY-26SEP18-B82.5", "strike_type": "between", "floor_strike": 82.0, "cap_strike": 83.0},
    {"ticker": "KXHIGHNY-26SEP18-B84.5", "strike_type": "between", "floor_strike": 84.0, "cap_strike": 85.0},
    {"ticker": "KXHIGHNY-26SEP18-B86.5", "strike_type": "between", "floor_strike": 86.0, "cap_strike": 87.0},
    {"ticker": "KXHIGHNY-26SEP18-T80", "strike_type": "less", "floor_strike": None, "cap_strike": 80.0},
    {"ticker": "KXHIGHNY-26SEP18-T87", "strike_type": "greater", "floor_strike": 87.0, "cap_strike": None},
]


def _ladder():
    return Ladder(bracket_from_market(m) for m in NY_26SEP18)


def test_ladder_reproduces_ins1_day():
    lad = _ladder()
    assert lad.validate() is None
    K = lad.second_floor()
    assert K == 80.0
    pay = lambda T: call_payout(T, K, 6.0)  # noqa: E731
    q = quantities(lad, pay)
    assert math.isclose(sum(q.values()), 19.5)
    assert "KXHIGHNY-26SEP18-T80" not in q  # below K: buys nothing
    assert q["KXHIGHNY-26SEP18-T87"] == 6.0  # top rung at floor+1 = 88 -> capped
    assert ladder_payout(lad, "KXHIGHNY-26SEP18-B80.5", pay) == 0.5
    # the realised T = 80 sits in the winner; binning error = H(80) - 0.5 = -0.5
    assert lad.bracket_of(80).ticker == "KXHIGHNY-26SEP18-B80.5"
    # every integer maps to exactly one bracket (no double count at the edges)
    for T in range(60, 100):
        assert sum(b.contains(T) for b in lad.brackets) == 1


def test_bottom_bracket_is_cap_minus_one_for_puts():
    lad = _ladder()
    pay = lambda T: put_payout(T, 82.0, 6.0)  # noqa: E731
    q = quantities(lad, pay)
    # "less than 80" = T <= 79 -> put pays 82 - 79 = 3 (ins1's H(cap) would give 2)
    assert q["KXHIGHNY-26SEP18-T80"] == 3.0
    assert lad.bracket_of(79).ticker == "KXHIGHNY-26SEP18-T80"
    assert lad.bracket_of(80).ticker != "KXHIGHNY-26SEP18-T80"


def test_ask_at_t_never_uses_a_later_candle():
    rng = np.random.default_rng(1)
    for _ in range(200):
        n = int(rng.integers(1, 40))
        ts = np.sort(rng.choice(np.arange(0, 200 * 3600, 3600), size=n, replace=False))
        ask = rng.uniform(0.01, 0.99, n)
        bid = ask - 0.02
        perm = rng.permutation(n)  # candles may arrive unsorted
        qs = QuoteSeries(ts[perm], ask[perm], bid[perm])
        for t in rng.integers(-3600, 210 * 3600, 30):
            got = qs.at(int(t))
            before = ts[ts <= t]
            if len(before) == 0:
                assert got is None and offer_status(got) == "no_candle"
            else:
                assert got[2] <= t
                assert got[2] == before.max()
                assert got[0] == ask[ts == before.max()][0]


def test_both_candle_schemas_parse_the_same():
    hist = {"end_period_ts": 100, "yes_ask": {"close": "0.42"}, "yes_bid": {"close": "0.40"}}
    live = {"end_period_ts": 100, "yes_ask": {"close_dollars": "0.4200"}, "yes_bid": {"close_dollars": "0.4000"}}
    assert normalize_candle(hist) == normalize_candle(live) == (100, 0.42, 0.40)


def test_fee_rounds_up_per_order_without_float_noise():
    assert kalshi_fee(100, 0.5) == 1.75          # 0.07*100*0.25 = 1.75 exactly: no phantom cent
    assert kalshi_fee(1, 0.5) == 0.02            # 0.0175 -> 0.02
    assert kalshi_fee(1, 0.055) == 0.01          # Kalshi worked example 0.00363825 -> 0.01
    assert kalshi_fee(10, 0.99) == 0.01          # 0.00693 -> 0.01
    assert kalshi_fee(0, 0.5) == 0.0 and kalshi_fee(5, 1.0) == 0.0
    # rounding is per order: two orders of 1 cost more than one order of 2
    assert kalshi_fee(1, 0.3) * 2 > kalshi_fee(2, 0.3)
