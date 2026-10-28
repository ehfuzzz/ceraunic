**Verdict: inconclusive on the owner’s hedging-premium question. No reliable premium is demonstrated at an approximate MDE of 77.6 HDD / 34.9 CDD in the 13-city activity-day sample, with four season clusters per index.** These are settlement marks on days with reported activity, not negotiated block prices. The original three-city fixed-lead activity sample has only one HDD observation at nominal L=7 and none in the other L=7/L=1 cells. It cannot answer what participants paid.

The forecast evidence is mixed. On the original cities, settlements have lower RMSE than archived MOS at L=7 for HDD; MOS has lower RMSE for CDD there and for both indexes at L=1. None of the paired squared-error differences has a season-cluster 95% interval excluding zero. This does not establish incremental forecasting value for Kalshi design 2. That design should remain a research idea on this evidence.

Written 2026-10-24T22:47:29Z. This is a repair of an already reviewed experiment, not a blind new test. The old “trades lean cold” claim is withdrawn.

### What is being measured

Class A requires positive cleared volume, a date from 15 calendar days before delivery-month start through delivery-month end, and a changed settlement versus a previous valid settlement no more than five days earlier. The price remains a settlement proxy. Class B is an in-window mark with no reported positive cleared volume; missing volume is not proof of no activity. Activity with an unchanged mark, out-of-window activity/marks, and snapshot-only days do not enter the scored A/B panels. A mark-only day need not equal Speedwell’s absolute forecast level.

A valid settlement must have the actual flag, have been received on a weekday in Chicago, and be available before that trade date’s local midnight. The preferred final-flag record is selected only among those available by then; otherwise use the latest eligible preliminary record. Reference dates are daily alignment labels; receipt, event, cutoff, and forecast initialization timestamps are retained in UTC. Later reported cleared volume is used only for the ex-post activity label, never as a forecast input.

CME says relevant activity before 15:00 CT determines Tier 1; without trade information, its procedure applies Speedwell’s one-day change. Whole-day cleared volume does not show which transaction set the settlement, and can contain other clearing activity. Neither the activity filter nor a changing mark identifies negotiated block execution prices. [CME settlement method](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457413229/Weather)

### Data and feed audit

Existing Databento statistics and trades were reused. No Databento re-pull, paid call, AWS access, box launch, order, account, or credential action was needed. The interrupted worker had already completed all 52 station-year MOS downloads (about 58 MB). This resumed run downloaded no new market/weather data; numerical dependencies were about 20 MB. Disk remained above the 3 GB floor (9.7–11 GiB free).

The raw-feed audit was written before the final scoring pass. Daily settlement selection is the pre-registered reduction; no eligible daily record was silently thinned. Intrasecond updates/s, size-only updates, book depth, race blocks, and clock/react-to-print baselines do not describe this monthly weather experiment and are not substituted with invented measurements.

| Stream | Raw/eligible evidence | Retention and timing |
| --- | --- | --- |
| CME statistics | 3,244,836 pre-seal records; 480,772 in expired delivery universe | Receipt filtered before downstream analysis |
| CME settlements | 445,516 raw; 349,881 eligible | 100% eligible records kept until final/preliminary daily selection |
| Selected daily marks | 125,916 of 165,557 contract-days | 39,641 snapshot/theoretical-only days excluded; selected-day gap p99 4 days |
| Settlement timing | Reference-to-receipt p50/p99 22.63/66.07 hours | Event-to-receipt p50/p99 1.04/149.01 ms |
| MOS | 44,715 distinct valid-time rows / 2,981 runs per station | 13 station identities checked; 45 duplicate boundary rows removed per station; no conflicts |
| ACIS | 13 stations, existing daily max/min history | Require complete monthly outcome and complete accrued observations |
| Globex executions | 87 prints; 5,375 lots | All match 62 valid settlement days |


There are 117,266 selected daily contract-days without a cleared-volume record. They are labelled “no reported positive volume,” not verified no-trade days. The activity census has 215 A days / 109 contracts / 92,659 cleared lots, 14,806 B days, and 45 in-window positive-volume days excluded for an unchanged or insufficiently recent prior mark. Out-of-window rows are excluded from the scored comparisons. These totals do not establish a block-volume share.

### The actual sample

The valid delivery universe has 492 contracts with complete ACIS outcomes: 230 HDD and 262 CDD. The fixed-lead paired panels retain 229 HDD and 262 CDD contracts; the original three cities retain 69 HDD and 64 CDD. “Four years” is a date span, not four complete seasons. Both indexes supply just four independent season labels, and early coverage is sparse. HDD season is named by its October start year; CDD season is calendar year.

