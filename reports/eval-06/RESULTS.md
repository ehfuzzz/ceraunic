# EVAL-06 results: learning a business's weather sensitivity from its daily sales

Pre-registration: `reports/eval-06/PREREG.md`, frozen 2026-09-30T13:22:04Z. Final run: `uv run python scripts/eval05.py --all`, results.json written 2026-09-30T14:06:51Z (220 s, 2,000 bootstrap draws). Detail tables: `tables.md`. Figures: `figures/`. Data manifest: `manifest.md`. Portal prior: `priors.json` (copied to `src/wi/elasticity/priors.json`).

Every number below is a median across units in one group, with a 5-95 % moving-block (7-day) bootstrap interval in brackets. HE = 1 - var(U + hedge P&L) / var(U), where U is revenue minus a climatological-weather forecast made at the origin. Groups are reported separately. There is no pooled headline.

## Verdicts (pre-registered tests)

| test | G1 NYC-bike | G2 CHI-bike | G3 CHI-transit | G4 CHI-taxi | G5 NYC-taxi |
|---|---|---|---|---|---|
| T1 signal (mu_heat and mu_wet nonzero) | **FAIL** (heat) | PASS | - | - | - |
| T2 cover, A3, heat+rain >= 0.20 | **FAIL** 0.072 [0.056, 0.091] | **FAIL** 0.053 [0.026, 0.077] | 0.009 [0.003, 0.018] (no bar) | -0.001 [-0.003, 0.001] (no bar) | -0.006 [-0.016, 0.000] (no bar) |
| T3 at real asks | **FAIL** | **FAIL** | - | - | - |
| T4 shrinkage beats own OLS by >= 0.02 at n = 60-180 | **FAIL** | **FAIL** | **FAIL** | **FAIL** | **FAIL** |
| T5 n* (own / EB) | 120 / 30; sector prior alone passes at every n (n* = 0) | 60 / 30; n* = 0 with prior | none | none | none |
| P1 placebo | **FAIL** (mu significant); HE -0.035 passes | **FAIL** (mu); HE 0.012 passes | **FAIL** (mu); HE -0.004 passes | **FAIL** (mu); HE -0.001 passes | **FAIL** (mu); HE 0.002 passes |

In one line: out of sample, the learned hedge (capped heat call above K plus a wet-day binary) takes 5-10 % out of daily revenue surprise for bikeshare and about nothing for transit and taxi. Bought at real 24 h Kalshi asks, even the bikeshare hedge keeps under a tenth of that. The pre-registered 0.20 bar is missed by a wide margin in both bike groups, in both hedge years.

### T1 signal
- G1: mu_wet = -0.105 (a wet day costs 10.5 % of starts), 95 % CI [-0.107, -0.103]. mu_heat = +0.0002 per degF above K = 75, CI [-0.0001, +0.0006]: **not significant, so T1 fails for G1**. The pre-registered consequence is "stop: the data or weather join is broken". The evidence says the join is not broken. The wet effect is large and precise. G2's heat and wet effects are significant. In the 2023 estimation window (replication split, K = 82) G1's mu_heat is -0.0092, significant under both the DL and the day-block interval. The 5 degF bin diagnostic (figure `k_profile_and_temp_bins.png`) shows why 2024 comes out flat. Citi Bike starts rise to +21 % at 75-79 degF against 60-64 degF, stay flat through 94 degF, and drop only at 95+ (+11 %). The K profile picks K = 75, the edge of the pre-registered grid. One slope above 75 then averages a flat shoulder and a late drop, and nets to zero. The capped-linear heat contract cannot represent that shape. We ran everything after T1 anyway and flag every G1 heat result as conditional on this failure.
- G2: mu_heat = +0.0055 (Divvy riders go out more on hot days, so the business is long heat), mu_wet = -0.191. Both CIs exclude 0. PASS.

