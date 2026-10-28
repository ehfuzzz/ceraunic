# Weekly rain two-leg book (EVAL-04 extension)

Run 2026-09-30T18:57:45Z by `uv run python scripts/eval04_rain.py` (26.2 s, deterministic, seed 20260930). Rules frozen in `PREREG-rain.md` at 2026-09-30T18:45:48Z, before any number. All numbers are in `rain_book.json`; keys in backticks.

## Verdicts (pre-registered lines)

| ID | Line | Result | Verdict |
|---|---|---|---|
| R1 | NR >= 0.25 at >= 3 of 5 | NYC 0.000, EWR 0.003, TTN 0.000, MDW 0.014, MIA 0.000; pooled 0.003 | **NOT MATERIAL** |
| R2 | two-leg C_30 / 30-day notional <= 0.35 | 0.166 (C_30 $1,081,899) | **LEVERAGE HOLDS** |
| R3 | two-leg C_30 / station C_30 <= 1.25 | 1.002 (absorb-all, D1: 1.085) | **RESIDUAL CHEAP TO CARRY** |
| R4 | depth proxy / net short contracts >= 0.5 in >= 3 of 5 | NYC 0.0005, EWR 0.0060, TTN 0.0092, MDW 0.0046, MIA 0.0062 | **THE HOUSE CARRIES IT** |
| R5 | 1-in-20 junior return positive over 3 seasons (May-Sep, model) | spec_t10 -1327 %, spec_t20 -1331 %, margin_t10 -236 %, margin_t20 -240 % | **spec_t10 FAIL, spec_t20 FAIL, margin_t10 FAIL, margin_t20 FAIL** |

## Netting and leftover

- Central priors, 2 %: pooled NR 0.003; shrink-to-common null 0.000; prior ensemble pooled p10/p50/p90 0.004 / 0.055 / 0.217. Residual leg per cell: 0.003. Only delivery and cinemas gain on wet days, and they are too few.

| station | businesses | wet-cover units bought/day | sold/day | leftover $/wet day | station-leg max payout $/week |
|---|---|---|---|---|---|
| NYC | 1008 | 134,338 | 0 | 134,338 | 940,366 |
| EWR | 319 | 36,199 | 55 | 36,144 | 253,007 |
| TTN | 166 | 23,506 | 0 | 23,506 | 164,544 |
| MDW | 455 | 55,870 | 382 | 55,487 | 388,412 |
| MIA | 244 | 32,620 | 0 | 32,620 | 228,343 |

## Kalshi depth

Depth proxy = 10 % of the median contracts traded before the T-24h cutoff (no daily-rain order book on file). Buying the binary at the 24 h ask costs 1.205 per $1 of payout (EVAL-01: 1.20). An uncapped hedge would cost $9,308 a day in spread and fees on the observed run.

| city | observed days | mean net short contracts/day | depth proxy | ratio | participation it supports |
|---|---|---|---|---|---|
| NYC | 519 | 96,401 | 44 | 0.0005 | 0.0009 % |
| EWR | 33 | 24,099 | 144 | 0.0060 | 0.0120 % |
| TTN | 33 | 17,495 | 160 | 0.0092 | 0.0183 % |
| MDW | 71 | 37,060 | 170 | 0.0046 | 0.0092 % |
| MIA | 70 | 29,964 | 186 | 0.0062 | 0.0125 % |

## Auctions (observed run)

| market | days / markets | hedger fill share | no-trade share | clearing - fair (c) |
|---|---|---|---|---|
| NYC/station | 519 | 0.718 | 0.083 | 0.72 |
| NYC/residual | 11352 | 0.022 | 0.461 | 0.36 |
| EWR/station | 33 | 0.668 | 0.000 | 0.59 |
| EWR/residual | 7396 | 0.019 | 0.658 | 0.23 |
| TTN/station | 33 | 0.744 | 0.091 | 0.65 |
| TTN/residual | 6106 | 0.018 | 0.639 | 0.23 |
| MDW/station | 71 | 0.673 | 0.000 | 0.85 |
| MDW/residual | 10234 | 0.037 | 0.437 | 0.36 |
| MIA/station | 70 | 0.919 | 0.000 | 0.70 |
| MIA/residual | 5676 | 0.032 | 0.381 | 0.41 |

House P&L after the capped hedge, per day: mean $2,532 (95 % CI $-800 to $5,537), worst day $-83,312, worst 30 days $-373,301. Residual leg per week: mean $342.

## Capital (Phase 4 rule; C = min(FC, max(ES99, worst window)))

