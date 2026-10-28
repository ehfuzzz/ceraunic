# The story, for two kinds of investor

*weather-insurance (codename), Phase 16 pitch narrative, 30 September 2026. One page per audience, then what both stories share. Every number carries its source key; the shorthand is the same as in the deck outlines (E1 = `reports/eval-01/results.json`, E45 = `reports/eval-04-05/results.json`, H = `reports/eval-04-05/handoff.json`, J = `reports/eval-04-05/junior_returns.json`, E6 = `reports/eval-06/results.json`, M14/M15 = the token and legal memos in `reports/pitch/`). Kalshi is named only as the hedge venue; before anything goes out, the owner asks Kalshi about naming it (Developer Agreement v1.1 §6.4) and about a data licence (M15 §6).*

---

## For crypto-native funds

We're building a way for a small business to get paid when the weather hurts its sales. An ice cream shop in Queens does well on hot days and badly on cool, rainy ones. It picks a payout tied to the weather near it, pays a premium, and gets paid in USDC when the official number crosses the line. Nobody files a claim.

Part of that payout can be hedged on Kalshi's daily weather contracts, which settle at the nearest big station. The rest, the gap between the station and the shop, works differently for heat and rain. Heat residuals are quoted on request. Rain residuals settle weekly on PRISM weather-grid cells and trade in the daily batch auction on Hyperliquid's EVM chain. Whatever doesn't match lands in a USDC pool. The pool is the counterparty for most of what we sell, and that's the part a crypto investor should care about.

The pool has two layers. The house's own money loses first. Outside depositors come later, lose only after the first layer is gone, and share the margin we keep. The token, WI for now, is how you own that first-loss layer. If you stake it, you vote on the pool's risk settings inside fixed ranges, and when the first-loss layer loses money, your stake is cut by the same share and the cut tokens are burned. Claims are always paid in USDC. WI has a fixed supply and no emissions, and in the first version stakers earn nothing, because what they may earn is a question for counsel (M14 §3, M15 §5). Every one of those rules comes from a protocol that got hurt: Aave's own-token backstop, Maple's stakers leaving before a default, BarnBridge's tranches (M14 §4).

Here's the part I won't dress up. On today's settings, the first-loss layer earns about 43% in a median modelled summer and is wiped out in about one summer in twenty (J `model.splits.margin_t10.boot_median`, `.boot_p05_1in20`: +43%, −144%). Our own three-season test fails. The fix is a bigger risk load, and only a pilot can tell us whether businesses will pay it.

What's built: the contracts, the auction, the pool, the staking burn, a reference engine and the portal. The engine and the contracts agree to the unit on every shared test case, and the same scenario run through the real contracts on a local chain gives exactly the same money as the simulator (S08, S09). The contracts are ready for testnet; I run that deploy myself. Nothing is on mainnet, and whether Hyperliquid users want weather risk at all is untested.

---

## For fintech and insurtech funds

Weather moves small-business sales, and nobody sells a café simple cover for it. Bespoke weather contracts have high minimums (one provider's minimum premium is usually $50,000, M15 §7), and the small-business version that was tried before died on demand and underwriting cost. Our bet is that you can price this from public weather data and liquid exchange contracts instead of analysts.

A shop owner uploads a year of daily sales or connects Square. The portal estimates how heat and rain move those sales, suggests a cover, shows the price broken into its parts, and settles each day on the NWS climate report with a hash of the exact data release. There's no claim to file.

The numbers are mixed, and I'll show all of them. Kalshi's station contracts track a heat payout at the station 0.95 of the way (E1 `temperature.pooled[rule=A,h=24,pool=liquid NY+CHI+MIA].he_cover.est`), and the official number they settle on is clean. But bought a day ahead, the price already contains the forecast, so a buyer only hedges the forecast miss: 0.37 on 2025-26 days (E1 `...liquid 2025+ (post-hoc)].he_ladder.est`, a window picked after seeing the data). That's why the default product is one fixed-price policy where we hedge daily and a capitalised pool carries the forecast risk. It makes us look more like a small insurer with an unusually good hedge than a broker.

The cleanest first product is rain-day cover. The daily rain market forecasts far better than climatology (Brier 0.106 vs 0.247, E1 `rain_daily.horizons.24.brier_market`, `.brier_clim`) and costs about 20% over fair value. The portal sells heat and cool cover today; rain is next.

Then the legal route. A weather payout with no proof of loss is a swap under US law unless a licensed insurer issues it (M15 §2). The route we want counsel to test is a hybrid: station and regional contracts on a regulated exchange, the last-mile gap as a carrier-issued parametric policy, and our pool as collateralised reinsurance behind the carrier (M15 §7). The token is secondary in that world. The pilot doesn't need one.

---

## What both stories share

**What we proved.**
- The station contracts pay when they should: 0.95 over 4,462 city-days (E1, same key, `.n_citydays`), and the settled number matched the official report on all but 0.2% of days (E1 `mismatch[city=all,settle_source=all].value_mismatch_share`).
- The daily rain market beats climatology easily (E1 `verdicts.T3`, PASS).
- Settlement data doesn't move after the fact: no payout-moving revision in 4,573 station-days (E45 `verdicts.M4.share`).
- Rain sensitivity is learnable, at least for bikeshare: about −10.5% on wet days (E6 `verdicts.T1.G1.mu_wet`).
- The on-chain auction and pool are built, with exact engine-to-contract parity; the portal, Square connect (on recorded responses) and a live sim demo exist (S07-S12).

**What we didn't.**
- The day-ahead price failed our pre-registered bar: 24.6% over fair value against 20% (E1 `...liquid NY+CHI+MIA].overround.est`). Over all years, buying the contracts a day ahead was worse than doing nothing (−0.32, `.he_ladder.est`).
- Netting between businesses is modest and rests on our guesses: 40%, or 1.9% if businesses react to weather alike (E45 `netting.central.pooled`, `netting.null.pooled`). We don't lead with it.
- Capital looks affordable only with daily repricing: 0.126 per dollar of 30-day notional, 0.36 for the station leg if priced before the forecast, about 0.22 on a whole-summer basis (E45 `verdicts.M3.CPC`; H `capital_per_usd_cover_H30.per_usd_pool_notional_clim_priced_station_only`; J `model.weather_pnl_hist.2009`). One bad summer can wipe the first-loss layer.
- Learning a shop's sensitivity failed on public stand-ins: 7% and 5% of revenue surprise removed against a 20% bar (E6 `verdicts.T2.G1.heat_rain_median`, `verdicts.T2.G2.heat_rain_median`). Those are bike, transit and taxi counts, not a shop's sales, so the café question is untested.
- The residual contract design and the geography numbers are **pending Phase 3**.
- No customers, nothing on testnet or mainnet, the legal route unresolved, and "cheaper than a bespoke contract" never measured (EVAL §11).

**What the money buys.** We're raising a pre-seed of roughly $500k to $1.5M (M14 §7). The first dollars go to what could kill this: counsel's written answer on the swap-or-insurance fork and the open auction, and a pilot with real sales from 10 to 40 weather-exposed shops, with the test written down before we see a number. After that: re-running the price and depth numbers on our own recorded order books, audits, testnet, and mainnet only once the counsel gates in M15 §7 are met. If the legal answer or the pilot comes back badly, we'll know within a year.
