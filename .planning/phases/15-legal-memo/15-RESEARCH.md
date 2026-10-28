# Phase 15: Legal-options memo - Research

**Researched:** 2026-09-30
**Domain:** US derivatives law (CFTC/CEA), state insurance law, securities law (token), DeFi and parametric-insurance precedents
**Confidence:** MEDIUM overall. Statute and rule text: HIGH (fetched from primary sources). How it applies to our facts: LOW–MEDIUM. Only counsel can settle that part.

> **Not legal advice.** This is research to help write a memo for counsel. It is not a legal opinion, and nothing here clears any activity. Every conclusion tagged [est.] is our reading of the law, not counsel's. Nothing goes to mainnet, takes real money or faces a real customer until counsel answers (owner ruling 2026-09-30).
> Tags: [est.] = our inference; [unverified] = one secondary source or recalled; [sister] = taken from `~/Desktop/defi-options/.planning/research/notes/notes-D-legal-pm.md` (2026-09-23), not re-checked here. "Fetched" = primary text read on 2026-09-30.

## Summary

We read the statutes and rules that decide what this product legally is. Covered: the CEA swap definition and the insurance safe harbour, CEA §2(e), the FCM/IB/CTA/CPO definitions, Kalshi's rulebook, member, developer and data terms, and CFTC Letter 26-25. On insurance: NY Insurance Law §1101(a), the new NY parametric line §1113(a)(34) and NY OGC Opinion 00-02-05. On securities: the SEC's March 2026 crypto interpretation and the August 2026 Regulation Crypto Assets proposal. We also pulled every 2025–2026 CFTC event-contract rulemaking from the Federal Register, the Kalshi and Polymarket state litigation, and the structures of Arbol, FloodFlash, Descartes, Raincoat, Sola, Etherisc, Nayms, Ensuro, Nexus Mutual, Polymarket US and Kalshi's partners.

**The one finding that drives everything is a fork.** A cash payout on temperature or rain at a place, with no proof of loss, is a "swap" under CEA §1a(47). The statute names "a weather swap" outright. It stops being a swap only if a state-supervised insurer provides it and state law regulates it as insurance (17 CFR 1.3 "Swap" para (4)). CEA §12(h) then bars states from treating any swap as insurance. There is no third bucket. It follows that:
- In path (a), the legal problem is the policy itself (an off-exchange swap with a business that is usually a non-ECP, barred by CEA §2(e)), not the house's Kalshi trades.
- In path (b), the residual is still our swap, and the hedge-size advice adds CTA and IB questions.
- A residual auction open to any wallet is an unregistered swap trading facility (CEA §5h; Polymarket 2022; Opyn 2023).
- A junior token that earns premium and takes first loss is very likely a security and possibly a commodity-pool interest (March 2026 SEC interpretation; BarnBridge 2023).

**Routes.** Route (i), offshore with a US geo-block, blocks the customers themselves: every target business sits at a US station. Route (ii), a licensed carrier issuing a filed parametric policy, is proven at micro-premium scale. Sola sells admitted parametric tornado cover for about $88 a year through Spinnaker and Beazley. NY has had a parametric line since the 2024 amendment. Route (iii), a partner DCM listing regional contracts with us as market maker, is the only way retail can trade these contracts lawfully in the US, and the CFTC's June 2026 NPRM calls weather contracts "uncontroversial". The station leg also carries venue risk. NY's Attorney General sued Kalshi on 31 Jul 2026 and Polymarket US on 24 Sep 2026 as illegal gambling. Kalshi's data terms also bar using Kalshi data to price or settle instruments without written consent.

**Primary recommendation:** Build the memo around the swap-or-insurance fork. Ask counsel to test one hybrid: station and regional legs on a DCM (route iii), and the last-mile residual as a carrier-issued parametric policy (route ii), with the on-chain pool acting as collateralised reinsurance for eligible investors. For US persons, drop "any wallet" trading of our own residual contracts. Present route (i) only as a non-US capital venue, and flag that it conflicts with the owner's sister-project stance ("do not go offshore", defi-options K-BS(c), 2026-09-28).

## Standard Stack (the governing law)

Here "stack" means the statutes, rules and partner terms the plans must work inside.

### Core
| Law / rule | Cite (as of 2026-09-30) | What it does | Why it binds us |
|---|---|---|---|
| Swap definition | CEA §1a(47)(A)(ii), (iii)(XVII); 7 U.S.C. 1a(47) (fetched) | Swaps include any payment "dependent on the occurrence, nonoccurrence, or the extent of the occurrence of an event or contingency associated with a potential financial, economic, or commercial consequence". The list names "a weather swap". | Our policy and residual are swaps unless the insurance safe harbour applies |
| Insurance safe harbour | 17 CFR 1.3 "Swap" para (4) (fetched); SEC Rule 3a69-1; adopting release 77 FR 48208 (13 Aug 2012) | Not a swap if it passes the Product Test and the Provider Test, or is an Enumerated Product (incl. "property and casualty insurance") and passes the Provider Test. Product Test: insurable interest held for the whole term; "loss to occur and to be proved"; payment ≤ insurable interest; not traded separately. Provider Test: state-supervised insurer, and the contract is "regulated as insurance under applicable State law" (or eligible non-admitted insurer, or reinsurer to one). Non-exclusive (77 FR at 48214). Anti-evasion in para (6). | The only way out of "swap" |
| Swaps are not insurance | CEA §12(h), 7 U.S.C. 16(h), added by Dodd-Frank §722(b) (fetched) | "A swap— (1) shall not be considered to be insurance; and (2) may not be regulated as an insurance contract under the law of any State." | The fork is binary. It also keeps state insurance law off DCM-listed weather contracts |
| Retail swap limit | CEA §2(e) (fetched) | "It shall be unlawful for any person, other than an eligible contract participant, to enter into a swap unless the swap is entered into on, or subject to the rules of, a [DCM]." | Most small businesses; every retail wallet |
| ECP definition | CEA §1a(18)(A)(v), (xi) (fetched) | Entities qualify with total assets >$10M, or net worth >$1M **and** a contract "in connection with the conduct of the entity's business or to manage the risk". Individuals need >$10M invested (>$5M if hedging). | Businesses above $1M net worth that hedge revenue are ECPs [est.], so an OTC channel exists for them only |
| Swap trading facility | CEA §5h(a)(1), 7 U.S.C. 7b-3(a)(1) (fetched); SEF definition §1a(50) | "No person may operate a facility for the trading or processing of swaps unless the facility is registered as a swap execution facility or as a designated contract market" | The multi-wallet residual auction |
| Swap dealer | CEA §1a(49); 17 CFR 1.3 "Swap dealer" (4)(i)(A) (fetched) | De minimis: ≤$8B gross notional of dealing swaps per 12 months (≤$25M with special entities) | The house MM stays under de minimis for a long time. The dealing analysis still applies |
| Intermediaries | CEA §1a(28) FCM, §1a(31) IB, §1a(12) CTA, §1a(11) CPO, §1a(10) commodity pool (fetched); IB registration §4d(g) | Taking orders and customer money = FCM. Taking orders without money = IB. Paid advice on "the value of or the advisability of trading in" swaps/futures = CTA. Pooled funds "for the purpose of trading in commodity interests, including any ... swap" = pool, run by a CPO. | House hedge, overlay path, pool |
| CTA/CPO exemptions | 17 CFR 4.14(a)(9), 4.14(a)(10) / CEA §4m(1), 4.13(a)(3) (fetched) | (a)(9): no advice "tailored to ... particular clients". (a)(10): ≤15 persons in 12 months and no general holding out. 4.13(a)(3): Reg D 506(c)/144A offering plus a 5% margin or 100% net-notional limit | Pilot scale only. The pool likely fails the de minimis trading test [est.] |
| Event contracts on DCMs | CEA §5c(c)(5)(C) (fetched); 17 CFR 40.11; 17 CFR 40.2 self-certification | The CFTC may bar event contracts involving unlawful activity, terrorism, assassination, war, gaming. Other contracts are self-certified (filed by the business day before listing) [40.2 timing from training] | Weather is not enumerated: the route (iii) listing path |
| Extraterritorial reach | CEA §2(i) (fetched) | Swap rules reach offshore activity with "a direct and significant connection with activities in, or effect on, commerce of the United States" | Route (i) |
| Anti-fraud / manipulation | CEA §6(c)(1); 17 CFR 180.1 | Covers swaps and event contracts, including on DCMs (CFTC advisory, 25 Feb 2026) | Oracle and settlement design; house-MM conduct |
| State insurance definition | NY Ins. Law §1101(a) ("material interest which will be adversely affected"), via NY OGC Op. 00-02-05 (15 Feb 2000); NY §1113(a)(34) parametric line (A10344/S9420, ch. 569 of 2024, signed 13 Dec 2024) (fetched) | Defines insurance and a licensed parametric line: "insurance against the occurrence of a weather-related event ... where the indemnification is based on the proximity and magnitude of the event as measured and reported by a state or federal government agency" | Route (ii). An unlicensed index contract is not NY insurance, so it is a swap |
| Securities | Securities Act §2(a)(1), §5; *Howey*; SEC interpretation 91 FR 13714 (23 Mar 2026); proposed Regulation Crypto Assets 91 FR 54510 (21 Aug 2026) (fetched) | How tokens are classified; offering exemptions; investment-contract safe harbour (proposed Rule 400) | Junior tranche token |

