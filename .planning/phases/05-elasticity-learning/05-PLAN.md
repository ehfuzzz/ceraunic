---
phase: 05-elasticity-learning
plan: 01-04 (single worker run)
type: execute
depends_on: ["01-02","01-03"]
files_modified: [src/wi/data/sales.py, src/wi/elasticity/*, scripts/eval05.py, reports/eval-06/*, data/cache/sales_daily/*]
---
<objective>EVAL-06: learn weather sensitivity ex ante from stand-in daily demand series near NYC and Chicago, prescribe a Kalshi-ladder (+ rain binary) hedge, evaluate out of sample at real 24 h asks with fees; arms none/own/pooled/EB/oracle; HE_cover and HE_ladder; days-of-history curve; placebo. The estimator ships as the portal's elasticity engine (closed form + priors.json).
Output: reports/eval-06/{PREREG.md, results.json, tables.md, figures/, RESULTS.md, priors.json}, src/wi/elasticity/.</objective>
<context>@AGENTS.md @docs/CONVENTIONS.md @.planning/PROJECT.md
@.planning/phases/05-elasticity-learning/05-RESEARCH.md — implement its Recommended Estimator Spec and freeze its Pre-registration Draft (sections 1–11) as PREREG.md with a UTC timestamp; use its Datasets table (G1 Citi Bike, G2 Divvy, G3 CTA, G4 Chicago Taxi, G5 NYC TLC; Miami none) and Code Examples.
Weather: data/cache/weather/official_daily.parquet (CLI KNYC / KMDW highs + precip; trace = dry). Kalshi asks: data/cache/kalshi/candles.parquet (both schemas; forward-fill rule in CONVENTIONS). Ladder mapper: if Phase 2 has written src/wi/eval/ladder.py and fees.py, import them; otherwise implement the same rule (07-RESEARCH Pattern 8) in src/wi/elasticity/ladder_shim.py and note the duplication for the seat to merge.
DISK IS TIGHT (~6 GB free): pull sales data streaming — Chicago Taxi and CTA via Socrata SoQL server-side aggregation (no raw storage); NYC TLC via DuckDB httpfs remote aggregation of the monthly Parquet (no raw storage); Citi Bike and Divvy one monthly zip at a time → aggregate to station-day counts → delete the zip. Window 2022-07-01..2026-08-31. Check `df -k /` before each download; stop below 3 GB free and report.</context>
<tasks>
<task type="auto"><name>Task 1: PREREG + panels</name><files>reports/eval-06/PREREG.md, src/wi/data/sales.py, data/cache/sales_daily/*.parquet</files>
<action>Freeze PREREG first. Then build unit-day panels for G1–G5 with local-day aggregation (document the DST note), eligibility filters from PREREG §1, joined to CLI weather on the CLI day. Manifest every source (URL, bytes streamed, rows).</action>
<verify>panel row counts per group; unit counts after eligibility; PREREG timestamp precedes any results file.</verify><done>Panels + PREREG.</done></task>
<task type="auto"><name>Task 2: Estimator + evaluation</name><files>src/wi/elasticity/{design.py,fit.py,shrink.py,hedge.py,evaluate.py}, scripts/eval05.py</files>
<action>Per-unit OLS with HAC(7), heat payoff regressor + wet indicator + controls; EB shrinkage (combine_effects, LOO, pre-origin); arms A0–A4; hedge at 24 h asks with fees and no-offer rule (heat) + KXRAINNYC (NYC rain); HE_cover/HE_ladder with joint block bootstrap; learning curve over origins × n; placebo P1; sensitivities as listed. Tests: only look-ahead guards (no post-origin data in any fitted object; property on a synthetic panel) and the ladder-mapping fixture. Export priors.json (sector×city μ, τ², K_g, cap) and a `wi.elasticity.portal.estimate(sales_rows, weather_rows, priors)` function with no pandas dependency at call time beyond numpy (the API will call it).</action>
<verify>`uv run python scripts/eval05.py --all` writes results.json; T1–T5, P1 evaluated.</verify><done>All PREREG metrics.</done></task>
<task type="auto"><name>Task 3: RESULTS.md</name><files>reports/eval-06/RESULTS.md</files>
<action>Pre-reg vs results, by sector (never one pooled headline), HE_cover vs HE_ladder, n* curve, placebo, caveats (demand proxies not revenue; bikeshare flatters), what it means for the portal (kill/keep rules from PREREG §10).</action>
<verify>RESULTS.md complete with deviations.</verify><done>Done.</done></task>
</tasks>
<output>`.planning/phases/05-elasticity-learning/05-SUMMARY.md` (≤ 60 lines).</output>
