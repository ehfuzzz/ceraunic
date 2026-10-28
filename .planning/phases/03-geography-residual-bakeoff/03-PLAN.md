---
phase: 03-geography-residual-bakeoff
plan: 01-04 (single worker run)
type: execute
depends_on: ["01-03","01-04"]
files_modified: [src/wi/eval03/*, scripts/eval03.py, reports/eval-03/*]
---
<objective>EVAL-02 + EVAL-03 exactly as pre-registered in 03-RESEARCH: geography basis at held-out ASOS stations and grid points; residual designs D0, G1-P, G1-N, G1-P*/N* (continuity), C1-N, R-A, R-P, R-N, R-A-PC, R-N-PC, P-A, P-A-IDW; temperature daily and rain weekly; train 2024 / test 2025-01-01..2026-08-31; verdict + the residual spec for Phase 7.
Output: reports/eval-03/{PREREG.md, results.json, tables.md, figures/, RESULTS.md, residual-spec.md}.</objective>
<context>@AGENTS.md @docs/CONVENTIONS.md @.planning/phases/03-geography-residual-bakeoff/03-RESEARCH.md (Method recommendation, Patterns 1–4, tests that belong, Q5 station tables + networks, the Pre-registration Draft — freeze it VERBATIM with a UTC timestamp as PREREG.md, Code Examples) @.planning/phases/01-data-foundation/01-04-SUMMARY.md (what grid/GHCN data exists and where) 
Data: data/cache/weather/stations_daily.parquet (IEM daily; biased pre-2025-10 at CLI stations — the PREREG data-quality check switches those to CLI), data/cache/weather/official_daily.parquet, data/cache/ghcnd/*.parquet (CLI-consistent nearby stations), data/cache/grid_disc/source={nclimgrid,prism}/, county averages, PRISM .stn.csv. If a nearby station's IEM series fails the 2 % check and it has no CLI, use GHCN-D per 01-RESEARCH Pitfall 2.</context>
<tasks>
<task type="auto"><name>Task 1: PREREG.md + points/align/sources</name><files>reports/eval-03/PREREG.md, src/wi/eval03/{points.py,align.py,sources.py}</files>
<action>Freeze PREREG first. Station registry with roles/networks from Q5; align.py as the only place day conventions live; loaders. Run the pre-evaluation data-quality check (IEM vs CLI mismatch shares; PRISM .stn.csv contamination per truth point) and write it to tables.md BEFORE any HE.</action>
<verify>PREREG timestamp precedes results.json; data-quality table present.</verify><done>Frozen.</done></task>
<task type="auto"><name>Task 2: indexes/designs/metrics + run</name><files>src/wi/eval03/{indexes.py,designs.py,metrics.py,run.py}, scripts/eval03.py</files>
<action>Implement LOO truth, same-source residuals, equal-weight/PC1(frozen on 2024, LOO, clipped)/IDW, county averages, all designs; metrics HE, ΔHE, β, η, sd(r), κ, L; joint circular block bootstrap (14-day, 2,000, seed 20260930); the descriptive EVAL-02 extras (station-leg HE at every land cell both grids aligned; nearest-cell RMSE both alignments); sensitivities listed in PREREG. Tests: only the four in "Tests that belong".</action>
<verify>`uv run python scripts/eval03.py --all` writes results.json with every (market, point, design) row for the 37 temperature and 26 rain pairs.</verify><done>All metrics.</done></task>
<task type="auto"><name>Task 3: verdict + residual-spec.md + RESULTS.md</name><files>reports/eval-03/{RESULTS.md,residual-spec.md}</files>
<action>Apply the pass rule P1–P4 and winner/tie rules verbatim; RESULTS.md with pre-reg vs results, EVAL-02 basis-vs-distance figure, the EWR-via-NYC and TTN-via-NYC cross-market point, caveats; residual-spec.md = the settleable index spec template filled for the winning design(s) (station list, weights, rounding, quorum, fallback, revision cut-off) for Phase 7's index registry. If nothing survives, say so and give the best design's numbers.</action>
<verify>RESULTS.md lists deviations; residual-spec.md present.</verify><done>Verdict delivered.</done></task>
</tasks>
<output>`.planning/phases/03-geography-residual-bakeoff/03-SUMMARY.md` (≤ 60 lines).</output>

<addendum date="2026-09-30 14:30Z">Phase 6's report builder expects the key names in `.planning/phases/06-evaluation-report/06-EVAL03-CONTRACT.md`. Write `reports/eval-03/results.json` to that contract (add keys freely, but every key it names must exist with that meaning), then run `make report` at the end and confirm sections 5–6 and fig8 render without "n/a".</addendum>