### Supporting (relief, guidance, partner terms)
| Item | Date | Use |
|---|---|---|
| CFTC Staff Letter 26-25 (MPD): passive software provider (PSP) no-action from IB registration; extends Letter 26-09 (Phantom, 17 Mar 2026) to all PSPs (fetched) | 17 Sep 2026 | The portal as a front end to a DCM or FCM. Ten conditions: no statutory disqualification; conflict and risk disclosures; users onboard directly as DCM members or FCM/IB customers; NFA-style marketing rules; joint-and-several liability undertaking with each registrant; Reg 1.31 records; notice filing. Excluded if the PSP holds user assets, "generate[s] express 'buy' or 'sell' signals", or has routing discretion. Covers registered venues only. IB relief only, not CTA |
| CFTC Staff Letter 25-28: QCX/QC Clearing swap-data no-action | 3 Sep 2025 | Template for reporting relief on event contracts |
| Kalshi Rulebook v1.29 (fetched): Rule 4.1–4.5 market makers (4.2(a): "financial resources, relevant experience, business reputation"); Rule 5.17(e)–(g); FCM Member and IB Member definitions | current | Route (iii) MM role; limits on path (a) |
| Kalshi Member Agreement (S3 copy "v1.4"; Exchange Notice of an updated agreement 23 Oct 2025) (fetched) | current | §V.E: "not allow any person not identified to Kalshi to access or use these Services". Restricted jurisdictions include Canada, UK, Singapore and Switzerland; Bermuda, Cayman and BVI are not listed |
| Kalshi Developer Agreement v1.1 (fetched) | current | §3: "Use of Kalshi APIs is expressly limited to facilitating a members own trading". §3.1 no caching or sharing API data. §3.2 no "facilitating trading or account creation by other members". §3.7 no sublicensing. §6.4 prior approval for public statements about Kalshi |
| Kalshi Data Terms of Use (fetched) | current | Personal, non-commercial use only. No use of Kalshi Data "to create, calculate, issue, settle, maintain, support or develop any financial instruments (including ... swaps, options ...), indexes, products, services (including ... risk management services, or valuation services)" without written consent. No ML use |
| Kalshi Liquidity Incentive Program (help centre, fetched) | ends 1 Jan 2027 | Ineligible: Kalshi affiliates; "Introducing Brokers, FCMs, and their customers"; "International, non-U.S. users" |
| NY OGC Opinion 00-02-05 (fetched) | 15 Feb 2000 | Weather derivatives are not insurance under §1101(a), because "the issuer is obligated to pay the purchaser whether or not that purchaser suffers a loss". Caveat for "unique circumstances" |

### Alternatives considered (the three routes; detail in the Routes Comparison)
| Instead of | Could use | Tradeoff |
|---|---|---|
| Unlicensed on-chain policy to US businesses | (i) Offshore entity + US geo-block + US affiliate on Kalshi | Blocks the actual customers; Opyn says a geo-block alone fails; the US-person founder stays exposed |
| Unlicensed on-chain policy | (ii) Carrier-issued parametric policy; protocol = pricing/risk engine; pool = reinsurance capital; netting done internally | State forms and a fronting deal needed; token = security; no public trading of the policy |
| Our own residual market | (iii) Partner DCM self-certifies regional/grid contracts; we are the LIP market maker; portal is a passive front end | A DCM must agree to list thin contracts; tailored advice = CTA; the token loses its pool role |

## Findings by Research Question

### Q1. CFTC

**1.1 When a cash-settled weather contract is a swap.** [law HIGH; application MEDIUM]
- CEA §1a(47)(A)(ii) covers any payout tied to an event "associated with a potential financial, economic, or commercial consequence". §1a(47)(A)(iii)(XVII) lists "a weather swap". None of the §1a(47)(B) exclusions fit. The forward exclusion needs physical settlement, and the securities exclusions don't apply.
- The insurance safe harbour (17 CFR 1.3 "Swap" para (4)) needs a qualifying product and a qualifying provider. A pure index payout fails the Product Test ("loss to occur and to be proved"). It can still qualify as an Enumerated Product ("property and casualty insurance") if a state-supervised insurer issues it and state law regulates it as insurance [est.; counsel Q7]. Either way, an unlicensed protocol fails the Provider Test.
- The adopting release (77 FR 48208, fn. 41): "if a person uses a weather derivative or catastrophe swap to assume all or part of the risks contained in a portfolio of property and casualty insurance policies, that weather derivative or catastrophe swap would be a Title VII instrument". Contracts labelled reinsurance but "executed as a swap" do not qualify. **So in route (ii) the pool must take risk as genuine reinsurance, not through a weather swap with the carrier.**
- NY OGC 00-02-05 confirms the state side: in NY a no-loss weather contract is not insurance. With CEA §12(h), our unlicensed contract is a swap in NY [est.].
- The CFTC's own position (NPRM, 91 FR 35806, 12 Jun 2026): exchange-traded event contracts are swaps within its exclusive jurisdiction. The NPRM names weather as a use case ("hedge exposure to ... weather, and climate conditions") and calls "contracts on the weather or agricultural production" markets that "have long been traded uncontroversially on CFTC-registered DCMs" (fetched).

**1.2 CEA §2(e) and the non-ECP problem.** [HIGH]
- Non-ECPs may enter swaps only on a DCM. A small business is an ECP only with >$10M assets, or >$1M net worth while hedging its business (§1a(18)(A)(v)). No other small-business or end-user carve-out exists. The trade-option exemption needs physical delivery [sister].
- ECP-only trading still has limits:
  - multi-party trading needs a SEF or DCM (§5h(a)(1));
  - the house's dealing counts toward the $8B de minimis;
  - OTC swaps carry Part 43/45 reporting [training; confirm].
- A single-dealer RFQ (house quotes, customer accepts) is generally not multi-to-multi, so not a SEF [est.; counsel Q4].

**1.3 Intermediary status, activity by activity.**
| Activity | Path | Likely characterization | Out / relief | Confidence |
|---|---|---|---|---|
| House hedges its own book in its own Kalshi account; the customer contract never mentions house positions; no customer money at Kalshi | (a) | Proprietary trading by a Kalshi member. Not FCM/IB for that leg. The problem is the policy (1.1–1.2) | — | MEDIUM [est.] |
| House buys the ladder "for" the customer, holds it as nominee or passes the payout through | (a) variant | Accepts orders and money for DCM trades = FCM (§1a(28)); breaches Kalshi Rule 5.17(f) ("transfer the benefit of any position ... other than through a transaction executed through the Platform") and 5.17(g)(1) ("No Person shall trade for a Person other than itself"); Developer Agreement §3.2 | Register as FCM/IB, or route through an FCM member | HIGH on the terms; MEDIUM on characterization |
| Outside capital (LPs or token) funds a pool that writes residual contracts and holds Kalshi hedges | pool | Commodity pool (§1a(10)); the operator is a CPO (§1a(11)) | 4.13(a)(3) needs 506(c)/144A plus a 5% or 100%-notional limit (a weather-writing pool likely fails); 4.7 for QEPs; Aug 2026 proposal (91 FR 54264) | MEDIUM |
| Portal prescribes ladder size from the business's own sales, for a fee or bundled with paid products | (b) | CTA (§1a(12)): advice "as to the value of or the advisability of trading in" swaps/event contracts | 4.14(a)(9) fails (tailored). 4.14(a)(10)/§4m(1): ≤15 persons and no general holding out, so a concierge pilot only. Otherwise register with NFA | MEDIUM |
| Portal sends orders to Kalshi or an FCM, or earns per-trade/referral fees | (b) | IB: the CFTC reads "soliciting or accepting orders" broadly; per-trade or referral pay makes you the FCM's "agent" (48 FR 35248, quoted in Letter 26-25) | Letter 26-25 PSP relief, but "express 'buy' or 'sell' signals" are excluded; needs a Kalshi/FCM contract and a joint-and-several undertaking | HIGH on letter text |
| Our own residual auction, open to many wallets, with collateral in our contracts | both | Unregistered SEF/DCM; possibly FCM (collateral) plus a missing customer-identification programme. This is the Opyn/Deridex fact pattern | DCM (route iii) or no multi-party swap trading | HIGH precedent |