### T2 cover quality (policy frame, A3 EB, primary split, daily)
| group | origin | units | K | HE_cover heat+rain | units > 0 | HE_cover heat only (Jun-Sep) | weekly heat+rain | oracle A4 heat+rain |
|---|---|---|---|---|---|---|---|---|
| G1 | 2025-01-01 | 980 | 75 | 0.072 [0.056, 0.091] | 100 % | 0.001 [0.000, 0.002] | 0.026 [0.004, 0.047] | 0.115 |
| G2 | 2025-01-01 | 191 | 75 | 0.053 [0.026, 0.077] | 88 % | 0.009 [-0.008, 0.022] | 0.029 [-0.016, 0.074] | 0.063 |
| G3 | 2025-01-01 | 140 | 80 | 0.009 [0.003, 0.018] | 97 % | 0.020 [0.012, 0.030] | 0.008 | 0.020 |
| G4 | 2025-01-01 | 41 | 84 | -0.001 [-0.003, 0.001] | 39 % | -0.002 | -0.002 | 0.003 |
| G5 | 2024-01-01 | 82 | 75 | -0.006 [-0.016, 0.000] | 12 % | -0.009 | -0.010 | 0.005 |

Replication (origin 2024-01-01, A3 heat+rain): G1 0.081 [0.061, 0.102], G2 0.103 [0.064, 0.139], G3 -0.019 [-0.039, -0.004], G4 -0.001. Same picture: bikes around 0.05-0.10, the rest around zero or below.

**The limit is the instruments, not the estimator.** A4, the oracle fitted on the hedge year itself, reaches only 0.115 (G1) and 0.063 (G2). A heat call above K plus a wet-day binary does not touch most of what moves daily demand. That includes cold-side temperature (the `tlin` slope, unhedged), rain amount (`heavy`, unhedged), lags, and plain noise. Almost all of the bikeshare cover comes from the rain leg. The heat-only summer HE is 0.001 (G1) and 0.009 (G2).

Volume terciles (G1 A3): low 0.055, mid 0.076, high 0.091. G2: 0.039 / 0.061 / 0.068. Busier units hedge better, as expected. A real café is closer to the low tercile, and the binomial-thinning sensitivity (mean 150 starts/day) gives the same 0.072 because the thinning noise is small next to daily weather-unrelated swings.

### T3 at real Kalshi asks (execution frame, 24 h before close, fees, no-offer rule)
- G1 heat+rain: HE_ladder 0.006 [-0.003, 0.014]. Realised cost over the hedge year on buy-side legs (almost all rain) was 32 % of payout (premium incl. fees 17.1 M scaled $ vs payout 13.0 M). **FAIL** on both conditions.
- G2 heat: HE_ladder 0.001 [-0.003, 0.004]. **FAIL**. G2 is long heat, so the hedge sells the ladder. Received 0.86 M, paid out 0.98 M: the seller-side cost was 11 % of payout. The pre-registered cost ratio (C20) is buy-side only, so it is undefined here; the test fails on HE alone.
- Ladder-transferable share (HE_ladder / HE_cover, A3 heat+rain): G1 0.08. The HE_cover - HE_ladder gap, 0.066 for G1, is the forecast-level risk that the 24 h ask already prices. A 24 h Kalshi price is tomorrow's forecast. A hedge bought at that price only moves with the forecast miss, not with the weather level. The research found the same thing on the ins1 rows (0.94 -> 0.53).
- Chicago rain has no daily asks before Sep 2026, so G2-G4 HE_ladder is heat only. NYC rain markets (KXRAINNYC) listed on 355 of 365 days in 2025 and on none in 2024. The G1 replication and G5 hedge windows therefore have no rain leg at asks.

