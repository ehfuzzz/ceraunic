# How the pool and the token work

*weather-insurance (codename), token and pool economics memo, 30 September 2026. Numbers from our Phase 2, 4 and 5 runs carry footnotes naming their file and key.*

A note on words: this memo says "cover" and "policy", not "insurance". Whether what we sell is legally insurance, a swap or an exchange product is for our counsel memo (Phase 15); I won't assume the answer.

## 1. What the pool does

**From the business's side.** Say you run an ice cream shop in Queens. Hot days are great for you and cool, rainy summer days hurt. We estimate how weather moves your sales from your sales history, you pick a payout tied to the temperature or rain at your location, and you pay a premium. If the weather goes against you, you get paid in USDC. Nobody files a claim; the payout follows a published weather number.

**From the pool's side.** Part of that payout can be hedged with Kalshi's daily weather contracts, which settle at the nearest big airport station. Their payout tracks a heat payout at the station closely: a hedge effectiveness of 0.95 over 4,462 city-days.[^he1] Bought a day ahead, they do much less (section 5). The books are thin: one snapshot supported 33 to 55 units a day per city near the best price,[^depth] against about 4,400 unmatched units a day at Central Park alone in our simulation.[^left] The gap between the airport and your street can't be hedged there at all. Businesses with opposite exposure (a laundromat or a gym might not want heat) can trade with each other in a daily auction, which cancels some risk, though less than we'd like. What doesn't match lands in the pool. So the pool is the counterparty for most of what we sell, and has to hold enough to pay on a bad day.

## 2. The two layers, and who loses first

All pool money is USDC in one vault. Before a policy binds, its maximum payout is set aside from the pool's cash, so every live policy's money is always there. The layers decide whose money it is.

```
   a loss is taken from:
   1. junior layer   (protocol-owned USDC: the house seed, then retained premium)
   2. senior layer   (outside stablecoin depositors, later, only if counsel allows)

   staked WI is cut (burned) in proportion to what the junior layer lost that day
```

The junior layer is in USDC, not our own token, because claims are paid in dollars and we never want to sell our own token into a falling market to pay one. Senior depositors want a steadier return and lose money only once the junior layer is gone. We won't take them until counsel says how we may.

Here's how a premium dollar gets split in the prototype, in order:

1. The protocol fee comes off first (10 basis points of notional plus 10% of the risk margin) and goes to the treasury, which is an operating account and not at risk.
2. Senior depositors get about a fifth of the margin we keep, not of the whole premium (section 5 shows why); the prototype sets it at 0.3% of each premium dollar after the fee.
3. The junior layer gets the rest. It also takes all the hedge profit or loss, and every loss first.
4. Above its target, the junior layer's excess could later go to stakers or buybacks, if counsel allows; the prototype releases nothing.

The house market-maker runs the pool's hedges (Kalshi legs and auction trades) as the pool's agent. Their profit or loss lands in the junior layer, the house keeps none, and both books are published.

Leaving the pool takes two steps. An LP asks to withdraw and waits out the withdrawal delay (12 days in the prototype), then has a 3-day window to claim. A matured request not claimed in 3 days lapses: the shares go back to the LP's tranche and no USDC moves, so the LP stays invested. An LP can cancel before maturity. The withdrawal delay and the unstake cooldown must each be at least the house return window plus 2 days, and the contracts now enforce that, not just the deploy script.

## 3. What the token is, and what it isn't

The token (WI for now) is how you own the junior layer. If you stake it, you take the first hit; the design also gives you a vote on risk settings (not built yet). If the junior layer loses 10% of its money on a bad day, every staked position is cut by 10%, up to a cap per day (30% in the prototype, still an open parameter), and the cut tokens are burned. Nothing is sold. Unstaked WI doesn't vote and isn't cut.

Stated plainly:

- **Claims are paid in USDC.** The token never pays a claim.
- **The cut follows the junior layer's dollar loss,** so we need no price feed for WI, and there's nothing to manipulate.
- **There are no emissions.** WI has a fixed supply, minted once, and staking can only burn. If the pool earns little, stakers earn little.
- **What stakers earn is undecided.** Paying stakers from pool income runs into the SEC and CFTC's March 2026 guidance that a digital commodity doesn't convey "rights to future income". Income share, buybacks or nothing is counsel's call; the prototype pays nothing.
- **The pilot doesn't need a token.** Until WI exists, the junior layer is just the house seed in USDC. The token matters once outside senior depositors exist.

Governance is deliberately narrow. In v0 an owner key sets the parameters; staked-WI voting inside fixed ranges with a delay is the design, not yet built. Nobody votes on claims or live policies. A small multisig can pause new sales but can't move money.

## 4. Why it's built this way

Each rule comes from a protocol that got hurt (Appendix H).

- **Junior layer in USDC, token cut by burning.** Aave dropped its own-token safety module in June 2025 because a loss meant selling AAVE into a falling market. Nexus Mutual burns staked tokens.
- **Long exits that still take the cut.** In Maple's first version, informed stakers left before the Orthogonal default. Heatwaves are forecast days ahead, so this matters more for us.
- **Caps on total exposure and on any one city on any one day, a minimum junior share, and automatic halts.** InsurAce paid out 124 times what it collected when UST collapsed.
- **Fixed supply, no mint role, audits first.** Cover Protocol's mint bug and Resolv's $25 million key abuse were each bigger than a tranche.
- **No outside deposits, staker payouts or token sale before counsel picks a route.** The SEC settled with BarnBridge over senior and junior tranches in 2023.
- **The house trades only as the pool's agent, and both books are published.** Hyperliquid's house vault lost deposits in the JELLY scare.

## 5. The numbers