| book | history | C_30 | ES99_30 | worst 30 d | binding | CPC_30 | C_153 | junior ES95_30 |
|---|---|---|---|---|---|---|---|---|
| station leg | 1999-2025 | $1,469,321 | $988,038 | $1,469,321 | worst_window | 0.239 | $3,005,521 | $767,066 |
| station leg | 2024-26 | $1,080,006 | $1,075,329 | $1,080,006 | worst_window | 0.176 | $2,501,536 | $834,092 |
| two legs (primary) | 2024-26 | $1,081,899 | $1,076,272 | $1,081,899 | worst_window | 0.166 | $2,505,199 | $834,942 |
| two legs, R-A | 2024-26 | $1,084,634 | $1,074,608 | $1,084,634 | worst_window | 0.167 | $2,500,836 | $833,539 |
| two legs, R-A | 1999-2025 | $1,472,794 | $987,066 | $1,472,794 | worst_window | 0.227 | $2,988,330 | $765,886 |
| two legs, 19-pair | 2024-26 | $1,080,581 | $1,075,997 | $1,080,581 | worst_window | 0.167 | $2,504,407 | $834,740 |
| station leg, May-Sep | 1999-2025 | $1,278,408 | $970,213 | $1,278,408 | worst_window | 0.208 | $2,320,608 | $746,783 |
| two legs, May-Sep | 2024-26 | $915,845 | $915,845 | $855,333 | ES99 | 0.140 | $2,411,322 | $741,012 |
| station, no hedge | 1999-2025 | $1,472,511 | $990,460 | $1,472,511 | worst_window | 0.239 | $3,013,114 | $768,913 |
| two legs, uncapped hedge | 2024-26 | $10,523 | $10,523 | $9,175 | ES99 | 0.027 | $23,220 | $7,791 |
| D1 absorb-all two legs | 2024-26 | $1,171,319 | $1,171,319 | $1,164,874 | ES99 | 0.051 | $2,762,362 | $906,573 |
| D1 absorb-all, 19-pair | 2024-26 | $1,140,771 | $1,140,771 | $1,122,238 | ES99 | 0.057 | $2,688,709 | $884,878 |
| D1 absorb-all, May-Sep | 2024-26 | $938,744 | $938,744 | $817,417 | ES99 | 0.041 | $2,401,275 | $749,955 |
| D1 absorb-all R-A | 1999-2025 | $1,619,200 | $1,018,047 | $1,619,200 | worst_window | 0.070 | $2,942,412 | $797,267 |
| D1 residual alone | 2024-26 | $387,065 | $387,065 | $300,274 | ES99 | 0.023 | $855,260 | $289,334 |

Two-leg long figure (station 1999-2025 × the 2024-26 two-leg/station ratio): C_30 $1,471,897, C_153 $3,009,922. Weekly station/residual P&L correlation on 2024-26: 0.27 (absorb-all 0.27).

## Junior return (junior_returns method)

J0 = two-leg ES95_30 = $834,942; S0 = $246,957.

| rule | observed 2025 | observed 2026 | model May-Sep median | 1-in-20 | p1 | 3-season p5 | model year median | year 1-in-20 | absorb-all May-Sep median / 1-in-20 / 3-season p5 |
|---|---|---|---|---|---|---|---|---|---|
| spec_t10 | -196 % | -476 % | -347 % | -514 % | -580 % | -1327 % | -802 % | -1061 % | -293 % / -451 % / -1150 % |
| spec_t20 | -197 % | -478 % | -348 % | -515 % | -581 % | -1331 % | -805 % | -1064 % | -294 % / -452 % / -1154 % |
| margin_t10 | +102 % | +45 % | +12 % | -147 % | -211 % | -236 % | +28 % | -221 % | +38 % / -113 % / -146 % |
| margin_t20 | +101 % | +43 % | +11 % | -149 % | -213 % | -240 % | +24 % | -225 % | +37 % / -115 % / -149 % |

Mean modelled May-Sep season: station premium $15,149,812, margin inside it $130,868 (0.9 %), payouts $15,017,277, hedge $-3,860, residual $7,546. Observed 2025 is NYC only (KXRAINNYC); 2026 adds CHI/MIA from mid-July and EWR/TTN from late August.

## Two lines for the report and memo

§7 paragraph:

