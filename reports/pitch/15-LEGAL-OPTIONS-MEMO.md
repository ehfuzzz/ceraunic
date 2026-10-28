# weather-insurance: legal options memo for counsel

> **Research for counsel. Not legal advice. Prepared 2026-09-30; rechecked 2026-09-30.**
>
> This gives counsel our facts and the sources we've read. It isn't a legal opinion and clears nothing. Every statement about the law points to a dated source listed in section 9. Where a sentence is our own reading of how the law applies to us, it's tagged **[est.]**. Where a claim comes from memory or a single secondary source and we haven't checked the primary text, it's tagged **[unverified]**. Sources were read on 2026-09-30 unless a different date is given. Treat it as stale after 2026-10-14.
>
> Standing rule (owner, 2026-09-30): nothing goes to mainnet, takes real money, or faces a real customer until counsel has answered.

---

## 1. The facts (no conclusions)

We're building a way for a small business to hedge its own local weather, like a Brooklyn café that sells less on very hot or rainy days. The only liquid US weather contracts settle at a few official stations (Kalshi's daily temperature and rain markets), but the business cares about the weather at its door. The gap between the station and the shop is the residual.

What the prototype does today (sources: OWNER-RULINGS.md and Phase 7 spec decisions, 07-CONTEXT.md, both 2026-09-30):

- **Path (a), the default.** The business buys one policy from us: a cash payout per °F above a strike, or per inch of rain, on a named location and day. The house hedges the station part in its own Kalshi account and puts the residual into our auction. The customer's contract doesn't mention or depend on the house's Kalshi positions.
- **Path (b), the fallback.** The business buys the Kalshi station ladder itself, in its own account. Our portal shows which contracts and how many, sized from its sales data. We sell only the residual ("basis") contract.
- **The residual contract.** A fully collateralised contract that pays on the difference between a local index (a regional average or a nearby station) and the Kalshi settlement station. Settlement data is NOAA and possibly PRISM (Oregon State University). No proof of loss: the payout depends only on the reported number.
- **The auction.** Residual contracts trade in a uniform-price batch auction on HyperEVM, open to any wallet (owner ruling). A one-way RFQ lets the house and whitelisted makers quote firm prices.
- **The pool.** A USDC vault backs the residual and tail risk. A junior layer takes losses first (protocol-owned, seeded by the house; in v0 only the house can deposit). A senior layer takes outside LPs, who get a transferable share token.
- **The token.** By owner ruling, the token (codename WI) is the pool's junior first-loss capital and carries votes on risk parameters. In the current spec WI has a fixed supply, and staked WI votes and is burned pro rata (capped per event) when the junior layer loses money. What stakers earn is left open for this memo; in v0, nothing.
- **Status.** Testnet only, mock USDC, no points, airdrops, customers or real money. We read Kalshi's public, keyless endpoints (book recorder, research, portal quotes) and place no orders. The owner plans a pre-seed raise of about $500k to $1.5M.

## 2. The fork: swap or insurance

**Our reading of the statute.** The Commodity Exchange Act defines a swap to include any payment "dependent on the occurrence, nonoccurrence, or the extent of the occurrence of an event or contingency associated with a potential financial, economic, or commercial consequence", and the examples name "a weather swap" outright (CEA §1a(47)(A)(ii) and (iii)(XVII), 7 U.S.C. 1a(47)). None of the §1a(47)(B) exclusions seem to fit a cash-settled weather payout **[est.]**. The 6th Circuit's narrow "swap" reading (section 6) still keeps weather inside the definition, which fits this fork **[est.]**.

**The only way out is the insurance safe harbour.** A contract isn't a swap if it passes a Product Test and a Provider Test, or if it's an "Enumerated Product" (which includes property and casualty insurance) and passes the Provider Test (17 CFR 1.3 "Swap" para (4), eCFR 2026-09-01; 77 FR 48208, 13 Aug 2012). The Product Test needs an insurable interest, a "loss to occur and to be proved", a payment no bigger than the insurable interest, and no separate trading. The Provider Test needs a state-supervised insurer and a contract "regulated as insurance under applicable State law".

A pure index payout fails the Product Test (no loss is proved), and an unlicensed company fails the Provider Test however the product is designed **[est.]**. Whether a filed parametric policy from a real carrier counts as an Enumerated Product is open (Q7).

**The door closes behind it.** CEA §12(h) says a swap "shall not be considered to be insurance" and "may not be regulated as an insurance contract under the law of any State" (7 U.S.C. 16(h)). We see no third bucket: it's a swap (CFTC) or insurance from a supervised insurer (the state) **[est.]**. New York's OGC said in 2000 that weather derivatives aren't insurance under §1101(a) because "the issuer is obligated to pay the purchaser whether or not that purchaser suffers a loss", with a caveat for "unique circumstances" (Op. 00-02-05, 2000). With §12(h), our unlicensed contract looks like a swap in NY **[est.]**.