Every figure is from our result files (footnotes and Appendix E). Phase 4's numbers come from a simulation, not customers: 2% of small businesses near five stations hedging every warm-season day, with our own low-confidence guesses about which businesses gain or lose on hot days. Read them as what the design needs if the world looks like this, not as a forecast.

**1. Capital per dollar of cover.** To survive the worst 30-day stretch in 26 summers, the simulated book needs $412k of capital,[^c30] or 0.126 per dollar of 30-day pool notional.[^cpc] The 0.126 holds only if cover is repriced every day off the forecast. If a business buys cover at a fixed price set from climatology, which is closer to what a small business wants, it rises to 0.18 for the whole book and 0.36 for the station leg,[^clim] just over the 0.35 line we set in advance. Even repriced daily, the station leg alone is 0.25.[^st]

That's a 30-day figure. A whole summer can lose more: the worst modelled one, 2009, loses $731k.[^ssn] So a season's writing is capped at capital divided by that loss: about 0.22 per dollar of notional on a season basis. We always quote both.

**2. Junior share.** Half of that capital, $206k, is the junior layer, sized to the average of the worst 5% of 30-day losses.[^jr] That's above the worst historical one-day loss ($35k),[^h1] so under our rule it's the junior target.

**3. Fee income.** A 10 basis point fee on hedgers' notional earns $0.001 per dollar, about $22k a season; 50 basis points earns $0.005, about $112k.[^fee] Keeping half of each hedger's price improvement earns about $0.004, or $90k.[^cow]

**4. Netting.** Real but modest. Under our guesses, about 40% of hedge units cancel between businesses at the same station, and 3 of 5 stations clear our 25% bar: Miami 0.65, Central Park 0.36, Midway 0.32, with Newark (0.21) and Trenton (0.13) below it.[^nr] If businesses mostly move together, which is what the best US daily evidence says, netting falls to 2%.[^null] Rain doesn't net, and Kalshi's daily rain markets are about 300 times too thin to lay it off, so a rain book is the pool's own risk: about $1.08M of 30-day capital at 2% take-up, and the junior layer loses money in a bad year.[^rain]

**5. Worst window.** The worst 30-day loss, $412k, sets the 30-day capital; the 30-day ES99 is $269k.[^es] On Kalshi-era days the model was too cautious, not too thin: one breach of its daily 99% line in 599 days (about six expected), and a worst real 30-day loss of $104k.[^m5]

**6. Hedge quality.** Kalshi's ladders track a station heat payout well (0.95),[^he1] but counting the price paid a day ahead, it's 0.37 in 2025–26 and −0.32 over 2022–26,[^hel] because the day-ahead price already contains the forecast; only the forecast miss gets hedged.

We also learned hedges from a year of daily sales on public stand-ins (we have no shop data yet). Heat-and-rain cover removed 7% of daily revenue surprise for New York bikeshare, 5% for Chicago's, and about nothing for transit or taxis;[^hc] at real day-ahead asks, bikeshare kept under a tenth of that.[^hl6] Both missed our 0.20 bar, so the portal shows learned sensitivity as advice only.

**7. What the junior layer earns.** This is what a staker cares about, and it isn't good yet. The premium is almost all expected payout: $2.63M a season on the simulated book, with a 1.5% margin ($40k) inside it. Our first draft gave senior 20% of the whole premium, about $526k a season on $206k of senior money,[^js] and the junior layer lost money in all four simulated seasons.[^jspec] So the rule changed: senior now gets about 20% of the margin we keep (0.3% of premium in the prototype). On that rule the junior layer's return on its $206k is:[^jb]

| Season | Junior return |
|---|---|
| 2023 / 2024 / 2025 / 2026, simulated on real Kalshi prices | +123% / +97% / +159% / −65% |
| Same, local gap priced off the last five years | +72% / +42% / +87% / −111% |
| Median season, modelled on 26 past summers | +43% |
| 1-in-20 season, modelled | −144% (−293% resampling whole summers) |
| Worst of the 26 summers (2009) | −332% |

In plain words: in a bad season, about one summer in twenty by our model, the junior layer loses all its money and senior money starts paying claims. The halt rules stop new sales once the junior layer runs thin, but policies already sold still pay. The 30% haircut cap only limits how much staked WI is burned on one day; it doesn't limit how many dollars the junior layer loses. Our rule wants the 1-in-20 return positive over three seasons. It fails: the junior layer would need about $177k a season of kept margin, against $47k now. The treasury cut barely matters: about $4k a season at 10%.[^jt] The fix is a bigger risk load, a smaller book per dollar of junior money, or both. The pilot has to show whether businesses will pay that load.

**What the house makes.** The house's trades for the pool made $1,154 a day,[^mk] almost all from pricing the Central Park gap off long climatology; priced off the last five years, it's $384.[^mk5]

## 6. What could go wrong