**1.4 Kalshi terms that bind our design** (fetched). Rulebook v1.29 Rule 5.17(e)–(g); Member Agreement §V.E; Developer Agreement v1.1 §§3, 3.1, 3.2, 3.7, 6.4; Data Terms of Use (no use in pricing, settling or indexing instruments without consent). Partner channels do exist:
- FCM Members and IB Members (Rulebook definitions);
- market makers (Rules 4.1–4.5, designation on financial resources and experience);
- broker API partnerships: Apex (tastytrade first), Alpaca (via its FCM Alpaca Derivatives), DriveWealth (2026, search summaries) [unverified detail];
- Kalshi tokenized markets on Solana through DFlow (1 Dec 2025, solana.com). Every trading wallet must pass KYC with DFlow's provider Proof, and Kalshi announced $2M+ in builder grants [search summary].
- Our current keyless use (hl-mm book recorder, the paper, portal quotes) may fall under the Developer Agreement ("any user of Kalshi's API") and the data terms. That is a counsel and licence question (Q13), not a settled breach.

**1.5 CFTC event-contract rulemaking and the Kalshi litigation (2025–2026).** [HIGH for Federal Register and CFTC releases; MEDIUM for court items from secondary coverage]
- **Rulemaking:**
  - The 2024 "Event Contracts" NPRM was withdrawn (91 FR 5386, 6 Feb 2026).
  - ANPRM "Prediction Markets" (91 FR 12516, 16 Mar 2026; comments to 30 Apr). Q12 asks "How do event contracts compare to, or substitute for, insurance contracts?"
  - NPRM "Prediction Markets; Public Interest Determinations" (91 FR 35806, 12 Jun 2026; comments to 27 Jul; RIN 3038-AF65). It covers only the five enumerated activities; weather is untouched.
  - NPRM on data reporting for certain event contracts (91 FR 40102, 1 Jul 2026).
  - Joint SEC/CFTC request for comment on further defining "swap" (91 FR 37873, 24 Jun 2026).
  - NPRM "Conflicts and Affiliations", covering DCMs and affiliated trading firms (91 FR 50926, 6 Aug 2026; comments to 5 Oct).
  - CPO/CTA exemption proposal (91 FR 54264, 21 Aug 2026; comments to 5 Oct).
  - Chairman Michael Selig sworn in 22 Dec 2025 (CFTC PR 9164-25).
- **CFTC v. states:** the CFTC has sued AZ, CT, IL (2 Apr 2026), NY (24 Apr), WI, NM, MN (19 May), RI and KY (23 Jun), and filed amicus briefs in the 6th and 9th Circuits and the Massachusetts SJC (CFTC PR 9206-26, 9218-26, 9260-26, 9267-26).
- **Courts:**
  - 3rd Cir. (*KalshiEX v. Flaherty*) held NJ's sports-gambling rules preempted because the contracts are swaps. NJ petitioned for certiorari on 2 Sep 2026; docketed 8 Sep; Kalshi's response due 8 Oct [search summaries; No. 26-299 per sister].
  - 9th Cir. (28 Aug 2026, Nevada) held Kalshi unlikely to show preemption for sports contracts, and remanded the election-contract question (Holland & Knight, fetched).
  - SDNY (Judge Torres, 7 Jul 2026, 1:25-cv-08846) denied Kalshi a preliminary injunction against the NY Gaming Commission; Kalshi appealed [search summary].
  - NY AG v. KalshiEX (filed 31 Jul 2026, seeking a TRO on event contracts and >$36B) was removed to SDNY the same day (1:26-cv-06550, Judge Broderick). NY's remand motion was fully briefed by 28 Aug, with no TRO on the docket as of then (CourtListener, fetched).
  - A Michigan court ordered trade cancellations (TRO 29 Jun 2026); the CFTC stayed Kalshi's emergency rule on 14 Jul (PR 9267-26) and issued a market-emergency order on 11 Aug (PR 9281-26).
  - NY AG sued QCX d/b/a Polymarket US on 24 Sep 2026 (NY AG release, fetched).
- **What it means for us:** none of these cases targets weather. But NY's theory ("outcomes ... uncertain and outside the control of the bettor") is not limited to sports, and NY asked to halt all Kalshi event contracts [est.].

### Q2. Insurance

**2.1 When a parametric weather payout is insurance.** [MEDIUM]
- **NY:** §1101(a) needs a "material interest which will be adversely affected" by the event. OGC 00-02-05 (2000): weather derivatives are not insurance because payment does not depend on loss. §1113(a)(34), enacted by ch. 569 of 2024 and effective in early 2025 (about 30 days after signing, per secondary coverage [unverified exact date]), creates a licensed parametric line for weather-related events measured and reported by a state or federal agency, with an applicant disclosure that it is not a substitute for property or flood cover (nysenate.gov bill page, fetched). Open points for counsel:
  - Is a daily temperature or rainfall index at a shopfront a "weather-related event"? The statute's examples are windstorm, flood, snow, wildfire, tornado, cyclone and earthquake.
  - Does the data source fit? NOAA nClimGrid and ASOS are federal. PRISM is produced by Oregon State University [est.: public university; unclear].
- **Insurable interest:** the CFTC Product Test needs insurable interest held for the whole term, plus proven loss. NY §3401 needs insurable interest for property insurance [training]. The portal's sales upload is itself evidence of insurable interest. A payout cap at documented revenue exposure moves the design toward the Product Test [est.].
- **NAIC:** the NAIC weather-derivatives white paper named in the brief was **not located** in this pass. One search found nothing on point, and then the search budget ran out. The 2012 product-definitions release records NAIC's comment letter. NCOIL's P&C committee took a parametric briefing on 18 Apr 2026, and no model act was found (NCOIL minutes, search summary).
- **IL, FL, NJ:** not researched (open question).

**2.2 Who may sell it.** [MEDIUM]
- An admitted carrier with approved forms and rates for the line.
- A licensed producer or MGA/program administrator binding under a written carrier agreement. The NAIC MGA model act has been widely adopted [training].
- Surplus lines, through a licensed surplus-lines broker after a diligent search. The NRRA "exempt commercial purchaser" shortcut needs a qualified risk manager, >$100,000 in prior-year commercial P&C premium, and >$20M net worth or >$50M revenue (Insurance Journal/NAIC, search summary). Small businesses won't qualify, so the diligent search applies.
- Behind the carrier sits reinsurance. Unrated or unlicensed reinsurers generally post 100% collateral (Mayer Brown, search summary), and fronting carriers keep about 10–20% of gross written premium (Insurance Business, search summary).

**2.3 How the parametric peers are built.** [MEDIUM]
| Firm | Structure | Location basis | Lesson for us |
|---|---|---|---|
| **Arbol** | Arbol Inc.; Arbol Insurance Services has been a Lloyd's coverholder since May 2023, plus a London MGA; sells weather **derivatives** (energy, agriculture, travel) alongside **insurance** and reinsurance; lined up $250M of non-traditional capacity; spun out the dClimate data network (Artemis; arbol.io, fetched) | Custom index per client | Keep regulated risk contracts apart from any data/network token. Who may face Arbol's derivatives (ECP-only?) is [unverified] |
| **FloodFlash** | FloodFlash Ltd, FCA-authorised (FRN 784452), Lloyd's coverholder since launch, reinsurance-backed (floodflash.co, fetched) | Sensor at the insured site | Location parametric via an MGA; UK-focused (US presence unverified) |
| **Descartes** | US "Flood-at-Location" (25 Jun 2025): surplus lines in all 50 states, limits up to $70M; min premium "usually" $50,000; $250M+ GWP in 2025 (descartesunderwriting.com, fetched) | On-site sensors | A $50k minimum is orders of magnitude above our ticket size. Wrong model for SMB daily covers |
| **Raincoat** | Puerto Rico; builds products for insurers, reinsurers and governments; hurricane microinsurance distributed by Popular Insurance, underwritten by Óptima Seguros (newsismybusiness, search summary) | Hurricane/quake index | Distribution partner + local insurer + our tech is the micro-cover model |
| **Sola** (added) | Admitted parametric tornado cover: about $88/yr premium [secondary], limits to $15k, 15 states, NWS EF-scale trigger. Sola is the MGA; Artemis (31 Aug 2023, fetched) names Spinnaker as issuing carrier and Beazley as capacity, while a search summary of Beazley's page says Beazley Insurance Company provides the admitted cover. Check which entity issues in which state | NWS-defined tornado path | **Closest template for route (ii):** admitted, standard form, micro-premium, government-agency trigger |

