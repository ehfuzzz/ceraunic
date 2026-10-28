# Every number in the paper, with its source

Paths are relative to the repository root. `file :: key` means a JSON key; a `.md` file name means the number is in that hand-written results file (which itself cites its JSON key). Where a number in `main.tex` appears more than once, it is listed once, at its first use.

Short names: **e01** = `reports/eval-01/results.json`, **e03** = `reports/eval-03/results.json`, **e45** = `reports/eval-04-05/results.json`, **e45h** = `reports/eval-04-05/handoff.json`, **jr** = `reports/eval-04-05/junior_returns.json` (and `.md`), **rain** = `reports/eval-04-05/rain_book.json` (and `.md`), **e06** = `reports/eval-06/results.json`. "Pooled liquid, A, 24 h" = `temperature.pooled[rule=A,h=24,pool=liquid NY+CHI+MIA]`.

## Numbers checked against the brief

| brief said | repo says | source |
|---|---|---|
| rain residual raised median HE 0.49 → 0.81 | yes: 0.491 → 0.808 (pooled medians on the same 26 pairs) | e03 :: `bakeoff.rain.G1-P.pooled_median_he0_same_pairs`, `.pooled_median_he` |
| +0.229, 95 % CI 0.12–0.32 | yes: 0.229 [0.119, 0.318] | e03 :: `bakeoff.rain.G1-P.pooled_median_dhe`, `.dhe_ci` |
| 25 of 26 pairs (not 26 of 26) | both are true, they count different things: G1-P **runs** on 26 of 26 pairs, and the gain is **positive** on 25 of 26 (share 0.9615). `reports/EVALUATION.md` and `.planning/STATE.md` say "on 26/26"; the paper says "a gain at 25 of 26" | e03 :: `bakeoff.rain.G1-P.n_pairs` = 26, `.share_pairs_dhe_pos` = 0.961538 |
| 7 of 10 pre-registered tests failed | **no source found.** No file in the repo contains a "7 of 10" count. The paper instead lists all 24 yes/no lines (Appendix A): 8 pass, 15 fail or fire the adverse branch, 1 split. Counting only the 6 hedge-question tests (station T1-T4, heat residual, rain residual) gives 4 fails of 6 | ledger rows below |
| temperature version failed | yes: no temperature residual survives | e03 :: `verdicts.winner.temperature` = none |
| Kalshi hedge markup ~24.6 % vs a 20 % bar | yes: 24.6 % [21.4, 27.9], fees excluded; 29.7 % with fees | e01 :: pooled liquid, A, 24 h `.overround`; bar in `reports/eval-01/PREREG.md` §7 T1 |

## Abstract and introduction

| number | source |
|---|---|
| HE_cover 0.95 [0.95, 0.96] | e01 :: pooled liquid, A, 24 h `.he_cover` |
| 4,462 city-days | e01 :: pooled liquid, A, 24 h `.n_citydays` |
| markup 24.6 % [21.4 %, 27.9 %] | e01 :: pooled liquid, A, 24 h `.overround` |
| 20 % limit | `reports/eval-01/PREREG.md` §7 T1 |
| HE_ladder −0.32 [−0.47, −0.20] | e01 :: pooled liquid, A, 24 h `.he_ladder` |
| HE_ladder 0.37 (2025+, post hoc) | e01 :: `temperature.pooled[rule=A,h=24,pool=liquid 2025+ (post-hoc)].he_ladder.est` |
| station leg alone 0.81 (heat), 0.49 (weekly rain) | e03 :: `eval02.temperature.pooled_median_he0`, `eval02.rain.pooled_median_he0` |
| 50 km | `reports/eval-03/PREREG.md` (Stations: inclusion rule) |
| rain residual 0.81, +0.229 [0.119, 0.318], 25 of 26 | see table above |

## Section 3 (setting)

| number | source |
|---|---|
| cap 6 °F | e01 :: `meta.cap`; `reports/eval-01/PREREG.md` §3 |
| 0.01 in wet threshold | `reports/eval-01/PREREG.md` §6; `reports/eval-03/PREREG.md` |
| weekly cap 3 in | `reports/eval-03/PREREG.md` (Exposure and payouts) |
| 24, 12, 2 h | `reports/eval-01/PREREG.md` §5 |
| fee 0.07 × C × P(1 − P) | `reports/eval-01/PREREG.md` §5; medium confidence per `reports/EVALUATION.md` §2 |

