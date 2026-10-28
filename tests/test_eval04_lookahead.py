"""Look-ahead controls for EVAL-04/05 (PREREG): how the history simulation could silently cheat.

1. Fair value or orders reading a candle that ends after the cutoff, or the realised settlement:
   perturbing every post-cutoff candle and the settlement must leave mu, every order, p* and every
   fill unchanged.
2. Settlement reading a CLI product issued after D+1 12:00Z (a later correction must not leak in).
"""
import numpy as np
import pandas as pd

from wi.oracle.revision import settlement_vintage
from wi.pool import kalshi_leg as kl
from wi.pool import sim

CLOSE = pd.Timestamp("2026-07-02 05:00", tz="UTC")


def _fixture(post_shift: float = 0.0):
    lows = [(None, 80.0, "less"), (80.0, 81.0, "between"), (82.0, 83.0, "between"), (84.0, 85.0, "between"),
            (86.0, 87.0, "between"), (87.0, None, "greater")]
    rungs = pd.DataFrame([dict(event_ticker="E", market_ticker=f"M{i}", strike_type=t, floor_strike=f, cap_strike=c,
                               close_time=CLOSE, result="yes" if i == 3 else "no") for i, (f, c, t) in enumerate(lows)])
    rungs["v"] = [kl.rung_value(t, f, c) for t, f, c in zip(rungs.strike_type, rungs.floor_strike, rungs.cap_strike)]
    rungs["K"] = 80.0
    rungs["Hv"] = kl.H(rungs["v"], rungs["K"])
    base = np.array([0.05, 0.15, 0.30, 0.30, 0.15, 0.05])
    rows = []
    for h in range(48, 0, -1):
        ts = CLOSE - pd.Timedelta(hours=h)
        after = ts > CLOSE - pd.Timedelta(hours=24)
        for i, b in enumerate(base):
            p = b + (post_shift * (1 if i >= 3 else -1) if after else 0.0)
            p = float(np.clip(p, 0.02, 0.97))
            rows.append(dict(market_ticker=f"M{i}", ts=ts, yes_ask_close=round(p + 0.01, 2), yes_bid_close=round(p - 0.01, 2)))
    return rungs, pd.DataFrame(rows)


def _run(post_shift: float):
    rungs, candles = _fixture(post_shift)
    q = kl.quotes_at(rungs, candles, 24, "c24")
    mu = float(kl.fair_value(q, "c24")["mu_c24"].iloc[0])
    h = np.random.default_rng(1).normal(0, 40, size=300)   # signed business units (from 1951-2020 weather)
    rng = np.random.default_rng([20260930, 0, CLOSE.toordinal(), 0])
    m = sim.run_market(h, sim.STATION, mu, 0.0, rng, 0.01, 0.01, 50_000.0)
    return mu, m


def test_post_cutoff_data_does_not_move_orders_prices_or_fills():
    mu0, m0 = _run(0.0)
    mu1, m1 = _run(0.25)            # every candle after the cutoff moves a lot
    assert mu0 == mu1
    assert np.array_equal(m0["tick"], m1["tick"]) and np.array_equal(m0["qty"], m1["qty"])
    assert m0["r"].p_star == m1["r"].p_star and m0["r"].fills == m1["r"].fills
    # the settlement value only enters after clearing
    assert sim.settle_market(m0, 0.9)["mo_settle"] != sim.settle_market(m0, 0.1)["mo_settle"] or m0["r"].q_star == 0


def test_settlement_ignores_cli_products_after_d1_12z():
    day = pd.Timestamp("2026-07-01")
    prods = pd.DataFrame([
        dict(station="NYC", day=day, issued_utc=pd.Timestamp("2026-07-01 20:32", tz="UTC"), prelim=True, tmax=88),
        dict(station="NYC", day=day, issued_utc=pd.Timestamp("2026-07-02 05:30", tz="UTC"), prelim=False, tmax=90),
        dict(station="NYC", day=day, issued_utc=pd.Timestamp("2026-07-02 13:30", tz="UTC"), prelim=False, tmax=93),  # late correction
    ])
    v = settlement_vintage(prods).iloc[0]
    assert v["tmax_settle"] == 90 and v["tmax_latest"] == 93
