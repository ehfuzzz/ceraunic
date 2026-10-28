# weather-insurance (codename) — Localized Weather Insurance on Event Contracts

## What This Is

A weather-insurance protocol for small businesses built on top of existing liquid event contracts. A business picks a payout tied to the temperature or rainfall at its own location; most of that payout is hedged with the liquid Kalshi (later CME) ladders that settle at a nearby airport station, and a smaller on-chain "residual" contract covers the difference between the station and the business's location, settled on NOAA/PRISM data. Nearby businesses with opposite exposure (ice-cream shop long heat, foot-traffic shops short heat) trade the residual against each other in batch auctions; what does not net is held by a shared liquidity pool that the house market-maker seeds first. A portal reads a business's sales history, estimates how weather moves its revenue, and prescribes the cover.

Owner: Ehfaz (ehfuzzz). The protocol and the coin keep the plain codename `weather-insurance` until the owner renames them.

## Core Value

Prove, with real Kalshi bid/ask data and real weather data, that liquid station contracts plus a small residual market hedge a business's local weather risk better than doing nothing and cheaper than a bespoke contract — and ship the prototype that lets a business do it.

## Requirements

### Validated

- ✓ Liquid daily ladders (KXHIGHNY / KXHIGHCHI / KXHIGHMIA) replicate a capped linear heat payout at the settlement station with hedge effectiveness (HE) 0.86–0.94 and overround 0–17 % — hl-mm ins1, 272 city-days, 2026-09-30
- ✓ Thin ladders (KXHIGHTEWR / KXHIGHTTTN) are executable only near close: 2.4–2.7× overround at 24 h — hl-mm ins1
- ✓ Geography is the dominant hedge error: HE at a nearby station hedged with the settlement ladder falls to 0.1–0.6 (LGA/JFK on NYC, FLL/OPF on MIA, TTN/EWR cross) — hl-mm ins1
- ✓ Per-cell nClimGrid residual overlay FAILS as designed: 0 of 1,206 cells within 0.1 of station HE; residuals around one station are common-mode (ρ 0.74–0.83), so a residual book does not diversify across cells; nearest cell (0.7–2.5 km) HE 0.37–0.71 vs station 0.89–0.96; day-definition (grid label D = calendar D+1) and interpolation noise are a large part of the gap — hl-mm ins2, 2026-09-30
- ✓ Kalshi Chicago settles at Midway (CLIMDW), not O'Hare; Chicago markets close 06:00Z — hl-mm ins1

### Active

Evidence (the paper)
- [ ] EVAL-01 Station hedge quality for the five cities (NYC, EWR, TTN, CHI/MDW, MIA), temperature AND rain, from real Kalshi bid/ask (hourly candles + recorded order books): HE, overround, spread cost, liquidity depth, binning error, settlement-source mismatch
- [x] EVAL-02 Geography basis at nearby stations and at gridded points around each settlement station. **Done 2026-09-30 (descriptive):** station leg alone within 50 km, pooled median HE temperature 0.81 [0.78, 0.84], rain weekly 0.49 [0.38, 0.66], Miami lowest (0.67 / 0.13) (reports/eval-03/results.json `eval02`)
- [x] EVAL-03 Residual-contract bake-off: per-cell (PRISM and nClimGrid), one regional factor per station ("metro minus station"), nearby-station pairs; temperature and rain; report HE with station ladder + residual, and pick the design(s) that survive. **Done 2026-09-30:** temperature, nothing survives the +0.10 bar (best G1-P +0.061, P-A-IDW +0.052) → station leg alone plus RFQ residuals on P-A-IDW; rain weekly, G1-P (PRISM per-cell spread) wins at +0.229 on all 26 pairs after the 2026-10-02 PRISM re-pull (was +0.186 on 19 of 26), R-A the alternate; its HE lead over the failing runner-up P-A-IDW has a CI that includes 0 (reports/eval-03/results.json `verdicts`)
- [ ] EVAL-04 Netting: how much opposite-sign business exposure cancels at zip / station / metro level (Census CBP NAICS×zip × sector weather elasticities), and what the batch auction leaves for the pool
- [ ] EVAL-05 Pool economics: capital needed to carry the unmatched residual (tail, correlated heatwave days), house-MM markouts, trading costs, weather-data revision risk (prelim vs final), all with pre-registered rules
- [ ] EVAL-06 Learning a business's weather sensitivity from public stand-in sales data (Citi Bike / Divvy station-days, Rossmann, M5 or similar): ex-ante elasticity → prescribed hedge → out-of-sample HE vs no hedge vs pooled (shrunk) estimate; days-of-history-until-hedging-beats-nothing curve
- [ ] EVAL-07 Reproducible evaluation report with every number in the brief's Evaluation section, rules written before results

