# EVAL-01 results: how well Kalshi station ladders hedge heat and rain at the station

Rules frozen in `PREREG.md` at **2026-09-30T13:22:08Z**. First run 13:29Z; final run 13:37Z (`uv run python
scripts/eval02.py --all`, 24 s). Numbers are in `results.json` and `tables.md`; per-day rows in `citydays.csv.gz`
and `rain_daily.csv`; figures in `figures/`. Deviations: 7 logged in PREREG.md (a CLI fill for 205 missing
settlement values, a bracket-validity check, a clarified rain Brier sample, the rain wet-day conditional firing,
KXRAINNY dropped, one post-hoc descriptive pool, and a rule-B strike caveat). None of them changes a verdict.

Units: one policy unit pays $1 per °F above the strike, up to 6 °F (at most $6 a day). "Premium" means the
sum of YES asks for the replicating contracts, before fees. "Overround" = total premium ÷ total ladder payout − 1.

## Verdicts

| test | rule (frozen) | result | verdict |
|---|---|---|---|
| T1 | liquid ladders (NY, CHI, MIA), 24 h, pooled 2022-2026: HE_cover ≥ 0.85 **and** overround ≤ 20 % | HE_cover 0.95 [0.95, 0.96]; overround 24.6 % [21.4, 27.9] | **FAIL** (on price, not on fit) |
| T1b | HE_ladder, no threshold, expected about 0.5 at 24 h | −0.32 [−0.47, −0.20] pooled; 0.37 [0.33, 0.42] for 2025+ | below expectation |
| T2 | thin ladders fail if 24 h overround > 100 % | EWR 241 %, TTN 266 % | **FAIL** (both, as ins1 said) |
| T3 | daily rain binary: climatology Brier − market Brier ≥ 0.02 at 24 h | 0.247 − 0.106 = 0.141 [0.128, 0.152] | **PASS** |
| T4 | liquid ladders: 24 h no-offer share ≤ 10 % in every city-year from 2024 | 2024: NY 12.8 %, CHI 12.3 %, MIA 13.7 %; 2025: 0.3 % each; 2026: 0 % | **FAIL** (2024 only) |

The frozen sample without the CLI fill gives the same verdicts: T1 HE_cover 0.95, overround 25.3 %; T4 2024
shares unchanged (`sensitivity_prereg_strict_sample` in results.json).

## Headline numbers (strike rule A: K = floor of the ladder's second bracket, 24 h before close)

Brackets are 95 % intervals from a 7-day block bootstrap (2,000 draws, seed 20260930).

| ladder | city-days (executable) | premium | payout | overround | fee | HE_cover | HE_ladder |
|---|---|---|---|---|---|---|---|
| NY (Central Park), 2022-04 → | 1,612 (1,435) | 4.07 [3.84, 4.32] | 3.11 [2.93, 3.30] | 31.0 % [26.7, 35.9] | 0.17 | 0.96 [0.95, 0.96] | −0.23 [−0.36, −0.10] |
| CHI (Midway), 2022-04 → | 1,615 (1,444) | 4.56 [4.32, 4.80] | 3.66 [3.48, 3.83] | 24.7 % [21.0, 28.8] | 0.19 | 0.96 [0.95, 0.96] | −0.34 [−0.52, −0.19] |
| MIA, 2023-05 → | 1,235 (1,087) | 5.80 [5.60, 5.99] | 4.88 [4.77, 4.98] | 19.0 % [15.3, 22.9] | 0.23 | 0.93 [0.92, 0.94] | −0.59 [−0.97, −0.25] |
| EWR (thin), 2026-08 → | 34 (34) | 8.93 [5.61, 12.23] | 2.62 [2.27, 3.40] | 241 % | 0.19 | 0.95 [0.93, 0.97] | −7.4 |
| TTN (thin), 2026-08 → | 34 (33) | 8.87 [5.28, 12.23] | 2.42 [1.96, 3.09] | 266 % | 0.17 | 0.90 [0.77, 0.94] | −13.9 |

The pooled number hides three market eras. The liquid ladders are a different market now than in 2023-24:

| liquid ladders, 24 h | overround | spread cost per unit | no-offer share | HE_ladder |
|---|---|---|---|---|
| 2022 (4-bracket ladders) | NY 17.7 %, CHI 12.0 % | 0.27-0.34 | 6.5-9.7 % | 0.30-0.31 |
| 2023-2024 | 33-47 % | 1.15-1.43 | 12-42 % | −1.23 to −0.16 |
| 2025-2026 (post-hoc pool, not a verdict) | 9.7 % [7.7, 11.7] | 0.29 | 0.2 % | 0.37 [0.33, 0.42] |

