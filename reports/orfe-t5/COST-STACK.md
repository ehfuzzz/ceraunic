# ORFE T5 - weather cost stack

Generated 2026-10-01T10:18:27+00:00 by `scripts/orfe_t5_cost_stack.py` (runtime 63.6 s). Local data only; numbers come from the script, the JSON (`COST-STACK.json`) holds every table.

## Verdicts

1. **Hedge cost rule:** FAIL: (b)/(a) <= 1.15 in 13 of 123 cover x city-month rows; pooled all-TMAX ratio 1.887, demo TMAX covers 3.429; rows <= 1.15 by cover: CHI-bakery-heat-K90 2/20, MIA-juice-heat-K93 0/20, NYC-icecream-cold-K75 1/20, REF-call-K2nd-cap6 10/60, CHI-rain-digital 0/3 -> the hedge IS a cost problem; the loss-meter step is not next by this rule
2. **Tail-bucket rule:** TRIGGERED: (b)/(a) >= 1.5 in tail/end buckets for CHI-bakery-heat-K90 (tail 6.767, end 4.115); MIA-juice-heat-K93 (tail 5.962, end 11.474); NYC-icecream-cold-K75 (tail 4.237); REF-call-K2nd-cap6 (tail 2.2)
3. **Variance-at-listing rule:** NOT TRIGGERED: variance resolved at listing (ladder proxy / persistence proxy) NYC 0.877/0.055, MDW 0.899/0.118, MIA 0.559/0.16; over half by both proxies nowhere

Read with rule 3: the ladder proxy alone says most of the day's variance is gone by listing at NYC and MDW; the rule fails only on the persistence proxy, which is a floor on forecast skill (station's own D-2 anomaly). Rule 3 as frozen is not met; see Fidelity limits.

## Pre-registration

Frozen from the T5 brief (2026-10-01) before any number below was produced.

- **Question.** Per demo cover and city-month: where does the premium dollar go, and can the Kalshi ladder hedge the cover at all? Four numbers: (a) burn price from detrended station history; (b) ask-side cost to replicate the payoff from the ladder (superhedge LP over rung asks plus fees, and exact replication where the rungs span the payoff); (c) when the ladder first lists relative to the covered day and how much of the day's TMAX variance is resolved by then; (d) margin left at the engine's quoted premium.
- **Data.** Local only. Covers: CHI bakery heat K=90 (KMDW/KXHIGHCHI), MIA juice heat K=93 (KMIA/KXHIGHMIA), NYC ice-cream cold K=75 (KNYC/KXHIGHNY), all cap 10 F; CHI rain digital (KORD/KXRAIN-CHI); reference cover $1/F, K = second-bracket floor, cap 6, for NYC, MDW, MIA. Ladders: `data/cache/eval04/{rungs,ladders}.parquet` (warm season, 6-rung ladders, 24 h asks), `data/cache/kalshi/candles.parquet` (listing), `data/cache/elasticity/ladder_quotes.parquet` (30/24/12 h), demo snapshot `data/demo/{ladders,rain}.json.gz` (quote-time asks, engine quotes). Burn: `data/cache/eval04/ghcnd_tmax.parquet` through `wi.pool.scenarios.fit_proxy` (35 prior years, warm-season linear trend), 7-day block bootstrap.
- **Decision rule.** (1) (b)/(a) <= 1.15 everywhere -> the hedge is not the problem; next is the loss meter (lens 02 item 7). (2) (b)/(a) >= 1.5 in tail buckets -> stop buying tail buckets; say which covers. (3) Over half of the day's variance resolved before listing by both proxies -> a cover sold a week or more ahead cannot be hedged on the ladder, and the pricer stops pricing it as hedgeable.

## Definitions used

