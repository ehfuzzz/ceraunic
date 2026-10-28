# Junior return and premium split (EVAL-04 add-on)

Run 2026-09-30T14:26:00Z by `uv run python scripts/eval04_junior.py` (deterministic, seed 20260930). Rules frozen in `PREREG-junior.md` at 14:23Z, before any number. All numbers are in `junior_returns.json`.

## Method

- Junior capital J0 = $206,315 (handoff `junior_ES95_30d_usd`); senior S0 = C_30 − J0 = $205,793.
- The SPEC waterfall on Phase 4's book: station-leg house fills are policies the pool writes (premium in, payout out). Residual-leg fills and the Kalshi hedge are the house's trades for the pool (§8.6): all their P&L goes to junior, none to senior.
- Premium per $1 scalar unit = the clearing price p* when the house sells cover, 1 − p* when it buys (SPEC writes that as a put with payout UNIT − L(x)). Risk margin = premium − expected payout at the house's fair value (`mu_s`).
- Treasury = 10 % or 20 % of the station risk margin. Senior = 20 % of (premium − treasury) under SPEC. Junior = the rest, plus residual and hedge P&L, minus payouts.
- Sensitivity B (not SPEC): senior gets 20 % of the kept margin, (1 − t) × risk margin, instead of 20 % of the whole premium.
- Observed seasons: the 2023–2026 Kalshi-era auction simulation (`auction_primary`), and the same with the residual priced off the last five years (`auction_resid_trailing5`).
- Model-based seasons: Phase 4's capital scenario (both legs, 26 seasons 2000–2025, C_30 check $412,109), weather P&L of the average book at fair value, plus the 2023–26 daily means of margin, hedge cost, premium and station margin by calendar month. 10,000 seasons from a calendar-aligned joint-date block bootstrap (7-day blocks). The "1-in-20 season" is the 5th percentile of that distribution: a model number, not something we observed.

## Observed seasons (junior P&L ÷ J0, uncapped)

| rule | 2023 | 2024 | 2025 | 2026 | median | worst | first junior wipe-out (waterfall) |
|---|---|---|---|---|---|---|---|
| primary, spec_t10 | -6% | -92% | -143% | -449% | -118% | -449% | 2025: 2025-08-08, 2026: 2026-06-13 |
| primary, spec_t20 | -8% | -94% | -145% | -451% | -120% | -451% | 2025: 2025-08-07, 2026: 2026-06-13 |
| primary, margin_t10 | +123% | +97% | +159% | -65% | +110% | -65% | none |
| primary, margin_t20 | +122% | +96% | +157% | -67% | +109% | -67% | none |
| resid trailing-5, spec_t10 | -58% | -147% | -215% | -495% | -181% | -495% | 2024: 2024-07-20, 2025: 2025-06-29, 2026: 2026-06-08 |
| resid trailing-5, spec_t20 | -59% | -149% | -217% | -497% | -183% | -497% | 2024: 2024-07-20, 2025: 2025-06-29, 2026: 2026-06-08 |
| resid trailing-5, margin_t10 | +72% | +42% | +87% | -111% | +57% | -111% | 2026: 2026-09-11 |
| resid trailing-5, margin_t20 | +71% | +41% | +86% | -113% | +56% | -113% | 2026: 2026-09-11 |

## Model-based seasons (junior P&L ÷ J0)

| rule | median | 1-in-20 (p5) | p1 | worst of 10,000 | worst of the historical seasons | 3-season sum, p5 | 1-in-20 positive over 3 years? |
|---|---|---|---|---|---|---|---|
| spec_t10 | -214% | -401% | -475% | -596% | -589% (2009) | -961% | no |
| spec_t20 | -216% | -403% | -476% | -598% | -591% (2009) | -966% | no |
| margin_t10 | +43% | -144% | -218% | -339% | -332% (2009) | -190% | no |
| margin_t20 | +41% | -146% | -219% | -341% | -333% (2009) | -195% | no |

Block-length sensitivity (deviation D1): median / 1-in-20 / 3-season p5.

| rule | 7-day blocks (primary) | 30-day blocks | whole seasons (resample the 26) |
|---|---|---|---|
| spec_t10 | -214% / -401% / -961% | -212% / -418% / -999% | -183% / -550% / -1192% |
| spec_t20 | -216% / -403% / -966% | -213% / -420% / -1004% | -184% / -551% / -1197% |
| margin_t10 | +43% / -144% / -190% | +45% / -161% / -228% | +74% / -293% / -421% |
| margin_t20 | +41% / -146% / -195% | +44% / -163% / -232% | +73% / -294% / -425% |

## Premium split, mean observed season (primary run)

Station premium the pool wrote: $2,632,542 a season; risk margin inside it $39,839 (1.5 % of premium). The 10 bps notional fee, paid on top, is $5,420.

