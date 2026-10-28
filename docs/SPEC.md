# weather-insurance protocol spec (v0)

Status: **frozen for build**, 2026-09-30 (plan 07-01). Engine (07-02..06), contracts (08-02..05), API (09-02..05) and portal (10–11) build from this file. Locked inputs: `.planning/phases/07-protocol-spec-engine/07-CONTEXT.md` (wins over the research files), OWNER-RULINGS.md. Every choice made here beyond 07-CONTEXT is listed in `07-01-SUMMARY.md`. A change to anything below is a dated entry in §18, never a silent edit.

## 0. Status and scope

- v0 = HyperEVM **testnet** + anvil + the in-process `sim` chain, with **paper** Kalshi hedging. No mainnet, no real money, no real Kalshi orders, no keys held by agents.
- The Python engine (`src/wi/engine`) is the numerical reference. Solidity must reproduce its integer results exactly on the parity fixtures (§14).
- Out of scope in v0: sensor oracles, per-zip bespoke warehousing, native HyperCore markets, cancels of auction orders, sealed bids, hedge credit in margin, staker income, outside junior depositors, upgradeable contracts.
- Prototype-only choices (must be revisited before anything real): open auctions to any wallet; one operator key set (reporter, quoter, house); paper hedge P&L carried into the pool by the house (trust, §8.6); MockUSDC with an open faucet; void refunds decided by one reporter window.
- `src/wi/engine` must not import pandas / xarray / netCDF4 / pyarrow / matplotlib at module level (API bundle size). Data loading lives in `wi.data`.
- Portal and API copy never calls the product "insurance" (§16). "weather-insurance" is a codename.