| Index | Season label | Contracts | Cities | Delivery months represented |
| --- | --- | --- | --- | --- |
| CDD | 2023 | 26 | 10 | 5 |
| CDD | 2024 | 68 | 13 | 6 |
| CDD | 2025 | 91 | 13 | 7 |
| CDD | 2026 | 77 | 13 | 6 |
| HDD | 2022 | 25 | 8 | 6 |
| HDD | 2023 | 24 | 8 | 7 |
| HDD | 2024 | 91 | 13 | 7 |
| HDD | 2025 | 90 | 13 | 7 |


The full 13-city seven-month seasons are HDD 2024 (91 contracts) and CDD 2025 (91). HDD 2025 has 90; CDD 2026 has 77 because October 2026 is not expired. Earlier labels are fragments. Sacramento February-2026 HDD and June-2026 CDD are excluded for incomplete ACIS outcomes. No additional rows silently omit missing accrued days.

### Original cities first: archived MOS at L=7 and L=1

Chicago is O’Hare, New York is LaGuardia, and Cincinnati is CVG. Every comparison uses the same contract/date/outcome rows. The table combines A+B valid window settlements; almost every row is B. Errors are settlement minus ACIS outcome, in degree-days. Parentheses are row-weighted season-cluster SEs. Every row has four clusters and is direction only. MDE is the approximate 80%-power planning value for a mean premium, not a bound on executable profit.

| Index | Nominal L | Contracts | Bias (SE) | 95% CI | RMSE settle | RMSE MOS | MOS point sensitivity | MDE DD |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HDD | 7 | 69 | +2.2 (5.2) | [-14.5, +18.9] | 20.4 | 26.2 | 26.3 | 21.8 |
| HDD | 1 | 69 | -0.8 (1.0) | [-3.9, +2.4] | 6.3 | 4.6 | 4.7 | 4.1 |
| CDD | 7 | 64 | +4.7 (1.5) | [-0.0, +9.5] | 17.9 | 15.9 | 15.2 | 6.2 |
| CDD | 1 | 64 | +0.5 (0.7) | [-1.6, +2.6] | 5.5 | 3.9 | 3.7 | 2.7 |


The primary CDD L=7 CI is [-0.0025, +9.4869] before rounding: it includes zero. The registered “prices the outcome” rule is met descriptively for HDD L=7 only; the other three fixed-lead cells are inconclusive. No fixed-lead activity cell establishes the hedging-pressure rule: A has one HDD row at L=7 (actual lead 9, bias +9 DD; one season; SE/MDE unavailable), and zero HDD L=1 / CDD L=7 / CDD L=1 rows.

B-only counts are 68/69 HDD contracts at L=7/L=1 and 64/64 CDD. Their settlement/MOS RMSEs are 20.5/26.4, 6.3/4.6, 17.9/15.9 and 5.5/3.9, respectively. The same descriptive verdict holds. The A+B primary actual-lead distributions are:

| Index / nominal L | Actual lead : contracts |
| --- | --- |
| HDD / 7 | 7: 46, 8: 15, 9: 8 |
| HDD / 1 | 1: 57, 2: 6, 3: 6 |
| CDD / 7 | 7: 48, 8: 7, 9: 9 |
| CDD / 1 | 1: 43, 2: 9, 3: 12 |


All requested MOS days in these fixed-lead panels were found: 483/156 HDD days and 448/161 CDD days at L=7/L=1, with no older-run or climatology fallback inside the seven-day forecast window. After that window the benchmark uses climatology, as registered.

### Secondary 13-city panel

Every row below also has four season clusters. These are predominantly mark-only days, not market execution evidence.

| Index | Nominal L | Contracts | Bias (SE) | RMSE settle | RMSE MOS | MDE DD |
| --- | --- | --- | --- | --- | --- | --- |
| HDD | 7 | 229 | +2.1 (2.2) | 16.3 | 21.1 | 9.1 |
| HDD | 1 | 229 | +0.3 (0.4) | 5.6 | 3.8 | 1.8 |
| CDD | 7 | 262 | +4.1 (1.0) | 15.8 | 13.4 | 4.0 |
| CDD | 1 | 262 | +1.6 (0.7) | 8.5 | 3.7 | 2.9 |


B-only samples contain 227/229 HDD and 261/262 CDD contracts at L=7/L=1. Their RMSE pairs are 16.3/21.2, 5.6/3.8, 15.8/13.5 and 8.5/3.7. Only the HDD L=7 cell meets the descriptive “prices the outcome” rule. The positive pooled CDD L=7 mark bias has an illustrative season CI above zero, but its MOS-bias difference does not meet the registered hedging-pressure rule, and it is a mark panel.