### Q3. DeFi precedents: see the **Precedents** section (US persons, geo-blocking, tokens).

### Q4. Token

- **SEC, 2025–2026** [HIGH on text]
  - Interpretation, 91 FR 13714 (23 Mar 2026; SEC PR 17 Mar; CFTC joined). Five categories: digital commodities, collectibles, tools, stablecoins, digital securities.
  - A digital commodity "does not have intrinsic economic properties or rights, such as generating a passive yield or conveying rights to future income, profits, or assets of a business enterprise". A junior token that receives premium and absorbs underwriting losses carries exactly those rights, which points to "digital security" or investment contract [est.].
  - The interpretation accepts governance rights as consistent with a digital commodity when they concern a functional crypto system (software upgrades, treasury). It does not extend that comfort to rights over a business's income.
  - The protocol-staking comfort covers only staking digital commodities in proof-of-stake consensus (solo, delegated, custodial, liquid). Staking as first-loss capital for an insurance book is outside it [est.].
- **Regulation Crypto Assets** (proposed 91 FR 54510, 21 Aug 2026; comments to 20 Oct 2026) [HIGH on text; fit est.]
  - Offering exemptions: $5M per four years and $75M per 12 months.
  - Proposed Rule 400: a safe harbour for when an investment contract "has ceased to exist".
  - It is built around investment contracts sold with non-security crypto assets. A token that is itself a claim on pool income probably stays a security [est.].
- **Precedents**
  - BarnBridge (SEC, 22 Dec 2023, Rel. 33-11262): the "SMART Yield" tranche products were unregistered securities and the pools unregistered investment companies. $1,457,000 disgorgement plus $125,000 per founder; products shut down (SEC order; search summaries). This is the controlling analogue for a junior/senior tranche token [est.].
  - Ooki DAO (CFTC, 9 Jun 2023): a DAO is a "person"; token-holder governance is not a shield.
- **CFTC side:** pool/CPO (Q1.3). The CPO/CTA proposal (21 Aug 2026) would add an exemption for SEC-registered advisers running sophisticated-investor pools, and would raise the small-pool threshold for inflation.
- **Statute** [HIGH on the vote; MEDIUM on outlook]
  - CLARITY Act (H.R. 3633) passed the House on 17 Jul 2025 (294–134, Latham tracker, fetched).
  - Senate cloture on the motion to proceed failed on 15 Sep 2026: 49–50 in most reports, and one summary inverted the order. Either way, 60 were needed. It stays on the calendar (Calendar No. 423), no new date is set, and coverage calls 2026 passage unlikely.
  - GENIUS Act (stablecoins) signed 18 Jul 2025. It matters for which stablecoin the senior tranche holds.
- **Safe-harbour proposals:** proposed Rule 400 (above). The earlier Peirce token safe-harbour drafts were never adopted [training]. BRCA (S.3611) is not law [sister]. The CFTC sent "Regulation Crypto Asset Transactions/Markets" to OIRA on 17 Sep 2026 [sister].

## Architecture Patterns (how the memo should reason)

### Recommended memo structure (for plan 15-02)
1. One page of facts: both hedge-leg paths, the residual, the auction, the pool, the token, testnet only. No conclusions.
2. The fork: swap or insurance.
3. Path (a) house hedge vs path (b) overlay: who is an intermediary.
4. Open residual auctions and retail wallets.
5. Pool and token (CFTC pool/CPO; SEC security).
6. Venue dependence: Kalshi terms, the data licence, state litigation.
7. The three routes table and gates before mainnet.
8. Questions for counsel.
9. Appendix: primary sources with dates.
If the memo goes out in the owner's name, apply the owner writing-style guide (AGENTS.md): plain words, honest about what is unproven.

### Pattern 1: The fork decides the regulator
**What:** An unlicensed issuer means a swap (CFTC). A state-supervised insurer with a filed policy means insurance (the state). CEA §12(h) closes the gap.
**When to use:** First section of the memo; every later answer depends on it.

### Pattern 2: The house hedge is proprietary risk management, never a pass-through
**What:** Path (a) customer contracts must not reference, transfer or depend on house Kalshi positions (Rule 5.17(f), (g)(1); FCM definition). The house hedges its own net book.
**When to use:** Engine and portal copy ("hedged on a CFTC-regulated exchange" is itself a counsel question, Q2).

### Pattern 3: The overlay path turns the portal into an adviser and introducer
**What:** Tailored sizing = CTA question. Order routing or per-trade pay = IB question. Letter 26-25 helps with IB only, and only without express buy/sell signals.
**When to use:** Path (b) design; shapes what the portal is allowed to display.

### Pattern 4: Many wallets trading swaps = a swap trading facility
**What:** Under CEA §5h(a)(1) and §2(e), retail trading is lawful for US persons only on a DCM. Offshore plus IP blocking was "not sufficient" (Opyn, 7 Sep 2023).
**When to use:** The auction section; the answer is route (iii) or no US persons.

### Pattern 5: A first-loss pool token is two regulated things
**What:** A commodity-pool interest (CPO) and a security (digital security, investment contract; BarnBridge). In route (ii) it becomes an interest in a reinsurance vehicle: still a security, but no CPO question if the vehicle writes reinsurance rather than swaps [est.].

### Anti-patterns to avoid
- **"Testnet or decentralised, so not ours":** bZeroX founders were charged personally (22 Sep 2022); Ooki DAO was held a "person" (9 Jun 2023).
- **Treating an IP geo-block as the compliance plan:** the Opyn order.
- **Calling the product "insurance" (or "not insurance") in the UI:** labels don't decide it (anti-evasion; the OGC caveat), and selling "insurance" without a licence is a state-law problem.
- **Pricing the product off Kalshi books without a licence:** the Kalshi Data Terms.
- **Tying payouts to house Kalshi fills:** Rule 5.17(f).
- **Token-holder votes as the legal decision-maker for risk parameters:** Ooki DAO.

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---|---|---|---|
| "Insurance or swap?" | Our own label or disclaimer | Counsel's analysis under 17 CFR 1.3 para (4); a licensed carrier if we want "insurance" | Anti-evasion para (6); NY OGC 00-02-05 caveat |
| Excluding US persons | IP geo-block + ToS checkbox | KYC at a registered venue, carrier onboarding, or not serving the US | Opyn 2023 |
| Retail access to swaps | Our own open auction | A DCM listing (partner) | CEA §2(e), §5h(a)(1) |
| Routing customer orders to Kalshi | Our own API bridge trading for customers | Kalshi FCM/IB members, broker APIs, or a Letter 26-25 front end with a Kalshi contract | Developer Agreement §3.2; Rule 5.17(g)(1) |
| Kalshi data in the product | Silent use of the keyless API or recorder | A written Kalshi data licence | Data Terms; Developer Agreement §3.1 |
| Public pool capital | Open vault + junior token | A reinsurance vehicle (route ii) or an MM fund with a CPO answer (route iii), sold under a securities exemption | §1a(11); 91 FR 13714; BarnBridge |
| Governance over risk parameters | DAO voting as the legal decision-maker | A legal entity with accountable officers; token votes advisory at most | Ooki DAO |
| Settlement data | Business-owned gauges; PRISM without written terms | NOAA data (US-government work; a federal agency, which fits NY §1113(a)(34) wording) with a stated revision policy | Moral hazard. PRISM's current web terms say data "may be freely reproduced and distributed", but the older PDF still online says "Sale or other commercial use of the data must be arranged" (both fetched) |
| Hedge-size advice | A personalised "buy N contracts" engine for the public, unregistered | CTA registration; non-tailored calculators (4.14(a)(9)); or a ≤15-client pilot (4.14(a)(10)) | §1a(12) |

