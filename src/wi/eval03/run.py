"""Phase 3 run: EVAL-02 (geography basis) and EVAL-03 (residual bake-off).

`evaluate(cfg, data, ctx)` is pure (no I/O, no clock) so that two runs give the same results.json apart from
the meta timestamps; `main()` loads the caches, calls it, and writes reports/eval-03/.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
from pathlib import Path

import numpy as np
import pandas as pd

from wi.eval03 import designs as D
from wi.eval03 import metrics as M
from wi.eval03.designs import DESIGNS, ROLE, Config, Opts, Units, unit_windows
from wi.eval03.indexes import fit_beta_train, haversine

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "reports" / "eval-03"
VARS = (("temperature", "day"), ("rain", "week"))
P1_DHE, P2_SHARE, P3_ETA, HE_GRADE, TIE_HE, PC1_MARGIN = 0.10, 0.70, 0.5, 0.70, 0.02, 0.03
P2_MARKETS = {"temperature": 4, "rain": 3}
LAMBDAS = (0.10, 0.25, 0.50)

# P4: settleability, judged on the written formula and the data's publication and revision cycle
# (docs/CONVENTIONS.md section 11; Phase 4 revision numbers). Same answer for temperature and rain.
P4 = {
    "D0": (True, "Kalshi ladder / NWS CLI; baseline"),
    "G1-P": (True, "PRISM cell values: count-1 grid at T+1, count-2 at T+5; settle on the count-2 snapshot the oracle "
                   "archives (PRISM keeps no old versions, so the oracle's copy is the only record)"),
    "G1-N": (True, "nClimGrid prelim about 2 days behind (provisional within 7 days), final on the first scaled file "
                   "(M+1, days 4-7); prelim-to-scaled moves Tmax >= 0.5 F on 64 % of cell-days (Phase 4)"),
    "G1-P*": (True, "as G1-P, minus the CLI; continuity only"),
    "G1-N*": (True, "as G1-N, minus the CLI; continuity only"),
    "C1-N": (True, "NCEI county-average CSV (published number); prelim within 7 days, final on the scaled file"),
    "R-A": (True, "equal-weight mean of NWS CLI / GHCN-D values over a published station list, T+1; quorum and "
                  "T+7 GHCN-D fallback (spec template)"),
    "R-P": (True, "cos-lat mean of a fixed PRISM cell list; count-2 snapshot at T+5"),
    "R-N": (True, "cos-lat mean of a fixed nClimGrid cell list; prelim provisional, scaled final"),
    "R-A-PC": (True, "as R-A with a weight vector published at listing"),
    "R-N-PC": (True, "as R-N with a weight vector published at listing"),
    "P-A": (True, "one NWS CLI / GHCN-D station minus S, T+1"),
    "P-A-IDW": (True, "fixed IDW blend of 3 published stations, T+1"),
}


# ------------------------------------------------------------------------------------------ helpers
def _f(x, nd=6):
    if x is None:
        return None
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return None if not math.isfinite(float(x)) else round(float(x), nd)
    return x


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, np.ndarray):
        return [clean(v) for v in o.tolist()]
    return _f(o)


def med(x) -> float:
    x = np.asarray([v for v in x if v is not None and np.isfinite(v)], float)
    return float(np.median(x)) if len(x) else float("nan")


def pairs_of(cfg: Config, variable: str, outer: bool = False) -> list[tuple[str, str]]:
    src = cfg.outer if outer else cfg.truth
    return [(m, b) for m in cfg.markets for b in src[variable].get(m, [])]


# ------------------------------------------------------------------------------------------ core
def run_variable(cfg, data, U, variable, opts, mask, plist, keep_arrays=False, ladder_leg=False):
    """Every (pair, design) for one variable/unit/option set. Returns rows + per-unit stat columns."""
    rows, cols, arrs = [], {}, {}
    mk_cache, f_cache = {}, {}
    for m, b in plist:
        if m not in f_cache:
            f_cache[m] = D.payout_fn(cfg, U, m, opts, data)
            mk_cache[m] = D.market_level(cfg, U, m, f_cache[m], opts)
        f = f_cache[m]
        pr = D.pair(cfg, U, variable, m, b, f, mk_cache[m], opts)
        HS = pr["HS"]
        if ladder_leg:
            lad = (data.ladder or {}).get(m)
            HS = lad["X"].reindex(U.index).to_numpy(float) if lad is not None else np.full(len(U.index), np.nan)
        d0 = M.point_stats(pr["E"], HS, pr["r"]["D0"], mask)
        min_pay = cfg.min_pay_days if U.unit == "day" else (cfg.min_pay_weeks if U.unit == "week" else 1)
        included = bool(d0["n_pay"] >= min_pay and np.isfinite(d0["var_E"]) and d0["var_E"] > 0)
        dist = haversine(cfg.coords[m], cfg.coords[b])
        for d in DESIGNS:
            r = pr["r"][d]
            st = M.point_stats(pr["E"], HS, r, mask)
            ok = included and np.isfinite(st["dhe"]) and st["n_pay"] >= min_pay
            row = {"market": m, "point": b, "design": d, "dist_km": round(dist, 2), "included": bool(included),
                   "available": bool(ok), "zero": d in pr["zero"] or d == "D0", "zero_reason": pr["zero"].get(d), **st}
            rows.append(row)
            if ok:
                cols[(m, b, d)] = M.stat_columns(pr["E"], HS, r, mask)
            if keep_arrays:
                arrs[(m, b, d)] = (pr["E"], HS, r)
        arrs[("meta", m, b)] = pr["meta"]
    return {"rows": rows, "cols": cols, "arrs": arrs, "mk": {m: v["meta"] for m, v in mk_cache.items()}}


def pooled(rows: list[dict], variable: str, design: str, markets, lam=0.25, premium=None,
           restrict: set | None = None) -> dict:
    R = [r for r in rows if r["design"] == design and r["available"]]
    if restrict is not None:
        R = [r for r in R if (r["market"], r["point"]) in restrict]
    if not R:
        return {"n_pairs": 0}
    nz = [r for r in R if not r["zero"]]
    by_m = {}
    for m in markets:
        rm = [r["dhe"] for r in nz if r["market"] == m]
        allm = [r["dhe"] for r in R if r["market"] == m]
        by_m[m] = {"median_dhe": med(rm) if rm else (0.0 if allm else float("nan")),
                   "median_he": med([r["he"] for r in R if r["market"] == m]),
                   "n": len(allm), "n_nonzero": len(rm)}
    etas = [r["eta"] for r in nz if r["sd_r"] > 0]
    sds = [r["sd_r"] for r in nz if r["sd_r"] > 0]
    out = {
        "n_pairs": len(R), "n_pairs_nonzero": len(nz),
        "pooled_median_he": med([r["he"] for r in R]),
        "pooled_median_he0_same_pairs": med([r["he0"] for r in R]),
        "pooled_median_dhe": med([r["dhe"] for r in R]),
        "share_pairs_dhe_pos": (float(np.mean([r["dhe"] > 0 for r in nz])) if nz else float("nan")),
        "markets_dhe_pos": int(sum(1 for m in markets if np.isfinite(by_m[m]["median_dhe"]) and by_m[m]["median_dhe"] > 0)),
        "pooled_median_eta": med(etas),
        "pooled_median_beta": med([r["beta"] for r in nz if r["sd_r"] > 0]),
        "sd_r_median": med(sds),
        "mean_r_median": med([r["mean_r"] for r in nz if r["sd_r"] > 0]),
        "L_median": lam * med(sds) if sds else float("nan"),
        "L_by_lambda": {str(l_): (l_ * med(sds) if sds else float("nan")) for l_ in LAMBDAS},
        "by_market": by_m,
    }
    if premium:
        pct = [lam * r["sd_r"] / premium[r["market"]] for r in nz if r["sd_r"] > 0 and premium.get(r["market"])]
        out["L_pct_station_premium_median"] = med(pct)
    cph = [lam * r["sd_r"] / max(r["dhe"], 0.01) for r in nz if r["sd_r"] > 0]
    out["cost_per_he_point_median"] = med(cph)
    return out


def bootstrap(res: dict, designs: list[str], mask: np.ndarray, cfg: Config, block: int,
              restrict: dict | None = None) -> dict:
    """Joint circular block bootstrap on the test units: one resampled calendar per draw, shared by every
    pair and market. Returns per-design arrays [draws] of pooled median HE, dHE, HE0 (same pairs)."""
    idx = np.where(mask)[0]
    W = M.circular_block_counts(len(idx), cfg.draws, block, cfg.seed)
    out = {}
    for d in designs:
        keys = sorted(k for k in res["cols"] if k[2] == d and (restrict is None or restrict.get(d) is None
                                                               or (k[0], k[1]) in restrict[d]))
        if not keys:
            continue
        Mx = np.stack([res["cols"][k][idx] for k in keys], axis=1)  # [U, P, 7]
        Tb = np.einsum("bu,upk->bpk", W, Mx)
        h = M.he_from_sums(Tb)
        with np.errstate(all="ignore"):
            out[d] = {"he": np.nanmedian(h["he"], axis=1), "dhe": np.nanmedian(h["dhe"], axis=1),
                      "he0": np.nanmedian(h["he0"], axis=1), "keys": keys}
    return out


def distinct_contracts(rows, design, market, ctx_cells, meta) -> int:
    R = [r for r in rows if r["design"] == design and r["market"] == market and r["available"] and not r["zero"]]
    if design == "D0":
        return 0
    if design.startswith("R-"):
        return 1 if R else 0
    if design == "C1-N":
        return len({meta[("meta", r["market"], r["point"])]["C1-N"]["county_b"] for r in R})
    if design == "P-A":
        return len({meta[("meta", r["market"], r["point"])]["P-A"]["partner"] for r in R})
    if design in ("G1-P", "G1-P*"):
        return len({ctx_cells["prism_cell"].get(r["point"]) for r in R})
    if design in ("G1-N", "G1-N*"):
        return len({ctx_cells["nclimgrid_cell"].get(r["point"]) for r in R})
    return len(R)  # P-A-IDW: one blend per business point


def evaluate(cfg: Config, data, ctx: dict | None = None) -> dict:
    ctx = ctx or {}
    cells = ctx.get("cells", {"prism_cell": {}, "nclimgrid_cell": {}})
    out = {"eval02": {"points": [], "points_outer": []}, "bakeoff": {}, "pairs": {}, "outer": {}, "concentration": {},
           "verdicts": {"winner": {}, "runner_up": {}, "winner_vs_runner_up": {}, "rules": {}, "best_if_none": {}},
           "sensitivities": {}, "fits": {}, "counts": {}}
    boots = {}
    for variable, unit in VARS:
        U = Units(data, variable, unit)
        tr, te = unit_windows(U.index, unit, cfg)
        plist = pairs_of(cfg, variable)
        res = run_variable(cfg, data, U, variable, Opts(), te, plist, keep_arrays=True)
        rows = res["rows"]
        out["counts"][variable] = {"test_units": int(te.sum()), "train_units": int(tr.sum()),
                                   "pairs": len(plist),
                                   "pairs_included": len({(r["market"], r["point"]) for r in rows if r["included"]})}
        # ---- EVAL-02: HE of the station leg alone
        d0 = [r for r in rows if r["design"] == "D0"]
        inc = [r for r in d0 if r["included"]]
        for r in d0:
            out["eval02"]["points"].append({"market": r["market"], "point": r["point"], "variable": variable,
                                            "dist_km": r["dist_km"], "he0": r["he0"], "included": r["included"],
                                            "n": r["n"], "n_pay": r["n_pay"]})
        block = cfg.block_days if unit == "day" else cfg.block_weeks
        # PRISM-missing pairs: G1-N also on the reduced set (deviation 1)
        prism_pairs = {(r["market"], r["point"]) for r in rows if r["design"] == "G1-P" and r["available"]}
        bs = bootstrap(res, DESIGNS, te, cfg, block)
        bs_red = bootstrap(res, ["G1-N"], te, cfg, block, restrict={"G1-N": prism_pairs})
        boots[variable] = bs
        e2 = {"pooled_median_he0": med([r["he0"] for r in inc]),
              "pooled_median_he0_ci": M.pct_ci(bs["D0"]["he0"]) if "D0" in bs else [None, None],
              "n_pairs": len(d0), "n_pairs_included": len(inc),
              "excluded_pairs": [f"{r['market']}:{r['point']} (paying units {r['n_pay']})" for r in d0 if not r["included"]],
              "by_market": {m: {"median_he0": med([r["he0"] for r in inc if r["market"] == m]),
                                "n": sum(1 for r in inc if r["market"] == m)} for m in cfg.markets},
              "units": "calendar days" if unit == "day" else "Mon-Sun weeks"}
        out["eval02"][variable] = e2
        # ---- bake-off
        bo = {}
        for d in DESIGNS:
            p = pooled(rows, variable, d, cfg.markets, cfg.lam, cfg.premium if variable == "temperature" else None)
            if p.get("n_pairs", 0) == 0:
                bo[d] = {"n_pairs": 0, "verdict": "not available", "role": ROLE[d]}
                continue
            b_ = bs.get(d)
            p["dhe_ci"] = M.pct_ci(b_["dhe"]) if b_ else [None, None]
            p["he_ci"] = M.pct_ci(b_["he"]) if b_ else [None, None]
            settle, why = P4[d]
            p["settleable"], p["settleable_note"] = settle, why
            P1 = bool(p["pooled_median_dhe"] >= P1_DHE and p["dhe_ci"][0] is not None and p["dhe_ci"][0] > 0)
            P2 = bool(np.isfinite(p["share_pairs_dhe_pos"]) and p["share_pairs_dhe_pos"] >= P2_SHARE
                      and p["markets_dhe_pos"] >= P2_MARKETS[variable])
            P3 = bool(np.isfinite(p["pooled_median_eta"]) and p["pooled_median_eta"] >= P3_ETA)
            p["P1"], p["P2"], p["P3"], p["P4"] = P1, P2, P3, bool(settle)
            p["insurance_grade"] = bool(p["pooled_median_he"] >= HE_GRADE)
            killed = bool(p["pooled_median_dhe"] <= 0) if d != "D0" else False
            rule = "KILLED" if killed else ("SURVIVES" if (P1 and P2 and P3 and settle) else "FAILS")
            p["rule_outcome"] = rule if d != "D0" else "baseline"
            p["role"] = ROLE[d]
            p["verdict"] = {"baseline": "baseline", "continuity": "continuity", "exploratory": "exploratory"}.get(ROLE[d], rule)
            if d == "D0":  # no residual: nothing transferred, so these are exact zeros, not missing values
                p.update(share_pairs_dhe_pos=0.0, sd_r_median=0.0, L_median=0.0, mean_r_median=0.0,
                         L_by_lambda={str(l_): 0.0 for l_ in LAMBDAS}, pooled_median_eta=0.0, pooled_median_beta=0.0,
                         eta_note="D0 hands no variance to the pool (r = 0); eta is set to 0 by convention (dHE = 0 for any eta)")
            p["distinct_contracts_by_market"] = {m: distinct_contracts(rows, d, m, cells, res["arrs"]) for m in cfg.markets}
            p["distinct_contracts_mean"] = float(np.mean(list(p["distinct_contracts_by_market"].values())))
            bo[d] = p
        red = pooled(rows, variable, "G1-N", cfg.markets, cfg.lam, restrict=prism_pairs)
        if red.get("n_pairs"):
            red["dhe_ci"] = M.pct_ci(bs_red["G1-N"]["dhe"]) if "G1-N" in bs_red else [None, None]
            bo["G1-N"]["on_prism_pairs"] = {k: red[k] for k in ("n_pairs", "pooled_median_he", "pooled_median_dhe", "dhe_ci",
                                                                "share_pairs_dhe_pos", "pooled_median_eta")}
        for d in ("G1-P", "G1-P*"):
            if bo[d].get("n_pairs") and bo[d]["n_pairs"] < len(plist):
                bo[d]["verdict_note"] = (f"computed on {bo[d]['n_pairs']} of {len(plist)} pairs: no PRISM cell was pulled for the "
                                         "others (deviation 1); see bakeoff_matched_prism_pairs for all designs on the same pairs")
        out["bakeoff"][variable] = bo
        # like-for-like view on the pairs that have a PRISM cell (deviation 1): every design, same pairs
        bs_m = bootstrap(res, DESIGNS, te, cfg, block, restrict={d: prism_pairs for d in DESIGNS})
        mt = {}
        for d in DESIGNS:
            q = pooled(rows, variable, d, cfg.markets, cfg.lam, restrict=prism_pairs)
            if not q.get("n_pairs"):
                continue
            mt[d] = {k: q[k] for k in ("n_pairs", "n_pairs_nonzero", "pooled_median_he", "pooled_median_he0_same_pairs",
                                        "pooled_median_dhe", "share_pairs_dhe_pos", "markets_dhe_pos", "pooled_median_eta",
                                        "sd_r_median", "L_median")}
            if d in bs_m:
                mt[d]["dhe_ci"] = M.pct_ci(bs_m[d]["dhe"])
                mt[d]["he_ci"] = M.pct_ci(bs_m[d]["he"])
        if "G1-P" in bs_m:
            mt["_paired_he_diff_vs_G1-P"] = {d: {"he_diff": mt["G1-P"]["pooled_median_he"] - mt[d]["pooled_median_he"],
                                                 "ci": M.pct_ci(bs_m["G1-P"]["he"] - bs_m[d]["he"])}
                                             for d in DESIGNS if d in bs_m and d != "G1-P"}
        out.setdefault("bakeoff_matched_prism_pairs", {})[variable] = mt
        out["pairs"][variable] = [{k: r[k] for k in ("market", "point", "design", "dist_km", "included", "available", "zero",
                                                     "zero_reason", "n", "n_pay", "he", "he0", "dhe", "beta", "eta", "sd_r", "mean_r")}
                                  for r in rows]
        # ---- concentration per market (test units, included pairs)
        conc = {}
        for m in cfg.markets:
            conc[m] = {}
            for d in DESIGNS[1:]:
                rs = []
                for r in rows:
                    if r["market"] == m and r["design"] == d and r["available"]:
                        rr = res["arrs"][(m, r["point"], d)][2]
                        rs.append(np.where(te, rr, np.nan)[te])
                c = M.concentration(rs)
                c["production_kappa"] = 1.0 if d.startswith("R-") else c["kappa"]
                conc[m][d] = c
        out["concentration"][variable] = conc
        # ---- fits (no look-ahead record)
        fits = {}
        for (k0, m, b), meta in ((k, v) for k, v in res["arrs"].items() if k[0] == "meta"):
            if "R-A-PC" in meta:
                fits[f"R-A-PC:{m}:{b}"] = meta["R-A-PC"]
        for m, meta in res["mk"].items():
            if "R-N-PC" in meta:
                fits[f"R-N-PC:{m}"] = meta["R-N-PC"]
        out["fits"][variable] = fits
        # ---- design metadata (partners, counties, IDW weights) for the spec
        out.setdefault("design_meta", {})[variable] = {
            f"{m}:{b}": {k: v for k, v in meta.items() if k in ("P-A", "P-A-IDW", "C1-N", "R-A")}
            for (k0, m, b), meta in ((k, v) for k, v in res["arrs"].items() if k[0] == "meta")}
        out["design_meta"][variable]["_market"] = res["mk"]
        # ---- verdicts
        surv = [d for d in DESIGNS if bo[d].get("verdict") == "SURVIVES"]
        elig = [d for d in DESIGNS if ROLE[d] == "eligible" and bo[d].get("n_pairs")]
        winner = None
        if surv:
            best = max(bo[d]["pooled_median_he"] for d in surv)
            tied = [d for d in surv if best - bo[d]["pooled_median_he"] <= TIE_HE]
            tied.sort(key=lambda d: (bo[d]["distinct_contracts_mean"], bo[d]["L_median"], -bo[d]["pooled_median_he"], d))
            winner = tied[0]
        out["verdicts"]["winner"][variable] = winner
        ranked = sorted(elig, key=lambda d: (-bo[d]["pooled_median_he"], d))
        top = winner or (ranked[0] if ranked else None)
        runner = next((d for d in ranked if d != top), None)
        out["verdicts"]["runner_up"][variable] = runner
        if top and runner and top in bs and runner in bs:
            diff = bs[top]["he"] - bs[runner]["he"]
            out["verdicts"]["winner_vs_runner_up"][variable] = {
                "designs": [top, runner], "he_diff": bo[top]["pooled_median_he"] - bo[runner]["pooled_median_he"],
                "ci": M.pct_ci(diff)}
        others = [d for d in sorted(surv, key=lambda d: (-bo[d]["pooled_median_he"], d)) if d != winner]
        if winner and others and winner in bs and others[0] in bs:
            nx = others[0]
            out["verdicts"].setdefault("winner_vs_next_survivor", {})[variable] = {
                "designs": [winner, nx], "he_diff": bo[winner]["pooled_median_he"] - bo[nx]["pooled_median_he"],
                "ci": M.pct_ci(bs[winner]["he"] - bs[nx]["he"])}
        out["verdicts"].setdefault("survivors", {})[variable] = surv
        if not surv and elig:
            bd = max(elig, key=lambda d: (bo[d]["pooled_median_dhe"], d))
            out["verdicts"]["best_if_none"][variable] = {"design": bd, **{k: bo[bd].get(k) for k in (
                "pooled_median_he", "pooled_median_dhe", "dhe_ci", "share_pairs_dhe_pos", "markets_dhe_pos",
                "pooled_median_eta", "sd_r_median", "L_median", "P1", "P2", "P3", "P4")}}
        out["verdicts"]["rules"][variable] = {d: {k: bo[d].get(k) for k in ("P1", "P2", "P3", "P4", "rule_outcome", "verdict")}
                                              for d in DESIGNS}
        # PC1 vs equal (Q2)
        for pc, eq in (("R-A-PC", "R-A"), ("R-N-PC", "R-N")):
            if pc in bs and eq in bs:
                diff = bs[pc]["he"] - bs[eq]["he"]
                hd = bo[pc]["pooled_median_he"] - bo[eq]["pooled_median_he"]
                ci = M.pct_ci(diff)
                out["verdicts"].setdefault("pc1_vs_equal_all", {}).setdefault(variable, {})[f"{pc}_vs_{eq}"] = {
                    "he_diff": hd, "ci": ci, "adopted": bool(hd >= PC1_MARGIN and ci[0] > 0)}
        # ---- outer ring (reported, never gating)
        olist = pairs_of(cfg, variable, outer=True)
        if olist:
            ores = run_variable(cfg, data, U, variable, Opts(), te, olist)
            out["outer"][variable] = {d: pooled(ores["rows"], variable, d, cfg.markets) for d in DESIGNS}
            for r in ores["rows"]:
                if r["design"] == "D0":
                    out["eval02"]["points_outer"].append({"market": r["market"], "point": r["point"], "variable": variable,
                                                          "dist_km": r["dist_km"], "he0": r["he0"], "included": r["included"]})
            out["outer"][variable]["_rows"] = [{k: r[k] for k in ("market", "point", "design", "dist_km", "he0", "he", "dhe", "eta", "sd_r")}
                                               for r in ores["rows"] if r["available"]]
        if cfg.extras:
            out["sensitivities"][variable] = sensitivities(cfg, data, variable, unit, res, te, tr, plist)
    # the contract's single pc1_vs_equal = the ASOS network (R-A-PC vs R-A), temperature
    pa = out["verdicts"].get("pc1_vs_equal_all", {}).get("temperature", {}).get("R-A-PC_vs_R-A")
    out["verdicts"]["pc1_vs_equal"] = dict(pa or {"he_diff": None, "ci": [None, None], "adopted": False},
                                           pair=["R-A-PC", "R-A"], variable="temperature")
    if cfg.extras:
        out["rain_secondary"] = rain_secondary(cfg, data)
        out["eval02"]["extras"] = eval02_extras(cfg, data, ctx)
        out["cross_market"] = cross_market(cfg, data, out)
    return out


# ------------------------------------------------------------------------------------------ sensitivities
def _summ(rows, variable, markets, designs=None):
    o = {}
    for d in designs or DESIGNS:
        p = pooled(rows, variable, d, markets)
        if p.get("n_pairs"):
            o[d] = {k: p[k] for k in ("n_pairs", "pooled_median_he", "pooled_median_dhe", "share_pairs_dhe_pos",
                                      "markets_dhe_pos", "pooled_median_eta")}
    return o


def radius_network(cfg: Config, data, variable: str, market: str, km: float) -> list[str]:
    X = data.T if variable == "temperature" else data.P
    out = []
    for c in sorted(cfg.coords):
        if c == market or c in cfg.awos or c not in X.columns:
            continue
        if haversine(cfg.coords[c], cfg.coords[market]) > km:
            continue
        ok = all(X[c].loc[a:b].notna().mean() >= 0.9 for a, b in (cfg.train, cfg.test))
        if ok:
            out.append(c)
    return out


def sensitivities(cfg, data, variable, unit, res, te, tr, plist) -> dict:
    s = {}
    U = Units(data, variable, unit)
    idx = U.index
    runs = {"unrounded": (Opts(rounded=False), te)}
    if variable == "temperature":
        runs["linear_uncapped"] = (Opts(linear=True), te)
        runs["fixed_monthly_strike"] = (Opts(strike="fixed_monthly"), te)
    runs["may_sep"] = (Opts(), te & np.isin(idx.month, [5, 6, 7, 8, 9]))
    # post-hoc, descriptive (deviation logged): the period in which IEM equals the CLI
    start = idx - pd.Timedelta(days=6) if unit == "week" else idx
    runs["posthoc_iem_clean_era_2025_10_on"] = (Opts(), te & (start >= pd.Timestamp("2025-10-01")))
    runs["metro_mean_excl_S"] = (Opts(metro_incl_S=False), te)
    for km in (30, 70):
        runs[f"network_{km}km"] = (Opts(net_override={m: radius_network(cfg, data, variable, m, km) for m in cfg.markets}), te)
    for km in (15, 40):
        runs[f"grid_disc_{km}km"] = (Opts(disc_km=float(km)), te)
    if data.prism_rel is not None:
        rel = data.prism_rel.reindex(pd.date_range(idx.min() - pd.Timedelta(days=6), idx.max()))
        if unit == "day":
            m8 = (rel.reindex(idx) == 8).to_numpy()
        else:
            m8 = np.array([(rel.loc[w - pd.Timedelta(days=6):w] == 8).all() for w in idx])
        runs["prism_grid_count_8"] = (Opts(), te & m8)
    for name, (op, mask) in runs.items():
        r_ = run_variable(cfg, data, U, variable, op, mask, plist)
        s[name] = _summ(r_["rows"], variable, cfg.markets)
        s[name]["_units"] = int(mask.sum())
        if name.startswith("network_"):
            s[name]["_networks"] = op.net_override
    # fitted beta on train, applied to test (upper bound of a sized overlay)
    fb, fit_last = [], ""
    for (m, b, d), val in res["arrs"].items():
        if m == "meta" or d == "D0":
            continue
        E, HS, r = val
        fb_fit = fit_beta_train(E - HS, r, idx, tr)
        beta = fb_fit["beta"]
        if not np.isfinite(beta):
            continue
        fit_last = max(fit_last, fb_fit["fit_last"] or "")
        st = M.point_stats(E, HS, beta * r, te)
        inc = next((x["available"] for x in res["rows"] if x["market"] == m and x["point"] == b and x["design"] == d), False)
        if inc:
            fb.append({"design": d, "he": st["he"], "dhe": st["dhe"], "beta_train": beta})
    s["fitted_beta_train"] = {d: {"n_pairs": len([x for x in fb if x["design"] == d]),
                                  "pooled_median_he": med([x["he"] for x in fb if x["design"] == d]),
                                  "pooled_median_dhe": med([x["dhe"] for x in fb if x["design"] == d]),
                                  "median_beta_train": med([x["beta_train"] for x in fb if x["design"] == d])}
                              for d in DESIGNS[1:]}
    s["fitted_beta_train"]["_fit_window"] = [cfg.train[0], cfg.train[1]]
    s["fitted_beta_train"]["_fit_last_used"] = fit_last or None
    if variable == "temperature" and data.ladder:
        mask = te & np.isin(idx, pd.DatetimeIndex(sorted(set().union(*[set(v.index) for v in data.ladder.values()]))))
        r_ = run_variable(cfg, data, U, variable, Opts(strike="kalshi"), mask, plist, ladder_leg=True)
        s["kalshi_ladder_subsample"] = _summ(r_["rows"], variable, cfg.markets)
        s["kalshi_ladder_subsample"]["_n_by_market"] = {
            m: int(max([x["n"] for x in r_["rows"] if x["market"] == m and x["design"] == "D0"] or [0])) for m in cfg.markets}
        s["kalshi_ladder_subsample"]["_eval02_he0_by_market"] = {
            m: med([x["he0"] for x in r_["rows"] if x["market"] == m and x["design"] == "D0" and x["included"]]) for m in cfg.markets}
    s["cocorahs_weekly_truth"] = {"_status": "not run: Phase 1 did not pull CoCoRaHS (PREREG: only if pulled)"}
    return s


def rain_secondary(cfg, data) -> dict:
    out = {}
    # daily wet-day false negatives: point wet, hedge (station leg + residual) pays < 0.5
    U = Units(data, "rain", "wetday")
    _, te = unit_windows(U.index, "wetday", cfg)
    res = run_variable(cfg, data, U, "rain", Opts(), te, pairs_of(cfg, "rain"), keep_arrays=True)
    fn = {}
    for (m, b, d), val in res["arrs"].items():
        if m == "meta":
            continue
        E, HS, r = val
        ok = te & ~(np.isnan(E) | np.isnan(HS) | np.isnan(r)) & (E == 1)
        if ok.sum() < 20:
            continue
        fn[(m, b, d)] = float(np.mean((HS + r)[ok] < 0.5))
    o = {}
    for d in DESIGNS:
        vals = [(k, v) for k, v in fn.items() if k[2] == d]
        rel = [v / fn[(k[0], k[1], "D0")] - 1 for k, v in vals if fn.get((k[0], k[1], "D0"), 0) > 0]
        o[d] = {"n_pairs": len(vals), "fn_rate_median": med([v for _, v in vals]), "fn_rel_change_vs_D0_median": med(rel)}
    out["wetday_false_negative"] = o
    # monthly totals, descriptive
    U = Units(data, "rain", "month")
    _, te = unit_windows(U.index, "month", cfg)
    res = run_variable(cfg, data, U, "rain", Opts(), te, pairs_of(cfg, "rain"))
    out["monthly_totals"] = _summ(res["rows"], "rain", cfg.markets)
    out["monthly_totals"]["_units"] = int(te.sum())
    return out


def eval02_extras(cfg, data, ctx) -> dict:
    ex = {"cell_he": {}, "nearest_cell": {}, "prism_contamination": ctx.get("prism_contamination")}
    for variable, unit in VARS:
        U = Units(data, variable, unit)
        _, te = unit_windows(U.index, unit, cfg)
        ex["cell_he"][variable] = {}
        for m in cfg.markets:
            f = D.payout_fn(cfg, U, m, Opts(), data)
            HS = f(U.st[m].to_numpy(float)) if m in U.st.columns else None
            for src in ("prism", "nclimgrid"):
                d = U.disc.get((src, m))
                if d is None or HS is None:
                    continue
                hes, dists = [], []
                for j, cid in enumerate(d["X"].columns):
                    E = f(d["X"][cid].to_numpy(float))
                    st = M.point_stats(E, HS, np.zeros(len(E)), te)
                    if np.isfinite(st["he0"]):
                        hes.append(st["he0"])
                        dists.append(float(d["dist"][j]))
                if not hes:
                    continue
                hes, dists = np.array(hes), np.array(dists)
                ex["cell_he"][variable][f"{m}:{src}"] = {
                    "n_cells": int(len(hes)), "median": float(np.median(hes)), "p10": float(np.percentile(hes, 10)),
                    "p90": float(np.percentile(hes, 90)), "nearest_cell_he": float(hes[np.argmin(dists)]),
                    "nearest_cell_km": float(dists.min()),
                    "median_by_band": {band: med(hes[(dists > lo) & (dists <= hi)]) for band, (lo, hi) in
                                       {"0-10": (-1, 10), "10-20": (10, 20), "20-30": (20, 30), "30-40": (30, 40)}.items()}}
    # nearest-cell tmax RMSE and correlation vs the station value, both grids, both alignments
    lo, hi = cfg.train[0], cfg.test[1]
    for src, G in (("nclimgrid", data.NT), ("prism", data.PT)):
        rows = {}
        for c in sorted(set(G.columns) & set(data.T.columns)):
            st = data.T[c].loc[lo:hi]
            for al, g in (("aligned", G[c]), ("unaligned", G[c].shift(1))):
                j = pd.concat([st, g.loc[lo:hi]], axis=1).dropna()
                if len(j) < 100:
                    continue
                e = j.iloc[:, 1] - j.iloc[:, 0]
                rows.setdefault(c, {})[al] = {"rmse": float(np.sqrt((e ** 2).mean())), "bias": float(e.mean()),
                                              "corr": float(j.corr().iloc[0, 1]), "n": int(len(j))}
        ex["nearest_cell"][src] = rows
        for al in ("aligned", "unaligned"):
            v = [r[al]["rmse"] for r in rows.values() if al in r]
            ex["nearest_cell"][f"{src}_median_rmse_{al}"] = med(v)
    return ex


def cross_market(cfg, data, out) -> dict:
    """EWR and TTN hedged with the liquid NYC ladder plus a residual (03-RESEARCH Q5 cross-market point)."""
    U = Units(data, "temperature", "day")
    _, te = unit_windows(U.index, "day", cfg)
    res = run_variable(cfg, data, U, "temperature", Opts(), te, [("NYC", "EWR"), ("NYC", "TTN")])
    o = {}
    for b in ("EWR", "TTN"):
        o[f"{b}_via_NYC"] = {r["design"]: {k: r[k] for k in ("he", "he0", "dhe", "eta", "sd_r", "mean_r", "n", "available")}
                             for r in res["rows"] if r["point"] == b}
        o[f"{b}_via_NYC"]["_meta"] = {k: v for k, v in res["arrs"][("meta", "NYC", b)].items() if k in ("P-A", "P-A-IDW", "R-A")}
    o["premium_per_unit_day"] = cfg.premium
    return o


# ------------------------------------------------------------------------------------------ outputs
def default_config() -> Config:
    from wi.eval03 import points as P

    return Config(markets=P.MARKETS, truth=P.TRUTH, network=P.NETWORK, outer=P.OUTER,
                  coords={c: (s.lat, s.lon) for c, s in P.STATIONS.items()},
                  county={c: s.county for c, s in P.STATIONS.items()},
                  awos={c for c, s in P.STATIONS.items() if s.awos}, premium=station_premiums())


def station_premiums() -> dict:
    """Station-leg 24 h ask premium per unit-day, rule A, 2025-26 (Phase 2 results.json, city_year, n-weighted)."""
    f = ROOT / "reports" / "eval-01" / "results.json"
    fallback = {"NYC": 1.73, "MDW": 3.14, "MIA": 4.79}
    if not f.exists():
        return fallback
    cy = json.loads(f.read_text())["temperature"]["city_year"]
    m = {"NY": "NYC", "CHI": "MDW", "MIA": "MIA", "EWR": "EWR", "TTN": "TTN"}
    acc = {}
    for x in cy:
        if x.get("rule") == "A" and x.get("h") == 24 and int(x.get("year")) in (2025, 2026) and x["city"] in m:
            n, p = x["n"]["est"], x["premium"]["est"]
            a = acc.setdefault(m[x["city"]], [0.0, 0.0])
            a[0] += n * p
            a[1] += n
    return {k: v[0] / v[1] for k, v in sorted(acc.items())} or fallback


def prism_contamination(cfg: Config) -> dict:
    from wi.eval03.sources import CACHE

    out = {"day": "2026-07-15 (PRISM label; the only .stn.csv kept by Phase 1)", "points": {}}
    lists = {}
    for var in ("tmax", "ppt"):
        f = CACHE / "prism_stn" / f"prism_{var}_20260715.stn.csv"
        if f.exists():
            lists[var] = pd.read_csv(f, skiprows=1, dtype=str)
    codes = sorted({b for v in cfg.truth.values() for lst in v.values() for b in lst} | set(cfg.markets))
    for c in codes:
        la, lo = cfg.coords[c]
        row = {}
        for var, d in lists.items():
            lat = pd.to_numeric(d["Latitude"], errors="coerce").to_numpy()
            lon = pd.to_numeric(d["Longitude"], errors="coerce").to_numpy()
            dist = np.array([haversine((la, lo), (a, b)) if np.isfinite(a) and np.isfinite(b) else 1e9 for a, b in zip(lat, lon)])
            idc = d["Station"].astype(str).str.upper()
            hit = (dist <= 1.5) | idc.isin([c, "K" + c]).to_numpy()
            row[var] = {"present": bool(hit.any()),
                        "entries": sorted(f"{d['Station'].iloc[i]} ({d['Network'].iloc[i]}, {dist[i]:.1f} km)" for i in np.where(hit)[0])[:6],
                        "inputs_within_10km": int((dist <= 10).sum())}
        out["points"][c] = row
    return out


def fin(v) -> bool:
    return v is not None and isinstance(v, (int, float)) and math.isfinite(v)


def write_tables(res: dict, dq: pd.DataFrame, path: Path) -> None:
    L = ["# EVAL-02 / EVAL-03 tables", "", "Generated by `uv run python scripts/eval03.py --all` from results.json. "
         "HE = 1 − Var(E − H_S − r)/Var(E) on the test window (2025-01-01..2026-08-31); ΔHE = HE − HE(D0) on the same units. "
         "CIs: joint circular block bootstrap (14-day blocks, 2-week blocks for weekly rain), 2,000 draws, seed 20260930.", ""]
    L += ["## 1. Data-quality check (run before any HE)", "",
          "IEM daily summary vs the reference (NWS CLI at CLI stations; GHCN-D at non-CLI stations with a USW record), "
          "2024-01-01..2026-08-31. Rule: switch to the reference if they differ on > 2 % of days (tmax: integer °F; "
          "precip: 0.01 in). Coverage = share of days with a value in the chosen source.", "",
          "| station | var | reference | days compared | mismatch | before 2025-10 | from 2025-10 | mean IEM − ref (before 2025-10) | source used | coverage train | coverage test |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in dq.iterrows():
        fm = lambda v, p=True: ("n/a" if not np.isfinite(v) else (f"{100 * v:.1f} %" if p else f"{v:+.2f}"))  # noqa: E731
        L.append(f"| {r.code} | {r['var']} | {r.ref} | {'' if not np.isfinite(r.n_compared) else int(r.n_compared)} | "
                 f"{fm(r.mismatch_share)} | {fm(r.mismatch_pre_2025_10)} | {fm(r.mismatch_post_2025_10)} | "
                 f"{fm(r.mean_iem_minus_ref_pre, False)} | {r.source} | {100 * r.cov_train:.1f} % | {100 * r.cov_test:.1f} % |")
    L.append("")
    g = lambda v, nd=3: "n/a" if v is None or (isinstance(v, float) and not fin(v)) else (f"{v:.{nd}f}" if isinstance(v, (float, int)) else str(v))  # noqa: E731
    ci = lambda c, nd=3: "n/a" if not c or c[0] is None else f"[{c[0]:.{nd}f}, {c[1]:.{nd}f}]"  # noqa: E731
    L += ["## 2. EVAL-02: HE of the station leg alone (D0) at held-out truth points", ""]
    for v in ("temperature", "rain"):
        e = res["eval02"][v]
        L.append(f"**{v}** ({e['units']}): pooled median HE(D0) {g(e['pooled_median_he0'])} {ci(e['pooled_median_he0_ci'])}, "
                 f"{e['n_pairs_included']} of {e['n_pairs']} pairs included. Excluded: {', '.join(e['excluded_pairs']) or 'none'}.")
        L.append("")
        L.append("| market | median HE(D0) | pairs |")
        L.append("|---|---|---|")
        for m, x in e["by_market"].items():
            L.append(f"| {m} | {g(x['median_he0'])} | {x['n']} |")
        L.append("")
    L += ["| market | point | variable | km | HE(D0) | units | paying units | included |", "|---|---|---|---|---|---|---|---|"]
    for p in sorted(res["eval02"]["points"] + [dict(x, outer=True) for x in res["eval02"]["points_outer"]],
                    key=lambda x: (x["variable"], x["market"], x["dist_km"])):
        L.append(f"| {p['market']} | {p['point']}{' (outer)' if p.get('outer') else ''} | {p['variable']} | {p['dist_km']:.1f} | "
                 f"{g(p['he0'])} | {p.get('n', '')} | {p.get('n_pay', '')} | {'yes' if p['included'] else 'no'} |")
    L.append("")
    for v in ("temperature", "rain"):
        L += [f"## 3. Bake-off, {v}", "",
              "| design | role | pairs (non-zero) | pooled median HE | ΔHE | ΔHE CI | pairs ΔHE>0 | markets ΔHE>0 | η | β | sd(r) | mean(r) | L (λ=0.25) | L % station premium | P1 | P2 | P3 | P4 | verdict |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for d in DESIGNS:
            b = res["bakeoff"][v][d]
            if not b.get("n_pairs"):
                L.append(f"| {d} | {ROLE[d]} | 0 | | | | | | | | | | | | | | | | not available |")
                continue
            sh = b["share_pairs_dhe_pos"]
            L.append(f"| {d} | {ROLE[d]} | {b['n_pairs']} ({b['n_pairs_nonzero']}) | {g(b['pooled_median_he'])} | {g(b['pooled_median_dhe'])} | "
                     f"{ci(b.get('dhe_ci'))} | {'n/a' if not fin(sh) else f'{100 * sh:.0f} %'} | {b['markets_dhe_pos']} | "
                     f"{g(b['pooled_median_eta'], 2)} | {g(b['pooled_median_beta'], 2)} | {g(b['sd_r_median'], 2)} | {g(b['mean_r_median'], 2)} | "
                     f"{g(b['L_median'], 2)} | {g(100 * b['L_pct_station_premium_median'], 1) + ' %' if b.get('L_pct_station_premium_median') is not None and fin(b['L_pct_station_premium_median']) else 'n/a'} | "
                     f"{'Y' if b['P1'] else 'n'} | {'Y' if b['P2'] else 'n'} | {'Y' if b['P3'] else 'n'} | {'Y' if b['P4'] else 'n'} | {b['verdict']} |")
        if "on_prism_pairs" in res["bakeoff"][v]["G1-N"]:
            x = res["bakeoff"][v]["G1-N"]["on_prism_pairs"]
            L.append("")
            L.append(f"G1-N on the {x['n_pairs']} pairs that have a PRISM cell: HE {g(x['pooled_median_he'])}, ΔHE {g(x['pooled_median_dhe'])} "
                     f"{ci(x['dhe_ci'])}, η {g(x['pooled_median_eta'], 2)}.")
        L += ["", f"Market medians of ΔHE (non-zero pairs), {v}:", "", "| design | " + " | ".join(res["eval02"][v]["by_market"]) + " |",
              "|---|" + "---|" * len(res["eval02"][v]["by_market"])]
        for d in DESIGNS[1:]:
            b = res["bakeoff"][v][d]
            if b.get("n_pairs"):
                L.append(f"| {d} | " + " | ".join(g(b["by_market"][m]["median_dhe"]) for m in b["by_market"]) + " |")
        L += ["", f"Distinct residual contracts per market and concentration κ (test window), {v}:", "",
              "| design | " + " | ".join(f"{m} contracts / κ" for m in res["eval02"][v]["by_market"]) + " |",
              "|---|" + "---|" * len(res["eval02"][v]["by_market"])]
        for d in DESIGNS[1:]:
            b = res["bakeoff"][v][d]
            if b.get("n_pairs"):
                L.append(f"| {d} | " + " | ".join(f"{b['distinct_contracts_by_market'][m]} / {g(res['concentration'][v][m][d]['kappa'], 2)}"
                                                  for m in b["by_market"]) + " |")
        L.append("")
        L += [f"Per pair ΔHE, {v} (blank = not available; 0 = residual identically zero by construction):", "",
              "| market | point | km | HE(D0) | " + " | ".join(DESIGNS[1:]) + " |", "|---|---|---|---|" + "---|" * (len(DESIGNS) - 1)]
        pr = {(r["market"], r["point"], r["design"]): r for r in res["pairs"][v]}
        for m, b in sorted({(r["market"], r["point"]) for r in res["pairs"][v]}, key=lambda x: (x[0], pr[(x[0], x[1], "D0")]["dist_km"])):
            r0 = pr[(m, b, "D0")]
            cells = []
            for d in DESIGNS[1:]:
                r = pr[(m, b, d)]
                cells.append("" if not r["available"] else ("0" if r["zero"] else f"{r['dhe']:+.3f}"))
            L.append(f"| {m} | {b} | {r0['dist_km']:.1f} | {g(r0['he0'])} | " + " | ".join(cells) + " |")
        L.append("")
    L += ["## 4. Verdicts", ""]
    vd = res["verdicts"]
    for v in ("temperature", "rain"):
        L.append(f"- {v}: winner **{vd['winner'][v] or 'none'}**; runner-up {vd['runner_up'].get(v)}; "
                 f"top vs runner-up HE diff {g((vd['winner_vs_runner_up'].get(v) or {}).get('he_diff'))} "
                 f"{ci((vd['winner_vs_runner_up'].get(v) or {}).get('ci'))}.")
        if vd["best_if_none"].get(v):
            x = vd["best_if_none"][v]
            L.append(f"  - nothing survives; best eligible design by ΔHE: {x['design']} (ΔHE {g(x['pooled_median_dhe'])} {ci(x['dhe_ci'])}, "
                     f"HE {g(x['pooled_median_he'])}, η {g(x['pooled_median_eta'], 2)}).")
    for v, dd in vd.get("pc1_vs_equal_all", {}).items():
        for k, x in dd.items():
            L.append(f"- PC1 vs equal ({v}, {k}): HE diff {g(x['he_diff'])} {ci(x['ci'])}, adopted {x['adopted']}.")
    L.append("")
    L += ["## 5. Sensitivities (reported, never gating): pooled median ΔHE", ""]
    for v in ("temperature", "rain"):
        s = res["sensitivities"].get(v, {})
        names = [k for k in s if not k.startswith("cocorahs")]
        L += [f"**{v}**", "", "| design | main | " + " | ".join(names) + " |", "|---|---|" + "---|" * len(names)]
        for d in DESIGNS[1:]:
            b = res["bakeoff"][v][d]
            cells = [g(s[n].get(d, {}).get("pooled_median_dhe")) for n in names]
            L.append(f"| {d} | {g(b.get('pooled_median_dhe'))} | " + " | ".join(cells) + " |")
        L.append("")
    L += ["## 6. EVAL-02 extras (descriptive)", "", "Station-leg HE at every land cell within 40 km (exposure = cell value, hedge = station leg):", "",
          "| variable | market:grid | cells | median | p10 | p90 | nearest cell (km) | 0-10 km | 10-20 | 20-30 | 30-40 |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for v, dd in res["eval02"]["extras"]["cell_he"].items():
        for k, x in dd.items():
            bands = x["median_by_band"]
            L.append(f"| {v} | {k} | {x['n_cells']} | {g(x['median'])} | {g(x['p10'])} | {g(x['p90'])} | {g(x['nearest_cell_he'])} ({x['nearest_cell_km']:.1f}) | "
                     + " | ".join(g(bands[b_]) for b_ in ("0-10", "10-20", "20-30", "30-40")) + " |")
    L += ["", "Nearest-cell tmax vs the station value (°F), 2024-01-01..2026-08-31:", "",
          "| station | nClimGrid RMSE aligned / unaligned | nClimGrid corr aligned | PRISM RMSE aligned / unaligned | PRISM corr aligned |", "|---|---|---|---|---|"]
    nc_ = res["eval02"]["extras"]["nearest_cell"]
    for c in sorted(set(nc_["nclimgrid"]) | set(nc_["prism"])):
        a, p_ = nc_["nclimgrid"].get(c, {}), nc_["prism"].get(c, {})
        fmtr = lambda x: f"{x['aligned']['rmse']:.2f} / {x['unaligned']['rmse']:.2f}" if "aligned" in x and "unaligned" in x else "n/a"  # noqa: E731
        L.append(f"| {c} | {fmtr(a)} | {g(a.get('aligned', {}).get('corr'))} | {fmtr(p_)} | {g(p_.get('aligned', {}).get('corr'))} |")
    L.append(f"| median | {g(nc_['nclimgrid_median_rmse_aligned'], 2)} / {g(nc_['nclimgrid_median_rmse_unaligned'], 2)} | | "
             f"{g(nc_['prism_median_rmse_aligned'], 2)} / {g(nc_['prism_median_rmse_unaligned'], 2)} | |")
    pc = res["eval02"]["extras"].get("prism_contamination") or {}
    if pc:
        L += ["", f"PRISM input-station contamination, {pc['day']}:", "", "| station | in tmax inputs | in ppt inputs | tmax inputs within 10 km | entries matched |", "|---|---|---|---|---|"]
        for c, x in pc["points"].items():
            t, p_ = x.get("tmax", {}), x.get("ppt", {})
            L.append(f"| {c} | {'yes' if t.get('present') else 'no'} | {'yes' if p_.get('present') else 'no'} | {t.get('inputs_within_10km', '')} | "
                     f"{'; '.join(t.get('entries', [])[:3])} |")
    L += ["", "## 7. Rain secondary (not gating)", "", "| design | wet-day FN rate (median) | relative change vs D0 | monthly-total HE | monthly ΔHE |", "|---|---|---|---|---|"]
    rs = res["rain_secondary"]
    for d in DESIGNS:
        w = rs["wetday_false_negative"].get(d, {})
        mo = rs["monthly_totals"].get(d, {})
        L.append(f"| {d} | {g(w.get('fn_rate_median'))} | {g(w.get('fn_rel_change_vs_D0_median'))} | {g(mo.get('pooled_median_he'))} | {g(mo.get('pooled_median_dhe'))} |")
    L += ["", "## 8. Cross-market: EWR and TTN hedged with the NYC ladder plus a residual", "", "| point | design | HE | HE(D0) | ΔHE | η | sd(r) | mean(r) |", "|---|---|---|---|---|---|---|---|"]
    for k in ("EWR_via_NYC", "TTN_via_NYC"):
        for d, x in res["cross_market"][k].items():
            if d.startswith("_") or not x.get("available", True):
                continue
            L.append(f"| {k} | {d} | {g(x['he'])} | {g(x['he0'])} | {g(x['dhe'])} | {g(x['eta'], 2)} | {g(x['sd_r'], 2)} | {g(x['mean_r'], 2)} |")
    L += ["", "Station-leg 24 h ask premium per unit-day (Phase 2, rule A, 2025-26): " +
          ", ".join(f"{k} {v:.2f}" for k, v in res["cross_market"]["premium_per_unit_day"].items()), ""]
    L += ["## 9. Outer ring (50-110 km, reported only)", "", "| design | pairs | pooled median HE | ΔHE | η |", "|---|---|---|---|---|"]
    for d in DESIGNS:
        x = res["outer"].get("temperature", {}).get(d, {})
        if x.get("n_pairs"):
            L.append(f"| {d} (temperature) | {x['n_pairs']} | {g(x['pooled_median_he'])} | {g(x['pooled_median_dhe'])} | {g(x['pooled_median_eta'], 2)} |")
    for d in DESIGNS:
        x = res["outer"].get("rain", {}).get(d, {})
        if x.get("n_pairs"):
            L.append(f"| {d} (rain) | {x['n_pairs']} | {g(x['pooled_median_he'])} | {g(x['pooled_median_dhe'])} | {g(x['pooled_median_eta'], 2)} |")
    L.append("")
    L += ["## 10. Frozen PC1 fits (train window only)", "", "| fit | inputs with w>0 | max w | PC1 share | fit first | fit last | days/weeks |", "|---|---|---|---|---|---|---|"]
    for v, fits in res["fits"].items():
        for k, x in sorted(fits.items()):
            w = x.get("w")
            npos = sum(1 for val in w.values() if val > 0) if w else x.get("n_pos")
            mx = max(w.values()) if w else x.get("w_max")
            L.append(f"| {v} {k} | {npos} | {g(mx, 2)} | {g(x.get('pc1_share'), 2)} | {x.get('fit_first')} | {x.get('fit_last')} | {x.get('n_fit')} |")
    path.write_text("\n".join(L) + "\n")


def write_figures(res: dict, figdir: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figdir.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 4))
    for v, mk, col in (("temperature", "o", "tab:red"), ("rain", "^", "tab:blue")):
        p = [x for x in res["eval02"]["points"] if x["variable"] == v and x["he0"] is not None and x["included"]]
        q = [x for x in res["eval02"]["points_outer"] if x["variable"] == v and x["he0"] is not None]
        ax.scatter([x["dist_km"] for x in p], [x["he0"] for x in p], marker=mk, color=col, label=f"{v} (≤ 50 km)")
        ax.scatter([x["dist_km"] for x in q], [x["he0"] for x in q], marker=mk, facecolors="none", edgecolors=col, label=f"{v} outer ring")
    ax.axhline(0.70, ls="--", color="grey", lw=1)
    ax.set_xlabel("distance from the settlement station, km")
    ax.set_ylabel("HE of the station leg alone (test window)")
    ax.set_title("EVAL-02: geography basis vs distance")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(figdir / "eval02_he0_vs_distance.png", dpi=130)
    plt.close(fig)
    for v in ("temperature", "rain"):
        fig, ax = plt.subplots(figsize=(9, 4))
        ds = [d for d in DESIGNS[1:] if res["bakeoff"][v][d].get("n_pairs")]
        for i, d in enumerate(ds):
            ys = [r["dhe"] for r in res["pairs"][v] if r["design"] == d and r["available"]]
            ax.scatter(np.full(len(ys), i) + np.linspace(-0.2, 0.2, len(ys)), ys, s=10, alpha=0.6)
            b = res["bakeoff"][v][d]
            ax.plot([i - 0.3, i + 0.3], [b["pooled_median_dhe"]] * 2, color="k", lw=2)
            if b.get("dhe_ci") and b["dhe_ci"][0] is not None:
                ax.plot([i, i], b["dhe_ci"], color="k", lw=1)
        ax.axhline(0.10, ls="--", color="green", lw=1, label="P1 bar +0.10")
        ax.axhline(0.0, color="grey", lw=0.8)
        ax.set_xticks(range(len(ds)), ds, rotation=45, fontsize=8)
        ax.set_ylabel("ΔHE vs station leg alone")
        ax.set_title(f"EVAL-03 {v}: ΔHE per (market, point); bar = pooled median, line = 95 % CI")
        ax.legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(figdir / f"bakeoff_dhe_{v}.png", dpi=130)
        plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4))
    for v, mk in (("temperature", "o"), ("rain", "^")):
        for d in DESIGNS[1:]:
            b = res["bakeoff"][v][d]
            if b.get("n_pairs") and b.get("pooled_median_eta") is not None and fin(b["pooled_median_eta"]):
                ax.scatter(b["sd_r_median"], b["pooled_median_eta"], marker=mk)
                ax.annotate(f"{d} ({v[0]})", (b["sd_r_median"], b["pooled_median_eta"]), fontsize=6)
    ax.axhline(0.5, ls="--", color="green", lw=1)
    ax.set_xlabel("median sd(r) per unit")
    ax.set_ylabel("pooled median η = 2β − 1")
    ax.set_title("Residual efficiency vs residual size")
    fig.tight_layout()
    fig.savefig(figdir / "eta_vs_sdr.png", dpi=130)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pull", action="store_true")
    ap.add_argument("--dq", action="store_true")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    from wi.eval03 import sources as S

    if a.pull:
        S.pull_iem()
        S.pull_cli()
        S.pull_county()
        S.pull_nclimgrid_points()
    if a.dq or a.all:
        dq, choice = S.data_quality()
    if a.dq:
        now = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        tmp = OUT / "dq.md"
        write_tables_dq_only(dq, tmp, now)
        print(dq.to_string())
    if a.all:
        prereg = (OUT / "PREREG.md").read_text()
        frozen = re.search(r"Frozen at: (\S+)\*\*", prereg).group(1)
        cfg = default_config()
        days = pd.date_range("2023-12-20", "2026-08-31")
        data, cells = S.build_data(days, choice)
        ctx = {"cells": cells, "prism_contamination": prism_contamination(cfg)}
        res = evaluate(cfg, data, ctx)
        res["data_quality"] = dq.to_dict(orient="records")
        res["station_sources"] = {f"{c}:{v}": s for (c, v), s in sorted(choice.items())}
        res["cells"] = cells
        dev = json.loads((OUT / "deviations.json").read_text()) if (OUT / "deviations.json").exists() else []
        res["deviations"] = dev
        res["meta"] = {"prereg_frozen_utc": frozen,
                       "written_utc": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                       "seed": cfg.seed, "draws": cfg.draws, "block_days": cfg.block_days, "block_weeks": cfg.block_weeks,
                       "train": list(cfg.train), "test": list(cfg.test), "command": "uv run python scripts/eval03.py --all"}
        order = ["meta", "eval02", "bakeoff", "bakeoff_matched_prism_pairs", "verdicts", "deviations", "concentration", "sensitivities", "rain_secondary",
                 "cross_market", "outer", "fits", "counts", "data_quality", "station_sources", "cells", "design_meta", "pairs"]
        res = {k: res[k] for k in order if k in res}
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "results.json").write_text(json.dumps(clean(res), indent=1, allow_nan=False) + "\n")
        write_tables(clean(res), dq, OUT / "tables.md")
        write_figures(clean(res), OUT / "figures")
        print("wrote", OUT / "results.json")


def write_tables_dq_only(dq: pd.DataFrame, path: Path, now: str) -> None:
    path.write_text(f"# Data-quality check (run {now}, before any HE)\n\n```\n{dq.to_string(index=False)}\n```\n")