**Why this matters.** CEA §2(e) makes it unlawful for anyone who isn't an eligible contract participant (ECP) to enter a swap unless it's on or subject to the rules of a designated contract market (DCM) (7 U.S.C. 2(e)). A business is an ECP only with more than $10M in assets, or more than $1M net worth and a contract hedging its business (CEA §1a(18)(A)(v)). Many cafés clear neither. So if the policy is a swap, selling it off-exchange to most of our customers is the problem, not the house's Kalshi hedge **[est.]**.

One more point shapes route (ii): using "a weather derivative or catastrophe swap to assume all or part of the risks contained in a portfolio of property and casualty insurance policies" is still a swap (77 FR 48208, fn. 41). Behind a carrier, our pool has to take risk through genuine reinsurance, not a weather swap **[est.]**.

## 3. Path (a) house hedge vs path (b) overlay: who is an intermediary

Four CEA roles matter (7 U.S.C. 1a):

- **FCM** (§1a(28)): takes orders for futures or swaps and accepts money to margin them.
- **Introducing broker** (§1a(31)): takes those orders without holding the money.
- **Commodity trading advisor** (§1a(12)): paid advice "as to the value of or the advisability of trading in" futures or swaps.
- **CPO / commodity pool** (§1a(10), (11)): pooled money "for the purpose of trading in commodity interests, including any ... swap".

**Path (a).** If the house hedges its own net book in its own Kalshi account, with no customer money at Kalshi and no link between the customer's contract and the house's fills, that looks like proprietary trading by a Kalshi member, not FCM or IB activity for that leg **[est.]**. The legal weight sits on the policy (section 2), not the hedge.

That changes if the house buys the ladder *for* the customer or passes the payout through. Kalshi's rulebook bars transferring "the benefit of any position ... other than through a transaction executed through the Platform" (Rule 5.17(f)) and says "No Person shall trade for a Person other than itself" (Rule 5.17(g)(1)) (DCM Rulebook v1.29, read 2026-09-30). The Developer Agreement §3.2 bars "facilitating trading or account creation by other members". Taking orders and money for DCM trades is the FCM definition **[est.]**. Our engine keeps these apart, but does the phrase "hedged on a CFTC-regulated exchange" in customer copy create a problem (Q2)?

**Path (b).** The portal tells a business how many Kalshi contracts to buy from its own sales. That looks like tailored CTA advice, so the non-tailored exemption (17 CFR 4.14(a)(9)) doesn't help **[est.]**. The small-adviser exemption covers 15 or fewer persons in 12 months with no general holding out (17 CFR 4.14(a)(10); CEA §4m(1)). That fits a concierge pilot at most, and we don't know whether a public website is holding out (Q5).

If the portal also routes orders or earns per-trade or referral fees, that raises the IB question. CFTC Staff Letter 26-25 (17 Sep 2026) gives passive software providers no-action relief from IB registration on ten conditions. It excludes anyone who holds user assets, has routing discretion, or "generate[s] express 'buy' or 'sell' signals", and it's IB relief only, not CTA. Whether "suggested cover: 12 contracts" is such a signal is Q6.

## 4. Open residual auctions and retail wallets

The owner's ruling is that anyone with a wallet can trade in the residual auction. On mainnet we should assume it's the riskiest piece of the design.

**The statute.** "No person may operate a facility for the trading or processing of swaps unless the facility is registered as a swap execution facility or as a designated contract market" (CEA §5h(a)(1), 7 U.S.C. 7b-3(a)(1)). With §2(e), retail trading of swaps by US persons is lawful only on a DCM **[est.]**. The CFTC's June 2026 proposal says the same: "a prediction market that offers event contracts for trading by the general public in the form of swaps or futures contracts must register with the CFTC as a DCM", citing CEA §2(e) (91 FR 35806, 12 Jun 2026, read 2026-09-30). Comments closed 27 Jul 2026, with no extension or final rule under RIN 3038-AF65. It's a proposal, not a rule. A batch auction where many wallets bid on residual contracts looks like a facility for trading swaps even if every participant were an ECP **[est.]**. A single-dealer RFQ, where only the house quotes and the customer accepts, is generally not many-to-many, but counsel should confirm (Q4).

**The enforcement record is direct.**