**Key insight:** every shortcut here already has an enforcement precedent: Polymarket 2022, bZeroX/Ooki 2022–23, Opyn/0x/Deridex 2023, BarnBridge 2023. The cheap path is to borrow a licence (carrier, DCM, FCM), not to argue around one.

## Common Pitfalls

### Pitfall 1: Asking counsel about the hedge instead of the policy
**What goes wrong:** Counsel is asked "is the house an FCM when it hedges on Kalshi?", answers no (proprietary account), and nobody asks whether the policy is an illegal off-exchange swap.
**Why it happens:** The regulated venue is the visible part.
**How to avoid:** Put the fork first. Q1 before Q2.
**Warning signs:** Drafts that call the policy "insurance-like" without naming whose licence it is issued under.

### Pitfall 2: Assuming "small business" means non-ECP, or the reverse
**What goes wrong:** Every business is shut out of OTC, or every business is assumed eligible.
**Why:** Entity ECP = >$10M assets, or >$1M net worth plus business hedging.
**How to avoid:** Capture an ECP attestation in onboarding. Ask whether a bilateral, single-dealer ECP channel can run while the retail path waits (Q3).

### Pitfall 3: Geo-blocking your own customers
**What goes wrong:** Route (i) blocks US persons, but every target business is in NYC, Newark/Trenton, Chicago or Miami, because the ladders settle at US stations.
**How to avoid:** Route (i) can host only non-US traders and LPs. The US product still needs route (ii) or (iii).

### Pitfall 4: A single venue that is under state attack
**What goes wrong:** The station leg lives on Kalshi. NY sued Kalshi (31 Jul 2026) and Polymarket US (24 Sep 2026); Michigan ordered trade cancellations (June–July 2026).
**How to avoid:** Treat venue continuity as a gate. The engine should support a second DCM: ForecastEx lists "climate" contracts (forecastex.com, fetched), and CME weather futures exist [unverified this pass: CME blocked automated access]. In route (ii), claims get paid whether or not the hedge venue is up.

### Pitfall 5: Data licences as an afterthought
**What goes wrong:** Quotes, sizing and dashboards are built on Kalshi books, and the data terms bar that use without consent.
**How to avoid:** The owner requests a Kalshi data licence before any commercial use (agents contact no one). Keep the paper framed as research. Q13.

### Pitfall 6: Marketing first-loss as "yield"
**What goes wrong:** "Stake to earn premium yield" is the Howey fact pattern, and the March 2026 staking comfort covers consensus staking only.
**How to avoid:** Decks describe the token as "junior capital in a regulated pool, offered only to eligible investors under an exemption" until counsel says otherwise. This affects Phase 14 and Phase 16 wording.

### Pitfall 7: A testnet that quietly has value
**What goes wrong:** Points, airdrop hints or "early LP" allocations tied to testnet use create an expectation of value.
**How to avoid:** No points, allocations or promises until counsel answers (Q14).

## Precedents (replaces Code Examples)

### Enforcement and orders
| Precedent | Date / source | What happened | Lesson |
|---|---|---|---|
| Polymarket (Blockratize) | 3 Jan 2022, CFTC PR 8478-22 (fetched) | $1.4M penalty. Event markets "constitute swaps" and "can only be offered on a registered exchange"; unregistered DCM/SEF; wind-down ordered | An open on-chain event market = an unregistered DCM/SEF |
| bZeroX / Ooki DAO | 22 Sep 2022, PR 8590-22; 9 Jun 2023, PR 8715-23 (fetched) | Founders fined $250k. The DAO was held a "person"; default judgment of $643,542; website takedown | DAO form doesn't shield; token voters exposed |
| Opyn / ZeroEx / Deridex | 7 Sep 2023, PR 8774-23 (fetched) | Failing to register as SEF/DCM and FCM; no customer-identification programme. "Blocking users with U.S. internet protocol addresses ... [was] not sufficient". $250k / $200k / $100k | Geo-block insufficient; US-based developers charged |
| BarnBridge DAO | 22 Dec 2023, SEC Rel. 33-11262 (SEC order; search summaries) | Tranche "SMART Yield" = securities; pools = unregistered investment companies; about $1.7M total; ceased | Tranche tokens |
| OKX | 24 Feb 2025, DOJ [sister] | Guilty plea, about $504M; had a no-US policy but courted US clients | Offshore + policy ≠ protection |

### Structures (US persons, geo-blocking, tokens)
| Project | Structure | US persons | Token | Source (date) |
|---|---|---|---|---|
| **Polymarket US** | Bought DCM+DCO QCEX for $112M (Jul 2025) → QCX; swap-data no-action 3 Sep 2025; amended order of designation 25 Nov 2025 allowing intermediated access through FCMs; US app from Dec 2025 (sports first). NY AG sued it on 24 Sep 2026 | Onshore app for US users; the offshore site has blocked US users since the 2022 settlement [training] | None in the regulated product | CFTC PR 9113-25 (fetched); NY AG (fetched); Coindesk/PYMNTS (search) |
| **Kalshi partners** | FCM/IB members; market-maker programme; broker APIs (Apex, Alpaca, DriveWealth); DFlow tokenized Kalshi positions as SPL tokens on Solana (1 Dec 2025) | US members; KYC on every DFlow wallet via Proof; LIP excludes non-US users | No Kalshi token; position tokens are wrappers | Kalshi Rulebook; solana.com (fetched); search summaries |
| **Etherisc** | Software (the GIF framework). Kenya crop cover with ACRE Africa (a licensed intermediary) and insurers; Lemonade Crypto Climate Coalition (a DAO, Mar 2022; members incl. Hannover Re, Pula); farmers pay under $1 | Not a US retail product | DIP token [training], separate from the risk carriers | Etherisc blog; BusinessWire 28 Mar 2023 (search) |
| **Nayms** | Nayms SAC Ltd (Bermuda). Two years in the BMA sandbox (DABA Class M + IGB) → full DABA Class F + IIGB (May 2022); a segregated-accounts marketplace for insurers, brokers and capital | Participant limits [unverified] | — | Crowdfund Insider / Royal Gazette, May 2022 (search) |
| **Ensuro** | "Licensed to conduct digital asset business and general (re)insurance business by the Bermuda Monetary Authority". Junior/senior **eTokens** in USDC; partners' products plug in as "risk modules" | **United States on its restricted list**; KYC/AML required; retail investors only in some jurisdictions, with caps | eTokens = the LP tranche | ensuro.co; docs.ensuro.co terms (fetched) |
| **Arbol / dClimate** | Regulated MGA/coverholder plus derivatives desk; dClimate spun out as a separate data network | Not verified | dClimate token separate from the risk contracts | Artemis; arbol.io (search/fetch) |
| **Nexus Mutual** | Began as Nexus Mutual Limited, a UK company limited by guarantee (discretionary mutual). Now a "stateless DAO without ultimate legal personality" under a BVI-law Member Agreement (document dated 24 Feb 2022); the UK company is dormant (accounts to 31 Aug 2024) | KYC membership; the restricted list (Japan, India, Mexico, China and others) does **not** include the US | NXM, a membership token | docs.nexusmutual.io; member agreement PDF (fetched); Companies House (search) |

**Reading across them [est.]:**
- Every live project that pays claims on real-world risk puts a licensed insurer, reinsurer or DCM in the chain (Etherisc, Nayms, Ensuro, Arbol, Sola, Polymarket US).
- Pure-DAO designs (Nexus) avoid "insurance" by making claims discretionary. That can't be combined with a parametric promise to pay.
- The on-chain junior/senior analogue closest to ours (Ensuro) excludes US persons from the capital side.

## Routes Comparison

