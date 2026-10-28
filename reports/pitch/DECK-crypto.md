# Deck outline: crypto-native funds

*weather-insurance (codename), Phase 16 deck outline, 30 September 2026. Audience: crypto-native funds. The token and the on-chain pool lead; the evidence shows what the payout and the pool can do, and demand is named as untested. 15 slides. Slides tagged `[shared S-x]` are word-for-word the same in both decks; edit them in both or neither.*

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

## Slide 1 · weather-insurance: weather cover for small businesses, carried by an on-chain pool

- **Message:** We're building a way for a small business to get paid when the weather hurts its sales, with the risk carried by a USDC pool on Hyperliquid's EVM chain and the first loss owned by the pool's token.
- **On the slide:**
  - Working prototype in simulation, contracts ready for testnet (hardened: 6 audit findings fixed, 41 Foundry tests). No customers and nothing on mainnet yet.
  - Pre-seed, roughly $500k to $1.5M.
- **Evidence:**
  - Status: `.planning/PROJECT.md` (Out of Scope, Constraints); M15 §1 "Status"; hardening: `.planning/phases/08-solidity-contracts/08-AUDIT.md` ("Hardening pass (08-HARDEN)")
  - The ask: `.planning/OWNER-RULINGS.md` ("The ask")
- **Visual:** Wordmark only. Optional small inset: `reports/demo/screenshots/11-policy-settled.png` (a policy settling day by day).
- **Say it:** I'll show you what we proved, what failed, and the demo. The short version: the payout works, the pool is the business, and the legal route is the open question.

## Slide 2 · A café loses money on the wrong weather, and the only liquid weather contracts settle at an airport

- **Message:** Small businesses have real weather risk, but the liquid contracts settle at a few official stations and bespoke cover is priced for big buyers.
- **On the slide:**
  - An ice cream shop in Queens does well on hot days and loses on cool, rainy ones. A café can be the opposite.
  - The liquid US weather contracts settle at a handful of stations: Central Park, Midway, Miami airport, Newark, Trenton.
  - Bespoke weather cover exists, but one provider's minimum premium is usually $50,000. The small-business version has been tried before and died on demand and analyst cost.
- **Evidence:**
  - Settlement stations: EVAL §2 (Kalshi series used); `docs/CONVENTIONS.md`
  - $50,000 minimum premium (Descartes, 25 Jun 2025): M15 §7
  - WeatherBill's small-business product (later Climate Corp) died on demand and analyst cost: `.planning/PROJECT.md` Context, prior art
- **Visual:** Draw: a map dot for each of the five settlement stations with a few shop pins around one of them. No file exists.
- **Say it:** The risk is at the shop's door, but the only contracts anyone trades settle at the airport. That gap is what we're trying to close without paying an analyst to write a custom contract for every café.

## Slide 3 · How it works, and why Hyperliquid's EVM chain

- **Message:** A business buys one policy; the house hedges the station part on Kalshi. The gap between the station and the shop is quoted on request for heat (no temperature residual cleared our bar) and for rain the residual is designed to settle weekly on PRISM cells and trade in the daily on-chain batch auction (not built yet), and a USDC pool takes whatever doesn't match.
- **On the slide:**
  - Two ways to buy: we handle the hedge (default), or the business places the station contracts itself and we sell only the local gap.
  - Contracts are ordinary HyperEVM smart contracts, so no HYPE stake is needed. The auction clears in a fixed number of steps, so its worst case (about 480k gas) fits the chain's small 3M-gas blocks. Deploying needs big-block mode once.
  - Whether Hyperliquid users want weather risk is untested.
- **Evidence:**
  - Flow and both paths: M14 §1; M15 §1; `.planning/OWNER-RULINGS.md` (hedge leg)
  - No stake for HyperEVM contracts (the 500k HYPE stake is for native HIP-3/HIP-4 markets only): `.planning/PROJECT.md` Out of Scope
  - clear worst case 479,473 gas under a 3,000,000-gas block; big-block deploys: S08 gas table
  - Untested demand from Hyperliquid users: M14 §8
- **Visual:** Draw the flow: business → policy → (station leg → Kalshi, hedged by the house) + (local gap → residual auction → pool). Inset: `reports/demo/screenshots/07-recommend-quotes.png` (the two paths side by side).
- **Say it:** The chain choice is practical. We don't need a native market or a big stake, just contracts that clear cheaply once a day. The part I can't tell you yet is whether people on Hyperliquid want to hold weather risk; nobody has tested that.

## Slide 4 · The pool, and who loses first

- **Message:** All pool money is USDC in one vault; the house's own money loses first, outside depositors lose only after it's gone, and every live policy's maximum payout is set aside before the policy binds.
- **On the slide:**
  - Junior layer: protocol-owned USDC, seeded by the house, then retained premium. It takes every loss first and all the hedge profit or loss.
  - Senior layer: outside stablecoin depositors, later, and only if counsel allows. Senior gets about a fifth of the margin we keep, not a fifth of the premium.
  - The house trades only as the pool's agent, its wallet returns or writes off each day's money within the 10-day window, and both books are published.