- Polymarket (CFTC, 3 Jan 2022, PR 8478-22): event markets "constitute swaps" and "can only be offered on a registered exchange". $1.4M penalty.
- Opyn, ZeroEx and Deridex (CFTC, 7 Sep 2023, PR 8774-23): charged with failing to register as SEF/DCM and FCM. Blocking US IP addresses was "not sufficient". Penalties of $250k, $200k and $100k.
- bZeroX and Ooki DAO (CFTC, 22 Sep 2022, PR 8590-22; 9 Jun 2023, PR 8715-23): the founders were charged personally, and a DAO was held to be a "person".

"It's decentralised" and "we geo-block the US" have each already failed on facts close to ours **[est.]**. The workable options we see: list the residual on a DCM (route iii), gate it to KYC'd ECPs facing only the house, or not serve US persons.

## 5. Pool and token

**The pool as a commodity pool (CFTC).** If outside money, from LPs or token holders, funds a vault that writes residual contracts and holds Kalshi hedges, that fits the commodity pool definition, and whoever runs it looks like a CPO (CEA §1a(10), (11)) **[est.]**. The usual light-touch exemption needs a Reg D 506(c) or 144A offering plus a trading limit of 5% margin or 100% net notional (17 CFR 4.13(a)(3), eCFR 2026-09-01). A pool whose whole job is writing weather contracts probably fails that limit **[est.]**. The August 2026 CPO/CTA proposal might help at the margins (91 FR 54264; comments close 5 Oct). If the pool instead writes genuine reinsurance behind a carrier (route ii), the CPO question may fall away, because it isn't trading swaps **[est.]**.

**The token as a security (SEC).** The SEC's interpretive release of 17 Mar 2026, which the CFTC joined, sorts crypto assets into five categories (91 FR 13714, 23 Mar 2026). A digital commodity "does not have intrinsic economic properties or rights, such as generating a passive yield or conveying rights to future income, profits, or assets of a business enterprise". If WI holders, as the pool's junior capital, receive premium and absorb underwriting losses, that points to "digital security" or investment contract **[est.]**.

Its comfort for governance covers a functional crypto system (upgrades, treasury), not votes over a business's risk book, and its staking comfort covers proof-of-stake consensus only **[est.]**. The current spec, where stakers earn nothing and get burned on losses, avoids "passive yield" for now. Any answer to "why hold WI?" that pays stakers from premium puts us back in the security bucket **[est.]**.

**The closest precedent** is BarnBridge. The SEC found its tranched "SMART Yield" products were unregistered securities and the pools unregistered investment companies, with $1,457,000 in disgorgement plus $125,000 per founder (Rel. 33-11262, 22 Dec 2023). Our tranche design looks like the same shape, Investment Company Act point included **[est.]**.

**What might help, and what won't.** Proposed Regulation Crypto Assets adds offering exemptions ($5M per four years, $75M per 12 months) and a Rule 400 safe harbour for when an investment contract "has ceased to exist" (91 FR 54510, 21 Aug 2026; comments close 20 Oct). A token that is itself a claim on pool income probably stays a security **[est.]**. The CLARITY Act passed the House on 17 Jul 2025, but Senate cloture failed on 15 Sep 2026, and coverage calls passage this year unlikely (CNBC, 15 Sep 2026).

**Governance.** Ooki DAO (PR 8715-23) says token-holder voting shields no one. Until Q10 is answered, the plan is an entity with accountable officers and token votes advisory at most. Decks should call the token "junior capital in a pool, offered only to eligible investors under an exemption", never "stake to earn yield".

## 6. Venue dependence: Kalshi's terms, the data licence, state litigation

The station leg of the hedge lives on Kalshi today. That's three separate risks.

**Kalshi's own terms** (all read 2026-09-30):

- **Member Agreement** §V.E: "not allow any person not identified to Kalshi to access or use these Services".
- **Developer Agreement v1.1** (file dated 9 Nov 2023): API use "is expressly limited to facilitating a members own trading" (§3); no caching or sharing API data (§3.1); no facilitating other members' trading (§3.2); no API use for "benchmarking or competitive purposes" (§3.5); users must be Kalshi Members (§4.1.1); prior approval for promotional or marketing materials relating to Kalshi (§6.4). Kalshi's docs say continuing to use the API means "agreeing to be bound" (docs.kalshi.com/welcome). The docs link to kalshi.com/developer-agreement, which blocked us, so a newer version there is **[unverified]**.
- **Data Terms of Use**: personal, non-commercial use only. No use of Kalshi Data "to create, calculate, issue, settle, maintain, support or develop any financial instruments (including ... swaps, options ...), indexes, products, services (including ... risk management services, or valuation services)" without written consent, and no machine-learning use.
- **Liquidity Incentive Program**: ends 1 Jan 2027; excludes "Introducing Brokers, FCMs, and their customers" and "International, non-U.S. users".