All paired settlement-versus-MOS squared-error CIs include zero. The MDEs for that comparison are in DD squared, not DD: primary HDD L=7/L=1 808/56; primary CDD 368/59; pool HDD 305/44; pool CDD 277/214. With four seasons these estimates are fragile. No forecasting gain is established at those MDEs.

### Secondary activity-day estimates and the withdrawn sentence

These pool all qualifying leads, unlike the original fixed-lead design. The original-city sample has HDD leads 9–44 and CDD 6–43 days; the pool has HDD 8–45 and CDD 2–45. Each row has four season clusters.

| Sample | Index | Days / contracts | Settlement - outcome (SE) | 95% CI | MDE DD | Settlement - trend (SE) |
| --- | --- | --- | --- | --- | --- | --- |
| 3 original cities | HDD | 75 / 34 | +23.9 (24.0) | [-52.5, +100.3] | 99.9 | +4.4 (8.8) |
| 3 original cities | CDD | 22 / 12 | -1.2 (10.7) | [-35.1, +32.7] | 44.3 | +4.2 (6.9) |
| 13 cities | HDD | 141 / 70 | +9.7 (18.6) | [-49.6, +69.0] | 77.6 | +12.3 (6.5) |
| 13 cities | CDD | 74 / 39 | -3.2 (8.4) | [-29.8, +23.5] | 34.9 | -4.9 (2.4) |


The row-weighted 13-city CDD gap versus trend is -4.9 DD, SE 2.4, with an illustrative season-cluster CI [-12.7, +2.8]. The old “lean cold, 3.7 SE” sentence does not survive and is withdrawn. There is no reliable mean settlement-proxy premium at MDE 77.6 HDD / 34.9 CDD on four clusters, not evidence that meaningful conditional premia are absent. The corresponding primary-sample MDEs are 99.9 HDD / 44.3 CDD. At $20/DD the pooled values are about $1,551 / $698 per lot. These are finite-cluster planning approximations; the normal 2.8×SE shortcuts would be 52.2 / 23.5 DD and are not the headline.

The old registered “prices the outcome” inequality happens to hold in the all-lead A aggregates. That algebra does not repair the nearly empty fixed-lead A test or turn settlement proxies into executions.

Globex is separate: 39 HDD days / 27 contracts / three seasons have VWAP-minus-outcome -3.3 DD (SE 7.6, approximate MDE 40.5); 23 CDD days / 17 contracts / three seasons have -1.3 (SE 4.1, MDE 22.2). Whole-day VWAP and the settlement also have different clocks. Settlement differs from VWAP by 2.92 DD in mean absolute value, up to 25 DD. The 5,375 executed lots are actual Globex quantity; the residual from cleared volume is not verified block quantity.

### Final-index repair

All outcomes now use complete ACIS daily max/min months, with daily mean (max+min)/2 and the 65°F HDD/CDD hinge. No post-expiry last-mark fallback is used. The 19 review-flagged extracted “finals” are listed below; every retained row uses the ACIS replacement. Some contracts have no qualifying pre-expiry rows and are excluded entirely. These corrections concern the prior extraction; they do not establish that CME’s official expiry settlements were themselves wrong.

| Contract | Old extracted final | ACIS replacement | Old - ACIS DD |
| --- | --- | --- | --- |
| H002-2024 | 353.0 | 357.0 | -4.0 |
| H111-2023 | 259.0 | 277.5 | -18.5 |
| H302-2024 | 678.0 | 655.5 | 22.5 |
| H412-2024 | 807.5 | 803.0 | 4.5 |
| H502-2024 | 250.0 | 245.5 | 4.5 |
| H702-2024 | 536.0 | 545.5 | -9.5 |
| H711-2023 | 509.0 | 518.0 | -9.0 |
| HQ02-2024 | 913.0 | 918.0 | -5.0 |
| HR02-2024 | 138.0 | 143.5 | -5.5 |
| HS02-2024 | 360.0 | 368.5 | -8.5 |
| HS11-2023 | 285.0 | 291.5 | -6.5 |
| HW02-2024 | 852.0 | 865.0 | -13.0 |
| HW11-2023 | 653.0 | 659.5 | -6.5 |
| K008-2024 | 952.5 | 904.5 | 48.0 |
| K009-2024 | 651.0 | 636.0 | 15.0 |
| K208-2023 | 310.0 | 289.5 | 20.5 |
| K508-2023 | 720.0 | 863.5 | -143.5 |
| KP08-2023 | 364.0 | 376.0 | -12.0 |
| KQ08-2023 | 168.0 | 300.0 | -132.0 |


