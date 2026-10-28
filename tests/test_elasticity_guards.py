"""EVAL-06 guards. Only failure modes that silently corrupt the evaluation or lose money:

1. Look-ahead: a hedge ratio (or any fitted object: scale, K, per-unit fits, EB priors,
   climatology, baseline forecast F) that moves when post-origin sales or weather change.
   Property on a synthetic panel: corrupt everything after the origin, refit, compare.
2. Look-ahead in the hedge-time price: a candle ending after the decision time must never set
   the price, and a stale candle (> 6 h) must not either.
3. Ladder mapping: the ins1 19.5-contracts-per-$1/degF fixture, the "less cap=c -> T <= c-1"
   bracket fix, payout on the winning bracket, and fee rounding to the cent.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from wi.elasticity import evaluate as E
from wi.elasticity import hedge as H
from wi.elasticity import ladder_shim as LS
from wi.elasticity.panel import GROUPS, Group, Panel

ORIGIN = "2025-01-01"


def _weather(seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("1990-01-01", "2026-06-30", freq="D")
    doy = idx.dayofyear.values
    t = np.rint(58 + 24 * np.sin(2 * np.pi * (doy - 110) / 365.25) + rng.normal(0, 6, len(idx)))
    p = np.where(rng.random(len(idx)) < 0.3, rng.exponential(0.3, len(idx)), 0.0)
    return pd.DataFrame({"tmax_f": t, "prcp_in": p, "snow_in": 0.0}, index=idx)


def _panel(w: pd.DataFrame, seed=2) -> Panel:
    rng = np.random.default_rng(seed)
    g = Group("GS", "synthetic", "bike", "SYN", "SYN", "KXHIGHNY", None, "none", 20, "test",
              ORIGIN, None, (ORIGIN,))
    dates = pd.date_range("2022-07-01", "2026-06-30", freq="D")
    T = w["tmax_f"].reindex(dates).values
    P = w["prcp_in"].reindex(dates).values
    doy = dates.dayofyear.values
    nu = 12
    beta = rng.normal(-0.02, 0.008, nu)
    heat = np.clip(T - 82, 0, 10)
    ly = (6 + 0.4 * np.sin(2 * np.pi * doy / 365.25))[:, None] + heat[:, None] * beta[None, :] \
         - 0.15 * (P >= 0.01)[:, None] + rng.normal(0, 0.12, (len(dates), nu))
    Y = np.exp(ly) * rng.uniform(0.5, 3, nu)[None, :]
    prev = dates - pd.Timedelta(days=1)
    return Panel(g, dates.values.astype("datetime64[D]"), np.array([f"u{i}" for i in range(nu)]), Y, Y.copy(),
                 T, P, np.zeros(len(dates)), w["tmax_f"].reindex(prev).values, w["prcp_in"].reindex(prev).values)


def _fitted_objects(p: Panel, monkeypatch, w: pd.DataFrame) -> dict:
    monkeypatch.setattr(E, "weather_series", lambda station: w)
    monkeypatch.setitem(GROUPS, "GS", p.group)
    ctx = E.build_ctx(p, ORIGIN, 365, E.Cfg(boot=10))
    E.baseline(ctx)
    out = {"K": ctx.K, "profile": tuple(sorted(ctx.k_profile.items())), "F": ctx.F.copy(),
           "scale_pre": ctx.Ys[: ctx.i0].copy(), "clim_heat": ctx.clim["heat"].copy()}
    for n in (60, 180, 365):
        f = E.fit_n(ctx, n)
        out[f"coef_{n}"] = f["coef"].copy()
        out[f"se_heat_{n}"] = f["se"]["heat"].copy()
        ab = E.arm_betas(ctx, n)
        for arm in ("A1", "A2", "A3"):
            h, hw = E.hedge_sizes(ctx, *ab[arm])
            out[f"h_{arm}_{n}"] = h
            out[f"hw_{arm}_{n}"] = hw
    return out


def test_no_post_origin_data_in_any_fitted_object(monkeypatch):
    w = _weather()
    p = _panel(w)
    base = _fitted_objects(p, monkeypatch, w)

    # corrupt every post-origin input: sales x10 with noise, and a +15 degF / all-wet weather shift
    i0 = int(np.where(p.dates == np.datetime64(ORIGIN))[0][0])
    rng = np.random.default_rng(9)
    p2 = Panel(p.group, p.dates, p.units, p.Y.copy(), p.CNT.copy(), p.tmax.copy(), p.prcp.copy(),
               p.snow.copy(), p.tmax_prev.copy(), p.prcp_prev.copy())
    p2.Y[i0:] *= 10 * rng.uniform(0.5, 1.5, p2.Y[i0:].shape)
    p2.CNT[i0:] = p2.Y[i0:]
    p2.tmax[i0:] += 15
    p2.prcp[i0:] = 1.0
    p2.tmax_prev[i0 + 1:] += 15
    p2.prcp_prev[i0 + 1:] = 1.0
    w2 = w.copy()
    w2.loc[w2.index >= pd.Timestamp(ORIGIN), "tmax_f"] += 15
    w2.loc[w2.index >= pd.Timestamp(ORIGIN), "prcp_in"] = 1.0
    corrupt = _fitted_objects(p2, monkeypatch, w2)

    assert set(base) == set(corrupt)
    for k in base:
        if isinstance(base[k], np.ndarray):
            np.testing.assert_array_equal(base[k], corrupt[k], err_msg=k)
        else:
            assert base[k] == corrupt[k], k


def test_pre_origin_change_does_move_the_fit(monkeypatch):
    """Guard against a vacuous property: the same corruption before the origin must change the fit."""
    w = _weather()
    p = _panel(w)
    base = _fitted_objects(p, monkeypatch, w)
    i0 = int(np.where(p.dates == np.datetime64(ORIGIN))[0][0])
    p2 = Panel(p.group, p.dates, p.units, p.Y.copy(), p.CNT.copy(), p.tmax, p.prcp, p.snow, p.tmax_prev, p.prcp_prev)
    hot = p.tmax[i0 - 200:i0] > 82
    p2.Y[i0 - 200:i0][hot] *= 3
    moved = _fitted_objects(p2, monkeypatch, w)
    assert not np.allclose(base["coef_365"], moved["coef_365"])


def test_price_never_uses_a_candle_after_the_decision_time():
    rng = np.random.default_rng(3)
    close = pd.Timestamp("2025-07-16 03:59", tz="UTC")
    ts = pd.date_range(close - pd.Timedelta(hours=40), close, freq="h")
    c = pd.DataFrame({"market_ticker": "M", "ts": ts, "yes_ask_close": rng.uniform(0.05, 0.95, len(ts)),
                      "yes_bid_close": rng.uniform(0.01, 0.5, len(ts))})
    mk = pd.DataFrame({"market_ticker": ["M"], "close_time": [close]})
    for Hh in (24, 30, 12, 2):
        dec = close - pd.Timedelta(hours=Hh)
        a, b = LS.quotes_at(mk, c, Hh)
        ref = c[c.ts <= dec].iloc[-1]
        assert a[0] == ref.yes_ask_close and b[0] == ref.yes_bid_close
        assert LS.price_at(c, dec) == (ref.yes_ask_close, ref.yes_bid_close)
        # wild candles after the decision time change nothing
        c2 = c.copy()
        c2.loc[c2.ts > dec, ["yes_ask_close", "yes_bid_close"]] = [0.5, 0.49]
        a2, b2 = LS.quotes_at(mk, c2, Hh)
        assert (a2[0], b2[0]) == (a[0], b[0])
    # stale: the only candle is 7 h before the decision time -> no price
    old = c[c.ts == close - pd.Timedelta(hours=31)]
    a, b = LS.quotes_at(mk, old, 24)
    assert np.isnan(a[0]) and np.isnan(b[0])


def _fixture_ladder():
    # 2023+ style ladder: less cap 84 sits next to between 84-85 (so "less 84" means T <= 83)
    rows = [("less", np.nan, 84.0), ("between", 84.0, 85.0), ("between", 86.0, 87.0),
            ("between", 88.0, 89.0), ("between", 90.0, 91.0), ("greater", 91.0, np.nan)]
    return pd.DataFrame(rows, columns=["strike_type", "floor_strike", "cap_strike"])


def test_ladder_mapping_ins1_fixture_and_bracket_fix():
    lad = _fixture_ladder()
    assert LS.ladder_is_partition(lad)
    bounds = [LS.bracket_bounds(*r) for r in lad.itertuples(index=False)]
    # T = 84 belongs to "between 84-85", not to "less 84" (the ins1 off-by-one)
    owner = [i for i, (lo, hi) in enumerate(bounds) if lo <= 84 <= hi]
    assert owner == [1]
    K, cap = 84.0, 6.0  # K = floor of the second bracket (ins1)
    g = np.array([np.clip(LS.rep_value(*r) - K, 0, cap) for r in lad.itertuples(index=False)])
    assert g.sum() == pytest.approx(19.5)            # 0 + 0.5 + 2.5 + 4.5 + 6 + 6

    # execution: h = $10/degF on a day where T = 87 settles (bracket 86-87 wins)
    L = H.DayLadder(G=np.r_[g, [0, 0]][None, :], ASK=np.r_[[0.02, 0.10, 0.30, 0.35, 0.15, 0.08], [np.nan] * 2][None, :],
                    BID=np.r_[[0.01, 0.08, 0.27, 0.32, 0.12, 0.06], [np.nan] * 2][None, :],
                    NOBUY=np.zeros((1, 8), bool), NOSELL=np.zeros((1, 8), bool),
                    WIN=np.r_[[0, 0, 1, 0, 0, 0], [0, 0]].astype(bool)[None, :], avail=np.array([True]))
    r = H.ladder_leg(np.array([[10.0]]), L)
    assert r["contracts"][0, 0] == 5 + 25 + 45 + 60 + 60
    assert r["pay"][0, 0] == 25                      # = h * g(86.5)
    exp_prem = sum(q * a + H.fee(np.array(q), np.array(a)) for q, a in
                   ((5, 0.10), (25, 0.30), (45, 0.35), (60, 0.15), (60, 0.08)))
    assert r["prem"][0, 0] == pytest.approx(float(exp_prem))
    # a needed rung with no offer makes the whole day unhedgeable (no partial ladder)
    L.NOBUY[0, 3] = True
    r2 = H.ladder_leg(np.array([[10.0]]), L)
    assert r2["unhedge"][0, 0] and r2["prem"][0, 0] == 0 and r2["pay"][0, 0] == 0


def test_fee_rounds_up_to_the_cent():
    assert LS.kalshi_fee(1, 0.5) == 0.02            # 0.07 * 0.25 = 1.75c -> 2c
    assert LS.kalshi_fee(100, 0.5) == 1.75          # exact cents stay exact
    assert float(H.fee(np.array(100.0), np.array(0.5))) == 1.75
    assert float(H.fee(np.array(1.0), np.array(0.5))) == 0.02
    assert float(H.fee(np.array(-3.0), np.array(0.9))) == LS.kalshi_fee(3, 0.9)


def test_vectorised_fee_matches_the_shared_scalar_fee():
    """hedge.fee (vectorised, used for every unit-day) must equal the per-order fee the engine uses."""
    rng = np.random.default_rng(5)
    q = rng.integers(-300, 300, 2000).astype(float)
    p = np.round(rng.uniform(0.01, 0.99, 2000), 2)
    vec = H.fee(q, p)
    ref = np.array([LS.kalshi_fee(abs(a), b) for a, b in zip(q, p)])
    np.testing.assert_array_equal(vec, ref)