| | (i) Offshore entity + US geo-block; US affiliate trades the Kalshi leg | (ii) Parametric-insurance wrapper: carrier issues; protocol = risk engine, pool, matching | (iii) DCM listing of regional/grid contracts; we are the LIP market maker |
|---|---|---|---|
| Who sells to the US business | No one offshore (US blocked). The US affiliate can only trade its own book or give advice (CTA question) | The carrier (admitted, or surplus lines via a broker). We act as MGA/program administrator | The DCM. The business is a direct member or an FCM customer; we quote as MM; the portal is a passive front end |
| What the residual legally is | A swap, sold to non-US persons | Insurance (filed P&C/parametric; Provider Test met), not a swap | An exchange-traded swap/event contract; lawful for non-ECPs |
| Open auction with retail wallets | Non-US wallets only; needs more than IP blocking; the US founder is still exposed (CEA §2(i)) | Not on the policy (Product Test: not traded separately). Netting becomes internal portfolio management; any auction moves to the reinsurance layer among eligible investors | Yes, on the DCM. Our on-chain auction is replaced by the DCM book or its auctions; on-chain access only via KYC'd wrappers (DFlow pattern) |
| Token | Offshore junior token; securities and CPO law still reach US-person promoters | An interest in a reinsurance/ILS vehicle = security; eligible investors (Reg D/Reg S; 144A for ILS) | No natural pool role. MM capital is our own or a fund (CPO + securities) |
| **What must be true before mainnet** | Real US-person exclusion (KYC; no US marketing; offshore ops not run by US persons); counsel's opinion on CEA §2(i); an offshore licence where the activity is regulated there; a separate US customer product (route ii or iii); the owner accepts founder exposure and revisits his sister-project stance ("do not go offshore") | Fronting carrier signed; forms filed or approved in each launch state (NY §1113(a)(34) disclosure); producer/MGA licences; reinsurance vehicle licensed and 100% collateralised; insurable-interest check and payout cap in the product; NOAA settlement source; Kalshi data licence if pricing uses Kalshi | A DCM agrees to self-certify the contracts (40.2) with a NOAA settlement source and revision policy; MM agreement signed (Rule 4.1(d)); portal meets Letter 26-25 or we register as CTA; businesses onboard at the DCM/FCM; data licence; conflicts rules for MM + portal (91 FR 50926) |
| **Biggest open question** | Who is the customer if US businesses are blocked? | Will a carrier front $30–$120/day micro-covers with an on-chain reinsurer, and does NY's parametric line cover a daily temperature/rain index? | Will a DCM list thin location or regional-factor contracts and pay incentives on them? |
| Rough time (comparables) | Entity setup: weeks to months [unsourced]. A Bermuda digital-asset + insurance licence: Nayms spent about 2 years in the BMA sandbox (→ May 2022) | Sola launched admitted in 15 states (Aug 2023; setup time not disclosed). Estimate 6–12 months to the first state with a fronting partner [est., LOW] | Once a DCM agrees, 40.2 allows listing the business day after filing [training]; the deal itself is unknown. CTA registration: est. 1–3 months [LOW]. Own DCM: the 180-day clock starts only when the application is "materially complete"; "multi-month to multi-year" (Katten, 20 Nov 2025); 12–24+ months [sister] |
| Rough cost (comparables) | Setup not sourced; get a counsel quote. Downside comparables: Opyn $250k; Polymarket $1.4M; OKX about $504M | Fronting carriers keep about 10–20% of GWP; unrated reinsurer posts 100% collateral against limits; producer licences minor. Bermuda vehicle: own licence (Nayms path) or rent a cell in an existing segregated-accounts company [est.] | Partner route: mostly MM capital + integration. Own DCM: financial resources >12 months of operating expenses (Katten), commonly quoted as $5M+ [sister, secondary]. Buying one: $112M (Polymarket/QCEX, Jul 2025) |
| Verdict for the memo [est.] | Weakest for this product | Best fit for the last-mile residual | Best fit for station + regional legs; pairs with (ii) |

## Gates Before Mainnet (cross-route checklist for 15-02 and Phase 17)
1. Counsel's written answer to the fork (Q1) and the auction question (Q4).
2. A route chosen by the owner; its licence or partner signed (carrier, DCM, FCM).
3. Kalshi (or other DCM) data licence, or a product whose quotes use no Kalshi data (Q13).
4. No retail wallet can face our contract outside a DCM: the auction is ECP/KYC-gated, single-dealer, or replaced.
5. No token sale or distribution to the public until the securities and CPO answers (Q9, Q10); the testnet has no points (Q14).
6. Oracle on NOAA data with the stated revision policy; PRISM commercial terms confirmed in writing if used.
7. A venue-continuity plan for Kalshi's state litigation.
8. An entity with accountable officers. Governance votes are not the legal decision-maker.
9. An owner ruling on offshore posture: this project has none; the sister project said "do not go offshore".
10. Where possible, one counsel engagement shared with defi-options, whose open CPO and US-person venue questions overlap [sister project PROJECT.md].

## Questions for Counsel

1. **The fork.** Is a cash payout of $X per °F above a strike (or per inch of rain) on NOAA-reported data at a named location a "swap" under CEA §1a(47)(A)(ii)/(iii), when sold by an unlicensed company to a business with no proof-of-loss condition? Would adding an insurable-interest attestation, a payout cap at documented revenue exposure and a loss affidavit change that when the provider is not a state-supervised insurer? Or is failing the Provider Test decisive?
2. **Path (a) house hedge.** The house sells its own contract and separately hedges in its own Kalshi account: no reference to its positions, no customer funds at Kalshi. Is it acting as an FCM, IB or CPO for the Kalshi leg? Does customer-facing wording such as "hedged on a CFTC-regulated exchange" raise Kalshi Rule 5.17(f)/(g)(1) or FCM issues?
3. **An ECP-only channel.** Can we offer the residual contract bilaterally to businesses that certify ECP status under §1a(18)(A)(v)(III), with the house as sole counterparty? What swap-dealer (de minimis), Part 43/45 reporting and documentation duties apply at our size? Is a CFTC no-action request (Reg 140.99) or a §4(c) exemption realistic for an off-exchange weather hedge offered to non-ECP businesses?
4. **The auction.** Is a uniform-price batch auction on HyperEVM, where many wallets post bids and offers on residual contracts, a "facility for the trading or processing of swaps" (§5h(a)(1)) even if limited to ECPs? Does a single-dealer RFQ to the house avoid SEF/DCM status?
5. **Overlay advice.** In path (b), is sizing a ladder from a business's own sales "commodity trading advice" (§1a(12))? Can a ≤15-business concierge pilot rely on 4.14(a)(10)/§4m(1), and does a public website count as "holding out"? Is CTA registration needed for self-serve?
6. **Front-end relief.** Can the portal qualify as a Passive Software Provider under Letter 26-25 (17 Sep 2026) if it shows an elasticity estimate and a suggested cover, but the user places each order at Kalshi or an FCM? Where is the line between information and an "express 'buy' or 'sell' signal"?
7. **The insurance route.** Under NY Ins. Law §1113(a)(34), is a daily temperature or rainfall index at a business location a "weather-related event"? Does NOAA gridded data count as "measured and reported by a state or federal government agency" (and PRISM, from Oregon State University)? Is such a policy "property and casualty insurance" for the Enumerated Products prong of 17 CFR 1.3 para (4)? What is the treatment in IL, FL and NJ?
8. **Our role in route (ii).** Can we act as MGA or program administrator (pricing engine; binding within carrier guidelines) with producer licences, while a separate vehicle provides reinsurance collateralised on-chain? Does that reinsurance meet the reinsurance prong of the Provider Test (para (4)(i)(B)(3)) if the vehicle is in Bermuda? What collateral would the fronting carrier need?
9. **Pool and CPO.** If token holders fund a pool that writes residual contracts and holds Kalshi hedges, is it a commodity pool, and are we its CPO? Do 4.13(a)(3), 4.7 or the Aug 2026 proposal (91 FR 54264) help? If the pool is instead a reinsurance vehicle, does the CPO question go away?
10. **The token.** Is a transferable junior-tranche token that receives premium and takes first loss a security under *Howey* and the 23 Mar 2026 interpretation? Which exemption fits the pre-seed raise and a later LP distribution: Reg D 506(b)/(c), Reg S, or proposed Reg Crypto Assets? Is BarnBridge (Dec 2023) the controlling precedent, including the Investment Company Act point? Does token voting on risk parameters create Ooki-style liability?
11. **The offshore route.** For a US-person founder, does an offshore opco running the auction and pool for non-US persons, with a US affiliate trading Kalshi proprietary, have a "direct and significant connection" with US commerce (§2(i))? What controls beyond IP blocking have regulators accepted? Which offshore jurisdiction would license this activity itself?
12. **The DCM route.** What does a partner DCM need from us to self-certify regional/grid weather contracts under 40.2 (settlement source, revision policy, data rights, manipulation analysis)? As its designated market maker who also runs the portal that suggests those contracts, what conflict rules apply (Rule 4.4; 91 FR 50926)?
13. **Kalshi terms.** Does our keyless use of Kalshi's public endpoints (book recorder, research paper, portal quotes) bind us to Developer Agreement v1.1 and the Data Terms? Does any of it breach §3.1 or the ban on pricing or indexing with Kalshi Data? What licence should the owner request? Does §6.4 limit naming Kalshi in investor decks?
14. **Testnet.** Is a public HyperEVM testnet with mock USDC, open wallets and no points or airdrops free of CEA and securities exposure? What must we avoid saying or promising during the pre-seed raise while it runs?
15. **State exposure.** Given NY AG v. KalshiEX (31 Jul 2026, removed, remand pending), NY AG v. Polymarket US (24 Sep 2026) and the circuit split (3rd Cir. for Kalshi; 9th Cir., 28 Aug 2026, against), could a state treat a weather event contract bought by a local business as gambling or insurance despite CEA §12(h)? Does that change which DCM we should use for the station leg?