The audit also discloses all 32 old differences greater than 1 DD, rather than hiding the tail behind an agreement percentage. Thirteen are outside the reviewers’ 19-contract list; some smaller differences may involve revisions or rounding. Official expiry reconciliation for those differences is not established. Using ACIS consistently resolves the outcome definition for this experiment without pretending to have that official-source reconciliation.

### Baseline timing, uncertainty, and limits

Observed DD end at T-1. Both climatologies use only dates before assessment date T. The warming fit uses complete annual observations within the 30-calendar-year window before T’s calendar year, so an early assessment for a January contract cannot use that autumn’s future weather. Burbank has only 13–17 complete years in that window; other cities have 28–30 (Cincinnati 29–30). This shorter history affects the secondary trend comparison.

The archived GFS extended MOS is a valid NWS MOS source allowed by the brief. Day-T max uses the 00Z T run, while day-T morning min uses 12Z T-1; subsequent days use 00Z T. The archive has initialization and forecast-valid times, not a verified historical publication receipt. These early runs provide a buffer before settlement time, but exact availability is not proven. MEX daytime/nighttime extremes can differ from ACIS calendar-day extremes. The Gaussian daily-mean uncertainty (2.5 + 0.5k °F) is an assumed mapping, not a calibrated forecast distribution; the point-value sensitivity is reported above. [NWS MEX definition](https://vlab.noaa.gov/web/mdl/mex-card), [IEM archive](https://mesonet.agron.iastate.edu/mos/)

The settlement can see intraday observations that early-day MOS cannot. A labelled hindsight diagnostic replaces day T’s forecast DD with its eventual observed DD; primary RMSE becomes 25.6/3.8 HDD and 15.2/3.1 CDD at L=7/L=1, versus settlement 20.4/6.3 and 17.9/5.5. This is not a historically available baseline or a cure for the missing intraday information history. Current-vintage ACIS also is not a historical vintage archive. The comparison cannot establish an equal-information-time trading edge.

SE is for the reported row-weighted mean: with N rows and G seasons, SE² = G/(G-1) × Σ_g[Σ_i∈g(x_i−mean)]²/N². Each season’s score respects its actual number of rows. Monthly-cluster SEs are also saved. CI = mean ± t(.975,G−1)SE; approximate MDE = [t(.975,G−1)+t(.80,G−1)]SE. These are planning approximations with very few independent seasons, not an exact-power calculation or a reliable asymptotic significance claim. No z/t test statistic is reported.

### Deviations and verification

The original pre-registration is preserved. The earlier experiment changed three cities to 13, replaced MOS with trend climatology, pooled activity across leads, used a different error sign, and did not apply its declared verdict rule; those results are superseded. This redo tightens activity and snapshot validity, replaces extracted finals with ACIS, moves uncertainty from months to seasons with matching row weights, runs MOS on the original cities first, limits delivery to expired months through September 2026, and omits the paid 2010–22 extension. Fixed-lead settlement lag is limited to two days and actual leads are displayed. Expanded cities, pooled activity-day estimates, trend fits, Gaussian mapping sensitivities, and hindsight day-T observations are secondary. Receipt cutoffs and complete-outcome exclusion are stricter than the original plan; no CME fallback is used.

During the repair, a raw-data audit showed volume often arrives the next day. Before inspecting scored redo results, the initial same-day volume restriction was withdrawn: volume is an ex-post label only. A first pass also stopped on a Burbank history assertion; the complete-year window was clarified before successful output. A subsequent Globex column-name collision was fixed without changing any statistical definition. These failed passes produced no accepted summary. The interrupted worker’s pre-registration timestamp is retained as supplied rather than independently certified. This repair remains informed by both prior reviews and is not a fresh confirmatory test.

Checks passed for future-weather perturbation invariance, failure on missing accrued observations, the weighted cluster sandwich on unequal group sizes, an archived-card MOS date-alignment fixture, all 52 station-year identities, UTC receipt/observation cutoffs, activity eligibility, independently recomputed artifact means/SEs, and input/code hashes. No tests merely assert configuration lists. All computation was laptop CPU. Nothing was staged or committed.

Reproduce with `uv run --no-project --with databento --with pandas --with scipy python .planning/research/cme-first-look/redo.py`. Inspect the [frozen definitions](REDO-PREREG.txt), [raw-feed audit](redo-feed-audit.json), [paired rows](redo-rows.csv), [full statistics and hashes](redo-summary.json), [final-index corrections](redo-final-corrections.csv), [season coverage](redo-season-coverage.csv), and [execution-price sensitivity](redo-globex.csv), and [artifact validation](redo-validation.txt).