By city and year (tables.md): 2026 overround is NY 13.2 %, CHI 6.4 %, MIA 2.4 %; 2025 is NY 16.4 %,
CHI 14.2 %, MIA 7.1 %. So T1 fails because of 2023-24 pricing. On today's market the liquid ladders would clear
the 20 % bar, but that is a post-hoc reading, not the pre-registered test.

Other horizons (liquid, pooled): overround 30.1 % at 12 h and 7.5 % at 2 h. Fees add 0.20 per unit at 24 h
(about 4 % of premium) and 0.02 at 2 h. The ins1 NYC subset reproduces (see Checks).

## HE_cover and HE_ladder, side by side

HE_cover asks: does the ladder's payout track the loss? Yes, about 0.95 every year in every liquid city.
Binning costs little (RMSE 0.42 per unit). The settled value matches the NWS climate report on 99.8 % of days.

HE_ladder asks: after paying the ask 24 hours ahead, is the buyer's net result steadier than doing nothing?
Mostly no. Pooled it is −0.32, meaning the buyer's net swings more than the bare exposure. The reason is that the
24 h ask already contains tomorrow's forecast. The price moves with the forecast, so the buyer swaps the
weather swing for a price swing of about the same size. Only the forecast miss (the surprise between 24 h and
the settled high) is actually transferred. When markups were noisy (2023-24, spread cost above $1 per unit),
that markup noise was larger than the surprise, and HE_ladder went negative. In 2025-26 it is 0.36-0.59 by
city-year, close to the 0.5 we expected from ins1. On the ins1 days this engine gives 0.53, the same number.
At 2 h the price already knows the answer, so HE_ladder is about 0 (0.01 for 2025+).

With a fixed strike (rule B, below) the gap is wider: HE_cover 0.97 but HE_ladder −0.75 pooled, −0.20 for
2025+. A fixed strike means a lot of the exposure is predictable level (a hot week), and the 24 h price
charges for all of it.

The difference HE_cover − HE_ladder is the forecast-level risk. On the default path (the business buys one
fixed-price policy and the house hedges daily) the house carries it. For 2025+ it is about 0.6 of exposure
variance under rule A and more under a fixed strike. Phase 4 capital needs this number.

## Fixed strike (rule B: K = floor of the trailing 7-day mean of the settled high)

- Tail outside the ladder: on 3.1 % of liquid city-days the high settled in an open-ended bracket and the ladder
  paid less than the policy. That loses 2.6 % of total policy payout (1.6 % for 2025+). Under rule A, 1.1 %
  of days and 0.5 % of payout, all in the 4-bracket 2022 ladders (zero from 2023).
- Unspanned days: on 27 % of liquid city-days (CHI 37 %, NY 27 %, MIA 14 %) the fixed strike sat at or above
  the ladder's top bracket, so the ladder bought nothing. Most of those days pay nothing anyway. The ones that
  do pay show up in the tail share above.
- Cost: overround 28.1 % pooled, 11.0 % for 2025+. That is a bit worse than rule A because a fixed strike
  leans on the thin tail rungs.

## Thin ladders (EWR, TTN)

Executable only near the close: 24 h overround 241-266 %, 12 h 182-216 %, 2 h 8-20 %. HE_cover is fine
(0.90-0.95). Only 34 days each, all August-September 2026, so the CIs are wide. ins1's call stands: do not
hedge on them. Use NYC and carry the EWR/TTN minus NYC gap as a residual (Phase 3).

## Settlement source

- CLI high vs Kalshi's settled value, 2023+ (3,822 city-days with a real expiration_value): 0.2 % differ;
  0.1 % fall outside the bracket that settled. Under the TWC rules (from 2026-08-15, 46 days a city) the only
  miss is 1 MIA day.
- ins1 counted 5/272 "TWC ≠ NWS" days, but it compared against IEM ASOS, not the CLI. IEM runs about
  0.5 °F low (CONVENTIONS §8), so most of ins1's mismatch was measurement, not settlement. Against the
  official climate report the settlement leg is almost exact.

## Rain

- Daily "> 0 in" binary, 1,053 settled markets (KXRAINNYC 769 from 2021-09; KXRAIN 284 for NY/CHI/MIA/EWR/TTN
  from 2026-07-15). At the 24 h mid, Brier 0.106 vs 0.247 for leave-year-out monthly climatology (T3 pass by a
  wide margin). By city at 24 h: NY 0.102, CHI 0.113, MIA 0.182, EWR 0.085, TTN 0.054 (climatology 0.21-0.27).
