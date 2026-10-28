# EVAL-01 pre-registration — station hedge quality
Frozen: 2026-09-30T13:22:08Z (UTC). Written before any Phase 2 number was produced.
Author: worker, plan `.planning/phases/02-station-hedge-quality/02-PLAN.md` Task 1.

Nothing below is a result. The only numbers are thresholds, dates, sizes and seeds. Priors quoted from ins1
(prior/hl-mm-ins/reports/ins1) are labelled as priors. Any change after this timestamp goes in the Deviations
log at the bottom with a UTC time.

## 1. Question
How well do Kalshi's station ladders replicate a capped-linear daily heat payout (and do the daily rain
binaries and monthly rain ladders price a wet-day exposure) at the settlement station, bought at real hourly
asks with fees, 24 h / 12 h / 2 h before close? What does it cost (premium, overround, spread, fees), how often
can it not be bought, how big can a policy be, and how often does the settled value differ from the NWS
climate report?

## 2. Sample
- Temperature: every settled city-day (one event ticker = one city-day; market day = the date in the event
  ticker) of the daily high ladders, from `data/cache/kalshi/markets.parquet`:
  KXHIGHNY incl. legacy `HIGHNY-` tickers (2021-08 →), KXHIGHCHI incl. `HIGHCHI-` (2021-08 →),
  KXHIGHMIA incl. `HIGHMIA-` (2023-05 →), KXHIGHTEWR and KXHIGHTTTN (2026-08 →). Last day = last settled event
  in the cache. KXHIGHNY0 (2021-07, before the window) is excluded.
- A city-day enters if: it has ≥ 4 bracket markets with usable strikes, exactly one bracket settled `yes`,
  and a numeric `expiration_value`. Events failing this are counted and listed as exclusions, not dropped
  silently.
- Rain, daily binary: every settled KXRAINNYC, KXRAINNY (if its rules are the same daily "> 0 in at
  Central Park" binary) and multi-city KXRAIN-{date}-{CITY} market for NY, CHI, MIA, EWR, TTN. KXRAIN is not
  in the Phase 1 cache; it is pulled keyless and read-only (≤ 4 req/s) into a separate cache file because
  the plan's sample requires it.
- Rain, monthly ladders: every settled KXRAINNYCM, KXRAINCHIM, KXRAINMIAM market.
- Depth: every recorded order book we can read. The hl-mm S3 recorder prefix
  (s3://hlmm-reduced-5325/kalshi-weather-books/) was not listable from this Mac at freeze time (anonymous:
  AccessDenied; default profile: expired session), so depth uses `prior/hl-mm-ins/reports/ins1/books.json`
  (2026-09-29 books for the 2026-09-30 ladders) only.

## 3. Payout
- Heat call per $1/°F unit: H(T;K) = min(max(T − K, 0), 6), T integer °F.
- Strike rule A (ins1, headline): K = floor strike of the ladder's second bracket (brackets sorted by floor,
  the `less` bracket first).
- Strike rule B (fixed strike, Phase 3 rule): K_t = floor(mean of T_S over days t−7..t−1), T_S = the settled
  `expiration_value` of the same series (NWS CLI high from `official_daily.parquet` fills a missing day,
  2023+). Needs ≥ 5 of the 7 days, else the city-day is out of rule B. Rule B exists to show how much of a
  fixed-strike payout falls outside what the ladder can replicate.
- Settled station value T_S = `expiration_value` (the value Kalshi settled on). T_CLI = the NWS CLI daily
  high (2023-01 → only).

## 4. Replication (07-RESEARCH Pattern 8, 05-RESEARCH Pitfall 6)
- Representative value per bracket: `between` f..c → (f + c)/2; `greater` f → f + 1; `less` c → c − 1
  (the ins1 off-by-one fixed: `less cap=c` means T ≤ c − 1).
