# ins1 — Insurance payoffs from Kalshi event-contract ladders (course PDF project 3a)

Pre-registered 2026-09-29 23:40Z (reports/S4-RESULTS.md); results 2026-09-30 00:20Z. Seat-run analysis.

## Setup
- Target payoff per city-day: heat cover H(T) = $1 × min(max(T − K, 0), 6), K = floor of the ladder's second bracket.
- Replicating portfolio: for each bracket contract buy H(bracket midpoint) YES at the YES ask (hourly candle close) 24 h / 12 h / 2 h before close. Top open bracket priced at floor+1. A rung with ask ≥ 99c and bid < 90c counts as "no offer".
- Data: settled `KXHIGHNY`, `KXHIGHCHI`, `KXHIGHMIA` (68 days each, since 2026-07-24), `KXHIGHTEWR`, `KXHIGHTTTN` (34 days); NWS ASOS daily max from IEM (NYC/LGA/JFK, EWR/TTN, MDW/ORD, MIA/FLL/OPF); order books 2026-09-29 for the 09-30 ladders and the insurance-horizon ladders. Re-pull candles with `pull_candles.py` (≈40 MB, not committed).
- Kalshi Chicago settles on Midway (CLIMDW); the market day is the date in the event ticker (Chicago closes 06:00Z, not 03:59Z).

## Results (per $1/°F unit ladder ≈ 19.5 contracts)
| ladder | n | premium@24h | realised payoff | overpay | HE own station | spread cost | binning RMSE | TWC≠NWS |
|---|---|---|---|---|---|---|---|---|
| NYC (Central Park) | 68 | 1.73 | 1.43 | 17% | 0.94 | 0.12 | 0.42 | 0/68 |
| Chicago (Midway) | 68 | 3.14 | 2.93 | 7% | 0.94 | 0.12 | 0.50 | 1/68 |
| Miami | 68 | 4.79 | 4.79 | 0% | 0.86 | 0.14 | 0.51 | 3/68 |
| Newark EWR (thin) | 34 | 8.93 | 2.62 | 241% | 0.96 | 3.69 | 0.44 | 0/34 |
| Trenton TTN (thin) | 33 | 8.87 | 2.42 | 266% | 0.90 | 3.75 | 0.49 | 1/34 |

Geography (exposure at a nearby station hedged with the settlement-station ladder), raw HE → HE after in-sample offset/ratio fit:
LGA 0.21→0.49, JFK 0.13→0.36, TTN-via-EWR 0.46→0.49, EWR-via-TTN −0.06→0.35, ORD-via-MDW 0.64→0.68, FLL 0.08→0.30, OPF 0.46→0.57. Mean station offsets: LGA +1.8°F vs Central Park, FLL −1.1°F vs MIA.

Liquidity (09-29 books, 09-30 ladders): 80–450 contracts per rung within 3c of best ask → ≈ 5–20 units → a policy paying at most ~$30–120 per city-day at ≤3c slippage. Insurance-horizon ladders: monthly rain NYC 20–90c wide, tornado 10–30c wide with 10–50 contracts, Cincinnati HDD ladder empty, hurricane counts 1–2c wide with 500–5,000 contracts.

Horizon: 56% of open weather-market volume closes within 2 days, 37% in 36–120 days (hurricane season counts). 34 series have ≥30-day two-sided ≤10c quotes; all are hurricane/climate/annual, none are local monthly rain/snow/degree-day ladders. No weather series is in the incentive program.

Capital: buyer pays premium only. Seller locks (1 − p) per contract: negligible for daily ladders, ≈0.8c per contract on the 63-day hurricane ladders at 5%/yr, i.e. most of the 1–2c spread.

## Verdicts
- T1 PASS on the three liquid ladders (HE ≥ 0.86, overpay ≤ 17%); FAIL on thin ladders (offers 3.4× payoff at 24 h; only executable at 2 h).
- T2: geography basis dominates (HE 0.1–0.6 vs 0.9 own-station); binning ≈ 10–30% RMSE of mean payoff; settlement source ≤ 4% mismatch; liquidity caps a policy at ~$100/day.
- T3 FAIL for local insurance-grade primitives (only hurricane counts qualify).
- V1 sell-side: NYC +1.5c/contract, CHI +1.1c, MIA 0c all-maker markout; worst day −2.6 to −3.9 per unit (9–19× the daily mean) → a 100-unit book breaches the $150 window cap. NOT KEEP as a bot; note only.
- V2 weather-LP on thin ladders: untested; needs a per-series fair model + multi-week inventory; queued, not now.
- V4 cross-venue: Polymarket Cat-4 landfall 6c / Cat-5 2.6c vs Kalshi ≥1 major hurricane 13–14c ask different questions; no arb.
- V5 course paper: KEEP. This is the 3a evaluation (executable replicating portfolio from bid/ask, error decomposed into binning / geography / settlement source / liquidity / capital) with a 272 city-day sample; extends Luo (SSRN 7138562) from price calibration to executable hedges.