## Section 4 (data)

| number | source |
|---|---|
| 61 series, 34,495 markets, 1,113,358 candle rows | `data/manifests/DATA.md` D1 |
| 2022-04-27, 2023-05-11, 2026-08-26, 2026-09-28 | e01 :: `meta.date_range.NY`, `.MIA`, `.EWR` |
| 1,053 rain binaries | e01 :: `rain_daily.n_markets` |
| book snapshot 2026-09-29 | e01 :: `depth.snapshot` |
| 6,832 CLI rows | `data/manifests/DATA.md` D4 |
| 10,054 issued reports | e45 :: `revision.n_products` |
| 26 ASOS stations | `data/manifests/DATA.md` D3 |
| 50 nClimGrid vintages | e45 :: `revision.nclimgrid_prelim_vs_scaled.n_vintages` |
| 1,109,492 small establishments | e45 :: `population.small_business.est_small` |
| 2022-07-01 | e06 :: `panels.G1.first` |
| grid label D = calendar D−1 | `docs/CONVENTIONS.md`; `reports/EVALUATION.md` §2 |

## Section 5 (design) and Table 1

| number | source |
|---|---|
| block lengths 7 d (station), 14 d / 2 weeks (residual), 2,000 draws | `reports/eval-01/PREREG.md` §6; `reports/eval-03/PREREG.md` (Inference) |
| P1 +0.10, P2 70 % and 4 of 5 (3 of 5 rain), P3 η ≥ 0.5 | `reports/eval-03/PREREG.md` (Pass rule) |
| T2 100 %, T3 0.02, T4 10 % | `reports/eval-01/PREREG.md` §7 |
| EWR 241 %, TTN 266 % | e01 :: `verdicts.T2.EWR.overround`, `verdicts.T2.TTN.overround` |
| Brier gain 0.141 | e01 :: `rain_daily.horizons.24.brier_gain` |
| MIA 2024 13.7 % | e01 :: `verdicts.T4.worst`, `verdicts.T4.worst_share` |
| heat best ΔHE +0.061 | e03 :: `bakeoff.temperature.G1-P.pooled_median_dhe` |
| M1 3 of 5; M3 0.126 | e45 :: `verdicts.M1.stations_ge_0p25`, `verdicts.M3.CPC` |
| M5 1 breach in 599 days | e45 :: `verdicts.M5.kupiec.x`, `.n` |
| junior −190 % | jr.md, model-based table, `margin_t10` "3-season sum, p5" (jr :: `model.splits.margin_t10`) |
| learning T2 0.072, 0.053; bar 0.20 | e06 :: `verdicts.T2.G1.heat_rain_median`, `verdicts.T2.G2.heat_rain_median`; `reports/eval-06/PREREG.md` §8 |

## Section 6.1 (station) and Table 2

| number | source |
|---|---|
| Table 2, all rows | e01 :: `temperature.pooled[rule=A,h=24,...]` and `temperature.city[rule=A,h=24,...]` (reproduced in `reports/EVALUATION.md` §4) |
| binning RMSE 0.42 | e01 :: pooled liquid, A, 24 h `.binning_rmse` |
| 0.2 % of 3,822 city-days | e01 :: `mismatch[city=all,settle_source=all]` |
| 29.7 % with fees | e01 :: pooled liquid, A, 24 h (total load), `reports/EVALUATION.md` §4 horizon table |
| 2023-24 markups 33–47 %, 2025-26 2–16 % | e01 :: `temperature.city_year[rule=A,h=24,city,year].overround` (`reports/EVALUATION.md` §4 city-year table) |
| 9.7 % (2025+) | e01 :: 2025+ pool `.overround.est` |
| 0.5 expected | `reports/eval-01/PREREG.md` §7 T1b |
| HE_ladder 0.01 at 2 h (2025+) | e01 :: `temperature.pooled[rule=A,h=2,pool=liquid 2025+ (post-hoc)].he_ladder.est` |
| 34 days each (EWR, TTN) | e01 :: `meta.n_citydays.EWR` |
| ≤ 0.3 % no-offer 2025-26 | e01 :: `verdicts.T4.per_city_year` |
| 33, 54, 55 units | e01 :: `depth.ladders.KXHIGH{NY,CHI,MIA}-26SEP30.max_units_3c` |
| 3 cents | `reports/eval-01/PREREG.md` §6 (depth) |
| rule B: 3.1 %, 27 %, −0.75, −0.20 | e01 :: `temperature.pooled[rule=B,h=24,...]` `.tail_outside_share`, `.unspanned_share`, `.he_ladder.est` (all years and 2025+) |
| rain: 0.106, 0.247, 0.141 [0.128, 0.152], $1.20, 0.83, 0.27 | e01 :: `rain_daily.horizons.24.{brier_market,brier_clim,brier_gain,cost_per_dollar_payout,he_wet.he_cover.est,he_wet.he_ladder.est}` |
| 26 trace days settled NO (Jul-Sep 2026) | `reports/eval-01/trace_kxrain_2026.json :: trace_days` |
| trace-dry sensitivity 0.76, 0.23 | `reports/eval-01/sensitivity_trace_dry.json :: rain_daily_dry.horizons.24.he_wet.{he_cover,he_ladder}.est` |