Appendix G has the full table. Four look most real: a margin too thin to carry a bad summer (item 7); cover priced before the forecast (we reprice daily); netting smaller than assumed (pricing and capital don't count on it); and local gaps priced off stale climatology (the house uses a recent window).

## 7. The raise

We're raising a pre-seed of roughly $500k to $1.5M. Audit costs come from published 2026 pricing; counsel, team and pilot figures are my estimates until we get real quotes.

| | $500k (about 12 months) | $1M (about 18 months) | $1.5M (18–24 months) |
|---|---|---|---|
| Counsel (memo, entity, SAFE and token warrant; later route and token opinion) | $60–90k | $120–180k | $200–300k |
| Security audits, contest, bug bounty reserve | $40–70k | $90–150k | $150–250k |
| House seed (the pilot book's junior target, at most $206k), then runway and hedging float | $100–150k | $200–300k | $300–450k |
| Hedge working capital (Kalshi leg, if counsel allows) | $15–30k | $30–60k | $50–80k |
| Pilot businesses (premium subsidies, hands-on onboarding) | $15–30k (10–15 businesses) | $40–70k (25–40) | $60–100k (50+) |
| Data, oracle signer, hosting, monitoring | $8–15k | $15–30k | $25–50k |
| Team | $150–200k | $300–400k | $400–550k |
| Reserve | $40–50k | $80–100k | $80–120k |
| **Total range** | **about $430–635k** | **about $875k–1.29M** | **about $1.27–1.9M** |

So $500k gets counsel's answer, one audit, a small pilot and a year of runway. $1M adds a second audit and an engineer, enough to show a season of policies settling. $1.5M adds token-launch readiness and room to grow the book, if counsel clears it.

The house seed is the junior target of the book we actually carry. For a book the size of our simulation, thousands of businesses, that's $206k,[^jr] the ceiling; a pilot with a few dozen businesses needs far less.

## 8. What we don't know yet

- **The right risk load.** At a 1.5% margin the junior layer fails our three-season test (section 5).
- **What stakers may earn, and whether US persons can stake, deposit or hold WI at all.** A weather payout with no proof of loss is a swap under US law unless a licensed insurer issues it, so the pool may end up behind a licensed carrier; the token design has to work either way.
- **Whether the local contract works.** For heat, no: none of eight designs cleared our bar, so heat is station-only. A weekly rain design passed our bar, tested on all 26 station pairs, and isn't built yet.[^e03]
- **Whether businesses want this, and whether their weather risk is learnable.** No paying customers yet; our only sensitivity evidence is from public stand-ins, which missed our bar.
- **Whether Hyperliquid users want weather risk.** Untested.
- **Whether Kalshi stays available.** New York's attorney general sued Kalshi in July 2026, and Kalshi's data terms restrict pricing other products off its data without written consent.
- **The haircut cap and lock lengths.** The 30% daily cap and the 12-day locks are open parameters (SPEC §17).

---

## Appendix A. Precedents

| Protocol | First-loss money | What went wrong | Lesson for us |
|---|---|---|---|
| Nexus Mutual (2019–) | NXM staked into underwriting pools; claims paid from pool assets, staked NXM burned | Redemptions froze in the bonding-curve era; claims moved from stake votes to an expert panel in v3 | A token backed by pool assets works if claims come from those assets; stakers shouldn't vote on their own losses |
| Sherlock (2021–) | USDC stakers | Euler payout of $4.5M against a pool that had shrunk from $30M to $2.9M; about $4M lost in a Maple pool | One event can exceed the pool; never invest pool money elsewhere |
| Maple v1 (2021–22) | 50/50 MPL-USDC cover | Informed stakers left before the $36M Orthogonal default | First-loss that can leave will leave |
| Maple v2 / SYRUP | Delegate cover; staking ended | Rewards replaced by buybacks (MIP-019, Oct 2025) | Revenue beats emissions |
| Ondo v1 (2021–22) | Junior tranche takes all excess and shortfall | Wound down as yields compressed | Junior demand needs a real excess return |
| Risk Harbor (2021–) | Stablecoin underwriters, parametric | Paid about $2.43M as designed; now commercially dead | Parametric payout works; distribution is the hard part |
| Ensuro (2021–) | Junior and senior USDC tranches, licensed partners | No public blow-up found | Closest template for our waterfall and caps |
| Neptune Mutual (2022–24) | Stablecoin pools; NPM for governance | Closed in 2024, cited failing to list its token | A token that depends on listings is fragile; support a clean wind-down |
| Etherisc (2017–) | DIP staked to activate stablecoin capital | No large loss; rewards are emissions | Token-gated stablecoin capital didn't create demand by itself |
| Nayms / OnRe (2022–) | Bermuda-licensed reinsurance pool | Restructured; headline yields include incentives | A regulated route for weather risk exists |
| InsurAce (2021–) | Stakers' pool | About $11.7M paid on about $94k of UST premiums; changed terms afterward | Correlated tails wipe pools; never change terms after the event |
| Cover Protocol (2020) | n/a | Mint bug, about $4.4M drained, price down 97% | Mint authority is the attack surface |
| Unslashed (2020–) | Capital buckets; juries | Large claims refused, long disputes | Voted claims end in fights |
| Aave Safety Module → Umbrella | stkAAVE → staked aTokens, burn-only | Replaced in June 2025 to avoid selling AAVE into a loss | Strongest case against an own-token junior |
| Hyperliquid HLP | USDC house vault | Deposits fell sharply after JELLY (Mar 2025) despite no net loss | Depositors leave a house vault after a scare |
| BarnBridge | Senior/junior tranches | SEC order, Dec 2023 | Tranches aren't legally neutral |
| Resolv (2026) | RLP junior | $25M lost to a single minting key | A junior covers underwriting losses, not code failures |

## Appendix B. Comparable rounds, 2025–2026

Valuations are almost never disclosed, so this table shows round sizes only. We found no 2025–2026 round for an on-chain parametric weather protocol.

| Company | What it does | Round | Amount | Lead | Date |
|---|---|---|---|---|---|
| functionSPACE | On-chain pricing of numerical outcomes | Pre-seed | $1.7M | Maven 11 | Sep 2026 |
| ParlayX | Prediction-market infrastructure | Pre-seed | $1.25M | Dreamcraft Ventures | Sep 2026 |
| Elastics | AI agents for prediction markets | Pre-seed | about $2M | Frst | May 2026 |
| Cork | Cover tokens and depeg swaps | Seed | $5.5M | a16z CSX | Jan 2026 |
| OnRe | On-chain reinsurance | Series A | $5M | Forward Industries, RockawayX | May 2026 |
| Hyperbeat | HyperEVM yield vaults | Seed | $5.2M | ether.fi Ventures, Electric Capital | Aug 2025 |
| Pascal | Prediction markets | Series A | $9M | n/a | Jul 2026 |
| Risk Harbor (older) | Parametric DeFi cover | Seed | $3.25M | Pantera | Jun 2021 |

Context: a secondary tally of Q2 2026 web3 deals put the pre-seed median at about $2.5M, usually a post-money SAFE plus a token warrant. Our ask sits below that, which seems right for a team with a prototype and no customers yet. Typical token splits are 15–25% team and 11–19% investors, each with a 12-month cliff. Every HyperEVM pitch gets compared to Hyperliquid, which raised no VC money and gave 31% of HYPE to users at launch. Insiders' tokens in our design can only be staked after their cliff, so nobody collects the junior layer's upside without being locked.

## Appendix C. Facts for counsel (not legal conclusions)

| Date | Source | What it says | Why it matters |
|---|---|---|---|
| 22 Dec 2023 | SEC, BarnBridge order | Senior/junior tranches were unregistered securities | Same shape as our pool |
| 29 May 2025 | SEC staff, protocol staking statement | Proof-of-stake staking isn't a securities offering; excludes assets with passive yield | Doesn't cover staking WI for first-loss |
| 18 Jul 2025 | GENIUS Act | Stablecoin issuers can't pay holders yield | Senior layer can't be framed as a yield-bearing stablecoin |
| 17 Mar 2026 | SEC + CFTC joint interpretation | A digital commodity doesn't convey "rights to future income"; may convey governance rights | Central question for what stakers can earn |
| 22 Jul 2026 | Commissioner Peirce (personal) | Vaults can be investment contracts depending on who picks the strategy | A pool with governed risk settings looks like a managed vault |
| 18 Aug 2026 | SEC, proposed Regulation Crypto Assets | Startup and fundraising exemptions; not final; comments due 20 Oct 2026 | A possible path for a WI sale |
| 7 Sep 2023 | CFTC, Opyn order | US IP blocking "was not sufficient" | Geo-blocking alone isn't a defence |
| 3 Jan 2022 | CFTC, Polymarket order | Penalty for unregistered event-based binary options | Event-style payouts to US persons |
| CEA §1a(47) | Statute | Names "a weather swap" | Our payout is a swap unless a licensed insurer issues it |

## Appendix D. Sources

Full source list with links is in `.planning/phases/14-token-pool-memo/14-RESEARCH.md` (Sources section). Primary sources used most here: Nexus Mutual docs and 15 Jan 2026 review; Ensuro docs; Aave Umbrella docs and the BGD proposal of 24 Jul 2024; SEC Rel. 33-11412, PR 2023-258 and the 29 May 2025 staking statement; the Cover Protocol post-mortem. Hedge-quality and residual findings are from the hl-mm ins1 and ins2 studies (30 Sep 2026). The legal fork is from `.planning/phases/15-legal-memo/15-RESEARCH.md`. The section 5 numbers are from our own runs (`reports/eval-01`, `reports/eval-04-05`, `reports/eval-06`); keys are in Appendix E and the footnotes.

## Appendix E. The numbers, with sources

File shorthand: **H** = `reports/eval-04-05/handoff.json`, **R4** = `reports/eval-04-05/results.json`, **J** = `reports/eval-04-05/junior_returns.json`, **E1** = `reports/eval-01/results.json`, **E6** = `reports/eval-06/results.json`. Values are copied and rounded for reading only.

| # | Number | Value | Source (file: key) |
|---|---|---|---|
| 1 | Capital per $ of 30-day pool notional, both legs, repriced daily | 0.126 | H: `capital_per_usd_cover_H30.per_usd_pool_notional_both_legs` |
| 1 | Same, station leg only | 0.251 | H: `capital_per_usd_cover_H30.per_usd_pool_notional_station_leg_only` |
| 1 | Same, cover priced at climatology, both legs / station leg | 0.177 / 0.360 | H: `capital_per_usd_cover_H30.per_usd_pool_notional_clim_priced_both_legs` / `..._clim_priced_station_only` |
| 1 | Per $ of gross hedger cover; per $ of full collateral | 0.067; 0.248 | H: `capital_per_usd_cover_H30.per_usd_gross_hedger_cover`; `.C_over_full_collateral` |
| 1 | 30-day capital C_30; 30-day pool notional | $412,109; $3,260,235 | H: `C30_usd`; R4: `verdicts.M3.N30` |
| 1 | Worst modelled season weather loss (2009), simulated book | $731,394 | J: `model.weather_pnl_hist.2009` |
| 1 | Capital per $ of pool notional, season basis (30-day figure × worst season loss ÷ C_30) | 0.22 | derived: H `capital_per_usd_cover_H30.per_usd_pool_notional_both_legs` × J `model.weather_pnl_hist.2009` ÷ J `model.C30_check` |
| 2 | Junior share; junior ES95 (30 days) | 0.501; $206,315 | H: `junior_share`; H: `junior_ES95_30d_usd` |
| 2 | Worst one-day loss on the simulated book | $34,800 | H: `capital_H.H1.worst_window` |
| 3 | Fee income per $ notional: 10 / 25 / 50 bps / half of improvement | 0.001 / 0.0025 / 0.005 / 0.0040 | H: `fee_income_per_usd_notional.{bps10,bps25,bps50,cow50}` |
| 3 | Fee income per season, same rules | $22,442 / $56,105 / $112,211 / $90,322 | H: `fee_income_per_season_usd.{bps10,bps25,bps50,cow50}` |
| 4 | Netting ratio, central: NYC / EWR / TTN / MDW / MIA / pooled | 0.36 / 0.21 / 0.13 / 0.32 / 0.65 / 0.40 | H: `netting_ratio.central.*` |
| 4 | Netting ratio, null (sectors move together), pooled | 0.019 | H: `netting_ratio.null.pooled` |
| 4 | Pooled netting ratio across 1,000 prior draws, p10 / p50 / p90 | 0.22 / 0.38 / 0.56 | H: `netting_ratio.ensemble_p10_p50_p90.pooled` |
| 5 | Worst historical 30-day loss; 30-day ES99 | $412,109; $269,430 | H: `worst_window_30d_usd`; H: `ES99_30d_usd` |
| 5 | Backtest: exceedances in 599 days; worst real 30-day loss | 1; $104,387 | R4: `verdicts.M5.kupiec.x`; `verdicts.M5.worst_realized_30day_loss` |
| 6 | Station ladders, HE_cover, liquid pooled 2022–26 | 0.95 | E1: `verdicts.T1.he_cover` |
| 6 | Station ladders, HE_ladder (premium paid), pooled / 2025+ | −0.32 / 0.37 | E1: `verdicts.T1b.he_ladder` / `temperature.pooled[2].he_ladder.est` (rule A, 24 h, "liquid 2025+ (post-hoc)") |
| 6 | NYC bikeshare (G1): HE_cover / HE_ladder | 0.072 / 0.006 | E6: `verdicts.T2.G1.heat_rain_median` / `verdicts.T3.G1.ladder_median` |
| 6 | Chicago bikeshare (G2): HE_cover / HE_ladder (heat only) | 0.053 / 0.001 | E6: `verdicts.T2.G2.heat_rain_median` / `verdicts.T3.G2.ladder_median` |
| 6 | Chicago transit (G3): HE_cover / HE_ladder | 0.009 / −0.001 | E6: `verdicts.T2.G3.heat_rain_median` / `groups.G3.primary.arms.A3.ladder_heat_rain_daily.median` |
| 6 | Chicago taxi (G4): HE_cover / HE_ladder | −0.001 / 0.001 | E6: `verdicts.T2.G4.heat_rain_median` / `groups.G4.primary.arms.A3.ladder_heat_rain_daily.median` |
| 6 | New York taxi (G5): HE_cover / HE_ladder | −0.006 / −0.000 | E6: `verdicts.T2.G5.heat_rain_median` / `groups.G5.primary.arms.A3.ladder_heat_rain_daily.median` |
| – | House P&L after hedge, per day: primary / residual priced on trailing 5 years | $1,154 / $384 | H: `house_markout_mean_daily_usd.primary` / `.resid_trailing5` |
| – | Pool return on C_30 by season 2023 / 2024 / 2025 / 2026 | 0.67 / 0.57 / 0.88 / −0.23 | R4: `pool_return.by_season.{2023..2026}.return_on_C30` |
| – | Mean season return on C_30: primary / trailing-5 residual | 0.47 / 0.19 | R4: `pool_return.mean_season_return_on_C30` / `..._resid_trailing5` |
| 7 | Station premium a season; risk margin inside it; senior take under the old rule (20% of net premium, `seniorPremiumBps` 2000) | $2,632,542; $39,839; $525,712 | J: `premium_split_mean_observed_season.station_premium` / `.station_risk_margin` / `.splits.spec_t10.senior` |
| 7 | Junior return 2023–26, old senior rule (20% of net premium), 10% cut | −6% / −92% / −143% / −449% | J: `observed.primary.spec_t10.by_season.*.junior_return` |
| 7 | Junior return 2023–26, senior on kept margin, 10% cut: primary / residual on 5 years | +123 / +97 / +159 / −65%; +72 / +42 / +87 / −111% | J: `observed.primary.margin_t10.by_season.*.junior_return`; `observed.resid_trailing5.margin_t10.by_season.*.junior_return` |
| 7 | Modelled junior return, senior on kept margin, 10% cut: median / 1-in-20 / worst of 26 | +43% / −144% / −332% (2009) | J: `model.splits.margin_t10.boot_median` / `.boot_p05_1in20` / `.hist_worst` |
| 7 | Same, 20% cut: median / 1-in-20 | +41% / −146% | J: `model.splits.margin_t20.boot_median` / `.boot_p05_1in20` |
| 7 | 1-in-20 resampling whole summers; 3-season 1-in-20 | −293%; −190% | J: `model.splits.margin_t10.sens_whole_season.p05_1in20`; `.three_season_sum_p05` |
| 7 | Kept margin a season needed to pass the 3-season rule; kept now | $177,226; $46,611 | J: `model.splits.margin_t10.junior_income_needed_per_season_for_rule_usd` / `.deterministic_per_season_usd` |
| 7 | Treasury a season at 10% / 20% cut | $3,984 / $7,968 | J: `premium_split_mean_observed_season.splits.{spec_t10,spec_t20}.treasury` |
| – | Leftover units per day at Central Park; its max payout | 4,426; $26,555 | R4: `netting.leftover_units_per_day.NYC.mean_units` / `.mean_max_payout_usd` |
| – | Max units at ≤ 3c, one book snapshot: NYC / CHI / MIA | 33 / 54 / 55 | E1: `depth.ladders.{KXHIGHNY,KXHIGHCHI,KXHIGHMIA}-26SEP30.max_units_3c` |

Prototype settings quoted in the memo come from `docs/SPEC.md`: fee 10 bps of notional plus 10% of risk margin (§11); senior share 0.3% of premium net of the treasury fee, about 20% of the simulated book's 1.5% kept margin (`seniorPremiumBps` 30, §17, ruled 30 Sep 2026; it was 2000); haircut cap 30% per day (`haircutCapBps` 3000, §8.7); 10 days for `houseReturnWindow` (§8.6) and 12 days for both `withdrawDelay` and `unstakeCooldown` (§8.2, §8.7; seat ruling 30 Sep 2026, Phase 8: the return window plus 2 days, so nobody can leave inside the 10-day write-off window and dodge a cut; the contracts enforce that floor, `BadWindows`). A matured withdrawal request must be claimed within 3 days or it lapses back to the LP's tranche (`CLAIM_WINDOW`, §8.2; audit hardening pass, finding 6). All of these are open parameters in SPEC §17.

## Appendix F. Deviations from the rules written for this section, and what's still open

The rules for section 5 were written in 14-RESEARCH before any number existed. Where the result files didn't match them:

1. **Capital per $ of cover.** The rule defined it as (junior target + required senior) ÷ unmatched residual payout after netting. Phase 4 reported capital per $ of 30-day pool notional instead (plus per $ of gross hedger cover and of full collateral). The memo quotes Phase 4's definitions rather than re-deriving ours.
2. **Junior target.** The rule compares the tail measure with the worst historical metro-day loss on the pilot book. There is no pilot book yet, and Phase 4 didn't report a per-metro worst day, so the memo uses the worst one-day loss on the whole simulated book ($35k). Per-metro worst days are still open.
3. **Junior return in a median, 1-in-20 and worst year.** Computed by a Phase 4 add-on (`scripts/eval04_junior.py`, rules in `reports/eval-04-05/PREREG-junior.md`, results in `junior_returns.md`). Assumptions: station-leg house fills count as policies, with premium = clearing price when the pool sells cover and 1 − price when it buys (SPEC's put); the residual leg and Kalshi hedge are house trades, all to junior; senior capital = C_30 − $206k. The "1-in-20 season" is the 5th percentile of a bootstrap on Phase 4's capital scenario. That scenario covers 1999–2025 for the two-leg book, not 1951–2025. The rule-4 "worst year" is the worst of those 26 summers. The 7-day blocks understate the tail against whole summers (−144% vs −293%); both are shown. No yield on idle USDC is counted.
4. **Premium split at 10% and 20% treasury cuts.** Computed on the same run, with the cut taken from the station risk margin (SPEC `feeMarginBps`). Under the old senior rule (20% of net premium, `seniorPremiumBps` 2000) the junior loses money in every season. On 30 Sep 2026 the seat ruled that senior's share is a share of kept margin: SPEC now sets `seniorPremiumBps` 30 (0.3% of premium net of the treasury fee, about 20% of the 1.5% margin), and mainnet routes the margin explicitly through the house-signed quote. Section 5 quotes the kept-margin run, which is that rule. The run gives senior exactly 20% of margin; the 30 bps setting moves each junior return by under one point a season.
5. **"HE_ladder by sector" from Phase 5.** The sectors are public stand-ins (bikeshare, transit, taxi), not retail sales. Chicago has no daily rain asks before September 2026, so Chicago bikeshare's HE_ladder is heat only.

## Appendix G. What could go wrong (full table)

| What could go wrong | What we do about it | What's still left |
|---|---|---|
| A loss forces a token sale | Junior layer in USDC; burn-only cut | WI's price still drops on bad news, but the pool's capacity doesn't |
| Stakers leave before a forecast heatwave | Exit delays longer than forecast plus settlement; unstaking positions still cut | Long locks make staking less attractive |
| One hot week in one city wipes out the junior layer | City-day cap; automatic halt; station leg hedged on Kalshi where the books allow | Our tail model could be wrong; Kalshi depth covers little of the book |
| Cover priced before the forecast is known | Reprice daily; size capital on the climatology-priced case until the pilot says otherwise | Station-leg capital rises to 0.36 per $ of notional |
| Netting smaller than assumed | Don't count on it in pricing or capital | If sectors move together, the pool carries nearly all of it |
| Local gaps priced off stale climatology | Price them off a recent window | Station climates keep drifting |
| Arguments over claims | Parametric index; revision rule written before sale; no claims votes | Data errors (revised grids, station outages) need a written fallback |
| Someone buys cheap WI after a loss and loosens the caps | Design, not built (v0: owner key sets parameters): fixed ranges, waiting period, only locked stake votes | Harm inside the ranges is still possible |
| A code bug bigger than the pool | Fixed supply; no mint role; audits; per-transaction and per-day caps; pause | Bugs nobody has found |
| Pool money lost outside weather | Plain USDC | Stablecoin issuer risk |
| The house's two roles | House trades only as the pool's agent; both books published | How it looks to depositors |
| Yield that is really incentives | No emissions | A lower headline yield than competitors |
| Tranches or staker income treated as securities | Nothing outside testnet before counsel picks a route | Legal, and the biggest single unknown |


## Appendix H. Why it's built this way, in full

None of these rules is new. Each comes from a protocol that got hurt.

**Loss currency.** Aave's old safety module held its own token as backstop, and a loss would have meant selling that token. Its engineers wrote that "the sell pressure of the slashing itself will circularly reduce the coverage", and in June 2025 Aave replaced it with a design that burns instead of sells. **Our rule:** the junior layer is USDC, and the token is cut by burning. **What it prevents:** a death spiral where a loss forces a sale, the price drops, and the pool can carry less exactly when it needs to carry more.

**Burn, not sell.** Nexus Mutual pays claims from its capital pool and burns the staked tokens of the pool that wrote the cover. It has paid more than $18.5 million in claims since 2019 this way. **Our rule:** pro-rata burn of staked WI, capped per event. **What it prevents:** the need for a WI price oracle and a market sale on the day of a loss.

**Exit timing.** In Maple's first version, people who saw the December 2022 Orthogonal default coming pulled their first-loss cover, and what was left covered only a few percent of the bad debt. Weather makes this worse, because heatwaves are forecast days ahead. **Our rule:** unstaking and withdrawals take longer than the forecast window plus the time for weather data to become final (the prototype uses 12 days for both; the lengths are still open parameters), and positions that are unstaking still take the cut. **What it prevents:** stakers and depositors leaving right before a heatwave that everyone can see coming.

**Correlated tails.** InsurAce paid about $11.7 million on about $94,000 of premiums when UST collapsed, 124 times what it collected. Our own data shows the same shape: residuals around one station move together (correlation 0.74 to 0.83 for a grid cell minus the station; 0.13 to 0.35 for the same-source spread Phase 3 picked, still not zero), so a book of nearby residuals doesn't diversify much. **Our rule:** a cap on total exposure, a cap on any one city on any one day no larger than the junior layer, and a minimum junior share. If any limit is hit, new sales stop automatically. **What it prevents:** one hot week in one city wiping out the junior layer and hitting senior depositors.

**Claims.** Unslashed's token-voted juries ended in long fights, and Nexus moved claims away from stakers in v3. **Our rule:** payouts follow the published weather index and a revision rule written before the policy was sold, and changes to data sources only apply to new contracts. The data version hash is recorded with each report; it is not yet inside the signed payload (a mainnet item). **What it prevents:** stakers voting on claims that would burn their own stake, and changing terms after the fact.

**Pool money stays put.** Sherlock lost about $4 million of stakers' USDC parked in a Maple pool that defaulted. **Our rule:** pool money sits in plain USDC. **What it prevents:** losing money on something other than weather.

**Mint authority.** Cover Protocol's mining contract had a bug that minted about 40 quintillion tokens in 2020, and Resolv lost about $25 million in March 2026 when one key with minting power was abused. **Our rule:** fixed supply, no mint role after deploy, audits before any value touches the contracts. **What it prevents:** a code failure bigger than any tranche.

**Emissions.** Maple ended staking rewards in late 2025 for buybacks from real revenue. **Our rule:** no emissions, and underwriting return reported separately from anything else. **What it prevents:** a yield that looks good only because the protocol is paying people in its own token.

**Tranches and securities law.** In December 2023 the SEC settled with BarnBridge over senior and junior tranches it had sold as unregistered securities. **Our rule:** no outside depositors, no staker payouts and no token sale before counsel picks a route. **What it prevents:** us building exactly the fact pattern the SEC has already charged.

**The house wearing two hats.** Hyperliquid's house vault lost a large share of deposits after the March 2025 JELLY scare, even though it ended that episode up. **Our rule:** the house trades only as the pool's agent, its wallet returns or writes off each day's money within the 10-day window, both books are published, and there are no off-market house trades against the pool. **What it prevents:** depositors wondering whether the house is using the pool as its own balance sheet.


[^he1]: `reports/eval-01/results.json`: `verdicts.T1.he_cover` = 0.953 (liquid NY/CHI/MIA ladders, 24 h, 2022–26); city-days from `temperature.pooled[0].n_citydays` = 4,462.
[^depth]: `reports/eval-01/results.json`: `depth.ladders.{KXHIGHNY,KXHIGHCHI,KXHIGHMIA}-26SEP30.max_units_3c` = 33.0 / 54.4 / 55.3. One book snapshot, 2026-09-29.
[^left]: `reports/eval-04-05/results.json`: `netting.leftover_units_per_day.NYC.mean_units` = 4,426 ($1/°F units; `mean_max_payout_usd` = $26,555).
[^c30]: `reports/eval-04-05/handoff.json`: `C30_usd` = 412,109 (binding: `worst_window_30d_usd`); 26 joint seasons per `caveats`.
[^cpc]: `reports/eval-04-05/handoff.json`: `capital_per_usd_cover_H30.per_usd_pool_notional_both_legs` = 0.1264.
[^clim]: `reports/eval-04-05/handoff.json`: `capital_per_usd_cover_H30.per_usd_pool_notional_clim_priced_both_legs` = 0.1769; `capital_per_usd_cover_H30.per_usd_pool_notional_clim_priced_station_only` = 0.3602. The 0.35 line is rule M3 in `reports/eval-04-05/PREREG.md`.
[^st]: `reports/eval-04-05/handoff.json`: `capital_per_usd_cover_H30.per_usd_pool_notional_station_leg_only` = 0.2511.
[^ssn]: `reports/eval-04-05/junior_returns.json`: `model.weather_pnl_hist.2009` = −731,394 (worst of 26 modelled seasons), against `model.C30_check` = 412,109. Season-basis capital per $ of notional = 0.1264 × 731,394 ÷ 412,109 = 0.224; the write cap (SPEC §8.4) is capital ÷ worst modelled season loss, about 0.56 of the simulated book per $412k.
[^jr]: `reports/eval-04-05/handoff.json`: `junior_ES95_30d_usd` = 206,315; `junior_share` = 0.5006.
[^h1]: `reports/eval-04-05/handoff.json`: `capital_H.H1.worst_window` = 34,800.
[^fee]: `reports/eval-04-05/handoff.json`: `fee_income_per_usd_notional.bps10` = 0.001, `.bps50` = 0.005; `fee_income_per_season_usd.bps10` = 22,442, `.bps50` = 112,211.
[^cow]: `reports/eval-04-05/handoff.json`: `fee_income_per_usd_notional.cow50` = 0.00402; `fee_income_per_season_usd.cow50` = 90,322.
[^nr]: `reports/eval-04-05/handoff.json`: `netting_ratio.central.pooled` = 0.396; per station `netting_ratio.central.{MIA,NYC,MDW,EWR,TTN}` = 0.649 / 0.356 / 0.320 / 0.211 / 0.130. The 0.25 bar at 3 of 5 stations is rule M1 in `reports/eval-04-05/PREREG.md`.
[^null]: `reports/eval-04-05/handoff.json`: `netting_ratio.null.pooled` = 0.0195.
[^es]: `reports/eval-04-05/handoff.json`: `worst_window_30d_usd` = 412,109; `ES99_30d_usd` = 269,430.
[^m5]: `reports/eval-04-05/results.json`: `verdicts.M5.kupiec.x` = 1, `.n` = 599, `.expected` = 5.99; `verdicts.M5.worst_realized_30day_loss` = 104,387.
[^hel]: `reports/eval-01/results.json`: `verdicts.T1b.he_ladder` = −0.325 (pooled 2022–26); `temperature.pooled[2].he_ladder.est` = 0.371 (rule A, 24 h, pool "liquid 2025+ (post-hoc)", descriptive, not a pre-registered verdict).
[^hc]: `reports/eval-06/results.json`: `verdicts.T2.{G1,G2,G3,G4,G5}.heat_rain_median` = 0.072 / 0.053 / 0.009 / −0.001 / −0.006 (HE_cover, empirical-Bayes arm, daily, primary split). The 0.20 bar is test T2 in `reports/eval-06/PREREG.md`.
[^hl6]: `reports/eval-06/results.json`: `verdicts.T3.G1.ladder_median` = 0.0061, `verdicts.T3.G2.ladder_median` = 0.0009 (heat only); `groups.{G3,G4,G5}.primary.arms.A3.ladder_heat_rain_daily.median` = −0.0006 / 0.0005 / −0.0003.
[^mk]: `reports/eval-04-05/handoff.json`: `house_markout_mean_daily_usd.primary` = 1,154.
[^mk5]: `reports/eval-04-05/handoff.json`: `house_markout_mean_daily_usd.resid_trailing5` = 384.
[^js]: `reports/eval-04-05/junior_returns.json`: `premium_split_mean_observed_season.station_premium` = 2,632,542, `.station_risk_margin` = 39,839, `.splits.spec_t10.senior` = 525,712; `capital.S0` = 205,793. Premium convention in Appendix F item 3.
[^jspec]: `reports/eval-04-05/junior_returns.json`: `observed.primary.spec_t10.by_season.{2023..2026}.junior_return` = −0.065 / −0.924 / −1.434 / −4.494; modelled median `model.splits.spec_t10.boot_median` = −2.14.
[^jb]: `reports/eval-04-05/junior_returns.json` (10% treasury cut, senior on kept margin): `observed.primary.margin_t10.by_season.*.junior_return` = 1.230 / 0.972 / 1.589 / −0.655; `observed.resid_trailing5.margin_t10.by_season.*.junior_return` = 0.719 / 0.422 / 0.872 / −1.114; `model.splits.margin_t10.boot_median` = 0.430, `.boot_p05_1in20` = −1.443, `.sens_whole_season.p05_1in20` = −2.926, `.hist_worst` = −3.319 (`.hist_worst_season` 2009), `.three_season_sum_p05` = −1.899, `.junior_income_needed_per_season_for_rule_usd` = 177,226, `.deterministic_per_season_usd` = 46,611. The three-season rule is 14-RESEARCH §2.4.
[^jt]: `reports/eval-04-05/junior_returns.json`: `premium_split_mean_observed_season.splits.margin_t10.{treasury,senior}` = 3,984 / 7,171 and `.margin_t20.{treasury,senior}` = 7,968 / 6,374, over `.station_premium` 2,632,542; 20% cut modelled median `model.splits.margin_t20.boot_median` = 0.414, 1-in-20 −1.459.
[^e03]: `reports/eval-03/results.json`: `verdicts.winner.temperature` = null (best `bakeoff.temperature.G1-P.pooled_median_dhe` = +0.061, P-A-IDW +0.052, against the +0.10 bar in `reports/eval-03/PREREG.md`); heat ships as the station leg alone with local cover by RFQ (seat ruling 2026-09-30), 30-day capital $416k (`reports/eval-04-05/results.json` `capital.deploy_detrended.pooled_station_leg_only.H30.C`) next to $412k for Phase 4's two-leg book, which used R-A before Phase 3 ran. `verdicts.winner.rain` = G1-P (PRISM per-cell weekly spread), +0.229 on `bakeoff.rain.G1-P.n_pairs` = 26 of 26 (after the 2026-10-02 PRISM re-pull; it was +0.186 on 19 of 26 before); R-A is the alternate. Earlier, ins2's per-grid-cell residual failed on all 1,206 cells.
[^rain]: `reports/eval-04-05/rain_book.json` (weekly wet-day two-leg book, 2% take-up, modelled): `netting.central.pooled` = 0.003; Σ `depth.by_city.<ST>.depth_proxy` = 704 contracts a day against Σ `.mean_net_short_contracts` = 205,019 (about 291 times; a volume proxy, no rain order book on file); `capital.two_leg_joint.H30.C` = 1,081,899 (2024–26; `R2.CPC` = 0.166); `junior.model_MaySep.splits.margin_t10.p05_1in20` = −1.47, `R5.margin_t10.three_season_sum_p05` = −2.36 (FAIL under all four splits). Caveats: 32-month two-leg history; the residual is paid on weekly wet-day counts, untested by Phase 3; depth is a 10%-of-volume guess.