## State of the Art (dated timeline)

| Date | Event | Source | Impact on us |
|---|---|---|---|
| 15 Feb 2000 | NY OGC: weather derivatives not insurance | OGC Op. 00-02-05 | Unlicensed = swap in NY |
| 13 Aug 2012 | CFTC/SEC product definitions; insurance safe harbour | 77 FR 48208 | The fork |
| 3 Jan 2022 | Polymarket order, $1.4M | CFTC PR 8478-22 | Open event-market precedent |
| 22 Sep 2022 / 9 Jun 2023 | bZeroX; Ooki DAO a "person" | PR 8590-22, 8715-23 | DAO ≠ shield |
| 7 Sep 2023 | Opyn/0x/Deridex; IP blocking "not sufficient" | PR 8774-23 | Geo-block route |
| 22 Dec 2023 | BarnBridge tranche tokens | SEC Rel. 33-11262 | Tranche = security |
| 13 Dec 2024 (eff. ~Jan 2025) | NY parametric insurance line | A10344, ch. 569 | Route (ii) in NY |
| 17 Jul 2025 | CLARITY passes House, 294–134; GENIUS signed 18 Jul | Latham tracker | — |
| Jul / 3 Sep / 25 Nov / Dec 2025 | Polymarket buys QCEX ($112M); QCX no-action; amended order (FCM access); US app | CFTC PR 9113-25; search | Onshore path costs a DCM |
| 1 Dec 2025 | DFlow tokenizes Kalshi markets on Solana (KYC per wallet) | solana.com | On-chain access to DCM contracts |
| 22 Dec 2025 | Selig sworn in as CFTC Chairman | PR 9164-25 | Pro-DCM, pro-preemption CFTC |
| 6 Feb 2026 | 2024 event-contract NPRM withdrawn | 91 FR 5386 | — |
| 25 Feb 2026 | CFTC prediction-markets enforcement advisory | PR 9185-26 | 180.1 applies on DCMs |
| 16 Mar 2026 | ANPRM "Prediction Markets" (asks about insurance substitutes) | 91 FR 12516 | Comment record |
| 17 / 23 Mar 2026 | SEC crypto interpretation (five categories), CFTC joined | 91 FR 13714 | Token classification |
| 17 Mar 2026 | Letter 26-09 (Phantom) | cited in Letter 26-25 | Front-end relief begins |
| 2 Apr – 23 Jun 2026 | CFTC sues 9 states | PR 9206-26, 9218-26, 9260-26 | Preemption campaign |
| 12 Jun 2026 | NPRM on public-interest determinations (enumerated activities only; weather "uncontroversial") | 91 FR 35806 | Weather listings safe |
| 24 Jun 2026 | Joint SEC/CFTC request for comment on the "swap" definition | 91 FR 37873 | Future line-drawing |
| 29 Jun / 14 Jul 2026 | Michigan TRO; CFTC stays Kalshi's cancellation rule | Michigan AG; PR 9267-26 | Venue risk |
| 7 Jul 2026 | SDNY denies Kalshi PI vs NY Gaming Commission | 1:25-cv-08846 (search) | Venue risk in NY |
| 31 Jul / 11 Aug 2026 | NY AG sues Kalshi (removed to SDNY); CFTC emergency order | NY AG; CourtListener; PR 9281-26 | Venue risk |
| 6 Aug / 21 Aug 2026 | Conflicts & Affiliations NPRM; CPO/CTA exemption NPRM; SEC Reg Crypto Assets | 91 FR 50926; 91 FR 54264; 91 FR 54510 | MM conflicts; pool; token |
| 28 Aug 2026 | 9th Cir.: Kalshi unlikely to show preemption for sports (Nevada) | Holland & Knight | Split |
| 2 / 8 Sep 2026 | NJ cert petition, *Flaherty v. KalshiEX*; response due 8 Oct | NJ OAG; search | SCOTUS may take preemption |
| 15 Sep 2026 | CLARITY cloture fails (49–50; 60 needed) | CNBC; Fintech Weekly; Latham | No token statute in 2026 |
| 17 Sep 2026 | Letter 26-25 passive-software relief | PR 9300-26; letter (fetched) | Portal as front end |
| 24 Sep 2026 | NY AG sues Polymarket US | NY AG | Venue risk extends past Kalshi |

**Deprecated / outdated:**
- The 2024 CFTC event-contract proposal is withdrawn (Feb 2026). Don't cite it as pending.
- Nexus Mutual's "UK mutual" framing is out of date: it now runs as a BVI-law stateless DAO, and the UK company is dormant.
- PRISM's "non-commercial only" PDF terms appear superseded by the current web terms. Confirm with PRISM before relying on either.

## Open Questions

1. **NAIC weather-derivatives white paper.** Not located (search budget exhausted). Pull it if it exists; it is often cited as an early-2000s paper on temperature instruments [unverified].
2. **IL, FL and NJ insurance treatment** of index weather contracts and parametric policies. Not researched. Needed for launch-state choice.
3. **3rd Cir. *Flaherty* decision date and exact holding.** Only secondary summaries. The cert docket number (26-299) comes from sister notes.
4. **Kalshi's appetite.** Would Kalshi license data, list regional contracts or sign us as MM for weather? Unknown. Only the owner can ask (agents contact no one).
5. **Kalshi entity accounts for small businesses (path b).** The Member Agreement contemplates entities ("if You are not a natural person"); the onboarding friction for a café is unverified.
6. **CME weather futures today.** Not verified; CME blocks automated access, so don't retry by script.
7. **HyperEVM / Hyperliquid front-end terms on US persons.** Not checked. Our contracts are ours regardless.
8. **Arbol's derivatives counterparties** (ECP-only?) and **Nayms participant limits.** Unverified.
9. **NY AG TRO against Kalshi.** None on the federal docket as of 28 Aug 2026; the remand motion is pending. Re-check before the memo ships.
10. **PRISM commercial-use terms.** The web page and the PDF conflict.

## Sources

