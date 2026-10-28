# Phase 7: Protocol spec + reference engine - Research

**Researched:** 2026-09-30
**Domain:** Mechanism design (uniform-price call auction, two-tranche pool, full-collateral margin), parametric weather settlement (NWS CLI, nClimGrid-Daily, PRISM), Kalshi ladder replication and paper fills, deterministic Python reference engine
**Confidence:** MEDIUM overall. Data-lifecycle and Kalshi contract facts are HIGH (official docs plus the recorded 2026-09-29 market records). Mechanism choices are recommendations built on cited precedents. A few items could not be re-checked because the web tools hit a session limit near the end; those are marked LOW.

## Summary

Scope: everything plan 07-01 needs to write SPEC.md, and everything plans 07-02..07-06 need to build the engine. Phase 7 has no CONTEXT.md. The locked choices come from `.planning/OWNER-RULINGS.md` (2026-09-30) and `PROJECT.md`:
- HyperEVM testnet, and the Python engine is the numerical reference.
- Both hedge-leg paths, with the house hedge as the default.
- Residual auctions open to any wallet.
- Token = junior first-loss capital + governance. The house MM seeds the pool first.
- Paper Kalshi hedging only. Free data only. Prototype-grade, with tests only for money failures.

The residual index is not frozen until the Phase 3 verdict. So the spec keeps the index abstract (an index registry) and freezes everything else now.

The approach is to reuse proven parts and add nothing clever:
- **Auction:** a one-shot uniform-price call auction per residual contract per market day. Rules: max volume, then min imbalance. Orders at the marginal price level are rationed pro rata (Budish–Cramton–Shim frequent batch auctions). Limit orders are open on-chain, as in Gnosis EasyAuction, with a minimum order size to bound gas.
- **Pool:** a Tinlake-style waterfall. The senior claim accrues a fixed rate, and junior is whatever is left. The WI token is the junior share, minted at NAV. Add Ensuro-style solvency locks and a utilisation cap, plus a Maple/Centrifuge-style withdrawal queue.
- **Margin:** full collateral everywhere, which is how Kalshi and HIP-4 do it.
- **Oracle:** the operator signs an EIP-712 settlement report under a fixed-vintage revision rule (Kalshi precedent: settle on the first non-preliminary publication).
- **Hedge:** the ins1 replication rule, paper-filled against recorded books.
- **RFQ:** reuse the defi-options vocabulary. The maker signs a firm quote, the taker accepts it on-chain, and there is no last look.

Three findings change the spec from what the roadmap assumed:
1. **Close time.** Kalshi daily weather markets close when the NWS climate day ends, which is midnight local *standard* time. That is 05:00Z for ET stations and 06:00Z for Chicago, all year. `docs/CONVENTIONS.md` §2 says 03:59Z for ET, which is true only for the weekly and monthly rain series.
2. **Hedgeable range.** The station leg can only be hedged near the forecast. Each daily ladder has 6 rungs: an open tail on each side and four 2 °F brackets spanning 8 °F. If a fixed strike sits in the open top bracket, it has no hedge that day. Daily Kalshi rain is an indicator only (">0 in"). Chicago rain settles at O'Hare, while Chicago temperature settles at Midway.
3. **Settlement lag.** Settlement lag is what drives capital. The weather is public days before a grid value settles, so LP deposits and withdrawals must wait out that window.

**Primary recommendation:** Specify the residual as a standard capped **basis swap** on (location index − settlement-station index). It is fully collateralised as a split pot, like Kalshi YES/NO, and traded in a daily 03:00Z uniform-price auction per contract, with the pool posting a standing quote schedule. Build the engine as a pure integer-money event reducer with a hash-chained JSONL log, and emit parity vectors that the Foundry contracts must reproduce.

## Standard Stack

### Core (Python engine, `src/wi/engine/`)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| CPython | 3.14.0 (`.python-version`, `.venv`) | Runtime | Already pinned for the repo |
| stdlib `dataclasses`, `json`, `hashlib`, `itertools`, `datetime` (`timezone(timedelta(hours=-5))`) | 3.14 | State, canonical JSON, hash chain, fixed-offset LST zones | No dependency; deterministic |
| pydantic | 2.13.5 (installed) | Event/param models at the JSON boundary (`model_dump(mode="json")`) | Already a dep; strict validation of fixtures and events |
| numpy | 2.5.3 (installed) | Pricing/risk only (empirical ΔX distributions) | Already a dep; never used in money state |
| pandas | 3.0.6 (installed) | Loading Phase 1 parquet fixtures only | Already a dep |
| eth-account | 0.14.0 (NEW) | EIP-712 settlement reports and RFQ quotes (`Account.sign_typed_data`, `encode_typed_data`) | Seat-verified 2026-09-30: installs on Python 3.14, and sign/recover round-trips |
| typer | installed | `wi-engine run` CLI for the fixture end-to-end run | Already a dep |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| hypothesis | 6.168.3 (NEW, dev group) | Property tests: clearing conserves units, waterfall conserves value, caps never breached | Only for the money-failure properties listed in AGENTS.md |
| netCDF4 / xarray | installed | Oracle adapter reads nClimGrid monthly NetCDF | Reuse `prior/hl-mm-ins/scripts/ins2/extract.py` logic |
| `wi.data.iem` (in-repo, plan 01-03) | — | NWS CLI values via IEM `/json/cli.py` | CLI-based indices and fallbacks |
| `wi.data.kalshi` (in-repo, plan 01-02) | — | Candles, markets, settlement `result` | Hedge fixtures, and to read hedge payouts |
| OpenZeppelin Contracts | v5.7.0 (installed by 08-01) | `EIP712`, `ECDSA`, `Math.mulDiv` on the Solidity side | Phase 8 uses them to verify what this engine signs |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-written reducer | `eventsourcing` library | Adds aggregates/repositories/serialization machinery for a single-process replay. A ~150-line reducer is easier to make byte-deterministic. |
| Open on-chain orders | Commit–reveal sealed bids | Needs two transactions per bidder and a reveal deposit. Non-reveal griefing, and collateral size leaks the bid. Defer to v1. |
| Open on-chain orders + on-chain clearing | CoW-style off-chain signed intents + operator-computed clearing verified on-chain | The scale path once order counts exceed the gas budget. Adds a solver role and signature checks. Not needed at prototype volumes. |
| Tinlake-style waterfall (senior accrues, junior is residual) | Ensuro-style premium split (pure premium + jrCoc/srCoc paid at policy creation) | Ensuro prices capital per policy, which is more precise but needs per-policy SCR formulas. Tinlake needs one invariant and is enough for v0. |
| Full collateral | SPAN-like scenario margin | Our payouts are bounded, so full collateral costs little extra, and there are no margin calls and no liquidation engine. SPAN matters only for portfolio offsets we do not have. |

**Installation:**
```bash
uv add eth-account==0.14.0
uv add --group dev hypothesis
```

## Architecture Patterns

### Recommended Project Structure
```
src/wi/engine/
├── units.py        # scales (USDC 1e6, °F×10, in×100), tdiv (truncate toward zero), tick rounding
├── spec.py         # frozen params: PayoutType, InstrumentSpec, IndexRegistry, AuctionParams, PoolParams, OracleSources, Timeline
├── payoff.py       # integer payout functions; basis-swap split-pot settlement
├── ledger.py       # accounts, escrow, locks, treasury; conservation check
├── events.py       # pydantic event models, canonical JSON, hash chain
├── engine.py       # Engine.apply(event) reducer; snapshot()/restore(); state hash
├── auction.py      # clear(orders) -> (price, fills), pure function (see Code Examples)
├── pool.py         # tranche NAVs, waterfall, deposit/withdraw queue, epoch processing
├── margin.py       # collateral requirement per instrument; exposure caps
├── oracle.py       # source adapters (CLI, nClimGrid, PRISM), fixed-vintage policy, EIP-712 reports, vintage archive
├── hedge.py        # Kalshi replication (ins1 rule) + paper fills (book walk / candle fallback) + fees
├── pricing.py      # station-leg cost at asks, residual fair value (point-in-time), risk metrics
├── rfq.py          # request / firm quote / accept
├── house_mm.py     # quote schedule from pricing + inventory + remaining caps
└── run.py          # typer CLI: fixture end-to-end run -> var/runs/<run_id>/ + manifest
fixtures/engine/nyc-30d/      # small, committed inputs for 07-06 (ladders at T-24h, CLI values, businesses)
parity/                       # JSON vectors (orders->fills, payouts, waterfall steps) for Foundry tests
tests/engine/                 # money-failure tests only
docs/SPEC.md                  # repo-level spec (contracts + portal + engine read it)
reports/engine/e2e-nyc-30d/   # committed manifest + summary of the 07-06 run
```

