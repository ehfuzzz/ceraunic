"""EVAL-04 add-on: junior-tranche return and premium split (rules: reports/eval-04-05/PREREG-junior.md).

uv run python scripts/eval04_junior.py

Reads Phase 4's caches (data/cache/eval04/) and handoff.json; reuses scripts/eval04.py's
scenario bundle, average book and unit matrices. Writes only reports/eval-04-05/junior_returns.{json,md}.
Deterministic (seed 20260930).

SPEC mapping (docs/SPEC.md §6, §8.3, §8.6, §11):
- station-leg house fills = policies the pool writes; premium per $1 scalar unit = p* (house offer,
  pool writes a call) or 1 - p* (house bid, pool writes a put, payout UNIT - L(x));
- residual-leg house fills + Kalshi hedge = house deployment: all P&L to junior, no senior share;
- treasury = t x station risk margin; senior = s x (premium - treasury); junior = the rest.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
_spec = importlib.util.spec_from_file_location("eval04", ROOT / "scripts" / "eval04.py")
E4 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(E4)

from wi.pool import capital as cap  # noqa: E402

CACHE = ROOT / "data" / "cache" / "eval04"
REPORT = ROOT / "reports" / "eval-04-05"
SEED = 20260930
S_SENIOR = 0.20                       # SPEC §17 seniorPremiumBps 2000
T_CUTS = (0.10, 0.20)                 # 14-RESEARCH rule 5
BLOCK, REPS = 7, 10_000
NDAYS = len(cap.SEASON)               # 153


def decompose(a: pd.DataFrame) -> pd.DataFrame:
    """Per market-day: premium, fair expected payout, risk margin, payout, hedge cost (all $)."""
    a = a.copy()
    a["date"] = pd.to_datetime(a["date"])
    p = a["p_star"] / 100.0
    a["prem"] = p * a["house_off"] + (1 - p) * a["house_bid"]
    a["exp_pay"] = a["mu_s"] * a["house_off"] + (1 - a["mu_s"]) * a["house_bid"]
    a["rm"] = a["prem"] - a["exp_pay"]
    a["pay"] = a["x"] * a["house_off"] + (1 - a["x"]) * a["house_bid"]
    assert np.allclose(a["prem"] - a["pay"], a["mo_settle"], atol=1e-6), "premium - payout must equal the house markout"
    # Kalshi hedge vs its fair value: hedge_units $1/degF units long H, fair mu ($), settled 6x ($)
    fair_hedge = np.where(a["leg"] == "station", a["hedge_units"] * (6.0 * a["x"] - a["mu"]), 0.0)
    a["hedge_cost"] = a["hedge_pnl"] - fair_hedge
    st = a["leg"] == "station"
    a["prem_st"] = np.where(st, a["prem"], 0.0)
    a["rm_st"] = np.where(st, a["rm"], 0.0)
    a["pay_st"] = np.where(st, a["pay"], 0.0)
    a["mo_res"] = np.where(st, 0.0, a["mo_settle"])
    a["polnotional_st"] = np.where(st, a["house_bid"] + a["house_off"], 0.0)
    return a


def split(prem, rm_st, t, senior_rule="spec"):
    """(treasury, senior, junior premium share) for station premium `prem` and margin `rm_st`."""
    tre = t * rm_st
    sen = S_SENIOR * (prem - tre) if senior_rule == "spec" else S_SENIOR * (1 - t) * rm_st
    return tre, sen, prem - tre - sen


def junior_daily(d: pd.DataFrame, t: float, rule: str) -> pd.Series:
    """Daily junior P&L = junior premium share - station payouts + residual P&L + hedge P&L."""
    tre, sen, jp = split(d["prem_st"], d["rm_st"], t, rule)
    j = jp - d["pay_st"] + d["mo_res"] + d["hedge_pnl"]
    return j.groupby(d["date"]).sum(), sen.groupby(d["date"]).sum()


def waterfall(jd: pd.Series, sd: pd.Series, J0: float, S0: float) -> dict:
    """Day by day: junior floored at 0 (senior pays the rest, SPEC _loss); first wipe-out date."""
    J, S, wipe = J0, S0, None
    for date in jd.index:
        S += sd.loc[date]
        J += jd.loc[date]
        if J < 0:
            S += J
            J = 0.0
            if wipe is None:
                wipe = str(date.date())
    return dict(junior_end=J, senior_end=S, junior_return_floored=J / J0 - 1, senior_return=S / S0 - 1,
                junior_wiped_on=wipe)


def observed(a: pd.DataFrame, J0: float, S0: float) -> dict:
    d = decompose(a)
    out = {}
    for rule in ("spec", "margin"):
        for t in T_CUTS:
            key = f"{rule}_t{int(t * 100)}"
            per = {}
            for y, g in d.groupby(d["date"].dt.year):
                jd, sd = junior_daily(g, t, rule)
                tre, sen, jp = split(g["prem_st"].sum(), g["rm_st"].sum(), t, rule)
                per[int(y)] = dict(days=int(g["date"].nunique()), station_premium=float(g["prem_st"].sum()),
                                   station_risk_margin=float(g["rm_st"].sum()), station_payouts=float(g["pay_st"].sum()),
                                   residual_pnl=float(g["mo_res"].sum()), hedge_pnl=float(g["hedge_pnl"].sum()),
                                   treasury=float(tre), senior=float(sen), junior_premium=float(jp),
                                   notional_fee_10bps_on_top=float(0.001 * g["polnotional_st"].sum()),
                                   junior_pnl=float(jd.sum()), junior_return=float(jd.sum() / J0),
                                   senior_return_simple=float(sen / S0), **waterfall(jd, sd, J0, S0))
            r = np.array([v["junior_return"] for v in per.values()])
            out[key] = dict(by_season=per, median_return=float(np.median(r)), worst_return=float(r.min()),
                            worst_season=int(list(per)[int(r.argmin())]))
    return out, d


def model_based(d_obs: pd.DataFrame, J0: float) -> dict:
    """Bootstrap seasons on the capital scenario (deploy_detrended, both legs, 1999-2025)."""
    pop = pd.read_parquet(CACHE / "population.parquet")
    uw = pd.read_parquet(CACHE / "unit_weights.parquet")
    part = dict(np.load(CACHE / "participants.npz"))
    biz = E4.business_table(pop, part["p2"], uw)
    auc = pd.read_parquet(CACHE / "auction_primary.parquet")
    book, price, _ = E4.average_book(auc, biz)
    W = E4.load_weather()
    B = E4.proxy_bundle(W, (1951, 2025), True)
    years = list(range(1999, 2026))
    mats = E4.unit_matrices(B, years, (1951, 2025))
    pnl, miss = E4.book_pnl(mats, book)
    keep = miss.sum(axis=1) <= 5
    pnl = pnl[keep]
    kept_years = [y for y, k in zip(years, keep) if k]
    # check against Phase 4's headline capital (same matrix -> same C_30)
    c30 = cap.capital(pnl, 30, E4.fc_per_day(book, price)[0])["C"]

    # per-calendar-month daily means from the Kalshi-era primary auction (deterministic terms)
    g = d_obs.assign(month=d_obs["date"].dt.month)
    daily = g.groupby(["date", "month"])[["rm", "hedge_cost", "prem_st", "rm_st"]].sum().reset_index()
    mon = daily.groupby("month")[["rm", "hedge_cost", "prem_st", "rm_st"]].mean()
    month_of = np.array([int(x[:2]) for x in cap.SEASON])
    per_day = {c: mon[c].reindex(month_of).to_numpy() for c in mon.columns}

    def boot(block: int, seed: int) -> tuple[np.ndarray, np.ndarray]:
        rng = np.random.default_rng(seed)
        nb = -(-NDAYS // block)
        ys = rng.integers(0, len(kept_years), size=(REPS, nb))
        w = np.zeros(REPS)
        for b in range(nb):
            cols = slice(b * block, min((b + 1) * block, NDAYS))
            w += pnl[ys[:, b], cols].sum(axis=1)
        # three-season sums: independent draws from the same bootstrap
        return w, w[rng.integers(0, REPS, size=(REPS, 3))].sum(axis=1)

    boot_w, trip = boot(BLOCK, SEED)
    hist_w = pnl.sum(axis=1)
    # deviation D1 (added after the first run): longer blocks, because 7-day blocks cut the
    # season-long persistence of the weather P&L and the historical seasons are fatter-tailed
    sens_blocks = {blk: boot(blk, SEED) for blk in (30, NDAYS)}

    out = dict(seasons_used=kept_years, n_seasons=len(kept_years), C30_check=float(c30),
               weather_pnl_hist={str(y): float(v) for y, v in zip(kept_years, hist_w)},
               deterministic_per_season={c: float(v.sum()) for c, v in per_day.items()}, splits={})
    for rule in ("spec", "margin"):
        for t in T_CUTS:
            prem, rm_st = per_day["prem_st"].sum(), per_day["rm_st"].sum()
            tre, sen, _ = split(prem, rm_st, t, rule)
            det = per_day["rm"].sum() + per_day["hedge_cost"].sum() - tre - sen
            b = (boot_w + det) / J0
            h = (hist_w + det) / J0
            tr = (trip + 3 * det) / J0
            out["splits"][f"{rule}_t{int(t * 100)}"] = dict(
                deterministic_per_season_usd=float(det), treasury_per_season=float(tre), senior_per_season=float(sen),
                boot_median=float(np.median(b)), boot_p05_1in20=float(np.percentile(b, 5)),
                boot_p01=float(np.percentile(b, 1)), boot_min=float(b.min()), boot_share_negative=float((b < 0).mean()),
                boot_share_below_minus100=float((b < -1).mean()),
                hist_median=float(np.median(h)), hist_worst=float(h.min()), hist_worst_season=int(kept_years[int(h.argmin())]),
                three_season_sum_p05=float(np.percentile(tr, 5)),
                rule_1in20_positive_over_3y=bool(np.percentile(tr, 5) > 0),
                junior_income_needed_per_season_for_rule_usd=float(-np.percentile(trip, 5) / 3),
                hist_p05_interp=float(np.percentile(h, 5)),
                sens_block30=dict(median=float(np.median((sens_blocks[30][0] + det) / J0)),
                                  p05_1in20=float(np.percentile((sens_blocks[30][0] + det) / J0, 5)),
                                  three_season_sum_p05=float(np.percentile((sens_blocks[30][1] + 3 * det) / J0, 5))),
                sens_whole_season=dict(median=float(np.median((sens_blocks[NDAYS][0] + det) / J0)),
                                       p05_1in20=float(np.percentile((sens_blocks[NDAYS][0] + det) / J0, 5)),
                                       three_season_sum_p05=float(np.percentile((sens_blocks[NDAYS][1] + 3 * det) / J0, 5)),
                                       junior_income_needed_per_season_for_rule_usd=float(-np.percentile(sens_blocks[NDAYS][1], 5) / 3)))
    return out


def fmt_pct(x):
    return f"{100 * x:+.0f}%"


def write_md(R: dict) -> str:
    J0, S0 = R["capital"]["J0"], R["capital"]["S0"]
    L = ["# Junior return and premium split (EVAL-04 add-on)", "",
         f"Run {R['written_utc']} by `uv run python scripts/eval04_junior.py` (deterministic, seed {SEED}). "
         "Rules frozen in `PREREG-junior.md` at 14:23Z, before any number. All numbers are in `junior_returns.json`.", "",
         "## Method", "",
         f"- Junior capital J0 = ${J0:,.0f} (handoff `junior_ES95_30d_usd`); senior S0 = C_30 − J0 = ${S0:,.0f}.",
         "- The SPEC waterfall on Phase 4's book: station-leg house fills are policies the pool writes (premium in, payout out). "
         "Residual-leg fills and the Kalshi hedge are the house's trades for the pool (§8.6): all their P&L goes to junior, none to senior.",
         "- Premium per $1 scalar unit = the clearing price p* when the house sells cover, 1 − p* when it buys (SPEC writes that as a put with payout UNIT − L(x)). "
         "Risk margin = premium − expected payout at the house's fair value (`mu_s`).",
         "- Treasury = 10 % or 20 % of the station risk margin. Senior = 20 % of (premium − treasury) under SPEC. Junior = the rest, plus residual and hedge P&L, minus payouts.",
         "- Sensitivity B (not SPEC): senior gets 20 % of the kept margin, (1 − t) × risk margin, instead of 20 % of the whole premium.",
         "- Observed seasons: the 2023–2026 Kalshi-era auction simulation (`auction_primary`), and the same with the residual priced off the last five years (`auction_resid_trailing5`).",
         f"- Model-based seasons: Phase 4's capital scenario (both legs, {R['model']['n_seasons']} seasons {R['model']['seasons_used'][0]}–{R['model']['seasons_used'][-1]}, "
         f"C_30 check ${R['model']['C30_check']:,.0f}), weather P&L of the average book at fair value, plus the 2023–26 daily means of margin, hedge cost, "
         "premium and station margin by calendar month. 10,000 seasons from a calendar-aligned joint-date block bootstrap (7-day blocks). "
         "The \"1-in-20 season\" is the 5th percentile of that distribution: a model number, not something we observed.", "",
         "## Observed seasons (junior P&L ÷ J0, uncapped)", "",
         "| rule | 2023 | 2024 | 2025 | 2026 | median | worst | first junior wipe-out (waterfall) |", "|---|---|---|---|---|---|---|---|"]
    for run, O in (("primary", R["observed"]["primary"]), ("resid trailing-5", R["observed"]["resid_trailing5"])):
        for k, v in O.items():
            s = v["by_season"]
            wipes = ", ".join(f"{y}: {x['junior_wiped_on']}" for y, x in s.items() if x["junior_wiped_on"]) or "none"
            L.append(f"| {run}, {k} | " + " | ".join(fmt_pct(s[y]["junior_return"]) for y in (2023, 2024, 2025, 2026))
                     + f" | {fmt_pct(v['median_return'])} | {fmt_pct(v['worst_return'])} | {wipes} |")
    L += ["", "## Model-based seasons (junior P&L ÷ J0)", "",
          "| rule | median | 1-in-20 (p5) | p1 | worst of 10,000 | worst of the historical seasons | 3-season sum, p5 | 1-in-20 positive over 3 years? |",
          "|---|---|---|---|---|---|---|---|"]
    for k, v in R["model"]["splits"].items():
        L.append(f"| {k} | {fmt_pct(v['boot_median'])} | {fmt_pct(v['boot_p05_1in20'])} | {fmt_pct(v['boot_p01'])} | {fmt_pct(v['boot_min'])} | "
                 f"{fmt_pct(v['hist_worst'])} ({v['hist_worst_season']}) | {fmt_pct(v['three_season_sum_p05'])} | {'yes' if v['rule_1in20_positive_over_3y'] else 'no'} |")
    L += ["", "Block-length sensitivity (deviation D1): median / 1-in-20 / 3-season p5.", "",
          "| rule | 7-day blocks (primary) | 30-day blocks | whole seasons (resample the 26) |", "|---|---|---|---|"]
    for k, v in R["model"]["splits"].items():
        a, b = v["sens_block30"], v["sens_whole_season"]
        L.append(f"| {k} | {fmt_pct(v['boot_median'])} / {fmt_pct(v['boot_p05_1in20'])} / {fmt_pct(v['three_season_sum_p05'])} | "
                 f"{fmt_pct(a['median'])} / {fmt_pct(a['p05_1in20'])} / {fmt_pct(a['three_season_sum_p05'])} | "
                 f"{fmt_pct(b['median'])} / {fmt_pct(b['p05_1in20'])} / {fmt_pct(b['three_season_sum_p05'])} |")
    ps = R["premium_split_mean_observed_season"]
    L += ["", "## Premium split, mean observed season (primary run)", "",
          f"Station premium the pool wrote: ${ps['station_premium']:,.0f} a season; risk margin inside it ${ps['station_risk_margin']:,.0f} "
          f"({100 * ps['station_risk_margin'] / ps['station_premium']:.1f} % of premium). The 10 bps notional fee, paid on top, is ${ps['notional_fee_10bps_on_top']:,.0f}.", "",
          "| rule | treasury | senior | junior (before payouts) | senior ÷ S0 |", "|---|---|---|---|---|"]
    for k, v in ps["splits"].items():
        L.append(f"| {k} | ${v['treasury']:,.0f} ({100 * v['treasury'] / ps['station_premium']:.2f} %) | ${v['senior']:,.0f} ({100 * v['senior'] / ps['station_premium']:.2f} %) | "
                 f"${v['junior']:,.0f} ({100 * v['junior'] / ps['station_premium']:.2f} %) | {fmt_pct(v['senior'] / S0)} |")
    L += ["", "## What it says", "", *R["reading"], "", "## Assumptions (with source keys)", ""]
    L += [f"- {a}" for a in R["assumptions"]]
    L += ["", "## Caveats", ""] + [f"- {c}" for c in R["caveats"]]
    L += ["", "## Deviations", ""] + [f"- {c}" for c in R["deviations"]]
    return "\n".join(L) + "\n"


def main() -> None:
    H = json.loads((REPORT / "handoff.json").read_text())
    J0 = H["junior_ES95_30d_usd"]
    S0 = H["C30_usd"] - J0
    obs_p, d_p = observed(pd.read_parquet(CACHE / "auction_primary.parquet"), J0, S0)
    obs_t, _ = observed(pd.read_parquet(CACHE / "auction_resid_trailing5.parquet"), J0, S0)
    model = model_based(d_p, J0)
    yrs = d_p.groupby(d_p["date"].dt.year)
    prem = float(yrs["prem_st"].sum().mean())
    rm = float(yrs["rm_st"].sum().mean())
    splits = {}
    for rule in ("spec", "margin"):
        for t in T_CUTS:
            tre, sen, jp = split(prem, rm, t, rule)
            splits[f"{rule}_t{int(t * 100)}"] = dict(treasury=tre, senior=sen, junior=jp)
    ms = model["splits"]
    R_n = model["n_seasons"]
    ob, ot = obs_p["margin_t10"]["by_season"], obs_t["margin_t10"]["by_season"]
    sp = obs_p["spec_t10"]["by_season"]
    mb = ms["margin_t10"]
    reading = [
        f"- Under SPEC as written, senior's 20 % comes out of the whole premium (${prem:,.0f} a season on the simulated book), while the margin inside that premium is ${rm:,.0f} "
        f"({100 * rm / prem:.1f} %). Senior would collect about ${splits['spec_t10']['senior']:,.0f} a season on ${S0:,.0f} of capital "
        f"({fmt_pct(splits['spec_t10']['senior'] / S0)}), paid by the junior. The junior loses money in all four observed seasons "
        f"({', '.join(fmt_pct(v['junior_return']) for v in sp.values())}) and in {100 * ms['spec_t10']['boot_share_negative']:.0f} % of modelled seasons "
        f"(median {fmt_pct(ms['spec_t10']['boot_median'])}). A day-ahead book priced close to fair can't pay senior a share of gross premium; `seniorPremiumBps` has to apply to margin, or senior needs a different rule.",
        f"- With senior on 20 % of the kept margin (sensitivity B, 10 % cut), the junior's modelled median season is {fmt_pct(mb['boot_median'])}, "
        f"the 1-in-20 season {fmt_pct(mb['boot_p05_1in20'])} (7-day blocks; {fmt_pct(mb['sens_whole_season']['p05_1in20'])} resampling whole seasons), "
        f"and the worst of the {R_n} historical seasons {fmt_pct(mb['hist_worst'])} ({mb['hist_worst_season']}). Below −100 % the junior is gone and senior pays.",
        f"- The 14-RESEARCH test (1-in-20 junior return positive over three seasons) fails under every split: the 3-season p5 is {fmt_pct(mb['three_season_sum_p05'])}. "
        f"Passing it needs about ${mb['junior_income_needed_per_season_for_rule_usd']:,.0f} a season of junior income before weather "
        f"(${mb['sens_whole_season']['junior_income_needed_per_season_for_rule_usd']:,.0f} with whole-season resampling), against ${mb['deterministic_per_season_usd']:,.0f} now: "
        "a much bigger risk load, a smaller book per dollar of junior, or both.",
        f"- Observed 2023–26 under B (10 % cut): {', '.join(fmt_pct(v['junior_return']) for v in ob.values())}; with the residual priced off five years: "
        f"{', '.join(fmt_pct(v['junior_return']) for v in ot.values())}. Three good seasons and one bad one; four seasons is a small sample next to {R_n}.",
        "- The treasury cut barely matters: 10 points of a margin this thin is about $4k a season. The senior rule and the size of the risk load are what matter.",
        "- A season can lose more than the 30-day capital: modelled season weather losses reach $" + f"{-min(model['weather_pnl_hist'].values()):,.0f}" + " (2009) against C_30 of $412k. C_30 is a 30-day number; the halt rules (SPEC C2) are what stop a bad season from running on.",
    ]
    deviations = [
        "D1 (2026-09-30 14:25Z, after the first run at 14:24Z): added 30-day and whole-season block lengths as sensitivities, because 7-day blocks cut the season-long persistence of the weather P&L "
        "and the historical seasons had a fatter left tail than the 7-day bootstrap. The 7-day result stays primary.",
        "D2: added `junior_income_needed_per_season_for_rule_usd` (−p5 of the 3-season weather sum ÷ 3) to say how far the split is from the 14-RESEARCH test.",
    ]
    assumptions = [
        "Premium per scalar unit = p* (house offer) or 1 − p* (house bid); source `data/cache/eval04/auction_primary.parquet` columns `p_star`, `house_bid`, `house_off`; SPEC §6.4 put payout.",
        "Expected payout at the house fair value `mu_s` (same file); risk margin = premium − expected payout.",
        "Residual house fills and the Kalshi hedge are house deployment (§8.6), not policies: no senior share. Counting residual fills as policies would add their premium (about $2.5M a season) to senior's base.",
        "Treasury cut applies to station risk margin only (SPEC §11 `feeMarginBps`; auction fee 0). The 10 bps notional fee is paid by hedgers on top of p*, as in Phase 4's `fees.bps10`.",
        "Junior J0 = handoff `junior_ES95_30d_usd`; senior S0 = handoff `C30_usd` − J0 (the capital stack of the simulated book, not a pilot).",
        "Model-based deterministic terms (margin, hedge cost, premium, station margin) = 2023–26 daily means by calendar month from `auction_primary.parquet`; the premium does not move with the weather in the bootstrap.",
        "Model-based weather P&L = Phase 4's capital matrix (`proxy_bundle` fit 1951–2025 detrended, `average_book`, `unit_matrices`), both legs, seasons with ≤ 5 missing book days; the brief's \"1951–2025\" history is 1999–2025 for the two-leg book (Phase 4 D3).",
        "No collateral yield on idle USDC is counted (14-RESEARCH rule 4 wants it as a separate line; none is assumed).",
    ]
    caveats = [
        "Everything rests on Phase 4's simulated book: 2 % participation, low-confidence sector priors, 5-unit Kalshi hedge.",
        "Returns are over J0 for a whole season and are not floored; below −100 % means the junior is gone and senior paid the rest (the waterfall column shows the date). SPEC C2 would halt new risk at that point, so later days would not happen.",
        "The model-based distribution uses persistence-forecast pricing, which Phase 4's backtest found conservative against Kalshi (M5). It is a model, not a record.",
        "Bootstrap blocks keep all stations on the same date (joint shocks) but break the within-season persistence past 7 days.",
        "The observed primary seasons carry the Central Park residual pricing artefact (Phase 4 D6); the trailing-5 run is the cleaner read.",
    ]
    R = dict(written_utc=dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), prereg="reports/eval-04-05/PREREG-junior.md",
             seed=SEED, capital=dict(J0=J0, S0=S0, source="handoff.json junior_ES95_30d_usd, C30_usd"),
             senior_share=S_SENIOR, treasury_cuts=list(T_CUTS),
             observed=dict(primary=obs_p, resid_trailing5=obs_t), model=model,
             premium_split_mean_observed_season=dict(station_premium=prem, station_risk_margin=rm,
                                                     notional_fee_10bps_on_top=float(0.001 * yrs["polnotional_st"].sum().mean()),
                                                     splits=splits),
             reading=reading, assumptions=assumptions, caveats=caveats, deviations=deviations)
    (REPORT / "junior_returns.json").write_text(json.dumps(R, indent=1, default=float))
    (REPORT / "junior_returns.md").write_text(write_md(R))
    print(write_md(R))


if __name__ == "__main__":
    main()