Protocol (on-chain + engine)
- [ ] PROT-01 Off-chain engine (Python, the numerical reference): contract spec and payout functions, pricing/risk engine, margin engine, uniform-price batch auction, pool accounting with a junior (token) and senior (stablecoin) tranche, NOAA/PRISM oracle adapter with a stated revision policy, hedging engine that paper-trades the Kalshi leg at recorded books, RFQ engine for bespoke residuals
- [ ] PROT-02 Solidity contracts (Foundry) for HyperEVM: policy/residual contract, batch auction, pool vault, oracle adapter, mock USDC; tests; one-command deploy script for HyperEVM testnet (big-block mode) that the owner runs
- [ ] PROT-03 Engine API with a chain-mode switch (`sim` | `anvil` | `testnet`) so the portal works end to end before the testnet deploy
- [ ] PROT-04 House market-maker: quotes residual auctions from the risk engine, hedges on Kalshi (paper), seeds the pool; outside LPs later
- [ ] PROT-05 Both hedge-leg paths: (default) business buys one policy and the house hedges the station leg; (fallback) business buys the Kalshi ladder itself and the venue sells only the residual overlay

Portal + onboarding
- [ ] PORT-01 Deployable Next.js portal on Vercel: wallet onboarding, sales-CSV upload, elasticity view, coverage recommendation + quote, buy policy (both paths), settlement/claims view
- [ ] PORT-02 Trading UI: anyone with a wallet can post bids/offers into the residual batch auctions; LP/pool dashboard; house-MM/admin dashboard
- [ ] PORT-03 POS-connect: Square Orders adapter, fixture-backed until the owner creates the sandbox app, then live against the sandbox
- [ ] PORT-04 Hosted demo at a public URL running in `sim` mode, flipping to testnet with no UI change

Pitch
- [ ] PITCH-01 Token + pool economics memo: token = junior first-loss capital of the pool + governance over risk parameters; pre-seed raise $500k–$1.5M with uses of funds
- [ ] PITCH-02 Legal-options memo for counsel: intermediary status of the house hedge, open auctions with retail wallets, offshore vs parametric-insurance wrapper vs DCM-listing path; nothing goes to mainnet before counsel
- [ ] PITCH-03 Two decks from the same evidence, in the owner's voice: crypto-native funds (token story leads) and fintech/insurtech funds (product story leads); demo script

### Out of Scope

- Mainnet deployment, real money, real customers in v1 — testnet + paper hedging until the counsel memo is answered (owner 2026-09-30)
- Agents placing Kalshi orders, holding exchange keys, creating accounts, or contacting anyone — standing rule across the owner's projects; the Kalshi recorder runs read-only in the hl-mm session
- Native HyperCore markets (HIP-3 / HIP-4) — need a 500k HYPE stake (~$44M); partner path only. Our contracts are ordinary HyperEVM smart contracts and need no stake
- Sensor / business-owned gauge oracles — moral hazard and tamper risk (hl-mm ins2 V4)
- Bespoke per-zip contracts warehoused one by one by a dealer — fixed underwriting cost per quote, thin-book overround, WeatherBill precedent (hl-mm ins2 V0)
- Production hardening, mirror tests, enterprise process — prototype-grade engineering in the 2-day window (owner: "we don't have to engineer heavy rn just build a prototype")
- Paid weather vendors or data licences — free NOAA, PRISM, IEM, Kalshi keyless reads, public sales datasets only

## Context