- Contracts per unit: q_b = H(v_b; K). Ladder payout per unit: X_lad = H(v_{b*}; K), b* the bracket that
  settled `yes` (Kalshi `result`, never recomputed from CLI).
- Binning error = H(T_S; K) − X_lad. Binning RMSE reported per city-year and pooled.
- Puts (min(max(K − T, 0), C)) use the same mapper; not evaluated here, only covered by the code.

## 5. Prices at the decision time
- t = close_time − h, h ∈ {24 h, 12 h, 2 h}, close_time read per market from the cache (never a constant).
- Ask/bid at t = `yes_ask_close` / `yes_bid_close` of the last hourly candle with candle end ≤ t (forward
  fill, no look-ahead, no staleness cap: a missing hour means no change, 01-RESEARCH Pitfall 5). Staleness
  (t − candle end) is reported.
- A needed rung (q_b > 0) has no executable ask if: no candle ends ≤ t, or the ask is null or ≤ 0, or
  ask ≥ 0.99 with bid < 0.90 (null bid = 0). Reasons are tallied separately.
- Premium per unit π_h = Σ_b q_b × ask_b (fees excluded). Spread cost = Σ_b q_b × (ask_b − mid_b),
  mid = (ask + bid)/2. Book sum = Σ_b ask_b over all rungs − 1 (secondary).
- Fee: per rung order, ceil to the cent of 0.07 × C × P × (1 − P), C = contracts, P = ask. Fees are computed
  at a reference policy of 10 units per city-day (C = 10 × q_b, integer for rule A) and divided by 10 to
  quote per unit; the unrounded fee 0.07 × q_b × P × (1 − P) is reported too. For rule B, C is rounded to the
  nearest whole contract before the fee.

## 6. Metrics (per city × year, per city pooled, liquid pooled NY+CHI+MIA, by settle_source, by
   candle source historical/live; each horizon; strike rules A and B)
- Mean premium, mean realised ladder payout, overround = Σ π / Σ X_lad − 1 (fees excluded), fee cost per
  unit, total load = (Σ π + Σ fees) / Σ X_lad − 1, spread cost, binning RMSE.
- HE_cover = 1 − var(E − X_lad) / var(E), exposure E = H(T_S; K).
- HE_ladder = 1 − var(E − (X_lad − π − fee)) / var(E) (payout net of the price paid at the horizon).
- Both HE on the same city-days: those with an executable premium at that horizon. HE_cover on all settled
  days is also reported. Pooled HE demeans within each city (1 − Σ_c n_c var_c(resid) / Σ_c n_c var_c(E)).
- A secondary exposure E_CLI = H(T_CLI; K) (2023+) is reported next to E, to show what the settlement-source
  difference does to HE.
- CIs: 7-day calendar-block bootstrap, 2,000 draws, numpy seed 20260930, blocks drawn jointly across cities
  on the same calendar dates; 95 % percentile interval. Point estimates decide pass/fail; CIs are reported.
- No-offer share (T4 metric) = share of city-days with at least one needed rung without an executable ask at
  the horizon. Rung-level no-offer share also reported. Unhedgeable-day share = no-offer days plus, for rule
  B, days where K ≥ the top bracket's representative value (the ladder buys nothing).
- Tail-outside-ladder share (rule A and B) = share of city-days where b* is an open-ended bracket and
  H(T_S;K) ≠ X_lad; plus the share of Σ H(T_S;K) lost on those days (Σ |H − X_lad| / Σ H).
- Settlement mismatch: share of city-days (2023+) with T_CLI ≠ T_S, and share with T_CLI outside the settled
  bracket. settle_source from `rules_primary`: "Weather Company" → TWC, "National Weather Service" /
  "Climatological" → NWS, otherwise "unstated".
- Depth (books.json): best YES ask = 1 − best NO bid (levels sorted explicitly); contracts within 3c of the
  best ask per rung; implied max units at ≤ 3c slippage = min over needed rungs of depth_b / q_b (rule A).
