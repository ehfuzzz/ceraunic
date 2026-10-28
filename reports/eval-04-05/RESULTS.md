# EVAL-04 / EVAL-05 results: netting and pool economics

Run 2026-09-30, 13:31Z-13:49Z (UTC). Rules frozen in `PREREG.md` at 13:26:00Z, before any number. Every number below comes from `uv run python scripts/eval04.py --all` (deterministic, seed 20260930); full detail in `results.json` and `tables.md`; figures in `figures/`. Hand-off numbers for Phases 7, 14 and 16 are in `handoff.json`.

## Verdicts, pre-registered rule vs result

| ID | Rule (frozen) | Result | Verdict |
|---|---|---|---|
| M1 | NR ≥ 0.25 for ≥ 3 of 5 stations, central priors, 2 % participation | NYC 0.36, MDW 0.32, MIA 0.65 pass; EWR 0.21, TTN 0.13 fail (both on September 2026 only). Pooled 0.40 | **MATERIAL** (3 of 5, the minimum) |
| M2 | pooled NR under the shrink-to-common null < 0.10 → the pitch must not lead with netting | 0.019 (per station 0.005-0.054) | **The pitch must not lead with netting** |
| M3 | CPC = C_30 / 30-day pool notional ≤ 0.35 | 0.126 (C_30 = $412k on $109k/day of pool notional) | **LEVERAGE STORY HOLDS**, with the caveats below |
| M4 | CLI payout-moving revisions after D+1 12:00Z ≤ 2 % of units | 0 of 4,573 station-days (73 days had a reissued final report; none changed the high) | **ACCEPTABLE** |
| M5 | two-sided Kupiec on 1-day VaR99, Kalshi-era days, model fit on 1951-2020 | 1 exceedance in 599 days (6 expected), LR 6.44, p = 0.011 | **REJECTED, too few exceedances**: the model is too conservative, not too thin. No realised 30-day loss came near C_30 (worst $104k vs $417k) |

## What the numbers say, in plain words

**Netting is real under our priors and gone under the null.** With the frozen sector priors, about 40 % of the gross hedge units cancel inside one station-day auction (Miami 65 %, Central Park 36 %, Midway 32 %). The spread across 1,000 prior draws is wide (pooled p10-p90 0.22-0.56; two thirds of the draws still pass M1). But if sectors mostly move together, as the best US daily evidence says (Deryugina 2021), netting falls to 2 %. So netting is a result of the priors' sign spread, not something the data have shown. Rain nets to about zero: nearly every sector loses on wet days. Netting inside one ZIP code is about half the station-level number, so the station (not the neighbourhood) is the right pool.

**Who is on which side.** Under the central priors the long-heat businesses (liquor stores, convenience stores, snack bars, HVAC contractors) outweigh the short-heat ones in every city. They sell heat cover; the house ends up buying it. At 2 % participation that is about 1,000 businesses around Central Park and a leftover of roughly 4,400 $1/°F units a day ($26k of max payout) that the pool has to carry. Kalshi depth (a 5-unit cap per city-day) covers almost none of it.

**The auction works mechanically.** Every market-day cleared (no-trade share 0). The price lands one tick inside the house quote, about 0.5-0.8 cents (scalar) below the Kalshi-implied fair value, because the leftover is on the sell side. 92 % of station-leg hedger units filled. The matched minority got the house price, better than their limits. The one clearing function conserved units and cash on 4,000 random books.

**Capital.** Revaluing the pool's average book on joint-date history, the 30-day capital is $412k: the worst historical 30-day window (binding in every case) against a 30-day ES99 of $269k and 30-day full collateral of $1.66M. Per $ of pool notional that is 0.13; per $ of the pool's full collateral 0.25; per $ of gross hedger cover 0.07. The junior (token) layer at ES95 is $206k, half of C_30. Three things make 0.13 look better than it is:
1. The residual leg's notional is large ($12 of range per $1/°F unit) while its risk is small, so it inflates the denominator. **The station leg alone is 0.25.**
2. The scenario prices the cover every day at a persistence-forecast fair value. If the cover is priced before the forecast is known (strips priced at inception, the seat's Phase 2 point, see D5), the station-leg-only number is **0.36, just over the 0.35 line**, and the both-legs number is 0.18.
3. The worst-window floor rests on 26 joint seasons for the two-leg book (the residual network only exists from ~1999) and 64 seasons for the station leg.
The backtest says the model over-reserves against Kalshi-priced days: the persistence forecast is worse than the market's forecast, so the model's daily VaR99 was beaten once in 599 days. That is the honest reading of the M5 rejection.

**House markouts are not a result to lean on.** Pooled house P&L after the Kalshi hedge was +$1,154/day (95 % CI +$610 to +$1,710). Almost all of it is the Central Park residual leg (+$1,382/day), and that is a pricing artefact: Central Park reads cool against its airport neighbours, and that gap grew about 1 °F in the mid-1990s and another ~0.7 °F since 2020, so a climatology through year D-1 underprices the residual. Priced on the trailing 5 years it drops to +$484/day, and the pooled house P&L to +$384/day. The station legs net to about zero (+$94/day): the house loses at NYC, EWR and TTN and wins at MDW and MIA, which tracks the sign of the Kalshi mid's bias in each city (MIA ladders underpriced the heat payout by $0.44 per unit per day in 2023-26; NYC overpriced it by $0.17). The CoC setting (6/15/30 %) barely moves anything because the capital charge is under one tick. Pool return on C_30: 47 % a season in the primary run, 19 % with the residual priced on the trailing 5 years; neither is a pre-registered verdict.

**Fees.** 10 bps of notional on hedger fills is $22k a season on today's simulated flow; 50 bps is $112k. The CoW-style rule (half of each hedger's price improvement, capped at 0.98 % of notional) earns 40 bps of notional ($90k a season), because the hedgers' limits carry up to 25 % loading and the uniform price gives most of that back as improvement.

