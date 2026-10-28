# EVAL-04 extension: weekly rain two-leg book (pre-registration)

Frozen 2026-09-30T18:45:48Z (UTC, `date -u`), before any number of this extension was produced. Asked for by the seat after Phase 3 (03-SUMMARY "Rain needs a new weekly two-leg book"). Script: `scripts/eval04_rain.py` (deterministic, seed 20260930). Outputs: `reports/eval-04-05/rain_book.{json,md}`; intermediates in `data/cache/eval04_rain/`. It reads Phase 4 caches (`data/cache/eval04/population.parquet`, `participants.npz`) and reuses `wi.pool.sim.run_market` (THE clearing function), `wi.pool.quote`, `wi.pool.kalshi_leg.fee`, `wi.pool.capital.es`; it writes nothing Phase 4 or the junior add-on wrote. Every change after this timestamp goes to the deviations list in `rain_book.json` / `rain_book.md` with UTC time.

What I had looked at before freezing (no book numbers): file schemas, date ranges and counts (KXRAINNYC 2021-09..2026-07-15 with the 2022-09..2024-12 gap; KXRAIN NY/CHI/MIA from 2026-07-15, EWR/TTN from 2026-08-27; PRISM discs 2024-01..2026-09; GHCN-D PRCP at TTN continuous only from 1998; participants at 2 % = 2,192 businesses).

## The book
- **Population and participation:** exactly Phase 4 (PREREG.md "Sample" and "Participation"): ZBP 2023 small establishments within 40 km of NYC / EWR / TTN / MDW / MIA, the `p2` binomial draw (2 %, seed 20260930) from `participants.npz`. Chicago businesses stay in Phase 4's Midway catchment, but the Kalshi daily rain market settles at O'Hare (CLIORD, CONVENTIONS §7), so the Chicago rain station leg is ORD.
- **Sector priors:** `e_R` from `priors_2026-09-30.csv` (sha256 checked by `load_priors`): central for the book; 1,000 triangular draws (seed 20260930) and the Phase 4 shrink-to-common null (`0.75·c + 0.25·e`) for netting only.
- **Cover:** wet-day cover. 1 unit pays $1 for a wet day. Business i's units `h_i = −daily_rev_i · e_R,i / 100` (+ = buys wet cover). Exposure is exactly linear in the wet-day flag, so no regression (Phase 4's rain rule). Order size `round(|h_i|)` units; 0 dropped.
- **Wet day:** station precipitation > 0 in, **trace counts as wet** (Kalshi "strictly greater than 0", EVAL-01: trace days settle YES 61.5 %, Kalshi agrees with trace-as-wet 95.8 %). Kalshi-era payout = the market's `result`; history = GHCN-D PRCP > 0 or M-flag T.
- **Station leg (daily):** each business holds `h_i` units of its station's day-D wet binary for every day of its week (7 daily legs a week). Priced and hedged per day at T−24h.
- **Residual leg (weekly), primary G1-P-wd:** the Phase 3 winner's design (PRISM per-cell spread, same source at b and S; residual-spec §1: cells fixed at listing, Mon-Sun week = PRISM labels Tue..Mon, all 7 labels at both cells or the leg voids) with the payout on wet-day counts instead of inches: `r_w = WD(c(b), w) − WD(c(S), w)`, `WD` = number of the 7 labels with ppt ≥ 0.01 in (PRISM has no trace). `c(b)` = PRISM cell nearest the business ZIP internal point inside the S disc; `c(S)` = NYC 40.7917_-73.9583, EWR 40.6667_-74.1667, TTN 40.2917_-74.8333, MIA 25.7917_-80.3333, Chicago = O'Hare's cell 41.9583_-87.9167 (the spec lists Midway's cell; the rain station leg is ORD). Businesses with `c(b) = c(S)` have r ≡ 0. Units per week = `h_i` (same sign as the station leg). One contract per (station, cell). Values = PRISM as cached (grid counts 1-8; the count-2 settlement snapshot is not reproducible, residual-spec caveat). Reason for the day-count form: the book pays on wet days; an inch residual on a wet-day book needs a sizing ratio nobody has fitted. The inch spec stays the listed index; this is the same design on the book's payout.
- **Pricing at the cutoff (no look-ahead):**
  - Station fair `μ_d` = YES mid of the last hourly candle ending ≤ `close_time` − 24 h (CONVENTIONS §5, no-offer rule applied: invalid quote = the station-day drops from the observed sample).
  - Residual fair `μ_r` per cell = mean of that cell's `r` over all complete weeks strictly before the week's Monday, if ≥ 8 weeks, else 0. MAD_r likewise (fallback 0.3).
  - House quote: `wi.pool.quote.inner_ticks` with width 1 (station) and width 14 / offset 7 (residual, `r ∈ [−7, 7]`); charge per unit = (CoC 15 %/365) × standalone per-unit ES99 of the 30-day loss (tick-bound in Phase 4, expected tick-bound here). Three levels, one third of capacity each (`quote.schedule`).
  - Hedger limits: loading ℓ ~ U[0, 0.25] seeded per market; buyer `μ(1+ℓ)`, seller `μ − ℓ(1−μ)`; residual `μ_r ± ℓ·MAD_r`.
  - Clearing: one call auction per (station, day) for the station leg and per (station, cell, week) for the residual, through `wi.pool.sim.run_market`. Capacity: $250,000 of full collateral per day split equally over that day's station-leg markets; $250,000 per week split over that week's residual markets in proportion to their gross hedger units. Unfilled units counted.