**Trust assumptions (all operator trust, all stated in the portal's "how it works"):** T1 the reporter key signs index values; T2 the quoter key signs policy prices; T3 the house executes paper hedges and returns their proceeds to the pool (bounded by cap C1 and the write-off rule, §8.6), and picks which of its residual-leg orders binds each policy (§6.3); T4 the owner registers indices, sets parameters and can pause new risk (never exits); T5 the house cutoff is 30 min before the public cutoff so the operator never moves last.

## 1. Units and encodings

| Quantity | Engine / chain type | Scale / rule | Wire (API) |
|---|---|---|---|
| Money | int / `uint128` (`int256` where signed) | USDC base units, 1 USDC = 1_000_000 (`UNIT`) | `…E6` int |
| Scalar-unit quantity | int / `uint128` | whole units; 1 unit pays at most `UNIT` | `qty` int |
| Price | int / `uint8` tick | tick t ∈ 1..99 = t cents per unit = t × 10_000 base units (`TICK`) | `tick` + `priceE6` |
| Temperature index | int / `int64` | tenths of °F. CLI integer °F × 10. Grid °C → `round_half_away(C×18 + 320)` | `…TenthsF` |
| Precipitation index | int / `int64` | hundredths of inch. CLI "T" (trace) = 0. mm → `round_half_away(mm×100/25.4)` | `…HundredthsIn` |
| Indicator index | int / `int64` | −1, 0, 1 (scale 1) | int |
| Basis index | int / `int64` | same scale as its components (a − b) | int |
| Day | int / `uint32` | epoch day of the **climate-day date** = (date − 1970-01-01).days. Never derived from a block timestamp | `YYYY-MM-DD` |
| Timestamp | int / `uint64` | Unix seconds UTC | ISO-8601 `Z` |
| Rates | int | bps (1e4 = 100 %); probabilities ppm (1e6 = 1) | int |
| Kalshi quantity | int | centi-contracts (1 contract = 100) | int |
| Kalshi price | int | cents | int |
| indexId | `bytes32` | `keccak256(utf8(name))`, name = `<SOURCE>:<SITE>:<VAR>:v<n>` (§3) | `0x…` + name |
| marketId | `bytes32` | `keccak256(abi.encode(bytes32 indexId, uint32 day, int64 lo, int64 hi))` | `0x…` |

Rounding rules (the only ones allowed; all in `wi.engine.units`):
- `tdiv(a, b)`: signed division truncating toward zero (= Solidity `/`). Python `//` floors and differs on negatives; it is banned on anything that can be negative.
- `mul_div(a, b, c)` = floor(a·b/c), non-negative only (= OZ `Math.mulDiv` Floor). Share mint and redeem use it, so rounding favours the pool.
- `round_half_away(a, b)`: nearest, halves away from zero. Used for unit conversions, hedge sizing and implied-price display only, never on a money transfer.
- `bps(a, r)` = `mul_div(a, r, 10⁴)` for every rate applied to money.
- `ceil_div`: Kalshi fees only.
- Floats never enter money, index values, events or state. Pricing may use floats internally and must convert to ticks/ints with an explicit rule before emitting an event.

## 2. Markets and the scalar unit

A **market** is `(indexId, day, lo, hi)` with `lo < hi` in the index's own scale. One **scalar unit** is fully collateralised by exactly `UNIT`:

```
L(x) = 0                               if x <= lo
     = UNIT                            if x >= hi
     = tdiv((x - lo) * UNIT, hi - lo)  otherwise          # quotient > 0, so tdiv == floor here
long  receives  qty * L(x)
short receives  qty * (UNIT - L(x))
```
Long + short = `qty × UNIT` exactly; the one floor sends at most 1 base unit per unit to the short side. There is no other rounding sink. `L` is `units.L`; Solidity `lib/Payoff.sol` must be the same expression.

Implied index from a price (display only): `tick_to_index(t) = round_half_away(lo·100 + t·(hi − lo), 100)`. For a basis market `[−R, +R]` that is the signed basis price `−R + t·2R/100`.

| Payout family (business view) | Market | Business side | Max payout |
|---|---|---|---|
| CAPPED_CALL(K, C): `clamp(X − K, 0, C)` per $/°F | `[K, K+C]` | long | units × UNIT |
| CAPPED_PUT(K, C): `clamp(K − X, 0, C)` | `[K−C, K]` | short | units × UNIT |
| DIGITAL_ABOVE(K): `1{X > K}` | `[K, K+1]` | long | units × UNIT |
| DIGITAL_BELOW(K): `1{X ≤ K}` | `[K, K+1]` | short | units × UNIT |
| BASIS_SWAP(±R) on `index_a − index_b` | `[−R, +R]` on the basis index | long = gains when a > b | units × UNIT |

Business-facing conversion: `units = dollarsPerDegF × C_F` (C in whole °F), i.e. `units = N_E6 × C_tenths / (10 × UNIT)`; units must be a positive integer. `DIGITAL_*` strictness comes from the integer grid: on a tenths index, `x ≥ K+1` ⇔ `x > K`.

### Worked examples (all verified with `wi.engine.units`)

**(a) $1/°F heat call, K = 88 °F, C = 6 °F at NYC (Central Park).** Market `(CLI:NYC:TMAX:v1, D, 880, 940)`, buyer long 6 units, max payout 6,000,000.

| CLI high | x | L(x) | payout = 6·L |
|---|---|---|---|
| 87 °F | 870 | 0 | 0 |
| 89 °F | 890 | 166,666 | 999,996 |
| 91 °F | 910 | 500,000 | 3,000,000 |
| 93 °F | 930 | 833,333 | 4,999,998 |
| ≥ 94 °F | ≥ 940 | 1,000,000 | 6,000,000 |

The 4-base-unit shortfall at 89 °F is the floor dust; it stays with the pool (the short side).

**(b) $2/°F cool cover, K = 70 °F, C = 5 °F at NYC.** CAPPED_PUT → market `(CLI:NYC:TMAX:v1, D, 650, 700)`, buyer **short** 10 units. High 67 °F: L = tdiv(20·10⁶, 50) = 400,000; buyer gets 10 × 600,000 = 6,000,000 = 2 × (70 − 67) dollars.

**(c) Rain digital, $50 if LGA records any rain.** Market `(CLI:LGA:PRCP:v1, D, 0, 1)`, buyer long 50 units. x = 0 (none or trace) → 0; x ≥ 1 hundredth → 50,000,000.

**(d) ±5 °F residual basis unit, LGA − Central Park.** Index `PAIR:LGA-NYC:TMAX:v1` (value = x_LGA − x_NYC, tenths), market `[−50, +50]`. Tick 68 ↔ implied basis `−50 + 68·100/100 = +18` = +1.8 °F. If the realised basis is +3.0 °F (x = 30): L = tdiv(80·10⁶, 100) = 800,000 → each long unit gets $0.80, each short $0.20. If x = −70 (−7 °F) → clamped, long 0, short $1. One basis unit carries $1/(2R_F) = $0.10 per °F of basis; $1/°F of basis exposure = 2R_F = 10 units.

## 3. Index registry

Every settleable index is registered once (engine `IndexRegistered`, chain `OracleAdapter.registerIndex`) before any market references it. Registry fields: `name`, `indexId = keccak256(name)`, `kind`, `variable`, `scale` (10 / 100 / 1), `station` (settlement station for cap grouping), `metro`, `inputs[]` (source station ids), `quorumBps`, `fetchLag`, `disputeWindow`, `voidGrace` (seconds, §9), `version`, `listedDay`. Station lists and weights never change during a live market; a change is a new `v<n>`.

| Kind | Name pattern | Value on climate day D | Source |
|---|---|---|---|
| CLI station | `CLI:<SITE>:TMAX:v1`, `CLI:<SITE>:PRCP:v1` | NWS CLI daily max (°F×10) or precip (in×100, T = 0) for midnight–midnight LST | IEM `/json/cli.py` (`wi.data.iem`) |
| Station pair (P-A; the v0 auction listing) | `PAIR:<A>-<S>:TMAX:v1` | `x_A − x_S`, both CLI | as above; both required |
| Metro mean | `METRO:<MKT>:TMAX:v1` | `round_half_away(Σ x_i, n)` over available listed inputs (tenths), inputs incl. S | CLI where issued, else GHCN-D TMAX (USW id) |
| Regional factor (R-A) | `RA:<MKT>:TMAX:v1` | `METRO:<MKT>` value − `x_S` | as above |
| Rain indicator basis | `RAIN:<A>-<S>:IND:v1` | `1{p_A ≥ 1} − 1{p_S ≥ 1}` ∈ {−1, 0, 1} | CLI precip |
| Wet-day indicator (rain cover) | `CLI:<S>:WET:v1` | 1 if the CLI daily precip at the Kalshi rain station S is ≥ 0.01 in, else 0 (a trace is 0) (scale 1); the rain cover is the `[0, 1]` market on it, business long (§18, 13-RAIN) | CLI precip (S = CLINYC, CLIORD, CLIMIA) |
| Inverse-distance blend (P-A-IDW) | `IDW:<B>-<S>:TMAX:v1` (indicative) | `round_half_away(Σ w_j x_j, Σ w_j) − x_S` over the three nearest listed ASOS CLI stations to the business point B (w_j ∝ d⁻², Phase 3 `residual-spec.md`); the RFQ reference for heat residuals | as above; no engine or contract kind in v0, so this row is the spec only |
| Weekly PRISM cell spread (G1-P) | `PRISM:<cell_B>-<cell_S>:PRCP7:v1` (indicative) | weekly precipitation at the local PRISM cell minus the cell of settlement station S; count-2 snapshot at T+5, void if a day is missing (Phase 3 `residual-spec.md`); the rain residual | PRISM; no engine or contract kind in v0 |
| Grid (reserved) | `NCG:<cell>:TMAX:v1`, `PRISM:<cell>:TMAX:v1` | calendar D = grid label D+1 | nClimGrid / PRISM; registered only if Phase 3 selects a grid design |

Settlement stations per (city, variable): NYC temp + rain CLINYC (Central Park); EWR temp CLIEWR; TTN temp CLITTN; **Chicago temp CLIMDW (Midway), Chicago rain CLIORD (O'Hare)**; MIA temp + rain CLIMIA. Registered v0 candidates (07-CONTEXT §8): R-A for each of the five markets with the Phase 3 networks (03-RESEARCH Q5 lists, S included) and P-A pairs `LGA-NYC`, `JFK-NYC`, `EWR-NYC`, `TTN-NYC` (the thin-ladder route, §7.1), `ORD-MDW`, `FLL-MIA`, `OPF-MIA`, each with a `RAIN:<A>-<S>:IND:v1` twin where both stations report rain. The fixture run (07-06) uses `PAIR:LGA-NYC` and `PAIR:JFK-NYC`. Phase 3's verdict is in (§17): the station pair is kept as the v0 residual venue (labelled; it adds ≈ +0.01 as cover), P-A-IDW is the RFQ reference for heat residuals, and the weekly PRISM spread is the rain residual. The registry is the swap point.

Quorum and fallback: a METRO/RA value needs `≥ quorumBps` (v0 6000) of listed inputs present at the fetch; a PAIR or RAIN value needs both inputs. If short at the fetch, the reporter may post when inputs arrive, any time before `finalizeAt` (§9). If nothing valid is posted by `finalizeAt + voidGrace`, the index-day is **void** (§9.4). No substitute station is ever used silently.

TWC vs NWS: Kalshi settles the station leg on The Weather Company's value; our indices settle on NWS CLI. The difference is house basis, reported, never "fixed" by recomputing Kalshi results from CLI.

## 4. Daily timeline (UTC; D = epoch day of the climate date)

| When | What | Where enforced |
|---|---|---|
| D−1 14:00Z | Kalshi ladder for D opens; markets for D created; policy sales and auction orders open | engine schedule; `MarketCreated` |
| D 02:15Z = `saleCutoff` | policy sales close (quote `expiry ≤ saleCutoff`) | chain (`PolicyManager`) |
| D 02:30Z = `houseCutoff` | house quote schedule + all policy residual legs placed and frozen; the house address cannot place after this | chain (`BatchAuction`) + engine |
| D 03:00Z = `cutoff` | public order cutoff; `clear(market)` callable by anyone | chain + engine |
| D 03:00Z–04:30Z | house claims its residual-leg fills, calls `bind` on each policy (downsizing, §6.3) | `bindBy` = D 04:30Z |
| `close_time − 24h` (D 05:00Z ET, 06:00Z CT) | house paper-hedges station legs (headline). T−12h, T−2h recorded as shadow only | engine |
| `close_time` (D+1 05:00Z ET, 06:00Z CT) | Kalshi close = end of the NWS climate day. **Read `close_time` per market from data; never hard-code** | engine |
| D+1 12:00Z | CLI fetch → signed report posted | `fetchLag` |
| D+1 ~19:00Z | Kalshi `result` known → `HedgeSettled` | engine |
| D+2 12:00Z | CLI indices finalize (24 h dispute) → positions and policies settle | `finalizeAt` |
| D+5 12:00Z / D+6 12:00Z | nClimGrid fetch / finalize (if listed) | |
| D+7 12:00Z / D+8 12:00Z | PRISM fetch / finalize (if listed) | |
| daily 12:30Z | `PoolEpoch`: engine claims matured withdrawals it was asked to (inside their 3-day claim window, §8.2; the fixture scheduler lapses those past it), closes eligible days (§8.7), writes the day snapshot | engine |

Market times are **derived, never caller-chosen**: at `createMarket`, `saleCutoff = dayStart(D) + saleCutoffOffset` (2h15m), `houseCutoff = dayStart(D) + houseCutoffOffset` (2h30m), `cutoff = dayStart(D) + cutoffOffset` (3h), `bindBy = dayStart(D) + bindByOffset` (4h30m), from owner-set global offsets (demo worlds compress them; a market keeps the values it was created with). Because `marketId` excludes the times, deriving them stops a front-runner from creating a market with bad times. A policy bought before 02:15Z has seen no part of climate day D (which starts 05:00Z ET).

## 5. Residual batch auction

One auction per auctioned market (basis markets; owner/house may open others). Open (not sealed) call auction, uniform price.

**Order (chain struct):** `{address trader; bytes32 market; bool isBid; uint8 tick; bool claimed; uint128 qty; uint128 ahead}`. `isBid` = buys long units. `ahead` = quantity already queued at the same (market, side, tick) when placed. Orders are numbered globally from 1 in placement order.

**Placement rules:** `houseCutoff ≤ now < cutoff` is closed to the house address; `now ≥ cutoff` closed to all. `1 ≤ tick ≤ 99`, `1 ≤ qty ≤ MAX_ORDER_QTY = 2⁶⁴ − 1` (with the uint16 order count this keeps Q* and every level total below 2⁸⁰, so the uint128 book fields never truncate). Non-house orders only: escrow ≥ `MIN_ORDER_ESCROW = 1 USDC`, at most `MAX_ORDERS = 200` per market (the 201st reverts `BookFull`) and at most `MAX_ORDERS_PER_TRADER = 20` per address per market. House orders (residual legs and quote schedule) are exempt from all three, so cheap refundable spam cannot lock the house out of a book (§18 08-HARDEN). **No cancels** (they would corrupt `ahead`). Escrow is pulled at placement:
```
bid escrow   = qty * (tick * TICK + auctionFeePerUnit)
offer escrow = qty * ((100 - tick) * TICK + auctionFeePerUnit)
```
Bid escrow ≥ worst-case loss (tick·TICK per unit), offer escrow ≥ (100 − tick)·TICK per unit: fully collateralised.

**Clearing (identical in `wi.auction.clear`, `wi.engine` and `BatchAuction.clear`):**
```
bid[t], off[t] = total bid / offer qty at tick t (t = 1..99)
D[t] = sum(bid[u] for u >= t);  S[t] = sum(off[u] for u <= t)
for t in 1..99: V[t] = min(D[t], S[t]);  I[t] = |D[t] - S[t]|
Q* = max V. If Q* == 0: no cross, pStar = 0, every order refunds in full.
T  = { t : V[t] == Q* and I[t] == min(I over ticks with V == Q*) }   # contiguous [lo, hi]
pStar = (lo + hi) // 2                                              # lower midpoint
tb = highest t with D[t] >= Q*;   mb = Q* - D[tb + 1]               # marginal bid tick / qty
to = lowest  t with S[t] >= Q*;   mo = Q* - S[to - 1]               # marginal offer tick / qty
```
Scan ticks 1..99 ascending; a strictly better (V, then smaller I) resets `lo = hi = t`; an equal one sets `hi = t`. `D[100] = S[0] = 0`. Python reference (exists, Phase 4; the engine imports it, read 2026-09-30 and matches this rule): `wi.auction.clear.clear(orders) -> ClearResult(p_star, q_star, tb, mb, to, mo, fills, escrow, cost)`, `orders` = `Order(oid, is_bid, tick, qty)` in placement order, per-order tuples aligned with the input; pure ints, no pandas. Its escrow/cost exclude `auctionFeePerUnit`; the engine adds `qty × fee` to escrow and `fill × fee` to the fee line. The parity fixture needs per-order `ahead`; 07-02 may add an `ahead` tuple to `ClearResult` (additive) or recompute it with the same rule. `clear` moves `Q* × UNIT` of escrow to `PolicyManager.fundMarket` as that market's collateral.

**Fill per order (O(1), at claim; price-time at the marginal tick):**
```
slice(m, ahead, qty) = 0 if m <= ahead else min(m - ahead, qty)
bid:   fill = qty if tick > tb else slice(mb, ahead, qty) if tick == tb else 0
offer: fill = qty if tick < to else slice(mo, ahead, qty) if tick == to else 0
cost   = fill * pStar * TICK            (bid)      fill * (100 - pStar) * TICK   (offer)
fee    = fill * auctionFeePerUnit       (to treasury)
refund = escrow - cost - fee
```
Guarantees: Σ bid fills = Σ offer fills = Q*; Σ costs = Q*·UNIT; `tb ≥ pStar ≥ to`, so no fill crosses its limit; a claimed order records its position in PolicyManager via `recordFill(market, trader, isLong, fill, cost)` (`long += fill` or `short += fill`, `paid += cost`). Claims are lazy and permissionless per order (refund goes to the trader). After all claims the auction holds 0 for that market.

**Worked example (6 orders, fee 0).** Placement order: #1 bid 72×40, #2 bid 70×30, #3 bid 64×20, #4 offer 60×35, #5 offer 66×20, #6 offer 66×30 (ahead 20).
D: t ≤ 64 → 90; 65–70 → 70; 71–72 → 40; > 72 → 0. S: t < 60 → 0; 60–65 → 35; ≥ 66 → 85.
V = 35 on 60–65, **70 on 66–70 (I = 15)**, 40 on 71–72 → Q* = 70, tie range [66, 70], pStar = 68. tb = 70, mb = 70 − D[71] = 30; to = 66, mo = 70 − S[65] = 35.

| # | side@tick×qty | escrow | fill | cost | refund |
|---|---|---|---|---|---|
| 1 | bid 72×40 | 28,800,000 | 40 (tick > tb) | 27,200,000 | 1,600,000 |
| 2 | bid 70×30 | 21,000,000 | 30 (slice(30, 0, 30)) | 20,400,000 | 600,000 |
| 3 | bid 64×20 | 12,800,000 | 0 (tick < tb) | 0 | 12,800,000 |
| 4 | offer 60×35 | 14,000,000 | 35 (tick < to) | 11,200,000 | 2,800,000 |
| 5 | offer 66×20 | 6,800,000 | 20 (slice(35, 0, 20)) | 6,400,000 | 400,000 |
| 6 | offer 66×30 | 10,200,000 | 15 (slice(35, 20, 30)) | 4,800,000 | 5,400,000 |

Σ cost = 70,000,000 = Q*·UNIT. Longs: #1 40, #2 30. Shorts: #4 35, #5 20, #6 15.

**Who trades:** any wallet; businesses on the overlay path; the house, which posts (a) one residual-leg order per house-path policy (§6.2) and (b) a quote schedule of ≤ 3 levels per side (§6.6). House orders fill against each other when they cross; that is harmless (a self-held long+short pair returns exactly UNIT at settlement) and is how "the pool keeps what does not net" shows up in the book.

## 6. Policies

### 6.1 Signed quote and purchase (house-hedge path = default)
EIP-712 domain `{name: "wi-policy", version: "1", chainId, verifyingContract: PolicyManager}`. Type string (exact):
```
Quote(bytes32 market,address buyer,bool isLong,uint128 units,uint128 premium,uint128 fee,uint64 expiry,uint256 nonce)
```
`buyPolicy(Quote q, bytes sig)` requires: signer = `quoter`; `msg.sender == q.buyer`; `now ≤ q.expiry`; `now < market.saleCutoff`; nonce unused (per-quoter bitmap); `q.fee ≤ q.premium ≤ q.units × UNIT`; market exists; `units ≥ 1`. Effects: pull `premium` into PolicyManager **escrow** (not yet the pool's), `pool.reserve(day, units × UNIT)` (reverts on any cap, §8.4), store `Policy{buyer, market, isLong, units, boundUnits: 0, premium, fee, status: Bought}`. `createMarket(indexId, day, lo, hi, auctioned)` is owner/house-only until the day's `houseCutoff`, then permissionless for non-auctioned markets (it moves no money and the times are derived; the window stops a stranger squatting a basis market as non-auctioned before the house opens its book, §18 08-HARDEN); auctioned markets only by owner/house; the index must be registered and active in the oracle; creating an existing market reverts.

### 6.2 House booking (engine; the house acts as the pool's agent)
For a policy on location index `X_loc` with settlement station `S` (the index's `station`):
1. **Station leg:** replicate `units` of the same `[lo, hi]` on the Kalshi ladder for S (§7), aggregated per (series, day).
2. **Residual leg:** one limit order on the basis market `B = (basis index loc−S, D, −R, +R)` placed before `houseCutoff`:
   - capped temperature: `δ_ppm` from ladder mids (§7.4); `h = round_half_away(units × δ_ppm × 2R, (hi − lo) × PPM)`; call (business long) → house **bids** h; put (business short) → house **offers** h.
   - rain digital: `h = 2 × units` on `RAIN:<loc>-<S>:IND` (`[−1, +1]`), bid for DIGITAL_ABOVE, offer for DIGITAL_BELOW. This hedge is exact; in base units: `units·UNIT·1{loc} = units·UNIT·1{S} + (2·units·L(x) − units·UNIT)` with x = 1{loc} − 1{S}.
   - limit tick = the residual tick used in the premium (§6.6). `h = 0` → no order.
   Example: call (a) at LGA with δ = 550,000 ppm, R = 50: h = round_half_away(6·550,000·100, 60·10⁶) = round(5.5) = **6**, bid.
3. The pool carries everything the hedge does not: convexity at strike and cap, the ladder tail beyond the top rung (§7.3), rounding to contract steps, depth shortfall and TWC/NWS basis.
Temperature digitals and indices without a Kalshi ladder are overlay/RFQ-only in v0.
Three residual index types (§3, §17): (a) the station-pair spread is what the v0 auction lists, a labelled residual venue that adds ≈ +0.01 as cover per Phase 3, so no heat residual is sold as cover on its strength; (b) P-A-IDW, the three-nearest-ASOS inverse-distance index, is the reference for RFQ heat residuals; (c) the PRISM per-cell weekly spread is the rain residual (G1-P). The daily auction stays the venue; the rain residual settles weekly.

### 6.3 Binding and downsizing
After `clear`, before `bindBy`, the house calls `bind(policyId, residualOrderId)`. The chain checks: order placed by the house, its auction cleared, the order not already used to bind another policy, and the order's market day equals the policy's day (that the order sits on the right basis market is engine-checked, trust T3). `residualOrderId = 0` means h = 0.
```
h = order.qty; fill = the order's fill (§5, O(1) view)
boundUnits = units                               if residualOrderId == 0
           = mul_div(units, fill, h)             otherwise
keptPremium = mul_div(premium, boundUnits, units)
refund      = premium - keptPremium                               # to buyer (rounding favours the buyer)
keptFee     = mul_div(fee, boundUnits, units)                     # to treasury
toPool      = keptPremium - keptFee  -> pool.creditPremium(day, toPool)       # skipped when 0
if boundUnits > 0: pool.release(day, (units - boundUnits) * UNIT)
else:              pool.absorbLoss(day, units * UNIT, 0, buyer)                 # closes the policy
```
A policy bound at 0 units counts as settled for §8.7. `bind` reverts once the index-day is void (the unbound policy then refunds its full premium, §6.4). After `bindBy` **anyone** may call `bind(policyId, 0)`, i.e. `boundUnits = units` (the buyer keeps full cover if the house does nothing). The station hedge at T−24h uses bound units only, so nothing is unwound.

### 6.4 Settlement and void
After `oracle.getFinal(indexId, day)` succeeds: `payout = boundUnits × L(x)` if `isLong` else `boundUnits × (UNIT − L(x))`; `pool.absorbLoss(day, boundUnits × UNIT, payout, buyer)`; status Settled; each policy settles once. If the index-day is **void**: refund `keptPremium − keptFee` to the buyer through `absorbLoss` (same junior-first path), release the reserve; the treasury fee is not refunded. Unbound policies on a void day refund the full escrowed premium from PolicyManager.

### 6.5 Overlay path (fallback) and strips
- **Overlay:** the portal shows the Kalshi rung list (contracts per rung, §7.1) for the business to buy itself; the venue sells only the basis unit, either as an auction order or as a `buyPolicy` on the basis market (`fee` as usual; no station leg, no residual leg, `h = 0`).
- **Strips (v0 = floating day-ahead cover):** `openStrip(indexId, lo, hi, isLong, units, maxDailyPremium, startDay, endDay)` with a USDC allowance; each day the quoter calls `buyStripDay(stripId, Quote q, sig)` which behaves as `buyPolicy` for `q.buyer = strip owner` if `q.market` matches the strip template for that day, `q.units ≤ units`, `q.premium ≤ maxDailyPremium`. A day priced above the max is skipped, never partially filled. `closeStrip` stops future days. A fixed-price term is shown as a climatology quote only (not sold in v0).

### 6.6 Premium components (the quote identity)
```
stationLegE6  = Σ_rungs q_b × ask_b × 100  +  Kalshi fees (§7.5)  +  q_total × slipBufferCents × 100     # q in centi, ask in cents → E6
residualLegE6 = h × (t_res × TICK − UNIT/2)        (bid leg)        h × (UNIT/2 − t_res × TICK)   (offer leg)
tailE6        = mul_div(units × (UNIT − L(v_top)), p_top_ppm, 2 × PPM)   # call; mirror with the bottom rung for puts; strike-dependent when the range lies beyond the ladder (§18, 2026-09-30)
riskMarginE6  = bps(units × UNIT, riskLoadBps)
notionalFeeE6 = bps(units × UNIT, feeNotionalBps)
premium = max(stationLegE6 + residualLegE6 + tailE6 + riskMarginE6 + notionalFeeE6,  fee + minPremiumE6)
fee     = notionalFeeE6 + bps(riskMarginE6, feeMarginBps)
```
`t_res` = house residual tick: bid legs `ceil(fair + halfSpread)`, offer legs `floor(fair − halfSpread)`, clamped to 1..99. `fair` = E[L(Δ)]/TICK over the trailing 60 **finalised** days of the basis index (same month optional), all finalised before the quote time (no look-ahead); `halfSpread = max(minHalfTicks, z × sd/√n + buffer)`. The house schedule: bid `fair − halfSpread − k·inventory − {0, 1, 2}`, ask `fair + halfSpread − k·inventory + {0, 1, 2}`, each level sized by remaining cap headroom ÷ worst-case loss per unit. Every component is itemised in `QuoteIssued` and the API `Quote`.

## 7. House station leg: replication and paper fills

### 7.1 Replication (ins1 rule, any K, C, units, both directions)
Ladder rungs from Kalshi market records: `between` (floor f, cap c; covers integers f..c), `greater` (floor f; means ≥ f+1), `less` (cap c; means ≤ c−1). Representative value `v_b` (tenths): between `5 × (f + c)`, greater `10 × (f + 1)`, less `10 × (c − 1)`. Per policy and rung:
```
q_b_centi = round_half_away(units × L(v_b) × 100, UNIT)            # business long (calls, digital above)
q_b_centi = round_half_away(units × (UNIT − L(v_b)) × 100, UNIT)   # business short (puts, digital below)
```
Aggregate over all bound policies on the same (series, day), then round once to `CONTRACT_STEP` (centi; default 100 = 1 contract) with `round_half_away`. Example (a) with ladder `<86, 86–87, 88–89, 90–91, 92–93, >93`: v = 850, 865, 885, 905, 925, 940 → L = 0, 0, 83,333, 416,666, 750,000, 10⁶ → q = 0, 0, 50, 250, 450, 600 centi (0.5 / 2.5 / 4.5 / 6 contracts).
Rain: `q = units × 100` YES on the daily ">0 in" market (DIGITAL_ABOVE) or NO for DIGITAL_BELOW. The rain cover settles on `CLI:<S>:WET:v1` (≥ 0.01 in; a trace is dry), the same rule KXRAIN settles on (§17), so the cover and the Kalshi leg settle the same way: no house basis on trace days.
Thin ladders (`KXHIGHTEWR`, `KXHIGHTTTN`, 2.4–2.7× overround at 24 h) are not hedged directly: an EWR/TTN policy hedges on `KXHIGHNY` and routes `EWR−NYC` / `TTN−NYC` basis to a residual contract (listed only if Phase 3 keeps it; otherwise those policies are overlay-only). `hedgeableSeries` is a parameter.

### 7.2 Execution and paper fills (decision time `T = close_time − 86,400`)
- **Book:** use the recorded book snapshot with the largest `ts ≤ T` and `T − ts ≤ 120 s`. YES asks = `100 − NO bid` (cents) at the NO quantity; sort ascending (recorded arrays are ascending best-last; never trust order). Walk levels while `ask ≤ bestAsk + 3` and quantity is still needed. Record `filledCenti`, per-level cost, `shortfallCenti = need − filled` (pool exposure).
- **Candle fallback** (no qualifying snapshot, or history before the recorder): YES ask close of the last hourly candle with `end_period_ts ≤ T`; fill `min(need, candleCapCenti)` per rung (default 3,000 = 30 contracts), labelled `candle`.
- **No-offer rung:** ask ≥ 99 and bid < 90, or no ask → not bought; its payout is pool exposure; reported as a liquidity failure.
- Nothing after `T` may be read (point-in-time). T−12h and T−2h fills are shadow records for Phase 2 only and never move money.

### 7.3 Tail
The replication pays at most `L(v_top)` per unit for calls (`v_top` = the `greater` rung's v); `units × (UNIT − L(v_top))` is unhedged tail and is priced in `tailE6`. For puts the bottom rung mirrors this. When the whole policy range lies beyond the end rung's v, `tailE6` follows the strike-dependent rule in §18 (2026-09-30). Engine metric: share of policy-days with a non-zero tail.

### 7.4 δ for residual sizing
Per rung, `k_b` = number of integers t it covers (between: {f, c}; greater: {f+1}; less: {c−1}) with `lo < 10t ≤ hi`, `n_b` = 2 for between, 1 for tails. With mids in half-cents `m_b = bid_b + ask_b` from the same point-in-time source as the quote:
`δ_ppm = min(PPM, mul_div(PPM, Σ_b m_b × k_b × (2 / n_b), 2 × Σ_b m_b))` — i.e. the mid-implied P(lo < X ≤ hi), normalised by Σ mids. (`2/n_b` is 1 or 2, so all terms are integers.)

### 7.5 Fees and hedge payout
Kalshi taker fee per rung order, levels summed then rounded up once: `feeCents = ceil_div(Σ_levels 7 × q_centi × P × (100 − P), 1,000,000)` (P in cents). Examples: 1 contract at 30c → 2c; 3 at 45c → 6c. Money: `costE6 = Σ q_centi × P × 100 + feeCents × 10,000`. Hedge payout = `Σ filledCenti × 10,000` over rungs whose Kalshi `result == "yes"` (TWC-settled; never recomputed from CLI).

## 8. Pool

### 8.1 Ledgers and custody
One `PoolVault` holds all claim-paying USDC. Internal ledgers (never `balanceOf`): `seniorAssets`, `juniorAssets`, `reserved`, `deployed` (Σ `deployedByDay`). `capital = seniorAssets + juniorAssets`. Identity: `usdc.balanceOf(pool) == capital − deployed` (absent donations). Senior = outside LPs, `SeniorShare` ERC-20 (decimals 12). Junior = protocol-owned: internal non-transferable shares, deposits only from `juniorDepositor` addresses (v0: owner/house).

### 8.2 Shares (OZ ERC-4626 virtual offset 10⁶)
```
mint:   shares = mul_div(assets, supply + 10**6, trancheAssets + 1)
redeem: assets = mul_div(shares, trancheAssets + 1, supply + 10**6)
```
Deposits are immediate (senior earns only its premium share and is hit only after junior is gone, so a timed deposit gains nothing material). Withdrawals: `requestWithdraw(tranche, shares)` escrows the shares; `claimWithdraw(id)` after `withdrawDelay` (v0 12 days = `houseReturnWindow` + 2; testnet demo constructor arg) burns them at **claim-time** NAV, from cash only, and reverts if afterwards §8.4 caps or `jMin` would break. A loss during the delay hits the leaver too. **Claim window:** a matured request is claimable only in `[claimableAt, claimableAt + 3 days)` (`CLAIM_WINDOW`, `withdrawClaimWindow`); after that `claimWithdraw` reverts `ClaimWindowClosed` and anyone may call `lapseWithdraw(id)`, which hands the escrowed shares back to the owner (they never left the tranche supply, so no money leaves the tranche or the pool; the LP stays invested and may request again). Without the window a matured request was a standing option to exit at full NAV the moment a loss became visible but before it was booked. **Cancel:** the owner may `cancelWithdraw(id)` before `claimableAt`; the shares come back the same way. A request closes once (claimed, cancelled or lapsed; chain `claimed` flag = closed; events `Withdrawn` / `WithdrawCancelled` / `WithdrawLapsed`).

### 8.3 Waterfall
```
reserve(day, a):        require C1, C2 after; reserved += a; openPolicies[day] += 1
creditPremium(day, a):  s = bps(a, seniorPremiumBps); seniorAssets += s; juniorAssets += a - s; dayPnl[day] += a - s
absorbLoss(day, released, loss, to):   require loss <= released
    reserved -= released; _loss(day, loss); transfer loss to `to`; openPolicies[day] -= 1
_loss(day, l):   j = min(l, juniorAssets); juniorAssets -= j; seniorAssets -= l - j; dayPnl[day] -= j   # senior only once junior is 0
release(day, amount):   reserved -= amount           (downsizing; no count change)
gain(day, g) (house return, §8.6):  juniorAssets += g; dayPnl[day] += g
```
Senior earns a fixed share of the premium net of the treasury fee (`a` in `creditPremium` is `toPool` = kept premium − kept fee); junior earns the rest and carries all hedge P&L and all losses first. **Illustration at `seniorPremiumBps = 2000`** (the retired 20 % split, used here because the numbers are easy to follow; the v0 default is 30, §17/§18). Junior 10,000 USDC, senior 40,000; premium 4.20 with fee 0.30 → net premium (pool) 3,900,000 → senior 780,000, junior 3,120,000; a 3,000,000 payout → junior 10,000,120,000, senior 40,000,780,000. The first senior deposit of 40,000 USDC (40,000,000,000) minted 4·10¹⁶ shares at supply 0 (`mul_div(4·10¹⁰, 10⁶, 1)`), so redeeming 10 % of senior shares (4·10¹⁵) pays `mul_div(4·10¹⁵, 40,000,780,001, 4·10¹⁶ + 10⁶)` = 4,000,077,999. At the v0 default of 30 bps the same 3,900,000 splits senior 11,700, junior 3,888,300.

### 8.4 Caps (full collateral; no hedge credit in v0)
Chain (on every `reserve`, `fundHouse`, withdrawal claim):
- **C1** `(reserved + deployed) × 10⁴ ≤ capBps × capital` (u_max). With `capBps ≤ 10⁴` this implies `cash = capital − deployed ≥ reserved`, so every reserved payout is payable from cash, and it survives losses by construction (a loss ≤ its released reserve).
- **C2** `juniorAssets × 10⁴ ≥ jMinBps × capital` for new risk, senior deposits and junior withdrawals.
Engine (at quote signing and on every house order / RFQ; exposure = policy reserve + house order escrow + house RFQ collateral), grouped by the index registry:
- **C3** per (indexId, day) ≤ `alphaBps` × capital; **C4** per (station, day) ≤ `betaBps` × capital (residuals around one station are common-mode, ρ 0.74–0.83: treat as fully correlated); **C5** per (metro, day) ≤ `gammaBps` × capital; **C6** house station units per (series, day) ≤ depth-derived `maxHedgeCenti`.
Hedge-credit capital is reported as a metric only (Phase 4/14).
**Season basis (v0 write cap, off-chain at quote signing).** C1–C5 bound exposure day by day, and the Phase 4 capital figure (C_30) covers a 30-day window. A season can lose more than C_30, so the operator also caps the season's book: write cap = capital ÷ worst modelled season loss per unit of book. Capital is always stated on both horizons, the 30-day figure next to the season figure, never one alone.

### 8.5 Epochs, seeding, wipe-out
Seeding order: house junior deposit first; senior deposits open once `juniorAssets ≥ minJuniorForSenior`. If `juniorAssets == 0` (or C2 fails) all new risk and senior deposits revert until the owner recapitalises junior. No share-price reset in v0. `PoolEpoch` (daily 12:30Z) is engine bookkeeping only; nothing on chain waits for it.

### 8.6 House deployment (the pool's hedge book; trust T3)
The house wallet executes the pool's hedges: Kalshi paper legs (off-chain) and auction/RFQ positions (on-chain). Money moves only through:
- `fundHouse(day, amount)` (house only): cash → house wallet, `deployedByDay[day] += amount`; C1 applies; `day ∈ [today − 1, today + 2]` with `today = now / 86,400` (a far-future day could not be written off for years, §18 08-HARDEN).
- `returnFromHouse(day, amount)` (house): pulls `amount` from the caller, closes the day: `pnl = amount − deployedByDay[day]`; `pnl ≥ 0` → `gain(day, pnl)`; `pnl < 0` → `_loss(day, −pnl)`; `deployedByDay[day] = 0`. One return per day.
- `writeOffHouse(day)` (anyone, after `dayStart(day) + houseReturnWindow`, v0 10 days): unreturned `deployedByDay[day]` is booked as `_loss(day, deployedByDay[day])` and zeroed.
In `sim`, the Kalshi counterparty is the reserved account `@kalshi` (its balance may go negative); on chain the house wallet itself plays Kalshi's role for paper fills (testnet only). Station-leg and residual-leg P&L therefore reach the pool, so the pool carries only what the hedge misses; the house's own P&L is zero by construction and both are published.

### 8.7 Day close and WI staking haircut
`closeDay(day)` (anyone) once `openPolicies[day] == 0` and `deployedByDay[day] == 0` (returned or written off): if `dayPnl[day] < 0` with `l = −dayPnl[day]`,
`haircutBps = min(mul_div(l, 10⁴, juniorAssets + l), haircutCapBps)` (default cap 3000) and `WIStaking.haircut(day, haircutBps)` burns `mul_div(totalStaked, haircutBps, 10⁴)` WI. Example: junior lost 500 USDC net on D, junior now 9,500 → 500 bps → 50,000 of 1,000,000 staked WI burned. A day closes once.
**WI:** fixed supply, minted once to the deployer at construction; no mint function. `WIStaking`: `stake(amount)` mints `mul_div(amount, totalShares + 10**6, totalStaked + 1)` shares; `requestUnstake(shares)` starts `unstakeCooldown` (v0 12 days = houseReturnWindow + 2, seat ruling 2026-09-30) and the shares **stay cuttable**; `claimUnstake` pays `mul_div(shares, totalStaked + 1, totalShares + 10**6)`. Cuts are pro rata through `totalStaked` (O(1), cooldown included). Burned, never sold. Voting power = staked amount not in cooldown. Stakers earn nothing in v0 (Phase 15 question). WI never pays a claim.

## 9. Oracle and settlement

### 9.1 Report
EIP-712 domain `{name: "wi-oracle", version: "1", chainId, verifyingContract: OracleAdapter}`. Type string (exact, 07-CONTEXT §6):
```
Report(bytes32 indexId,uint32 day,int64 value,uint16 revision,uint64 asOf)
```
Signed by an allow-listed reporter; posted by anyone via `post(indexId, day, value, revision, asOf, vintageHash, sig)`. `vintageHash` (sha256 of the fetched source bytes, or the CLI product id hashed) is **stored and emitted but not signed** (it is audit metadata; the type string is locked). The engine's vintage archive keeps every fetch.

### 9.2 Per-index windows (`dayStart(D+1) = (day + 1) × 86,400`)
`fetchAt = dayStart(D+1) + fetchLag`; `finalizeAt = fetchAt + disputeWindow`; void allowed after `finalizeAt + voidGrace`.

| Source | fetchLag | disputeWindow | finalizeAt | voidGrace |
|---|---|---|---|---|
| NWS CLI (and PAIR/RAIN/METRO/RA on CLI) | 12 h (D+1 12:00Z) | 24 h | D+2 12:00Z | 72 h |
| METRO/RA with GHCN-D inputs | 12 h | 24 h (placeholder; Phase 3) | D+2 12:00Z | 72 h |
| nClimGrid-Daily prelim | 4 d 12 h (D+5 12:00Z) | 24 h | D+6 12:00Z | 72 h |
| PRISM daily | 6 d 12 h (D+7 12:00Z) | 24 h | D+8 12:00Z | 72 h |

### 9.3 Acceptance predicates for `post` (all must hold, else revert)
P1 index registered and active; P2 not finalized, not void; P3 `asOf ≥ fetchAt`; P4 `asOf ≤ now`; P5 `now − asOf ≤ maxReportAge` (v0 24 h); P6 `now < finalizeAt`; P7 `revision >` last accepted revision (first post any value ≥ 0); P8 `ECDSA.recover(_hashTypedDataV4(structHash), sig)` is an allow-listed reporter. Policy: revision 0 is the value in the source as fetched at `fetchAt` (fixed vintage). Later revisions only correct a transcription error against the **same vintage** (dispute by anyone off-chain in the window; the reporter re-posts). Later source revisions are ignored.

### 9.4 Finalize, read, void
`finalize(indexId, day)`: anyone, `now ≥ finalizeAt`, something posted. `getFinal` reverts unless finalized; settlement reads only `getFinal`. `voidDay(indexId, day)`: anyone, `now ≥ finalizeAt + voidGrace`, nothing posted. Void effects: positions refund exactly `paid` per (market, trader) (§10.3); bound policies refund `keptPremium − keptFee` from the pool; unbound policies refund escrow. The index registry never changes the windows of an already-listed index.

## 10. RFQ and positions

### 10.1 Flow (one-way, no last look)
1. `RfqRequested{requestId, requester, market, requesterLong, qty, windowEnd}` (off-chain via the API; the market is created first if bespoke).
2. The house responds first, then whitelisted makers, each with a firm signed quote under the `wi-policy` domain:
```
RfqQuote(bytes32 requestId,bytes32 market,address maker,address taker,bool takerLong,uint8 tick,uint128 maxQty,uint64 validUntil,uint256 nonce)
```
3. Best price wins at `windowEnd` for the requester's side (taker long → lowest tick, taker short → highest); ties → earlier response.
4. `acceptRfq(q, sig, qty)`: `msg.sender == q.taker`; signer == `q.maker` and maker whitelisted; `now ≤ q.validUntil` and `now < market.cutoff`; `q.nonce ≥ makerNonceFloor[maker]`; `filled[digest] + qty ≤ maxQty`. Taker pays `qty × tick × TICK` (long) or `qty × (100 − tick) × TICK` (short) by transferFrom; the maker's pre-deposited **margin balance** in PolicyManager pays the complement. Market collateral `+= qty × UNIT`. Makers cancel by `bumpNonceFloor`.
5. While only the house responds, the API labels the venue **single-responder**.

### 10.2 Positions
PolicyManager keeps per (market, trader): `longQty`, `shortQty`, `paid` (Σ entry costs). Market collateral = Σ paid over traders = `UNIT × Σ longQty` = `UNIT × Σ shortQty`.

### 10.3 Position settlement
`claimPosition(market)` after final: pays `longQty × L(x) + shortQty × (UNIT − L(x))`, once. On a void day pays back `paid`. A self-held pair (house long + short) returns exactly UNIT per pair.

## 11. Fees

| Fee | Rule | v0 value | Destination |
|---|---|---|---|
| Policy notional fee | `bps(units × UNIT, feeNotionalBps)` inside `Quote.fee` | 10 bps | treasury at bind |
| Policy margin fee | `bps(riskMarginE6, feeMarginBps)` inside `Quote.fee` | 1000 bps (10 % of risk margin) | treasury at bind |
| Auction fee | `auctionFeePerUnit` per filled unit per side | 0 (the chain cannot tell hedgers from traders; Phase 4 sweep may turn it on) | treasury at claim |
| RFQ fee | `rfqFeePerUnit` | 0 | treasury |
| Kalshi taker fee | §7.5 | Kalshi's | paper, in `stationLegE6` |
Fees are parameters, not code. Only the treasury address receives fees; the treasury is never at risk.

## 12. Invariants (asserted inside the engine's `apply` after every event; Foundry invariants mirror I1–I12)

| # | Invariant | Guards (events) |
|---|---|---|
| I1 | Conservation: Σ wallet USDC + auction escrow + PM (policy escrow + market collateral + maker margin) + pool cash + treasury + `@kalshi` == Σ `AccountFunded` | all |
| I2 | Per cleared market: Σ bid fills == Σ offer fills == Q*; Σ costs == Q*·UNIT; auction balance for the market == Σ unclaimed escrow after clear, 0 after all claims | AuctionCleared, OrderClaimed |
| I3 | No filled bid with tick < pStar, no filled offer with tick > pStar; no unfilled bid and unfilled offer both marketable at pStar | AuctionCleared, OrderClaimed |
| I4 | Every order escrow ≥ worst-case loss + fee; every escrow split exactly into cost + fee + refund | OrderPlaced, OrderClaimed |
| I5 | Market collateral == Σ paid == UNIT·Σ long == UNIT·Σ short; payouts per market ≤ collateral; each position claimed once | OrderClaimed, RfqAccepted, PositionSettled, PositionRefunded |
| I6 | Pool identity: pool cash == seniorAssets + juniorAssets − deployed; senior + junior NAV == capital | all pool events |
| I7 | Junior first: seniorAssets decreases in a step only if juniorAssets is 0 at the end of that step | PolicySettled, PolicyVoided, HouseReturned, HouseWrittenOff |
| I8 | C1 and C2 hold after every voluntary action (reserve, fundHouse, deposit, withdraw claim) | PolicyBought, HouseFunded, *Deposited, WithdrawClaimed |
| I9 | C3–C6 hold after every PolicyBought / house OrderPlaced / RfqAccepted / HedgeFilled | same |
| I10 | Policy payout ≤ boundUnits·UNIT, paid once; `refund + keptPremium == premium`; `keptFee + toPool == keptPremium`; `boundUnits ≤ units` | PolicyBound, PolicySettled, PolicyVoided |
| I11 | Nothing settles before `IndexFinalized`; the finalized value is the last accepted report; every accepted report satisfies P1–P8; void only with no report | ReportPosted, IndexFinalized, IndexVoided, *Settled |
| I12 | WI: Σ balances + staked == initial supply − Σ burned; haircut ≤ haircutCapBps; one close per day | WIHaircut, DayClosed |
| I13 | Point-in-time: a quote for day D uses only book/candle data with ts ≤ quote ts and basis history finalized before quote ts; a hedge fill uses only data with ts ≤ T = close − 24 h; no event reads a later-ts input | QuoteIssued, HedgeDecision, HedgeFilled |
| I14 | Paper fill ≤ recorded depth inside the 3-cent band (or ≤ candle cap) | HedgeFilled |
| I15 | Withdrawals: claimableAt ≤ claim ts < claimableAt + withdrawClaimWindow (claimableAt = request ts + withdrawDelay); a cancel or lapse hands the shares back and moves no pool money or share supply; unstake claim ts ≥ request ts + unstakeCooldown | WithdrawClaimed, WithdrawCancelled, WithdrawLapsed, WIUnstakeClaimed |
| I16 | Log hygiene: ints only (no floats) in payloads; `ts` non-decreasing; `seq` = previous + 1; `prev` = sha256 of the previous line's canonical JSON | all |

## 13. Event log and catalogue

Line = `{"seq": int, "ts": int, "type": str, "payload": {...}, "prev": hex64}`; canonical JSON = `units.canonical_json` (sorted keys, no whitespace, UTF-8, no floats); `prev` of seq 0 = 64 zeros; `prev` of line n = `units.event_hash(line n−1)`. Snapshots: canonical state JSON at each UTC day boundary + sha256; replay from snapshot k + tail must equal full replay. The reducer is pure: no wall clock, network or unseeded randomness; scheduler actions are events stamped with fixture ts.

Field types: `int` (JSON integer; u32/u64/u128/i64 ranges as in §1), `addr` (0x + 40 lowercase hex, or a reserved account `@pool`, `@treasury`, `@auction`, `@pm`, `@kalshi`, `@staking`), `b32` (0x + 64 lowercase hex), `str`, `bool`, `[…]` list. Money fields are base units; `tranche` ∈ {`senior`, `junior`}; `source` ∈ {`book`, `candle`}.

| Event | Payload |
|---|---|
| ParamsSet | key:str, value:int |
| AccountFunded | account:addr, amount:int |
| IndexRegistered | indexId:b32, name:str, kind:str, scale:int, station:str, metro:str, inputs:[str], quorumBps:int, fetchLag:int, disputeWindow:int, voidGrace:int |
| MarketCreated | marketId:b32, indexId:b32, day:int, lo:int, hi:int, saleCutoff:int, houseCutoff:int, cutoff:int, bindBy:int, auctioned:bool |
| SeniorDeposited / JuniorDeposited | owner:addr, amount:int, shares:int |
| WithdrawRequested | requestId:int, owner:addr, tranche:str, shares:int, claimableAt:int |
| WithdrawClaimed | requestId:int, owner:addr, amount:int |
| WithdrawCancelled / WithdrawLapsed | requestId:int, owner:addr, shares:int |
| HouseFunded | day:int, amount:int |
| HouseReturned | day:int, amount:int, deployed:int, pnl:int |
| HouseWrittenOff | day:int, deployed:int |
| DayClosed | day:int, juniorPnl:int, haircutBps:int |
| PoolEpoch | (empty) |
| WIStaked | owner:addr, amount:int, shares:int |
| WIUnstakeRequested | requestId:int, owner:addr, shares:int, claimableAt:int |
| WIUnstakeClaimed | requestId:int, owner:addr, amount:int |
| WIHaircut | day:int, bps:int, burned:int |
| QuoteIssued | digest:b32, market:b32, buyer:addr, isLong:bool, units:int, premium:int, fee:int, expiry:int, nonce:int, stationLeg:int, residualLeg:int, tail:int, riskMargin:int, notionalFee:int, residualMarket:b32, residualQty:int, residualTick:int, deltaPpm:int, dataAsOf:int |
| PolicyBought | policyId:int, digest:b32, market:b32, buyer:addr, isLong:bool, units:int, premium:int, fee:int |
| PolicyBound | policyId:int, residualOrderId:int, boundUnits:int, refund:int, keptFee:int, toPool:int, seniorPremium:int, juniorPremium:int |
| PolicySettled | policyId:int, x:int, payout:int |
| PolicyVoided | policyId:int, refund:int |
| StripOpened | stripId:int, owner:addr, indexId:b32, lo:int, hi:int, isLong:bool, units:int, maxDailyPremium:int, startDay:int, endDay:int |
| StripClosed | stripId:int |
| OrderPlaced | orderId:int, market:b32, trader:addr, isBid:bool, tick:int, qty:int, ahead:int, escrow:int, policyId:int (0 = none) |
| AuctionCleared | market:b32, pStar:int, qStar:int, tb:int, to:int, mb:int, mo:int |
| OrderClaimed | orderId:int, fill:int, cost:int, fee:int, refund:int |
| MarginDeposited / MarginWithdrawn | maker:addr, amount:int |
| RfqRequested | requestId:b32, requester:addr, market:b32, requesterLong:bool, qty:int, windowEnd:int |
| RfqQuoted | requestId:b32, digest:b32, maker:addr, tick:int, maxQty:int, validUntil:int, nonce:int |
| RfqAccepted | digest:b32, market:b32, taker:addr, maker:addr, takerLong:bool, tick:int, qty:int |
| PositionSettled | market:b32, trader:addr, longQty:int, shortQty:int, x:int, payout:int |
| PositionRefunded | market:b32, trader:addr, refund:int |
| ReportPosted | indexId:b32, day:int, value:int, revision:int, asOf:int, signer:addr, vintageHash:b32 |
| IndexFinalized | indexId:b32, day:int, value:int |
| IndexVoided | indexId:b32, day:int |
| HedgeDecision | series:str, day:int, decisionTs:int, closeTs:int, source:str, snapshotTs:int, rungs:[{ticker:str, needCenti:int}] |
| HedgeFilled | series:str, day:int, rungs:[{ticker:str, filledCenti:int, costCents:int, feeCents:int}], costE6:int, shortfallCenti:int |
| HedgeSettled | series:str, day:int, rungs:[{ticker:str, result:str, filledCenti:int}], payoutE6:int |

Chain events carry the same names and fields where a chain action exists (`PolicyBought`, `OrderPlaced`, …); off-chain-only events (`QuoteIssued`, `Hedge*`, `Rfq{Requested,Quoted}`, `PoolEpoch`) exist only in the engine log. Chain-only bookkeeping events (`BookOpened`, `Reserved`, `Released`, `PremiumCredited`, `LossAbsorbed`) have no engine twin; their amounts are inside `PolicyBought` / `PolicyBound` / `PolicySettled` / `PolicyVoided`. `ParamsSet` carries integer parameters; list-valued parameters (`hedgeableSeries`, station networks) live in the world params file whose sha256 goes into the run manifest.

## 14. Parity fixtures

Written by the engine (07-06) to `contracts/test/fixtures/`; read in Foundry with `vm.parseJson`. Tolerance: **exact integer equality on every field**. Never regenerate them from Solidity (that would be a mirror).

| File | Cases | Must include | Checked fields |
|---|---|---|---|
| `auction_cases.json` | ≥ 50 books | no cross, one-sided, all orders at one tick, V ties, I ties (tie ranges of odd and even length), marginal splits on both sides with `ahead > 0`, tick 1 and 99, 200 orders, nonzero `auctionFeePerUnit` | pStar, qStar, tb, to, mb, mo; per order ahead, fill, cost, fee, refund |
| `payoff_cases.json` | ≥ 60 | x below/at/above lo and hi, negative lo (basis), [0, 1] and [−1, 1] markets, hi−lo not dividing UNIT, qty up to 2¹²⁸−1 bounds tested for overflow | L, long payout, short payout, sum == qty·UNIT |
| `pool_cases.json` | ≥ 20 step sequences | first deposit, virtual-offset rounding, premium split, loss < junior, loss > junior (senior hit), house return with gain and with loss, write-off, cap and jMin reverts, withdrawal after a loss | ledgers, shares, reserved, deployed, cash, expected revert name |
| `bind_cases.json` | ≥ 15 | h = 0, full fill, partial, zero fill, premium not divisible by units | boundUnits, refund, keptFee, toPool, senior/junior split |
| `haircut_cases.json` | ≥ 10 | below cap, at cap, above cap, cooldown shares cut, day with net gain | bps, burned, per-position balances |
| `eip712_cases.json` | ≥ 3 per type | Report, Quote, RfqQuote with anvil key #2 (reporter) / #1 (quoter, maker), chainIds 31337 and 998, fixed verifyingContract | typeHash, structHash, digest, signature (v, r, s), recovered signer |

The API layer adds its own end-to-end golden (`tests/api/golden/scenario_nyc_3d.json`, Phase 9) that sim and anvil must both match on every `…E6` field.

## 15. Chain modes

| Mode | State | Who signs | API returns |
|---|---|---|---|
| `sim` | the engine reducer (this spec) | engine for every role, demo users included; EIP-712 domain `chainId 31337`, `verifyingContract` = sentinels `0x…00a1` (oracle), `0x…00a2` (policy) so sim signatures never verify on a real chain | `done` |
| `anvil` | local contracts | server with anvil **public** keys: #0 admin, #1 house + quoter + RFQ maker, #2 reporter, #3 keeper, #4–#9 users (or `needs_signature` if `ANVIL_SERVER_SIGNS_USERS=0`) | `done` |
| `testnet` (998) | HyperEVM contracts | **no key on the server** (boot guard). Users sign in their wallets; quotes, house actions and reports are signed by owner-run processes with owner-created role keys (Phase 17) | `needs_signature` |

Contract interfaces (signatures + NatSpec, `contracts/src/interfaces/`): `IPolicyManager` (§2, §6, §10), `IBatchAuction` (§5), `IPoolVault` (§8), `IOracleAdapter` (§9), `IWIStaking` (§8.7). `WIToken` becomes fixed supply (mint once to the deployer in the constructor, no mint function, ERC20Burnable so staking can burn); `SeniorShare` is minted/burned only by the vault. Admin: Ownable2Step + Pausable on every contract; pause blocks new risk only (`buyPolicy`, `buyStripDay`, `placeOrder`, `acceptRfq`, deposits, `fundHouse`), never claims, settlement, finalize, withdrawals or returns. No proxies.

The same event names and integer results hold in every mode; flipping the mode changes no UI. Timestamps: sim uses the fixture/world clock; chain modes use `block.timestamp` (never `block.number`). Gas: every non-deploy call ≤ 2.0 M gas (HyperEVM small blocks are 3 M; forge adds 30 %); `clear` ≤ 1.5 M with all 99 ticks populated.

## 16. Regulatory notes (not legal conclusions)

- Nothing here is a legal conclusion. The Phase 15 research (for counsel) finds that a cash payout on local weather without proof of loss is likely a swap under the CEA unless a state-supervised insurer provides it as insurance; open residual auctions and a junior token that earns income raise further questions.
- Mainnet access rules are **undecided**: eligibility gating (ECP/KYC), a DCM-listing route, a carrier wrapper for the policy, and whether stakers may receive any income. v0 runs on testnet with mock USDC, open auctions, no points and no rewards.
- Kalshi's data terms restrict using Kalshi data to price or settle instruments without consent; v0 uses Kalshi data only for paper hedges and research.
- Portal and API copy must not call the product "insurance" or promise "coverage" in the regulated sense; use "weather cover", "payout", "policy" (internal term) and state that it is a testnet prototype.

## 17. Open parameters

Placeholders until the named phase sets them. Anything here is the **only** allowed TODO in this file.

| Parameter | v0 value | Set by |
|---|---|---|
| Residual index types (§3, §6.2) | (a) station-pair spread = v0 auction listing (PAIR:LGA-NYC, PAIR:JFK-NYC in the fixture), labelled residual venue, ≈ +0.01 as cover per Phase 3; (b) P-A-IDW three-nearest-ASOS inverse-distance = RFQ reference for heat residuals; (c) PRISM per-cell weekly spread = rain residual (G1-P) | Phase 3 verdict + seat ruling 2026-09-30 (07-CONTEXT, rulings on 07-CONSISTENCY) |
| Basis range R (tenths) | 50 (±5 °F); rain 1 | Phase 3/4 (high percentile of \|Δ\|) (TODO) |
| `capBps` (u_max) | 8000 | Phase 4 handoff.json (TODO) |
| `alphaBps` / `betaBps` / `gammaBps` | 1000 / 2000 / 3000 | Phase 4 (TODO) |
| `jMinBps`, `minJuniorForSenior` | 2000; 1,000 USDC | Phase 4 / 14 (TODO) |
| `seniorPremiumBps` | 30 | Seat ruling 2026-09-30 (04-JUNIOR): senior gets ≈ 20 % of kept margin; the simulated book keeps ≈ 1.5 % of premium, so 0.2 × 1.5 % ≈ 30 bps of premium net of the treasury fee (the base `creditPremium` applies it to) |
| Season write cap | notional written per season ≤ capital ÷ worst modelled season loss per unit of book (≈ 0.22 of notional on a season basis vs 0.126 on the 30-day basis for the simulated book); both horizons always stated (§8.4) | Seat ruling 2026-09-30 (04-JUNIOR) |
| `haircutCapBps` | 3000 | Phase 4 stress days / 14 (TODO) |
| `withdrawDelay`, `unstakeCooldown`, `houseReturnWindow` | 12 d (= houseReturnWindow + 2; guard), 12 d (= houseReturnWindow + 2; closes the haircut-dodge found in Phase 8), 10 d (demo: constructor args). Deploy guard: `unstakeCooldown ≥ houseReturnWindow + 2 d` and `withdrawDelay ≥ houseReturnWindow + 2 d` | seat ruling 2026-09-30 (rulings on 07-CONSISTENCY, item 1) |
| Vintage hash in the signed Report payload | not in v0: the hash is stored and emitted but not signed (§9.1); the engine enforces the fixed vintage (`VintageChanged`), the chain cannot. Mainnet: the vintage hash enters the signed Report payload | mainnet item (seat ruling 2026-09-30) |
| Parameter governance | v0: the owner key sets parameters. Mainnet: staked-WI parameter voting inside fixed ranges with a timelock (voting power §8.7) | mainnet item (seat ruling 2026-09-30) |
| `feeNotionalBps` / `feeMarginBps` | 10 / 1000 | Phase 4 fee sweep (TODO) |
| `auctionFeePerUnit` / `rfqFeePerUnit` | 0 / 0 | Phase 4 fee sweep (TODO) |
| `riskLoadBps` / `minPremiumE6` / `slipBufferCents` | 200 / 10,000 / 1 | Phase 4 / 07-04 (TODO) |
| House quoting: `minHalfTicks`, `z`, `buffer`, `k`, level step | 1, 1.0, 1 tick, 0, 1 tick | 07-05 / Phase 4 markouts (TODO) |
| `MAX_ORDERS` | 200 non-house orders per book (house exempt); `MAX_ORDERS_PER_TRADER` 20; `MIN_ORDER_ESCROW` 1 USDC; `MAX_ORDER_QTY` 2⁶⁴ − 1 | Phase 8 gas measurement (TODO); limits 08-HARDEN |
| Withdrawal claim window | 3 days after `claimableAt`, then the request lapses (shares back to the owner) | seat ruling 2026-09-30 (08-AUDIT #6) |
| `CONTRACT_STEP` (centi) | 100 (1 contract) | confirm Kalshi fractional trading (TODO) |
| `candleCapCenti` | 3,000 per rung per city-day | Phase 2 depth (TODO) |
| `hedgeableSeries` | KXHIGHNY, KXHIGHCHI, KXHIGHMIA + daily rain for NYC/CHI(ORD)/MIA | Phase 2 (TODO) |
| Kalshi fee formula | 0.07·q·P·(1−P), ceil per order | confirm official schedule (TODO) |
| Trace precipitation | trace (T) = 0 (§1): the rain cover pays on CLI daily precip ≥ 0.01 in only, and a trace day is dry. Evidence: the multi-city KXRAIN series the house trades settled 26/26 trace days NO at CLINYC/CLIORD/CLIMIA over 2026-07-15..09-29, 94/94 measurable days YES and 96/96 dry days NO (`reports/eval-01/trace_kxrain_2026.json`). The 61.5 % trace-YES figure (eval-01 `rain_daily.trace_yes_share`) comes from the older KXRAINNYC series and does not describe KXRAIN | 13-RAIN trace flip, seat ruling 2026-09-30 |
| METRO/RA GHCN-D disputeWindow, `quorumBps` | 24 h, 6000 | Phase 3 (TODO) |
| `maxReportAge`, `voidGrace` | 24 h, 72 h | Phase 8 / 17 (TODO) |
| Market time offsets (sale / house / public cutoff / bindBy) | 2h15m / 2h30m / 3h / 4h30m after dayStart(D) | fixed for v0; demo worlds compress |

## 18. Change log

- 2026-09-30: v0 frozen (07-01). Deviations from `docs/CONVENTIONS.md` §2: daily Kalshi temperature/rain markets close at 05:00Z (ET) / 06:00Z (CT), not 03:59Z (03:59Z is the weekly/monthly rain series); the engine reads `close_time` from data.
- 2026-09-30: `seniorPremiumBps` 2000 → 30 (seat ruling, 04-JUNIOR). The senior share is a share of kept margin; v0 approximates with 30 bps of premium net of the treasury fee (base corrected from "gross" in the 2026-09-30 consistency pass, below); mainnet routes margin explicitly via the house-signed quote. Added the season-basis write cap (§8.4, §17): write cap = capital ÷ worst modelled season loss, both horizons always stated.
- 2026-09-30: tail charge made strike-dependent (07-ENGINE resolution #3; seat addendum in 07-CONTEXT; hosted-demo polish). Before: when the whole policy range lay beyond the ladder (a put with `hi ≤ v_bot`, a call with `lo ≥ v_top`), the station leg was 0 and `tailE6 = units × UNIT × p_end / 2` at every line (NYC cool-day cover in the July heat wave: $46.88/day at every line from 75 to 88 °F). Now, in that case only (other policies keep §6.6 as written):
  ```
  spreads  y_i  = floor(|n·Δ_i − ΣΔ| / n) for each finalised basis value Δ_i in each trailing window   # centred per window
  windows       = the policy's own basis market window (the §6.6 fair-value window: 60 days, finalised ≤ quote time);
                  with no basis market (policy AT the settlement station), every PAIR index on the same station
  u(y)          = L(v_bot) − L(v_bot − y)   (put)          L(v_top + y) − L(v_top)   (call)
  estE6         = mul_div(units × Σ_i u(y_i), p_end_ppm, N × PPM)                      # N = number of y_i
  tailE6        = max(units × TICK, min(mul_div(units × UNIT, p_end_ppm, 2 × PPM), estE6))
  ```
  `p_end_ppm` is the end rung's normalised mid (unchanged). A line further from the ladder edge costs strictly less until the floor of one tick per unit; the charge never exceeds the old one. No window → the old charge. Engine: `pricing.tail_charge`, `pricing.station_basis_windows`; test `tests/api/test_tail_charge.py`. Fixture run, `pool_cases.json`/`waterfall_cases.json` and the API golden regenerated.
- 2026-09-30 (07-CONSISTENCY pass, seat rulings in 07-CONTEXT): (1) §8.3 worked example labelled as an illustration at `seniorPremiumBps = 2000`; the redeem line fixed (share count 4·10¹⁶, not 4·10¹⁷, so the printed 4,000,077,999 now matches the formula); the senior premium base is the premium net of the treasury fee everywhere (§8.3, §17, §18). (2) `unstakeCooldown` 10 → 12 d and `withdrawDelay` 10 → 12 d (both = `houseReturnWindow` + 2; haircut-dodge found in Phase 8), with a deploy guard for both. (3) §17 rows added: vintage hash enters the signed Report payload (mainnet); staked-WI parameter voting with ranges and a timelock (mainnet; v0 owner key). (4) Index registry: three residual index types (§3, §6.2, §17): station-pair spread = v0 auction listing and labelled residual venue (≈ +0.01 as cover), P-A-IDW = RFQ reference for heat residuals, PRISM per-cell weekly spread = rain residual; the daily auction stays the venue, rain residuals settle weekly. (5) Trace rain TODO resolved: trace settles wet, 61.5 % of trace days settled YES in 2023–2026; the encoding stays T = 0 and the difference is house basis (§7.1).
- 2026-09-30 (13-RAIN, rain cover end to end): wet-day cover on the daily station leg. **Index** `CLI:<S>:WET:v1` (§3; S = the metro's Kalshi rain station: NYC → CLINYC, Chicago → CLIORD, MIA → CLIMIA), value 1 when the CLI daily precip is ≥ 0.01 in or T. **Market** `[0, 1]`, business long `units`; payout = `units × UNIT` per wet day (§2 DIGITAL_ABOVE), one engine policy per covered day. **Station leg** one KXRAIN "> 0 in" contract per unit per day (§7.1), bought by the house at `T = close − 24 h` (candle rule §7.2 in the demo); the world file carries `rainSeries` {station → series} beside `hedgeableSeries`. **Price** per day, SPEC 6.6 with no residual leg: `stationLegE6 = need × t × 100 + fee(need, t) × 10⁴ + need × slipBufferCents × 100` (need = units × 100 centi, fee per §7.5, rounded up once), where `t` = the day's Kalshi ask if its market is quotable at the quote time (ask = mid + half-spread), else `t = ceil(fair + halfSpread)` with `fair` = mean wet-day indicator over the trailing `historyDays` finalised days (finalised ≤ quote time) and `halfSpread` by the §6.6 residual rule; `tailE6` = trace load on Kalshi-priced days = `mul_div(units × (UNIT − mid), traces, traces + dry days)` over the same window (0 on history-priced days, which already count traces as wet); `premium ≤ units × UNIT` or no quote; C3–C5 apply. **Residual** none listed: the G1-P weekly PRISM spread needs a weekly market, a weekly fetch window and one residual order binding seven daily policies (§6.3 binds one order to one policy on the same day), which the v0 engine and contracts do not have, so rain ships as station-leg-only cover and the business's local difference is RFQ-only. **Clock** a house day whose Kalshi leg settles after D+2 12:00Z (KXRAIN settles D+2 11:30–15:30Z) returns at that settlement instead of at finalize. Engine: `pricing.price_rain_policy`, `pricing.finalized_rows`, `hedge.rain_needs`, `house_mm.station_series`; API `quoting.build_rain`; test `tests/api/test_rain_cover.py`. Temperature quotes, the fixture run and the API golden are unchanged.
- 2026-09-30 (13-RAIN trace flip, seat ruling 2026-09-30, 07-CONTEXT.md): the rain cover pays on measurable rain only (CLI daily precip ≥ 0.01 in; a trace is dry), which is how KXRAIN settles (26/26 trace days NO, 94/94 measurable YES, 96/96 dry NO, 2026-07-15..09-29, `reports/eval-01/trace_kxrain_2026.json`). The cover and the station leg therefore settle identically; the trace load in the entry above is removed (`tailE6 = 0` for rain) and §3, §7.1, §17 now say so. Supersedes the trace clauses of the 13-RAIN entry above.
- 2026-09-30 (08-HARDEN, money-safety pass on the Phase 8 contracts; seat rulings in 08-AUDIT): (1) `createMarket` is owner/house-only until the day's `houseCutoff`, then permissionless for non-auctioned markets (§6.1), so nobody can squat a basis market before the house opens its book. (2) Public auction orders need ≥ 1 USDC escrow and are capped at 20 per address and 200 per book; house orders are exempt (§5). (3) Order qty ≤ 2⁶⁴ − 1, so Q* can no longer truncate in its uint128 slot and strand escrow (§5). (4) `bind` reverts once the index-day is void, so an unbound buyer always gets the full premium back (§6.3, §6.4). (5) `fundHouse` only for days in [today − 1, today + 2] (§8.6), so every deployment can be written off within `houseReturnWindow`. (6) Withdrawal claim window: a matured request is claimable for 3 days, then lapses (shares back to the owner, nothing leaves the pool); cancel before maturity (§8.2, §12 I15, §13 `WithdrawCancelled` / `WithdrawLapsed`). Also: `withdrawDelay` 12 d in the deploy script and engine default, and the `withdrawDelay` / `unstakeCooldown` ≥ `houseReturnWindow` + 2 d guard now lives in the contracts (PoolVault constructor, `setStaking`, `setWindows`, `WIStaking.setUnstakeCooldown`) as well as the deploy script. Engine mirrors (1)–(6) where it models them ((1) has no engine twin: engine events carry no sender); the fixture run and `pool_cases.json` / `waterfall_cases.json` regenerated.