Our use today is keyless (book recorder, research paper, portal quotes). Whether keyless use binds us is a licence question, not a settled breach **[est.]**. But pricing a commercial product off Kalshi books without a written licence looks like what the Data Terms forbid **[est.]**. Counsel should check the keyless book recorder and our research use against §3.5 (and §4.1.1), since both collect Kalshi data for analysis.

**What the owner should ask Kalshi for** (agents contact no one):

1. a written data licence to price, size and risk-manage our own contracts, and for dashboards and the paper;
2. whether the keyless recorder and research use already needs one, including under §3.5;
3. whether Kalshi would list regional or grid weather contracts and designate us as a weather market maker (Rule 4.2(a));
4. how hard entity onboarding is for a small business in path (b) **[unverified]**;
5. §6.4 permission to name Kalshi in investor decks.

**State litigation.** None of these cases is about weather, but the station leg depends on a venue that states are attacking. As of 30 Sep 2026 nothing is in force against Kalshi in New York:

- **NY AG v. KalshiEX**, filed 31 Jul 2026 seeking a TRO on event contracts and more than $36B, removed to SDNY the same day (1:26-cv-06550). The remand motion has been fully briefed since 28 Aug, with no ruling and no TRO on the docket (CourtListener, read 2026-09-30).
- **NY AG v. Polymarket US**, filed 24 Sep 2026 and removed to SDNY the same day (1:26-cv-08338). NY also sued Coinbase and Gemini in April (secondary); we found no NY action against Robinhood or Crypto.com **[unverified]**.
- **CFTC v. New York** (1:26-cv-03404): argued 14 Sep 2026 (secondary); no ruling on the docket through 28 Sep.
- **Michigan** ordered trade cancellations (TRO 29 Jun 2026); the CFTC acted on 14 Jul and 11 Aug (PR 9267-26, 9281-26).
- **Circuit split.** The 3rd Circuit held NJ's sports-gambling rules preempted (*Flaherty*, 172 F.4th 220 (3d Cir. 2026); holding details **[unverified]**); NJ petitioned for certiorari on 2 Sep 2026 and Kalshi's response is due 8 Oct. The 9th Circuit (28 Aug 2026, Nevada) went the other way on sports, as did the 6th Circuit (*KalshiEX v. Schuler*, 25 Sep 2026), holding Kalshi's sports contracts aren't swaps. Its footnote 7 says weather swaps are, given their "historic and widely accepted association with economic risk" (read 2026-09-30). The CFTC has also sued nine states (PR 9206-26, 9218-26, 9260-26).

NY's theory, that outcomes are "uncertain and outside the control of the bettor", isn't limited to sports, and NY asked to halt all Kalshi event contracts **[est.]**. So the risk isn't that weather gets banned. It's that our station-leg venue gets enjoined in a state where our customers are. Two mitigations we can build now: an engine that can use a second DCM (ForecastEx lists "climate" contracts; CME weather futures **[unverified]**), and, under route (ii), claims paid whether or not the hedge venue is up.

## 7. Three routes, one hybrid, and the gates before mainnet

Time and cost figures are comparables, not quotes.

| | (i) Offshore entity + US geo-block; a US affiliate trades the Kalshi leg | (ii) Parametric insurance: a carrier issues; we run pricing, risk and the pool | (iii) A partner DCM lists regional/grid contracts; we're the market maker |
|---|---|---|---|
| Who sells to the US business | Nobody offshore (US persons are blocked). The US affiliate can only trade its own book or give advice | The carrier (admitted, or surplus lines through a broker, NY Ins. Law §2105). We act as MGA or program administrator | The DCM. The business is a direct member or FCM customer; we quote as market maker; the portal is a passive front end |
| What the residual legally is | A swap, sold to non-US persons | Insurance (filed policy; Provider Test met), not a swap **[est.]** | An exchange-traded swap/event contract, lawful for non-ECPs |
| Open auction with retail wallets | Non-US wallets only, and IP blocking isn't enough (Opyn). The US founder is still exposed under CEA §2(i) | Not on the policy itself (Product Test: not traded separately). Any auction moves to the reinsurance layer among eligible investors | Yes, on the DCM's own book. On-chain access only through KYC'd wrappers, like DFlow's Kalshi tokens on Solana (1 Dec 2025) |
| Token | Offshore junior token; US securities and CPO law still reach US-person promoters | An interest in a reinsurance/ILS vehicle, so a security, sold to eligible investors | No natural pool role. Market-making capital is ours or a fund's |
| Biggest open question | Who's the customer, if US businesses are blocked? | Will a carrier front $30–$120/day micro-covers with an on-chain reinsurer? Does NY's parametric line cover a daily index? | Will a DCM list thin location contracts and pay incentives on them? |
| Rough time and cost | Unsourced; get a quote. Nayms took about 2 years in the Bermuda sandbox (May 2022) | 6–12 months to a first state **[est.]**; fronting carriers keep about 10–20% of premium (secondary) | Listing the business day after a 40.2 filing **[unverified]**; own DCM "multi-month to multi-year" (Katten, 20 Nov 2025) |
| Our read **[est.]** | Weakest for this product | Best fit for the last-mile residual | Best fit for station and regional legs; pairs with (ii) |