### Pattern 1: Daily cycle (Q1 cadence, Q6 timing)
**What:** One fixed UTC schedule per market day D. D is the date in the Kalshi ticker, which is the NWS climate day.
**Timeline (ET stations; Chicago closes 1 h later):**

| UTC | Event |
|-----|-------|
| D−1 14:00Z | Kalshi ladder for D opens (observed on all five cities, 2026-09-29 records) |
| D−1 14:00Z → D 02:30Z | Policy purchases and any-wallet residual orders for D |
| D 02:30Z | **House cutoff**: pool/house quote schedule posted and frozen. The house is the operator and must not move last with full sight of the book. |
| D 03:00Z | **Public cutoff**; auction for every listed residual contract clears (permissionless `clear`) |
| D 05:00Z (06:00Z CHI) | House paper-hedges station legs at **T−24h** (headline). T−12h and T−2h are recorded as shadow fills for Phase 2 only. |
| D+1 05:00Z (06:00Z CHI) | Kalshi close = end of climate day (midnight LST) |
| D+1 12:00Z | Oracle fetch for CLI-based indices → signed report posted |
| D+1 ~19:00Z | Kalshi `expected_expiration_time`; hedge payout read from Kalshi `result` |
| D+2 12:00Z | CLI reports final (24 h dispute window) → positions settle |
| D+5 12:00Z / D+6 12:00Z | nClimGrid prelim fetch / final |
| D+7 12:00Z / D+8 12:00Z | PRISM fetch (after the ~5-day second model run) / final |
| Daily 12:30Z | Pool epoch: senior accrual, matured deposit/withdraw requests |

**Why 03:00Z:** it is before T−24h for every city (ET 05:00Z, CT 06:00Z). Also, 24 h before close is the start of day D in local time, so a policy bought before the cutoff has seen no part of day D's weather. A T−2h fill is not a hedge. By 03:00Z on D+1 the day's high is known, so its low price reflects certainty, not cheap cover (ins1: thin ladders are executable only near close).

### Pattern 2: Instruments (Q5)
- **Policy (house-hedge path, default).**
  - The business buys one daily payout on its location index: `n × f(X_loc)`, where f is capped-linear or digital (enum below).
  - The house splits it into a station leg `n × f(X_sta)`, paper-hedged on Kalshi, and a residual leg `n × [f(X_loc) − f(X_sta)]`.
  - The residual leg is entered in D's auction as a limit order, with quantity `h = round(n × δ)`. Here δ = P(K < X_sta ≤ K+C) is read from the ladder's mid prices at quote time. This is the first-order delta, since f(X+Δ) − f(X) ≈ 1{K<X≤K+C}·Δ.
  - The pool carries the convexity left over at strike and cap.
  - Strips are auto-renewing daily policies with a business-set max daily premium.
- **Residual basis swap (the auction-traded contract).** Per `contractId = (variable, index_a, index_b, C_r)` and day D:
  - Long receives `clamp(X_a − X_b, −C_r, +C_r)`, in dollars per unit, where 1 unit = $1 per 1.0 °F.
  - Collateral works as a split pot. Long escrows `p + C_r` and short escrows `C_r − p`. At settlement long gets `clamp + C_r` and short gets `C_r − clamp`, so each unit is `2·C_r` locked.
  - Prices are signed. The mean LGA − Central Park offset is +1.8 °F and FLL − MIA is −1.1 °F (ins1), so fair prices sit away from zero.
  - Opposite businesses land on opposite sides. A heat-hurt shop near LGA (buys heat cover) is long ΔX. A cool-hurt shop near LGA (buys cool cover) is short ΔX.
- **Rain residual:** the same contract with indicator values (X ∈ {0,1}, C_r = 1), because the only daily Kalshi rain market is "total precipitation at CLIxxx strictly greater than 0 inches".
- **Overlay-only (fallback path):** the business buys the replicating ladder at Kalshi itself (the portal shows contracts per rung), and the venue sells only the basis swap. The station leg is informational, not booked.
- **Bespoke residual (RFQ):** any index or cap not listed in the auction, with the same payout enum.
- **Regional-factor design:** if Phase 3 picks it, `index_a` = metro factor and there is one contract per station. If it picks station pairs, there is one contract per pair (LGA−NYC, JFK−NYC, …). So the auction key must be a contract id, not the `stationId` in the 08-01 `IBatchAuction` stub.

### Pattern 3: Payout enum + integer units (Q5)
| Quantity | Encoding |
|---|---|
| Money | int, USDC base units (1e6); signed where prices can be negative |
| Temperature | int, tenths of °F (CLI/Kalshi integer °F × 10; grids converted from °C and rounded half away from zero to 0.1 °F) |
| Precipitation | int, hundredths of inch; CLI "T" (trace) = 0 (to verify against Kalshi rain settlements) |
| Day | int, days since 1970-01-01 of the civil climate-day date (never a block-timestamp date) |
| Timestamps | int, Unix seconds UTC |
| Quantity | int units; 1 unit = $1 per 1.0 °F (or $1 per indicator event); MIN_QTY = 1 |
| Price tick | $0.01 per unit = 10,000 base units; band [−C_r, +C_r] |

| PayoutType | Formula (per unit, before × notional) | Use |
|---|---|---|
| `CAPPED_CALL` | `clamp(X − K, 0, C)` | Heat cover (business hurt by heat) |
| `CAPPED_PUT` | `clamp(K − X, 0, C)` | Cool cover (business hurt by cool days) |
| `DIGITAL_ABOVE` | `1{X > K}` | Rain cover (K = 0), heat trigger |
| `DIGITAL_BELOW` | `1{X ≤ K}` | Dry cover |
| `BASIS_SWAP` | `clamp(X_a − X_b, −C, C)` (long), split pot | Residual |

Payout in base units = `tdiv(notional × value_scaled, SCALE)`, where SCALE is 10 for °F and 100 for inches. **Division truncates toward zero** in both Python and Solidity (see Pitfall 1). The 08-01 `IPolicyManager.PayoutType` needs `BASIS_SWAP` added, and `Indicator` split into two directions.

### Pattern 4: Uniform-price clearing (Q1)
**Rule (reference = `auction.py`, reproduced bit-for-bit in Solidity):**
1. Evaluate every tick in [min limit, max limit], not just the limit prices. Between two limits the demand and supply steps can cross with a smaller imbalance than at either end.
2. Pick the tick with maximum executable volume `min(D(p), S(p))`. Break ties by minimum `|D(p) − S(p)|`, then by the lower median of the tied ticks. This is deterministic and needs no operator reference price.
3. Fill each side best price first. At the marginal price level, ration pro rata with integer largest-remainder, then by earliest order id. Σ long fills = Σ short fills exactly.
4. Everyone pays or receives the clearing price. Refund `limit − p` per filled unit to longs and `p − limit` to shorts, and return escrow for unfilled units.