- **Evidence:**
  - Waterfall and premium split (fee 10 bps of notional plus 10% of risk margin; senior 0.3% of premium net of the treasury fee ≈ 20% of kept margin): M14 §2; seat ruling 2026-09-30 14:40Z in `.planning/phases/07-protocol-spec-engine/07-CONTEXT.md` addenda
  - Junior-first holds in the contracts across 256 invariant runs (`invariant_juniorFirst`) and in the engine on random pool sequences: S08, S07
  - Why senior shares margin, not premium: under the first rule junior lost money in all four simulated seasons (J `observed.primary.spec_t10.by_season.*.junior_return`)
- **Visual:** `reports/demo/screenshots/04-seeded-pool.png` (tranche block and "Junior loses first" text) next to the waterfall diagram from M14 §2. Its senior rate, 0.30%, is the v0 parameter (SPEC §17), not a measured return.
- **Say it:** Our first draft paid senior 20% of the whole premium, and the junior layer lost money every season, because on this product the premium is almost all expected payout. So senior now shares the margin we keep. That's the kind of thing the simulation is for.

## Slide 5 · What the token is, and what it isn't

- **Message:** WI is how you own the first-loss layer: staked WI is burned in proportion to junior losses, and the design lets it vote on the pool's risk settings inside fixed ranges with a delay (not built yet; in v0 an owner key sets the parameters); it never pays a claim, has a fixed supply and no emissions, and in the first version stakers earn nothing.
- **On the slide:**
  - Claims are paid in USDC. We never sell our own token into a falling market to pay one.
  - If the junior layer loses 10% on a day, every staked position is cut 10% (capped at 30% a day) and the cut WI is burned. The cut follows dollars lost, so there's no WI price feed to manipulate.
  - What stakers earn is for counsel to decide. The pilot doesn't need a token at all. We describe WI as junior capital in a pool, offered only to eligible investors under an exemption.
- **Evidence:**
  - Token rules: M14 §3; 30% daily cap: M14 §3; 12-day unstake cooldown: seat ruling in `07-CONTEXT.md` addendum 14:24Z
  - Fixed supply, burnable, no mint role; the local-chain end-to-end run burns 5,940 WI on a loss day, including shares in cooldown: S08
  - "Rights to future income" (SEC + CFTC, 17 Mar 2026) and the required wording: M15 §5
  - Design lessons (Aave's own-token backstop, Nexus burns, Maple exits, BarnBridge tranches): M14 §4, Appendix A
- **Visual:** Bullet diagram from M14 §2 ("staked WI is cut in proportion to what the junior layer lost that day"). Optional: the WI staking panel from the Phase 13 pool screenshot.
- **Say it:** Every rule here comes from a protocol that got hurt. Aave dropped its own-token backstop because a loss meant selling the token into a crash. Maple's stakers left right before a default. So the money is USDC, the token is burned instead of sold, and you can't unstake ahead of a heatwave everyone can see coming. We won't pitch staking as a way to make money. Right now it earns nothing.

## Slide 6 · The station contracts pay when they should `[shared S-A]`

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

## Slide 7 · A day ahead, you're paying for the forecast `[shared S-B]`

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

## Slide 8 · The pool is the business, not the matching `[shared S-C]`

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

## Slide 9 · Capital: affordable only with daily repricing, and one bad summer can wipe the first-loss layer `[shared S-D]`

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

## Slide 10 · What the first-loss layer earns, and why it isn't good enough yet

- **Message:** This is what a staker would care about: the median modelled season earns 43% on the junior money, but a 1-in-20 season wipes it out and our own three-season test fails, so the risk load has to go up.
- **On the slide:**
  - Simulated on real Kalshi prices, 2023 / 2024 / 2025 / 2026: +123% / +97% / +159% / −65%.
  - Modelled over 26 past summers: median +43%, 1-in-20 −144% (−293% if you resample whole summers), worst (2009) −332%.
  - To pass our test the junior layer needs about $177k a season of kept margin. It keeps about $47k now. The fix is a bigger risk load, a smaller book per junior dollar, or both, and the pilot has to show whether businesses pay for that.
- **Evidence:**
  - Observed seasons: J `observed.primary.margin_t10.by_season.{2023..2026}.junior_return`
  - Median / 1-in-20 / whole-summer / worst: J `model.splits.margin_t10.boot_median`, `.boot_p05_1in20`, `.sens_whole_season.p05_1in20`, `.hist_worst`
  - $177k needed vs $47k kept: J `model.splits.margin_t10.junior_income_needed_per_season_for_rule_usd`, `.deterministic_per_season_usd`; the three-season rule is 14-RESEARCH §2.4
  - Premium is $2.63M a season with only $40k (1.5%) of margin inside it: J `premium_split_mean_observed_season.station_premium`, `.station_risk_margin`
  - All from a simulated book, not customers (M14 §5)
- **Visual:** Small table (text), two rows: observed seasons, modelled seasons. No chart; put the −144% in the same weight as the +43%.
- **Say it:** I'm not going to dress this up. On today's settings the junior money has good years and then loses everything about once every twenty summers. That's fixable, but only by charging businesses more, and we don't know yet whether they'll pay. That's a pilot question, not a spreadsheet question.

## Slide 11 · Learning a shop's weather sensitivity failed on public stand-ins `[shared S-E]`

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

## Slide 12 · What's built, and how we checked it `[shared S-F]`

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
- **Demo cue:** switch to the live portal here. Follow `reports/pitch/DEMO-WALKTHROUGH.md` (crypto order: Trade → Pool → Onboard/Coverage → Policies), about 5 minutes.

## Slide 13 · The legal fork: swap or insurance `[shared S-H]`

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