**Route (i) blocks our own customers.** Every business we'd hedge sits near a US station (NYC, Chicago, Miami). An offshore venue that geo-blocks the US can host non-US traders and LPs, but it can't sell to the café. CEA §2(i) reaches offshore activity with "a direct and significant connection with activities in, or effect on, commerce of the United States" (7 U.S.C. 2(i)), and the founder is a US person. Ensuro, the closest on-chain analogue to our pool, is Bermuda-licensed and restricts the US. This also conflicts with the owner's defi-options ruling "do not go offshore" (K-BS(c), 2026-09-28). This project has no offshore ruling yet, so route (i) appears only as a possible home for non-US capital, and that needs his decision.

**Route (ii) has a working template.** NY created a licensed parametric line: "insurance against the occurrence of a weather-related event ... where the indemnification is based on the proximity and magnitude of the event as measured and reported by a state or federal government agency" (NY Ins. Law §1113(a)(34), ch. 569 of 2024, signed 13 Dec 2024). The law was introduced at DFS's request, adds a §3416 disclosure (the policy isn't a substitute for property or flood insurance), and lets excess line brokers place it (§2105) (A10344, read 2026-09-30). Its examples are windstorm, flood, snow, wildfire, tornado, cyclone and earthquake, so a daily temperature or rain index is an open question (Q7). We found no 2026 statement on parametric weather cover from NY DFS or the Illinois, Florida or New Jersey regulators. Sola sells admitted parametric tornado cover for about $88 a year in 15 states on an NWS trigger (Artemis, 31 Aug 2023; premium secondary). Descartes is the other end, with a "usually" $50,000 minimum premium (25 Jun 2025).

**Route (iii) is the only lawful way retail can trade these contracts in the US** (CEA §2(e)) **[est.]**. Weather isn't a category the CFTC can bar (CEA §5c(c)(5)(C)), and the June 2026 proposal calls weather contracts "uncontroversial" on DCMs (91 FR 35806). The catch: a DCM has to want thin contracts, and being market maker while running the portal brings conflict rules (Rule 4.4; 91 FR 50926).

### The hybrid we'd like counsel to test

Our suggestion **[est.]**:

1. **Station and regional legs on a DCM (route iii).** We make markets; the portal is a passive front end under Letter 26-25, or we register as a CTA.
2. **The last-mile residual as a carrier-issued parametric policy (route ii).** Filed policy, NOAA trigger, insurable-interest check, payout capped at documented revenue exposure. We act as MGA.
3. **The on-chain pool as collateralised reinsurance for eligible investors.** Genuine reinsurance, 100% collateralised, not a weather swap (77 FR 48208, fn. 41), sold only under a securities exemption.
4. **No "any wallet" trading of our own residual contracts for US persons.** That reverses a current owner ruling, so it's his call.

### Gates before mainnet

1. Counsel's written answer to the fork (Q1) and the auction (Q4).
2. A route picked by the owner, with its carrier, DCM or FCM partner signed.
3. A Kalshi (or other DCM) data licence, or quotes that use no Kalshi data (Q13).
4. No retail wallet faces our contract outside a DCM: the auction is ECP/KYC-gated, single-dealer, or replaced.
5. No public token sale or distribution before the securities and CPO answers (Q9, Q10); no testnet points (Q14).
6. A NOAA oracle with a stated revision policy. PRISM only with written commercial terms: its web terms say data "may be freely reproduced and distributed", but an older PDF says "Sale or other commercial use of the data must be arranged".
7. A venue-continuity plan for Kalshi's state litigation.
8. An entity with accountable officers; token votes aren't the legal decision-maker.
9. An owner ruling on offshore posture.
10. Ideally one counsel engagement shared with defi-options, whose CPO questions overlap.

## 8. Questions for counsel

