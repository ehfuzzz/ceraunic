# Roadmap: weather-insurance

## Overview

Four milestones inside a 2-day window, one after it. v0.1 turns the hl-mm ins1/ins2 findings into the full evidence set from real Kalshi bid/ask, station and gridded weather, and stand-in sales data (pre-registered rules, then numbers). v0.2 builds the protocol: the Python reference engine (contract spec, pricing/risk, margin, batch auction, pool tranches, oracle, hedging, RFQ) and the Solidity contracts for HyperEVM with a one-command deploy the owner runs. v0.3 ships the portal and hosted demo in `sim` mode (onboarding, elasticity, coverage, trading, dashboards, POS-connect). v0.4 is the pitch: token/pool memo, legal-options memo, two decks. v0.5 is the owner-hand tail: testnet deploy, Square sandbox flip, recorder-fed re-evaluation, pilot prep.

Mode is YOLO with heavy parallelization: phases inside a wave run concurrently on detached workers; the seat (lead) plans, reviews and commits.

## Domain Expertise


## Milestones

- 📋 **v0.1 Evidence** — Phases 1–6 (the paper: every number in the brief's Evaluation section)
- 📋 **v0.2 Protocol** — Phases 7–9 (reference engine, Solidity contracts, engine API with chain modes + house MM)
- 📋 **v0.3 Portal + demo** — Phases 10–13 (Next.js portal, trading + dashboards, POS-connect, hosted demo)
- 📋 **v0.4 Pitch** — Phases 14–16 (token + pool memo, legal memo, two decks)
- 📋 **v0.5 Live tail (owner-hand)** — Phase 17 (testnet deploy, Square sandbox, recorder-fed re-evaluation, pilots)

## Execution waves (parallel plan)

| Wave | Runs concurrently | Gate to next wave |
|------|-------------------|-------------------|
| A | 1 Data foundation · 7 Spec + engine core (spec first) · 8 Contracts (from the spec draft) · 15 Legal memo · 14 Token memo (research half) | Phase 1 manifests land; Phase 7 spec frozen |
| B | 2 Station hedge · 3 Geography + residual bake-off · 4 Netting + pool · 5 Elasticity learning · 9 Engine API + house MM · 10 Portal core · 11 Trading + dashboards · 12 POS-connect | Evidence phases produce results; API contract stable |
| C | 6 Evaluation report · 13 Hosted demo · 14 Token memo (numbers half) · 16 Decks | Report + demo URL exist |
| D | 17 Live tail | Owner runs deploy script; owner pastes Square sandbox token |

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

### v0.1 Evidence
- [ ] **Phase 1: Data foundation** - Repo scaffold, ins1/ins2 code and data imported with attribution, every dataset pulled with manifests and point-in-time conventions documented
- [ ] **Phase 2: Station hedge quality** - EVAL-01: how well the liquid ladders hedge temperature and rain at the settlement station, from real bid/ask
- [ ] **Phase 3: Geography basis + residual bake-off** - EVAL-02/03: basis at nearby stations and grid points; per-cell (PRISM, nClimGrid), regional-factor and station-pair residual designs compared and picked
- [ ] **Phase 4: Netting + pool economics** - EVAL-04/05: how much opposite business exposure nets by geography; auction leftovers; pool capital, house-MM markouts, costs, revision risk
- [ ] **Phase 5: Elasticity learning** - EVAL-06: learn a business's weather sensitivity from stand-in sales data and show the prescribed hedge beats doing nothing
- [ ] **Phase 6: Evaluation report** - EVAL-07: one reproducible report, pre-registration vs results, figures, one-command rebuild

### v0.2 Protocol
- [ ] **Phase 7: Protocol spec + reference engine** - PROT-01: contract spec and the Python engine (payoffs, pricing/risk, margin, batch auction, pool tranches, oracle policy, Kalshi paper hedging, RFQ)
- [ ] **Phase 8: Solidity contracts** - PROT-02: Foundry contracts for HyperEVM (policy/residual, auction, pool vault with junior token tranche, oracle adapter, mock USDC, token), money-failure tests, owner-run deploy script
- [ ] **Phase 9: Engine API, chain modes, house MM** - PROT-03/04/05: the API the portal talks to, `sim` | `anvil` | `testnet` switch, house market-maker loop, both hedge-leg paths

### v0.3 Portal + demo
- [ ] **Phase 10: Portal core** - PORT-01: Next.js on Vercel — wallet onboarding, sales-CSV upload, elasticity view, coverage recommendation and quote, buy policy (both paths), policies/claims view
- [ ] **Phase 11: Trading + dashboards** - PORT-02: residual auction UI for any wallet, LP/pool dashboard, house-MM/admin dashboard
- [ ] **Phase 12: POS-connect** - PORT-03: Square Orders adapter on fixtures, flips to the sandbox when the owner's token lands
- [ ] **Phase 13: Hosted demo** - PORT-04: public URL in `sim` mode with seeded demo businesses, smoke-tested, demo script

### v0.4 Pitch
- [ ] **Phase 14: Token + pool economics memo** - PITCH-01: token as junior first-loss pool capital + governance; pre-seed $500k–$1.5M uses of funds, with numbers from Phases 4–5
- [ ] **Phase 15: Legal-options memo** - PITCH-02: counsel-ready memo on intermediary status, open auctions with retail wallets, offshore vs parametric wrapper vs DCM listing
- [ ] **Phase 16: Decks + demo script** - PITCH-03: crypto-native deck and fintech/insurtech deck from the same evidence, owner's voice, demo walkthrough

### v0.5 Live tail (owner-hand)
- [ ] **Phase 17: Testnet + sandbox + re-evaluation** - Owner runs the deploy; portal flips to testnet; Square sandbox live; recorder-fed re-run of Phases 2–4 on real order books; pilot prep and mainnet-readiness checklist

## Phase Details

### Phase 1: Data foundation
**Goal**: Everything downstream reads from one documented, manifested data layer: Kalshi candles for every weather series in the five cities (temperature and rain, full available history), recorded order books from the hl-mm S3 feed, IEM ASOS daily max/precip for settlement and nearby stations, nClimGrid-Daily and PRISM daily grids, Census CBP NAICS×zip, and the stand-in sales datasets (Citi Bike, Divvy, Rossmann, M5). ins1/ins2 code and rows.json imported with attribution. Point-in-time conventions written down once (nClimGrid label D = calendar D+1, Chicago 06:00Z close, TWC vs NWS source).
**Depends on**: Nothing (first phase)
**Research**: Likely (data access + history coverage)
**Research topics**: Kalshi historical weather series and how far back candles go (older tickers before KXHIGH*; rain/low-temp/snow series per city); PRISM daily download path and terms; NOAA Stage IV for rain; S3 recorder schema (from hl-mm); which stand-in sales datasets are downloadable without an account; CBP table access
**Plans**: 6 plans

Plans:
- [ ] 01-01: Repo scaffold (uv Python project `wi`, pnpm workspace placeholder, data/ layout, manifests convention) + import ins1/ins2 code and data with attribution
- [ ] 01-02: Kalshi history: discover every weather series for the five cities, pull candles (all history) and settlements, keyless; S3 recorder reader
- [ ] 01-03: Station weather: IEM ASOS daily max/min/precip for settlement + nearby stations (NYC/LGA/JFK, EWR/TTN, MDW/ORD, MIA/FLL/OPF) over the Kalshi history
- [ ] 01-04: Gridded weather: nClimGrid-Daily and PRISM daily tmax/prcp subsets within 40 km of each station; day-alignment check reproduced
- [ ] 01-05: Sales stand-ins + business mix: Citi Bike, Divvy, Rossmann, M5 (or substitutes), Census CBP NAICS×zip for the five metros
- [ ] 01-06: DATA.md manifest (URLs, bytes, md5, dates), conventions doc, one-command `make data`

### Phase 2: Station hedge quality
**Goal**: EVAL-01 answered with pre-registered rules: for each city and for temperature and rain, the executable replicating portfolio from bid/ask at 24 h / 12 h / 2 h, HE at the settlement station, overround, spread cost, depth (from recorded books), binning RMSE, settlement-source mismatch — extending ins1 to the full history and to rain.
**Depends on**: Phase 1
**Research**: Unlikely (ins1 method exists; extension)
**Plans**: 3 plans

Plans:
- [ ] 02-01: Pre-registration (rules, thresholds, sample) + temperature ladders over full history
- [ ] 02-02: Rain ladders (and any low-temp/snow series present) with the same method
- [ ] 02-03: Liquidity and cost from recorded order books; results tables + figures written to reports/eval-01/

### Phase 3: Geography basis + residual bake-off
**Goal**: EVAL-02 and EVAL-03: basis at nearby stations and at PRISM/nClimGrid points around each settlement station, then the residual designs head to head — per-cell (PRISM and nClimGrid), one regional factor per station, nearby-station pairs — for temperature and rain, reporting HE of station ladder + residual, residual book variance, and implied premium; a verdict on which designs survive.
**Depends on**: Phase 1
**Research**: Likely (method choice)
**Research topics**: Regional-factor estimation (first principal component of cell−station residuals vs simple metro mean); how PRISM and nClimGrid differ in observation-day convention; rain interpolation error at 4 km
**Plans**: 4 plans

Plans:
- [ ] 03-01: Pre-registration + geography basis at nearby stations and grid points (temperature, rain)
- [ ] 03-02: Per-cell residual with PRISM vs nClimGrid (re-run of ins2 V1 on both grids, full history)
- [ ] 03-03: Regional-factor residual and station-pair residual designs
- [ ] 03-04: Bake-off table, verdict, and the residual spec handed to Phase 7 (which index, which day convention, which revision policy)

### Phase 4: Netting + pool economics
**Goal**: EVAL-04 and EVAL-05: build a synthetic business population per metro from Census CBP NAICS×zip and published sector weather elasticities, compute net weather exposure at zip / station / metro, run the batch-auction mechanism on that population against history, and measure what the pool must carry: capital for the tail (correlated heatwave/rain days), house-MM markouts, trading costs, and weather-data revision risk under the stated settlement policy.
**Depends on**: Phase 1 (Phase 3 verdict improves it but is not required to start)
**Research**: Likely (elasticity priors, capital rule)
**Research topics**: Sector weather elasticities (Lazo et al. 2011 and later), CBP access, a defensible capital rule (TVaR at 99 % vs stress days), auction fee/price rules for uniform-price batch clearing
**Plans**: 4 plans

Plans:
- [ ] 04-01: Pre-registration + business population and exposure map by geography
- [ ] 04-02: Batch-auction simulation on history (netting ratio, leftovers, clearing prices)
- [ ] 04-03: Pool capital, house-MM markouts, trading costs, revision-risk tables
- [ ] 04-04: Results write-up to reports/eval-04-05/ with the numbers Phase 14 needs (capital per $ of cover, fee income, tail)

### Phase 5: Elasticity learning
**Goal**: EVAL-06: on stand-in sales data, estimate weather sensitivity ex ante (year 1), prescribe the hedge, evaluate out of sample (year 2) at real Kalshi asks: HE vs no hedge, single-store vs pooled/shrunk estimate, and the days-of-history-until-hedging-beats-nothing curve. This is the elasticity engine's method, proven before it goes in the portal.
**Depends on**: Phase 1
**Research**: Likely (method)
**Research topics**: Regression form with day-of-week/holiday/trend controls; hierarchical shrinkage across stores; mapping elasticity to a capped-linear payout; which datasets sit near a Kalshi city
**Plans**: 4 plans

Plans:
- [ ] 05-01: Pre-registration + panel construction (store-day sales joined to station weather)
- [ ] 05-02: Elasticity estimator (single-store and pooled) with confounder controls
- [ ] 05-03: Prescribed hedge and out-of-sample evaluation at asks
- [ ] 05-04: Days-of-history curve, results to reports/eval-06/, estimator packaged for Phase 7/9

### Phase 6: Evaluation report
**Goal**: EVAL-07: one reproducible report (Markdown + figures, PDF export) that states the pre-registered rules, the results of Phases 2–5, deviations, caveats, and what the numbers mean for the product; a single command rebuilds every table from the manifested data.
**Depends on**: Phases 2, 3, 4, 5
**Research**: Unlikely (assembly)
**Plans**: 3 plans

Plans:
- [ ] 06-01: Report skeleton + pre-registration vs results ledger
- [ ] 06-02: Figures and tables assembled; caveats and deviations
- [ ] 06-03: Fresh-eyes review (reviewer) against the brief's Evaluation section; fixes; `make report`

### Phase 7: Protocol spec + reference engine
**Goal**: PROT-01: a written protocol spec (instruments, payout functions, settlement and revision policy, auction rules, pool tranches, margin, fees, hedge-leg paths) and the Python engine that implements it end to end on historical data: pricing/risk, margin, uniform-price batch auction, pool accounting (junior token / senior stablecoin), oracle adapter, Kalshi paper-hedging engine, RFQ for bespoke residuals. Fixture-driven end-to-end run produces a verifiable artifact.
**Depends on**: Nothing to start (spec); Phase 3 verdict to freeze the residual index
**Research**: Likely (mechanism design)
**Research topics**: Uniform-price batch auction clearing with both-sided hedgers and MMs; junior/senior tranche waterfall precedents (Nexus Mutual, Ondo, Maple); margin for bounded-payout contracts; oracle revision policy precedents (Arbol, USDA PRF)
**Plans**: 6 plans

Plans:
- [ ] 07-01: Protocol spec v0 (SPEC.md) — instruments, payoffs, settlement, auction, pool, margin, fees, both hedge-leg paths
- [ ] 07-02: Pricing/risk engine + margin engine
- [ ] 07-03: Batch auction + pool accounting with tranches
- [ ] 07-04: Oracle adapter (nClimGrid/PRISM/ASOS, revision policy) + Kalshi paper-hedging engine
- [ ] 07-05: RFQ engine + house-MM quoting logic
- [ ] 07-06: End-to-end fixture run (one metro, 30 days) producing a manifest artifact; money-failure tests only

### Phase 8: Solidity contracts
**Goal**: PROT-02: Foundry project with PolicyManager (policies and residual positions), BatchAuction (commit/reveal or sealed-bid uniform price), PoolVault (senior stablecoin + junior token tranche, waterfall), OracleAdapter (settlement values with revision window), MockUSDC, the protocol token; tests only for money-failure modes; anvil deploy script; HyperEVM testnet deploy script with the big-block toggle, run by the owner.
**Depends on**: Phase 7 spec v0 (07-01)
**Research**: Likely (chain specifics)
**Research topics**: HyperEVM testnet chain id, RPC, faucet path, big-block `evmUserModify`, gas limits; Foundry config for HyperEVM; auction privacy (sealed bids) vs simplicity for a prototype
**Plans**: 5 plans

Plans:
- [ ] 08-01: Foundry scaffold, MockUSDC, token, interfaces from SPEC.md
- [ ] 08-02: PolicyManager + OracleAdapter with settlement/revision window
- [ ] 08-03: BatchAuction (uniform price) + PoolVault tranches and waterfall
- [ ] 08-04: Money-failure tests (clearing conserves value, tranche waterfall, margin cap, settlement on stale oracle)
- [ ] 08-05: Deploy scripts (anvil + HyperEVM testnet with big blocks), addresses file, owner runbook

### Phase 9: Engine API, chain modes, house MM
**Goal**: PROT-03/04/05: the API the portal talks to — quote, buy policy (house-hedge path and overlay path), post auction orders, pool deposit/withdraw, positions, settlements — with a `CHAIN_MODE` switch: `sim` (fully in-engine state), `anvil`, `testnet` (viem against the deployed contracts). House-MM loop quotes residual auctions from the risk engine and paper-hedges on Kalshi at recorded books. Same behaviour in all modes.
**Depends on**: Phase 7 (engine), Phase 8 (ABIs)
**Research**: Likely (hosting decision)
**Research topics**: Where the engine API runs for the hosted demo — recommendation: TypeScript engine modules inside the Next.js app (Vercel) with Upstash Redis state and a parity fixture against the Python engine, vs Python FastAPI on Cloud Run (needs a GCP project the owner creates); decide in research and record
**Plans**: 5 plans

Plans:
- [ ] 09-01: API contract (OpenAPI) + engine port/bridge decision implemented; sim-mode state store
- [ ] 09-02: Quote / buy / positions / settlement endpoints (both hedge-leg paths)
- [ ] 09-03: Auction order endpoints + pool deposit/withdraw
- [ ] 09-04: anvil and testnet modes via viem; parity fixture vs Python engine
- [ ] 09-05: House-MM loop (quotes, paper Kalshi hedge, pool seeding) runnable as a job

### Phase 10: Portal core
**Goal**: PORT-01: Next.js app on Vercel with wallet onboarding (HyperEVM testnet chain config), sales-CSV upload, elasticity view (from the Phase 5 estimator), coverage recommendation with quote and cost breakdown (station leg vs residual leg), buy policy on either path, policies and claims/settlement view.
**Depends on**: Phase 9 API contract (09-01)
**Research**: Unlikely (owner's usual stack: Next.js, Vercel, Upstash)
**Plans**: 5 plans

Plans:
- [ ] 10-01: App scaffold, wallet connect, chain config, design tokens
- [ ] 10-02: Onboarding + CSV upload + elasticity view
- [ ] 10-03: Coverage recommendation + quote + buy (both paths)
- [ ] 10-04: Policies, claims and settlement views
- [ ] 10-05: End-to-end smoke on sim mode (Playwright), fixes

### Phase 11: Trading + dashboards
**Goal**: PORT-02: auction UI where any wallet posts bids/offers into the residual batch auctions and sees clearing results; LP/pool dashboard (tranches, utilisation, yield, drawdowns); house-MM/admin dashboard (book, hedges, margin, oracle status).
**Depends on**: Phase 9 (09-03), Phase 10 scaffold
**Research**: Unlikely (internal patterns)
**Plans**: 3 plans

Plans:
- [ ] 11-01: Auction trading UI
- [ ] 11-02: LP/pool dashboard
- [ ] 11-03: House-MM/admin dashboard

### Phase 12: POS-connect
**Goal**: PORT-03: Square Orders API adapter that fills the same sales panel the CSV upload does, running on recorded fixtures shaped like Square's responses until the owner pastes `SQUARE_SANDBOX_ACCESS_TOKEN`, then against the sandbox with no code change.
**Depends on**: Phase 10 (10-02)
**Research**: Likely (external API)
**Research topics**: Square Orders API search/pagination, sandbox seller setup, OAuth vs access token for the prototype
**Plans**: 2 plans

Plans:
- [ ] 12-01: Adapter + fixtures + connect flow in the portal
- [ ] 12-02: Sandbox flip (token from secrets.env), verification against a seeded sandbox seller

### Phase 13: Hosted demo
**Goal**: PORT-04: the portal deployed to a public Vercel URL in `sim` mode with seeded demo businesses (one per city, opposite exposures), a running house MM, a demo script the owner can follow in five minutes, and a smoke test that proves the loop (upload → recommend → buy → auction → settle) works at the URL.
**Depends on**: Phases 9, 10, 11 (12 optional)
**Research**: Unlikely (deploy patterns exist)
**Plans**: 3 plans

Plans:
- [ ] 13-01: Vercel project, env, Upstash state, deploy
- [ ] 13-02: Seed demo businesses + house MM job; demo script
- [ ] 13-03: Smoke test at the URL; owner push notification with the link

### Phase 14: Token + pool economics memo
**Goal**: PITCH-01: a memo in the owner's voice: what the token is (junior first-loss pool capital + governance over risk parameters), how premiums, auction fees and hedge P&L flow through the tranches, capital per $ of cover and tail from Phase 4, unit economics from Phase 5, and a pre-seed raise of $500k–$1.5M with uses of funds at each tier.
**Depends on**: Phase 4 numbers (research half can start at once)
**Research**: Likely (precedents)
**Research topics**: Tokenised first-loss capital precedents (Nexus Mutual, Ondo, Maple, Sherlock), pool-token failure modes, comparable pre-seed rounds in on-chain insurance / prediction-market infra
**Plans**: 2 plans

Plans:
- [ ] 14-01: Precedents + token mechanics draft
- [ ] 14-02: Numbers in (capital, fees, tail), uses of funds, final memo

### Phase 15: Legal-options memo
**Goal**: PITCH-02: a counsel-ready memo (not advice): intermediary status of the house-hedge path vs the overlay path; open residual auctions with retail wallets on an EVM chain; the three routes (offshore entity + US geo-block with a US affiliate for the Kalshi leg; parametric-insurance wrapper with a licensed carrier; DCM listing of grid/regional contracts); what must be true before mainnet; questions for counsel.
**Depends on**: Nothing
**Research**: Likely (regulatory)
**Research topics**: CFTC event-contract and swap rules for non-ECP counterparties, DCM/intermediary definitions, state parametric-insurance treatment, Kalshi terms on hedging for third parties, precedents (Arbol, Polymarket US, Kalshi partners)
**Plans**: 2 plans

Plans:
- [ ] 15-01: Research shards (CFTC, insurance, precedents) with sources
- [ ] 15-02: Memo with routes, gates before mainnet, counsel questions

### Phase 16: Decks + demo script
**Goal**: PITCH-03: two decks from the same evidence in the owner's voice — crypto-native funds (token story leads, Hyperliquid ecosystem angle) and fintech/insurtech funds (product story leads) — each with the evaluation numbers, the demo, the ask, and the legal posture; plus a demo walkthrough.
**Depends on**: Phases 6, 13, 14, 15
**Research**: Unlikely (assembly)
**Plans**: 3 plans

Plans:
- [ ] 16-01: Narrative + slide outline for both audiences (owner style guide applied)
- [ ] 16-02: Crypto-native deck
- [ ] 16-03: Fintech/insurtech deck + demo script

### Phase 17: Testnet + sandbox + re-evaluation
**Goal**: After the window: owner runs the HyperEVM testnet deploy (agents ship the runbook and verify the addresses); portal flips to `testnet`; Square sandbox goes live; Phases 2–4 re-run on the recorder's real order books once enough days exist; pilot-prep checklist and mainnet-readiness list from the legal memo.
**Depends on**: Phases 8, 12, 13; owner-hand items
**Research**: Unlikely
**Plans**: 3 plans

Plans:
- [ ] 17-01: Owner runbook executed; testnet addresses verified; portal in testnet mode
- [ ] 17-02: Square sandbox live; POS panel verified
- [ ] 17-03: Recorder-fed re-evaluation + pilot prep + mainnet-readiness checklist

## Progress

**Execution Order:**
Waves A → B → C → D as in the table above; within a wave phases run concurrently. Numeric order is the fallback when running sequentially.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Data foundation | v0.1 | 0/6 | Not started | - |
| 2. Station hedge quality | v0.1 | 0/3 | Not started | - |
| 3. Geography + residual bake-off | v0.1 | 0/4 | Not started | - |
| 4. Netting + pool economics | v0.1 | 0/4 | Not started | - |
| 5. Elasticity learning | v0.1 | 0/4 | Not started | - |
| 6. Evaluation report | v0.1 | 0/3 | Not started | - |
| 7. Protocol spec + reference engine | v0.2 | 0/6 | Not started | - |
| 8. Solidity contracts | v0.2 | 0/5 | Not started | - |
| 9. Engine API, chain modes, house MM | v0.2 | 0/5 | Not started | - |
| 10. Portal core | v0.3 | 0/5 | Not started | - |
| 11. Trading + dashboards | v0.3 | 0/3 | Not started | - |
| 12. POS-connect | v0.3 | 0/2 | Not started | - |
| 13. Hosted demo | v0.3 | 0/3 | Not started | - |
| 14. Token + pool economics memo | v0.4 | 0/2 | Not started | - |
| 15. Legal-options memo | v0.4 | 0/2 | Not started | - |
| 16. Decks + demo script | v0.4 | 0/3 | Not started | - |
| 17. Testnet + sandbox + re-evaluation | v0.5 | 0/3 | Not started | - |


## Recovery milestone — 2026-10-01

**Status:** planning/checkpointed; execution stopped. Existing phases/milestones/plans retained. Read [recovery entry](RECOVERY-2026-10-01.md).

**Resume:** 3 incomplete PRISM re-pull; 17 owner/testnet/recorder gates; 18 economics.

### Phase 18: Weather venue and recorder economics

**Goal:** Persist pending venue comparison and real-depth economics.
**Depends on:** 17 recorder data; ORFE 3 owns census.
**Status:** planned; window/census incomplete.
**Research:** Existing sources reviewed; further review before execution planning.
**Plans:** 0 new execution plans.
**Success criteria:** Census linked not duplicated; actual burn/ladder/depth/resolved variance checked; demo assumptions and non-executable hedge explicit.
**Context:** [context](phases/18-weather-venue-and-recorder-economics/18-CONTEXT.md).

### Existing phase directory register

Includes historical and alternate folders sharing a phase number; adds no IDs or completion claims.

| Phase source | Markdown artifacts |
|---|---|
| [01-data-foundation](phases/01-data-foundation/) | 8 |
| [02-station-hedge-quality](phases/02-station-hedge-quality/) | 3 |
| [03-geography-residual-bakeoff](phases/03-geography-residual-bakeoff/) | 6 |
| [04-netting-pool-economics](phases/04-netting-pool-economics/) | 6 |
| [05-elasticity-learning](phases/05-elasticity-learning/) | 4 |
| [06-evaluation-report](phases/06-evaluation-report/) | 3 |
| [07-protocol-spec-engine](phases/07-protocol-spec-engine/) | 8 |
| [08-solidity-contracts](phases/08-solidity-contracts/) | 6 |
| [09-engine-api-chain-modes](phases/09-engine-api-chain-modes/) | 6 |
| [10-portal-core](phases/10-portal-core/) | 3 |
| [11-trading-dashboards](phases/11-trading-dashboards/) | 2 |
| [12-pos-connect](phases/12-pos-connect/) | 3 |
| [13-hosted-demo](phases/13-hosted-demo/) | 5 |
| [14-token-pool-memo](phases/14-token-pool-memo/) | 6 |
| [15-legal-memo](phases/15-legal-memo/) | 5 |
| [16-decks](phases/16-decks/) | 2 |
| [17-testnet-sandbox-reeval](phases/17-testnet-sandbox-reeval/) | 1 |
| [18-weather-venue-and-recorder-economics](phases/18-weather-venue-and-recorder-economics/) | 1 |
