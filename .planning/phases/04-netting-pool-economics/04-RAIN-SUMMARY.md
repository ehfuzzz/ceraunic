# Phase 4 rain extension: weekly rain two-leg book

worker, 2026-09-30. PREREG-rain frozen 18:45:48Z before any number; final run 2026-09-30T18:57:45Z (`uv run python scripts/eval04_rain.py`, ~26 s; two runs byte-identical apart from `written_utc`/`runtime_s`). Outputs: reports/eval-04-05/{PREREG-rain.md, rain_book.json, rain_book.md}; cache data/cache/eval04_rain/. No Phase 4 or junior output touched.

## Verdicts vs PREREG-rain (keys in rain_book.json)
| ID | Result | Verdict |
|---|---|---|
| R1 netting | pooled NR 0.003 (`netting.central.pooled`), max station 0.014 (MDW); null 0.000; ensemble p50 0.055, p90 0.22 | NOT MATERIAL (as expected) |
| R2 leverage | two-leg C_30 $1.08M / 30-day notional = 0.166 (`R2.CPC`) | LEVERAGE HOLDS |
| R3 residual capital | two-leg / station C_30 = 1.002 (`R3.ratio`); absorb-all 1.085 (`D1_absorb_all.ratio30`) | RESIDUAL CHEAP TO CARRY |
| R4 depth | proxy 44-186 contracts/city-day vs 17k-96k net short (`depth.by_city.*`); ratio 0.0005-0.009 | THE HOUSE CARRIES IT |
| R5 junior 3-season | margin_t10 3-season p5 -236 %; spec_t10 -1327 % (`R5`) | FAIL under every split |

## Numbers
- Leftover at 2 %: $282k of payout per wet day across 5 cities, NYC $134k (`netting.leftover.<ST>.leftover_units_per_day`); ~$2.0M a week max on the station leg.
- Capital h=30 / h=153: two-leg 2024-26 $1.08M / $2.51M (`capital.two_leg_joint.H30.C`, `.H153.C`); station leg 1999-2025 $1.47M / $3.01M, CPC 0.24 (`capital.station_long_1999_2025`); two-leg long (scaled) $1.47M / $3.01M. Heat book was $412k. Junior ES95_30 $835k (`junior.J0`).
- Sensitivities: R-A $1.08M (joint) / $1.47M (long); 19-pair $1.08M; May-Sep two-leg $0.92M, station long $1.28M; absorb-all $1.17M, R-A absorb-all long $1.62M; residual alone $387k.
- Junior (margin_t10, senior on kept margin): model May-Sep median +12 %, 1-in-20 -147 %; observed 2025 +102 % (NYC only), 2026 +45 %. SPEC rule: senior takes 20 % of $15.1M premium with $131k margin inside it: junior -347 % median.
- Kalshi cost: ask/payout 1.205 (EVAL-01: 1.20); an uncapped hedge would cost $9.3k/day in spread+fee (`full_hedge_cost`). House P&L +$2.5k/day, CI -$0.8k to +$5.5k (`markouts.proxy`).

## Assumptions / deviations
Phase 4 population, 2 % `p2` draw, e_R priors; wet = >0 in incl. trace; Chicago leg at ORD; residual = G1-P design on weekly wet-day counts (not the inch spec); Markov scenario fair; depth = 10 % of pre-cutoff volume. D1 (18:52Z): frozen limits leave the residual under one 14-wide tick, so 2-4 % of residual units fill; absorb-all book added as a sensitivity.

## Caveats
Observed Kalshi era is 519 of 726 station-days NYC; two-leg history is 32 months (May-Sep h=153 has 2 windows); depth is a volume proxy (need is 110-2,200× it, so R4 is robust); wet-day residual untested for HE; LOW-confidence priors (outdoor rec, car washes, landscaping drive demand).

## The two lines (for a later builder edit; not placed)
§7: Rain as a weekly two-leg book (wet-day cover; station leg = daily Kalshi rain binaries, residual = PRISM per-cell spread; `reports/eval-04-05/rain_book.json`). Almost nothing nets: 0.003 of units cancel (`netting.central.pooled`), because nearly every sector loses on wet days. At 2 % participation the pool is short $282k of payout per wet day across the five cities (`netting.leftover.<ST>.leftover_units_per_day`), and Kalshi's daily rain markets can absorb about 700 contracts a day against about 205,000 needed (`depth.by_city.<ST>.depth_proxy`, `.mean_net_short_contracts`; a volume proxy, no order-book history), so the house carries it. The 30-day capital is $1.08M on the 2024-26 window (`capital.two_leg_joint.H30.C`; Phase 4's heat book: $412k, `handoff.C30_usd`), 0.17 of 30-day notional (`R2.CPC`), and $1.47M for the station leg on 1999-2025 (`capital.station_long_1999_2025.H30.C`); the season (153-day) figure is $2.51M (`capital.two_leg_joint.H153.C`). The residual leg adds little capital: ×1.00 as priced (`R3.ratio`), ×1.08 if the house wrote every residual unit (`D1_absorb_all.ratio30`). With senior paid out of margin, the junior's median May-Sep season is +12 % and the 1-in-20 season -147 % (`junior.model_MaySep.splits.margin_t10`), so the three-season test fails (`R5.margin_t10`).

Memo: Rain cover doesn't net and Kalshi's daily rain markets are about 300 times too thin to lay it off, so a rain book is the pool's own risk: about $1.08M of 30-day capital at 2 % take-up, and the junior loses money in a bad year.
