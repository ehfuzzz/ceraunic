"""Phase 3 tests: only the four silent-corruption failure modes listed in 03-RESEARCH "Tests that belong".

1. Day alignment: a grid heat maximum at label D+1 lands on calendar day D through the real loaders, for
   both grids, and a calendar Mon-Sun week sums grid labels Tue-Mon.
2. No look-ahead: fitted objects (PC1 weights, fitted beta) use only train-window units and do not move
   when test-window data change.
3. Leave-one-out: perturbing the held-out point's own series leaves every index used to evaluate it unchanged.
4. End-to-end fixture: 2 markets x 3 points x 60 test days -> results.json with known row counts and one
   hand-checked HE.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from wi.eval03 import designs as D
from wi.eval03 import sources
from wi.eval03.designs import Config, Data, Opts, Units, unit_windows
from wi.eval03.indexes import fit_beta_train, fit_pc1
from wi.eval03.run import clean, evaluate

ROOT = Path(__file__).resolve().parents[1]


# ------------------------------------------------------------------------------------------ fixture
def _fixture(seed: int = 7):
    rng = np.random.default_rng(seed)
    days = pd.date_range("2024-11-15", "2025-03-01")  # train 2024-11-22..12-31 used, test = 60 days
    n = len(days)
    coords = {"AAA": (40.0, -74.0), "A1": (40.05, -74.0), "A2": (40.0, -74.1), "A3": (40.2, -74.2),
              "BBB": (41.8, -87.7), "B1": (41.85, -87.7), "B2": (41.8, -87.85), "B3": (42.0, -88.0)}
    county = {"AAA": "X: One", "A1": "X: One", "A2": "X: Two", "A3": "X: Three",
              "BBB": "Y: One", "B1": "Y: Two", "B2": "Y: Two", "B3": "Y: Three"}
    codes = list(coords)
    base = {"A": 60 + 10 * np.sin(np.arange(n) / 9) + rng.normal(0, 4, n),
            "B": 50 + 12 * np.sin(np.arange(n) / 7) + rng.normal(0, 5, n)}
    T = pd.DataFrame({c: np.round(base[c[0]] + (0 if len(c) == 3 else rng.normal(0, 2.5, n) + 1.0)) for c in codes}, index=days)
    P = pd.DataFrame({c: np.round(np.maximum(rng.gamma(0.4, 0.3, n) - 0.05, 0), 2) for c in codes}, index=days)
    NT = T + rng.normal(0, 1.0, T.shape)
    NP = (P + np.abs(rng.normal(0, 0.02, P.shape))).round(2)
    PT = T + rng.normal(0, 1.0, T.shape)
    PP = (P + np.abs(rng.normal(0, 0.02, P.shape))).round(2)
    disc = {}
    for S in ("AAA", "BBB"):
        cells = [f"c{k}" for k in range(9)]
        lat = np.full(9, coords[S][0]) + np.linspace(-0.1, 0.1, 9)
        dist = np.linspace(2, 38, 9)
        for src, TT, PPP in (("prism", PT, PP), ("nclimgrid", NT, NP)):
            disc[(src, S)] = {"T": pd.DataFrame({c: TT[S] + rng.normal(0, 1.5, n) for c in cells}, index=days),
                              "P": pd.DataFrame({c: (PPP[S] + np.abs(rng.normal(0, 0.03, n))).round(2) for c in cells}, index=days),
                              "lat": lat, "dist": dist}
    cty = sorted(set(county.values()))
    CT = pd.DataFrame({k: T[[c for c in codes if county[c] == k]].mean(axis=1) + rng.normal(0, 0.5, n) for k in cty}, index=days)
    CP = pd.DataFrame({k: P[[c for c in codes if county[c] == k]].mean(axis=1) for k in cty}, index=days)
    data = Data(T=T, P=P, NT=NT, NP=NP, PT=PT, PP=PP, disc=disc, CT=CT, CP=CP)
    net = {"AAA": ["A1", "A2", "A3"], "BBB": ["B1", "B2", "B3"]}
    cfg = Config(markets=("AAA", "BBB"), truth={"temperature": net, "rain": net}, network={"temperature": net, "rain": net},
                 outer={"temperature": {}, "rain": {}}, coords=coords, county=county, train=("2024-11-22", "2024-12-31"),
                 test=("2025-01-01", "2025-03-01"), draws=50, min_pay_days=10, min_pay_weeks=2, extras=False)
    return cfg, data


# ------------------------------------------------------------------------------------------ 1. alignment
def test_grid_heat_day_lands_on_calendar_day_both_grids(tmp_path, monkeypatch):
    heat_day = pd.Timestamp("2025-07-28")  # calendar (CLI) day of the heat maximum
    labels = pd.date_range("2025-07-20", "2025-08-12")
    tmax_c = np.where(labels == heat_day + pd.Timedelta(days=1), 38.0, 27.0)  # the grid stores it at label D+1
    prcp_mm = np.where((labels >= "2025-07-29") & (labels <= "2025-08-04"), 25.4, 0.0)  # labels Tue..Mon
    # nClimGrid point-cell loader
    (tmp_path / "nclimgrid_points").mkdir()
    pd.DataFrame({"code": "NYC", "cell_id": "x", "lat": 40.78, "lon": -73.97, "label_day": labels.date,
                  "tmax_c": tmax_c, "prcp_mm": prcp_mm, "status": "scaled"}).to_parquet(tmp_path / "nclimgrid_points" / "202507.parquet")
    monkeypatch.setattr(sources, "E3", tmp_path)
    n = sources.nclimgrid_points().set_index("day")
    assert n.tmax_f.idxmax() == heat_day
    # PRISM disc loader (Phase 1 hive layout)
    part = tmp_path / "disc" / "source=prism" / "station=NYC"
    part.mkdir(parents=True)
    pd.DataFrame({"cell_id": "x", "lat": 40.78, "lon": -73.97, "dist_km": np.float32(1.0), "label_day": labels.date,
                  "tmax_f_tenths": pd.array(np.round((tmax_c * 9 / 5 + 32) * 10), dtype="Int16"),
                  "prcp_hundredths_in": pd.array(np.round(prcp_mm / 25.4 * 100), dtype="Int32"), "status": "an91d",
                  "prism_release_tmax": pd.array([8] * len(labels), dtype="Int8"),
                  "prism_release_ppt": pd.array([8] * len(labels), dtype="Int8")}).to_parquet(part / "part-202507.parquet")
    monkeypatch.setattr(sources, "DISC", tmp_path / "disc")
    g = sources.grid_disc("prism").set_index("day")
    assert g.tmax_f.idxmax() == heat_day
    # weekly: calendar Mon 07-28..Sun 08-03 = grid labels Tue 07-29..Mon 08-04 -> 7 inches, neighbours 0
    wk = D.to_units(g[["prcp_in"]], "week")["prcp_in"]
    assert wk.loc["2025-08-03"] == pytest.approx(7.0)
    assert wk.loc["2025-07-27"] == 0.0 and wk.loc["2025-08-10"] == 0.0
    # and on the real cache when present: the nClimGrid cell at Central Park peaks on the CLI hottest day of
    # summer 2025, not the day after
    monkeypatch.undo()
    if (sources.E3 / "nclimgrid_points").exists() and (sources.WEATHER / "official_daily.parquet").exists():
        cli = sources.cli_daily()
        nyc = cli[(cli.code == "NYC") & (cli.day >= "2025-06-01") & (cli.day <= "2025-08-31")].set_index("day").tmax_f
        d = nyc.idxmax()
        cell = sources.nclimgrid_points().query("code == 'NYC'").set_index("day").tmax_f
        assert cell.loc[d - pd.Timedelta(days=1): d + pd.Timedelta(days=1)].idxmax() == d


# ------------------------------------------------------------------------------------------ 2. no look-ahead
def test_fitted_objects_use_train_window_only():
    cfg, data = _fixture()
    U = Units(data, "temperature", "day")
    tr, te = unit_windows(U.index, "day", cfg)
    X, s = U.st[["A1", "A2", "A3"]], U.st["AAA"]
    fit = fit_pc1(X, s, cfg.train[0], cfg.train[1])
    assert fit["fit_last"] < cfg.test[0]
    Xp = X.copy()
    Xp.loc[cfg.test[0]:] += np.random.default_rng(1).normal(0, 20, Xp.loc[cfg.test[0]:].shape)
    assert np.allclose(fit_pc1(Xp, s, cfg.train[0], cfg.train[1])["w"], fit["w"])
    # the pipeline's own fits record train-only dates
    res = evaluate(cfg, data)
    for v in ("temperature", "rain"):
        for k, f in res["fits"][v].items():
            if f["fallback"] == "equal":  # too few complete train units: equal weights, no data used
                assert f["fit_last"] is None
            else:
                assert f["fit_last"] < cfg.test[0], (v, k, f["fit_last"])
    # fitted-beta sensitivity: train units only, unchanged by test-window data
    f = D.payout_fn(cfg, U, "AAA", Opts(), data)
    mk = D.market_level(cfg, U, "AAA", f, Opts())
    pr = D.pair(cfg, U, "temperature", "AAA", "A3", f, mk, Opts())
    b1 = fit_beta_train(pr["E"] - pr["HS"], pr["r"]["R-A"], U.index, tr)
    E2 = pr["E"].copy()
    E2[te] = E2[te] + 5.0
    b2 = fit_beta_train(E2 - pr["HS"], pr["r"]["R-A"], U.index, tr)
    assert b1["fit_last"] < cfg.test[0] and b1["beta"] == b2["beta"]


# ------------------------------------------------------------------------------------------ 3. LOO
@pytest.mark.parametrize("variable,unit", [("temperature", "day"), ("rain", "week")])
def test_held_out_point_never_enters_its_own_index(variable, unit):
    cfg, data = _fixture()
    rng = np.random.default_rng(3)

    def residuals(dd):
        U = Units(dd, variable, unit)
        f = D.payout_fn(cfg, U, "AAA", Opts(), dd)
        mk = D.market_level(cfg, U, "AAA", f, Opts())
        return D.pair(cfg, U, variable, "AAA", "A2", f, mk, Opts())

    base = residuals(data)
    col = "T" if variable == "temperature" else "P"
    pert = Data(**{**data.__dict__})
    panel = getattr(data, col).copy()
    panel["A2"] = (panel["A2"] + rng.normal(0, 8 if col == "T" else 0.5, len(panel))).clip(lower=0).round(2)
    setattr(pert, col, panel)
    new = residuals(pert)
    assert not np.allclose(np.nan_to_num(new["E"]), np.nan_to_num(base["E"]))  # the perturbation is real
    for d in ("R-A", "R-A-PC", "P-A", "P-A-IDW"):
        assert np.array_equal(np.isnan(new["r"][d]), np.isnan(base["r"][d])), d
        assert np.allclose(np.nan_to_num(new["r"][d]), np.nan_to_num(base["r"][d])), d
    assert new["meta"]["R-A-PC"]["w"] == base["meta"]["R-A-PC"]["w"]
    assert "A2" not in base["meta"]["R-A-PC"]["w"] and "A2" not in base["meta"]["P-A-IDW"]["w"]


# ------------------------------------------------------------------------------------------ 4. end to end
def test_end_to_end_fixture_results_json(tmp_path):
    cfg, data = _fixture()
    res = clean(evaluate(cfg, data))
    p = tmp_path / "results.json"
    p.write_text(json.dumps(res, allow_nan=False))
    out = json.loads(p.read_text())
    n_designs = len(D.DESIGNS)
    assert len(out["pairs"]["temperature"]) == 2 * 3 * n_designs
    assert len(out["pairs"]["rain"]) == 2 * 3 * n_designs
    assert len(out["eval02"]["points"]) == 12
    assert out["counts"]["temperature"]["test_units"] == 60
    assert set(out["bakeoff"]["temperature"]) == set(D.DESIGNS)
    # hand check: HE(D0) at (AAA, A3), computed here without the package's payout code
    T = data.T
    days = pd.date_range(cfg.test[0], cfg.test[1])
    E, H = [], []
    for d in days:
        prev = [T.loc[d - pd.Timedelta(days=k), "AAA"] for k in range(1, 8)]
        K = math.floor(sum(prev) / 7)
        E.append(min(max(math.floor(T.loc[d, "A3"] + 0.5) - K, 0), 6))
        H.append(min(max(math.floor(T.loc[d, "AAA"] + 0.5) - K, 0), 6))
    E, H = np.array(E, float), np.array(H, float)
    he0 = 1 - np.var(E - H) / np.var(E)
    row = next(x for x in out["eval02"]["points"] if x["market"] == "AAA" and x["point"] == "A3" and x["variable"] == "temperature")
    assert row["he0"] == pytest.approx(he0, abs=1e-6)
    # the dHE identity on the same pair for a non-zero design: dHE = Var(r)(2 beta - 1)/Var(E)
    r = next(x for x in out["pairs"]["temperature"] if x["market"] == "AAA" and x["point"] == "A3" and x["design"] == "R-A")
    assert r["dhe"] == pytest.approx(r["sd_r"] ** 2 * r["eta"] / np.var(E), abs=1e-5)