- **Kalshi paper hedge (station leg only):** after the auction, the house's net short wet units are bought as KXRAIN / KXRAINNYC YES at the T−24h ask (long: sold at the bid), whole contracts, taker fee ceil-to-cent(0.07·C·P·(1−P)) per order, payout from `result`. Cap per city-day = the **depth proxy**: 10 % of the median volume a settled market of that city traded in candles ending ≤ close − 24 h (no daily-rain order-book history exists; the only rain book on file is the monthly NYC ladder, median 550 contracts within 3c, EVAL-01, reported alongside). Also run with no hedge and with an uncapped hedge.
- **Observed (Kalshi-era) sample:** station-days with a settled KXRAINNYC (2025-01-01..2026-07-14) or KXRAIN (2026-07-15..2026-09-28) market, a valid T−24h quote and a result; KXRAINNY excluded (CONVENTIONS §7). Residual weeks: complete Mon-Sun weeks 2025-01-06..2026-08-30 with PRISM at both cells (all stations, whether or not a Kalshi station market exists that week).

## Capital (same rule as Phase 4)
- `C_h = min(FC_h, max(ES99(bootstrap h-day loss), worst historical h-day window loss))`; junior = ES95 of the same bootstrap; 7-day blocks, 10,000 paths, seed 20260930; windows never cross a gap in the data. Horizons **h = 30 days and h = 153 days** (the Phase 4 season length; "season horizon").
- Book = the pool's average signed position per (station, leg, month) [residual: per (station, cell, month)] from the primary observed run after the hedge; station-months without observed days use the station's (position ÷ net demand) ratio × that month's net demand (Phase 4 D4 rule), and stations with no observed days use the pooled ratio.
- Daily scenario P&L of a house long unit: station leg `W_d − μ_d`; residual leg `r_w − μ_r` booked on the Sunday that ends week w.
- Scenario fair: station leg = Markov persistence proxy `P(wet_d | station, month, wet_{d−1})` fitted on the history (the rain analogue of Phase 4's AR(1) proxy; in-sample, like Phase 4's deployable fit); residual `μ_r` = the cell's mean over the joint window (in-sample, labelled).
- Histories: (a) **station leg alone, long:** GHCN-D PRCP on joint dates 1999-2025 (TTN's record limits the start), all days of the year; (b) **two legs, joint window:** 2024-01-01..2026-08-31 (PRISM cache), station leg from CLI (`official_daily`) and ORD GHCN-D, residual from PRISM; the station leg alone is also computed on this window so the two-leg / station ratio is like for like. (c) Two-leg long figure (descriptive) = (a) × the (b) ratio.
- FC per day: station short unit `1 − p`, residual short unit `7 − μ_r` per week ÷ 7; notional per day: station $1 per unit, residual $14 per unit-week ÷ 7 (range width, Phase 4 convention).

## Junior return (the junior_returns method)
- J0 = two-leg ES95 30-day (joint window); S0 = C_30 − J0. Station-leg house fills = policies (premium = p* per unit sold, 1 − p* per unit bought); residual fills and the Kalshi hedge = house deployment (all P&L to junior). Rules spec_t10, spec_t20, margin_t10, margin_t20 exactly as PREREG-junior.
- Observed seasons: calendar years 2025 and 2026 of the Kalshi-era run (both legs), and May-Sep of each.
- Model-based: 10,000 bootstrap seasons, calendar-aligned 7-day blocks (each block's year drawn at random, all stations same date). Season = May 1-Sep 30 (153 days, primary, as Phase 4) and the calendar year (365 days). Station leg from history (a) with the quote rule applied to the scenario fair and the Kalshi hedge at scenario fair + the observed mean (ask − mid) + fee per contract; residual P&L drawn from the same calendar block of a random joint-window year (2024 or 2025), i.e. assumed independent of the station leg across years (the joint-window correlation is reported). Report median, p5 (1-in-20), p1, worst, 3-season-sum p5.

## Verdict lines (reported against; thresholds are priors, not tuned)
| ID | Metric | Line |
|---|---|---|
| R1 | Rain NR per station (Phase 4 M1 formula, wet-day units, central priors, 2 %) | MATERIAL if ≥ 0.25 at ≥ 3 of 5 stations; else NOT MATERIAL (expected: ≈ 0) |
| R2 | Two-leg CPC = C_30 / 30-day pool notional (joint window) | LEVERAGE HOLDS if ≤ 0.35; else FULL-COLLATERAL |
| R3 | Two-leg C_30 ÷ station-leg C_30 (joint window) | RESIDUAL CHEAP TO CARRY if ≤ 1.25; else RESIDUAL IS MATERIAL CAPITAL |
| R4 | Depth proxy ÷ mean net short station-leg contracts per city-day (observed run) | HEDGEABLE if ≥ 0.5 in ≥ 3 of 5 cities; else THE HOUSE CARRIES IT |
| R5 | 14-RESEARCH test: 1-in-20 junior return positive over three seasons (May-Sep, model-based) | PASS / FAIL, per split rule; margin_t10 is the headline |

Descriptive: leftover units `|L − S|` per station-day and max payout per week; NR under the null and the prior ensemble (p10/p50/p90); residual-leg NR per cell; station-leg C on history (a); house markout per day with a 7-day moving-block CI; Kalshi hedge cost per contract; fill and unfilled shares; the participation the depth proxy would support.

## Sensitivities (never gating)
1. **R-A instead of G1-P:** `r_w = mean of the weekly wet-day counts over the R-A rain list incl. S (CLI where the station issues one in `official_daily`, GHCN-D PRCP otherwise; quorum ≥ 60 % of listed inputs with all 7 days) − WD_S`; one contract per market; lists as residual-spec §2 (Chicago list {MDW, ORD, LOT, PWK, DPA}, S = ORD). Two-leg capital on the joint window and on the long history 1999-2025.
2. **19-pair vs all-pair:** primary = every business with a PRISM cell gets the residual leg (all-pair). "19-pair" = the residual leg is listed only for businesses whose nearest Phase 3 rain truth point (of their market's list) is one of the 19 with a PRISM cell; the rest (nearest point HPN, FRG, SMQ, PWK, DPA or FXE) hold the station leg only (residual-spec: do not list outside the evaluated locations before the re-pull).
3. **May-Sep only:** book, capital windows and bootstrap restricted to May 1-Sep 30 (then h = 153 is the whole season).
4. Hedge none / uncapped (for R4 and the depth read).

## Look-ahead controls
- `μ_d` reads only candles ending ≤ close − 24 h; `μ_r`/MAD_r only weeks ending before the week's Monday; orders, p* and fills are decided before the settlement value is read (`sim.settle_market` after clearing). A runtime assertion re-runs 20 random station markets with every post-cutoff candle and the result perturbed and requires identical ticks, p* and fills.
- Grid label D = calendar day D−1 (`wi.eval03.align`), weekly Tue..Mon labels.

## Known weak spots, stated before the run
- The observed Kalshi era is NYC for 2025 to mid-July 2026; the other cities have 11 weeks (CHI/MIA) or 5 weeks (EWR/TTN).
- The two-leg history is 32 months: the worst-window floor and the bootstrap rest on 2.7 years.
- No KXRAIN order book exists on file; the depth cap is a volume proxy.
- The residual on wet-day counts is not the design Phase 3 scored (inches); its hedge value is not re-tested here.
- Sector priors are LOW confidence; rain netting was already ≈ 0 in Phase 4.