### T4 shrinkage (learning curve, HE_cover heat+rain, pooled over origins)
| group | n = 60 | 90 | 120 | 180 | 365 (A3 vs A1) |
|---|---|---|---|---|---|
| G1 A3 - A1 | +0.039 [0.032, 0.047] | +0.087 | +0.043 | **+0.016** [0.013, 0.021] | 0.089 vs 0.085 |
| G2 A3 - A1 | +0.022 [0.016, 0.030] | +0.034 | **+0.019** | **+0.013** | 0.067 vs 0.060 |
| G3 | +0.006 | +0.014 | +0.022 | +0.009 | 0.001 vs -0.002 |
| G4 | +0.009 | +0.005 | +0.008 | +0.003 | -0.001 vs -0.002 |
| G5 | +0.034 | +0.021 | +0.007 | +0.008 | -0.012 vs -0.014 |

T4 fails everywhere by the letter: the gain falls under 0.02 at n = 180 (G1) and at n = 120-180 (G2), or the share of units with HE < 0 is not lower (G5). But in the bike groups shrinkage never hurt. A3 > A1 at every n in G1-G4, with the lower bound above zero in all but one cell (G3, n = 730). The share of G1 units with a negative HE falls from 23-35 % (own OLS, n <= 120) to under 1 %. G5 is the exception: at n = 270 and 545, A3 is slightly below A1 (-0.006, -0.000), and both are below zero. The pre-registered consequence ("own OLS only after n*") is worse on the bike data than always shrinking. That is a call for the seat.

### T5 days of history
Bikes: own OLS clears the bar from n* = 120 (G1) and 60 (G2). EB clears it from the smallest grid point (30). The sector prior alone (A2) passes at every n, so **"n* = 0 with a sector prior"**. G3-G5 never clear it (median HE_cover <= 0.002 at every n). Figure: `learning_curve.png`.

### P1 placebo (2019 weather on the estimation window, then hedge the real year)
The median placebo HE_cover is at or below 0.02 in every group (-0.035, 0.012, -0.004, -0.001, 0.002), so the controls are not letting seasonality pass for weather sensitivity. **P1 still fails by the letter in every group**, because the placebo group means come out "significant" under the pre-registered DerSimonian-Laird interval (e.g. G1 placebo mu_wet = +0.026 [0.023, 0.029]). That interval treats units as independent. They are not. Every unit in a city shares the same 365 weather days (05-RESEARCH Pitfall 3), so any chance line-up between 2019 weather and 2024 demand shocks moves all units the same way. The supplementary day-block bootstrap of mu (Deviation 8) resamples days jointly across units. Under it, every placebo mu interval includes zero. The real bike wet effects still exclude zero: G1 [-0.150, -0.067], G2 [-0.240, -0.108]. Under PREREG §8, a P1 fail "invalidates T2-T5 until explained". The explanation above is ours. The seat decides whether it is accepted. The same flaw makes T1's pass for G2 and the "significant" DL means in G3-G5 look stronger than they are. G2's heat mean does not survive the day-block interval ([-0.0016, 0.0122]); its wet mean does.

## Sensitivities (primary split, A3, HE_cover heat+rain unless stated)
None of them moves a verdict. G1: cap 6 0.064, levels sizing 0.086, PPML 0.074, thinning to 150/day 0.072, excluding suspension days 0.072, Paule-Mandel 0.072. G1 HE_ladder heat+rain moves from 0.006 at 24 h to 0.007 at 30 h and 0.012 at 12 h. A 20-contract depth cap takes it to 0.002 and raises the cost ratio from 32 % to 35 %. G2 stays at 0.046-0.056 across all of them. G3-G5 stay within +/-0.01 of zero. Full table: `tables.md`.

