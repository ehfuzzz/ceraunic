---
phase: 04-netting-pool-economics
plan: 01-04 (single worker run)
type: execute
depends_on: ["01-02","01-03"]
files_modified: [src/wi/population/*, src/wi/exposure/*, src/wi/auction/clear.py, src/wi/pool/*, src/wi/oracle/revision.py, scripts/eval04.py, reports/eval-04-05/*]
---
<objective>EVAL-04 + EVAL-05 with pre-registered rules: business population by ZIP/NAICS near the five stations, prior exposures → signed hedge units, netting at station-day level (central priors, 1,000-draw ensemble, shrink-to-common null), uniform-price auction on history, pool capital (ES99 on 1951–2025 joint-date weather, floored by worst window, capped at full collateral), junior/senior split, house-MM quotes + markouts on the Kalshi era, revision-risk measurement.
Output: reports/eval-04-05/{PREREG.md, priors_2026-09-30.csv, results.json, tables.md, figures/, RESULTS.md}.</objective>
<context>@AGENTS.md @docs/CONVENTIONS.md @.planning/PROJECT.md
@.planning/phases/04-netting-pool-economics/04-RESEARCH.md — follow its Patterns 1–7, the frozen prior table (copy verbatim into priors_2026-09-30.csv), the capital rule, and Pitfalls 1–14.
@.planning/phases/07-protocol-spec-engine/07-RESEARCH.md Pattern 4 and @.planning/phases/08-solidity-contracts/08-RESEARCH.md Pattern 2: THE CLEARING RULE IS FIXED AS: ticks 1..99 cents on a scalar unit in [0, 1e6]; choose p* to maximise min(D,S), then minimise |D−S|, then the midpoint of the tied range; price-time priority at the marginal tick. Put it in src/wi/auction/clear.py as the ONE function Phase 7 imports (pure integer, no pandas).
Data you pull yourself (small; manifest them): ZBP 2023 detail + totals, CBP county, SUSB 2022 state×NAICS6, 2024 ZCTA gazetteer, GHCN-Daily CSVs for NYC/EWR/TTN/MDW/ORD/MIA and the Phase 3 network stations if 01-04 has not written data/cache/ghcnd yet (check first; reuse if present). Kalshi candles/markets: data/cache/kalshi/. ins1 baselines: prior/hl-mm-ins/reports/ins1/.
Residual index for capital scenarios: the ASOS-network equal-weight metro mean minus station (03-RESEARCH R-A) computed from GHCN-D — no grids needed.</context>
<tasks>
<task type="auto"><name>Task 1: PREREG + priors + population</name><files>reports/eval-04-05/PREREG.md, priors_2026-09-30.csv, src/wi/population/*, src/wi/exposure/*</files>
<action>Freeze PREREG (metrics: netting ratio = matched share of gross signed units per station-day; leftover units; capital per $ of cover for H ∈ {1,5,30}; junior share; fee income under the fee sweep; markout series; revision share; thresholds as priors: M1 netting ratio ≥ 0.25 under central priors for ≥ 3 of 5 stations = "netting is material", M2 under the shrink-to-common null < 0.10 = "the pitch must not lead with netting"; M3 capital per $ of max payout ≤ 0.35 at H=30 for the pooled book = "leverage story holds", else full-collateral story; M4 revision share ≤ 2 % of units for CLI; M5 Kupiec backtest of ES99 on Kalshi-era days not rejected at 5 %). Build the population table (Pattern 1), revenue scale, nearest-station assignment (40 km, nearest only), prior exposure → signed units (Pattern 2) with the complementary-cover note.</action>
<verify>population parquet row count + md5 in the manifest; every prior row matches ≥ 1 ZBP row.</verify><done>PREREG timestamped before any netting number.</done></task>
<task type="auto"><name>Task 2: Netting + auction + capital</name><files>src/wi/auction/clear.py, src/wi/pool/*, scripts/eval04.py</files>
<action>Netting per station-day for the warm seasons in the Kalshi era (central, ensemble, null); auction on history with the house quote schedule (Pattern 5) and fee sweep {0, 10, 25, 50 bps; CoW-style 50 % surplus}; capital via scenario matrix on 1951–2025 (detrended, joint dates, Midway from ORD + offset pre-1997), ES99/worst-window/full-collateral, junior = ES95, H ∈ {1,5,30}; Kupiec backtest; markouts incl. Kalshi paper hedge at candle asks with fees and a 5-unit depth cap; revision measurement from IEM AFOS CLI issuances (corrections) and, if 01-04 wrote vintages, nClimGrid prelim vs scaled.</action>
<verify>`uv run python scripts/eval04.py --all` writes results.json; the clearing function passes a 4,000-random-book property (Σ long fills = Σ short fills, no limit violated, value conserved).</verify><done>All PREREG metrics produced.</done></task>
<task type="auto"><name>Task 3: RESULTS.md + handoff numbers</name><files>reports/eval-04-05/RESULTS.md, reports/eval-04-05/handoff.json</files>
<action>Pre-reg vs results, plain words, caveats (priors LOW confidence; 75 seasons not 11,000 windows; Kalshi depth). handoff.json with: capital per $ cover (H=30), junior share, fee income per $ notional under each fee rule, netting ratios (central/null), worst-window loss, ES99, for Phases 7, 14 and 16.</action>
<verify>handoff.json parses; RESULTS.md lists deviations.</verify><done>Done.</done></task>
</tasks>
<output>`.planning/phases/04-netting-pool-economics/04-SUMMARY.md` (≤ 60 lines).</output>