- **Prior work to reuse:** `~/Desktop/hl-mm-wt/corpus-fix/reports/ins1/` (analyze.py, pull_candles.py, rows.json with 272 city-days of ladder K / payout / ASOS max, iem-*.csv, books.json, open-weather-markets-2026-09-29.json) and `scripts/ins2/` (extract.py, analyze.py, revision.py for nClimGrid) plus `reports/ins2/DATA.md`. Uncommitted in that worktree; copy with attribution. The hl-mm `.venv` has netCDF4.
- **Live data feed:** the hl-mm session (owner-approved 07:45Z 2026-09-30) is deploying a key-less read-only Kalshi weather order-book recorder on the Tokyo AWS box: books every 60 s inside 48 h of close and every 5 min otherwise, settlements, hourly candles, daily re-discovery of open weather series → `s3://hlmm-reduced-5325/kalshi-weather-books/{books,settlements,candles,discovery}/date=YYYY-MM-DD/` (JSONL.gz, README at the prefix root, systemd `hlmm-wxrec.service`). Exact schema and first timestamp to be sent to this session.
- **Weather data:** NOAA nClimGrid-Daily (1/24°, monthly NetCDF, one file per month, prelim for the open month, no vintage archive → revisions only measurable going forward; grid label D = calendar day D+1), PRISM daily (4 km, free tier), IEM ASOS daily max/precip for the settlement and nearby stations, NOAA Stage IV for rain if needed.
- **Kalshi facts:** daily high-temp ladders for NY (Central Park), CHI (Midway), MIA, EWR, TTN; hourly candles carry yes bid/ask OHLC; public order-book endpoint is keyless; no historical book archive; 56 % of weather volume closes within 2 days; no weather series in the incentive program.
- **Prior art:** Arbol, WeatherBill→Climate Corp (SMB product died on demand and analyst cost), USDA PRF (0.25° CPC grid, works at scale, subsidised), FloodFlash, Planalytics; Luo (SSRN 7138562) on Kalshi weather price calibration; CME weather never found two-sided end users.
- **Sister projects:** defi-options (RFQ options venue on HyperEVM, same owner; shares chain family and counsel questions), hl-mm (Kalshi LIP bot, recorder, AWS boxes), market-analogs. Umbrella: Intelayer Labs (software products; no entity/website work yet).
- **Owner practice:** pre-register evaluation rules before producing numbers (hl-mm style); idea variants get tested, not just judged; owner writing-style guide applies to anything in his voice (see memory `owner-writing-style`).

## Constraints

- **Timeline:** prototype + numbers in under 2 days from 2026-09-30, by heavy parallelization; no plan-quota cap (owner). Cut order if tight: POS-connect last-mile and token-memo polish go first; keep numbers + testnet-ready demo + deck
- **Engineering depth:** prototype-grade; tests only for silent-corruption / money failure modes (AGENTS.md); end-to-end runs on fixtures over mirror tests
- **Chain:** HyperEVM testnet, Foundry/Solidity; deploy script run by the owner (agents hold no funded keys); big-block mode needed for contract deployment
- **Compute:** this Mac only for data work; GCP trial allowed but not required
- **Owner-hand items (workers build on anvil + fixtures until they land):** run the testnet deploy script; create the Square sandbox app and paste `SQUARE_SANDBOX_ACCESS_TOKEN` into `~/.config/dev/secrets.env`; owner does these when pinged (push notification only)
- **Legal:** nothing real until the counsel memo; residual auctions open to any wallet is a design choice the memo must address
- **Data:** free sources only; Open-Meteo free tier is non-commercial (do not build the product on it)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| On-chain protocol (HyperEVM) + off-chain Python simulator | "DeFi protocol" per owner; the simulator is the numerical reference and runs the evaluation on history | — Pending |
| Paper + working prototype + pitch pack as v1 "done" | VC raise + coin is the goal; evidence and demo both needed | — Pending |
| Test every residual design, let data pick | ins2 killed per-cell nClimGrid; regional factor / station pairs / PRISM untested | — Pending |
| Full engine suite in the portal (risk, margin, RFQ, hedging, onboarding, trading, coverage, elasticity) | Owner scope, 2026-09-30 | — Pending |
| Token = junior first-loss pool capital + governance | Gives the coin a cash-flow reason; VC question | — Pending |
| House market-maker seeds the pool first | Hyperliquid-style bootstrap; outside LPs after flow exists | — Pending |
| Both hedge-leg paths, house hedge default | Overlay path is the fallback if counsel objects to intermediating | — Pending |
| Residual auctions open to anyone with a wallet | Best liquidity story; legal memo carries the cost | — Pending |
| Concierge only if needed; self-serve CSV and POS-connect both built | Owner 2026-09-30 | — Pending |
| Hosted demo runs `sim` mode until testnet deploy | Owner runs deploy after the window; no UI change on flip | — Pending |
| Two decks (crypto-native, fintech/insurtech) | Owner 2026-09-30 | — Pending |
| Kalshi book recorder lives in hl-mm on AWS Tokyo, read-only | Owner: "tell it to start this process on a aws box we already have" | — Pending |
| Codename `weather-insurance` kept for protocol and coin | Owner 2026-09-30 | — Pending |
| Junior capital in USDC; WI = fixed-supply staked token cut (burned) pro rata on junior losses + governance | Phase 14 research: Aave and Maple abandoned own-token first-loss; claims must be paid in the claim's currency | — Pending |
| One scalar-unit instrument + gas-feasible clearing rule (max volume → min imbalance → midpoint; price-time at the margin) in engine and contracts | Phase 8 research: pro-rata at the margin needs a loop over orders and cannot fit a 3M-gas block; parity by fixture | — Pending |
| Engine API = FastAPI wrapping wi.engine on Vercel Python, Upstash state, testnet mode holds no keys | Phase 9 research: one engine, no drift; Vercel + Upstash logins exist on this Mac | — Pending |
| Prototype keeps open testnet auctions; memos + decks carry the legal findings; no redesign in the window | Owner ruling (testnet, counsel before mainnet); Phase 15 finds the payout is a swap unless carrier-issued | — Pending |
| Pre-registered rules before any number, HE_cover and HE_ladder always both reported | Owner practice; Phase 5 finding that 24 h asks embed the forecast | — Pending |