| rule | treasury | senior | junior (before payouts) | senior ÷ S0 |
|---|---|---|---|---|
| spec_t10 | $3,984 (0.15 %) | $525,712 (19.97 %) | $2,102,846 (79.88 %) | +255% |
| spec_t20 | $7,968 (0.30 %) | $524,915 (19.94 %) | $2,099,659 (79.76 %) | +255% |
| margin_t10 | $3,984 (0.15 %) | $7,171 (0.27 %) | $2,621,387 (99.58 %) | +3% |
| margin_t20 | $7,968 (0.30 %) | $6,374 (0.24 %) | $2,618,200 (99.46 %) | +3% |

## What it says

- Under SPEC as written, senior's 20 % comes out of the whole premium ($2,632,542 a season on the simulated book), while the margin inside that premium is $39,839 (1.5 %). Senior would collect about $525,712 a season on $205,793 of capital (+255%), paid by the junior. The junior loses money in all four observed seasons (-6%, -92%, -143%, -449%) and in 97 % of modelled seasons (median -214%). A day-ahead book priced close to fair can't pay senior a share of gross premium; `seniorPremiumBps` has to apply to margin, or senior needs a different rule.
- With senior on 20 % of the kept margin (sensitivity B, 10 % cut), the junior's modelled median season is +43%, the 1-in-20 season -144% (7-day blocks; -293% resampling whole seasons), and the worst of the 26 historical seasons -332% (2009). Below −100 % the junior is gone and senior pays.
- The 14-RESEARCH test (1-in-20 junior return positive over three seasons) fails under every split: the 3-season p5 is -190%. Passing it needs about $177,226 a season of junior income before weather ($335,955 with whole-season resampling), against $46,611 now: a much bigger risk load, a smaller book per dollar of junior, or both.
- Observed 2023–26 under B (10 % cut): +123%, +97%, +159%, -65%; with the residual priced off five years: +72%, +42%, +87%, -111%. Three good seasons and one bad one; four seasons is a small sample next to 26.
- The treasury cut barely matters: 10 points of a margin this thin is about $4k a season. The senior rule and the size of the risk load are what matter.
- A season can lose more than the 30-day capital: modelled season weather losses reach $731,394 (2009) against C_30 of $412k. C_30 is a 30-day number; the halt rules (SPEC C2) are what stop a bad season from running on.

## Assumptions (with source keys)

- Premium per scalar unit = p* (house offer) or 1 − p* (house bid); source `data/cache/eval04/auction_primary.parquet` columns `p_star`, `house_bid`, `house_off`; SPEC §6.4 put payout.
- Expected payout at the house fair value `mu_s` (same file); risk margin = premium − expected payout.
- Residual house fills and the Kalshi hedge are house deployment (§8.6), not policies: no senior share. Counting residual fills as policies would add their premium (about $2.5M a season) to senior's base.
- Treasury cut applies to station risk margin only (SPEC §11 `feeMarginBps`; auction fee 0). The 10 bps notional fee is paid by hedgers on top of p*, as in Phase 4's `fees.bps10`.
- Junior J0 = handoff `junior_ES95_30d_usd`; senior S0 = handoff `C30_usd` − J0 (the capital stack of the simulated book, not a pilot).
- Model-based deterministic terms (margin, hedge cost, premium, station margin) = 2023–26 daily means by calendar month from `auction_primary.parquet`; the premium does not move with the weather in the bootstrap.
- Model-based weather P&L = Phase 4's capital matrix (`proxy_bundle` fit 1951–2025 detrended, `average_book`, `unit_matrices`), both legs, seasons with ≤ 5 missing book days; the brief's "1951–2025" history is 1999–2025 for the two-leg book (Phase 4 D3).
- No collateral yield on idle USDC is counted (14-RESEARCH rule 4 wants it as a separate line; none is assumed).

## Caveats

- Everything rests on Phase 4's simulated book: 2 % participation, low-confidence sector priors, 5-unit Kalshi hedge.
- Returns are over J0 for a whole season and are not floored; below −100 % means the junior is gone and senior paid the rest (the waterfall column shows the date). SPEC C2 would halt new risk at that point, so later days would not happen.
- The model-based distribution uses persistence-forecast pricing, which Phase 4's backtest found conservative against Kalshi (M5). It is a model, not a record.
- Bootstrap blocks keep all stations on the same date (joint shocks) but break the within-season persistence past 7 days.
- The observed primary seasons carry the Central Park residual pricing artefact (Phase 4 D6); the trailing-5 run is the cleaner read.

## Deviations

- D1 (2026-09-30 14:25Z, after the first run at 14:24Z): added 30-day and whole-season block lengths as sensitivities, because 7-day blocks cut the season-long persistence of the weather P&L and the historical seasons had a fatter left tail than the 7-day bootstrap. The 7-day result stays primary.
- D2: added `junior_income_needed_per_season_for_rule_usd` (−p5 of the 3-season weather sum ÷ 3) to say how far the split is from the 14-RESEARCH test.
