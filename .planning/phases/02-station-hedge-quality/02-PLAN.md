---
phase: 02-station-hedge-quality
plan: 01-03 (single worker run)
type: execute
depends_on: ["01-02","01-03"]
files_modified: [src/wi/eval/hedge.py, src/wi/eval/ladder.py, src/wi/eval/fees.py, scripts/eval02.py, reports/eval-01/*]
---
<objective>
EVAL-01 on the full Kalshi history: how well the liquid station ladders replicate a capped-linear temperature payout (and the daily rain binary / monthly rain ladders) at the settlement station, from real hourly bid/ask, with fees, at 24 h / 12 h / 2 h before close; HE_cover and HE_ladder; overround; spread cost; no-offer share by year; binning RMSE; NWS-vs-TWC mismatch; depth from every recorded book we have. Pre-registered rules first, numbers second.
Output: reports/eval-01/{PREREG.md, results.json, tables.md, figures/, RESULTS.md}.
</objective>
<context>
@AGENTS.md @docs/CONVENTIONS.md @.planning/PROJECT.md
@prior/hl-mm-ins/reports/ins1/README.md and analyze.py (the method to generalise; note the ins1 bottom-bracket off-by-one: "less cap=c" means T ≤ c−1)
@.planning/phases/01-data-foundation/01-RESEARCH.md (Kalshi inventory, Pitfall 5 candle schemas, fee note)
@.planning/phases/05-elasticity-learning/05-RESEARCH.md (Verified Facts table; HE_cover vs HE_ladder; Code Examples "Ladder replication at the 24 h ask, with fees" and "HE with a joint day-block bootstrap")
@.planning/phases/04-netting-pool-economics/04-RESEARCH.md (Pitfall 7 fee formula; baselines table)
Data: data/cache/kalshi/{markets,candles}.parquet, data/cache/weather/official_daily.parquet (CLI values), prior/hl-mm-ins/reports/ins1/books.json (2026-09-29 books), and s3://hlmm-reduced-5325/kalshi-weather-books/ if `aws s3 ls --no-sign-request` or the default profile can list it (read-only; if not reachable, say so and use books.json only).
</context>
<tasks>
<task type="auto"><name>Task 1: PREREG.md (before any number)</name><files>reports/eval-01/PREREG.md</files>
<action>Write and timestamp (UTC) the rules: sample = every settled city-day with a daily high ladder (NY 2021-08→, CHI 2021-08→, MIA 2023-05→, EWR/TTN 2026-08→) and every settled KXRAINNYC / KXRAIN daily binary and monthly rain ladder market; payout H(T;K)=min(max(T−K,0),6) per $1/°F with K = floor of the second bracket (ins1 rule) AND a fixed-strike variant K = trailing-7-day mean of T_S (the Phase 3 rule) to show the tail-outside-ladder share; replication per 07-RESEARCH Pattern 8 (rung midpoints, top floor+1, bottom cap−1); ask at t−24h/12h/2h = last candle ending ≤ t (forward fill), no-offer rule (ask ≥ 99c & bid < 90c), fee = ceil-to-cent(0.07·q·P·(1−P)) per rung order; metrics per city-year and pooled: premium, realised payout, overround, spread cost, fee cost, binning RMSE (payout vs H(T_S) from expiration_value), HE_cover, HE_ladder (both with 7-day block bootstrap, 2,000 draws, seed 20260930), no-offer share, unhedgeable-day share, NWS(CLI)-vs-expiration_value mismatch share, settle_source split; depth: from every recorded book, contracts within 3c of best ask per rung and the implied max units at ≤ 3c slippage; rain: binary at 24 h ask — Brier score, realised cost per $ of payout, HE for a wet-day indicator exposure. Thresholds (priors, frozen now): T1 liquid ladders (NY, CHI, MIA) pooled HE_cover ≥ 0.85 and overround ≤ 20 % at 24 h; T1b HE_ladder reported with no threshold but a stated expectation (ins-derived 0.5 at 24 h); T2 thin ladders fail if overround > 100 %; T3 rain binary: Brier better than climatology by ≥ 0.02; T4 no-offer share ≤ 10 % of city-days per year for liquid ladders in 2024+. Deviations logged with UTC time.</action>
<verify>`head -3 reports/eval-01/PREREG.md` shows the timestamp; git diff shows no results files yet.</verify><done>Rules frozen before Task 2 runs.</done></task>
<task type="auto"><name>Task 2: Engine + run</name><files>src/wi/eval/{ladder.py,hedge.py,fees.py}, scripts/eval02.py</files>
<action>Implement the ladder mapper (any K, C, n; calls and puts; both candle schemas), the ask-at-t forward fill with the historical/live split, the fee function, replication + P&L, HE with block bootstrap; run for all cities × years × horizons; write results.json + tables.md (per city-year, pooled, by settle_source) + figures (HE by year, overround by year, no-offer share, depth histogram). Tests: only (a) a fixture day where the ladder mapper must reproduce the ins1 19.5-contract count and payout for a known T, (b) forward-fill never uses a candle after t (property on a synthetic series), (c) fee rounding. Keep the code importable by Phase 7 (the engine reuses ladder.py and fees.py).</action>
<verify>`uv run python scripts/eval02.py --all` completes; results.json has per-city-year rows; the 2026-07-24..09-29 NYC subset reproduces ins1's premium 1.73 / payout 1.43 within 5 % (state the numbers).</verify><done>All metrics in PREREG produced; ins1 reproduction check reported.</done></task>
<task type="auto"><name>Task 3: RESULTS.md</name><files>reports/eval-01/RESULTS.md</files>
<action>Pre-reg vs result table (T1–T4 pass/fail), the headline numbers by city with CIs, HE_cover vs HE_ladder side by side with the forecast-embedding explanation, the tail-outside-ladder share for fixed strikes, depth summary, caveats (candles sparse; depth only from 2026 books; fee formula MEDIUM), and one paragraph "what this means for the product". Plain words.</action>
<verify>RESULTS.md cites PREREG timestamp and lists deviations (or "none").</verify><done>Report complete.</done></task>
</tasks>
<output>`.planning/phases/02-station-hedge-quality/02-SUMMARY.md` (≤ 60 lines: verdicts, headline numbers, files, deviations).</output>