---
*Last updated: 2026-09-30 13:20Z after Wave A research (seat decisions added)*

## Recorder (hl-mm session, recorded 2026-09-30 14:30Z)
Kalshi weather order-book recorder LIVE on the hl-mm Tokyo box since 2026-09-30T07:49:22Z (first book row 07:49:26Z). Read-only for this project.
- Prefix: `s3://hlmm-reduced-5325/recorder/tokyo/kalshi-weather-books/{books,settlements,candles,discovery}/date=YYYY-MM-DD/` (+ `README.md`, `_status/status.json` at the prefix root). JSONL gzip, e.g. `books/date=2026-09-30/books-20260930T0745Z-b1790754563.jsonl.gz`. ~85 MB/day; hourly sync (≤ ~1 h lag).
- Rows carry `series` (ticker prefix: KXHIGHNY, KXHIGHCHI, KXHIGHMIA, KXHIGHTEWR, KXHIGHTTTN, rain/low-temp/hurricane/degree-day/snow). books: ts, t_req, srv_ts, srv_age_s, ticker, event_ticker, series, close_time, tier, book (all levels both sides as returned); cadence 60 s within 48 h of close (`tier`), else 5 min. settlements: …, status, result, settlement_ts, settlement_value_dollars, expiration_value, gave_up, market. candles: hourly via batch endpoint. discovery: series/summary/market_added/market_closed; daily 00:10Z + 30-min open-market refresh.
- Alive check (read-only, profile `hlmm-launch`): `aws s3 cp <prefix>/_status/status.json -`; newest books file < ~75 min old and `last_book_poll` within 5 min of `status.ts`.
- Nothing exists before 07:49Z 2026-09-30. Phase 2's depth tables (single books.json snapshot) are re-run in 17-03 once ≥ 14 days have accrued.

## Pitch pack links (2026-09-30)
- Hosted demo (sim): https://wi-portal.vercel.app · engine https://wi-engine.vercel.app · script reports/demo/DEMO-SCRIPT.md · walkthrough reports/pitch/DEMO-WALKTHROUGH.md
- Evaluation report: reports/EVALUATION.md (+ .html) · token memo reports/pitch/14-TOKEN-POOL-MEMO.md · legal memo reports/pitch/15-LEGAL-OPTIONS-MEMO.md
- Open placeholders: {{TEAM_LINE}} on the ask slide (owner writes it); "pending Phase 3" lines (seat fills when reports/eval-03 lands).