## Section 6.2 (geography) and Table 3

| number | source |
|---|---|
| 2025-01-01 to 2026-08-31, 608 days, 86 weeks; train 2024 | `reports/eval-03/PREREG.md` (Sample); `reports/eval-03/RESULTS.md` (Setup) |
| 37 temperature pairs, 26 rain pairs, five markets | e03 :: `bakeoff.temperature.D0.n_pairs`, `bakeoff.rain.D0.n_pairs` |
| by-market medians (Table 3) | e03 :: `eval02.<variable>.by_market.<MKT>.median_he0` |
| 0.81 [0.78, 0.84]; 0.49 [0.38, 0.66] | e03 :: `eval02.<variable>.pooled_median_he0`, `.pooled_median_he0_ci` |
| Kalshi strike: 0.36, 0.47, 0.27 | `reports/eval-03/RESULTS.md` ("The Kalshi-ladder sensitivity"); `reports/eval-03/tables.md` §5 |

## Section 6.3 (residual), Table 4

| number | source |
|---|---|
| Table 4, all rows | e03 :: `bakeoff.rain.<DESIGN>.{pooled_median_he,pooled_median_dhe,dhe_ci,share_pairs_dhe_pos,markets_dhe_pos,pooled_median_eta,verdict}` |
| eight eligible designs | `reports/eval-03/PREREG.md` (Designs table, "Eligible for verdict" = yes) |
| market medians +0.21 to +0.24 | e03 :: `bakeoff.rain.G1-P.by_market.<MKT>.median_dhe` (0.207–0.242) |
| G1-P vs R-A 0.112 [0.032, 0.238] | e03 :: `verdicts.winner_vs_next_survivor.rain` |
| G1-P vs P-A-IDW +0.062 [−0.008, 0.229] | e03 :: `verdicts.winner_vs_runner_up.rain` |
| Miami G1-P median HE 0.17 | e03 :: `bakeoff.rain.G1-P.by_market.MIA.median_he` (0.167) |
| May-Sep +0.357; 2025-10..2026-08 +0.150 | `reports/eval-03/RESULTS.md` (Sensitivities); `reports/eval-03/tables.md` §5 |
| monthly ladders no-offer 47–64 % | e01 :: `rain_monthly.<series>|1st of month 12:00Z` |
| temperature 0.81 → 0.87, +0.061 [0.044, 0.075], η 0.47, all pairs > 0 | e03 :: `bakeoff.temperature.G1-P.{pooled_median_he0_same_pairs,pooled_median_he,pooled_median_dhe,dhe_ci,pooled_median_eta,share_pairs_dhe_pos}` |
| P-A-IDW +0.052, R-A +0.033 | e03 :: `bakeoff.temperature.{P-A-IDW,R-A}.pooled_median_dhe` |
| Kalshi-strike sub-sample +0.161, +0.147 | `reports/eval-03/RESULTS.md` (Sensitivities) |
| PC1 −0.055 [−0.080, −0.034] | e03 :: `verdicts.pc1_vs_equal` |

## Section 6.4 (pool), Table 5

