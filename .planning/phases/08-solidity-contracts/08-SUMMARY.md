# 08 SUMMARY — Solidity contracts, tests, scripts, runbook (2026-09-30)

**Shipped (contracts/).** `src/`: PolicyManager (markets with derived times, `Quote` policies, bind/downsizing, settle/void, strips, RFQ + maker margin, positions), BatchAuction (O(99) clear, O(1) claim, 200-order cap, per-book fee snapshot), PoolVault (+SeniorShare 12 dp; junior-first waterfall, C1/C2, request→claim withdrawals, house fund/return/write-off, closeDay→haircut), WIToken (fixed supply, burnable), WIStaking, OracleAdapter, Lens (one eth_call per user), MockUSDC, `lib/Payoff.sol`, `lib/BindMath.sol`. Interfaces unchanged. `test/`: 2 invariant suites + handlers, OracleSettlement, StakingHaircut, MoneyEdges, GasBudget, `parity/` ×7. `script/`: Deploy (CREATE only), Configure (idempotent), Smoke (read-only), E2E + Warp (anvil only), `hl_big_blocks.py`, `anvil_e2e.sh`, `gas_table.py`. `Makefile`, `RUNBOOK.md`, `README.md`, `deployments/31337.json` + `deployments/e2e-31337.json` from a real anvil run. solc 0.8.37, cancun.

**Sizes (runtime / initcode B, EIP-170 24,576).** PolicyManager 22,781 / 23,984 (1,795 B margin: tight) · Lens 11,307 / 11,850 · PoolVault 11,093 / 14,600 · BatchAuction 9,051 / 9,579 · OracleAdapter 7,399 / 8,187 · WIStaking 4,981 / 5,461 · SeniorShare 2,303 · WIToken 1,939 · MockUSDC 1,862.

**Gas (worst case; budget 2.0M, clear 1.5M).** In-process `GasBudget` (200-order book, all 99 ticks both sides) / real anvil receipts under a 3,000,000 block (max gasUsed · max tx gas limit forge asked for):
| call | forge test | anvil 3M block |
|---|---|---|
| clear | 464,101 | 479,473 · 701,229 |
| buyPolicy | 401,416 | 371,084 · 512,558 |
| acceptRfq | 336,088 | 327,608 · 452,507 |
| placeOrder | 205,258 | 235,940 · 325,891 |
| bind (with order) | 219,886 | 226,843 · 331,757 |
| claim | 162,021 | 163,442 · 239,033 |
| requestWithdraw / closeDay (haircut) | 181,606 / 146,982 | 173,659 / 136,275 |
| settlePolicy / claimPosition | 112,388 / 100,646 | 99,642 / 90,906 |
| post / finalize / voidDay | 94,272 / 39,365 / 58,556 | 87,427 / 32,226 / 51,293 |
| Lens.userView (eth_call, ~34 orders) | 850,667 | n/a |
Deploys (need big blocks): PolicyManager 5.13M, PoolVault 3.15M, Lens 2.50M (×1.3 = 3.24M); the rest fit a small block. 518 mined anvil txs after the 3M drop, 0 over budget.

**Verification (run from contracts/, PATH=~/.foundry/bin).**
- `forge build --sizes` → clean, table above.
- `forge test` → **31 passed, 0 failed, 0 skipped** (13 suites). Invariants 256 runs × depth 100 (pool: depth 200), fuzz 1,000 runs.
- Parity vs the engine's `test/fixtures` (exact equality): auction 64 books (pStar/qStar/tb/to/mb/mo + per-order ahead/escrow/fill/cost/fee/refund), payoff 192 (incl. int64 extremes, qty 2¹²⁸−1), waterfall 23 sequences step by step (ledgers, shares, cash, per-day books, result, revert name), oracle 14 cases (1 engineOnly skipped), bind 16, haircut 11, eip712 18 (typeHash, domainSeparator, digest, signer). All pass on the first run. Absent file → `[SKIP: parity fixture not found …]` (checked with a throwaway test).
- Mutation checks: ceil in the premium split and a halved junior hit each fail WaterfallParity; the second also fails `invariant_juniorFirst`. Restored.
- `make anvil-e2e` (own anvil on :8547, stopped by PID) → deploy at 30M, `evm_setBlockGasLimit 3000000`, configure, smoke OK, 5-phase E2E (2 policies, 1 downsized 6→4 at a marginal tick, 204 orders incl. a full 200-order book, RFQ, house fund/return at a loss, revision 1, finalize, settle, void + refunds, withdrawal at claim-time NAV, closeDay burns 5,940 WI incl. cooldown shares). Phase 5 asserts exactly: auction holds 0, PM collateral 0, PM balance = maker margin, pool balance = capital − deployed, WI supply + burned = genesis, Σ USDC over known actors = totalSupply.
- `hl_big_blocks.py`: not run against testnet (no key). Guards checked: mainnet RPC host refused before any call; anvil (chain 31337) refused.
- Preflight dry run writes nothing (`dry run: not writing`).

**Deviations / choices beyond SPEC (seat to confirm).**
1. `closeDay` needs `now ≥ dayStart(D+1)` (stops a premature close that skips the haircut). The engine adopted it.
2. A fill claimed after its trader already claimed the position is paid out at once in `recordFill` (was stranded collateral). Found by the auction invariant.
3. P1 follows SPEC (post needs an active index). So deactivating an index voids its unreported days. The interface NatSpec says "existing days still settle". These conflict; the SPEC wins for now.
4. P5 (`maxReportAge`) cannot fire with the v0 CLI windows, because maxReportAge = disputeWindow = 24h. It is tested with 1h. Say so in §17.
5. `auctionFeePerUnit` is snapshotted per book at openBook, so escrow always matches the claim-time fee.
6. Token contracts (WIToken, SeniorShare, MockUSDC) carry no Ownable/Pausable. Pausing the oracle gates nothing. Pause also blocks `openStrip` and `stake`.
7. Per-user id arrays (policyIdsOf, orderIdsOf, marketsOf, withdrawIdsOf, unstakeIdsOf) feed the Lens. They cost about 22–44k gas per new item. The Lens is O(items); heavy users should page ordersOf/positionsOf.
8. The `OrderPlaced` chain event has no `policyId`, because the interface is the source of truth.
9. `settlePolicy` on a non-void unbound policy reverts `NotBound`: bind first (anyone can after bindBy). Offsets must satisfy sale ≤ house ≤ cutoff ≤ bindBy < 1 day.
10. SPEC observations: (a) an unstaker can escape a haircut if closeDay waits for a house write-off, because the 10-day return window equals the 10-day cooldown. Suggest cooldown > houseReturnWindow + 2 d. (b) Senior premium credited while senior supply is 0 ends up owned by the virtual shares. (c) MAX_ORDERS does not affect clear gas (O(99)), so 200 has headroom.
No revert name or check order changed after the engine read PoolVault.sol / OracleAdapter.sol. The fixtures need no rerun.

**Owner must do.** Follow `contracts/RUNBOOK.md`:
- Mainnet-deposited wallet → faucet → testnet HYPE → 0.5 HYPE to a fresh `wi-deployer` keystore → ~5 USDC on HyperCore to make B a Core user.
- Then run `testnet-preflight → bigblocks-on → deploy-testnet → bigblocks-off → configure-testnet → smoke-testnet`.
- Send back `deployments/998.json` and the smoke output. Optional: separate HOUSE/QUOTER/REPORTER/TREASURY addresses.
- Sourcify verification and all live-chain behaviour are untested here. Plan B (small-block-only deploy) is not possible until PolicyManager is split.