1. **The fork.** Is a cash payout of $X per °F above a strike (or per inch of rain) on NOAA-reported data at a named location a "swap" under CEA §1a(47)(A)(ii)/(iii), when sold by an unlicensed company to a business with no proof-of-loss condition? Would an insurable-interest attestation, a payout cap at documented revenue exposure and a loss affidavit change that, or is failing the Provider Test decisive?
2. **Path (a) house hedge.** The house sells its own contract and separately hedges in its own Kalshi account, with no reference to its positions and no customer funds at Kalshi. Is it acting as an FCM, IB or CPO for the Kalshi leg? Does wording such as "hedged on a CFTC-regulated exchange" raise Kalshi Rule 5.17(f)/(g)(1) or FCM issues?
3. **An ECP-only channel.** Can we offer the residual bilaterally to businesses that certify ECP status under §1a(18)(A)(v)(III), with the house as sole counterparty? What swap-dealer (de minimis), Part 43/45 reporting and documentation duties apply at our size? Is a no-action request (Reg 140.99) or §4(c) exemption realistic for non-ECP businesses?
4. **The auction.** Is a uniform-price batch auction on HyperEVM, where many wallets post bids and offers on residual contracts, a "facility for the trading or processing of swaps" (§5h(a)(1)) even if limited to ECPs? Does a single-dealer RFQ to the house avoid SEF/DCM status?
5. **Overlay advice.** In path (b), is sizing a ladder from a business's own sales "commodity trading advice" (§1a(12))? Can a concierge pilot of 15 or fewer businesses rely on 4.14(a)(10)/§4m(1), and does a public website count as "holding out"? Is CTA registration needed for self-serve?
6. **Front-end relief.** Can the portal qualify as a Passive Software Provider under Letter 26-25 if it shows an elasticity estimate and a suggested cover, but the user places each order at Kalshi or an FCM? Where's the line between information and an "express 'buy' or 'sell' signal"?
7. **The insurance route.** Under NY Ins. Law §1113(a)(34), is a daily temperature or rainfall index at a business location a "weather-related event"? Does NOAA gridded data count as "measured and reported by a state or federal government agency", and does PRISM, from Oregon State? Is such a policy "property and casualty insurance" for the Enumerated Products prong of 17 CFR 1.3 para (4)? How do IL, FL and NJ treat it?
8. **Our role in route (ii).** Can we act as MGA or program administrator (pricing engine; binding within carrier guidelines) with producer licences, while a separate vehicle provides on-chain collateralised reinsurance? Does that meet the reinsurance prong of the Provider Test (para (4)(i)(B)(3)) if the vehicle is in Bermuda? What collateral would a fronting carrier need?
9. **Pool and CPO.** If token holders fund a pool that writes residual contracts and holds Kalshi hedges, is it a commodity pool, and are we its CPO? Do 4.13(a)(3), 4.7 or 91 FR 54264 help? If the pool is instead a reinsurance vehicle, does the CPO question go away?
10. **The token.** Is a transferable junior-tranche token that receives premium and takes first loss a security under *Howey* and the 17 Mar 2026 interpretation (91 FR 13714)? What about the current spec, where staked WI earns nothing and is burned on losses? Which exemption fits the pre-seed raise and a later LP distribution: Reg D 506(b)/(c), Reg S, or proposed Reg Crypto Assets? Is BarnBridge the controlling precedent, Investment Company Act point included? Does token voting on risk parameters create Ooki-style liability?
11. **The offshore route.** For a US-person founder, does an offshore opco running the auction and pool for non-US persons, with a US affiliate trading Kalshi for its own account, have a "direct and significant connection" with US commerce (§2(i))? What controls beyond IP blocking have regulators accepted? Which offshore jurisdiction would license it?
12. **The DCM route.** What does a partner DCM need from us to self-certify regional or grid weather contracts under 40.2 (settlement source, revision policy, data rights, manipulation analysis)? As its designated market maker who also runs the portal that suggests those contracts, what conflict rules apply (Rule 4.4; 91 FR 50926)?
13. **Kalshi terms.** Does our keyless use of Kalshi's public endpoints (book recorder, research paper, portal quotes) bind us to Developer Agreement v1.1 and the Data Terms? Does the keyless book recorder or our research use fall under §3.5 ("benchmarking or competitive purposes") or §4.1.1 (users must be Kalshi Members), or breach §3.1 or the ban on pricing or indexing with Kalshi Data? What licence should the owner request? Does §6.4 limit naming Kalshi in investor decks?
14. **Testnet.** Is a public HyperEVM testnet with mock USDC, open wallets and no points or airdrops free of CEA and securities exposure? What must we avoid saying during the pre-seed raise while it runs?
15. **State exposure.** Given NY AG v. KalshiEX (31 Jul 2026, removed, remand pending with no ruling or TRO as of 30 Sep 2026), NY AG v. Polymarket US (24 Sep 2026, removed) and the circuit split (3rd Cir. for Kalshi; 9th Cir., 28 Aug 2026, and 6th Cir., 25 Sep 2026, against), could a state treat a weather event contract bought by a local business as gambling or insurance despite CEA §12(h)? Does that change which DCM we should use for the station leg?