## Checks recorded in results.json
- numpy HAC standard errors vs statsmodels `OLS(...).fit(cov_type="HAC", maxlags=7)`: max abs diff 6e-15.
- Paule-Mandel vs `combine_effects(method_re="iterated")`: equal. DerSimonian-Laird differs only where statsmodels returns a negative tau2 (-1e-5); ours truncates at 0.
- Holiday function vs pandas `USFederalHolidayCalendar` 2019-2027: identical.
- **Portal parity:** `wi.elasticity.portal.estimate` on one real unit per group, same 365-day window, reproduces the evaluation's own-OLS heat and wet coefficients to <= 1.2e-14.
- Guard tests (`tests/test_elasticity_guards.py`, 6 pass). (1) Corrupting every post-origin sale (x10) and all post-origin weather (+15 degF, all wet) leaves K, the K profile, every fit at n = 60/180/365, the EB priors, the climatology, F and all hedge sizes byte-identical on a synthetic panel. The same corruption before the origin does move the fit, so the test is not vacuous. (2) A candle after the decision time never sets the price; a candle more than 6 h stale gives no price. (3) The ins1 fixture needs 19.5 contracts per $1/degF, and T = 84 falls in "between 84-85", not "less 84". Payout is the winning bracket's contracts, and a missing rung makes the whole day unhedgeable. (4) The vectorised fee equals the shared per-order fee on 2,000 random orders.

## What it means for the portal (PREREG §10)
- **T2 failed for G1 and G2, so the portal shows elasticity as advisory only.** The decks cannot say that a learned hedge beats doing nothing at the pre-registered bar. What they can say, with these caveats: for a weather-heavy business, a wet-day hedge learned from a year of sales took 5-10 % out of daily revenue surprise out of sample, in two cities and two years. Transit and taxi got nothing.
- T3 would decide how much forecast-level risk the house carries. It is moot while T2 fails, but the gap is measured: at 24 h the ask keeps under a tenth of the cover (G1 0.006 of 0.072). For Phase 4/14 this means the default house-hedge path carries essentially all of the cover as forecast-level risk. The Kalshi daily ladder does not lay it off.
- T4 failed, so by the letter the portal uses own OLS only after n* (`priors.json` `portal_mode: own_ols_after_n_star`, `n_star_own` 120 G1 / 60 G2 / null elsewhere). On the bike data always-shrink was never worse and much better at short history. We recommend the seat revisit this rule rather than ship it as written.
- `priors.json` carries per group: K, cap, mu/tau2 for heat and wet, the seasonal offset for histories under 365 days, portal_mode, n_star_own and advisory_only = true. A sector without a stand-in panel gets `learned: false`.