- Trace days: 91, and 61.5 % settled YES. Kalshi's result agrees with the station wet flag (trace counted as
  wet) on 95.8 % of 831 markets. A policy that pays on "measurable rain" (≥ 0.01 in) will not match the Kalshi
  leg on trace days.
- Cost: buying the binary at the 24 h ask costs $1.20 per $1 of payout including fees ($1.13 at 2 h).
- Wet-day exposure (2023+, 730 markets): HE_cover 0.83 [0.74, 0.91], HE_ladder 0.27 [0.19, 0.35]. The same
  forecast effect as for heat.
- Monthly rain ladders (KXRAINNYCM, KXRAINCHIM, KXRAINMIAM): at the 1st of the month, 47-64 % of strikes have
  no offer and the median spread is 7-25c. They are not an insurance-grade primitive yet. 24 h before close the
  answer is mostly known (Brier 0.003-0.017), so those prices say nothing about hedging.

## Depth

The hl-mm S3 recorder prefix was not listable from this Mac (anonymous: AccessDenied; default profile: session
expired). So depth comes from the one ins1 snapshot, `books.json` (2026-09-29 books for the 2026-09-30
ladders; the file does not store the exact time).

- Contracts within 3c of the best ask per needed rung: NY 82-754, CHI 129-531, MIA 254-647, LAX 178-376.
- Max policy at ≤ 3c slippage, taking the thinnest rung relative to its contract need: NY 33 units, CHI 54,
  MIA 55, LAX 38. That is $33-55 per °F, at most about $200-330 of payout per city-day. ins1 said 5-20 units,
  but it did not size by rung. The binding rung is a middle bracket (NY B74.5, 82 contracts for 2.5 per unit).
- Other books (median contracts within 3c per rung): hurricane counts 970-1,260, monthly NYC rain 550,
  tornado 16, Cincinnati HDD empty.

## Checks

- ins1 reproduction (NYC 2026-07-24..09-29, rule A, 24 h, no fees): premium 1.728 vs 1.73 (−0.1 %), payout
  1.448 vs 1.43 (+1.2 %), n = 67 (ins1 68: our cache ends 09-28). **Within 5 %: yes.** The same days give
  HE_cover 0.94 and HE_ladder 0.53 (0.49 with fees), matching ins1's rows.
- ins1's table lists NYC "overpay 17 %". That is (premium − payout) ÷ premium. Its other rows divide by payout,
  and so does this report, which gives 20.4 % on the same numbers.
- Tests (`tests/test_eval_ladder.py`): the ins1 19.5-contract day and its 0.5 payout; the bottom `less` bracket
  is cap − 1 for puts; the ask at t never comes from a later candle (property on random series, unsorted input);
  both candle schemas parse the same; fee rounding per order with no phantom cent.

## Caveats

- Candles are sparse. "Ask at t" is the last candle ending at or before t, and a missing hour is read as no
  change (MEDIUM, observed not documented). Median staleness is 1 h at 24 h (p90 6 h) and 4 h at 2 h (p90 12 h).
- Depth is one 2026 snapshot of top-of-book levels. Nothing about depth in 2022-25, nothing intraday. Max units is
  an upper bound for one moment.
- The fee formula is MEDIUM confidence (secondary sources plus Kalshi's worked example; the PDF was not fetched).
  It is computed per rung order at a 10-unit policy.
- 205 settled values (2025-10 to 2026-01) were filled from the CLI (deviation 1). 509 early events (2021 to
  April 2022) had fewer than 4 brackets and are out, so NY/CHI start 2022-04-27.
- Rule B's strike uses day t−1's final high, which at the 24 h decision exists only as the ~5 pm preliminary
  (deviation 7).
- EWR/TTN and all TWC-era numbers rest on 34-49 days.
- HE here is at the settlement station. It says nothing about a business 10 km away (Phase 3).

## What this means for the product

The station leg works as a payout: the liquid ladders track a capped heat payout at the station about 95 % of
the way, settle on the official number, and today cost about 10 % over fair at 24 h (2-13 % in 2026), with room
for a few dozen $/°F per city-day. What the ladders cannot do is sell tomorrow's weather at yesterday's price.
Bought daily 24 h ahead, they move only the forecast miss. So a business buying the ladder itself (the fallback
path) gets a steadier result only in the current market, and only about 0.4 of its variance goes away.
The default path, one fixed-price policy with the house hedging daily, is the one that delivers the 0.95. But
then the house is carrying the forecast-level risk, and that has to be priced and capitalised (Phase 4).
EWR/TTN should be hedged on the NYC ladder plus a residual. Daily rain works for "any rain today" (the market
beats climatology easily, 20 % load) but not for rain amounts, and trace days need an explicit rule in the policy.