| number | source |
|---|---|
| 2 % take-up | `reports/eval-04-05/PREREG.md` (Fixed choices) |
| netting 40 %, null 1.9 %, rain 0.003 | e45 :: `netting.central.pooled`, `netting.null.pooled`; rain :: `netting.central.pooled` |
| 4,426 units vs 5 | e45 :: `netting.leftover_units_per_day.NYC.mean_units`; cap in `reports/eval-04-05/PREREG.md` |
| 704 vs 205,019 contracts | derived in `reports/EVALUATION.md` Appendix B rows 181-182 from rain :: `depth.by_city.<ST>` |
| Table 5, all rows | e45 :: `capital.deploy_detrended.<book>.H30` (reproduced in `reports/EVALUATION.md` §7) |
| station leg 0.25, climatology-priced 0.36 | e45h :: `capital_per_usd_cover_H30.per_usd_pool_notional_station_leg_only`, `.per_usd_pool_notional_clim_priced_station_only` |
| M5: 6 expected, p = 0.011 | e45 :: `verdicts.M5.kupiec.expected`, `.p_value` |
| junior $206k | jr :: `capital.J0` |
| worst season 2009, $731k | derived in `reports/EVALUATION.md` Appendix B row 154 from jr :: `model.weather_pnl_hist` |
| 20 % senior, 10 % treasury | jr :: `senior_share`, `treasury_cuts[0]` |
| +43 %, −144 %, −332 % | jr :: `model.splits.margin_t10.{boot_median,boot_p05_1in20,hist_worst}` |
| spec split median −214 % | jr.md, model-based table, `spec_t10` median |
| rain junior −236 %, rain C_30 $1,082k | rain :: `R5.margin_t10.three_season_sum_p05`, `capital.two_leg_joint.H30.C` |
| house $1,154/day, $384/day | e45 :: `markouts.pooled.hedged.mean`; e45h :: `house_markout_mean_daily_usd.resid_trailing5` |

## Section 6.5 (learning)

| number | source |
|---|---|
| 0.072 [0.056, 0.091], 0.053 [0.026, 0.077] | e06 :: `verdicts.T2.G{1,2}.heat_rain_median`, `.heat_rain_ci` |
| heat-only 0.001 | e06 :: `verdicts.T2.G1.heat_only_median` |
| oracle 0.115 | e06 :: `groups.G1.primary.arms.A4.cover_heat_rain_daily.median` |
| HE_ladder 0.006, cost 32 %, cap 25 % | e06 :: `verdicts.T3.G1.ladder_median`, `.cost_ratio`; `reports/eval-06/PREREG.md` §8 T3 |

## Section 7 and Appendix A (ledger)

| number | source |
|---|---|
| 24 lines: 8 pass, 15 fail/adverse, 1 split | counted from the ledger rows below |
| station T1-T4 and check (premium −0.1 %, payout 1.2 %) | e01 :: `verdicts.*`, `ins1_check` |
| residual heat/rain, Q2 | e03 :: `verdicts.winner`, `verdicts.pc1_vs_equal` |
| M1-M5 (M4 0.0 %) | e45 :: `verdicts.M1`..`verdicts.M5` |
| junior | jr.md, model-based table (all four rules "no") |
| R1 0.003, R2 0.166, R3 1.002, R4 ≤ 0.0092, R5 −236 % | rain.md, Verdicts table |
| learning T1 (split), T2, T3, T4 (0.016 at n = 180), P1 | e06 :: `verdicts.T1`..`verdicts.P1`; `verdicts.T4.G1.short_n.180.diff` |
| 205 filled city-days | `reports/eval-01/PREREG.md` Deviations, item 1 |
| 19 of 26 pairs, +0.186 before re-pull | `reports/eval-03/deviations.json` (deviation 1, resolution text); `.planning/phases/03-geography-residual-bakeoff/03-REPULL-SUMMARY.md` |
| freeze times 13:22, 13:26, 14:23, 15:40, 18:45 (UTC, 2026-09-30) | each `PREREG*.md` header |

## Section 8 (limitations)

| number | source |
|---|---|
| median staleness about 1 h | e01 :: pooled liquid, A, 24 h `.stale_median_h` |
| TWC settlement: 46 days per city; mismatch 0 % (NY, CHI), 2.2 % (MIA) | e01 :: `mismatch[city,settle_source=TWC]` |
| change in place by mid-August 2026 | `.planning/STATE.md` (update 2026-10-02T11:40Z); `reports/orfe-t5/VENUE-CENSUS.md` |
| nClimGrid prelim vs final: 64 % | e45 :: `revision.nclimgrid_prelim_vs_scaled.tmax_moves_ge_0p5F_share` |
| 26 joint seasons | e45 :: `capital.deploy_detrended.pooled_both_legs.H30.n_seasons` |
