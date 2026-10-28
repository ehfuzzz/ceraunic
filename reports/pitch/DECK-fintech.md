# Deck outline: fintech and insurtech funds

*weather-insurance (codename), Phase 16 deck outline, 30 September 2026. Audience: fintech and insurtech funds. The product and the numbers lead, then the legal route; the token is secondary. 15 slides. Slides tagged `[shared S-x]` are word-for-word the same in both decks; edit them in both or neither.*

**Source shorthand** (every number on a slide names one of these):
- **E1** = `reports/eval-01/results.json` (Phase 2, station hedge quality)
- **E45** = `reports/eval-04-05/results.json`, **H** = `reports/eval-04-05/handoff.json`, **J** = `reports/eval-04-05/junior_returns.json` (Phase 4, netting, capital, junior returns)
- **RB** = `reports/eval-04-05/rain_book.json` (Phase 4 rain extension, weekly two-leg rain book; rules in `reports/eval-04-05/PREREG-rain.md`)
- **TR** = `reports/eval-01/trace_kxrain_2026.json` (how the 216 settled 2026 KXRAIN markets treated trace, measurable and dry days; method in `trace_kxrain_2026.md`); **RS** = `.planning/phases/13-hosted-demo/13-RAIN-SUMMARY.md` (rain cover on the demo)
- **E6** = `reports/eval-06/results.json` (Phase 5, learning a business's sensitivity)
- **E03** = `reports/eval-03/results.json` (Phase 3, geography basis and the residual bake-off; rules in `reports/eval-03/PREREG.md`)
- **EVAL** = `reports/EVALUATION.md` (section given); **M14** = `reports/pitch/14-TOKEN-POOL-MEMO.md`; **M15** = `reports/pitch/15-LEGAL-OPTIONS-MEMO.md`
- **S07 / S08 / S09 / S10 / S12** = the phase SUMMARY files in `.planning/phases/` (what was built and how it was checked)
- **PREREG** = the pre-registered threshold in that phase's `PREREG.md`, written before any number existed
- "post hoc" means the cut was chosen after seeing results; it is never a verdict.

**Rules the seat keeps while rendering:** owner's voice (memory `owner-writing-style`), no banned words, no traction we don't have, no "45 pools"-style inflation. Kalshi is named only as the hedge venue. Naming Kalshi in a deck that goes out may need Kalshi's written OK (Developer Agreement v1.1 §6.4), and pricing a commercial product off Kalshi data needs a data licence (M15 §6, Q13). The owner asks Kalshi before any deck is sent; agents contact no one. The lines that waited on Phase 3 were filled from E03 on 30 September 2026, with the seat's rulings of that day on what ships.

---

## Slide 1 · Weather cover for small businesses, paid from the public weather record

- **Message:** A small business picks a payout tied to the temperature or rain near it, pays a premium, and gets paid automatically when the official weather number crosses the line, with no claim to file.
- **On the slide:**
  - Working prototype in simulation. No customers and no real money yet.
  - Pre-seed, roughly $500k to $1.5M.
- **Evidence:**
  - Status: `.planning/PROJECT.md` (Out of Scope); M15 §1 "Status"
  - The ask: `.planning/OWNER-RULINGS.md` ("The ask")
- **Visual:** `reports/demo/screenshots/11-policy-settled.png` (one policy, day-by-day readings from the NWS climate report and the payout each day).
- **Say it:** I'll walk you through what the business sees, what our numbers say, what failed, and what we'd do with the money.

## Slide 2 · Weather moves small-business sales, and nobody sells them simple cover

- **Message:** A café or ice cream shop has real weather risk, but bespoke weather cover is priced for big buyers, and the one small-business attempt we know of died on demand and underwriting cost.
- **On the slide:**
  - An ice cream shop does well on hot days and loses on cool, rainy ones. A café can be the opposite.
  - Bespoke cover has high minimums: one provider's minimum premium is usually $50,000.
  - Small parametric cover can be sold: a filed tornado policy on an NWS trigger sells for about $88 a year in 15 states. Nobody does it for daily heat or rain yet, as far as we found.
- **Evidence:**
  - $50,000 minimum premium (Descartes, 25 Jun 2025) and the Sola tornado policy (about $88 a year, secondary source, Artemis 31 Aug 2023): M15 §7
  - WeatherBill (later Climate Corp) small-business product died on demand and analyst cost: `.planning/PROJECT.md` Context, prior art
- **Visual:** Draw: a week of a shop's sales with the rainy days marked. No file exists; don't use real merchant data.
- **Say it:** The reason this doesn't exist isn't that the risk is fake. It's that writing a custom contract for a café costs more than the café would pay. So the question is whether we can price it from public data and liquid contracts instead of analysts.

## Slide 3 · What the business sees

- **Message:** Upload a year of daily sales or connect Square, see how the weather has moved them, pick a cover, buy it, and watch it settle day by day on the official climate report.
- **On the slide:**
  - The portal estimates how heat and rain move your sales and says plainly that it's advice, not a promise.
  - It shows two ways to buy with every price broken out: the station part, the local part, fees, and the most it can pay.
  - Each day settles on the NWS climate report, and the reporter publishes a hash of the data release (it is not yet part of the signed report).
- **Evidence:**
  - Portal flow and the money check in the end-to-end smoke (balance after settlement = start − premium + payouts, to the cent, on demo data): S10
  - Square connect: acceptance A1-A4 pass on 107k recorded Square orders with zero network calls; live sandbox waits on the owner's Square token: S12
  - Elasticity shown as advisory only: E6 `priors.json` `advisory_only: true`; `05-SEAT-RULINGS.md` ruling 4
- **Visual:** Three screenshots in a row: `reports/demo/screenshots/06-sales-elasticity.png`, `07-recommend-quotes.png`, `11-policy-settled.png`. Caption the "Expected hedge fit" lines (5% and 7%) as a demo-data estimate, not evidence.
- **Say it:** The whole point is that the owner of a shop never has to understand a weather contract. They see a line, a price and a payout. The 'hedge fit' number on these screens comes from demo data; the real evidence is on the next slides.

## Slide 4 · How we pay for it

- **Message:** Most of the payout is backed by liquid station contracts, a small local contract covers the gap between the station and the shop, and a capitalised pool carries what's left.
- **On the slide:**
  - Default: the business buys one fixed-price policy and the house hedges the station part every day.
  - Fallback: the business buys the station contracts itself and we sell only the local gap.
  - We made the house-hedge path the default because of the next two slides: a day ahead, the station contracts only hedge the forecast miss.
- **Evidence:**
  - Both paths and the default: `.planning/OWNER-RULINGS.md` (hedge leg); M15 §1
  - Why the default carries forecast risk: EVAL §10
- **Visual:** Draw the flow: business → one policy → (station leg hedged by the house) + (local gap → residual auction → pool). Inset: `reports/demo/screenshots/07-recommend-quotes.png` ("We handle the hedge" vs "You place the Kalshi part").
- **Say it:** Think of it as a small insurer that happens to have a very good, very cheap hedge for most of its risk, and a pool for the rest. I say 'insurer' loosely; whether it legally is one is slide 12.

## Slide 5 · The station contracts pay when they should `[shared S-A]`

- **Message:** Kalshi's daily high-temperature contracts, bought as a set, pay out in line with a simple heat payout at the weather station: they track 0.95 of the variance, and about the same in every year since 2022.
- **On the slide:**
  - Hedge effectiveness 0.95 [0.95, 0.96] over 4,462 city-days in New York, Chicago and Miami.
  - The settled number matched the official NWS climate report on all but 0.2% of 3,822 days.
  - The Newark and Trenton contracts are too thin to use a day ahead: 241% and 266% over fair value.
- **Evidence:**
  - 0.95 [0.95, 0.96]: E1 `temperature.pooled[rule=A,h=24,pool=liquid NY+CHI+MIA].he_cover.est` (CI `.he_cover`); 4,462: same row `.n_citydays`
  - 0.2% of 3,822: E1 `mismatch[city=all,settle_source=all].value_mismatch_share` and `.n`
  - 241% / 266%: E1 `verdicts.T2.EWR.overround`, `verdicts.T2.TTN.overround` (34 city-days each, `meta.n_citydays.EWR`)
- **Visual:** `reports/figures/fig1_he_by_year.png` (HE_cover and HE_ladder by city-year; highlight the HE_cover bars on this slide, the HE_ladder bars carry the next one).
- **Say it:** This is the part that works. If you run a shop near Central Park, Midway or Miami airport, there's already a liquid contract that pays on the number you care about, and the official number it settles on is clean. The catch is on the next slide.

## Slide 6 · A day ahead, you're paying for the forecast `[shared S-B]`

- **Message:** Bought 24 hours before the close, the price already contains tomorrow's forecast, so a buyer only hedges the forecast miss: 0.37 of the variance on 2025-26 days, and worse than doing nothing over all years.
- **On the slide:**
  - Counting the price paid, hedge effectiveness is 0.37 [0.33, 0.42] on 2025+ days and −0.32 over 2022-26.
  - Our pre-registered price test failed: 24.6% over fair value against a 20% bar.
  - Today's market is cheaper, 9.7% on 2025+ days, but we picked that window after seeing the numbers.
- **Evidence:**
  - 0.37 [0.33, 0.42]: E1 `temperature.pooled[rule=A,h=24,pool=liquid 2025+ (post-hoc)].he_ladder.est` (post hoc, deviation 6)
  - −0.32: E1 `temperature.pooled[rule=A,h=24,pool=liquid NY+CHI+MIA].he_ladder.est`
  - 24.6% vs 20%: E1 `temperature.pooled[rule=A,h=24,pool=liquid NY+CHI+MIA].overround.est` against PREREG `reports/eval-01/PREREG.md` §7 T1; verdict E1 `verdicts.T1` = FAIL
  - 9.7%: E1 `temperature.pooled[rule=A,h=24,pool=liquid 2025+ (post-hoc)].overround.est` (post hoc)
- **Visual:** `reports/figures/fig2_overround_by_year.png` (overround by city-year, dashed line = the 20% bar); optionally the HE_ladder bars of `fig1_he_by_year.png`.
- **Say it:** This is the number that changed the product. A business that buys the contracts itself a day ahead gets 0.37, not 0.95. So the default has to be one fixed-price policy where the house hedges every day, and that makes us the ones carrying the forecast risk. We're a capitalised pool that uses Kalshi for pricing and some hedging, not a pass-through.

## Slide 7 · Rain is the cleanest first product

- **Message:** Kalshi's daily rain market forecasts far better than climatology and costs about 20% over fair value, so rain-day cover is the cleanest to explain and price, and the cover pays on the same rule the contract settles on. It is also the hardest to lay off: the pool carries it.
- **On the slide:**
  - The market's day-ahead Brier score is 0.106 against 0.247 for climatology, a pre-registered pass.
  - It costs $1.20 per $1 of payout a day ahead, fees included. For a wet-day exposure it tracks 0.83 of the variance, 0.27 counting the price.
  - Kalshi's daily rain contract pays only on measurable rain (0.01 in or more), and our rain cover uses the same rule, so the hedge matches the cover on every day: all 216 settled 2026 KXRAIN markets in NYC, Chicago and Miami settled that way.
  - The catch: rain does not net (0.003), and Kalshi's daily rain markets are about 300 times too thin to lay it off, so a rain book is the pool's own risk. That is about $1.08M of 30-day capital at 2% take-up, and the junior layer loses money in a bad year.
- **Evidence:**
  - 0.106 vs 0.247: E1 `rain_daily.horizons.24.brier_market`, `.brier_clim`; T3 PASS (gain 0.141)
  - $1.20: E1 `rain_daily.horizons.24.cost_per_dollar_payout`; 0.83 / 0.27: E1 `rain_daily.horizons.24.he_wet.he_cover.est`, `.he_wet.he_ladder.est`
  - Sensitivity with the rule the product uses (trace = dry), labelled, primary unchanged: HE_cover 0.76 and HE_ladder 0.23 (primary 0.83 and 0.27), Brier gain 0.143 (primary 0.141), market Brier 0.106 unchanged: `reports/eval-01/sensitivity_trace_dry.json` `rain_daily_dry.horizons.24.he_wet.he_cover.est`, `.he_wet.he_ladder.est`, `.brier_gain`, `.brier_market`; run note `reports/eval-01/sensitivity_trace_dry.md`
  - 216 markets, 15 Jul to 29 Sep 2026: TR `settled_markets`; trace 26 days, none YES (TR `trace_days`, `trace_yes`); measurable 94 days, all YES (`measurable_days`, `measurable_yes`); dry 96 days, all NO (`dry_days`, `dry_no`); the 0.01 in rule: RS ("Trace flip"). The 62% all-series trace figure (E1 `rain_daily.trace_yes_share`) pools the older KXRAINNYC series and does not describe KXRAIN
  - 0.003: RB `netting.central.pooled`; about 300×: Σ RB `depth.by_city.<ST>.mean_net_short_contracts` (205,019) ÷ Σ `.depth_proxy` (704) = 291, a volume proxy because no daily-rain order book is on file (EVAL §7)
  - $1.08M: RB `capital.two_leg_joint.H30.C` (2024-26; 2% take-up is the Phase 4 participation; 32-month history); junior: RB `junior.model_MaySep.splits.margin_t10.median` +12%, `.p05_1in20` −147%; three-season test RB `R5.margin_t10.verdict` FAIL, and FAIL on all four splits (modelled; the two observed years, mostly New York, were positive)
  - The rain book's history counted trace as wet and was not rerun; its verdicts (no netting, depth about 300× too thin, junior fails) do not turn on trace days (EVAL §11)
- **Visual:** `reports/figures/fig3_rain_brier.png` (market vs climatology Brier by horizon).
- **Say it:** If I had to sell one thing to a café next month, it would be 'we pay you on rainy days'. It's easy to explain and the market prices it well. What we still don't know is whether a café's sales drop enough on rainy days to make the cover worth its price. And the honest catch: rain doesn't net, and the market is far too thin to lay it off, so we'd be carrying that risk ourselves, and on our current numbers the first-loss money doesn't survive a bad year.

## Slide 8 · Learning a shop's weather sensitivity failed on public stand-ins `[shared S-E]`

- **Message:** We tried to learn weather sensitivity from a year of daily demand on public datasets and it missed our bar; these are bike, transit and taxi counts, not a shop's sales, so the café question is still open.
- **On the slide:**
  - Out of sample, the learned hedge removed 7% (New York bikeshare) and 5% (Chicago bikeshare) of daily revenue surprise, against a 20% bar. Transit and taxi got about nothing.
  - At real day-ahead prices, the New York bike hedge kept 0.006.
  - The rain effect is real and precise, about −10.5% on wet days for Citi Bike. The heat leg didn't fit.
- **Evidence:**
  - 7% / 5%: E6 `verdicts.T2.G1.heat_rain_median` (0.072), `verdicts.T2.G2.heat_rain_median` (0.053); 20% bar: PREREG `reports/eval-06/PREREG.md` §8 T2; verdict FAIL for both
  - 0.006: E6 `verdicts.T3.G1.ladder_median`
  - −10.5%: E6 `verdicts.T1.G1.mu_wet`; replication year gives 0.081 and 0.103 (E6 `groups.G1.replication.arms.A3.cover_heat_rain_daily.median`, `groups.G2...`)
  - Seat rulings on this phase were made after the results and are reported as post hoc (`.planning/phases/05-elasticity-learning/05-SEAT-RULINGS.md`)
- **Visual:** `reports/figures/fig6_elasticity.png` (out-of-sample HE of the learned hedge by stand-in group; dashed line = the 0.20 bar).
- **Say it:** Bikeshare is far more weather-driven than a café, so if anything this is an upper bound. That's why the portal shows its estimate as advice only, and why we can't tell you a learned hedge beats doing nothing. The only way to answer the real question is real sales from real shops. That's the pilot.

## Slide 9 · The pool is the business, not the matching `[shared S-C]`

- **Message:** Businesses with opposite exposure do cancel some risk, but not much, and the station contracts are far too thin to absorb the rest, so a capitalised pool carries most of what we sell.
- **On the slide:**
  - In our simulation (2% of small businesses near five stations hedging every warm-season day), about 4,426 units a day are left over around Central Park. Our paper hedge was capped at 5 a day; one real order-book snapshot supported 33 near the best price.
  - Under our own sector guesses, 40% of hedge units cancel inside one station's daily auction. If businesses mostly react to weather the same way, it's 1.9%.
  - So pricing and capital don't count on netting at all.
- **Evidence:**
  - 4,426: E45 `netting.leftover_units_per_day.NYC.mean_units`; 2% and the 5-unit cap: PREREG `reports/eval-04-05/PREREG.md` fixed choices
  - 33: E1 `depth.ladders.KXHIGHNY-26SEP30.max_units_3c` (one snapshot, 2026-09-29)
  - 40%: E45 `netting.central.pooled`; passes M1 at the minimum, 3 of 5 stations (E45 `verdicts.M1.stations_ge_0p25`)
  - 1.9%: E45 `netting.null.pooled`; M2 verdict: the pitch must not lead with netting
- **Visual:** `reports/figures/fig4_netting.png` (share of hedge units that cancel, central priors vs 1,000 prior draws vs the null).
- **Say it:** Before we ran this, we wrote down that if netting in the 'everyone moves together' case came in under 10%, we couldn't lead with it. It came in at 1.9%, so we don't. The honest picture is a pool that carries the risk and gets paid a margin for it.

## Slide 10 · Capital: affordable only with daily repricing, and one bad summer can wipe the first-loss layer `[shared S-D]`

- **Message:** The pool needs about 13 cents of capital per dollar of 30-day cover if we reprice every day off the forecast; priced once up front, or measured over a whole summer, it needs more, and in a 1-in-20 summer the junior layer is wiped out.
- **On the slide:**
  - 30-day capital for the two-leg book we modelled is $412k, or 0.126 per dollar of notional, under our 0.35 bar. Heat cover now ships as the station leg alone, which needs $416k, or 0.25 per dollar. Priced before the forecast is known, it needs 0.36, over the bar.
  - The worst modelled summer (2009) loses $731k, so on a season basis it's about 0.22 per dollar. We always quote both horizons.
  - The junior (first-loss) layer is $206k. In a 1-in-20 modelled season it loses 144% of its money: it's gone, and senior money starts paying claims.
- **Evidence:**
  - $412k, 0.126: E45 `verdicts.M3.C30`, `verdicts.M3.CPC`; 0.35 bar: PREREG `reports/eval-04-05/PREREG.md` M3
  - $416k: E45 `capital.deploy_detrended.pooled_station_leg_only.H30.C`; 0.25: H `capital_per_usd_cover_H30.per_usd_pool_notional_station_leg_only`; 0.36: H `capital_per_usd_cover_H30.per_usd_pool_notional_clim_priced_station_only`
  - $731k: J `model.weather_pnl_hist.2009`; 0.22: derived, E45 `verdicts.M3.CPC` × worst season loss ÷ J `model.C30_check` (EVAL Appendix B row 143)
  - $206k: H `junior_ES95_30d_usd`; −144%: J `model.splits.margin_t10.boot_p05_1in20` (−293% resampling whole summers, `.sens_whole_season.p05_1in20`); modelled, not observed
  - Phase 4 ran before the residual test, so its two-leg book uses R-A as the local leg. No heat residual cleared the pre-registered +0.10 bar (E03 `verdicts.winner.temperature` = none; best G1-P +0.061, P-A-IDW +0.052, R-A +0.033 at `bakeoff.temperature.<design>.pooled_median_dhe`), so heat ships station-only with local cover quoted one by one (RFQ) on P-A-IDW. Seat ruling 2026-09-30: no heat capital re-run; the weekly two-leg rain book was sized separately (RB, fintech slide 7)
- **Visual:** `reports/figures/fig5_capital.png` (capital per dollar of notional; orange = priced before the forecast).
- **Say it:** I want to be clear about this one. The capital looks affordable only if we reprice every day. And a 30-day number isn't what a depositor cares about; a whole summer is. By our model, about one summer in twenty wipes out the first-loss money. The halt rules stop new sales when it runs thin, but policies already sold still pay.

## Slide 11 · What's built, and how we checked it `[shared S-F]`

- **Message:** The whole loop runs today in simulation, from sales upload to quote, purchase, auction, settlement and pool accounting, and the same scenario run through the real contracts on a local test chain gives exactly the same money.
- **On the slide:**
  - The reference engine and the Solidity contracts agree to the unit on every shared test case: 64 auction books, 192 payouts, 28 pool sequences, 14 oracle cases. The contracts are hardened: 6 audit findings fixed, 41 Foundry tests.
  - A 3-day New York scenario run through the deployed contracts on a local chain (710 transactions) matches the simulator's money exactly, and a planted tamper is caught.
  - The engine API and portal run in sim mode at public URLs. Square connect works on recorded Square responses. The testnet deploy script is written and waiting for me to run it.
  - The prototype portal sells heat, cool and rain cover today: rain pays a fixed amount for every day the official weather report at the city's Kalshi rain station shows measurable rain (0.01 in or more), the same rule Kalshi's rain contract settles on, so one contract per dollar per day hedges it exactly.
- **Evidence:**
  - Parity counts: S08 (`.planning/phases/08-solidity-contracts/08-SUMMARY.md`), with the pool sequences at 28 after the hardening pass. `forge test` 41 passed and the 6 fixed audit findings: the "Hardening pass (08-HARDEN)" section of `.planning/phases/08-solidity-contracts/08-AUDIT.md`
  - 710 txs, money = `tests/api/golden/scenario_nyc_3d.json`, CHAIN_DIVERGED tamper test: S09
  - Engine fixture run: 3,251 events, 116 policies, conservation 79,000 USDC funded = held: S07, regenerated after the hardening pass (`reports/engine/fixture-run/MANIFEST.json`)
  - Rain cover on the demo, its rule and the hedge match: RS ("Deck line (final)", "Trace flip"); 216 of 216 KXRAIN markets settled on the same rule: TR
  - Square fixtures: acceptance A1-A4 pass on 107k recorded orders, zero network calls: S12 (`12-01-SUMMARY.md`)
  - Engine: https://wi-engine.vercel.app (S09). Portal: https://wi-portal.vercel.app (Phase 13)
- **Visual:** `reports/demo/screenshots/03-seeded-auction-cleared.png` (the seeded LaGuardia-minus-Central-Park auction: 69¢, 20 units, and the conservation check line).
- **Say it:** Everything you'll see is simulated: test dollars, a simulated clock, a simulated chain. The weather readings and Kalshi prices in the demo world are real history from this summer. Nothing is on testnet yet because I run that deploy myself, and nothing is on mainnet.
- **Demo cue:** switch to the live portal here. Follow `reports/pitch/DEMO-WALKTHROUGH.md` (fintech order: Onboard → Coverage → Policies → Pool → Trade), about 5 minutes.

## Slide 12 · The legal fork: swap or insurance `[shared S-H]`

- **Message:** A weather payout with no proof of loss is a swap under US law unless a licensed insurer issues it, so how we sell this is a question for counsel, and nothing goes to mainnet, takes real money or faces a real customer before we have the answer.
- **On the slide:**
  - The Commodity Exchange Act names "a weather swap" in its definition. Selling swaps off-exchange to businesses that aren't eligible contract participants (roughly: under $10M in assets) is unlawful, and many cafés won't clear that bar.
  - An auction where any wallet can trade our contract looks like an unregistered swap trading facility. Polymarket and Opyn were charged on close facts, and blocking US IP addresses wasn't enough.
  - The route we want counsel to test: station and regional legs listed on a regulated exchange; the last-mile gap sold as a carrier-issued parametric policy; the on-chain pool as fully collateralised reinsurance for eligible investors.
- **Evidence:**
  - CEA §1a(47), 17 CFR 1.3 "Swap" para (4), CEA §12(h), §2(e): M15 §2
  - CEA §5h(a)(1); CFTC PR 8478-22 (Polymarket, 3 Jan 2022), PR 8774-23 (Opyn, 7 Sep 2023): M15 §4
  - Three routes to counsel, no lead picked (owner ruling 2026-09-30); the memo's hybrid is one option for counsel to test; the 10 gates before mainnet: M15 §7. Our reading, research for counsel, not legal advice; the memo tags these lines [est.]
- **Visual:** Simplified version of the routes table in M15 §7: three columns (offshore + geo-block / carrier-issued parametric policy / exchange-listed contracts) with our read under each, and an arrow to the hybrid. Draw it; no file exists.
- **Say it:** This is the biggest single unknown, and I'd rather you hear it from me. We haven't picked a route; all three go to counsel and we decide on the answer. Our own reading is that offshore is weakest for us, because every business we'd serve sits near a US station. The open-wallet auction stays in the design until counsel says otherwise.

## Slide 13 · The pool and the token, briefly

- **Message:** The pool is plain USDC with the house's own money losing first; a token comes later, if at all, as junior capital offered to eligible investors under an exemption, and the pilot doesn't need one.
- **On the slide:**
  - Every live policy's maximum payout is set aside before it binds. The house's money takes losses first; outside depositors come later and only if counsel allows.
  - Under the hybrid, the pool becomes collateralised reinsurance behind a licensed carrier, which may take it out of commodity-pool rules.
  - On today's settings the first-loss layer earns +43% in a median modelled season and is wiped out in a 1-in-20 season, so the risk load has to go up.
- **Evidence:**
  - Pool and token design: M14 §2-3; route (ii) and the pool: M15 §5, §7
  - +43% / −144%: J `model.splits.margin_t10.boot_median`, `.boot_p05_1in20` (modelled)
- **Visual:** `reports/demo/screenshots/04-seeded-pool.png` (tranches and "Junior loses first"; the 0.30% senior rate is the v0 parameter, not a result).
- **Say it:** For a fintech investor the token is an option, not the plan. If counsel says the right home is a carrier plus reinsurance, the pool still works, and the token becomes an interest in that vehicle sold to eligible investors.

## Slide 14 · Where it stands: proven, not proven, and what the money buys `[shared S-G]`

- **Message:** We've proven the payout, the settlement data and the machinery; we haven't proven that a café's risk is learnable, that the capital survives a bad summer, that anyone will pay, or that the legal route works, and the raise is for exactly those.
- **On the slide:**
  - **Proven.** The station contracts track the exposure (0.95). The daily rain market forecasts far better than climatology (Brier 0.106 vs 0.247). Settlement data is clean (no payout-moving revision in 4,573 station-days). Rain sensitivity is learnable on bikeshare. The on-chain auction and pool are built with exact engine-to-contract parity (hardened: 6 audit findings fixed, 41 Foundry tests). The rain cover sells on the demo and its hedge matches it day for day (216/216). Portal, Square connect and a live sim demo exist. Within 50 km of a station, the station contract alone covers 0.81 of a nearby heat payout. A weekly rain residual on PRISM grid cells passed our pre-registered test, run on all 26 station pairs (+0.229).
  - **Not proven.** A café's sensitivity on real sales. A day-ahead price that passes our bar. A listed heat residual: none of our designs cleared the bar (best +0.061 against +0.10), so heat cover is the station leg alone. Rain away from the station: the station contract covers only 0.49 of a nearby weekly rain payout, 0.13 in Miami; the weekly rain book isn't built and its station part has no liquid hedge. Junior capital surviving a bad season (our three-season test fails). A rain book the pool can afford (junior fails under every split). Demand: no customers. Nothing on testnet or mainnet. The legal route. "Cheaper than a bespoke contract" was never measured.
  - **What the money buys.** A pilot with real sales from weather-exposed shops, with its test written down first. Counsel's answer on the legal fork. A re-run of the price and depth numbers on our own recorded order books. Testnet, audits, then mainnet only after the counsel gates.
- **Evidence:**
  - 0.95: E1 `temperature.pooled[rule=A,h=24,pool=liquid NY+CHI+MIA].he_cover.est`; 0.106 vs 0.247: E1 `rain_daily.horizons.24.brier_market`, `.brier_clim` (T3 PASS)
  - 0 in 4,573: E45 `verdicts.M4.share` (sample in EVAL §9.3); −10.5% wet effect: E6 `verdicts.T1.G1.mu_wet`
  - Three-season junior test: J `model.splits.margin_t10.three_season_sum_p05` = −190% (rule: M14 §5 item 7)
  - Geography, station leg alone within 50 km: 0.81 [0.78, 0.84] E03 `eval02.temperature.pooled_median_he0` (CI `_ci`); 0.49 [0.38, 0.66] `eval02.rain.pooled_median_he0`; Miami 0.67 / 0.13 `eval02.<var>.by_market.MIA.median_he0`
  - Heat residual: E03 `verdicts.winner.temperature` = none (all fail P1, +0.10 in `reports/eval-03/PREREG.md`); +0.061 `bakeoff.temperature.G1-P.pooled_median_dhe` (37 of 37 pairs since the 2026-10-02 PRISM re-pull; fails P1 and P3), P-A-IDW +0.052 is the reference for RFQ quotes (seat ruling 2026-09-30)
  - Rain residual: E03 `verdicts.winner.rain` = G1-P, +0.229 [0.119, 0.318] `bakeoff.rain.G1-P.pooled_median_dhe` on 26 of 26 pairs (`.n_pairs`; +0.186 on 19 before the 2026-10-02 PRISM re-pull); +0.112 HE [0.032, 0.238] over R-A, the other survivor and the alternate (`verdicts.winner_vs_next_survivor.rain`). Its HE lead over P-A-IDW, which fails P1, is +0.062 with a CI that includes 0 [−0.008, 0.229] (`verdicts.winner_vs_runner_up.rain`). Caveats: the gain sits mostly in May-Sep, PRISM revisions are unmeasured, no liquid hedge for the weekly station leg
  - Rain book: RB `R5.margin_t10.verdict` and the three other splits (`R5.spec_t10`, `.spec_t20`, `.margin_t20`) = FAIL; junior 1-in-20 −147% `junior.model_MaySep.splits.margin_t10.p05_1in20` (modelled); fuller numbers on fintech slide 7
  - Rain cover sells on the demo: RS ("Deck line (final)"); hedge matches day for day, 216 of 216: TR `settled_markets`, with trace 26/0 YES, measurable 94/94 YES, dry 96/96 NO (fintech slide 7)
  - Hardening: `.planning/phases/08-solidity-contracts/08-AUDIT.md` ("Hardening pass (08-HARDEN)"): `forge test` 41 passed, 6 findings fixed
  - Gaps against the brief: EVAL §11 table; re-run on recorded books: `.planning/phases/17-testnet-sandbox-reeval/17-PLAN.md` (17-03)
- **Visual:** Three-column text table (no image). Keep the fails in the same type size as the passes.
- **Say it:** If you remember one slide, make it this one. I'd rather show you what failed than have you find it in the appendix. Most of what's unproven can only be answered with real shops, a lawyer and a season of data, which is what we're raising for.

## Slide 15 · The ask `[shared S-I]`

- **Message:** We're raising a pre-seed of roughly $500k to $1.5M to get counsel's answer, run a pilot on real sales, and take the contracts through audits, going to mainnet only once the legal gates are met.
- **On the slide:**
  - $500k covers about 12 months: counsel's answer, one audit, a pilot with 10-15 businesses and a year of runway.
  - $1M covers about 18 months: a second audit, a pilot with 25-40 businesses and an engineer, enough to show a season of policies settling.
  - $1.5M covers 18-24 months: everything above, plus getting ready for a token (entity, token opinion, KYC, geo-blocking) if counsel clears it, and room to grow the book. The house seed is the pilot book's first-loss target, at most $206k.
  - {{TEAM_LINE}}
- **Evidence:**
  - Uses-of-funds table and totals (about $430-635k / $875k-1.29M / $1.27-1.9M): M14 §7. Audit costs are from published 2026 pricing; counsel, team and pilot figures are my estimates until we get quotes
  - $206k ceiling: H `junior_ES95_30d_usd` (a pilot with a few dozen businesses needs far less)
  - Comparable pre-seed rounds (round sizes only): M14 Appendix B
- **Visual:** The M14 §7 table, three columns, with the totals row in bold. No chart.
- **Say it:** The first dollars go to the things that could kill this: the legal answer and whether real shops' sales move with the weather enough to pay for cover. If either comes back badly, we'll know within a year and we won't have spent the money pretending otherwise.