- **Per unit.** Every money column is dollars per $1/F unit per covered day (rain: per $1 wet-day unit).
- **(a) burn.** E[f(T)] with T = round(climatology at the cover year's level + anomaly), anomalies = every detrended warm-month anomaly of the calendar month in the 35 years before the cover year (no look-ahead). `burn` averages over the days the ladder was executable; `burn_month` is the same over every ladder day, with a 90 % interval from a 7-day block bootstrap of the anomaly pool (blocks = 7-day runs inside one year-month). Rain: wet-day frequency (>= 0.01 in) at O'Hare GHCND in a +-7-day window, 1991-2025, not detrended.
- **(b) superhedge.** `scipy.optimize.linprog` per ladder-day: minimise sum (ask_b + 0.07 ask_b (1 - ask_b)) x_b subject to sum_b x_b 1{T in b} >= f(T) for every integer T in the plausible support (that day's climatological sample range +- 5 F), x >= 0. Kalshi rungs partition the integers, so the LP lands on x_b = max f over the bucket; the LP is kept so gaps or overlaps would show. **Exact** = same LP with equality; it exists only when f is constant on every bucket inside the support (column `exact_spanned_share`); `exact` is blank when any day in the month is not spanned. `spec71` = the engine's fixed-quantity rule sum ask_b f(v_b) (SPEC 7.1, no fees) for comparison: it under-hedges inside buckets and in the ends, so it is cheaper than a superhedge. Asks at 24 h before close (last hourly candle, <= 6 h stale is not enforced on eval04 rows); days with any needed rung without an offer are dropped (`exec_days`).
- **ratio** = mean superhedge / mean burn over executable days. `ratio_vs_realised` = mean superhedge / mean realised cover payout on the same days.
- **Where the superhedge dollar goes.** `super_mid` = the same LP portfolio valued at mids without fees (so superhedge - super_mid is spread + fee); `super_clim_payout` = what that portfolio pays on average under the burn climatology (so super_clim_payout - burn is the structural over-hedge: the superhedge must pay the bucket's worst case on every outcome in the bucket); `super_realised_payout` = what it actually paid. super_mid - super_clim_payout is the gap between the ladder's forecast-conditional pricing and climatology, which averages out only over many days.
- **Reference-cover caveat.** The reference strike K (second-bracket floor) moves with the ladder, i.e. with the forecast, so its unconditional climatological burn is not a fair comparator: K is low exactly when T will be low. For the reference cover read `ratio_vs_realised` and the ladder-quality gate; the demo covers have fixed strikes and the climatological burn is the right actuarial price for them.
- **(c) listing lead.** Hours from the ladder's first candle (earliest rung) to close (`lead_close_h`) and to local midnight starting the covered day (`lead_day_h`), medians. **Variance resolved at listing**, two proxies (no forecast archive is on hand): `vr_ladder_listing` = 1 - sum (T - m_list)^2 / sum (T - clim)^2, m_list = mid-weighted mean of the rung values once every rung has quoted; `vr_persistence` = the same with F = clim + phi^2 (anomaly of D-2), the station's own AR(1) persistence forecast at ~38-40 h (D-1's high is not final at listing). Rain uses Brier skill against the wet-day climatology instead.
- **(d) premium.** Engine units are dollars of maximum payout per day (CHI 130 units x 7 days = $910 max), so the engine pays units x clamp(X - K, 0, C) / C; every engine number is divided by units / C to put it on the per-$1/F scale. `premium_parts` = station leg / tail / risk margin / notional fee per $1/F unit-day.
- **(d) premium (cont.).** Engine quote from `wi.api.quoting.build(emit=False)` on a fresh genesis world, one policy per day D quoted at D-1 20:00Z (the world's resting clock; Kalshi has listed D's ladder), house-hedge path; the demo seed week reproduces exactly (CHI $47.85/day, MIA $44.93/day, NYC $11.16/day at the seeded sizes). `superhedge_at_quote` = the LP on the demo ladder at that same quote time. `margin_vs_hedge` = premium - superhedge_at_quote; `margin_vs_burn` = premium - burn. Engine quotes exist only on the demo window 2026-07-16..09-28; other months show blanks.
- **Bucket position.** Rank on the 6-rung ladder: open-ended ends = ranks 0 and 5 (`less`, `greater`); tail = ranks 1 and 4; centre = ranks 2 and 3. Pooled ratio by position = sum of LP cost on those rungs / sum of burn earned on those rungs (burn split by which rung the climatological outcome lands in).

## Per-cover tables

### CHI-bakery-heat-K90

| station | month | days | exec_days | burn | burn_ci90 | exact | exact_spanned_share | superhedge | super_mid | super_clim_payout | super_realised_payout | spec71 | realised_payout | ratio | ratio_vs_realised | lead_close_h | lead_day_h | vr_ladder_listing | vr_persistence | premium | premium_parts | superhedge_at_quote | margin_vs_hedge | margin_vs_burn |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MDW | 2023-05 | 27 | 27 | 0.14 | [0.09, 0.20] |  | 0.00 | 3.48 | 2.79 | 3.74 | 3.15 | 0.00 | 0.04 | 24.94 | 93.86 | 37.00 | 14.00 | 0.87 | 0.04 |  |  |  |  |  |
| MDW | 2023-06 | 22 | 22 | 0.59 | [0.48, 0.75] |  | 0.00 | 3.10 | 2.64 | 5.00 | 2.00 | 0.19 | 0.09 | 5.21 | 34.05 | 37.00 | 14.00 | 0.90 | 0.14 |  |  |  |  |  |
| MDW | 2023-07 | 26 | 26 | 1.01 | [0.83, 1.23] |  | 0.00 | 4.96 | 3.25 | 4.44 | 1.58 | 0.89 | 0.35 | 4.89 | 14.31 | 37.00 | 14.00 | 0.78 | -0.13 |  |  |  |  |  |
| MDW | 2023-08 | 27 | 27 | 0.51 | [0.40, 0.63] |  | 0.00 | 4.48 | 2.73 | 4.40 | 1.11 | 1.46 | 0.70 | 8.77 | 6.37 | 37.00 | 14.00 | 0.84 | -0.07 |  |  |  |  |  |
| MDW | 2023-09 | 22 | 22 | 0.26 | [0.18, 0.37] |  | 0.00 | 2.60 | 1.84 | 4.16 | 0.41 | 0.60 | 0.36 | 9.84 | 7.14 | 37.00 | 14.00 | 0.91 | 0.08 |  |  |  |  |  |
| MDW | 2024-05 | 27 | 27 | 0.15 | [0.10, 0.20] |  | 0.00 | 4.38 | 3.40 | 3.37 | 3.56 | 0.05 | 0.04 | 29.50 | 118.36 | 37.00 | 14.00 | 0.86 | 0.11 |  |  |  |  |  |
| MDW | 2024-06 | 26 | 26 | 0.63 | [0.50, 0.78] |  | 0.00 | 4.72 | 3.82 | 3.73 | 3.81 | 1.73 | 1.15 | 7.45 | 4.09 | 37.00 | 14.00 | 0.81 | 0.09 |  |  |  |  |  |
| MDW | 2024-07 | 31 | 31 | 1.00 | [0.80, 1.21] |  | 0.00 | 2.36 | 1.80 | 4.46 | 0.94 | 0.51 | 0.23 | 2.35 | 10.44 | 37.00 | 14.00 | 0.87 | -0.10 |  |  |  |  |  |
| MDW | 2024-08 | 29 | 29 | 0.52 | [0.39, 0.64] |  | 0.00 | 3.74 | 3.05 | 3.93 | 1.62 | 0.90 | 0.69 | 7.25 | 5.43 | 37.00 | 14.00 | 0.91 | 0.23 |  |  |  |  |  |
| MDW | 2024-09 | 30 | 30 | 0.24 | [0.16, 0.32] |  | 0.00 | 2.74 | 2.01 | 3.09 | 1.70 | 0.15 | 0.17 | 11.60 | 16.42 | 37.00 | 14.00 | 0.93 | 0.15 |  |  |  |  |  |
| MDW | 2025-05 | 31 | 31 | 0.15 | [0.11, 0.21] |  | 0.00 | 1.84 | 1.47 | 5.26 | 2.13 | 0.10 | 0.16 | 11.94 | 11.42 | 38.00 | 14.00 | 0.94 | 0.21 |  |  |  |  |  |
| MDW | 2025-06 | 30 | 30 | 0.66 | [0.51, 0.78] |  | 0.00 | 2.71 | 2.27 | 3.29 | 2.00 | 1.44 | 1.10 | 4.10 | 2.46 | 38.00 | 14.00 | 0.84 | -0.08 |  |  |  |  |  |
| MDW | 2025-07 | 31 | 31 | 1.03 | [0.83, 1.22] |  | 0.00 | 2.03 | 1.65 | 3.14 | 1.10 | 1.33 | 0.97 | 1.98 | 2.10 | 38.00 | 14.00 | 0.93 | -0.15 |  |  |  |  |  |
| MDW | 2025-08 | 31 | 31 | 0.58 | [0.45, 0.72] |  | 0.00 | 1.48 | 1.19 | 4.07 | 0.68 | 0.61 | 0.58 | 2.55 | 2.55 | 38.00 | 14.00 | 0.92 | 0.25 |  |  |  |  |  |
| MDW | 2025-09 | 30 | 30 | 0.28 | [0.21, 0.38] |  | 0.00 | 0.98 | 0.78 | 3.19 | 1.60 | 0.00 | 0.00 | 3.48 |  | 38.00 | 14.00 | 0.91 | 0.39 |  |  |  |  |  |
| MDW | 2026-05 | 31 | 31 | 0.16 | [0.10, 0.21] |  | 0.00 | 0.63 | 0.53 | 3.91 | 0.00 | 0.00 | 0.00 | 3.93 |  | 39.00 | 14.00 | 0.96 | -0.06 |  |  |  |  |  |
| MDW | 2026-06 | 30 | 30 | 0.68 | [0.54, 0.80] |  | 0.00 | 0.74 | 0.63 | 4.42 | 0.30 | 0.40 | 0.27 | 1.09 | 2.77 | 39.00 | 14.00 | 0.92 | 0.29 |  |  |  |  |  |
| MDW | 2026-07 | 31 | 31 | 1.05 | [0.87, 1.28] |  | 0.00 | 1.71 | 1.51 | 3.69 | 1.13 | 1.26 | 0.97 | 1.63 | 1.76 | 39.00 | 14.00 | 0.92 | 0.10 | 1.01 | 0.72/0.08/0.20/0.01 | 1.21 | -0.20 | -0.04 |
| MDW | 2026-08 | 31 | 31 | 0.58 | [0.45, 0.71] |  | 0.00 | 0.39 | 0.32 | 3.95 | 0.07 | 0.03 | 0.03 | 0.67 | 12.15 | 39.00 | 14.00 | 0.83 | 0.18 | 0.35 | 0.05/0.09/0.20/0.01 | 0.37 | -0.01 | -0.23 |
| MDW | 2026-09 | 28 | 28 | 0.31 | [0.22, 0.40] |  | 0.00 | 1.10 | 0.98 | 3.90 | 1.00 | 0.62 | 0.54 | 3.56 | 2.06 | 39.00 | 14.00 | 0.93 | 0.25 | 0.79 | 0.49/0.10/0.20/0.01 | 0.81 | -0.01 | 0.48 |

### MIA-juice-heat-K93

| station | month | days | exec_days | burn | burn_ci90 | exact | exact_spanned_share | superhedge | super_mid | super_clim_payout | super_realised_payout | spec71 | realised_payout | ratio | ratio_vs_realised | lead_close_h | lead_day_h | vr_ladder_listing | vr_persistence | premium | premium_parts | superhedge_at_quote | margin_vs_hedge | margin_vs_burn |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MIA | 2023-05 | 17 | 17 | 0.08 | [0.05, 0.11] |  | 0.00 | 4.62 | 3.38 | 3.35 | 3.94 | 0.00 | 0.00 | 59.88 |  | 37.00 | 13.00 | -1.14 | 0.03 |  |  |  |  |  |
| MIA | 2023-06 | 20 | 20 | 0.17 | [0.12, 0.21] |  | 0.00 | 3.60 | 3.24 | 1.65 | 2.60 | 0.27 | 0.40 | 21.53 | 9.01 | 37.00 | 13.00 | 0.61 | 0.13 |  |  |  |  |  |
| MIA | 2023-07 | 24 | 24 | 0.21 | [0.17, 0.28] |  | 0.00 | 4.19 | 3.23 | 0.81 | 3.62 | 1.46 | 1.62 | 19.48 | 2.58 | 37.00 | 13.00 | 0.70 | 0.29 |  |  |  |  |  |
| MIA | 2023-08 | 20 | 20 | 0.20 | [0.15, 0.24] |  | 0.00 | 3.82 | 2.49 | 0.85 | 1.60 | 1.08 | 0.65 | 19.31 | 5.87 | 37.00 | 13.00 | 0.16 | 0.42 |  |  |  |  |  |
| MIA | 2023-09 | 19 | 19 | 0.07 | [0.05, 0.09] |  | 0.00 | 2.75 | 2.04 | 0.86 | 1.74 | 0.30 | 0.26 | 42.44 | 10.46 | 37.00 | 13.00 | 0.44 | 0.26 |  |  |  |  |  |
| MIA | 2024-05 | 28 | 28 | 0.07 | [0.04, 0.09] |  | 0.00 | 3.37 | 2.48 | 1.42 | 1.43 | 0.64 | 0.46 | 50.62 | 7.26 | 37.00 | 13.00 | 0.89 | 0.31 |  |  |  |  |  |
| MIA | 2024-06 | 24 | 24 | 0.19 | [0.14, 0.23] |  | 0.00 | 2.93 | 2.03 | 2.90 | 0.88 | 0.09 | 0.04 | 15.67 | 70.26 | 37.00 | 13.00 | 0.62 | -0.01 |  |  |  |  |  |
| MIA | 2024-07 | 29 | 29 | 0.29 | [0.23, 0.36] |  | 0.00 | 2.17 | 1.50 | 1.64 | 0.03 | 0.26 | 0.00 | 7.49 |  | 37.00 | 13.00 | 0.29 | -0.36 |  |  |  |  |  |
| MIA | 2024-08 | 31 | 31 | 0.25 | [0.20, 0.30] |  | 0.00 | 2.12 | 1.52 | 2.06 | 0.61 | 0.42 | 0.32 | 8.39 | 6.58 | 37.00 | 13.00 | 0.53 | -0.05 |  |  |  |  |  |
| MIA | 2024-09 | 30 | 30 | 0.07 | [0.06, 0.10] |  | 0.00 | 1.63 | 1.06 | 0.86 | 1.13 | 0.16 | 0.13 | 21.65 | 12.20 | 37.00 | 13.00 | 0.62 | 0.23 |  |  |  |  |  |
| MIA | 2025-05 | 31 | 31 | 0.07 | [0.05, 0.10] |  | 0.00 | 1.17 | 0.96 | 1.90 | 0.68 | 0.04 | 0.07 | 15.58 | 18.12 | 37.00 | 13.00 | 0.75 | 0.24 |  |  |  |  |  |
| MIA | 2025-06 | 27 | 27 | 0.22 | [0.17, 0.29] |  | 0.00 | 0.53 | 0.32 | 2.52 | 0.00 | 0.00 | 0.00 | 2.40 |  | 37.00 | 13.00 | 0.04 | 0.10 |  |  |  |  |  |
| MIA | 2025-07 | 31 | 31 | 0.32 | [0.23, 0.41] |  | 0.00 | 1.36 | 1.11 | 2.97 | 1.06 | 0.12 | 0.10 | 4.31 | 14.11 | 37.00 | 13.00 | 0.10 | 0.21 |  |  |  |  |  |
| MIA | 2025-08 | 31 | 31 | 0.30 | [0.23, 0.35] |  | 0.00 | 1.10 | 0.85 | 1.10 | 1.03 | 0.44 | 0.48 | 3.71 | 2.27 | 37.00 | 13.00 | 0.57 | 0.21 |  |  |  |  |  |
| MIA | 2025-09 | 30 | 30 | 0.09 | [0.07, 0.11] |  | 0.00 | 0.90 | 0.72 | 2.03 | 1.67 | 0.03 | 0.07 | 9.91 | 13.56 | 37.00 | 13.00 | -0.09 | -0.13 |  |  |  |  |  |
| MIA | 2026-05 | 31 | 31 | 0.08 | [0.05, 0.11] |  | 0.00 | 0.78 | 0.67 | 1.14 | 1.81 | 0.05 | 0.19 | 9.80 | 4.03 | 38.00 | 13.00 | 0.74 | 0.12 |  |  |  |  |  |
| MIA | 2026-06 | 30 | 30 | 0.21 | [0.16, 0.27] |  | 0.00 | 0.94 | 0.82 | 1.35 | 1.27 | 0.34 | 0.33 | 4.43 | 2.83 | 38.00 | 13.00 | 0.73 | 0.15 |  |  |  |  |  |
| MIA | 2026-07 | 31 | 31 | 0.32 | [0.25, 0.40] |  | 0.00 | 1.22 | 1.08 | 0.67 | 0.90 | 0.72 | 0.55 | 3.80 | 2.23 | 38.00 | 13.00 | 0.59 | 0.18 | 1.22 | 0.88/0.12/0.20/0.01 | 1.35 | -0.13 | 0.90 |
| MIA | 2026-08 | 31 | 31 | 0.32 | [0.26, 0.39] |  | 0.00 | 1.33 | 1.20 | 0.96 | 0.94 | 0.83 | 0.71 | 4.15 | 1.88 | 38.00 | 13.00 | 0.63 | 0.14 | 1.22 | 0.89/0.12/0.20/0.01 | 1.33 | -0.11 | 0.90 |
| MIA | 2026-09 | 28 | 28 | 0.10 | [0.08, 0.12] |  | 0.00 | 0.60 | 0.52 | 1.27 | 0.04 | 0.04 | 0.00 | 6.08 |  | 38.00 | 13.00 | 0.31 | -0.19 | 0.39 | 0.04/0.13/0.20/0.01 | 0.60 | -0.21 | 0.29 |

### NYC-icecream-cold-K75

| station | month | days | exec_days | burn | burn_ci90 | exact | exact_spanned_share | superhedge | super_mid | super_clim_payout | super_realised_payout | spec71 | realised_payout | ratio | ratio_vs_realised | lead_close_h | lead_day_h | vr_ladder_listing | vr_persistence | premium | premium_parts | superhedge_at_quote | margin_vs_hedge | margin_vs_burn |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NYC | 2023-05 | 22 | 22 | 4.33 | [4.08, 4.61] |  | 0.00 | 5.21 | 4.00 | 5.98 | 3.59 | 4.48 | 3.18 | 1.20 | 1.64 | 37.00 | 13.00 | 0.85 | 0.09 |  |  |  |  |  |
| NYC | 2023-06 | 13 | 13 | 1.16 | [0.99, 1.33] |  | 0.00 | 3.27 | 2.04 | 2.33 | 2.08 | 2.35 | 1.54 | 2.83 | 2.13 | 37.00 | 13.00 | 0.86 | -0.22 |  |  |  |  |  |
| NYC | 2023-07 | 14 | 14 | 0.16 | [0.11, 0.21] |  | 0.00 | 1.57 | 0.99 | 3.42 | 1.43 | 0.00 | 0.00 | 9.68 |  | 37.00 | 13.00 | 0.10 | -0.07 |  |  |  |  |  |
| NYC | 2023-08 | 25 | 25 | 0.23 | [0.17, 0.30] |  | 0.00 | 2.87 | 1.59 | 1.91 | 0.12 | 0.24 | 0.08 | 12.54 | 35.88 | 37.00 | 13.00 | 0.79 | -0.08 |  |  |  |  |  |
| NYC | 2023-09 | 19 | 19 | 1.78 | [1.59, 1.97] |  | 0.00 | 5.46 | 3.74 | 5.42 | 3.05 | 4.79 | 3.00 | 3.07 | 1.82 | 37.00 | 13.00 | 0.96 | 0.35 |  |  |  |  |  |
| NYC | 2024-05 | 30 | 30 | 4.18 | [3.92, 4.45] |  | 0.00 | 7.17 | 4.89 | 6.57 | 4.83 | 5.56 | 3.67 | 1.72 | 1.95 | 37.00 | 13.00 | 0.86 | 0.02 |  |  |  |  |  |
| NYC | 2024-06 | 26 | 26 | 0.99 | [0.83, 1.14] |  | 0.00 | 1.87 | 1.23 | 4.51 | 0.81 | 0.14 | 0.12 | 1.89 | 16.22 | 37.00 | 13.00 | 0.85 | 0.18 |  |  |  |  |  |
| NYC | 2024-07 | 30 | 30 | 0.18 | [0.12, 0.23] |  | 0.00 | 1.44 | 0.77 | 3.33 | 0.00 | 0.00 | 0.00 | 8.17 |  | 37.00 | 13.00 | 0.71 | 0.28 |  |  |  |  |  |
| NYC | 2024-08 | 31 | 31 | 0.24 | [0.19, 0.32] |  | 0.00 | 1.25 | 0.83 | 2.46 | 0.48 | 0.53 | 0.45 | 5.13 | 2.76 | 37.00 | 13.00 | 0.88 | -0.02 |  |  |  |  |  |
| NYC | 2024-09 | 30 | 30 | 1.96 | [1.73, 2.15] |  | 0.00 | 3.44 | 2.43 | 3.10 | 1.87 | 2.77 | 1.73 | 1.75 | 1.99 | 37.00 | 13.00 | 0.80 | 0.05 |  |  |  |  |  |
| NYC | 2025-05 | 31 | 31 | 4.32 | [4.03, 4.60] |  | 0.00 | 6.61 | 5.67 | 5.94 | 5.97 | 5.72 | 5.36 | 1.53 | 1.24 | 37.00 | 13.00 | 0.93 | 0.07 |  |  |  |  |  |
| NYC | 2025-06 | 28 | 28 | 0.91 | [0.77, 1.07] |  | 0.00 | 4.08 | 3.55 | 5.02 | 3.50 | 1.93 | 1.96 | 4.48 | 2.07 | 37.00 | 13.00 | 0.93 | 0.00 |  |  |  |  |  |
| NYC | 2025-07 | 31 | 31 | 0.17 | [0.12, 0.22] |  | 0.00 | 1.21 | 1.00 | 3.80 | 0.32 | 0.00 | 0.00 | 7.20 |  | 37.00 | 13.00 | 0.78 | -0.09 |  |  |  |  |  |
| NYC | 2025-08 | 31 | 31 | 0.23 | [0.17, 0.30] |  | 0.00 | 0.90 | 0.69 | 2.50 | 0.35 | 0.25 | 0.32 | 3.85 | 2.78 | 37.00 | 13.00 | 0.94 | -0.00 |  |  |  |  |  |
| NYC | 2025-09 | 30 | 30 | 1.82 | [1.61, 2.02] |  | 0.00 | 1.98 | 1.70 | 4.12 | 1.03 | 1.09 | 0.87 | 1.08 | 2.28 | 37.00 | 13.00 | 0.92 | 0.03 |  |  |  |  |  |
| NYC | 2026-05 | 31 | 31 | 4.34 | [4.06, 4.59] |  | 0.00 | 6.10 | 5.64 | 6.59 | 5.84 | 5.25 | 4.93 | 1.41 | 1.24 | 38.00 | 13.00 | 0.95 | -0.01 |  |  |  |  |  |
| NYC | 2026-06 | 30 | 30 | 1.02 | [0.86, 1.16] |  | 0.00 | 1.78 | 1.66 | 4.52 | 2.30 | 0.17 | 0.37 | 1.75 | 4.86 | 38.00 | 13.00 | 0.79 | 0.01 |  |  |  |  |  |
| NYC | 2026-07 | 31 | 31 | 0.16 | [0.12, 0.22] |  | 0.00 | 2.96 | 2.81 | 3.41 | 3.55 | 0.06 | 0.39 | 18.45 | 7.65 | 38.00 | 13.00 | 0.86 | 0.12 | 0.34 | 0.00/0.13/0.20/0.01 | 2.36 | -2.01 | 0.18 |
| NYC | 2026-08 | 31 | 31 | 0.23 | [0.16, 0.30] |  | 0.00 | 3.06 | 2.88 | 3.70 | 3.23 | 0.01 | 0.00 | 13.33 |  | 38.00 | 13.00 | 0.46 | 0.08 | 0.35 | 0.02/0.12/0.20/0.01 | 3.02 | -2.67 | 0.12 |
| NYC | 2026-09 | 28 | 28 | 1.66 | [1.45, 1.83] |  | 0.00 | 4.64 | 4.34 | 4.41 | 4.43 | 2.88 | 2.93 | 2.79 | 1.59 | 38.00 | 13.00 | 0.91 | 0.16 | 2.53 | 1.95/0.37/0.20/0.01 | 5.07 | -2.54 | 0.87 |

### REF-call-K2nd-cap6

| station | month | days | exec_days | burn | burn_ci90 | exact | exact_spanned_share | superhedge | super_mid | super_clim_payout | super_realised_payout | spec71 | realised_payout | ratio | ratio_vs_realised | lead_close_h | lead_day_h | vr_ladder_listing | vr_persistence | premium | premium_parts | superhedge_at_quote | margin_vs_hedge | margin_vs_burn |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MDW | 2023-05 | 27 | 27 | 3.25 |  |  | 0.00 | 7.03 | 5.54 | 3.33 | 5.52 | 6.39 | 5.37 | 2.17 | 1.31 | 37.00 | 14.00 | 0.87 | 0.04 |  |  |  |  |  |
| MDW | 2023-06 | 22 | 22 | 3.94 |  |  | 0.00 | 7.08 | 5.58 | 4.04 | 4.86 | 6.36 | 4.73 | 1.80 | 1.50 | 37.00 | 14.00 | 0.90 | 0.14 |  |  |  |  |  |
| MDW | 2023-07 | 26 | 26 | 3.85 |  |  | 0.00 | 8.13 | 5.81 | 3.98 | 4.73 | 7.38 | 4.58 | 2.11 | 1.78 | 37.00 | 14.00 | 0.78 | -0.13 |  |  |  |  |  |
| MDW | 2023-08 | 27 | 27 | 3.77 |  |  | 0.00 | 7.40 | 5.21 | 3.89 | 4.07 | 6.61 | 3.74 | 1.96 | 1.98 | 37.00 | 14.00 | 0.84 | -0.07 |  |  |  |  |  |
| MDW | 2023-09 | 22 | 22 | 3.42 |  |  | 0.00 | 5.92 | 4.69 | 3.51 | 4.50 | 5.26 | 4.27 | 1.73 | 1.39 | 37.00 | 14.00 | 0.91 | 0.08 |  |  |  |  |  |
| MDW | 2024-05 | 27 | 27 | 2.91 |  |  | 0.00 | 7.58 | 5.65 | 3.00 | 5.37 | 6.98 | 5.22 | 2.60 | 1.45 | 37.00 | 14.00 | 0.86 | 0.11 |  |  |  |  |  |
| MDW | 2024-06 | 26 | 26 | 3.01 |  |  | 0.00 | 6.60 | 5.31 | 3.11 | 4.65 | 5.97 | 4.58 | 2.20 | 1.44 | 37.00 | 14.00 | 0.81 | 0.09 |  |  |  |  |  |
| MDW | 2024-07 | 31 | 31 | 3.89 |  |  | 0.00 | 5.78 | 4.68 | 4.02 | 4.36 | 5.13 | 4.07 | 1.48 | 1.42 | 37.00 | 14.00 | 0.87 | -0.10 |  |  |  |  |  |
| MDW | 2024-08 | 29 | 29 | 3.44 |  |  | 0.00 | 6.60 | 5.36 | 3.57 | 4.90 | 6.00 | 4.69 | 1.92 | 1.41 | 37.00 | 14.00 | 0.91 | 0.23 |  |  |  |  |  |
| MDW | 2024-09 | 30 | 30 | 2.83 |  |  | 0.00 | 6.95 | 5.61 | 2.94 | 5.20 | 6.33 | 4.87 | 2.46 | 1.43 | 37.00 | 14.00 | 0.93 | 0.15 |  |  |  |  |  |
| MDW | 2025-05 | 31 | 31 | 4.04 |  |  | 0.00 | 5.13 | 4.27 | 4.11 | 4.45 | 4.54 | 4.32 | 1.27 | 1.19 | 38.00 | 14.00 | 0.94 | 0.21 |  |  |  |  |  |
| MDW | 2025-06 | 30 | 30 | 2.67 |  |  | 0.00 | 4.55 | 3.92 | 2.79 | 3.63 | 3.96 | 3.30 | 1.70 | 1.38 | 38.00 | 14.00 | 0.84 | -0.08 |  |  |  |  |  |
| MDW | 2025-07 | 31 | 31 | 2.67 |  |  | 0.00 | 3.86 | 3.26 | 2.80 | 3.03 | 3.25 | 2.61 | 1.45 | 1.48 | 38.00 | 14.00 | 0.93 | -0.15 |  |  |  |  |  |
| MDW | 2025-08 | 31 | 31 | 3.54 |  |  | 0.00 | 4.36 | 3.83 | 3.67 | 4.00 | 3.75 | 3.71 | 1.23 | 1.18 | 38.00 | 14.00 | 0.92 | 0.25 |  |  |  |  |  |
| MDW | 2025-09 | 30 | 30 | 2.85 |  |  | 0.00 | 4.75 | 4.22 | 2.96 | 4.23 | 4.14 | 3.93 | 1.67 | 1.21 | 38.00 | 14.00 | 0.91 | 0.39 |  |  |  |  |  |
| MDW | 2026-05 | 31 | 31 | 3.29 |  |  | 0.00 | 3.60 | 3.27 | 3.37 | 3.06 | 3.06 | 2.71 | 1.09 | 1.33 | 39.00 | 14.00 | 0.96 | -0.06 |  |  |  |  |  |
| MDW | 2026-06 | 30 | 30 | 3.44 |  |  | 0.00 | 3.26 | 2.96 | 3.54 | 2.63 | 2.69 | 2.33 | 0.95 | 1.40 | 39.00 | 14.00 | 0.92 | 0.29 |  |  |  |  |  |
| MDW | 2026-07 | 31 | 31 | 2.86 |  |  | 0.00 | 3.06 | 2.78 | 2.99 | 2.39 | 2.53 | 1.94 | 1.07 | 1.58 | 39.00 | 14.00 | 0.92 | 0.10 | 3.15 | 3.03/0.00/0.12/0.01 | 3.21 | -0.06 | 0.29 |
| MDW | 2026-08 | 31 | 31 | 3.79 |  |  | 0.00 | 3.78 | 3.48 | 3.94 | 3.68 | 3.19 | 3.16 | 1.00 | 1.19 | 39.00 | 14.00 | 0.83 | 0.18 | 3.31 | 3.19/0.00/0.12/0.01 | 3.41 | -0.09 | -0.48 |
| MDW | 2026-09 | 28 | 28 | 3.28 |  |  | 0.00 | 3.85 | 3.54 | 3.39 | 3.50 | 3.27 | 2.79 | 1.18 | 1.38 | 39.00 | 14.00 | 0.93 | 0.25 | 3.66 | 3.54/0.00/0.12/0.01 | 3.76 | -0.10 | 0.38 |
| MIA | 2023-05 | 17 | 17 | 4.87 |  |  | 0.00 | 8.27 | 5.96 | 5.03 | 5.88 | 7.62 | 5.82 | 1.70 | 1.42 | 37.00 | 13.00 | -1.14 | 0.03 |  |  |  |  |  |
| MIA | 2023-06 | 20 | 20 | 4.12 |  |  | 0.00 | 7.01 | 5.80 | 4.37 | 5.50 | 6.38 | 5.40 | 1.70 | 1.30 | 37.00 | 13.00 | 0.61 | 0.13 |  |  |  |  |  |
| MIA | 2023-07 | 24 | 24 | 3.37 |  |  | 0.00 | 7.37 | 5.72 | 3.69 | 5.46 | 6.74 | 5.42 | 2.19 | 1.36 | 37.00 | 13.00 | 0.70 | 0.29 |  |  |  |  |  |
| MIA | 2023-08 | 20 | 20 | 3.86 |  |  | 0.00 | 8.24 | 6.02 | 4.17 | 5.40 | 7.48 | 5.35 | 2.14 | 1.54 | 37.00 | 13.00 | 0.16 | 0.42 |  |  |  |  |  |
| MIA | 2023-09 | 19 | 19 | 4.14 |  |  | 0.00 | 7.28 | 5.76 | 4.39 | 5.79 | 6.74 | 5.79 | 1.76 | 1.26 | 37.00 | 13.00 | 0.44 | 0.26 |  |  |  |  |  |
| MIA | 2024-05 | 28 | 28 | 3.13 |  |  | 0.00 | 7.76 | 5.96 | 3.37 | 5.39 | 7.18 | 5.29 | 2.48 | 1.47 | 37.00 | 13.00 | 0.89 | 0.31 |  |  |  |  |  |
| MIA | 2024-06 | 24 | 24 | 4.71 |  |  | 0.00 | 7.79 | 5.93 | 4.88 | 5.25 | 7.07 | 5.08 | 1.66 | 1.53 | 37.00 | 13.00 | 0.62 | -0.01 |  |  |  |  |  |
| MIA | 2024-07 | 29 | 29 | 4.75 |  |  | 0.00 | 7.13 | 5.67 | 4.95 | 5.52 | 6.53 | 5.38 | 1.50 | 1.33 | 37.00 | 13.00 | 0.29 | -0.36 |  |  |  |  |  |
| MIA | 2024-08 | 31 | 31 | 4.65 |  |  | 0.00 | 7.38 | 5.89 | 4.85 | 5.29 | 6.78 | 5.07 | 1.59 | 1.46 | 37.00 | 13.00 | 0.53 | -0.05 |  |  |  |  |  |
| MIA | 2024-09 | 30 | 30 | 4.06 |  |  | 0.00 | 7.56 | 6.02 | 4.33 | 5.37 | 6.94 | 5.23 | 1.86 | 1.44 | 37.00 | 13.00 | 0.62 | 0.23 |  |  |  |  |  |
| MIA | 2025-05 | 31 | 31 | 3.98 |  |  | 0.00 | 6.13 | 5.48 | 4.22 | 5.29 | 5.62 | 5.26 | 1.54 | 1.17 | 37.00 | 13.00 | 0.75 | 0.24 |  |  |  |  |  |
| MIA | 2025-06 | 27 | 27 | 4.77 |  |  | 0.00 | 5.59 | 4.96 | 4.95 | 5.11 | 4.97 | 4.89 | 1.17 | 1.14 | 37.00 | 13.00 | 0.04 | 0.10 |  |  |  |  |  |
| MIA | 2025-07 | 31 | 31 | 5.11 |  |  | 0.00 | 5.87 | 5.24 | 5.26 | 5.16 | 5.30 | 5.03 | 1.15 | 1.17 | 37.00 | 13.00 | 0.10 | 0.21 |  |  |  |  |  |
| MIA | 2025-08 | 31 | 31 | 3.97 |  |  | 0.00 | 5.21 | 4.65 | 4.26 | 4.93 | 4.60 | 4.68 | 1.31 | 1.11 | 37.00 | 13.00 | 0.57 | 0.21 |  |  |  |  |  |
| MIA | 2025-09 | 30 | 30 | 4.81 |  |  | 0.00 | 5.57 | 4.91 | 4.98 | 5.20 | 4.96 | 4.93 | 1.16 | 1.13 | 37.00 | 13.00 | -0.09 | -0.13 |  |  |  |  |  |
| MIA | 2026-05 | 31 | 31 | 3.20 |  |  | 0.00 | 5.30 | 4.91 | 3.50 | 4.68 | 4.72 | 4.26 | 1.66 | 1.25 | 38.00 | 13.00 | 0.74 | 0.12 |  |  |  |  |  |
| MIA | 2026-06 | 30 | 30 | 3.33 |  |  | 0.00 | 5.12 | 4.75 | 3.64 | 5.03 | 4.50 | 4.60 | 1.54 | 1.11 | 38.00 | 13.00 | 0.73 | 0.15 |  |  |  |  |  |
| MIA | 2026-07 | 31 | 31 | 3.02 |  |  | 0.00 | 4.98 | 4.62 | 3.40 | 4.68 | 4.35 | 4.32 | 1.65 | 1.15 | 38.00 | 13.00 | 0.59 | 0.18 | 4.87 | 4.75/0.00/0.12/0.01 | 4.96 | -0.09 | 1.85 |
| MIA | 2026-08 | 31 | 31 | 3.68 |  |  | 0.00 | 5.33 | 4.98 | 4.00 | 5.03 | 4.76 | 4.77 | 1.45 | 1.12 | 38.00 | 13.00 | 0.63 | 0.14 | 5.07 | 4.94/0.00/0.12/0.01 | 5.16 | -0.09 | 1.38 |
| MIA | 2026-09 | 28 | 28 | 4.66 |  |  | 0.00 | 5.38 | 5.00 | 4.85 | 5.07 | 4.82 | 4.82 | 1.15 | 1.11 | 38.00 | 13.00 | 0.31 | -0.19 | 5.18 | 5.06/0.00/0.12/0.01 | 5.36 | -0.18 | 0.53 |
| NYC | 2023-05 | 22 | 22 | 3.00 |  |  | 0.00 | 6.11 | 4.84 | 3.10 | 4.27 | 5.43 | 4.00 | 2.04 | 1.53 | 37.00 | 13.00 | 0.85 | 0.09 |  |  |  |  |  |
| NYC | 2023-06 | 13 | 13 | 4.20 |  |  | 0.00 | 7.14 | 5.30 | 4.30 | 4.46 | 6.41 | 4.08 | 1.70 | 1.75 | 37.00 | 13.00 | 0.86 | -0.22 |  |  |  |  |  |
| NYC | 2023-07 | 14 | 14 | 2.87 |  |  | 0.00 | 6.03 | 4.67 | 3.03 | 3.79 | 5.35 | 3.57 | 2.10 | 1.69 | 37.00 | 13.00 | 0.10 | -0.07 |  |  |  |  |  |
| NYC | 2023-08 | 25 | 25 | 3.86 |  |  | 0.00 | 6.74 | 4.77 | 4.01 | 3.76 | 5.97 | 3.32 | 1.75 | 2.03 | 37.00 | 13.00 | 0.79 | -0.08 |  |  |  |  |  |
| NYC | 2023-09 | 19 | 19 | 3.21 |  |  | 0.00 | 6.28 | 4.69 | 3.33 | 4.21 | 5.56 | 3.74 | 1.95 | 1.68 | 37.00 | 13.00 | 0.96 | 0.35 |  |  |  |  |  |
| NYC | 2024-05 | 30 | 30 | 2.82 |  |  | 0.00 | 5.99 | 4.18 | 2.91 | 2.80 | 5.27 | 2.47 | 2.12 | 2.43 | 37.00 | 13.00 | 0.86 | 0.02 |  |  |  |  |  |
| NYC | 2024-06 | 26 | 26 | 2.32 |  |  | 0.00 | 5.94 | 4.28 | 2.46 | 3.19 | 5.22 | 2.88 | 2.55 | 2.06 | 37.00 | 13.00 | 0.85 | 0.18 |  |  |  |  |  |
| NYC | 2024-07 | 30 | 30 | 2.84 |  |  | 0.00 | 5.53 | 4.32 | 3.01 | 4.03 | 4.83 | 3.70 | 1.95 | 1.50 | 37.00 | 13.00 | 0.71 | 0.28 |  |  |  |  |  |
| NYC | 2024-08 | 31 | 31 | 3.59 |  |  | 0.00 | 5.69 | 4.54 | 3.73 | 3.97 | 4.98 | 3.45 | 1.58 | 1.65 | 37.00 | 13.00 | 0.88 | -0.02 |  |  |  |  |  |
| NYC | 2024-09 | 30 | 30 | 3.61 |  |  | 0.00 | 6.37 | 5.00 | 3.77 | 4.33 | 5.63 | 3.90 | 1.76 | 1.63 | 37.00 | 13.00 | 0.80 | 0.05 |  |  |  |  |  |
| NYC | 2025-05 | 31 | 31 | 3.33 |  |  | 0.00 | 3.95 | 3.40 | 3.44 | 2.81 | 3.37 | 2.52 | 1.19 | 1.57 | 37.00 | 13.00 | 0.93 | 0.07 |  |  |  |  |  |
| NYC | 2025-06 | 28 | 28 | 2.52 |  |  | 0.00 | 3.08 | 2.52 | 2.62 | 2.07 | 2.54 | 1.75 | 1.22 | 1.76 | 37.00 | 13.00 | 0.93 | 0.00 |  |  |  |  |  |
| NYC | 2025-07 | 31 | 31 | 2.61 |  |  | 0.00 | 3.88 | 3.31 | 2.77 | 3.16 | 3.24 | 2.90 | 1.49 | 1.33 | 37.00 | 13.00 | 0.78 | -0.09 |  |  |  |  |  |
| NYC | 2025-08 | 31 | 31 | 3.43 |  |  | 0.00 | 3.75 | 3.25 | 3.59 | 3.03 | 3.11 | 2.61 | 1.09 | 1.44 | 37.00 | 13.00 | 0.94 | -0.00 |  |  |  |  |  |
| NYC | 2025-09 | 30 | 30 | 2.65 |  |  | 0.00 | 3.70 | 3.13 | 2.79 | 3.23 | 3.06 | 2.87 | 1.40 | 1.29 | 37.00 | 13.00 | 0.92 | 0.03 |  |  |  |  |  |
| NYC | 2026-05 | 31 | 31 | 2.90 |  |  | 0.00 | 3.34 | 3.03 | 3.00 | 2.68 | 2.82 | 2.26 | 1.15 | 1.48 | 38.00 | 13.00 | 0.95 | -0.01 |  |  |  |  |  |
| NYC | 2026-06 | 30 | 30 | 2.42 |  |  | 0.00 | 3.58 | 3.27 | 2.55 | 2.50 | 3.05 | 2.13 | 1.48 | 1.68 | 38.00 | 13.00 | 0.79 | 0.01 |  |  |  |  |  |
| NYC | 2026-07 | 31 | 31 | 3.10 |  |  | 0.00 | 2.33 | 2.08 | 3.23 | 1.71 | 1.86 | 1.32 | 0.75 | 1.76 | 38.00 | 13.00 | 0.86 | 0.12 | 2.38 | 2.25/0.00/0.12/0.01 | 2.46 | -0.08 | -0.72 |
| NYC | 2026-08 | 31 | 31 | 2.60 |  |  | 0.00 | 2.00 | 1.78 | 2.76 | 1.68 | 1.53 | 1.29 | 0.77 | 1.55 | 38.00 | 13.00 | 0.46 | 0.08 | 1.88 | 1.75/0.00/0.12/0.01 | 1.94 | -0.06 | -0.71 |
| NYC | 2026-09 | 28 | 28 | 3.06 |  |  | 0.00 | 2.29 | 2.06 | 3.19 | 1.61 | 1.80 | 1.18 | 0.75 | 1.95 | 38.00 | 13.00 | 0.91 | 0.16 | 1.99 | 1.87/0.00/0.12/0.01 | 2.06 | -0.06 | -1.06 |

### CHI-rain-digital

| station | month | days | exec_days | burn | burn_ci90 | exact | exact_spanned_share | superhedge | super_mid | super_clim_payout | super_realised_payout | spec71 | realised_payout | ratio | ratio_vs_realised | lead_close_h | lead_day_h | vr_ladder_listing | vr_persistence | premium | premium_parts | superhedge_at_quote | margin_vs_hedge | margin_vs_burn |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ORD | 2026-07 | 12 | 12 | 0.33 |  | 0.56 | 1.00 | 0.56 |  |  |  |  | 0.17 | 1.67 | 3.33 | 43.00 | 19.00 | -0.12 | 0.03 | 0.57 | 0.55/0.00/0.02/0.00 | 0.60 | -0.03 | 0.24 |
| ORD | 2026-08 | 31 | 31 | 0.29 |  | 0.50 | 1.00 | 0.50 |  |  |  |  | 0.32 | 1.70 | 1.55 | 43.00 | 19.00 | 0.26 | -0.01 | 0.46 | 0.44/0.00/0.02/0.00 | 0.45 | 0.01 | 0.17 |
| ORD | 2026-09 | 28 | 28 | 0.28 |  | 0.36 | 1.00 | 0.36 |  |  |  |  | 0.25 | 1.25 | 1.43 | 44.00 | 19.00 | 0.51 | 0.02 | 0.34 | 0.32/0.00/0.02/0.00 | 0.31 | 0.03 | 0.06 |

## Pooled (b)/(a) by bucket position

| cover | centre | tail | end (open-ended) | all | cost share centre / tail / end |
|---|---|---|---|---|---|
| ALL-TMAX-covers | 3.02 | 2.44 | 1.17 | 1.89 | 0.39 / 0.27 / 0.34 |
| DEMO-TMAX-covers | 5.66 | 4.88 | 2.96 | 3.43 | 0.16 / 0.15 / 0.68 |
| CHI-bakery-heat-K90 | 8.35 | 6.77 | 4.12 | 4.57 | 0.12 / 0.10 / 0.78 |
| MIA-juice-heat-K93 | 7.16 | 5.96 | 11.47 | 10.11 | 0.04 / 0.12 / 0.84 |
| NYC-icecream-cold-K75 | 5.00 | 4.24 | 1.47 | 2.19 | 0.26 / 0.22 / 0.52 |
| REF-call-K2nd-cap6 | 2.82 | 2.20 | 0.55 | 1.56 | 0.49 / 0.33 / 0.17 |

Ratio = sum of superhedge cost on the rungs in that position / sum of climatological burn landing in those rungs. An end bucket can carry cost with almost no burn (the superhedge buys the cap there), so its ratio can run far above the others.

## Ladder-quality gate (lens 02 item 6)

| sample | events | all-valid | overround sum(ask)-1 | overround sum(mid)-1 | ref premium | ref payout | ref overround (payout basis) | settle in end bucket | mean err 24 h end: bias / MAE / RMSE (n) | mid-ladder | at listing end | at listing mid |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 1656 | 1656 | 0.316 | 0.112 | 4.79 | 3.81 | 0.260 | 0.138 | 0.54 / 3.26 / 3.52 (229) | 0.05 / 1.13 / 1.47 (1427) | 0.64 / 3.86 / 4.13 (229) | 0.12 / 1.27 / 1.63 (1427) |
| 2023-2024 | 749 | 749 | 0.542 | 0.187 | 6.19 | 4.43 | 0.397 | 0.148 | 2.09 / 3.46 / 3.69 (111) | -0.00 / 1.20 / 1.54 (638) | 2.46 / 4.04 / 4.33 (111) | 0.07 / 1.34 / 1.72 (638) |
| 2025+ | 907 | 907 | 0.129 | 0.049 | 3.65 | 3.29 | 0.108 | 0.130 | -0.92 / 3.07 / 3.35 (118) | 0.10 / 1.08 / 1.40 (789) | -1.06 / 3.68 / 3.93 (118) | 0.16 / 1.22 / 1.55 (789) |

By city-year (sum(ask)-1 / payout-basis overround of the reference cover):

MDW-2023 0.722 / 0.439 (n=124), MDW-2024 0.446 / 0.306 (n=143), MDW-2025 0.184 / 0.116 (n=153), MDW-2026 0.079 / 0.116 (n=151), MIA-2023 0.562 / 0.279 (n=100), MIA-2024 0.513 / 0.348 (n=142), MIA-2025 0.171 / 0.046 (n=150), MIA-2026 0.081 / 0.015 (n=151), NYC-2023 0.557 / 0.546 (n=93), NYC-2024 0.487 / 0.573 (n=147), NYC-2025 0.174 / 0.244 (n=151), NYC-2026 0.087 / 0.301 (n=151)

Horizon check, NY + CHI warm season, `ladder_quotes.parquet` sum(ask)-1: 30h 0.373 (802 events), 24h 0.454 (832 events), 12h 0.571 (923 events)

## Listing and variance resolved (pooled per station)

```
{
 "MDW": {
  "lead_close_h_median": 38.0,
  "lead_close_h_p10_p90": [
   37.0,
   39.0
  ],
  "lead_day_start_h_median": 14.0,
  "vr_ladder_listing": 0.899,
  "vr_ladder_24h": 0.924,
  "vr_ladder_2h": 0.986,
  "vr_persistence": 0.118,
  "phi": 0.604,
  "events": 571,
  "vr_persistence_long_history": 0.138
 },
 "MIA": {
  "lead_close_h_median": 37.0,
  "lead_close_h_p10_p90": [
   37.0,
   38.0
  ],
  "lead_day_start_h_median": 13.0,
  "vr_ladder_listing": 0.559,
  "vr_ladder_24h": 0.633,
  "vr_ladder_2h": 0.938,
  "vr_persistence": 0.16,
  "phi": 0.566,
  "events": 543,
  "vr_persistence_long_history": 0.103
 },
 "NYC": {
  "lead_close_h_median": 37.0,
  "lead_close_h_p10_p90": [
   37.0,
   38.0
  ],
  "lead_day_start_h_median": 13.0,
  "vr_ladder_listing": 0.877,
  "vr_ladder_24h": 0.908,
  "vr_ladder_2h": 0.975,
  "vr_persistence": 0.055,
  "phi": 0.585,
  "events": 542,
  "vr_persistence_long_history": 0.088
 },
 "ORD-rain": {
  "lead_close_h_median": 43.0,
  "lead_day_start_h_median": 19.0,
  "vr_ladder_listing_brier_skill": 0.299,
  "vr_persistence_brier_skill": 0.008,
  "days": 71
 }
}
```

## Sanity checks

- SPEC 7.1 cost of the reference cover vs eval04 `premask_c24`: max abs diff 0.0.
- CLI settlement high falls inside the rung Kalshi settled YES on 0.9994 of events.
- Ladders that partition the support: 1.0.
- Engine quote rows 525, of which no-price 11 (reasons in the JSON `engine_errors`).

## Fidelity limits

- **Best ask only, no depth.** Every ladder cost is the best YES ask of an hourly candle close, with infinite size assumed. Tail and end rungs are where the book is thinnest (EVALUATION.md section 4 one-snapshot depth: max 33-55 units at <= 3c slippage); the superhedge's end-bucket purchases at demo sizes (130-360 units) would walk the book. **Depth-aware tail cost waits for the S3 recorder** (`s3://hlmm-reduced-5325/recorder/tokyo/kalshi-weather-books/`, live since 2026-09-30 07:49Z, no reader in the repo; spec in the appendix).
- **Fees** enter the LP as 0.07 a (1-a) per contract without Kalshi's per-order cent rounding; at demo sizes the rounding is under a cent per order.
- **Forecast variance is a proxy.** There is no forecast archive locally. The ladder proxy measures what the market knew at listing (it includes the NWS forecast the market trades on, and the rung-value convention biases the mean in end buckets); the persistence proxy is only the station's own D-2 anomaly and is a floor on true skill at 38-40 h. Neither is a 7-day forecast; rule 3 is read off the listing time, as the brief states it.
- **Stations.** GHCND TMAX at the Kalshi settlement stations (Central Park, Midway, Miami Intl); Midway before 1997 is O'Hare plus a monthly offset (scenarios.py splice). GHCND vs NWS CLI agree on 99.7-100 % of days (DATA.md). Rain burn uses O'Hare GHCND precip, the KXRAIN-CHI station. Settlement T is eval04 `T_cli` (NWS CLI), not Kalshi's TWC source; the check above shows how often they land in the same rung.
- **Burn model.** Monthly anomaly pools ignore the within-month seasonal slope of the anomaly spread; the trend is a linear warm-season fit over the 35 prior years; rain is not detrended.
- **Engine premium.** Quoted on a fresh genesis world: the tail-charge window and residual history are the snapshot prehistory up to 2026-07-15, not the rolling window a live world would carry by August-September; risk margin and notional fee are the world-file parameters. One-day-ahead quotes (D-1 20:00Z); the seeded demo sold a 7-day window priced off the next day's ladder, which this table does not reproduce beyond the first week.
- **Rain** has only 2026-07-15..09-28 KXRAIN-CHI ladders; there is no longer CHI rain ladder history locally (KXRAINNYC history is NYC).
- **Cross-check numbers from EVALUATION.md:** overround 24.6 % all years, 9.7 % for 2025+, premium 4.73 vs payout 3.79 (liquid NY+CHI+MIA, 2021+ all months, 24 h, executable days). This run's sample is warm-season 2023-08+ six-rung ladders only (eval04 sample), so the gate table's payout-basis overround is comparable in method, not in sample.

## Appendix - recorder reader spec (not built)

What waits for the recorder: depth-aware superhedge cost (walk each rung's YES asks, = 1 - NO bids, to the LP quantity at demo sizes), the tail/end-bucket ratio at size (rule 2 at real size), slippage vs the SPEC 7.2 candle fill, and quote-time book staleness.

Reader `src/wi/data/recorder_books.py` (proposed):
1. Fetch (owner-run, AWS profile `hlmm-launch`): `aws s3 sync s3://hlmm-reduced-5325/recorder/tokyo/kalshi-weather-books/books/date=YYYY-MM-DD/ data/raw/recorder/books/date=YYYY-MM-DD/` plus `settlements/`, `discovery/`, `_status/status.json`; confirm the prefix first (older docs cite the shorter `s3://hlmm-reduced-5325/kalshi-weather-books/`).
2. Parse JSONL.gz rows `{ts, t_req, srv_ts, srv_age_s, ticker, event_ticker, series, close_time, tier, book}`; keep KXHIGHNY/CHI/MIA and KXRAIN-*; assert `book` has the `orderbook_fp` shape (`yes_dollars`, `no_dollars` as [price, qty] lists) that `wi.eval.ladder.book_yes_asks` parses; fail loudly otherwise.
3. Emit per-rung `books: [(ts_unix, [(ask_cents, qty_centi), ...])]` sorted by ts (YES asks from NO bids, ascending) in the shape `wi.engine.hedge.book_at` reads, and a parquet `data/cache/recorder/books.parquet` (ticker, ts, level, ask, qty) partitioned by date. Use the ts the recorder stamps (`ts`), UTC; drop rows with `srv_age_s` above the cadence (60 s within 48 h of close, else 300 s).
4. Point-in-time: a cost at quote time t uses the last snapshot with ts <= t and t - ts <= 120 s; never a later book.
5. Then: rerun this script with the LP's x_b priced by walking levels (convex piecewise-linear cost per rung -> still an LP with one variable per level), report cost per unit at demo sizes and the end/tail ratio with depth. Gate per the repo's plan 17-03: >= 14 days of books before any depth verdict.