**Revision.** The station CLI settles cleanly: settle on the latest final report at D+1 12:00Z and nothing later changes the high (0 of 4,573 days; 8 days had no final report by then and need the retry rule). The same-day 4 PM preliminary report differs from the final on 10.5 % of days, so N must be at least D+1. Gridded data is a different story: nClimGrid-Daily prelim at label day + 5 differs from the scaled file by ≥ 0.5 °F on 64 % of cell-days (mean 0.77 °F) and flips the wet-day flag on 2.9 %. Anything settled on nClimGrid must wait for the scaled file (about 6 days after month end), not the prelim.

## What this means for the product
- Lead with the pool, not with netting. Netting is a bonus that depends on unproven sector priors.
- The house is the counterparty for most of the flow and cannot lay it off on Kalshi at today's depth. Capital, not hedging, is the business; 25 % of full collateral on the station leg (13 % counting the residual) is the leverage number, and it only holds if the cover is repriced daily off the forecast.
- Price the residual off a recent window (or off the ladder plus a recent metro-minus-station offset), never off long climatology. Phase 7's house quote must include that.
- Settle station legs on CLI at D+1 12:00Z; settle gridded legs only on the scaled file.

## Caveats
- Priors are LOW confidence (two MEDIUM rows). M1 passes with the minimum 3 of 5 stations.
- EWR and TTN have September 2026 only (34 and 33 days).
- The capital tail is one worst window on 26 (both legs) or 64 (station leg) warm seasons; overlapping windows are not independent.
- Scenario fair values come from a persistence forecast; Kalshi-era days are priced by the market. Full collateral is computed at average Kalshi-era prices, so a scenario day can lose more than "full collateral" (station leg, h = 1: capped at FC).
- Kalshi hedge capped at 5 units per city-day from candles, not books (no book history before the hl-mm recorder).
- The residual index uses GHCN-D values as fetched today, not T+N vintages; JRB, MMU and GYY have no GHCN TMAX record and count as absent; LOT is the Romeoville COOP (USC00117457), not an ASOS id.
- Hedge demand assumes 2 % of small establishments hedge every warm-season day at hedge ratio 1. No participation data exist.
- Size classes above 49 employees are dropped; sectors whose large establishments are all suppressed in ZBP (cinemas, amusement parks, home centres) may have their small-establishment counts overstated (see D2).

## Deviations log (UTC)
- **D1 (in PREREG, 13:26Z):** Phase 2 had not frozen its sample; the hedge-day rule in PREREG replaces "Phase 2's frozen sample". Six-rung ladders only exist from late 2022, so NYC/MDW/MIA start in May 2023.
- **D2 (13:33Z, before any netting number):** the research imputation rule for suppressed ZBP cells (equal spread, ≤ 2 per cell) put most suppressed establishments into the 50+ employee classes: implied employment was ~10× CBP (median CBP/implied 0.10). Replaced by spreading each row's gap over its suppressed cells in proportion to the NAICS's national reported size distribution. Small establishments (national, prior NAICS): 947,087 → 1,109,492; CBP/implied median 0.10 → 1.87 (all-industry check 0.98). Both rules are in `src/wi/population/zbp.py`.
- **D3 (13:35Z):** TTN's GHCN record is continuous only from 1998; filled before that from NE Philadelphia (PNE, 27.7 km) plus a monthly offset, like MDW from ORD. O'Hare starts in 1958, so the joint five-station history starts in 1959, not 1951. The residual network reaches quorum only from 1997-1999, so the two-leg capital uses 2000-2025 (26 seasons; 1999 dropped for gaps), the station-leg capital 1959-2025, and the M5 backtest model uses 1999-2020 joint days.
- **D4 (13:40Z):** (a) EWR/TTN have no May-August auction days; their average book in those months = the station's (pool position ÷ net hedger demand) ratio from September × that month's net demand. (b) The house capital charge's co-ES is computed on the "house absorbs all net demand" book, because the actual book is an output of the auction.
- **D5 (13:41Z, seat request after Phase 2):** added the climatology-priced capital sensitivity (cover priced before the forecast is known). It is not in the headline M3 number; station-leg-only CPC is 0.36 under it.
- **D6 (13:43-13:44Z, after seeing the NYC residual markout):** added two residual fair-value sensitivities (ladder-conditional with metro-minus-station deltas; trailing 5 years). The pre-registered rule stays primary.
- **D7 (13:46Z):** plan 01-04 wrote nClimGrid prelim vintages during the run, so the prelim-vs-scaled measurement was added as the plan allows (descriptive; M4 is CLI only).
- Workers cannot commit, so PREREG carries the priors' sha256 and the UTC freeze time instead of a git hash.