## Caveats
- These are demand proxies, not a shop's revenue: station starts, turnstile entries, pooled taxi fares. Bikeshare is far more weather-driven than a café and flatters the product. Its numbers are an upper bound, not a small-business estimate.
- Eligibility (98 % active through the hedge year) is pre-registered but uses hedge-year activity: units that closed during the hedge year are out. The level-break rule also drops units whose seasonality differs from the group (lakefront and campus Divvy stations).
- One year per split. The hedge days are shared by every unit in a city. The effective sample is about 120 summer days and 59-124 payout days a year, not hundreds of units.
- Candle asks carry no depth. The 20-contract cap sensitivity is the only size check.
- The fee is 0.07 * C * P * (1 - P) in every year (not pinned from Kalshi's PDF).
- K sits at the grid floor (75 degF) in G1, G2 and G5. The capped-linear heat payoff is a poor description of a response that rises and then flattens or falls.

## Deviations

Times are UTC on 2026-09-30. "Before numbers" means before any Phase 5 coefficient or HE existed for the affected group.

- **Deviation 1: Chicago snow control from O'Hare.** What: the `snow` control for Chicago groups uses KORD snowfall (ACIS). Why: KMDW has no snowfall observation in either the CLI or ACIS. When: ~13:25Z, before numbers. The Chicago rain and heat legs still use KMDW.
- **Deviation 2: Midway climatology uses the years it has.** What: E_clim at KMDW averages the available years inside the 30-year window (26-27 years for the 2024-2025 origins; ACIS KMDW daily highs start in late 1997). Why: no older KMDW record in ACIS. When: ~13:25Z, before numbers.
- **Deviation 3: Divvy units are station names.** What: G2 units are start-station names, not ids. Why: Divvy recoded station ids to `CHI#####` in mid-2025, which dropped every station below the 98 % activity rule (max activity 71 %). When: 13:43Z, before any G2 number (the only earlier G2 attempt stopped at eligibility).
- **Deviation 4: Citi Bike id normalisation.** What: ids written with one decimal (`7596.1`) are read as two (`7596.10`); 105 ids affected. Why: the same station appears in both formats across monthly files. When: 13:44Z, before any G1 number.
- **Deviation 5: missing precipitation is missing, not dry.** What: design rows with missing CLI/ACIS precipitation (or missing previous-day precipitation) are dropped from fits; before the fix the `wet >= 0.01` comparison silently coded them dry. Why: found by the portal-vs-evaluation parity check. When: 13:47Z, after 100-200-draw trial runs for G3 and G5 had produced numbers; it affects at most 6 KMDW and 2 KNYC days in 2019-2026 and has no direction.
- **Deviation 6: Phase 2 modules appeared mid-run.** What: `src/wi/eval/ladder.py` and `fees.py` (Phase 2) were written at ~13:23Z, one minute after this PREREG froze C26. The shim now takes bracket semantics and the scalar fee from them (same rule; a test asserts the vectorised fee equals the shared one on 2,000 random orders). The 6 h staleness limit (C15) and the sell-side no-bid rule stay in the shim; Phase 2's `QuoteSeries.at` has no staleness limit. When: ~13:40Z. For the seat to merge.
- **Deviation 7: closed-form EB and HAC instead of calling statsmodels in the loop.** What: DerSimonian-Laird, Paule-Mandel and Newey-West are computed in numpy (the portal needs a numpy-only path). Checked on real data in results.json `checks`: HAC standard errors match statsmodels to ~1e-15; PM matches `combine_effects(method_re="iterated")`; DL matches except that statsmodels' `combine_effects(method_re="chi2")` returns a slightly negative tau2 when Q < k-1, which we truncate at 0 (the textbook estimator). When: build time, before numbers.
- **Deviation 8 (supplementary diagnostic, added after seeing numbers):** a joint day-block bootstrap interval for the group mean mu (`mu_day_block_bootstrap_supplementary`). Why: the pre-registered T1/P1 significance uses the DerSimonian-Laird interval, which treats units as independent; every unit in a city shares the same weather days, so that interval is too narrow (05-RESEARCH Pitfall 3). Added at ~13:34Z after a G3 trial showed a "significant" placebo mu_wet. It does not replace the pre-registered test; both are reported and verdicts use the pre-registered one.
- **Trial runs.** Before the final run, 100-200-draw trial runs were made for G3 (13:33Z, 13:45Z), G5 (13:40Z) and G1 (13:47Z) to shake out code errors. No threshold, sample rule, arm or metric was changed after them. The only code changes after a trial with numbers are Deviation 5 (data handling) and Deviation 8 (supplementary).
- **Deviation 9: two ladders on one date.** What: on 2024-02-28 Kalshi listed two KXHIGHCHI ladders (HIGHCHI-24FEB28 and a relisted HIGHCHI-2-24FEB28). The first full run crashed on the G2-G4 replication split. Fix: use the event quoted at the decision time (most non-missing asks). When: 14:03Z, after the first full run (all other splits had produced numbers; these replication splits had not). It affects one winter day with no heat payout.
- **Deviation 10: portal history length.** What: the portal's model choice uses the calendar span of the sales history (the evaluation's n), not the count of usable rows. Found by the parity check at 13:46Z. Implementation only.
- **Data notes (not deviations):** the bikeshare window ends 2026-06-30 and TLC ends 2024-12-31 (PREREG C4). The old id-keyed Divvy aggregates remain in `data/cache/sales_daily/divvy/` and are unused (G2 reads `divvy_named/`). TLC green 2024-09 answered HEAD with 403, so its file size is unknown in the manifest; the data read succeeded.
