# Phase 4 summary: netting and pool economics (EVAL-04 / EVAL-05)

Run 2026-09-30 13:31Z-13:49Z worker. PREREG frozen at 13:26:00Z, before any number (priors sha256 7c5de5b1...). Reproduce with `uv run python scripts/eval04.py --all` (about 30 s, deterministic).

## Verdicts
| ID | Result | Verdict |
|---|---|---|
| M1 netting ratio ≥ 0.25 at ≥ 3 of 5 stations | NYC 0.36, MDW 0.32, MIA 0.65; EWR 0.21, TTN 0.13 (Sept 2026 only); pooled 0.40 | MATERIAL (3 of 5, the minimum) |
| M2 null NR < 0.10 | pooled 0.019 | The pitch must not lead with netting |
| M3 C_30 / pool notional ≤ 0.35 | 0.126 (C_30 $412k); station leg alone 0.25; climatology-priced station leg 0.36 | LEVERAGE STORY HOLDS (fragile) |
| M4 CLI revision ≤ 2 % of units | 0 of 4,573 station-days | ACCEPTABLE |
| M5 Kupiec, 1-day VaR99 | 1 exceedance in 599 days (6 expected), p = 0.011 | REJECTED: model too conservative |

## Headline numbers (handoff.json)
- Capital, pooled five-station book, both legs, h = 30: C = $412k (binding: worst historical window; ES99 $269k; full collateral $1.66M). C/notional 0.126, C/full collateral 0.25, C per $ of gross hedger cover 0.067. Junior (ES95) $206k = 50 % of C.
- h = 1 / 5 / 30: C = $35k / $128k / $412k.
- Fees per $ hedger notional: 10 bps → $22k a season; 50 bps → $112k; CoW-style 50 % of improvement → 0.40 % of notional, $90k a season.
- House P&L after the 5-unit Kalshi hedge: +$1,154/day pooled, but +$1,062 of it is the NYC residual priced on long climatology (Central Park's cool bias against its neighbours moved ~1 °F in the 1990s and ~0.7 °F since 2020). Trailing-5-year residual pricing: +$384/day. Station legs net about zero (+$94/day): house loses at NYC/EWR/TTN, wins at MDW/MIA, following the Kalshi mid's bias per city.
- Leftover the pool carries at 2 % participation: NYC ~4,400 $1/°F units a day ($26k max payout); Kalshi depth covers 5.
- Revision: CLI clean at D+1 12:00Z (8 days lacked a final report by then). nClimGrid prelim at D+5 vs scaled moves Tmax ≥ 0.5 °F on 64 % of cell-days and flips the wet flag on 2.9 %: grid legs must settle on the scaled file.
- Rain netting ≈ 0 (almost every sector loses on wet days). ZIP-level netting is about half the station level.

## Phase 2 forecast-level risk (seat message)
Included as a sensitivity row, not in the headline: pricing the cover at climatology before the forecast is known raises the station-leg C_30 from $416k to $597k (C/notional 0.25 → 0.36, over the M3 line) and the two-leg C_30 to $577k (0.18). Phase 6 should read M3 as holding only if the cover is repriced daily off the forecast.

## Files
- reports/eval-04-05/{PREREG.md, priors_2026-09-30.csv, results.json, tables.md, RESULTS.md, handoff.json, figures/*.png}
- src/wi/auction/clear.py (THE clearing rule; matches contracts/src/BatchAuction.sol line for line on price, tb/to and the `ahead` slice)
- src/wi/population/{zbp,revenue,stations}.py, src/wi/exposure/{priors,hedge}.py, src/wi/pool/{scenarios,capital,quote,markout,sim,kalshi_leg}.py, src/wi/oracle/revision.py
- scripts/eval04.py; tests/test_clear_money.py (4,000-book property + 08-RESEARCH hand case), tests/test_eval04_lookahead.py
- data/manifests/{eval04.md, eval04-sources.csv}; raw pulls 106.5 MB (census, ghcnd_eval04, iem_afos_cli)

## Deviations (full log in RESULTS.md)
D1 hedge-day sample rule in place of Phase 2's frozen sample (six-rung ladders start late 2022). D2 ZBP suppressed-cell imputation replaced (research rule pushed ~10× employment into 50+ classes), before any netting number. D3 TTN filled from PNE before 1998; joint history starts 1959; residual network quorum only from ~1999, so the two-leg capital uses 26 seasons. D4 EWR/TTN May-Aug book by ratio; house co-ES on the absorb-all book. D5 climatology-priced sensitivity (seat). D6 residual fair-value sensitivities after seeing the NYC markout. D7 nClimGrid vintages measured once 01-04 landed.

## For Phase 7
Residual fair value must use a recent window (or ladder + recent offset), not long climatology. Capital charge at CoC 15 % is under one scalar tick, so house spread is tick-bound. Capacity never bound at 2 % participation with $250k/day.
