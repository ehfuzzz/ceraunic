"""EVAL-06 runner (plan 05): panels -> fits -> arms -> hedges -> HE -> tests -> artifacts.

uv run python scripts/eval05.py --all               everything available
uv run python scripts/eval05.py --groups G3 G4      subset
Flags: --no-lc --no-sens --no-placebo --boot N (default 2000, the pre-registered value)

Writes reports/eval-06/{results.json, tables.md, figures/*.png, priors.json} and
data/cache/sales_daily/panel_G*.parquet. PREREG.md must exist and predate this run.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wi.elasticity import design as D  # noqa: E402
from wi.elasticity import evaluate as E  # noqa: E402
from wi.elasticity.panel import GROUPS, build_panel, manifest_summary, write_panel_parquet  # noqa: E402
from wi.elasticity.shrink import dl, pm  # noqa: E402

REP = ROOT / "reports" / "eval-06"
FIG = REP / "figures"
PREREG = REP / "PREREG.md"
ARMS = ("A0", "A1", "A2", "A3", "A4")


def utcnow():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def prereg_ts() -> str:
    for line in PREREG.read_text().splitlines():
        if line.startswith("**Frozen:**"):
            return line.split("**Frozen:**")[1].split("(UTC)")[0].strip()
    raise SystemExit("PREREG.md has no frozen timestamp")


# ------------------------------------------------------------------ one split

def cost_stats(z: dict, legs: str) -> dict:
    """Realised cost over the hedge year: sums over units (buy-side days) and the median of unit ratios."""
    out = {}
    parts = [("heat", z["lad"])] + ([("rain", z["rain"])] if legs == "heat_rain" else [])
    prem_b = sum(np.where(p["buy"], p["prem"], 0.0) for _, p in parts)
    pay_b = sum(np.where(p["buy"], p["pay"], 0.0) for _, p in parts)
    prem_s = sum(np.where(p["sell"], p["prem"], 0.0) for _, p in parts)
    pay_s = sum(np.where(p["sell"], p["pay"], 0.0) for _, p in parts)
    fees = sum(p["fees"] for _, p in parts)
    tp, ty = float(prem_b.sum()), float(pay_b.sum())
    with np.errstate(divide="ignore", invalid="ignore"):
        unit_ratio = (prem_b.sum(0) - pay_b.sum(0)) / pay_b.sum(0)
    out["buy_premium_incl_fees"] = tp
    out["buy_payout"] = ty
    out["buy_cost_ratio"] = (tp - ty) / ty if ty > 0 else None
    out["buy_cost_ratio_unit_median"] = float(np.nanmedian(unit_ratio[np.isfinite(unit_ratio)])) if np.isfinite(unit_ratio).any() else None
    out["sell_premium_net"] = float(prem_s.sum())
    out["sell_payout"] = float(pay_s.sum())
    out["fees_total"] = float(fees.sum())
    out["buy_unit_days"] = int(sum(p["buy"] for _, p in parts).astype(bool).sum())
    out["sell_unit_days"] = int(sum(p["sell"] for _, p in parts).astype(bool).sum())
    out["unhedgeable_unit_days_heat"] = int(z["lad"]["unhedge"].sum())
    out["unhedgeable_unit_days_rain"] = int(z["rain"]["unhedge"].sum()) if legs == "heat_rain" else None
    out["mean_contracts_heat_per_unit_day"] = float(z["lad"]["contracts"].mean())
    return out


def run_split(p, origin: str, n_max: int, cfg: E.Cfg, arms=ARMS, weekly=True, ctx=None, real_ctx=None) -> tuple[dict, E.Ctx]:
    g = p.group
    ctx = ctx or E.build_ctx(p, origin, n_max, cfg)
    if real_ctx is not None:          # placebo: real U/F, placebo-fit betas and K
        ctx.F, ctx.U = real_ctx.F, real_ctx.U
    else:
        E.baseline(ctx)
    lg = E.legs_for(ctx)
    out = {"origin": origin, "n": n_max, "K": ctx.K, "cap": cfg.cap, "eligibility": ctx.elig_log,
           "k_profile_ssr": ctx.k_profile, "clim_years": ctx.clim["n_years"],
           "days_scored": int(lg.ok.sum()), "ladder_days_listed": int(lg.L.avail.sum()),
           "rain_days_listed": int(lg.R.avail.sum()),
           "payout_days_cli": int(((lg.X > 0) & lg.ok).sum()),
           "payout_days_kalshi": int((lg.L.avail & (lg.L.G * lg.L.WIN).sum(1).astype(bool)).sum()),
           "suspension_days": int(ctx.susp.sum()), "arms": {}}
    ab = E.arm_betas(ctx, n_max)
    det = ab["_detail"]
    out["prior"] = {leg: {"tau2_median_loo": float(np.nanmedian(det[leg]["tau2"])),
                          "tau2_zero_share": float(np.nanmean(det[leg]["tau2"] == 0)),
                          "B_median": float(np.median(det[leg]["B"])),
                          "identified_share": float(det[leg]["ident"].mean())} for leg in ("heat", "wet")}
    f = E.fit_n(ctx, n_max)
    bh = f["coef"][:, f["names"].index("heat")]
    bw = f["coef"][:, f["names"].index("wet")]
    out["beta_hat"] = {"heat_median": float(np.median(bh)), "wet_median": float(np.median(bw)),
                       "heat_iqr": [float(np.percentile(bh, 25)), float(np.percentile(bh, 75))],
                       "wet_iqr": [float(np.percentile(bw, 25)), float(np.percentile(bw, 75))]}
    for leg, b in (("heat", bh), ("wet", bw)):
        s = f["se"][leg]
        allp = dl(np.where(np.isfinite(s), b, np.nan), np.where(np.isfinite(s), s ** 2, np.nan))
        out[f"mu_{leg}_all"] = {**allp, "ci95": [allp["mu"] - 1.96 * allp["se_mu"], allp["mu"] + 1.96 * allp["se_mu"]]}
    out["mu_day_block_bootstrap_supplementary"] = E.mu_day_bootstrap(ctx, n_max)
    fc = [f["names"].index(c) for c in D.FOURIER_COLS]
    out["seasonal_offset_mean"] = dict(zip(D.FOURIER_COLS, map(float, f["coef"][:, fc].mean(0))))
    if real_ctx is None:
        out["temp_bin_shape"] = E.temp_bin_shape(ctx, n_max)
    keep = {}
    for arm in arms:
        if arm == "A0":
            continue
        res = {}
        if arm == "A4":
            for window in ("heat", "heat_rain"):
                h, hw = E.oracle_sizes(ctx, lg, window)
                r = E.score(ctx, lg, h, hw, want_weekly=weekly, windows=(window,))
                res.update({k: v for k, v in r.items() if not k.startswith("_")})
        else:
            h, hw = E.hedge_sizes(ctx, *ab[arm])
            r = E.score(ctx, lg, h, hw, want_weekly=weekly)
            res.update({k: v for k, v in r.items() if not k.startswith("_")})
            res["cost"] = cost_stats(r["_pnl"], "heat_rain" if g.rain_series else "heat")
            res["cost_heat_only"] = cost_stats(r["_pnl"], "heat")
            # policy-frame cost at the realised ladder load (Pattern 5)
            c = res["cost_heat_only"]
            load = c["buy_cost_ratio"] if c["buy_cost_ratio"] is not None else np.nan
            res["policy_cost_heat_at_ladder_load"] = float(np.nansum(np.clip(h, 0, None) * lg.EX[:, None]) * load) if np.isfinite(load) else None
            res["mean_h_heat_usd_per_degF"] = float(np.mean(h))
            res["mean_hw_rain_usd"] = float(np.mean(hw))
        keep[arm] = res
        out["arms"][arm] = res
    # volume terciles (A3, cover heat+rain daily)
    vol = ctx.Ys[ctx.i0 - 365:ctx.i0].mean(0)  # scaled -> use raw volume via scale-free rank on raw Y
    raw = p.Y[:, [list(p.units).index(u) for u in ctx.units]][ctx.i0 - 365:ctx.i0].mean(0)
    if "A3" in keep:
        he = keep["A3"]["cover_heat_rain_daily"]["_units"]
        q = np.quantile(raw, [1 / 3, 2 / 3])
        terc = np.digitize(raw, q)
        out["A3_cover_heat_rain_by_volume_tercile"] = {
            ["low", "mid", "high"][t]: {"median_he": float(np.nanmedian(he[terc == t])), "n": int((terc == t).sum()),
                                        "mean_daily_volume": float(raw[terc == t].mean())} for t in range(3)}
    return out, ctx


def ladder_share(res: dict) -> dict:
    out = {}
    for arm, r in res["arms"].items():
        for w in ("heat", "heat_rain"):
            c = r.get(f"cover_{w}_daily", {}).get("median")
            l = r.get(f"ladder_{w}_daily", {}).get("median")
            if c is not None and l is not None and c > 0:
                out[f"{arm}_{w}"] = l / c
    return out


# ------------------------------------------------------------------ learning curve

def lc_nmax(origin: str) -> int:
    o = np.datetime64(origin, "D")
    ok = [n for n in E.N_GRID if o - np.timedelta64(n, "D") >= np.datetime64("2022-07-01")]
    return max(ok)


def run_lc(p, cfg: E.Cfg) -> dict:
    g = p.group
    per = {}
    draws = {}
    for origin in g.origins_lc:
        n_max = lc_nmax(origin)
        if np.datetime64(origin) + np.timedelta64(365, "D") > p.dates[-1] + np.timedelta64(1, "D"):
            per[origin] = {"skipped": "hedge window beyond panel"}
            continue
        ctx = E.build_ctx(p, origin, n_max, cfg)
        E.baseline(ctx)
        lg = E.legs_for(ctx)
        po = {"n_max": n_max, "eligible": ctx.elig_log["eligible"], "K": ctx.K, "cells": {}}
        for n in [x for x in E.N_GRID if x <= n_max]:
            ab = E.arm_betas(ctx, n)
            cell = {}
            for arm in ("A1", "A2", "A3"):
                h, hw = E.hedge_sizes(ctx, *ab[arm])
                r = E.score(ctx, lg, h, hw, want_weekly=False, frames=("cover",), windows=("heat_rain",))
                s = r["cover_heat_rain_daily"]
                cell[arm] = {k: v for k, v in s.items() if not k.startswith("_")}
                draws[(origin, n, arm)] = s["_draws"]
                draws[(origin, n, arm, "units")] = s["_units"]
            cell["heat_identified_share"] = float(ab["_detail"]["heat"]["ident"].mean())
            cell["B_heat_median"] = float(np.median(ab["_detail"]["heat"]["B"]))
            po["cells"][n] = cell
        h, hw = E.oracle_sizes(ctx, lg, "heat_rain")
        r = E.score(ctx, lg, h, hw, want_weekly=False, frames=("cover",), windows=("heat_rain",))
        po["A4_cover_heat_rain_daily"] = {k: v for k, v in r["cover_heat_rain_daily"].items() if not k.startswith("_")}
        per[origin] = po
    # pooled over origins: average per-origin medians draw by draw
    pooled = {}
    origins = [o for o in g.origins_lc if "cells" in per.get(o, {})]
    for n in E.N_GRID:
        os_ = [o for o in origins if (o, n, "A1") in draws]
        if not os_:
            continue
        cell = {"origins": os_}
        for arm in ("A1", "A2", "A3"):
            dr = np.mean([draws[(o, n, arm)] for o in os_], axis=0)
            pt = float(np.mean([per[o]["cells"][n][arm]["median"] for o in os_]))
            sp = float(np.mean([per[o]["cells"][n][arm]["share_pos"] for o in os_]))
            sn = float(np.mean([per[o]["cells"][n][arm]["share_neg"] for o in os_]))
            cell[arm] = {"median": pt, "p05": float(np.percentile(dr, 5)), "p95": float(np.percentile(dr, 95)),
                         "share_pos": sp, "share_neg": sn}
        d31 = np.mean([draws[(o, n, "A3")] - draws[(o, n, "A1")] for o in os_], axis=0)
        cell["A3_minus_A1"] = {"median": cell["A3"]["median"] - cell["A1"]["median"],
                               "p05": float(np.percentile(d31, 5)), "p95": float(np.percentile(d31, 95)),
                               "paired_unit_median": float(np.mean([np.nanmedian(draws[(o, n, "A3", "units")] - draws[(o, n, "A1", "units")]) for o in os_]))}
        pooled[n] = cell
    return {"per_origin": per, "pooled": pooled}


def n_star(pooled: dict, arm: str) -> int | None:
    ns = sorted(pooled)
    ok = {n: (pooled[n][arm]["median"] > 0 and pooled[n][arm]["p05"] > 0 and pooled[n][arm]["share_pos"] >= 0.60) for n in ns}
    for i, n in enumerate(ns):
        if all(ok[m] for m in ns[i:]):
            return n
    return None


# ------------------------------------------------------------------ checks

def checks(p, ctx) -> dict:
    """Independent-implementation checks on real data (recorded, not unit tests)."""
    import statsmodels.api as sm
    from pandas.tseries.holiday import USFederalHolidayCalendar
    from statsmodels.stats.meta_analysis import combine_effects
    out = {}
    X, names, rows = E.design_at(ctx, 365)
    Ys = ctx.Ys[rows]
    diffs = []
    for u in range(min(3, Ys.shape[1])):
        ok = np.isfinite(X).all(1) & (Ys[:, u] > 0)
        from wi.elasticity.fit import fit_unit, select_columns
        keep = select_columns(X[ok], names)
        r = sm.OLS(np.log(Ys[ok, u]), X[ok][:, keep]).fit(cov_type="HAC", cov_kwds={"maxlags": 7})
        f = fit_unit(np.log(Ys[ok, u]), X[ok], names)
        kn = [names[j] for j in keep]
        diffs.append(max(abs(r.bse[kn.index(c)] - f["se"][c]) for c in ("heat", "wet") if c in kn))
    out["hac_vs_statsmodels_max_abs_se_diff"] = float(max(diffs))
    fit = E.fit_n(ctx, 365)
    b = fit["coef"][:, names.index("heat")]
    s = fit["se"]["heat"]
    m = np.isfinite(s)
    ce = combine_effects(b[m], s[m] ** 2, method_re="chi2")
    mine = dl(b[m], s[m] ** 2)
    out["dl_vs_combine_effects"] = {"tau2_sm": float(ce.tau2), "tau2_mine": mine["tau2"],
                                    "mu_sm": float(ce.mean_effect_re), "mu_mine": mine["mu"]}
    cep = combine_effects(b[m], s[m] ** 2, method_re="iterated")
    minep = pm(b[m], s[m] ** 2)
    out["pm_vs_combine_effects"] = {"tau2_sm": float(cep.tau2), "tau2_mine": minep["tau2"],
                                    "mu_sm": float(cep.mean_effect_re), "mu_mine": minep["mu"]}
    hol_pd = set(USFederalHolidayCalendar().holidays("2019-01-01", "2027-12-31").date)
    mine_h = set()
    for y in range(2019, 2028):
        mine_h |= set(D.us_holidays(y))
    extra = {d for d in mine_h if (d.month, d.day) in ((12, 24), (12, 31))} | \
            {D._nth_weekday(y, 11, 3, 4) + dt.timedelta(days=1) for y in range(2019, 2028)}
    fed_mine = {d for d in mine_h - extra if dt.date(2019, 1, 1) <= d <= dt.date(2027, 12, 31)}
    out["holidays_vs_pandas"] = {"missing": sorted(map(str, hol_pd - fed_mine - extra)),
                                 "extra": sorted(map(str, fed_mine - hol_pd))}
    return out


# ------------------------------------------------------------------ tests

def verdicts(R: dict) -> dict:
    V = {}
    # T1: mu_heat, mu_wet nonzero at 95 % for G1, G2 (primary)
    t1 = {}
    for gid in ("G1", "G2"):
        r = R["groups"].get(gid, {}).get("primary")
        if not r:
            t1[gid] = "not run"
            continue
        ch, cw = r["mu_heat_all"]["ci95"], r["mu_wet_all"]["ci95"]
        t1[gid] = {"mu_heat": r["mu_heat_all"]["mu"], "heat_ci": ch, "mu_wet": r["mu_wet_all"]["mu"], "wet_ci": cw,
                   "pass": bool((ch[0] > 0 or ch[1] < 0) and (cw[0] > 0 or cw[1] < 0))}
    V["T1"] = t1
    # T2: A3 primary, G1 and G2 cover heat+rain daily >= 0.20, LB > 0, >= 70 % units > 0; heat-only > 0 with LB > 0
    t2 = {}
    for gid in ("G1", "G2", "G3", "G4", "G5"):
        r = R["groups"].get(gid, {}).get("primary")
        if not r:
            t2[gid] = "not run"
            continue
        a = r["arms"]["A3"]
        hr, ho = a["cover_heat_rain_daily"], a["cover_heat_daily"]
        passed = bool(hr["median"] >= 0.20 and hr["p05"] > 0 and hr["share_pos"] >= 0.70 and ho["median"] > 0 and ho["p05"] > 0)
        t2[gid] = {"heat_rain_median": hr["median"], "heat_rain_ci": [hr["p05"], hr["p95"]], "share_pos": hr["share_pos"],
                   "heat_only_median": ho["median"], "heat_only_ci": [ho["p05"], ho["p95"]],
                   "pass": passed if gid in ("G1", "G2") else "no threshold (reported)"}
    V["T2"] = t2
    # T3: A3 G1 heat+rain, G2 heat: ladder HE > 0 with LB > 0, cost <= 25 % of payout
    t3 = {}
    for gid, w in (("G1", "heat_rain"), ("G2", "heat")):
        r = R["groups"].get(gid, {}).get("primary")
        if not r:
            t3[gid] = "not run"
            continue
        a = r["arms"]["A3"]
        l = a[f"ladder_{w}_daily"]
        c = a["cost"] if w == "heat_rain" else a["cost_heat_only"]
        cr = c["buy_cost_ratio"]
        t3[gid] = {"ladder_median": l["median"], "ladder_ci": [l["p05"], l["p95"]], "cost_ratio": cr,
                   "cost_ratio_unit_median": c["buy_cost_ratio_unit_median"],
                   "pass": bool(l["median"] > 0 and l["p05"] > 0 and cr is not None and cr <= 0.25)}
    V["T3"] = t3
    # T4 / T5 per group from the pooled learning curve
    t4, t5 = {}, {}
    for gid, gr in R["groups"].items():
        lc = gr.get("learning_curve")
        if not lc or not lc.get("pooled"):
            continue
        P = {int(k): v for k, v in lc["pooled"].items()}
        short = [n for n in (60, 90, 120, 180) if n in P]
        cond_short = all(P[n]["A3_minus_A1"]["median"] >= 0.02 and P[n]["A3_minus_A1"]["p05"] > 0
                         and P[n]["A3"]["share_neg"] < P[n]["A1"]["share_neg"] for n in short)
        cond_365 = (365 in P) and P[365]["A3"]["median"] >= P[365]["A1"]["median"] - 0.01
        t4[gid] = {"short_n": {n: {"diff": P[n]["A3_minus_A1"]["median"], "diff_ci": [P[n]["A3_minus_A1"]["p05"], P[n]["A3_minus_A1"]["p95"]],
                                   "share_neg_A1": P[n]["A1"]["share_neg"], "share_neg_A3": P[n]["A3"]["share_neg"]} for n in short},
                   "n365_A3": P.get(365, {}).get("A3", {}).get("median"), "n365_A1": P.get(365, {}).get("A1", {}).get("median"),
                   "pass": bool(cond_short and cond_365)}
        ns = {arm: n_star(P, arm) for arm in ("A1", "A2", "A3")}
        t5[gid] = {"n_star_A1": ns["A1"], "n_star_A3": ns["A3"], "A2_passes_all_n": ns["A2"] == min(P) if ns["A2"] else False,
                   "note": "n* = 0 with a sector prior" if ns["A2"] == min(P) else ""}
    V["T4"] = t4
    V["T5"] = t5
    p1 = {}
    for gid, gr in R["groups"].items():
        pl = gr.get("placebo")
        if not pl:
            continue
        ch, cw = pl["mu_heat_all"]["ci95"], pl["mu_wet_all"]["ci95"]
        he = pl["arms"]["A3"]["cover_heat_rain_daily"]["median"]
        insig = (ch[0] <= 0 <= ch[1]) and (cw[0] <= 0 <= cw[1])
        p1[gid] = {"mu_heat": pl["mu_heat_all"]["mu"], "heat_ci": ch, "mu_wet": pl["mu_wet_all"]["mu"], "wet_ci": cw,
                   "median_he_cover": he, "mu_insignificant": bool(insig), "he_le_0.02": bool(he <= 0.02),
                   "pass": bool(insig and he <= 0.02)}
    V["P1"] = p1
    return V


# ------------------------------------------------------------------ main

SENS = {
    "cap6": dict(cap=6.0),
    "levels_sizing": dict(target="level"),
    "ppml": dict(target="ppml"),
    "thin150": dict(thin=True),
    "decision_30h": dict(horizon=30),
    "decision_12h": dict(horizon=12),
    "excl_suspension_days": dict(exclude_susp=True),
    "eb_paule_mandel": dict(eb="pm"),
    "depth_cap_20": dict(depth_cap=20),
}


def run_sensitivity(p, name: str, kw: dict, boot: int) -> dict:
    g = p.group
    if name in ("ppml", "thin150") and g.sector == "taxi":
        return {"skipped": "count-only sensitivity (taxi series are fare dollars)"}
    cfg = E.Cfg(boot=boot, **{k: v for k, v in kw.items() if k != "target"})
    ctx = E.build_ctx(p, g.origins_primary, 365, cfg)
    E.baseline(ctx)
    lg = E.legs_for(ctx)
    out = {"K": ctx.K}
    target = kw.get("target", "log")
    if target != "log":
        f = E.fit_n(ctx, 365, target)
        ctx.fits[(365, "log_backup")] = ctx.fits[(365, "log")]
        ctx.fits[(365, "log")] = f          # arms read the default key
    ab = E.arm_betas(ctx, 365)
    if target != "log":
        ctx.fits[(365, "log")] = ctx.fits[(365, "log_backup")]
    for arm in ("A1", "A3"):
        sizing = "level" if target == "level" else "semi"
        h, hw = E.hedge_sizes(ctx, *ab[arm], sizing=sizing)
        r = E.score(ctx, lg, h, hw, want_weekly=False)
        out[arm] = {k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")} for k, v in r.items() if not k.startswith("_")}
        out[arm]["cost"] = cost_stats(r["_pnl"], "heat_rain" if g.rain_series else "heat")
    return out


# ------------------------------------------------------------------ artifacts: tables, figures, priors

def fmt(x, d=3):
    if x is None:
        return "-"
    if isinstance(x, (int, np.integer)):
        return str(x)
    try:
        return f"{x:.{d}f}"
    except (TypeError, ValueError):
        return str(x)


def ci(s):
    return f"{fmt(s['median'])} [{fmt(s['p05'])}, {fmt(s['p95'])}]"


def write_tables(R: dict) -> None:
    L = [f"# EVAL-06 tables", "", f"Generated {R['written_utc']} from results.json (PREREG frozen {R['prereg_frozen_utc']}). "
         f"Median across units, 5-95 % day-block bootstrap interval ({R['boot_draws']} draws). HE = 1 - var(U + hedge P&L) / var(U).", ""]
    L += ["## Panels and eligibility (primary split)", "", "| group | units in panel | active >= 98 % | volume floor | level break excluded | eligible | K (degF) | payout days (CLI) | ladder days | rain days listed |", "|---|---|---|---|---|---|---|---|---|---|"]
    for gid, gr in R["groups"].items():
        pr = gr.get("primary")
        if not pr:
            L.append(f"| {gid} | not run: {gr.get('not_run', '')} |||||||||")
            continue
        e = pr["eligibility"]
        L.append(f"| {gid} | {e['units_in_panel']} | {e['active_98']} | {e['volume_floor']} | {e['level_break_excluded']} | {e['eligible']} | {fmt(pr['K'], 0)} | {pr['payout_days_cli']} | {pr['ladder_days_listed']} | {pr['rain_days_listed']} |")
    for split in ("primary", "replication"):
        L += ["", f"## {split.title()} split: HE by arm (daily; weekly in the second table)", ""]
        for gid, gr in R["groups"].items():
            r = gr.get(split)
            if not r or "arms" not in r:
                continue
            L += [f"### {gid} {GROUPS[gid].label}, origin {r['origin']}, n = {r['n']}, K = {fmt(r['K'], 0)}", "",
                  "| arm | HE_cover heat (Jun-Sep) | HE_ladder heat (Jun-Sep) | HE_cover heat+rain | HE_ladder heat+rain* | units > 0 (cover h+r) |", "|---|---|---|---|---|---|"]
            L.append("| A0 none | 0 | 0 | 0 | 0 | - |")
            for arm in ("A1", "A2", "A3", "A4"):
                a = r["arms"].get(arm)
                if not a:
                    continue
                L.append(f"| {arm} | {ci(a['cover_heat_daily'])} | {ci(a['ladder_heat_daily'])} | {ci(a['cover_heat_rain_daily'])} | {ci(a['ladder_heat_rain_daily'])} | {fmt(a['cover_heat_rain_daily']['share_pos'], 2)} |")
            L += ["", "| arm (weekly sums) | HE_cover heat | HE_ladder heat | HE_cover heat+rain | HE_ladder heat+rain* |", "|---|---|---|---|---|"]
            for arm in ("A1", "A2", "A3", "A4"):
                a = r["arms"].get(arm)
                if not a or "cover_heat_weekly" not in a:
                    continue
                L.append(f"| {arm} | {ci(a['cover_heat_weekly'])} | {ci(a['ladder_heat_weekly'])} | {ci(a['cover_heat_rain_weekly'])} | {ci(a['ladder_heat_rain_weekly'])} |")
            a3 = r["arms"].get("A3", {})
            c = a3.get("cost", {})
            L += ["", f"A3 execution: buy-side premium incl. fees {fmt(c.get('buy_premium_incl_fees'), 0)}, payout {fmt(c.get('buy_payout'), 0)}, "
                  f"realised cost ratio {fmt(c.get('buy_cost_ratio'))} (unit median {fmt(c.get('buy_cost_ratio_unit_median'))}); fees {fmt(c.get('fees_total'), 0)}; "
                  f"sell-side net premium {fmt(c.get('sell_premium_net'), 0)} vs payout {fmt(c.get('sell_payout'), 0)}; unhedgeable unit-days heat {c.get('unhedgeable_unit_days_heat')}, rain {c.get('unhedgeable_unit_days_rain')}. "
                  f"Prior: tau2_heat zero share {fmt(r['prior']['heat']['tau2_zero_share'], 2)}, median B_heat {fmt(r['prior']['heat']['B_median'], 2)}; median beta_heat {fmt(r['beta_hat']['heat_median'], 4)}, beta_wet {fmt(r['beta_hat']['wet_median'], 4)}.",
                  "", "*Chicago groups: HE_ladder heat+rain = heat leg only (no daily Chicago rain asks before Sep 2026).", ""]
    L += ["## Learning curve (HE_cover heat+rain, daily; pooled over origins)", ""]
    for gid, gr in R["groups"].items():
        lc = gr.get("learning_curve")
        if not lc or not lc.get("pooled"):
            continue
        L += [f"### {gid}", "", "| n | A1 own | A2 pooled | A3 EB | A3 - A1 | units < 0 A1 / A3 |", "|---|---|---|---|---|---|"]
        for n, c in sorted(lc["pooled"].items(), key=lambda t: int(t[0])):
            d = c["A3_minus_A1"]
            L.append(f"| {n} | {ci(c['A1'])} | {ci(c['A2'])} | {ci(c['A3'])} | {fmt(d['median'])} [{fmt(d['p05'])}, {fmt(d['p95'])}] | {fmt(c['A1']['share_neg'], 2)} / {fmt(c['A3']['share_neg'], 2)} |")
        L.append("")
    L += ["## Placebo P1 (2019 weather on the estimation window; A3 on the real hedge year)", "", "| group | mu_heat [95 % CI] | mu_wet [95 % CI] | median HE_cover | day-block mu_heat CI | day-block mu_wet CI |", "|---|---|---|---|---|---|"]
    for gid, gr in R["groups"].items():
        pl = gr.get("placebo")
        if not pl:
            continue
        mb = pl.get("mu_day_block_bootstrap_supplementary", {})
        h, w = pl["mu_heat_all"], pl["mu_wet_all"]
        L.append(f"| {gid} | {fmt(h['mu'], 4)} [{fmt(h['ci95'][0], 4)}, {fmt(h['ci95'][1], 4)}] | {fmt(w['mu'], 4)} [{fmt(w['ci95'][0], 4)}, {fmt(w['ci95'][1], 4)}] | {fmt(pl['arms']['A3']['cover_heat_rain_daily']['median'])} | "
                 f"{fmt(mb.get('heat', {}).get('p025'), 4)}..{fmt(mb.get('heat', {}).get('p975'), 4)} | {fmt(mb.get('wet', {}).get('p025'), 4)}..{fmt(mb.get('wet', {}).get('p975'), 4)} |")
    L += ["", "## Sensitivities (primary split; median HE, A1 / A3)", "", "| group | sensitivity | cover heat+rain A1 | cover heat+rain A3 | ladder heat+rain* A3 | ladder heat A3 | A3 cost ratio |", "|---|---|---|---|---|---|---|"]
    for gid, gr in R["groups"].items():
        for name, sv in (gr.get("sensitivities") or {}).items():
            if "A3" not in sv:
                L.append(f"| {gid} | {name} | {sv.get('skipped') or sv.get('error')} |||||")
                continue
            L.append(f"| {gid} | {name} | {fmt(sv['A1']['cover_heat_rain_daily']['median'])} | {fmt(sv['A3']['cover_heat_rain_daily']['median'])} | {fmt(sv['A3']['ladder_heat_rain_daily']['median'])} | {fmt(sv['A3']['ladder_heat_daily']['median'])} | {fmt(sv['A3']['cost']['buy_cost_ratio'])} |")
    L += ["", "## Checks", "", "```", json.dumps(R.get("checks", {}), indent=1, default=str), "```", ""]
    (REP / "tables.md").write_text("\n".join(L))


def write_figures(R: dict) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    FIG.mkdir(parents=True, exist_ok=True)
    gids = [g for g in R["groups"] if R["groups"][g].get("primary")]
    # 1. HE by arm
    fig, axes = plt.subplots(1, len(gids), figsize=(3.2 * len(gids), 3.4), sharey=True, squeeze=False)
    for ax, gid in zip(axes[0], gids):
        a = R["groups"][gid]["primary"]["arms"]
        xs = np.arange(4)
        for k, (frame, col) in enumerate((("cover", "#3b6ea5"), ("ladder", "#c0504d"))):
            key = f"{frame}_heat_rain_daily"
            m = [a[x][key]["median"] for x in ("A1", "A2", "A3", "A4")]
            lo = [a[x][key]["median"] - a[x][key]["p05"] for x in ("A1", "A2", "A3", "A4")]
            hi = [a[x][key]["p95"] - a[x][key]["median"] for x in ("A1", "A2", "A3", "A4")]
            ax.bar(xs + (k - 0.5) * 0.38, m, 0.38, yerr=[lo, hi], color=col, label=f"HE_{frame}", capsize=2)
        ax.axhline(0, color="k", lw=0.6)
        ax.set_xticks(xs, ["own", "pooled", "EB", "oracle"])
        ax.set_title(gid, fontsize=9)
    axes[0][0].set_ylabel("median HE, heat+rain, daily")
    axes[0][0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(FIG / "he_by_arm.png", dpi=130)
    plt.close(fig)
    # 2. learning curve
    lcg = [g for g in gids if R["groups"][g].get("learning_curve", {}).get("pooled")]
    if lcg:
        fig, axes = plt.subplots(1, len(lcg), figsize=(3.2 * len(lcg), 3.2), squeeze=False)
        for ax, gid in zip(axes[0], lcg):
            P = R["groups"][gid]["learning_curve"]["pooled"]
            ns = sorted(int(n) for n in P)
            for arm, col in (("A1", "#999999"), ("A2", "#6aa84f"), ("A3", "#3b6ea5")):
                m = [P[str(n)][arm]["median"] if str(n) in P else P[n][arm]["median"] for n in ns]
                lo = [P[str(n)][arm]["p05"] if str(n) in P else P[n][arm]["p05"] for n in ns]
                hi = [P[str(n)][arm]["p95"] if str(n) in P else P[n][arm]["p95"] for n in ns]
                ax.plot(ns, m, "-o", ms=3, color=col, label=arm)
                ax.fill_between(ns, lo, hi, color=col, alpha=0.15)
            ax.axhline(0, color="k", lw=0.6)
            ax.set_xscale("log")
            ax.xaxis.set_minor_locator(matplotlib.ticker.NullLocator())
            ax.set_xticks(ns, [str(n) for n in ns], fontsize=6)
            ax.set_title(gid, fontsize=9)
            ax.set_xlabel("days of history")
        axes[0][0].set_ylabel("median HE_cover (heat+rain)")
        axes[0][0].legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(FIG / "learning_curve.png", dpi=130)
        plt.close(fig)
    # 3. K profile and 4. temperature bins
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4))
    for gid in gids:
        pr = R["groups"][gid]["primary"]
        kp = {int(k): v for k, v in pr["k_profile_ssr"].items()}
        ks = sorted(kp)
        base = min(kp.values())
        axes[0].plot(ks, [kp[k] / base - 1 for k in ks], "-o", ms=3, label=gid)
        tb = pr.get("temp_bin_shape", {})
        if tb:
            allabs = ["<40"] + [f"{a}-{a + 4}" for a in range(40, 95, 5)] + [">=95"]
            xs = [allabs.index(l) for l in tb]
            axes[1].plot(xs, [tb[l]["coef"] for l in tb], "-o", ms=3, label=gid)
            axes[1].set_xticks(range(len(allabs)), allabs, rotation=60, fontsize=6)
    axes[0].set_xlabel("K (degF)"); axes[0].set_ylabel("SSR / min SSR - 1"); axes[0].set_title("K profile (primary est. window)", fontsize=9)
    axes[1].axhline(0, color="k", lw=0.6); axes[1].set_ylabel("mean log effect vs 60-64 degF"); axes[1].set_title("5 degF bin shape (diagnostic)", fontsize=9)
    axes[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(FIG / "k_profile_and_temp_bins.png", dpi=130)
    plt.close(fig)


def write_priors(R: dict) -> dict:
    V = R.get("verdicts", {})
    t2 = V.get("T2", {})
    t2_bike_fail = all(isinstance(t2.get(g), dict) and t2[g].get("pass") is False for g in ("G1", "G2"))
    P = {"written_utc": R["written_utc"], "prereg_frozen_utc": R["prereg_frozen_utc"],
         "source": "reports/eval-06/results.json (primary split, n = 365, all eligible units, DerSimonian-Laird)",
         "design": "wi.elasticity.design v1: log sales ~ DOW + holidays + trend + Fourier(3) | offset + tlin + heat + wet + heavy + wet_l1 + heat_l1 + snow; HAC(7)",
         "fee": "ceil-to-cent(0.07 * C * P * (1 - P)) per order",
         "kill_keep": "PREREG §10", "groups": {}}
    for gid, gr in R["groups"].items():
        pr = gr.get("primary")
        if not pr:
            continue
        g = GROUPS[gid]
        t4 = V.get("T4", {}).get(gid, {})
        t5 = V.get("T5", {}).get(gid, {})
        mode = "always_shrink" if t4.get("pass") else "own_ols_after_n_star"
        P["groups"][gid] = {
            "gid": gid, "label": g.label, "sector": g.sector, "city": g.city, "weather_station": g.station,
            "heat_series": g.heat_series, "rain_series": g.rain_series, "weather_class": g.weather_class,
            "learned": True, "origin": pr["origin"], "estimation_days": pr["n"], "n_units": pr["eligibility"]["eligible"],
            "K": pr["K"], "cap": pr["cap"],
            "mu_heat": pr["mu_heat_all"]["mu"], "tau2_heat": pr["mu_heat_all"]["tau2"], "se_mu_heat": pr["mu_heat_all"]["se_mu"],
            "mu_wet": pr["mu_wet_all"]["mu"], "tau2_wet": pr["mu_wet_all"]["tau2"], "se_mu_wet": pr["mu_wet_all"]["se_mu"],
            "seasonal_offset": pr["seasonal_offset_mean"],
            "portal_mode": mode, "n_star_own": t5.get("n_star_A1"),
            "advisory_only": bool(t2_bike_fail),
        }
    P["new_sector_without_panel"] = {"learned": False, "note": "no stand-in panel: the prior is not learned; flag it in the UI (05-RESEARCH Pitfall 9)"}
    txt = json.dumps(P, indent=1, default=str)
    (REP / "priors.json").write_text(txt)
    (ROOT / "src" / "wi" / "elasticity" / "priors.json").write_text(txt)
    return P


def write_manifest(R: dict) -> None:
    rows = R.get("manifest", [])
    seen, agg = set(), {}
    for r in rows:
        if "url" not in r or (r["source"], r["url"]) in seen:
            continue
        seen.add((r["source"], r["url"]))
        a = agg.setdefault(r["source"], {"files": 0, "bytes": 0, "bytes_unknown": 0, "rows_read": 0, "rows_out": 0, "first": r["url"], "last": r["url"]})
        a["files"] += 1
        if r.get("bytes_streamed") is None:
            a["bytes_unknown"] += 1
        else:
            a["bytes"] += int(r["bytes_streamed"])
        a["rows_read"] += int(r.get("rows_read") or 0)
        a["rows_out"] += int(r.get("rows_out") or 0)
        a["last"] = r["url"]
    stops = [r for r in rows if r.get("source") == "guard"]
    L = ["# EVAL-06 data manifest", "", f"Generated {R['written_utc']}. Raw trips were never stored: bikeshare zips were deleted after aggregation, Socrata and TLC were aggregated server-side / by remote column reads. Per-file lines: `data/cache/sales_daily/manifest.jsonl` (gitignored).", "",
         "| source | files / requests | bytes streamed | rows read (trips or source rows) | unit-day rows out | first URL | last URL |", "|---|---|---|---|---|---|---|"]
    for src, a in agg.items():
        b = f"{a['bytes'] / 1e9:.2f} GB" + (f" (+{a['bytes_unknown']} files size unknown)" if a["bytes_unknown"] else "")
        L.append(f"| {src} | {a['files']} | {b} | {a['rows_read']:,} | {a['rows_out']:,} | {a['first']} | {a['last']} |")
    L += ["", "TLC bytes are the remote file sizes; DuckDB httpfs fetched only the pickup-time, zone and fare column chunks by HTTP range request. Chicago taxi `rows read` is the trip count summed server-side.", ""]
    if stops:
        L += ["Disk guard stops:", ""] + [f"- {s['ts_utc']}: {s['stopped']}" for s in stops] + [""]
    wr = ROOT / "data" / "cache" / "elasticity" / "weather_report.json"
    if wr.exists():
        L += ["## Weather", "", "NWS CLI (IEM, 2023-01-01..2026-09-29) spliced onto NOAA RCC-ACIS StnData (1990-01-01..). Agreement on the overlap:", "", "```", wr.read_text(), "```", ""]
    L += ["## Panels (unit-day rows with sales > 0, weather joined)", "", "| group | active unit-days | units | first | last | file |", "|---|---|---|---|---|---|"]
    for gid, pnl in R.get("panels", {}).items():
        L.append(f"| {gid} | {pnl['rows_active']:,} | {pnl['units_total']} | {pnl['first']} | {pnl['last']} | {pnl['path']} |")
    (REP / "manifest.md").write_text("\n".join(L) + "\n")


def portal_check(ctxs: dict, priors: dict) -> dict:
    """The portal function on one real unit per group (first eligible unit, the primary 365-day
    window) must reproduce the evaluation's own-OLS coefficients (same design, same fit)."""
    from wi.elasticity.portal import estimate
    from wi.elasticity.panel import weather_series
    out = {}
    for gid, (p, ctx) in ctxs.items():
        if gid not in priors["groups"]:
            continue
        u = 0
        rows = slice(ctx.i0 - 365, ctx.i0)
        dates = pd.to_datetime(ctx.dates[rows])
        sales = [{"date": d.strftime("%Y-%m-%d"), "sales": float(v)} for d, v in zip(dates, ctx.Ys[rows, u])]
        w = weather_series(p.group.station)
        w = w[(w.index >= dates[0] - pd.Timedelta(days=1)) & (w.index <= dates[-1])]
        wx = [{"date": d.strftime("%Y-%m-%d"), "tmax_f": float(r.tmax_f), "prcp_in": float(r.prcp_in),
               "snow_in": None if np.isnan(r.snow_in) else float(r.snow_in)} for d, r in w.iterrows()]
        est = estimate(sales, wx, priors, group=gid)
        f = E.fit_n(ctx, 365)
        ev_h = float(f["coef"][u, f["names"].index("heat")])
        ev_w = float(f["coef"][u, f["names"].index("wet")])
        out[gid] = {"unit": str(ctx.units[u]), "portal_beta_heat": est["heat"]["beta_own"], "eval_beta_heat": ev_h,
                    "portal_beta_wet": est["wet"]["beta_own"], "eval_beta_wet": ev_w,
                    "max_abs_diff": max(abs((est["heat"]["beta_own"] or 0) - ev_h), abs((est["wet"]["beta_own"] or 0) - ev_w)),
                    "portal_prescription": est["prescription"]}
    return out