- Rain daily binary at the 24 h ask (12 h, 2 h also reported): Brier score of the mid vs the settled result;
  climatology Brier with p = leave-year-out wet-day frequency for that station and calendar month from the
  station daily data in the cache (CLI for NYC/MIA/EWR/TTN/MDW; IEM daily precip for a market that settles at
  ORD); realised cost per $ of payout = Σ (ask + fee) / Σ payout; HE_cover and HE_ladder for a wet-day
  exposure E = 1{station precip ≥ 0.01 in} (trace = dry) against the $1 binary, 2023+ days only. If the
  trace check shows trace days settle YES in more than half of the trace cases, the wet definition switches to
  "precip > 0 incl. trace" (pre-registered conditional; logged either way).
- Monthly rain ladders: per strike, spread (ask − bid), no-offer share and Brier of the mid vs result at
  two times: the 1st of the contract month 12:00Z and close − 24 h. No threshold.

## 7. Thresholds (priors, frozen now)
- T1 (liquid ladders NY, CHI, MIA, rule A, 24 h, pooled over all years): PASS iff HE_cover ≥ 0.85 AND
  overround ≤ 20 %.
- T1b: HE_ladder reported with no threshold. Stated expectation (from the ins1 rows): about 0.5 at 24 h.
- T2 (thin ladders EWR, TTN, rule A, 24 h): each FAILS if overround > 100 %.
- T3 (rain daily binaries, pooled, 24 h): PASS iff Brier(climatology) − Brier(market mid) ≥ 0.02.
- T4 (liquid ladders NY, CHI, MIA, rule A, 24 h): PASS iff the no-offer share ≤ 10 % of city-days in every
  city-year from 2024 on.

## 8. Checks
- ins1 reproduction: NYC 2026-07-24..2026-09-29, rule A, 24 h, fees excluded must land within 5 % of ins1's
  premium 1.73 and payout 1.43 per unit. A miss is reported and explained, not tuned away.

## Deviations
Logged after the freeze; the rules above are unchanged text.

1. 2026-09-30T13:31Z — **T_S fill for missing expiration_value.** The Kalshi API returns an empty
   `expiration_value` for 205 settled liquid-ladder events (2025-10 to 2026-01, all NWS-rule era). As frozen,
   §2 would drop them (a hole in Nov-Dec 2025). Now: T_S = NWS CLI high when it lies inside the bracket that
   settled YES (all 205 did); `ts_source = cli_fill` in citydays.csv. The frozen strict sample is re-run as
   `sensitivity_prereg_strict_sample` in results.json; T1 and T4 verdicts are the same on both samples.
   The settlement-mismatch share uses expiration_value days only (filled days match by construction).
2. 2026-09-30T13:28Z — **Ladder validity check.** Added to the §2 entry test: brackets must cover disjoint,
   contiguous integer ranges. 4 legacy 2022 events with overlapping brackets are excluded and listed.
3. 2026-09-30T13:28Z — **Rain Brier sample (clarification).** Brier uses every market with a quote at t
   (candle ≤ t, ask present); cost and HE use executable markets only (§5 no-offer rule).
4. 2026-09-30T13:30Z — **Pre-registered wet-day conditional fired.** 91 trace days, 61.5 % settled YES
   (> 50 %), so wet = station precip > 0 incl. trace for the exposure and the climatology.
5. 2026-09-30T13:25Z — **KXRAINNY excluded** under the §2 condition: it settles on the Hudson River Pier 26
   gauge, not Central Park.
6. 2026-09-30T13:34Z — **Post-hoc descriptive pool** "liquid 2025+" added to the tables. It is not a
   verdict and does not replace T1/T4.
7. Caveat, no change: rule B uses day t−1's settled high. At the 24 h decision (about local midnight of day
   t) the final CLI for t−1 is not yet issued (preliminary ~5 pm, final ~2 am local), so rule B's strike has
   up to a few hours of look-ahead at 24 h. It sets only the strike, not a price.
