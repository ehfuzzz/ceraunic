# EVAL-06 pre-registration (frozen)

**Frozen:** 2026-09-30T13:22:04Z (UTC). No Phase 5 number (panel statistic, coefficient, HE, cost) existed when this file was written. Every results file in reports/eval-06/ is written after this timestamp; results.json records its own write time.

**Source:** sections 1-11 below are copied verbatim from `.planning/phases/05-elasticity-learning/05-RESEARCH.md`, "Pre-registration Draft", with the estimator defined by that file's "Recommended Estimator Spec" and Patterns 1-5. The block after section 11 ("Implementation clarifications") fixes choices the draft leaves open. It was written at the same time, before any number. Any later change is a deviation, logged in RESULTS.md with the time and whether it came before or after seeing numbers.

**Question.** Can a business's weather sensitivity, learned ex ante from its daily sales, prescribe a Kalshi-ladder hedge that reduces out-of-sample revenue variance? Does shrinkage toward a sector prior beat own-history estimates? How many days of history until hedging beats doing nothing?

**1. Data.** Groups G1 NYC-bike (Citi Bike), G2 CHI-bike (Divvy docked), G3 CHI-transit (CTA 'L'), G4 CHI-taxi (community-area Σ fare), G5 NYC-taxi (TLC yellow+green zone Σ fare_amount). Optional G6 NYC-transit (MTA). Weather is the IEM NWS CLI daily high and precipitation at KNYC / KMDW. Kalshi asks come from hourly candles (`/historical/...` before 2026-08-01). Eligibility: unit active on ≥ 98 % of days in [origin − n_max, origin + 365); median ≥ 20/day (bike), ≥ 30 trips/day (taxi) in the estimation window; no detected level break. All eligible units are used and reported by volume tercile. Scale factor, K, priors and climatology all come from pre-origin data only.

**2. Splits.** Primary: origin 2025-01-01, n = 365 (G1–G4); origin 2024-01-01 (G5, congestion-pricing break). Replication: origin 2024-01-01 for G1–G4. Learning curve: origins {2024-07-01, 2025-01-01, 2025-07-01} (G5: {2023-07-01, 2024-01-01}) × n ∈ {30, 60, 90, 120, 180, 270, 365, 545, 730} days immediately before the origin. The hedge window is the 365 days after the origin. Pre-2022-07-01 data is never used.

