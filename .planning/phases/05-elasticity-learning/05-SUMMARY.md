---
phase: 05-elasticity-learning
plan: 01-04 (single worker run)
status: complete (verdicts mostly FAIL; see below)
prereg_frozen: 2026-09-30T13:22:04Z
results_written: 2026-09-30T14:06:51Z
---
# Phase 5 summary: EVAL-06 elasticity learning

## Verdicts (A3 = empirical-Bayes arm, primary split, daily HE, median [5-95 % day-block CI])
| test | G1 NYC-bike | G2 CHI-bike | G3 CTA | G4 CHI-taxi | G5 NYC-taxi |
|---|---|---|---|---|---|
| T1 signal | FAIL (mu_heat ~0 at K=75; mu_wet -0.105 sig.) | PASS | - | - | - |
| T2 HE_cover heat+rain >= 0.20 | FAIL 0.072 [0.056, 0.091] | FAIL 0.053 [0.026, 0.077] | 0.009 | -0.001 | -0.006 |
| T3 at 24 h asks | FAIL (HE_ladder 0.006, LB < 0; cost 32 %) | FAIL (HE_ladder 0.001, LB < 0) | - | - | - |
| T4 shrinkage | FAIL (gain < 0.02 at n=180) | FAIL (n=120, 180) | FAIL | FAIL | FAIL |
| T5 n* own / EB | 120 / 30; prior alone passes (n* = 0) | 60 / 30; n* = 0 | none | none | none |
| P1 placebo | FAIL by DL mu sig.; HE -0.035 passes | FAIL (mu); HE 0.012 | FAIL (mu); HE -0.004 | FAIL (mu); HE -0.001 | FAIL (mu); HE 0.002 |

Replication (origin 2024-01-01): G1 0.081, G2 0.103, G3 -0.019, G4 -0.001. The oracle (A4, fitted on the hedge year) reaches only 0.115 (G1) and 0.063 (G2). The instruments (heat call above K + wet binary) are the limit, not the estimator. Nearly all bike cover comes from the rain leg.

## What the seat needs to decide
1. **P1 / T1 significance flaw.** The pre-registered DerSimonian-Laird interval treats units as independent, but every unit in a city shares one set of weather days. Placebo means come out "significant" in all groups. A supplementary joint day-block bootstrap (Deviation 8, added after seeing a trial number) puts every placebo mu interval across zero and keeps the real bike wet effects significant. Placebo HE <= 0.02 everywhere. Accept the explanation or not: PREREG says a P1 fail invalidates T2-T5 until explained.
2. **T1 fails for G1** (pre-registered "stop"). The join is fine (wet -10.5 %, G2 significant, G1 2023 heat -0.9 %/degF significant). The capped-linear hinge at K=75 (grid edge) cannot fit Citi Bike's rise-flat-drop temperature shape. All later G1 results are run under that flag.
3. **T4 rule.** By the letter: "own OLS after n*". But A3 > A1 at every n in G1-G4 (LB > 0 in all but one cell). Always-shrink looks better; `priors.json` ships the letter (`own_ols_after_n_star`).
4. **Kill/keep (PREREG §10):** T2 failed for G1 and G2, so portal elasticity is **advisory only** (`advisory_only: true` in priors.json). The decks cannot claim that a learned hedge beats nothing at the 0.20 bar. The 24 h ask keeps < 1/10 of the cover (G1 0.006 of 0.072), so the house-hedge path carries the rest as forecast-level risk (Phase 4/14 input).
5. **Merge:** Phase 2's `src/wi/eval/{ladder,fees}.py` appeared at 13:23Z mid-run. `src/wi/elasticity/ladder_shim.py` now delegates bracket semantics and the scalar fee to them and keeps the 6 h staleness rule (Phase 2 has none) plus the sell-side no-bid rule.

## Files
- reports/eval-06/: PREREG.md, RESULTS.md (pre-reg vs results, 10 deviations), results.json, tables.md, manifest.md, priors.json, figures/{he_by_arm,learning_curve,k_profile_and_temp_bins}.png
- src/wi/data/sales.py (streamed pullers: Citi Bike/Divvy zip-at-a-time, Socrata SoQL group-by, TLC via DuckDB httpfs)
- src/wi/elasticity/: weather.py (CLI + ACIS), panel.py, design.py, fit.py, shrink.py, hedge.py, ladder_shim.py, evaluate.py, portal.py, priors.json (copy)
- scripts/eval05.py (`--all`, `--report-only`); tests/test_elasticity_guards.py (6 pass: look-ahead property, price-time, ladder fixture, fees)
- Cache (gitignored): data/cache/sales_daily/{citibike,divvy_named,cta,chitaxi,tlc}/, panel_G*.parquet, manifest.jsonl; data/cache/elasticity/{weather_daily,ladder_quotes}.parquet

## Data and disk
Streamed 23.7 GB of Citi Bike, 0.9 GB of Divvy, 1.7 GB of TLC (remote column reads), plus the Chicago taxi and CTA server-side aggregates. That is 175 M + 23 M + 99 M + 27 M trips; nothing raw is kept (the sales cache is 40 MB). The disk guard never fired: free space stayed at 4.9 GB or more, 12.6 GB at the end. Units: G1 980, G2 191, G3 140, G4 41, G5 82 eligible (primary).

## Portal
`wi.elasticity.portal.estimate(sales_rows, weather_rows, priors, group=...)` uses numpy + stdlib only. It matches the evaluation's coefficients to <= 1.2e-14 on one real unit per group.

## Deviations (full list in RESULTS.md)
KORD snowfall for Chicago; MDW climatology uses available years (from 1998); Divvy units = station names (ids recoded in 2025); Citi Bike id normalisation; missing precip no longer coded dry (found after trial runs); Phase 2 modules delegation; numpy EB/HAC with DL tau2 truncated at 0; supplementary day-block mu CI; one date with two CHI ladders; portal history-length fix. Trial runs at 100-200 draws were made for G1/G3/G5 before the final run. No threshold, sample rule, arm or metric changed after them.