### Primary (HIGH) — fetched 2026-09-30 unless noted
- 7 U.S.C. 1a (§1a(10), (11), (12), (18), (28), (31), (47), (49), (50), (51)); 7 U.S.C. 2(e), 2(i); 7 U.S.C. 7a-2(c)(5)(C); 7 U.S.C. 7b-3(a)(1); 7 U.S.C. 16(h) — https://uscode.house.gov (title 7) and https://www.law.cornell.edu/uscode/text/7/16
- 17 CFR 1.3 ("Swap" para (4), (6); "Swap dealer" (4)(i)(A)); 17 CFR 4.13(a)(3); 17 CFR 4.14(a)(8)–(10) — eCFR API, version 2026-09-01
- 77 FR 48208 (13 Aug 2012), product definitions — https://www.federalregister.gov/documents/2012/08/13/2012-18003
- Federal Register (CFTC): 91 FR 5386 (6 Feb 2026); 91 FR 12516 (16 Mar 2026); 91 FR 35806 (12 Jun 2026, https://www.federalregister.gov/documents/2026/06/12/2026-11854/prediction-markets-public-interest-determinations); 91 FR 37873 (24 Jun 2026); 91 FR 40102 (1 Jul 2026); 91 FR 50926 (6 Aug 2026); 91 FR 54264 (21 Aug 2026)
- Federal Register (SEC): 91 FR 13714 (23 Mar 2026, crypto interpretation); 91 FR 54510 (21 Aug 2026, Regulation Crypto Assets)
- CFTC press releases: 8478-22, 8590-22, 8715-23, 8774-23, 9113-25, 9164-25, 9185-26, 9206-26, 9218-26, 9260-26, 9267-26, 9281-26, 9300-26, 9303-26 — https://www.cftc.gov/PressRoom/PressReleases/<number>
- CFTC Staff Letter 26-25 (17 Sep 2026) — https://www.cftc.gov/csl/26-25/download
- Kalshi: Member Agreement — https://kalshi-public-docs.s3.amazonaws.com/regulatory/agreement/kalshi_member_agreement.pdf ; Rulebook v1.29 — https://kalshi-public-docs.s3.amazonaws.com/regulatory/rulebook/Kalshi%20DCM%20Rulebook%20v.1.29.pdf ; Developer Agreement v1.1 — https://kalshi-public-docs.s3.amazonaws.com/Kalshi-Developer-Agreement.pdf ; Data Terms — https://kalshi-public-docs.s3.amazonaws.com/kalshi-data-terms-of-service.pdf ; LIP — https://help.kalshi.com/incentive-programs/liquidity-incentive-program
- NY OGC Op. 00-02-05 — https://www.dfs.ny.gov/insurance/ogco2000/rg000205.htm
- NY A10344 (parametric line) — https://www.nysenate.gov/legislation/bills/2023/A10344
- NY AG releases: Kalshi (31 Jul 2026) — https://ag.ny.gov/press-release/2026/governor-hochul-and-attorney-general-james-announce-new-york-has-sued-kalshi ; Polymarket US (24 Sep 2026) — https://ag.ny.gov/press-release/2026/attorney-general-james-and-governor-hochul-announce-lawsuit-against-polymarket
- CourtListener docket, NY v. KalshiEX, 1:26-cv-06550 (S.D.N.Y.) — https://www.courtlistener.com/docket/73700030/
- PRISM terms (web and PDF) — https://prism.oregonstate.edu/terms/ ; https://prism.oregonstate.edu/documents/PRISM_terms_of_use.pdf
- Ensuro site and terms — https://ensuro.co ; https://docs.ensuro.co/ensuro-docs/ensuro-terms-of-service ; https://docs.ensuro.co/
- Nexus Mutual docs and member agreement — https://docs.nexusmutual.io/overview/membership/ ; https://app.nexusmutual.io/assets/Nexus-Mutual-DAO-Member-Agreement-FIN.pdf
- Descartes — https://descartesunderwriting.com/newsroom/descartes-expands-us-flood-offer-highly-responsive-parametric-flood-location-product (25 Jun 2025); https://descartesunderwriting.com/about/descartes-underwriting
- FloodFlash — https://floodflash.co ; ForecastEx — https://forecastex.com ; DFlow/Kalshi — https://solana.com/news/dflow-prediction-markets-api (1 Dec 2025)

### Secondary (MEDIUM)
- WilmerHale, "10 Takeaways from the CFTC Event Contracts Proposed Rulemaking" (18 Jun 2026) — https://www.wilmerhale.com/en/insights/client-alerts/20260618-10-takeaways-from-the-cftc-event-contracts-proposed-rulemaking
- Katten, DCM application advisory (20 Nov 2025) — https://katten.com/so-you-want-to-apply-to-become-a-cftc-registered-designated-contract-market-dcm-heres-what-you-should-know
- Holland & Knight on the 9th Cir. (28 Aug 2026) — https://www.hklaw.com/en/insights/publications/2026/08/ninth-circuit-upholds-state-and-tribal-authority-over-sports-related
- Latham US Crypto Policy Tracker (updated Aug 2026) — https://www.lw.com/en/us-crypto-policy-tracker/legislative-developments ; CNBC (15 Sep 2026) — https://www.cnbc.com/2026/09/15/senate-cloture-vote-on-clarity-act-fails-dealing-regulatory-setback-to-crypto-industry.html ; Fintech Weekly — https://www.fintechweekly.com/news/clarity-act-cloture-vote-fails-49-50-september-2026
- Jones Day on Letter 26-25 (Sep 2026) — https://www.jonesday.com/en/insights/2026/09/cftc-extends-noaction-relief-for-introducing-broker-registration-to-all-providers-of-passive-software
- Artemis on Sola/Beazley/Spinnaker (31 Aug 2023) — https://www.artemis.bm/news/parametric-tornado-insurance-launched-by-beazley-sola-spinnaker/ ; Artemis on Arbol — https://www.artemis.bm/news/arbol-launches-london-mga-led-by-ibarra-to-write-global-parametric-business/
- NJ cert petition coverage — https://natlawreview.com/article/new-jersey-seeks-supreme-court-review-kalshi-decision-and-one-additional-argument ; https://www.njoag.gov/wp-content/uploads/2026/09/2026-0902_26-_PetitionForWritOfCertiorari.pdf
- BarnBridge coverage — https://www.theblock.co/post/269081/barnbridge-dao-settles-with-sec-for-1-7-million-agrees-to-stop-selling-crypto-bond-product ; SEC order — https://www.sec.gov/files/litigation/admin/2023/33-11262.pdf
- Polymarket US timeline — https://www.coindesk.com/policy/2025/09/03/u-s-cftc-gives-go-ahead-for-polymarket-s-new-exchange-qcx ; https://www.pymnts.com/cryptocurrency/2025/prediction-market-polymarket-begins-rolling-out-us-app/ ; https://www.prnewswire.com/news-releases/polymarket-acquires-cftc-licensed-exchange-and-clearinghouse-qcex-for-112-million-302509626.html
- Kalshi broker partners — https://thepaypers.com/fintech/news/apex-fintech-solutions-and-kalshi-launch-prediction-markets-api ; https://alpaca.markets/blog/alpaca-partners-with-kalshi-to-expand-prediction-market-access-through-its-global-brokerage-infrastructure/
- Nayms — https://www.crowdfundinsider.com/2022/05/191349-nayms-becomes-fully-regulated-insurance-marketplace-for-crypto-assets-in-bermuda/
- Etherisc / Lemonade coalition — https://www.businesswire.com/news/home/20230328005342/en/Nearly-7000-Kenyan-Farmers-Protected-by-the-Lemonade-Crypto-Climate-Coalition
- Raincoat — https://newsismybusiness.com/raincoat-raises-4-5m-to-create-new-insurance-for-natural-disasters/
- NRRA exempt commercial purchaser — https://www.insurancejournal.com/magazines/mag-ideaexchange/2018/09/17/500913.htm ; fronting retention — https://www.insurancebusinessmag.com/us/news/excess-surplus/mga-boom-raises-operational-and-credit-exposure-for-us-fronting-insurers-567929.aspx ; reinsurance collateral — https://www.mayerbrown.com/en/insights/resource-centers/insurtech/reinsurance
- Nexus Mutual UK company status — https://find-and-update.company-information.service.gov.uk/company/10917763/filing-history
- NCOIL P&C committee minutes (Apr 2026) — https://ncoil.org/wp-content/uploads/2026/05/Louisville-Prop-Cas-Cmte-Minutes-1.pdf

### Tertiary (LOW) — flag for validation
- Sister notes (`~/Desktop/defi-options/.planning/research/notes/notes-D-legal-pm.md`, 2026-09-23): OKX plea, the $5M+ DCM figure, 12–24 month DCM timeline, cert No. 26-299, CFTC crypto rules to OIRA, BRCA status.
- Practitioner estimates with no source: offshore setup time and cost, MGA program setup time, CTA registration time.

## Metadata

**Confidence breakdown:**
- Legal framework (statutes, rules, Kalshi terms, Letter 26-25): HIGH. Primary text fetched.
- Application to our facts (fork outcome, intermediary status, CPO, token): MEDIUM–LOW. Our inference; this is what counsel must answer.
- Insurance route: MEDIUM. NY text is verified; other states and the NAIC paper are not.
- Precedents: MEDIUM. Primary for enforcement, Ensuro and Nexus; secondary for Nayms, Arbol, Raincoat and the Polymarket US timeline.
- Routes time and cost: LOW–MEDIUM. Comparables are sourced; our own estimates are marked.

**Research limits:** The session's web-search budget (200 calls) ran out mid-research. Remaining checks used direct fetches of primary sources (Federal Register API, cftc.gov, Kalshi's S3 documents, NY AG, CourtListener). CME's site blocks automated access, so CME was not checked.

**Research date:** 2026-09-30
**Valid until:** 2026-10-14. This area is moving fast. Kalshi's cert response is due 8 Oct; comments on the CFTC CPO/CTA and conflicts proposals close 5 Oct; comments on Reg Crypto Assets close 20 Oct; the NY remand decision is pending; CLARITY could be re-filed.