**3. Estimator.** As in "Recommended Estimator Spec". n ≥ 365: own Fourier(3) + linear trend. 120 ≤ n < 365: group seasonal offset (Fourier(3) coefficients averaged over the group's other units, fit on their pre-origin 365 days) + own level + linear trend. n < 120: group seasonal offset + level, no trend. K_g by group profile SSR over 75–92 °F; cap = 10 °F. HAC(7) SEs.

**4. Arms.** A0 none; A1 own OLS; A2 pooled μ_g (LOO); A3 EB (DL τ², LOO); A4 oracle (bound only).

**5. Hedge.** Heat: `h_t = F_t·(−β_heat)` contracts per bracket weight g(r_b), bought (or sold if h < 0) at the 24 h YES ask (bid), with fees and the no-offer rule. Rain (NYC only at asks): `h^w_t = F_t·(1 − e^{β_wet})` KXRAINNYC YES at the 24 h ask. On days with no KXRAINNYC market listed (the series has gaps), the rain leg is 0 and the day is counted. Chicago rain: policy frame only. Contracts rounded to integers. Primary is uncapped depth; sensitivity caps at 20 contracts per bracket per day.

**6. Metrics.** HE_cover and HE_ladder (Pattern 5), daily and weekly, for the heat-only window (Jun–Sep) and heat+rain (all days). Realised cost per $ of payout. Ladder-transferable share. Unhedgeable-day count. Number of payout days.

**7. Inference.** Moving-block bootstrap over days (L = 7, 2,000 draws, seed 20260930), same indices for all units in a group. The statistic is the median across units. Report 5–95 % intervals.

**8. Tests and thresholds (draft priors; change only before numbers exist):**
- **T1 signal (sanity):** in the primary estimation window, the group priors μ_heat (G1, G2) and μ_wet (G1, G2) are nonzero at 95 %. If this fails, stop: the data or weather join is broken.
- **T2 cover quality (A3, primary split; daily is the test, weekly is reported alongside):** G1 and G2 median HE_cover(heat+rain) ≥ 0.20 with bootstrap LB > 0, and ≥ 70 % of units > 0. Heat-only median HE_cover > 0 with LB > 0. G3–G5 are reported with no threshold.
- **T3 at real asks (A3, G1 NYC heat+rain; G2 heat):** median HE_ladder > 0 with LB > 0, and realised cost over the hedge year (Σ premium + fees − Σ payout) ≤ 25 % of Σ payout.
- **T4 shrinkage (learning curve, pooled over origins):** for n ∈ {60, 90, 120, 180}, A3 − A1 median HE_cover ≥ 0.02 with LB > 0, and A3 has a lower share of units with HE < 0. At n = 365, A3 ≥ A1 − 0.01 (no harm).
- **T5 days of history (descriptive):** n* for A1 and A3 is the smallest grid n from which, for that n and all larger n, the median HE_cover > 0 with LB > 0 and ≥ 60 % of units > 0. If A2 alone passes, report "n* = 0 with a sector prior".
- **P1 placebo:** A3 fit on estimation-window sales with a different year's weather aligned by day of year (2019 weather for a 2024 window; any pre-origin year ≠ window year) gives group μ_heat and μ_wet insignificant at 95 % and a median out-of-sample HE_cover ≤ 0.02. A fail invalidates T2–T5 until explained.

**9. Sensitivities (reported, not tested).** cap 6; levels-model sizing; PPML for count units; binomial thinning to 150/day; decision times 30 h and 12 h; with and without service-suspension days; EB with Paule-Mandel.

**10. Kill / keep.**
- T2 fails for G1 and G2: the portal shows elasticity as advisory only, and the decks cannot say a learned hedge beats nothing.
- T2 passes and T3 fails: daily ladders cannot deliver the cover at asks. The default house-hedge path carries the forecast-level risk; hand the HE_cover − HE_ladder gap to Phase 4 capital.
- T4 fails: the portal uses own-OLS only after n*.
- T4 passes: the portal always shrinks, using priors.json.

**11. Deviations.** Log every change as "Deviation k: what / why / before or after seeing numbers" in reports/eval-06/RESULTS.md.

## 12. Implementation clarifications (fixed at freeze, before any number)

Data and weather
- C1. Weather regressors: NWS official daily high (int degF), precipitation and snowfall at KNYC (NYC groups) and KMDW (Chicago groups). 2023-01-01 onward from the IEM CLI table already cached (`data/cache/weather/official_daily.parquet`, snowfall from the raw CLI CSVs). Before 2023 (estimation windows back to 2022-07-01, placebo weather years, climatology) from NOAA RCC-ACIS `StnData` for the same stations (KNYC = USW00094728, KMDW = USW00014819), which serves the same official values. Agreement on the 2023+ overlap is measured and reported; CLI wins where both exist. Trace ("T") = 0.0 (dry), flagged.
- C2. Climatology E_clim[.] and P_clim(.) for every weather-derived design column (tlin, heat, wet, heavy, snow, lags) = mean over the 30 years before the origin year (years origin_year-30 .. origin_year-1), calendar days within +/-7 days of the day of year. Pre-origin only.
- C3. Local business day: trip timestamps are naive local wall-clock times (Citi Bike, Divvy, TLC, Chicago taxi); the business day is the wall-clock date. Converting to UTC and back gives the same date except in the repeated/skipped DST hour, which does not change the date, so the date is taken directly from the local wall clock (documented, not a deviation). The NWS climate day is local standard time (01:00-00:59 local clock during DST); the one-hour offset against a midnight-to-midnight sales day is accepted.
- C4. Sales windows pulled: 2022-07-01 .. 2026-06-30 for bikeshare (no split uses a later day; the last hedge window ends 2026-06-30), 2022-07-01 .. latest available for the Socrata datasets and 2022-07-01 .. 2024-12-31 for TLC (G5 hedge windows end 2024-12-31).
- C5. Units and measures: G1 Citi Bike start-station-day ride starts (all rideable types, trips with a start station id). G2 Divvy start-station-day ride starts with a non-null start station id. G3 CTA 'L' station-day `rides`. G4 Chicago taxi pickup-community-area-day sum(fare) (trips with a community area; both Socrata datasets stitched at 2024-01-01). G5 NYC TLC yellow+green PULocationID-day sum(fare_amount) over trips with fare_amount > 0 and pickup datetime on the day; zones 264/265 (unknown) excluded. G6 MTA is not built.
- C6. "Active" day = y > 0. Eligibility per split: active on >= 98 % of days in [origin - n_max, origin + 365), where n_max = 365 for the primary and replication splits and n_max = the longest grid n available at that origin (window start >= 2022-07-01) for the learning curve; median >= 20/day for bike, >= 30 trips/day for taxi (G4, G5, via a trip count pulled alongside fare), and >= 100 entries/day for CTA (the draft sets no CTA floor; 100 is fixed here), all measured on the estimation window only (the n_max days before the origin). The trip-count floor for taxi is applied to the daily trip count, not the fare.
- C7. Level-break diagnostic (estimation window only): r_t = log(y_it) - log(sum of y over the group's eligible units on day t); a unit is excluded and logged if |median(r over [t, t+28)) - median(r over [t-28, t))| > log(2) for any t in the estimation window.
- C8. Zero days: dropped from the log-OLS fit (Roth Tran convention), kept in scoring (U_t = y_t - F_t, a real loss).

Estimator
- C9. One design function (`wi.elasticity.design`) builds the regressors for the evaluation and for the portal. Columns: DOW dummies, hol/hol_m1/hol_p1 (US federal holidays + Dec 24, Dec 31, day after Thanksgiving), trend (years since the estimation-window start), Fourier k = 1..3 on day of year (n >= 365), tlin, heat, wet, heavy, wet_l1, heat_l1, snow (CLI snowfall >= 1.0"). A column that is constant in the estimation window is dropped. If heat has fewer than 5 nonzero days (or wet fewer than 5 wet days) in the estimation window, that coefficient is "not identified": A1 uses beta = 0 for it (no hedge on that leg) and s = infinity, so A3 falls back to mu (B = 0).
- C10. n in {545, 730}: same as n = 365 (own Fourier(3) + linear trend). n < 365 group seasonal offset: for unit i, the Fourier(3) coefficients of the other eligible units' n = 365 pre-origin fits are averaged (leave-one-out) and subtracted from ly as an offset.
- C11. K_g: profile SSR over K in {75..92} summed over the group's eligible units on the 365 pre-origin days, one K per group x origin; the same K is used for every n and every arm at that origin. cap = 10.
- C12. Prior (A2, A3): combine_effects over the other units' beta-hat and s at the same n when n >= 365, and over the other units' n = 365 fits when n < 365 (the stored-prior case the portal uses). DerSimonian-Laird ("chi2") primary, Paule-Mandel ("iterated") sensitivity. Heat and wet are shrunk separately.
- C13. Scale factor: one per unit x origin, 1500 / mean(y over the 365 pre-origin days). U, F, h and premiums are in scaled dollars.
- C14. Baseline F_t: the unit's longest-history model at that origin (n = 365 for primary/replication; n_max for the learning curve), trend frozen at its value on the origin date, weather columns at their climatological expectation (C2), Duan smearing factor (mean of exp(residual) in the estimation window). U_t = y_t - F_t is common to all arms and all n at that unit x origin.

Hedge
- C15. Heat leg per day: h_t = F_t * (-beta_heat). For each bracket b of that day's KXHIGHNY / KXHIGHCHI event, q_b = round(h_t * g(r_b)). Buys (q_b > 0) pay the 24 h YES ask; sells (q_b < 0) receive the 24 h YES bid. Price = close of the last hourly candle with end time <= close_time - 24 h and within 6 h of it. Buy-side no-offer: ask missing, stale, ask >= 0.99 with bid < 0.90, or ask <= 0. Sell-side no-bid (mirror, fixed here): bid missing, stale, bid <= 0.01 with ask > 0.10. Any needed bracket failing -> heat leg 0 that day, counted unhedgeable. Fee per bracket order = ceil-to-cent(0.07 * |q| * P * (1 - P)). Ladder payout X_lad = g(r_{b*}) with b* the bracket whose Kalshi `result` is yes (never recomputed from CLI). No event that day -> leg 0, counted.
- C16. Rain leg (NYC groups): h^w_t = F_t * (1 - exp(beta_wet)); q = round(h^w_t) KXRAINNYC YES (buy) or sell at bid if negative; same price, fee and no-offer rules; payout from the market `result`. Chicago groups: rain leg only in the policy frame (HE_cover).
- C17. HE_cover uses X = g(T_CLI) and W = wet_CLI with the same h_t and h^w_t (continuous, not rounded); HE_ladder uses the rounded contracts, asks/bids, fees and Kalshi results. Heat-only window = Jun 1 - Sep 30 of the hedge window, heat leg only. Heat+rain = all hedge-window days, both legs (Chicago: rain leg in HE_cover only; HE_ladder heat only).
- C18. A4 oracle = per-unit OLS (no intercept, demeaned) of U_t on the policy-frame legs over the scored days, the fitted $ ratios used as constant h in both frames. Bound only.
- C19. Weekly HE: U and hedge P&L summed by ISO week (weeks with all 7 days in the window).
- C20. Realised cost for T3: over the hedge year, summed over the group's units (median of unit ratios reported alongside): (sum premium + fees - sum payout) / sum payout, heat leg for G2 and heat+rain legs for G1, buy-side days. Sell-side legs are reported separately.

Inference and tests
- C21. Bootstrap: moving blocks of 7 days over the scored day index, 2,000 draws, numpy default_rng(20260930), the same indices for every unit and arm in a group; statistic = median across units; 5-95 % percentile interval; "LB > 0" means the 5th percentile > 0. For the learning curve pooled over origins, the per-origin bootstrap medians are averaged draw by draw.
- C22. T1: mu_heat and mu_wet from combine_effects over all eligible units (no leave-out) at the primary split; "nonzero at 95 %" = the random-effects 95 % CI excludes 0.
- C23. T4 "A3 has a lower share of units with HE < 0" is checked at each n in {60, 90, 120, 180} pooled over origins. T5 uses HE_cover heat+rain, daily.
- C24. P1 per group at the primary split: estimation-window sales paired with the weather of the year 2019 aligned by month-day (Feb 29 -> Feb 28 weather), K re-profiled on the placebo data, A3 hedge applied to the real hedge year with real weather and the real U. Pass = mu_heat and mu_wet CIs include 0 and median HE_cover (heat+rain, daily) <= 0.02.
- C25. Sensitivities run at the primary split, A1 and A3, reporting the same medians: cap 6; levels-model sizing (OLS of y_scaled in levels, beta read as $ per unit); PPML (GLM Poisson, HAC 7) for G1-G3; binomial thinning to mean 150/day for G1-G3 (seed 20260930); decision time 30 h and 12 h; excluding suspension days (group total < 25 % of the median of the same weekday over the prior 8 weeks); Paule-Mandel; depth cap 20 contracts per bracket per day.
- C26. The fee formula (0.07) is used for all years (Phase 2 has not pinned the schedule). The ladder mapper is `src/wi/elasticity/ladder_shim.py` (Phase 2's `src/wi/eval/ladder.py` does not exist at freeze); the rule is 07-RESEARCH Pattern 8 with the "less cap=c -> c-1" fix.