> Rain as a weekly two-leg book (wet-day cover; station leg = daily Kalshi rain binaries, residual = PRISM per-cell spread; `reports/eval-04-05/rain_book.json`). Almost nothing nets: 0.003 of units cancel (`netting.central.pooled`), because nearly every sector loses on wet days. At 2 % participation the pool is short $282k of payout per wet day across the five cities (`netting.leftover.<ST>.leftover_units_per_day`), and Kalshi's daily rain markets can absorb about 700 contracts a day against about 205,000 needed (`depth.by_city.<ST>.depth_proxy`, `.mean_net_short_contracts`; a volume proxy, no order-book history), so the house carries it. The 30-day capital is $1.08M on the 2024-26 window (`capital.two_leg_joint.H30.C`; Phase 4's heat book: $412k, `handoff.C30_usd`), 0.17 of 30-day notional (`R2.CPC`), and $1.47M for the station leg on 1999-2025 (`capital.station_long_1999_2025.H30.C`); the season (153-day) figure is $2.51M (`capital.two_leg_joint.H153.C`). The residual leg adds little capital: ×1.00 as priced (`R3.ratio`), ×1.08 if the house wrote every residual unit (`D1_absorb_all.ratio30`). With senior paid out of margin, the junior's median May-Sep season is +12 % and the 1-in-20 season -147 % (`junior.model_MaySep.splits.margin_t10`), so the three-season test fails (`R5.margin_t10`).

Memo line:

> Rain cover doesn't net and Kalshi's daily rain markets are about 300 times too thin to lay it off, so a rain book is the pool's own risk: about $1.08M of 30-day capital at 2 % take-up, and the junior loses money in a bad year.

## Assumptions

- Population, participation (2 %, Phase 4 `p2` draw) and e_R priors as Phase 4; wet-day units h = -daily_rev x e_R/100; Chicago businesses in the Midway catchment, rain station leg at O'Hare (KXRAIN CHI settles at CLIORD).
- Wet day = precipitation > 0 including trace (Kalshi rule). Joint-window station data: CLI (`official_daily`) for NYC/EWR/TTN/MIA, GHCN-D for ORD; long history GHCN-D PRCP 1999-2025 (TTN's record starts 1998).
- Residual = G1-P design on weekly wet-day counts (PRISM ppt >= 0.01 in on labels Tue..Mon), not the inch spec; cell nearest each business ZIP point; Chicago c(S) = O'Hare's cell. PRISM values as cached (mostly final grids), not the count-2 snapshot.
- Station fair value = Kalshi mid at T-24h; scenario fair value = Markov P(wet | month, wet yesterday) fitted in-sample on 1999-2025; residual scenario fair = in-sample cell mean over 2024-26.
- House quote = fair + max(charge, 1 tick); charges (CoC 15 %) are a fraction of a cent, so the quote is tick-bound, as in Phase 4.
- Kalshi hedge capped by the depth proxy (10 % of pre-cutoff volume, 44-186 contracts per city-day); hedge P&L includes the taker fee.
- Book for capital = average observed house position per station-month (after the hedge), ratio x demand where a month has < 5 observed days; residual book per cell-month from the observed weekly auctions.
- Junior: station fills are policies; residual fills and the hedge are house deployment (all to junior). Model seasons join the long station history with the residual from a random 2024/2025 block at the same calendar dates (independent across years).

## Caveats

- The observed Kalshi era is mostly NYC (519 of 726 station-days); other cities have 33-71 days, so their books lean on the ratio rule.
- The two-leg history is 32 months (2024-01..2026-08): the season-horizon (153-day) capital has few independent windows; May-Sep has 2.
- Depth is a volume proxy; no KXRAIN order book exists on file. The need is about 110 (TTN) to 2,200 (NYC) times the proxy, so the verdict survives any plausible error in it.
- The residual on wet-day counts was not scored in Phase 3 (which used inches); its hedge value is untested here.
- Under the frozen limits almost no residual trades (hedgers will not pay one 14-wide tick), so the primary two-leg book is the station leg plus a sliver; D1 gives the absorb-all read.
- The modelled residual component has a non-zero mean (+ about $250k a season absorb-all) because its fair value is the 2024-26 mean and the bootstrap draws 2024-25 only; the junior median under absorb-all is flattered by it.
- Sector priors are LOW confidence; e_R for outdoor recreation (-30 %), car washes (-40 %) and landscaping (-20 %) drive most of the demand.

## Deviations (UTC)

- D1 (2026-09-30T18:52:06Z, after the first full run at 18:50Z): under the frozen limits (mu_r +/- l*MAD_r, l <= 0.25, MAD ~0.5 wet days) a hedger's residual premium is under one tick of the 14-wide scalar ($0.14 per unit-week), so only 2-4 % of residual units fill and the primary two-leg book is almost the station leg alone. Added a residual 'absorb-all' sensitivity: the house takes every business's residual units (q_r = -sum h per cell, like Phase 4 D4(b)); capital, R3 ratio and junior reported for it alongside the primary. Also: clearing - fair is now averaged over markets that traded, and the no-trade share is reported (first run averaged over no-trade markets too). The primary rules and verdicts are unchanged.

Look-ahead runtime check: 20 station markets re-run with every post-cutoff candle and the result flipped; 0 moved.