def report(R: dict) -> None:
    write_manifest(R)
    write_tables(R)
    write_figures(R)
    write_priors(R)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--groups", nargs="*", default=None)
    ap.add_argument("--no-lc", action="store_true")
    ap.add_argument("--no-sens", action="store_true")
    ap.add_argument("--no-placebo", action="store_true")
    ap.add_argument("--boot", type=int, default=E.BOOT_DRAWS)
    ap.add_argument("--out", default=str(REP / "results.json"))
    ap.add_argument("--report-only", action="store_true")
    a = ap.parse_args()
    if a.report_only:
        report(json.loads(Path(a.out).read_text()))
        return
    t_start = time.time()
    pts = prereg_ts()
    gids = a.groups or list(GROUPS)
    R = {"written_utc": None, "prereg_frozen_utc": pts, "boot_draws": a.boot, "groups": {}, "panels": {}, "notes": []}
    first_ctx = None
    ctxs = {}
    for gid in gids:
        try:
            p = build_panel(gid)
        except FileNotFoundError as e:
            R["groups"][gid] = {"not_run": str(e)}
            continue
        R["panels"][gid] = write_panel_parquet(p)
        gr = {}
        cfg = E.Cfg(boot=a.boot)
        g = p.group
        print(f"[{utcnow()}] {gid} primary", flush=True)
        try:
            prim, pctx = run_split(p, g.origins_primary, 365, cfg)
        except ValueError as e:
            R["groups"][gid] = {"not_run": str(e)}
            continue
        prim["ladder_transferable_share"] = ladder_share(prim)
        gr["primary"] = prim
        if first_ctx is None:
            first_ctx = (p, pctx)
        ctxs[gid] = (p, pctx)
        if g.origins_replication:
            print(f"[{utcnow()}] {gid} replication", flush=True)
            try:
                rep, _ = run_split(p, g.origins_replication, 365, cfg)
                rep["ladder_transferable_share"] = ladder_share(rep)
                gr["replication"] = rep
            except ValueError as e:
                gr["replication"] = {"not_run": str(e)}
        if not a.no_placebo:
            print(f"[{utcnow()}] {gid} placebo", flush=True)
            pcfg = replace(cfg, placebo_year=2019)
            plc = E.build_ctx(p, g.origins_primary, 365, pcfg)
            pl, _ = run_split(p, g.origins_primary, 365, pcfg, arms=("A3",), weekly=False, ctx=plc, real_ctx=pctx)
            gr["placebo"] = pl
        if not a.no_lc:
            print(f"[{utcnow()}] {gid} learning curve", flush=True)
            gr["learning_curve"] = run_lc(p, cfg)
        if not a.no_sens:
            gr["sensitivities"] = {}
            for name, kw in SENS.items():
                print(f"[{utcnow()}] {gid} sens {name}", flush=True)
                try:
                    gr["sensitivities"][name] = run_sensitivity(p, name, kw, a.boot)
                except Exception as e:  # recorded, not hidden
                    gr["sensitivities"][name] = {"error": repr(e)}
        R["groups"][gid] = E.strip(gr)
        write(R, a.out, partial=True)
    if first_ctx:
        R["checks"] = checks(*first_ctx)
    R["verdicts"] = verdicts(R)
    R["written_utc"] = utcnow()
    pri = write_priors(E.strip(R))
    R.setdefault("checks", {})["portal_vs_eval"] = portal_check(ctxs, pri)
    R["manifest"] = manifest_summary()
    R["runtime_s"] = round(time.time() - t_start, 1)
    write(R, a.out)
    if Path(a.out).resolve() == (REP / "results.json").resolve():
        report(json.loads(Path(a.out).read_text()))
    print(json.dumps(E.strip(R["verdicts"]), indent=1, default=str))


def write(R, path, partial=False):
    R["written_utc"] = utcnow()
    R["partial"] = partial
    Path(path).write_text(json.dumps(E.strip(R), indent=1, default=str))


if __name__ == "__main__":
    main()