**Things we couldn't find or check** (so counsel knows where our research stops): the NAIC weather-derivatives white paper (not located), and a claimed 2025 NAIC parametric model act that has no source and isn't on NAIC's page **[unverified]**; IL, FL and NJ regulators on index weather cover (searched 30 Sep, nothing found; the NJ and FL bulletin pages didn't load); the 3rd Circuit *Flaherty* holding (secondary only); CME weather futures today (CME blocks automated access); Arbol's derivatives counterparties and Nayms's participant limits; a newer Kalshi Developer Agreement at kalshi.com/developer-agreement (blocked); and the PRISM terms conflict.

## 9. Appendix: sources with dates

Primary texts were read on 2026-09-30 unless a different date is given. Items marked "search summary" or "secondary" weren't checked against the primary text.

### Statutes and rules
- CEA, 7 U.S.C. 1a (§1a(10), (11), (12), (18), (28), (31), (47), (49), (50)); 7 U.S.C. 2(e), 2(i); 7 U.S.C. 7a-2(c)(5)(C); 7 U.S.C. 7b-3(a)(1); 7 U.S.C. 16(h). uscode.house.gov (title 7); law.cornell.edu/uscode/text/7/16. Read 2026-09-30.
- 17 CFR 1.3 ("Swap" para (4), (6); "Swap dealer" (4)(i)(A)); 17 CFR 4.13(a)(3); 17 CFR 4.14(a)(9)–(10). eCFR, version 2026-09-01.
- CFTC/SEC product definitions, 77 FR 48208 (13 Aug 2012). federalregister.gov/documents/2012/08/13/2012-18003
- NY Ins. Law §1101(a); §1113(a)(34), §3416 disclosure, §2105 excess-line placement, A10344/S9420, ch. 569 of 2024, signed 13 Dec 2024. nysenate.gov/legislation/bills/2023/A10344 (read 2026-09-30). NAIC parametric page, content.naic.org/insurance-topics/parametric-disaster-insurance (read 2026-09-30; no model act mentioned).
- NY OGC Opinion 00-02-05 (15 Feb 2000). dfs.ny.gov/insurance/ogco2000/rg000205.htm

### Federal Register, 2026
- CFTC proposal 91 FR 35806 (federalregister.gov/documents/2026/06/12/2026-11854), re-read 2026-09-30 for the DCM-registration sentence and docket status (RIN 3038-AF65).
- CFTC: withdrawal of 2024 event-contracts NPRM, 91 FR 5386 (6 Feb 2026); ANPRM "Prediction Markets", 91 FR 12516 (16 Mar 2026); NPRM "Prediction Markets; Public Interest Determinations", 91 FR 35806 (12 Jun 2026); data reporting NPRM, 91 FR 40102 (1 Jul 2026); "Conflicts and Affiliations" NPRM, 91 FR 50926 (6 Aug 2026); CPO/CTA exemptions NPRM, 91 FR 54264 (21 Aug 2026).
- Joint SEC/CFTC request for comment on the "swap" definition, 91 FR 37873 (24 Jun 2026).
- SEC: crypto-asset interpretation, press release 17 Mar 2026, published 91 FR 13714 (23 Mar 2026); proposed Regulation Crypto Assets, 91 FR 54510 (21 Aug 2026).

### CFTC and SEC orders, letters and releases
- CFTC PR 8478-22, Polymarket (3 Jan 2022); PR 8590-22, bZeroX (22 Sep 2022); PR 8715-23, Ooki DAO (9 Jun 2023); PR 8774-23, Opyn/ZeroEx/Deridex (7 Sep 2023). cftc.gov/PressRoom/PressReleases
- CFTC PR 9113-25, QCX amended designation (25 Nov 2025); PR 9164-25, Chairman Selig sworn in (22 Dec 2025); PR 9185-26, enforcement advisory (25 Feb 2026); PR 9206-26, 9218-26, 9260-26, suits against states (Apr–Jun 2026); PR 9267-26 (14 Jul 2026); PR 9281-26 (11 Aug 2026); PR 9300-26, Letter 26-25 (17 Sep 2026).
- CFTC Staff Letter 26-25 (17 Sep 2026). cftc.gov/csl/26-25/download. Letter 26-09 (Phantom, 17 Mar 2026), as cited in 26-25.
- CFTC Staff Letter 25-28, QCX swap-data no-action (3 Sep 2025).
- SEC Rel. 33-11262, BarnBridge DAO (22 Dec 2023). sec.gov/files/litigation/admin/2023/33-11262.pdf