Other rules:
- **Partial fills:** yes, by default. No all-or-none and no minimum fill in v0, because those break the simple clearing.
- **Minimum quantity:** 1 unit.
- **Max orders:** MAX_ORDERS per auction, placeholder 200. It exists to fit gas; HyperEVM small blocks are 3M gas and big blocks 30M. This is the same reason Gnosis EasyAuction has `minimumBiddingAmountPerOrder`.
- **Cancellation:** allowed until the cutoff (EasyAuction's `orderCancellationEndDate`).
- **Pool/house participation:** the house posts a small ladder of limit orders (a supply/demand schedule) by the house cutoff. A policy's residual leg is a limit order at the quoted residual price. Where it meets an opposite business, the clearing price moves toward fair value, and the pool fills less. That movement is the netting, and it can be seen in the price.
- **If the residual leg does not fill** (pool caps exhausted): the policy is downsized pro rata on both legs and the premium is refunded pro rata. This happens before the T−24h hedge, so no hedge has to be unwound.
- **Sealed vs open:** open orders in v0. Sniping near the cutoff is a documented weakness. v1 options, in order: randomised close (the Xetra-style random end of the call phase, LOW: not re-verified), commit–reveal, encrypted intents.

The house cutoff 30 min before the public cutoff is the conflict-of-interest guard. Without it the operator is always the last mover.

### Pattern 5: Pool with tranches (Q2)
Precedents, as they bear on us:

| Protocol | Premium/fee flow | Loss order | Lock-up / withdrawal | Utilisation / caps | Confidence |
|---|---|---|---|---|---|
| Ensuro | Premium = pure premium (to PremiumsAccount) + jrCoc + srCoc (to the eTokens) + Ensuro + partner commission; `purePremium = payout·lossProb·MoC`, `jrCoc = jrScr·jrRoc·Δt/yr` | Won pure premiums → borrow active premiums → junior eToken → senior eToken; repay senior first | Withdraw ≤ `totalSupply − scr·liquidityRequirement` | `maxUtilizationRate` rejects locks; SCR locked until expiry/claim | HIGH (docs) |
| Nexus Mutual | 50 % of the cover fee minted as NXM to stakers, streamed over cover period | Allocated stake burned pro rata on claims | 91-day tranches, up to 2 years; no early withdrawal (sell the staking NFT instead) | Capacity allocated per product by pool managers | HIGH (docs) |
| Centrifuge Tinlake | Senior DROP accrues a fixed rate; junior TIN gets the residual | TIN first | Epoch-based invest/redeem orders; solver maximises weighted orders; senior redemptions weighted highest | Min TIN risk buffer: DROP issuance stops when breached; max reserve | MEDIUM |
| Maple | Pool Delegate posts first-loss cover | Cover first, then LPs | Queue (FIFO as liquidity frees) or cycle windows (e.g. first days of each cycle) | — | MEDIUM |
| Ondo v1 | Senior fixed hurdle; junior gets excess | Junior first | Fixed-term vaults (deposit window → locked → redeem) | — | MEDIUM |
| Sherlock | Premiums + yield to USDC stakers | Stake slashed up to ~50 % per incident; UMA OO escalation | 6–12-month lockups | — | LOW (secondary) |
| Neptune Mutual / Risk Harbor | Parametric; LPs earn premium | Pool pays on incident resolution (Neptune: reporter staking; Risk Harbor: automated on-chain trigger) | Neptune: limited withdrawal windows, 3-month max cover | — | LOW (secondary) |

**Recommended minimal waterfall (v0):**
- **Assets and shares.** All pool assets are USDC. The senior shares are a vault token. The junior share **is WI**, minted and burned by the vault at junior NAV per share. This keeps "token = junior first-loss capital" without making claims depend on selling WI (Pitfall 11). 08-01's WIToken is owner-mintable; it needs a burn path for the vault.
- **Claims.** `senior_claim` accrues `r_s` (APR, per-second simple accrual at each epoch). `senior_nav = min(assets, senior_claim)`. `junior_nav = max(0, assets − senior_claim)`. Losses reduce `assets`, so junior absorbs them first by construction. Invariant: `senior_nav + junior_nav == assets`.
- **Income.** Everything except protocol fees goes to `assets`: net premiums, residual P&L, hedge P&L (paper transfer event), payouts out. Protocol fees go to a separate treasury account.
- **Limits.**
  - Min junior ratio `j_min` (placeholder 0.20). Senior deposits, junior withdrawals and new risk locks are rejected if they would breach it.
  - `u_max` (placeholder 0.8) on `locked / assets`.
- **Queue.** Deposits **and** withdrawals are requests. Each executes at the first daily epoch after `COOLDOWN` = max over listed sources of (fetch lag N + dispute window) + 1 day: 3 days if only CLI indices are listed, 9 if PRISM ones are. It executes at that epoch's NAV, from free capital only, senior redemptions first, junior only if `j_min` holds after. This is the known-outcome guard (Pitfall 9).
- **Seeding and wipe-out.** The house seeds junior first. Senior deposits open once junior ≥ a floor. If `junior_nav == 0`, the pool pauses new risk until an admin recap event. No share-price reset in v0.

### Pattern 6: Margin and exposure caps (Q3)
- **Full collateral, no SPAN.**
  - Basis swap: both sides escrow max loss (`C_r ± p`).
  - Policy: the pool locks `n × C` (max payout), with no credit for the off-chain Kalshi hedge in v0 (`hedge_credit = 0`). The risk engine *reports* capital needed with hedge credit as a metric for Phase 4/14.
  - Kalshi Klear requires every event contract to be fully collateralised for maximum downside exposure (CFTC filings).
- **House MM posts:** nothing separate. It trades as the pool's agent, so its auction orders escrow from pool free capital. Its own risk capital is its junior deposit. Its Kalshi paper account is a separate off-chain ledger, and P&L moves into pool `assets` by a signed `HedgeSettled` event (a trust assumption, stated in the spec).
- **Caps, checked in the reducer before any lock:**
  - Σ locked on (contract, D) ≤ α·assets
  - Σ locked on (station, D) over all contracts around that station ≤ β·assets. Residuals around one station are common-mode: ρ 0.74–0.83 (ins2). Treat them as fully correlated.
  - Σ locked on (metro, D) ≤ γ·assets. NYC/EWR/TTN share heat waves.
  - Σ locked overall ≤ u_max·assets.
  - Also: house-path station units per city-day ≤ `max_hedge_units`, read from the book at hedge time. ins1: 80–450 contracts per rung within 3c ≈ 5–20 units ≈ $30–120 max payout per city-day.
  - α/β/γ are placeholders until Phase 4.
- **Unhedged ladder tail:** for a policy with strike K, the replication covers only up to the top bracket's floor + 1. `n × (C − f(top_floor + 1))` is pool exposure, added to locks and caps.

### Pattern 7: Oracle, settlement, revision policy (Q4)
**Precedents:**
- **Kalshi** settles weather on The Weather Company's value for the NWS climate station (e.g. CLINYC). If "a material error in the initial non-preliminary publication" is found, it waits up to one week, and otherwise uses "the last fair price determined by Kalshi". Expiration is the first 7 or 8 AM ET after data release. (Recorded market rules, 2026-09-29.)
- **USDA RMA:** PRF moved from CPC to NCEI rainfall data for grid indices on 2026-08-31, citing "a consistent data release schedule" and faster final grid index values (RMA release, 2026-04-30). Parametric settlement on a named NOAA dataset with a published schedule is the accepted pattern.
- **Arbol/dClimate and Etherisc** push weather values through Chainlink oracle networks (LOW: marketing and blog sources). UMA's optimistic oracle uses asserter/disputer bonds with a default 2 h liveness (MEDIUM).

**Recommendation:**
- **Push, not fetch.** The operator key signs an EIP-712 `SettlementReport{contractOrIndexId, day, value, sourceId, vintageHash, fetchedAt, version}` and anyone may submit it. The contract checks the signer against a registered reporter. There is no on-chain HTTP on HyperEVM, and a single signed push is what Chainlink-style reports reduce to on a testnet. 08-01's `IOracleAdapter.postValue(…, nonce, sig)` should carry `sourceId`, `vintageHash` and `version` instead of a bare nonce.
- **Fixed vintage.** Settle on the value in the source as fetched at `D + N` days, 12:00Z. Ignore later revisions (the Kalshi rule). Store the vintage hash (file sha256, or the CLI product id). Disputes may only claim a transcription error (posted value ≠ the stated vintage at the stated coordinates). There is a 24 h window; the admin resolves with `version + 1`.
- **Fallback and void.** If the source has no value by `D + N_max`, use a registered fallback: grid → the nearest station's CLI. If there is none, **void**: the basis swap settles at its clearing price (each side gets its escrow back), and the policy refunds its premium.
- **Archive every vintage fetched**, so revision risk can be measured going forward. There is no nClimGrid vintage archive (ins2).

| Source | Day window | Label → calendar | First availability | N (fetch at D+N 12:00Z) |
|---|---|---|---|---|
| NWS CLI via IEM | Midnight–midnight **LST** (1 AM–1 AM local daylight in summer) | Same date | Full-day summary ~01:30 local next day | **1** |
| nClimGrid-Daily prelim | "24-hour period ending in the early morning of the specified day" | calendar D = label D+1 | 2–3 days after the observation date; prelim updated in place; "scaled" file after month end (Aug's appeared 6 days after) | **5** (prelim vintage) |
| PRISM AN daily | 1200–1200 UTC, day-ending label ("a day ending at 1200 UTC on 1 January is labeled 1 January") | calendar D (afternoon high) = label D+1 | First run ~24 h after day end, second after 5 days, then ~monthly to 6 months (8 runs); stable after 6 months | **7** (after second run; Phase 4 revision data may shorten it) |

### Pattern 8: Kalshi station leg for the house (Q6)
- **Replication (ins1 rule, generalised to any K, C, n and to puts):**
  - For each rung b, buy `q_b = n × f(v_b)` YES.
  - v_b = midpoint for "between" rungs. For the "greater" rung, v_b = floor + 1 (the ins1 convention). For the "less" rung, v_b = cap − 1 for puts (mirror convention; ins1 used `H(cap)` for calls, which pays 0 there anyway).
  - A $1/°F call with K = second-rung floor and C = 6 needs 19.5 contracts (0.5 + 2.5 + 4.5 + 6 + 6).
  - Round q_b to `CONTRACT_STEP`. Default 1 contract; recorded books show fixed-point quantities such as 34.34, but fractional trading is not confirmed (LOW).
- **Execution:** at `close_time − 24h`, using the book snapshot nearest at or before the decision time (the recorder writes every 60 s inside 48 h of close). No snapshot within 120 s → candle fallback. Record T−12h and T−2h as shadow only.
- **Paper fill (book):**
  - YES asks come from NO bids: `ask = 1 − no_price` at the same quantity. The book returns bids only (Kalshi API docs).
  - Sort explicitly. The recorded arrays are *ascending*, with the best level last, although the docs say "best to worst".
  - Walk levels while `ask ≤ best_ask + 3c` and quantity is still needed. Record VWAP and shortfall; the shortfall is carried by the pool.
  - Rung "no offer" rule: ask ≥ 99c and bid < 90c.
- **Paper fill (candles, history before the recorder):** YES ask close of the last hourly candle ending at or before the decision time. Fill up to a pre-registered cap of 5 units per city-day (the low end of ins1's depth), labelled `candle-fill`.
- **Fees:** taker fee per order = ceil to the cent of `0.07 × C × P × (1 − P)` (MEDIUM: several secondary sources agree; the official PDF could not be fetched). ins1 premiums exclude fees; the engine must include them.
- **Thin ladders (EWR/TTN, 2.4–2.7× overround at 24 h):** no house hedge on those ladders. Hedge on the metro's liquid ladder (NYC), and route the EWR/TTN−NYC basis to a residual contract. Phase 3 confirms which pair.
- **Hedge payout:** read Kalshi `result` for the rungs (TWC-settled). Never recompute it from CLI; TWC ≠ NWS on 5 of 272 ins1 days.

### Pattern 9: House-MM quoting (07-05)
- **Fair value:** fair basis-swap price for (contract, D) = E[clamp(ΔX, ±C_r)] over the trailing 60 *finalised* days at the same site, optionally the same month. Uncertainty = sample sd/√n + a model buffer.
- **Quotes:**
  - bid = fair − h − k·inventory, ask = fair + h − k·inventory
  - half-spread h = max(min_half, z·uncertainty)
  - Size at each of 3 levels is limited by remaining cap headroom ÷ worst-case loss per unit.
  - Posted by the house cutoff and frozen.
- **Policy quote:** station-leg cost (paper replication at current asks + fees + slippage buffer) + h × residual price + tail charge + policy fee. The pricing engine shows the business each component.

### Pattern 10: RFQ for bespoke residuals (Q7)
Vocabulary is from `defi-options/.planning/phases/05-venue-and-mm-design/05-HYPERLIQUID-HOSTING.md` §3:
1. **Request:** requester, payout spec (type, indices, K, C, days), quantity, side, response window. One-way in v0; the requester is a hedger with a known side (defi-options left two-way open).
2. **Responders:** the house MM first, then whitelisted makers. Each posts a *firm* EIP-712-signed `Quote{requestId, price, maxQty, validUntil, nonce}` for the window.
3. **Best price wins** at window end for the requester's side. Ties go to the earlier response.
4. **Accept:** the requester submits `acceptQuote(quote, sig, qty)` on-chain before `validUntil`. The contract verifies the signature and nonce, pulls full collateral from both sides (the responder pre-deposits a margin balance), and books the position. **No last look.** A responder cancels by bumping its nonce. This maker-signs/taker-fills pattern is common to on-chain RFQ systems (LOW: from training knowledge, not re-verified).
5. **Label:** the venue is labelled *single-responder* while only the house responds (defi-options rule).

### Pattern 11: Deterministic, replayable engine (Q8)
- **State:** state = fold(apply, events). The reducer is pure: no wall clock, no network, no unseeded randomness. Scheduler events (`Cutoff`, `Clear`, `HedgeDecision`, `OracleFetch`, `Finalize`, `Epoch`) are explicit events with UTC timestamps from the fixture timeline.
- **Event log:** JSONL of `{seq, ts, type, payload, prev}`, where `prev` = sha256 of the previous line's canonical bytes. Canonical JSON = `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`. **Integers only in money and index fields** (the reducer rejects floats). Floats are allowed only inside pricing outputs, and those are converted to ticks with explicit rounding before they become events.
- **Snapshots:** canonical state JSON at each day boundary, with its sha256. The replay test runs snapshot k + tail events and gets the same final hash as a full replay.
- **Checks:** invariants (conservation, caps, waterfall identity) are asserted inside `apply` after every event. This is the money-failure test harness; separate mirror tests are not needed.
- **Manifest (07-06 artifact):**
  - inputs (path, bytes, sha256), params hash, git sha
  - event count by type, final state hash, snapshot hashes
  - invariant results, per-day P&L CSV
  - parity vectors written for Foundry

### Anti-Patterns to Avoid
- **Keying the auction by station:** station-pair residuals put several contracts on one station. Key by contract id.
- **Floating strikes by default:** they make every business's cover a different product each day. Keep the business's K fixed, and let the replication handle whatever the ladder offers; the tail goes to the pool.
- **A separate "house wallet" book:** it would hide pool risk. The house trades as the pool's agent, and all its fills hit pool locks and caps.
- **Wall-clock time or `America/New_York` in the engine:** the climate day is fixed-offset LST. Use `timezone(timedelta(hours=-5))` for ET and `-6` for CT, or better, keep everything in UTC with per-source window tables.
- **Computing house fair value from days that settled after the auction:** that is look-ahead.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| EIP-712 struct hashing and signing | Custom keccak/abi encoding | `eth_account.Account.sign_typed_data` / `encode_typed_data` (0.14.0) | Byte-exact domain separator and type hashes that OZ `EIP712` verifies; seat-verified on Python 3.14 |
| Signature verification (Solidity) | `ecrecover` by hand | OZ `EIP712` + `ECDSA` (v5.7.0 installed) | Malleability and zero-address checks |
| Share math with rounding | `a*b/c` | OZ `Math.mulDiv(…, Rounding.Floor)`; Python `x*y//z` on non-negative ints only | Overflow; rounding direction must favour the pool on mint and redeem |
| Property tests | Random loops with asserts | `hypothesis` | Shrinking gives minimal failing books |
| NetCDF reads, day alignment | New parser | ins2 `extract.py` logic + netCDF4 | Already handles the label D+1 shift and ocean masks |
| CLI values | Scraping NWS product text | `wi.data.iem` (`/json/cli.py`) | Parsed, archived, keyless |
| Kalshi candles/markets | New client | `wi.data.kalshi` | Handles live/historical cutoff and legacy tickers |
| Event-sourcing framework | Adopting `eventsourcing` | A ~150-line reducer | Determinism and byte-stable hashes are easier without a framework (the inverse case: hand-rolling is right here) |

**Key insight:** the money paths (clearing, escrow, waterfall, payout rounding) must be the *same integer algorithm* in Python and Solidity. Parity vectors emitted by the engine, and read by Foundry through `vm.parseJson`, are how the two stay aligned, not two independent implementations.

## Common Pitfalls

### Pitfall 1: Python floor division ≠ Solidity division
**What goes wrong:** `-7 // 2 == -4` in Python, but `-7 / 2 == -3` in Solidity. Basis-swap payouts and signed prices drift by one base unit between engine and chain.
**How to avoid:** one `tdiv` helper (truncate toward zero) for every signed division in `units.py`. Parity vectors include negative cases.
**Warning signs:** parity diffs of ±1 on negative ΔX days.

### Pitfall 2: Close time and climate day
**What goes wrong:** joins keyed on 03:59Z mis-assign hedge decision times by an hour. `America/New_York` shifts the day window in summer.
**Why:** the NWS climate day is midnight–midnight local standard time all year. Kalshi daily temperature and rain markets close at 05:00Z (ET) / 06:00Z (CT) / 07:00Z (MT/Phoenix) / 08:00Z (PT) (2026-09-29 records). Weekly and monthly rain series close at 03:59Z.
**How to avoid:** read `close_time` per market. Record the deviation against CONVENTIONS.md §2 (seat to confirm on settled markets).

### Pitfall 3: Grid day labels
Both nClimGrid (documented) and PRISM (day-ending 12Z–12Z) carry calendar day D's afternoon high under label D+1. The oracle adapter must map `calendar D → label D+1` for both. ins2 measured the unaligned join at median cell HE −0.96 to −0.09.

### Pitfall 4: Kalshi order-book shape
The book has bids only: YES ask = 1 − NO bid. Recorded arrays are ascending (best last), despite the docs saying "best to worst". Quantities are fixed-point strings. Sort and parse explicitly, and assert best ask ≥ best bid.

### Pitfall 5: Fixed strike outside the ladder
The interior ladder spans only 8 °F around the forecast. A policy with K in the open top bracket gets `f(floor+1)` = 0 hedge that day, and the whole payout is pool tail. Put tail exposure in locks, caps and pricing. Report the share of policy-days with an unhedged tail as an engine metric.

### Pitfall 6: Day-ahead premium tracks the forecast
Daily cover bought at T−24h costs roughly the expected payout on a forecast-hot day. It removes forecast error, not climate risk. A fixed-price term needs the pool to carry forecast drift. This is a product decision (Open Question 1), not a bug. The spec must say which one v0 sells.

### Pitfall 7: A "hedge" near close
Thin ladders are executable only near close. By T−2h the outcome is mostly known, so such fills are measurement, not insurance. The house path must not count T−2h as a hedge.

### Pitfall 8: Settlement lag multiplies locked capital
Collateral is locked from the auction until final: about 2.5 days for CLI indices, 6.5 for nClimGrid, 8.5 for PRISM. With daily cover, that many days of positions overlap. Grid indices need about 3× the capital of CLI station pairs at the same daily size. Give this to Phase 3/4 as a cost of each design.

### Pitfall 9: LPs trading on known weather
**What goes wrong:** the weather for day D is public (CLI at D+1) days before a grid index settles. An LP can withdraw at today's NAV ahead of a known loss, or deposit ahead of a known gain.
**How to avoid:** deposits and withdrawals are both queued. Each executes at the first epoch after COOLDOWN, at that epoch's NAV. The reducer asserts that no position with market day ≤ request time is still open at execution.

### Pitfall 10: Clearing that mints or burns
**What goes wrong:** floor-only pro rata leaves Σ long ≠ Σ short. A price-improvement refund is forgotten. Fee rounding leaks base units.
**How to avoid:**
- largest-remainder allocation on the marginal level
- escrow-in == locks + refunds + fees, exactly, per auction
- hypothesis property test

### Pitfall 11: Junior capital in the protocol's own token
If junior deposits were WI, claims would force WI sales into a market falling on the same news. That is wrong-way risk, and nothing on testnet can sell it anyway. Keep junior assets in USDC, with WI as the NAV share. Phase 14 argues the token design.

### Pitfall 12: Correlated residuals treated as independent
Cell/station residuals around one station have mean pairwise correlation 0.74–0.83. A per-contract cap alone lets the pool stack one bet many times. Cap per station-day and per metro-day.

### Pitfall 13: Rebuilding the hedge payout from NWS
Kalshi settles on TWC's value for the CLI station. TWC and NWS disagree on 1.8 % of ins1 days (up to 4.4 % in Miami). Read Kalshi `result` for hedge payouts. The on-chain residual uses NWS CLI, so the TWC/NWS mismatch is a house basis, reported separately.

### Pitfall 14: Rain conventions
Kalshi says "strictly greater than 0 inches". CLI reports "T" for trace. Chicago rain is CLIORD, not CLIMDW. Define T = 0 and a per-(city, variable) station registry, and verify T = 0 against settled KXRAIN markets.

### Pitfall 15: Fee rounding on small hedges
The Kalshi fee rounds up to the cent per order. Across five rungs, that is up to 5c per hedge on policies worth a few dollars. ins1's premiums exclude fees, so do not reuse its overpay numbers as costs.

### Pitfall 16: Operator trust hidden
**What goes wrong:** the reporter key, the admin dispute resolution, the house cutoff and the paper-hedge P&L transfer are all trust in the operator.
**How to avoid:** list them in SPEC §20. Add key rotation and a pause. Testnet only (and the Phase 15 counsel memo).

### Pitfall 17: Non-deterministic serialization
Float repr, dict or set iteration order, or `datetime.now()` in the reducer each break hash equality across runs. Use canonical JSON with integers only, sorted containers and fixture clocks.

## Code Examples

### Integer units and truncating division
```python
# Source: seat design; mirrors Solidity int256 division semantics
USDC = 10**6
TICK = 10_000            # $0.01 per unit
F10 = 10                 # temperature scale: tenths of °F
IN100 = 100              # precipitation scale: hundredths of inch

def tdiv(a: int, b: int) -> int:
    """Integer division truncating toward zero (Solidity semantics). Use for ALL signed money math."""
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q

def clamp(x: int, lo: int, hi: int) -> int:
    return lo if x < lo else hi if x > hi else x
```

### Payouts (per position, base units)
```python
from enum import IntEnum

class PayoutType(IntEnum):            # order is the on-chain enum order
    CAPPED_CALL = 0; CAPPED_PUT = 1; DIGITAL_ABOVE = 2; DIGITAL_BELOW = 3; BASIS_SWAP = 4

def payout(kind: PayoutType, notional: int, x: int, k: int, cap: int, scale: int) -> int:
    """notional: base units per 1.0 index unit (or per event for digitals); x, k, cap in scaled ints."""
    if kind is PayoutType.CAPPED_CALL:   return tdiv(notional * clamp(x - k, 0, cap), scale)
    if kind is PayoutType.CAPPED_PUT:    return tdiv(notional * clamp(k - x, 0, cap), scale)
    if kind is PayoutType.DIGITAL_ABOVE: return notional if x > k else 0
    if kind is PayoutType.DIGITAL_BELOW: return notional if x <= k else 0
    raise ValueError("BASIS_SWAP settles via split_pot")

def split_pot(qty: int, xa: int, xb: int, cap_r: int, scale: int) -> tuple[int, int]:
    """Basis swap: 1 unit = $1 per 1.0 index unit. Returns (to_long, to_short) in base units; sums to 2*cap_r*qty."""
    r = clamp(xa - xb, -cap_r, cap_r)                   # scaled index units
    to_long = tdiv(qty * USDC * (r + cap_r), scale)
    return to_long, tdiv(qty * USDC * 2 * cap_r, scale) - to_long
```

### Uniform-price clearing (reference; seat-checked on 4,000 random books)
```python
# Checked in scratch 2026-09-30 for: sum long fills == sum short fills; no fill through a limit;
# price priority; no crossed leftovers. Foundry must reproduce these fills from parity vectors.
from dataclasses import dataclass
from itertools import groupby

@dataclass(frozen=True)
class Order:
    oid: int      # submission sequence
    side: str     # "B" long residual, "S" short residual
    limit: int    # signed base units per unit, multiple of TICK, within [-cap_r, +cap_r]
    qty: int      # whole units >= MIN_QTY

def _allocate(levels: list[list[Order]], vol: int) -> dict[int, int]:
    out, rem = {}, vol
    for lvl in levels:
        if rem == 0:
            break
        tot = sum(o.qty for o in lvl)
        if tot <= rem:
            out.update({o.oid: o.qty for o in lvl}); rem -= tot; continue
        base = {o.oid: o.qty * rem // tot for o in lvl}           # pro rata at the marginal level
        left = rem - sum(base.values())
        for o in sorted(lvl, key=lambda o: (-(o.qty * rem % tot), o.oid))[:left]:
            base[o.oid] += 1                                        # largest remainder, then earliest
        out.update({k: v for k, v in base.items() if v}); rem = 0
    assert rem == 0
    return out

def clear(orders: list[Order], tick: int = TICK) -> tuple[int | None, dict[int, int]]:
    if not orders:
        return None, {}
    bids = [o for o in orders if o.side == "B"]; asks = [o for o in orders if o.side == "S"]
    lo, hi = min(o.limit for o in orders), max(o.limit for o in orders)
    best, tied = (0, 0), []
    for p in range(lo, hi + tick, tick):                            # every tick, not only limit prices
        d = sum(o.qty for o in bids if o.limit >= p); s = sum(o.qty for o in asks if o.limit <= p)
        key = (min(d, s), -abs(d - s))                              # max volume, then min imbalance
        if key > best: best, tied = key, [p]
        elif key == best and key[0] > 0: tied.append(p)
    if best[0] == 0:
        return None, {}
    p = tied[(len(tied) - 1) // 2]                                  # lower median of tied ticks
    lv = lambda os, rev: [list(g) for _, g in groupby(sorted(os, key=lambda o: o.limit, reverse=rev), key=lambda o: o.limit)]
    fills = _allocate(lv([o for o in bids if o.limit >= p], True), best[0])
    fills |= _allocate(lv([o for o in asks if o.limit <= p], False), best[0])
    return p, fills
```
Escrow accounting around `clear`:
- Long escrow per unit = `limit + cap_r`; short = `cap_r − limit`.
- After clearing, lock `2·cap_r` per filled unit.
- Refund `(limit − p)` per filled long unit and `(p − limit)` per filled short unit, plus the full escrow of unfilled units.
- Assert `escrow_in == locked + refunds + fees`.

### Tranche waterfall (Tinlake-style)
```python
from dataclasses import dataclass
YEAR = 31_536_000

@dataclass
class Pool:
    assets: int = 0          # USDC base units held (free + locked)
    senior_claim: int = 0    # senior principal + accrued coupon
    senior_shares: int = 0
    junior_shares: int = 0   # == WI supply minted by the vault
    locked: int = 0

    def senior_nav(self) -> int: return min(self.assets, self.senior_claim)
    def junior_nav(self) -> int: return max(0, self.assets - self.senior_claim)

    def accrue(self, seconds: int, rate_ppm: int) -> None:     # simple accrual per epoch; junior pays it implicitly
        self.senior_claim += self.senior_claim * rate_ppm * seconds // (1_000_000 * YEAR)

    def book_pnl(self, pnl: int) -> None:                      # losses hit junior first by construction
        self.assets += pnl
        assert self.senior_nav() + self.junior_nav() == self.assets or self.assets < 0

    def deposit_junior(self, amt: int) -> int:                 # executes at epoch NAV (after COOLDOWN)
        nav = self.junior_nav()
        assert self.junior_shares == 0 or nav > 0, "junior wiped: pool paused until recap"
        minted = amt if self.junior_shares == 0 else amt * self.junior_shares // nav   # floor favours the pool
        self.assets += amt; self.junior_shares += minted
        return minted
```

### Paper fill against a recorded Kalshi book
```python
def yes_asks(orderbook_fp: dict) -> list[tuple[int, int]]:
    """Kalshi returns bids only; YES ask = 1 - NO bid. Returns [(ask_cents, qty_centi)] best first."""
    lv = [(100 - round(float(p) * 100), round(float(q) * 100)) for p, q in (orderbook_fp.get("no_dollars") or [])]
    return sorted(lv)                               # recorded arrays are ascending by NO price: sort, never trust order

def fill(asks: list[tuple[int, int]], need_centi: int, slip_cents: int = 3):
    if not asks:
        return 0, 0, 0
    best, got, cost, fee = asks[0][0], 0, 0, 0
    for px, q in asks:
        if px > best + slip_cents or got >= need_centi:
            break
        take = min(q, need_centi - got)
        got += take; cost += take * px
        fee += -(-7 * take * px * (100 - px) // 1_000_000)   # ceil(0.07*C*P*(1-P)) cents; C in centi-contracts (MEDIUM: verify schedule)
    return got, cost, fee                           # need_centi - got = shortfall carried by the pool
```
The fee line is per level and illustrative. Kalshi rounds per order, so the engine should compute one rounded fee per rung order, after checking the fee schedule.

### EIP-712 settlement report (seat-verified on Python 3.14, eth-account 0.14.0)
```python
from eth_account import Account
from eth_account.messages import encode_typed_data

DOMAIN = {"name": "weather-insurance", "version": "0", "chainId": 998, "verifyingContract": "0x..."}  # 998 = HyperEVM testnet per 08-01 (verify)
TYPES = {"SettlementReport": [
    {"name": "indexId", "type": "bytes32"}, {"name": "day", "type": "uint32"},
    {"name": "value", "type": "int32"}, {"name": "sourceId", "type": "uint8"},
    {"name": "vintageHash", "type": "bytes32"}, {"name": "fetchedAt", "type": "uint64"},
    {"name": "version", "type": "uint16"}]}

signed = Account.sign_typed_data(reporter_key, DOMAIN, TYPES, report)
assert Account.recover_message(encode_typed_data(DOMAIN, TYPES, report), signature=signed.signature) == reporter_address
```

### Hash-chained event log
```python
import hashlib, json

def canon(obj) -> bytes:
    def no_floats(o):
        if isinstance(o, float): raise TypeError("float in event; convert to scaled int first")
        if isinstance(o, dict): [no_floats(v) for v in o.values()]
        if isinstance(o, list): [no_floats(v) for v in o]
    no_floats(obj)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()

def append(log: list[dict], ts: int, etype: str, payload: dict) -> dict:
    prev = hashlib.sha256(canon(log[-1])).hexdigest() if log else "0" * 64
    ev = {"seq": len(log), "ts": ts, "type": etype, "payload": payload, "prev": prev}
    log.append(ev)
    return ev
```

## Verification rules for 07-06 (written before any run)

These are correctness gates for a fixture run, not evaluation numbers. The run's P&L is labelled "engine demo" and is never quoted as evidence.

1. **Determinism:** two runs with the same inputs give an identical final state hash and manifest, apart from the wall-clock fields.
2. **Replay:** snapshot at day 15 + tail events gives the same final hash as the full replay.
3. **Conservation:** after every event, Σ wallet balances + Σ escrow + pool assets + treasury == USDC minted by the fixture faucet, exactly.
4. **Auction:** per auction, Σ long fills == Σ short fills. No fill goes through its limit. `escrow_in == locked + refunds + fees`.
5. **Waterfall:** `senior_nav + junior_nav == assets`. Senior NAV never falls while junior NAV > 0.
6. **Caps:** no event leaves any α/β/γ/u_max cap breached, or `j_min` breached by a voluntary action.
7. **Oracle:** every settlement uses a report whose vintage `fetchedAt` ≥ D+N 12:00Z. Nothing settles before finalisation. All timestamps are UTC ints.
8. **Hedge:** no paper fill exceeds recorded depth. No book snapshot or candle is later than the decision time.
9. **Fixture:** NYC metro, 30 market days inside 2026-07-24..09-28. The station is CLINYC; the residual contracts are LGA−NYC and JFK−NYC on CLI (the Phase 3 winner swaps in later). There are 4 synthetic businesses (heat-hurt and cool-hurt at each of LGA and JFK), 1 house-seeded junior deposit, 1 senior LP, and 1 any-wallet trader with seeded random orders.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| CoW single-winner batch auction | Fair combinatorial auction (CIP-67): multiple solver bids, fairness filter, uniform *directional* clearing prices | 2025 | The uniform-price-per-direction idea still holds. Our single-contract auction is the degenerate case. |
| USDA PRF on NOAA CPC grids | PRF on NCEI data, same grids | Announced 2026-04-30; PRF switch 2026-08-31 | Strong precedent for settling parametric cover on an NCEI product with a release schedule |
| Kalshi weather settled on NWS | Settled on The Weather Company's value for the NWS climate station | Seen in 2026-09-29 rules | The station leg's truth is TWC. The residual's is NWS CLI, and the mismatch is house basis. |
| Kalshi integer contracts | Fixed-point (`_fp`) quantities in books and fields | Seen in 2026-09 data | Paper fills must parse fixed-point. Fractional *trading* is unconfirmed (LOW). |
| PRISM daily behind a paywall at 800 m | 800 m time series free since 2025-03-27; format and availability changes 2025-10-01 | 2025 | PRISM stays a free candidate index; check the post-2025 file layout in 01-04 |

**Deprecated/outdated:**
- CONVENTIONS.md "ET markets close 03:59Z": true only for weekly/monthly rain series; daily markets close at 05:00Z. Needs a dated deviation.
- ins1 premiums as cost estimates: they exclude Kalshi fees.

## Open Questions

1. **Floating day-ahead cover vs fixed-price term (owner ruling needed).**
   - What we know: Kalshi only hedges the last ~39 h, and day-ahead premiums track the forecast.
   - What's unclear: whether small businesses value cover that removes forecast error. That is exactly the loss for staffing and inventory set the day before.
   - Recommendation: v0 sells floating daily cover with a max daily premium. The pricing engine also displays a climatology-priced fixed term as a quote only. Ask the owner in one clickable question before 07-01 freezes §5.
2. **Residual index and cap C_r.**
   - What we know: ins2 killed per-cell nClimGrid, and Phase 3 picks among regional factor, station pairs and PRISM.
   - Recommendation: the spec keeps an index registry. Set C_r = 6 °F (the policy cap) as a placeholder, and let Phase 3/4 replace it with a high percentile of |ΔX|.
3. **Revision N for grids.**
   - What we know: there is no vintage archive for nClimGrid. PRISM re-runs at +5 days and then monthly.
   - Recommendation: use N = 5 / 7 from published schedules, archive every fetch, and let Phase 4/17 measure bin changes going forward.
4. **Kalshi fee schedule and fractional contracts.** The official fee PDF could not be fetched (HTTP 429 / HTML). Confirm the 0.07·P·(1−P) taker formula, per-order rounding, and whether fractional contracts trade.
5. **Gas bound for on-chain clearing.**
   - What we know: tick-grid clearing over ≤1,201 ticks plus ≤200 orders should fit a 30M big block. Fit in a 3M small block is unmeasured.
   - Recommendation: Phase 8 measures it. If it does not fit, split clearing into a price-computation call and paged fill calls (EasyAuction also allows multi-block price calculation).
6. **CLI coverage for nearby stations.** NWS OKX issues CLI for LGA and JFK (MEDIUM). Check that IEM `/json/cli.py` has LGA, JFK, FLL, ORD and whichever pairs Phase 3 picks, over the fixture window.
7. **Trace precipitation.** Check T = 0 against settled KXRAIN markets on trace days.
8. **No CONTEXT.md.** Owner memory says every phase is discussed before planning, but this project runs in YOLO mode with gates off. The seat decides whether Open Question 1 goes to the owner.

## Proposed SPEC.md outline (for plan 07-01)

Location: `docs/SPEC.md`. Each heading has a one-line content brief.

0. **Status and scope:** v0, testnet plus paper hedging only; what v0 excludes (mainnet, real Kalshi orders, sensor oracles, per-zip bespoke warehousing).
1. **Roles:** business, house operator, house MM (pool agent), senior LP, junior LP (WI holder), any-wallet trader, RFQ responder, reporter, disputer, admin.
2. **Units, encodings, rounding:** USDC 1e6 ints, °F×10, in×100, day = days since epoch of the climate-day date, UTC seconds, truncate toward zero, $0.01 tick, MIN_QTY.
3. **Calendar and daily cycle:** climate-day windows per source (LST, 12Z–12Z, label D+1). UTC table of open, house cutoff, public cutoff, hedge, close, fetch, finalise, epoch.
4. **Index registry and data sources:** index ids (CLI station, nClimGrid/PRISM cell, regional factor, station pair), the station per (city, variable) (CHI temp MDW, rain ORD), fallbacks, and the Phase 3 slot.
5. **Instruments:** Policy (house path, strip, max daily premium); Residual basis swap; Overlay-only policy; Bespoke residual (RFQ). How a policy decomposes into legs, and delta sizing of the residual leg.
6. **Payout functions:** enum `CAPPED_CALL | CAPPED_PUT | DIGITAL_ABOVE | DIGITAL_BELOW | BASIS_SWAP`, parameters, exact integer formulas, strictness (>, ≤), split-pot settlement.
7. **Pricing and quotes:** policy premium components (station leg at asks + Kalshi fees + slippage, residual price, tail charge, policy fee). Point-in-time fair value for basis swaps. What the portal shows.
8. **Residual batch auction:** key = (contractId, day), order fields, price band, escrow, cancellation, house cutoff, public cutoff. Clearing: max volume → min imbalance → lower median. Pro-rata marginal rationing, refunds, fees, MAX_ORDERS. Downsizing of unfilled policy legs. Published results.
9. **RFQ:** request fields, responder whitelist, EIP-712 Quote, response window, selection and tie rule, on-chain accept, no last look, collateral, single-responder label.
10. **Margin and exposure limits:** full-collateral table per instrument, policy locks (n×C, hedge_credit = 0), unhedged tail locks, α/β/γ/u_max caps, max_hedge_units, what the house posts.
11. **Pool and tranches:** USDC assets, senior claim accrual, junior residual with WI minted at NAV, identity invariant, j_min, deposit/withdraw queue with COOLDOWN and epoch NAV, senior-first redemptions, junior wipe-out pause, house seeding order.
12. **Fees and money flows:** policy fee, auction/RFQ per-unit fee, treasury vs pool, hedge P&L transfer, flow diagram of each dollar.
13. **House hedge on Kalshi (paper):** replication rule (calls, puts, open-bracket conventions), T−24h decision, book walk and candle fallback, 3c slippage, no-offer rule, fees, thin-ladder rule, shortfall and tail to pool, read-only guarantee.
14. **Oracle, settlement, revision policy:** SettlementReport EIP-712 type, reporter registration and rotation, fixed-vintage rule with N per source, 24 h transcription-only disputes, fallback, void, vintage archive.
15. **Settlement mechanics:** order of operations at finalise (positions → pool P&L → waterfall → claims), hedge settlement from Kalshi `result`, void handling.
16. **Hedge-leg paths:** house path vs overlay path, per-policy switch, what changes on-chain and off-chain, portal consequences.
17. **Chain mapping:** PolicyManager, BatchAuction, PoolVault, OracleAdapter, RFQ settlement, MockUSDC, WIToken (vault mint and burn). Events. Gas bounds (3M small, 30M big blocks). Required changes to the 08-01 stubs.
18. **Engine mapping and event log:** event types, state, reducer invariants, snapshots, manifest, parity vectors for Foundry.
19. **Parameters:** every parameter with v0 value or placeholder and its owner (Phase 3: index, C_r; Phase 4: α/β/γ, spreads; Phase 14: fees, r_s, j_min).
20. **Trust assumptions and known weaknesses:** operator reporter key, admin dispute resolution, paper-hedge transfer, open-book sniping, single responder, house as quoter, counsel items (Phase 15).
21. **Change log.**

## Sources

### Primary (HIGH confidence)
- Recorded Kalshi market records `prior/hl-mm-ins/reports/ins1/open-weather-markets-2026-09-29.json`: rules_primary/secondary (TWC source, material-error hold, last fair price), open/close/expiration times, rain series stations, ladder structure. Seat-read 2026-09-30.
- `prior/hl-mm-ins/reports/ins1/{README.md,analyze.py,books.json,rows.json}` and `reports/ins2/README.md`: replication rule, HE/overround, depth, geography, residual correlation, day alignment.
- [Kalshi API: Get Market Orderbook](https://docs.kalshi.com/api-reference/market/get-market-orderbook): bids only, YES ask = 1 − NO bid, keyless.
- [HyperEVM dual-block architecture](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/hyperevm/dual-block-architecture): 1 s / 3M gas, 1 min / 30M gas, `evmUserModify`.
- [PRISM dataset descriptions (PDF)](https://prism.oregonstate.edu/documents/PRISM_datasets.pdf): 1200–1200 UTC day, day-ending label convention.
- [NCEI nClimGrid-Daily](https://www.ncei.noaa.gov/products/land-based-station/nclimgrid-daily): prelim 2–3 days after the observation date, monthly consistency ~4th of the next month. Local `ncdd-2026MM-version.txt` files.
- [NWS Chicago observations/climate FAQ](https://www.weather.gov/lot/weather_observations_faq): climate day midnight–midnight LST.
- [USDA RMA release 2026-04-30](https://www.rma.usda.gov/print/pdf/node/7850): CPC → NCEI for PRF (2026-08-31).
- Ensuro docs: [Policy formulas](https://docs.ensuro.co/ensuro-docs/smart-contracts/policy), [Premiums Accounts](https://docs.ensuro.co/ensuro-docs/smart-contracts/premiums-accounts.md), [Liquidity pools](https://docs.ensuro.co/ensuro-docs/smart-contracts/liquidity-pools.md), [Policy lifecycle](https://docs.ensuro.co/ensuro-docs/smart-contracts/policy-lifecycle.md), [Pools overview](https://docs.ensuro.co/ensuro-docs/liquidity-providers/ensuros-pools-overview).
- [Nexus Mutual staking](https://docs.nexusmutual.io/protocol/staking/).
- CoW: [Fair combinatorial auction](https://docs.cow.fi/cow-protocol/concepts/introduction/fair-combinatorial-auction), [Batch auctions](https://docs.cow.fi/cow-protocol/concepts/introduction/batch-auctions), [Competition rules](https://docs.cow.fi/cow-protocol/reference/core/auctions/competition-rules), [CIP-67](https://forum.cow.fi/t/cip-67-moving-from-batch-auction-to-the-fair-combinatorial-auction/2967).
- [Gnosis Auction / EasyAuction (ido-contracts)](https://github.com/gnosis/ido-contracts).
- Budish, Cramton, Shim: [QJE paper](https://www.cramton.umd.edu/papers2015-2019/budish-cramton-shim-hft-frequent-batch-auctions.pdf), [AER P&P implementation details](https://www.aeaweb.org/articles?id=10.1257/aer.104.5.418), [CFTC TAC slides](https://www.cftc.gov/sites/default/files/idc/groups/public/@newsroom/documents/file/tac021014_budish.pdf).
- eth-account 0.14.0 EIP-712 sign/recover: seat-verified in a scratch venv on Python 3.14, 2026-09-30.
- Clearing algorithm: seat-verified in scratch against 4,000 random books (unit conservation, limits, price priority, no crossed leftovers).
- defi-options `05-HYPERLIQUID-HOSTING.md` §3 (RFQ flow, no last look, single-responder label), read-only.

### Secondary (MEDIUM confidence)
- Maple [WithdrawalManager Queue](https://docs.maple.finance/technical-resources/withdrawal-managers/withdrawal-manager-queue), [Withdrawal process](https://docs.maple.finance/maple-for-lenders/withdrawal-process).
- Centrifuge [Tinlake tranches](https://developer.centrifuge.io/tinlake/overview/tranches/), [Epochs](https://docs.centrifuge.io/learn/epoch/).
- Ondo [V1 vaults](https://docs.ondo.finance/ondo-v1-vaults-laas), [ondo-v1 Developer.md](https://github.com/ondoprotocol/ondo-v1/blob/main/Developer.md).
- Kalshi fee formula: [marketmath](https://marketmath.io/platforms/kalshi), [pm.wiki](https://pm.wiki/learn/kalshi-fees-explained), [whirligigbear](https://whirligigbear.substack.com/p/makertaker-math-on-kalshi); official [fee schedule PDF](https://kalshi.com/docs/kalshi-fee-schedule.pdf) not retrievable.
- Kalshi Klear full collateralisation: [CFTC rule filing](https://www.cftc.gov/sites/default/files/filings/orgrules/25/07/rules07042525566.pdf).
- UMA OOv3 liveness/bonds: [docs](https://docs.uma.xyz/developers/setting-custom-bond-and-liveness-parameters).
- PRISM model-run schedule (first run ~24 h, second after 5 days, then monthly to 6 months): PRISM pages summarised by search ([6-month page](https://prism.oregonstate.edu/6month/), [calendar](https://prism.oregonstate.edu/calendar/)).
- Commit–reveal drawbacks: [arXiv 2606.14939](https://arxiv.org/html/2606.14939), [a16z sealed-bid post](https://a16zcrypto.com/posts/article/hidden-in-plain-sight-a-sneaky-solidity-implementation-of-a-sealed-bid-auction/).
- IEM CLI table: [clitable](https://mesonet.agron.iastate.edu/nws/clitable.php?opt=bydate&year=2026&month=04&day=01); `wi.data.iem` docstring (1 AM–1 AM DST summaries).

### Tertiary (LOW confidence)
- Sherlock ([medium](https://medium.com/@jamesowen.dev/sherlock-the-protocol-revolutionizing-web3-audits-and-smart-contract-coverage-8b1aae43c5e4), [OpenCover](https://opencover.com/sherlock/)), Neptune Mutual ([capital pooling risks](https://neptunemutual.com/docs/capital-pooling-risks/)), Risk Harbor ([Pantera](https://blog.panteracapital.com/investing-in-risk-harbor-faf0e88a0ffa), [CoinDesk](https://www.coindesk.com/tech/2021/06/24/defi-insurance-upstart-risk-harbor-goes-live-with-325m-in-seed-funding)).
- Arbol/dClimate + Chainlink ([Arbol post](https://www.arbol.io/post/businesses-and-farmers-can-now-hedge-weather-risk-through-the-arbol-platform-and-chainlink-data)), Etherisc/ACRE ([Etherisc blog](https://blog.etherisc.com/next-exciting-chapter-for-etherisc-acre-africa-crop-insurance-is-now-on-celo-blockchain-46b555422eac)).
- Xetra-style auction tie-breaks and random end of call phase; maker-signed RFQ quote pattern (0x/Hashflow style): training knowledge. Not re-verified because the web session limit was hit.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH. Existing deps plus eth-account/hypothesis, both checked on PyPI and eth-account run on 3.14.
- Architecture (auction, pool, margin, RFQ): MEDIUM. Each piece copies a cited precedent. The combination and the parameter placeholders are our design. The clearing code is property-checked.
- Oracle and revision facts: HIGH for day definitions and first-availability. MEDIUM for PRISM re-run timing. Chosen N values are policy, pending Phase 4.
- Kalshi hedge: HIGH for book shape, close times and rules. MEDIUM for fees. LOW for fractional contracts.
- Pitfalls: HIGH for 1–5, 9–13 and 17 (verified or derived from local data). MEDIUM for the rest.

**Research date:** 2026-09-30
**Valid until:** 2026-10-14. The fast-moving parts are the Kalshi rules and fees, the recorder schema from hl-mm, and the Phase 3 verdict, which replaces the index placeholders.