### Kalshi documents (read 2026-09-30)
- DCM Rulebook v1.29 (Rules 4.1–4.5, 5.17(e)–(g)). kalshi-public-docs.s3.amazonaws.com/regulatory/rulebook/
- Member Agreement (S3 copy "v1.4"; updated agreement noticed 23 Oct 2025). kalshi-public-docs.s3.amazonaws.com/regulatory/agreement/kalshi_member_agreement.pdf
- Developer Agreement v1.1 (file dated 9 Nov 2023; §3.5, §4.1.1, §6.4). kalshi-public-docs.s3.amazonaws.com/Kalshi-Developer-Agreement.pdf
- Kalshi API docs, docs.kalshi.com/welcome ("agreeing to be bound"). Read 2026-09-30.
- Data Terms of Use. kalshi-public-docs.s3.amazonaws.com/kalshi-data-terms-of-service.pdf
- Liquidity Incentive Program (ends 1 Jan 2027). help.kalshi.com/incentive-programs/liquidity-incentive-program

### Litigation
- NY AG release, suit against Kalshi (31 Jul 2026). ag.ny.gov
- NY v. KalshiEX, 1:26-cv-06550 (S.D.N.Y.), CourtListener docket 73700030, read 2026-09-30 (remand fully briefed since 28 Aug; no ruling or TRO).
- *KalshiEX v. Schuler* (6th Cir., 25 Sep 2026), opinion 26a0272p-06, opn.ca6.uscourts.gov/opinions.pdf/26a0272p-06.pdf. Read 2026-09-30.
- NY v. Polymarket US, removed to S.D.N.Y. 24 Sep 2026, 1:26-cv-08338; CFTC v. New York, 1:26-cv-03404 (argued 14 Sep, secondary). Read 2026-09-30.
- NY AG release, suit against Polymarket US (24 Sep 2026). ag.ny.gov
- NJ petition for certiorari, *Flaherty v. KalshiEX* (2 Sep 2026), njoag.gov; cited as 172 F.4th 220 (3d Cir. 2026).
- Holland & Knight on the 9th Circuit Nevada decision (28 Aug 2026). hklaw.com (secondary)
- SDNY 1:25-cv-08846 PI denial (7 Jul 2026) and Michigan TRO (29 Jun 2026): search summaries only.

### Market structures and precedents
- Ensuro site and terms, read 2026-09-30. ensuro.co; docs.ensuro.co
- Nexus Mutual docs and DAO member agreement (dated 24 Feb 2022). docs.nexusmutual.io
- Descartes, US Flood-at-Location (25 Jun 2025). descartesunderwriting.com
- FloodFlash (FCA FRN 784452); ForecastEx. floodflash.co; forecastex.com. Read 2026-09-30.
- DFlow tokenized Kalshi markets on Solana (1 Dec 2025). solana.com/news/dflow-prediction-markets-api
- PRISM terms, web and PDF, read 2026-09-30. prism.oregonstate.edu/terms/; prism.oregonstate.edu/documents/PRISM_terms_of_use.pdf
- Artemis on Sola, Beazley and Spinnaker (31 Aug 2023) (secondary).
- Katten, DCM application advisory (20 Nov 2025) (secondary).
- Latham US Crypto Policy Tracker (updated Aug 2026); CNBC on CLARITY cloture (15 Sep 2026) (secondary).
- Jones Day on Letter 26-25 (Sep 2026); WilmerHale on the June 2026 NPRM (18 Jun 2026) (secondary).
- Crowdfund Insider on Nayms (May 2022); Polymarket/QCEX acquisition ($112M, Jul 2025, PR Newswire); fronting retention (Insurance Business); reinsurance collateral (Mayer Brown) (secondary).

### Sister-project and internal sources
- defi-options owner ruling K-BS(c), "do not go offshore" (2026-09-28).
- defi-options legal notes, `notes-D-legal-pm.md` (2026-09-23): OKX plea (24 Feb 2025), DCM cost and timeline figures, cert No. 26-299. Not re-checked **[unverified]**.
- weather-insurance OWNER-RULINGS.md (2026-09-30) and Phase 7 context (2026-09-30), for the facts in section 1.
- Full research file with confidence ratings: `.planning/phases/15-legal-memo/15-RESEARCH.md` (2026-09-30).
