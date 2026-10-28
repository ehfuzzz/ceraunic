# Phase 8: Solidity contracts - Research

**Researched:** 2026-09-30 (live RPC reads 07:50–08:15Z)
**Domain:** Foundry/Solidity on HyperEVM testnet (chain 998): tranche pool vault, uniform-price batch auction, EIP-712 signed-report oracle, policy/position ledger, owner-run big-block deploy
**Confidence:** MEDIUM-HIGH. Chain facts and Foundry behaviour were checked against official docs, the Foundry 1.8.3 source, and live testnet/mainnet RPC reads, and several were reproduced locally. The mechanism designs are engineering recommendations, not citations. The ecosystem notes are LOW–MEDIUM.

## Summary

**Chain (verified today).** HyperEVM testnet:
- Chain id `998` (`0x3e6`). RPC `https://rpc.hyperliquid-testnet.xyz/evm`. Gas token HYPE (18 decimals).
- Cancun without blobs, EIP-1559 on. Base fee 0.1 gwei (`0x5f5e100`) on both block types. Priority fees are burned.
- Throughput is split across two block types. Small blocks carry 3,000,000 gas and arrive about every second. Big blocks carry 30,000,000 gas and arrive every 60 s. The official docs say this, and it reproduces on the live testnet (head 65,636,467 at ~08:00Z) and on mainnet (119 small and 2 big blocks in 118 s).
- Big blocks are opt-in per address through a HyperCore L1 action, `{"type":"evmUserModify","usingBigBlocks":true}`, signed like any exchange action.
- Only an existing HyperCore user can send that action. The deployer address becomes a Core user by receiving a Core asset such as testnet USDC.
- The official faucet gives 1,000 mock USDC, and only to an address that has deposited on Hyperliquid mainnet. That is the owner's gating step. Agents never do it.

**Tooling.**
- Versions: Foundry 1.8.3 stable (2026-09-15), forge-std 1.16.2, OpenZeppelin Contracts 5.7.0 (all three already vendored by 08-01), solc 0.8.37 (2026-09-10; no entries in solc's `bugs_by_version.json`; the 0.8.28 pin carries 6, mostly via-IR).
- Foundry 1.8.3 and solc 0.8.37 both default to `osaka`, which adds the CLZ opcode, so `evm_version = "cancun"` is mandatory. 08-01 already sets it.

Three Foundry gotchas were reproduced here:
1. **The 130% multiplier breaks small blocks.** `forge script` sets each transaction's gas limit to 130% of its simulated gas. A deploy that simulates above ~2.3M gas therefore asks for more than 3M, and a 3M block rejects it (`tx.gas_limit > env.block.gas_limit`). A 10.2 KB OZ ERC-4626 + ERC20Votes contract already costs 2.36M gas to deploy.
2. **The fork simulation is capped at 3M.** Forge's fork simulation takes `block.gaslimit = 3,000,000` from the RPC, so a deploy above 3M reverts in simulation even after big blocks are enabled. `--disable-block-gas-limit` fixes it.
3. **HyperEVM's RPC ignores historical block tags.** It silently serves latest state for them, so forks "pinned" to a block are not point-in-time.

**Verification and explorers.**
- Etherscan V2 lists 999 but not 998. Sourcify lists 998 as `"supported": true`. Use `--verifier sourcify`.
- The testnet explorers people cite are unusable today. `testnet.purrsec.com` returns 404 and `purrsec.com` now serves a gambling spam page. HypeRPC's Blockscout (`explore-testnet.hyperpc.app`) stopped indexing at block 60,609,357 on 2026-08-03.

**Design (recommended).**
- **One instrument.** A fully collateralized scalar "unit" pays long `L(x)` and short `1e6 − L(x)` USDC base units, so each long/short pair locks exactly $1. Conservation of value is structural, and all three payout families in the 08-01 stub map onto it.
- **Auction.** An open (not sealed) call auction with price buckets ("ticks") of 1–99 cents. The price is chosen to maximize matched volume, then to minimize imbalance, then the midpoint of any tie. At the marginal price level, orders fill by price-time priority, tracked with a per-order "queue ahead" offset. Each order is settled when its owner claims it ("lazy claim"). All math is integer, clearing is a fixed 99-step loop with no loop over orders, and fills conserve value exactly.
- **Pool.** One PoolVault (not ERC-4626) holds all the USDC. It keeps internal NAV ledgers per tranche and issues two share classes: a senior share, and WI as the junior first-loss share. Losses hit junior first. Withdrawals are request-then-claim after a delay.
- **Oracle.** EIP-712 signed reports, a revision window anchored to the calendar, and explicit finalization.
- **Pool policies** are bought with a quote signed by the house MM's key, never at a premium the caller chooses.
- **Admin.** Ownable2Step + Pausable, no proxies.

**Deploy flow.** CREATE-only script with big blocks on → big blocks off → configuration transactions in 1-second small blocks → read-only smoke check.

**Primary recommendation:** Keep the 08-01 scaffold. Bump solc to 0.8.37 with `evm_version = "cancun"`, and build the five contracts to the patterns below. Keep every non-deploy call under 2.0M gas. Ship a Makefile flow the owner runs from a Foundry keystore account (`--account`, never a plaintext key): `testnet-preflight → bigblocks-on → deploy-testnet (--slow --disable-block-gas-limit --verify --verifier sourcify) → bigblocks-off → configure-testnet → smoke-testnet`.

## Starting Point (08-01 is done, commit f59bfed)

`contracts/` exists with the following. Build is clean and `make deploy-anvil` works.
- foundry.toml: solc 0.8.28, cancun, optimizer 200, `fs_permissions` on `./deployments`, profile `hyperevm_testnet` with chain 998 (forge names it `hyperliquid-testnet`).
- forge-std 1.16.2 and OZ 5.7.0 vendored with `--no-git` (git-ignored; `make install` restores them).
- `MockUSDC` (6 decimals, open mint) and `WIToken` (owner-mint).
- Four stub interfaces.
- `Deploy.s.sol` (reads `DEPLOYER_PRIVATE_KEY`) and a Makefile.

Interface revisions this research recommends. Each one closes a silent money-failure path.

| Stub | Problem | Change |
|------|---------|--------|
| `IPolicyManager.PayoutType` formula `units * min(max(index - strike, 0), cap)` | Compares index units (°F×10, inches×100) with USDC units. Silent mis-payout. | Use the scalar unit instead: market = `(indexId, day, lo, hi)`, long pays `units × L(x)`. CappedLinearAbove = long on `[K, K+C]`; CappedLinearBelow = short on `[K−C, K]`; Indicator = `[K, K+1]`. |
| `IPolicyManager.createPolicy(..., premium)` | Caller picks the premium, so anyone can buy cover for 0. | `buyPolicy(Quote q, bytes sig)`: EIP-712 quote signed by the `quoter` (house-MM engine key) with buyer, market, units, premium, expiry, nonce. |
| `IBatchAuction.runAuction` "fill orders, create the resulting policies" | Loops over every order. Unbounded gas; small blocks fail past ~50 orders. | `clear(market)` does O(99) tick math only. `claim(orderId)` computes each fill in O(1). |
| `IBatchAuction.Order.filled bool`, `int256 limitPrice` | Price is unbounded and not on a grid, and filled/unfilled is binary. | `uint8 tick` (1..99 cents per $1 unit), `uint128 qty`, `uint128 ahead`, `bool claimed`. |
| `IOracleAdapter.postValue(..., nonce, sig)` | A nonce does not order revisions and does not stop stale values. | `post(indexId, day, value, revision, asOf, sig)` with revision strictly increasing and `asOf` bounds; `stationId` goes into `indexId`. |
| `IPoolVault.absorbLoss` / `creditPremium` | No exposure accounting. | Add `reserve(amount)` (cap check), `settle(released, loss, to)` (junior-first waterfall), `capital()`, `reserved()`. |
| `WIToken` owner-mint | Must become the junior share. | Mint/burn only by PoolVault, which deploys it in its constructor. Optional ERC20Permit + ERC20Votes for "votes on risk parameters". |
| `Deploy.s.sol` reads `DEPLOYER_PRIVATE_KEY` | Plaintext key in the owner's env. | `vm.startBroadcast()` with no argument, and `--account <keystore>` on testnet. Anvil keeps `--private-key` with anvil's public key. |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Foundry (forge, cast, anvil) | 1.8.3 stable (2026-09-15) | Build, test (fuzz + invariant), script deploys, local chain | Already installed at `~/.foundry/bin` and used by 08-01; the de facto Solidity toolchain |
| Solidity | 0.8.37 (2026-09-10), with `evm_version = "cancun"` | Compiler | No known bugs listed for 0.8.37; 0.8.28 carries `TransientStorageClearingHelperCollision` (high, via-IR + cancun) and 5 others. OZ 5.7 needs `^0.8.24`. Checked here: 0.8.37 + cancun builds OZ 5.7 and the scratch auction/oracle tests pass. |
| OpenZeppelin Contracts | 5.7.0 (2026-07-29) | ERC20, ERC20Permit/Votes, EIP712, ECDSA, SafeERC20, Ownable2Step, Pausable, ReentrancyGuard, Math.mulDiv | Audited primitives; already vendored |
| forge-std | 1.16.2 (2026-06-30) | Test/Script base, `StdInvariant`, cheatcodes (`vm.sign`, `vm.readCallers`, `vm.eip712HashStruct`, `vm.parseJsonAddress`) | Already vendored; pin it in `make install` (currently "latest") |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| hyperliquid-python-sdk | 0.24.0 (PyPI 2026-06-04) | `Exchange.use_big_blocks(True/False)` signs and sends `evmUserModify` | Owner's big-block toggle; run isolated via `uv run --no-project --python 3.12 --with hyperliquid-python-sdk==0.24.0` (the project venv is 3.14) |
| @nktkas/hyperliquid | 0.33.3 | TS SDK with `evmUserModify` | Only if Phase 9 needs to toggle from TS; not needed in Phase 8 |
| viem | 2.57.1 | `hyperliquidEvmTestnet` (id 998) chain definition | Phase 9/10 client code (10-01 portal already uses it) |
| uv | installed | Runs the SDK without touching the project venv | Big-block script |
| Sourcify | API (chain 998 supported) | Contract verification | `forge script --verify --verifier sourcify` / `forge verify-contract --chain 998 --verifier sourcify` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| One PoolVault with two share classes | Two ERC-4626 vaults (senior, junior) | ERC-4626 withdraw is synchronous, which clashes with the withdrawal delay that stops exits ahead of a known loss. Two custody points need cross-vault waterfall calls. Only worth it if outside composability is needed (not in the prototype). |
| Async request/claim withdrawals (ERC-7540-shaped, not claimed compliant) | Full ERC-7540 | ERC-7540 is the standard for async vaults (Lagoon uses it on HyperEVM). Full compliance means operators, pending/claimable views and more. Mirror the names; skip the standard. |
| Open batch auction | Commit–reveal sealed bids | Two transactions per order, deposits forfeited on non-reveal, twice the tests. Uniform price already removes most in-batch front-running value. Keep it as a v2 upgrade. |
| Price-time priority at the marginal tick | Pro-rata at the marginal tick | Pro-rata leaves rounding dust on each side, so long ≠ short and a dust sink is needed. Price-time is exact with one stored offset per order. |
| Python SDK for `evmUserModify` | Community UI hyperevmblocktoggle.xyz (listed in the Hyperliquid docs) | A third-party site asking for a signature. Acceptable for the owner if he prefers a UI, but the runbook ships the SDK script. |
| Big-block deploy | Small-block-only deploy (`--gas-estimate-multiplier 110`, every contract ≤ ~2.7M simulated gas ≈ ≤ 11 KB runtime) | No HyperCore account needed at all (EVM gas only). Plan B if the owner cannot make the deployer a Core user. Contracts above the ceiling must be split. |
| Plain CREATE + deployments/998.json | CREATE2 via the canonical deployer `0x4e59b448…956C` (present on testnet, 69 bytes) | Deterministic addresses, but extra ceremony (salts; constructor args change the address). Not needed. |
| No proxies | OZ UUPS/Transparent | Storage-layout risk and more tests. Testnet state is disposable: redeploy. |

**Installation:**
```bash
foundryup --install stable        # 1.8.3 at research time; `forge --version` must print 1.8.x
cd contracts
make install                      # forge-std@v1.16.2 + OZ@v5.7.0, vendored with --no-git (edit Makefile to pin forge-std)
# Makefile lines:
#   forge install foundry-rs/forge-std@v1.16.2 --no-git --shallow
#   forge install OpenZeppelin/openzeppelin-contracts@v5.7.0 --no-git --shallow
forge build --sizes && forge test
```
Expected noise on 0.8.37:
- Warning 6335 ("`at` will be promoted to keyword"), coming from OZ 5.7 internals (the `at` functions 5.7 deprecates). Harmless; do not suppress other codes.
- forge-lint notes such as `block-timestamp`. Harmless; timestamps are the intended clock here (G10).

## HyperEVM Testnet Facts (Research Q1)

| Item | Value | Confidence / source |
|------|-------|---------------------|
| Chain id | 998 (`0x3e6`); mainnet 999 | HIGH: Hyperliquid docs; live `eth_chainId` = `0x3e6` |
| Official RPC | `https://rpc.hyperliquid-testnet.xyz/evm` (HTTP only, no websocket on the official RPC) | HIGH: docs. Public DNS resolves it (3.170.19.x). This agent sandbox could not reach it (DNS/TLS reset), so agents doing read-only checks should use the alternative. |
| Alternative RPC | `https://rpcs.chain.link/hyperevm/testnet` (`web3_clientVersion` = "hyperliquid evm Testnet") | HIGH: Chainlink docs + live read. Returns HTTP 429 in bursts, so it is unusable for `forge script`. |
| Gas token | HYPE, 18 decimals; base + priority fees burned; `eth_maxPriorityFeePerGas` = 0 | HIGH: docs + live |
| Base fee today | 0.1 gwei on small and big blocks (`eth_gasPrice` = `eth_bigBlockGasPrice` = `0x5f5e100`) | HIGH: live testnet + mainnet |
| Block types | small: 3,000,000 gas, ~1 s; big: 30,000,000 gas, 60 s. One interleaved block-number sequence. | HIGH: docs + live histogram |
| EVM version | Cancun without blobs | HIGH: docs |
| System contracts present on testnet | Multicall3 `0xcA11bde05977b3631167028862bE2a173976CA11` (3,808 B), CREATE2 deployer `0x4e59b44847b379578588920cA78FbF26c0B4956C`, WHYPE `0x5555…5555`, CoreWriter `0x3333…3333` | HIGH: live `eth_getCode` |
| Explorer | **None current.** `testnet.purrsec.com` → 404, and `purrsec.com` serves a gambling spam page (the domain looks lapsed or hijacked, but Chainlink docs still link it). `explore-testnet.hyperpc.app` (Blockscout v9.0.2) is stalled at block 60,609,357 / 2026-08-03. Etherscan V2 chainlist has 999 only. | MEDIUM: probed today; the claim about the spam page is a single observation |
| Verification | Sourcify: `{"chainId":998,"supported":true}` | HIGH: `sourcify.dev/server/chains` |
| Faucet (official) | `https://app.hyperliquid-testnet.xyz/drip`: 1,000 mock USDC on HyperCore testnet. **Precondition: the same address has deposited on Hyperliquid mainnet.** Email/Privy logins get different addresses on mainnet and testnet, so export the wallet first. | HIGH: docs "Testnet faucet" |
| Faucet (EVM gas) | Chainstack: up to 1 HYPE per 24 h. Needs a Chainstack API key, and the address must hold ≥ 0.08 ETH on Ethereum mainnet. QuickNode faucet listed; its precondition was not checked. | MEDIUM: Chainstack faucet page; QuickNode LOW |
| Getting HYPE to the EVM | Buy testnet HYPE on HyperCore testnet spot with drip USDC, then "Transfer to/from EVM" or send HYPE to `0x2222…2222`. Only HYPE works through `0x2222`; any other asset sent there is lost. | HIGH: docs |
| Core account activation | A new HyperCore account pays 1 quote token (1 USDC) on its first inbound transfer | HIGH: docs "Activation gas fee" |
| Status (2026-09-30) | Live and producing blocks (head 65,637,418 at ~08:13Z). HIP-4 deployer actions are documented as "Testnet-only". A separate L2, Kinetiq's "Elysium" testnet, launched 2026-09-22 and settles on HyperEVM. It is not our target. | HIGH (live); Elysium LOW (news only) |

## Big Blocks and Deploy Sequencing (Research Q2)

### Exact action and how to send it
- The JSON: `{"type": "evmUserModify", "usingBigBlocks": true}` (`false` to revert). It is an **L1 action** POSTed to `https://api.hyperliquid-testnet.xyz/exchange`. It is not an EVM transaction.
- **Signing.** Msgpack(action) ‖ nonce(8 bytes) ‖ vault flag, then keccak. The result is signed as EIP-712 `Agent{source:"b" (testnet) | "a" (mainnet), connectionId}` under domain `{name:"Exchange", version:"1", chainId:1337, verifyingContract:0x0}`.
- **`cast` cannot build this**, because it needs msgpack.
- **Use the Python SDK:** `Exchange(wallet, constants.TESTNET_API_URL).use_big_blocks(True)`. This is in the SDK's 0.24.0 tag and its official example `examples/basic_evm_use_big_blocks.py`.
- **Success response:** `{"status":"ok","response":{"type":"default"}}`. This is the shape in the TS SDK schema.
- **Check it:** `cast rpc eth_usingBigBlocks <addr> --rpc-url $RPC` returns `true`/`false`. Verified working on the mainnet RPC.
- **Body shape.** Signed offline here with anvil's public test key; nothing was sent:
```json
{"action":{"type":"evmUserModify","usingBigBlocks":true},
 "nonce":1790755000000,
 "signature":{"r":"0x7252…abc0","s":"0x567f…6816","v":28},
 "vaultAddress":null,"expiresAfter":null}
```
- **Preconditions (docs).**
  - The sender must be an existing HyperCore user. An EOA becomes one by receiving a Core asset such as USDC.
  - The flag is per address and routes **all** of that address's EVM transactions to big blocks. That means ~60 s confirmations until it is unset.
  - So the deployer must turn it off after deploying, and the house MM / demo wallets must be different addresses.

### Recommended sequence (the owner runs every broadcasting step)
1. **Preflight (read-only).** `cast chain-id` = 998; deployer HYPE balance ≥ 0.05; `eth_usingBigBlocks` = false. Dry-run `forge script script/Deploy.s.sol` with `--disable-block-gas-limit` and without `--broadcast`, which prints gas per transaction.
2. **`make bigblocks-on`.** Runs the SDK, then re-checks `eth_usingBigBlocks` = true.
3. **`make deploy-testnet`.** CREATE transactions only (6 contracts incl. PoolVault deploying its 2 share tokens). Flags: `--broadcast --slow --disable-block-gas-limit --with-gas-price <3× eth_bigBlockGasPrice> --timeout 300 --verify --verifier sourcify`.
   - `--slow` sends one transaction at a time and waits for success. That is about one minute each in big-block mode, roughly 6–8 minutes total.
   - It also avoids the mempool's "next 8 nonces per address" limit.
   - If interrupted, rerun the same command with `--resume`.
4. **`make bigblocks-off`.** Check that `eth_usingBigBlocks` = false.
5. **`make configure-testnet`.** Wiring, roles/signers, params, MockUSDC seed, tranche seed deposits, demo markets. Small transactions, about one second each.
6. **`make smoke-testnet`.** Read-only asserts, then write `deployments/998.json` including `startBlock`.

Gas budget: a full deploy is ≈ 15–30M gas. At a 0.1–0.3 gwei max fee that is under 0.01 HYPE. Fund the deployer with 0.5 HYPE for headroom.

### Foundry / chain gotchas (each verified unless tagged)
| # | Gotcha | Evidence | Do this |
|---|--------|----------|---------|
| G1 | Foundry 1.8.3 default `evm_version` = `Osaka`; solc 0.8.37 default = `osaka` (adds `clz`). HyperEVM is Cancun. | Foundry `crates/config/src/lib.rs` v1.8.3; solc 0.8.37 docs | Pin `evm_version = "cancun"` in `[profile.default]`; profiles inherit it (checked with `forge config`) |
| G2 | `forge script` gas limit = simulated gas × 130% (`--gas-estimate-multiplier`, default 130). A 2.36M deploy asks for 3,066,848 and a 3M block rejects it. | Reproduced on `anvil --gas-limit 3000000`: "tx.gas_limit > env.block.gas_limit"; `--gas-estimate-multiplier 110` then passed (2,595,025) | Big blocks for deploys; keep the non-deploy call budget ≤ 2.0M |
| G3 | Fork simulation inherits `block.gaslimit = 3,000,000` from the HyperEVM RPC, so a >3M CREATE reverts in simulation even with big blocks on | Reproduced against testnet: `D3::run()` reverted at ~3.03M; passed with `--disable-block-gas-limit` | Always pass `--disable-block-gas-limit` on testnet deploys (not needed for configure) |
| G4 | Mempool accepts only the next 8 nonces per address; transactions older than 1 day are pruned | Docs (dual-block page) | `--slow` for deploys; never fire more than 8 unconfirmed transactions from one address (Phase 9 house MM too) |
| G5 | `eth_gasPrice` = next **small** block base fee; `eth_bigBlockGasPrice` = next big block base fee | Docs JSON-RPC page | Pass `--with-gas-price` from `eth_bigBlockGasPrice` × 3 in big-block mode |
| G6 | `eth_call`/`eth_getStorageAt`/`eth_getCode`/`eth_estimateGas` support latest only. Historical block tags are **silently answered with latest state**. `cast chain` fails ("invalid block height: 0"). | Docs; mainnet reads at head−5000 returned the latest WHYPE supply | Never rely on pinned-block forks for point-in-time state; use `cast chain-id`, not `cast chain` |
| G7 | `eth_getLogs`: ≤ 50 blocks per query, ≤ 4 topics | Docs | Write `startBlock` into deployments JSON; indexers (Phase 9) scan in 50-block chunks |
| G8 | Forge prints "Unsupported Chain IDs: 998 … Solidity ≥ 0.8.20 might not work (EIP-3855)" | Seen in the testnet dry run | Harmless: Cancun includes PUSH0 (Shanghai). Say so in the runbook. |
| G9 | HyperCore precompiles (`0x…0800`+) and CoreWriter exist on testnet but not on anvil | Docs; live `eth_getCode` | Phase 8 contracts must not call them |
| G10 | `block.number` interleaves small and big blocks; two blocks can share a timestamp | Docs; 121 blocks spanned 118 s | Use `block.timestamp` for every window (auction cutoff, revision window, withdrawal delay) |
| G11 | Error code 10055 = HyperCore/HyperEVM boundary errors (nonce, insufficient funds, duplicate hash, underpriced replacement) | Docs | Runbook troubleshooting entry |
| G12 | Pre-EIP-155 transactions are accepted | Docs | Never use a key that ever sent pre-155 transactions (irrelevant for fresh keys) |
| G13 | Default `transaction_timeout` 120 s | Foundry source | `--timeout 300` for big-block deploys |
| G14 | EIP-170 (24,576 B runtime) and EIP-3860 (49,152 B initcode) assumed to apply on Cancun | Not stated in the Hyperliquid docs (LOW) | Keep under both; `forge build --sizes` in CI |
| G15 | A non-big-block transaction with gas limit > 3M: rejected or stuck? | Unknown (LOW) | Never send one; preflight checks each transaction's estimate |

## Architecture Patterns

### Recommended Project Structure
```
contracts/
├── foundry.toml
├── Makefile                  # build/test/anvil + testnet-preflight, bigblocks-on/off, deploy/configure/smoke-testnet
├── RUNBOOK.md                # owner runbook (08-05)
├── src/
│   ├── MockUSDC.sol          # exists
│   ├── WIToken.sol           # becomes the junior share: mint/burn by PoolVault only (+ERC20Permit/ERC20Votes)
│   ├── SeniorShare.sol       # minimal ERC20, mint/burn by PoolVault only
│   ├── PoolVault.sol         # USDC custody, senior/junior NAV ledgers, reserve/cap, waterfall, request/claim withdrawals
│   ├── OracleAdapter.sol     # EIP-712 reports, calendar revision window, finalize, getFinal
│   ├── PolicyManager.sol     # markets, signed-quote pool policies, auction position ledger, settlement + claims
│   ├── BatchAuction.sol      # tick-bucketed open uniform-price call auction, lazy claims
│   ├── lib/Payoff.sol        # scalar L(x) in [0, 1e6]
│   └── interfaces/           # exist; revise per the table above
├── script/
│   ├── Deploy.s.sol          # CREATE only (big blocks on)
│   ├── Configure.s.sol       # wiring + params + seed (big blocks off)
│   ├── Smoke.s.sol           # read-only post-deploy checks
│   └── hl_big_blocks.py      # evmUserModify on|off|status, testnet-only guard
├── test/
│   ├── invariant/AuctionInvariants.t.sol  + handlers/AuctionHandler.sol
│   ├── invariant/PoolInvariants.t.sol     + handlers/PoolHandler.sol
│   ├── OracleSettlement.t.sol             # stale/unsigned/tampered/replayed reports; double settlement
│   ├── AuctionParity.t.sol                # engine fixture → identical clearing
│   └── fixtures/auction_cases.json        # written by the Phase 7 Python engine
└── deployments/{31337,998}.json
```

### Pattern 1: The scalar unit (one instrument for policies and residual positions)
**What:** A market is `(indexId, day, lo, hi)`, and `marketId = keccak256(abi.encode(...))`. Per unit, long receives `L(x) = clamp((x − lo)·1e6 / (hi − lo), 0, 1e6)` USDC base units and short receives `1e6 − L(x)`. Price ticks are cents: a bid at tick t escrows `t·10_000` per unit and an offer escrows `(100 − t)·10_000`.
**Why:** Each long/short pair locks exactly `1e6`. The only division is the single floor inside `L(x)`, and short takes the complement, so payouts sum to `qty·1e6` exactly. There is no rounding sink anywhere.
**Mapping:**
- CappedLinearAbove(K, C) = long on `[K, K+C]`.
- CappedLinearBelow(K, C) = short on `[K−C, K]`.
- Indicator above K = `[K, K+1]`.
- A residual "metro minus station" with range ±R = `[−R, +R]`.

HIP-4 outcome markets use the same idea (Yes → `settleFraction`, No → `1 − settleFraction`), which gives a clean port if a HIP-4 partner ever lists it.

### Pattern 2: Open tick-bucketed uniform-price call auction with price-time priority and lazy claims
**What:** One auction per market with a fixed `cutoff` timestamp. The flow:
1. **Place.** Orders escrow USDC and add their qty to `levels[market][tick]`. Each order stores `ahead`, the qty already queued at that tick.
2. **Cancel.** Not allowed, because cancelling would corrupt the `ahead` offsets. Keep epochs short instead.
3. **Clear** (anyone, after cutoff), with no loop over orders:
   - Build `D[p]` (bids at ticks ≥ p) and `S[p]` (offers at ticks ≤ p).
   - Pick `p*` to maximize `V = min(D, S)`, then minimize `|D − S|`, then take the midpoint of the tied range. That range is contiguous, because V is unimodal and `D − S` is monotone.
   - Record the marginal bid tick `tb` (highest tick with `D[tb] ≥ Q*`) and its marginal fill `mb = Q* − D[tb+1]`.
   - Record the marginal offer tick `to` (lowest tick with `S[to] ≥ Q*`) and `mo = Q* − S[to−1]`.
   - Transfer `Q*·1e6` to PolicyManager as that market's collateral.
4. **Claim.** Each order computes its own fill in O(1):
   - A bid fills fully if `tick > tb`, fills `clamp(mb − ahead, 0, qty)` if `tick == tb`, and gets nothing otherwise. Offers mirror this at `to`.
   - Filled bids pay `p*`; filled offers post `100 − p*`. Each order gets back its escrow minus its cost, and its position is recorded in PolicyManager.

**Guarantees:** Bid fills sum to `D[tb+1] + mb = Q*` exactly, and offer fills to `Q*` exactly. `tb ≥ p* ≥ to`, so no limit price is violated. No order marketable at `p*` stays unfilled on both sides at once, which would contradict maximal volume. Clearing reads 99 slots (bid and offer qty packed into one slot per tick). Measured 473,753 gas worst case in the scratch prototype, well inside a small block.
**Why open, not sealed:** It is the simplest correct design for the 2-day window. Everyone pays the same price, so ordering inside the batch has little value. The residual risk is someone reading the book and "sniping" orders in just before cutoff. Commit–reveal is the v2 fix.
**Parity:** The Phase 7 Python engine must implement the identical rule: ticks 1..99, volume → imbalance → midpoint, price-time at the marginal tick. Assert parity from a fixture.

### Pattern 3: One PoolVault, two share classes, junior-first waterfall
**What:**
- **Ledgers.** Internal `seniorAssets` and `juniorAssets`. Never use `balanceOf`, which is exposed to donation and inflation attacks.
- **Share tokens.** `SeniorShare` and `WIToken` are minted and burned only by the vault, which deploys both in its constructor, so there are no wiring transactions. Share math copies OZ ERC-4626's virtual offset: `shares = assets·(supply + 10^6)/(trancheAssets + 1)`.
- **Losses:** `j = min(loss, juniorAssets)`, `s = loss − j`. Senior is touched only when junior reaches 0.
- **Premium income** is split by `seniorPremiumBps`; junior gets the remainder.
- **Exposure cap:** `reserved ≤ capBps/1e4 × (seniorAssets + juniorAssets)`. It is checked on every `reserve` and every withdrawal claim. With `capBps ≤ 10_000` it survives losses by construction: `R − M ≤ f(C − X)` whenever `X ≤ M` and `f ≤ 1`.
- **Withdrawals** are request-then-claim. The shares are priced at claim time, so a loss realized during the delay hits the leaver too. The claim reverts if it would break the cap.

**Why not ERC-4626:** Its withdraw is synchronous, there would be two custody points, and nothing in the prototype needs outside composability. Borrow OZ's rounding and virtual offset, not the interface.

### Pattern 4: EIP-712 signed-report oracle, calendar revision window, finalize
**What:** `Report(bytes32 indexId,uint32 day,int64 value,uint16 revision,uint64 asOf)`, signed by an allow-listed reporter key and posted by anyone (a relayer). `day` = UTC days since epoch.

`post` accepts a report only if all of these hold:
- not yet finalized;
- `asOf ≥ dayEnd`, so no value exists for an unfinished day;
- `asOf ≤ now`;
- `now − asOf ≤ maxReportAge`;
- `now < dayEnd + revisionWindow`;
- `revision >` the last accepted revision;
- the signer is allow-listed (`ECDSA.recover` over `_hashTypedDataV4`).

`finalize` works only after `dayEnd + revisionWindow` and only if something was posted. `getFinal` reverts unless the value is finalized, and settlement reads only `getFinal`. The EIP-712 domain (chainId + verifyingContract) blocks cross-chain and cross-deployment replay.
**Why a calendar anchor:** "Settle on the latest value published by D+W" is known when the policy is sold. That is the "stated revision policy" PROJECT.md asks for, and it matches nClimGrid's prelim-then-revised cadence. Phase 7 picks W; testnet demo deploys use a short W via constructor argument.
**Missing data:** If nothing is posted by `dayEnd + W`, `finalize` reverts. SPEC must state the fallback (recommended: after a grace period, the owner calls `void(indexId, day)`; policies refund the premium and pairs refund entry collateral).

### Pattern 5: Signed quotes for pool-backed policies
**What:** `buyPolicy(Quote q, bytes sig)` with `Quote{market, buyer, units, premium, expiry, nonce}`, signed by the `quoter` (the house-MM risk-engine key). It checks `msg.sender == q.buyer`, `now ≤ q.expiry`, that the nonce is unused, and that the signer is the quoter. It then pulls the premium, calls `pool.creditPremium`, and calls `pool.reserve(units·1e6)`.
**Why:** Without it the caller sets the premium (the 08-01 stub). This is also the on-chain half of the "house hedge" default path (PROT-05).

### Pattern 6: Admin: Ownable2Step + Pausable, pause new risk, never exits; no upgradeability
- `Ownable2Step` on every contract; the owner is the deployer EOA.
- `whenNotPaused` on `placeOrder`, `buyPolicy` and `deposit` only. `claim`, `settle`, `finalize`, `requestWithdraw` and `claimWithdraw` stay open.
- One-time setters (`setPolicyManager`, `setAuction`) that revert once set.
- Risk params (`capBps`, `seniorPremiumBps`, `withdrawDelay`, signer/quoter sets) are owner-set. Governance by WI votes is out of scope beyond the token's ERC20Votes checkpoints.
- No proxies. A change means redeploy plus new `deployments/998.json`.
- `ReentrancyGuard` (storage version) on functions that move USDC, plus checks-effects-interactions. Transient-storage guards should work on Cancun but add nothing here.

### Pattern 7: Small-block gas budget
Every non-deploy external function must use ≤ 2.0M gas worst case, so that ×1.3 < 3M. That rules out loops over orders, policies or holders; everything is per-id and pull-based. Test it on anvil: deploy at the default 30M limit, run `cast rpc evm_setBlockGasLimit 0x2dc6c0` (verified working), then run the whole E2E flow.

### Anti-Patterns to Avoid
- **Looping over orders/policies in `clear`/`settle`.** It exceeds 3M quickly. Use lazy claims.
- **`totalAssets = usdc.balanceOf(this)`.** Donations move the share price. Use internal ledgers.
- **Letting the caller choose the premium or limit price off-grid.** Silent underpricing and rounding leaks.
- **Pro-rata rounding without a dust sink.** Long ≠ short and collateral no longer adds up.
- **Leaving the deployer in big-block mode**, or reusing it as the house MM. Every transaction then waits ~60 s.
- **Fixed-point mismatches between the engine and the contract** (°F×10 vs °F×100, int64 vs int256 in the EIP-712 type string). Freeze scales in SPEC.md and assert them in the parity fixture.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Signature verification / EIP-712 domain | Custom `ecrecover` + domain hashing | OZ `EIP712` + `ECDSA.recover` (low-s, reverts on malformed) | Malleability, chain-id caching on forks. OZ 5.7: name/version must be ≤ 31 bytes. |
| Big-block toggle signing | msgpack + phantom-agent code | `hyperliquid-python-sdk==0.24.0` `use_big_blocks` | Byte-exact action hashing; the SDK is Hyperliquid's own |
| Share math / rounding | Ad-hoc `assets * supply / total` | OZ `Math.mulDiv` with ERC-4626's virtual offset | First-depositor inflation, rounding direction |
| Token transfers | Raw `transfer` bool checks | OZ `SafeERC20` | Non-standard tokens (harmless for MockUSDC but free) |
| Governance weight | Custom snapshots | OZ `ERC20Votes` (+ `ERC20Permit`) on WI | Checkpointing edge cases |
| Deterministic deploy / address book | Hand-copied addresses | Script writes `deployments/<chainId>.json`; `vm.parseJsonAddress` in Configure | Copy errors between scripts and portal |
| Invariant harness | Hand-written random loops | forge `StdInvariant` + handler + ghost variables | Shrinking, replay (`failure_persist_dir`), metrics |
| Key storage | `DEPLOYER_PRIVATE_KEY` in shell env | `cast wallet import wi-deployer --interactive` → `--account wi-deployer` | Encrypted V3 keystore; the Python toggle decrypts the same file with `eth_account` |

**Key insight:** The hard money bugs here come from rounding and unit mismatches, not algorithms. Choose instruments and ticks so every amount is an exact integer, and custom math shrinks to one floor.

## Common Pitfalls

### Pitfall 1: Compiling for Osaka/Prague
**What goes wrong:** Bytecode can contain opcodes Cancun lacks (e.g., CLZ). It deploys, then reverts at runtime.
**Why it happens:** Foundry 1.8.3 and solc ≥ 0.8.3x default to `osaka`.
**How to avoid:** `evm_version = "cancun"` in `[profile.default]`. Check with `forge config | grep evm_version` under every profile.
**Warning signs:** `forge config` shows osaka; an unknown `INVALID` opcode revert on testnet only.

### Pitfall 2: Deploy transaction too big for the block it lands in
**What goes wrong:** "tx.gas_limit > env.block.gas_limit", a revert in simulation, or a transaction that never mines.
**Why:** The 130% multiplier (G2) plus a fork simulation capped at 3M (G3), or big blocks not enabled.
**How to avoid:** Preflight dry-run prints gas per transaction. Big blocks on, `--disable-block-gas-limit` on deploys. Plan B: `--gas-estimate-multiplier 110` with contracts under ~2.7M.
**Warning signs:** Any contract over ~9.5 KB runtime (`forge build --sizes`).

### Pitfall 3: Mempool 8-nonce limit
**What goes wrong:** A batch deploy or MM loop fires transactions 9..n, which are rejected; forge reports a failure mid-script.
**How to avoid:** `--slow`; the house MM (Phase 9) waits for receipts.

### Pitfall 4: Auction value leak through rounding or cancels
**What goes wrong:** Long ≠ short, or collateral ≠ `Q*·1e6`, leaving the market insolvent at settlement or with dust stranded.
**How to avoid:** Integer ticks, price-time marginal allocation, no cancels, market collateral moved at `clear`, per-market collateral accounting in PolicyManager (underflow = revert).
**Warning signs:** Auction contract balance ≠ Σ unclaimed (escrow − cost) in the invariant run.

### Pitfall 5: Settling on an unfinal, stale, or foreign oracle value
**What goes wrong:** Payout on a preliminary value later revised, a replayed report from anvil, or a value for the wrong day.
**How to avoid:** Pattern 4 checks; settlement calls only `getFinal`; the domain includes chainId + contract.

### Pitfall 6: Exit ahead of a known loss
**What goes wrong:** An oracle value is posted during the revision window, and LPs who see the coming loss withdraw first.
**How to avoid:** Request/claim with the delay ≥ revision window, shares priced at claim, cap re-checked at claim. Remaining unfairness: free capital can still leave, which is acceptable for the prototype; note it in the token memo.

### Pitfall 7: Explorer links that go nowhere or to spam
**What goes wrong:** The portal or runbook links `testnet.purrsec.com` (dead; the parent domain serves gambling spam).
**How to avoid:** No explorer in the chain config. Link Sourcify (`https://repo.sourcify.dev/998/<address>`) for verified sources, and use `cast` for transactions.

### Pitfall 8: EIP-712 type drift between the engine and the contract
**What goes wrong:** Engine-signed reports or quotes never verify, or verify a different struct.
**How to avoid:** One canonical type string per struct in SPEC.md. The Foundry test uses `vm.eip712HashStruct(typeString, abi.encode(...))` and the Python engine's digest for the same fixture; assert equality.

### Pitfall 9: Agents trying to probe the official testnet RPC from the sandbox
**What goes wrong:** DNS or TLS failures in this environment look like a testnet outage.
**How to avoid:** Read-only agent checks use `https://rpcs.chain.link/hyperevm/testnet` sparingly (it returns 429 on bursts). The owner's machine uses the official RPC.

## Code Examples

### foundry.toml (validated with `forge config` under Foundry 1.8.3)
```toml
[profile.default]
src = "src"
out = "out"
libs = ["lib"]
test = "test"
script = "script"
solc_version = "0.8.37"          # latest; 0.8.28 also works. NEVER drop the next line.
evm_version = "cancun"           # HyperEVM = Cancun without blobs; Foundry/solc default is osaka
optimizer = true
optimizer_runs = 200
bytecode_hash = "ipfs"           # default; keeps Sourcify full matches
# no eth_rpc_url in default: it would make `forge test` fork (08-01 finding)
fs_permissions = [
  { access = "read-write", path = "./deployments" },
  { access = "read", path = "./test/fixtures" },
  { access = "read", path = "./broadcast" },
]

[fuzz]
runs = 1000

[invariant]
runs = 256
depth = 100                      # default 500; 100 keeps CI fast with 4–6 handler actions
fail_on_revert = false           # handlers use try/catch; reverts are expected (cap, window)
show_metrics = true

[rpc_endpoints]
anvil = "http://127.0.0.1:8545"
hyperevm_testnet = "https://rpc.hyperliquid-testnet.xyz/evm"
hyperevm_testnet_chainlink = "https://rpcs.chain.link/hyperevm/testnet"   # read-only checks; rate-limited

[profile.hyperevm_testnet]
chain_id = 998                   # forge shows it as "hyperliquid-testnet"; inherits evm_version etc.
```

### Deploy.s.sol skeleton (CREATE only; run with big blocks ON)
```solidity
// Source: pattern from forge-std 1.16.2 Script + Vm (readCallers, envOr, serialize*, writeJson)
contract Deploy is Script {
    function run() external {
        uint256 startBlock = block.number;          // lower bound for log scans (eth_getLogs ≤ 50 blocks/query)
        vm.startBroadcast();                        // signer = --account (testnet) or --private-key (anvil)
        (, address deployer,) = vm.readCallers();
        address signer = vm.envOr("ORACLE_SIGNER", deployer);   // owner may supply an unfunded signing key's address
        address quoter = vm.envOr("QUOTER", deployer);
        uint64 window  = uint64(vm.envOr("REVISION_WINDOW_S", uint256(1 hours)));

        MockUSDC usdc        = new MockUSDC();
        OracleAdapter oracle = new OracleAdapter(deployer, signer, window);
        PoolVault pool       = new PoolVault(IERC20(address(usdc)), deployer);  // deploys WIToken + SeniorShare inside
        PolicyManager pm     = new PolicyManager(IERC20(address(usdc)), pool, oracle, quoter, deployer);
        BatchAuction auction = new BatchAuction(IERC20(address(usdc)), pm, deployer);
        vm.stopBroadcast();

        string memory k = "d";
        vm.serializeUint(k, "chainId", block.chainid);
        vm.serializeUint(k, "startBlock", startBlock);
        vm.serializeAddress(k, "deployer", deployer);
        vm.serializeAddress(k, "MockUSDC", address(usdc));
        vm.serializeAddress(k, "OracleAdapter", address(oracle));
        vm.serializeAddress(k, "PoolVault", address(pool));
        vm.serializeAddress(k, "WIToken", address(pool.junior()));
        vm.serializeAddress(k, "SeniorShare", address(pool.senior()));
        vm.serializeAddress(k, "PolicyManager", address(pm));
        string memory json = vm.serializeAddress(k, "BatchAuction", address(auction));
        vm.writeJson(json, string.concat("./deployments/", vm.toString(block.chainid), ".json"));
    }
}
```
`Configure.s.sol` runs with big blocks OFF:
1. Read the addresses with `vm.readFile` + `vm.parseJsonAddress(json, ".PoolVault")`.
2. `vm.startBroadcast()`.
3. `pool.setPolicyManager(pm)`, then `pm.setAuction(auction)`.
4. Set `capBps`, `seniorPremiumBps` and `withdrawDelay` from env with defaults.
5. `usdc.mint(houseMM, …)` and seed deposits: junior first, then senior.
6. `pm.createMarket(...)` for the demo markets. The house MM address is an env var; it defaults to the deployer only on anvil.

### hl_big_blocks.py (owner runs; testnet only; nothing here ever touches mainnet)
```python
# Source: hyperliquid-python-sdk 0.24.0 Exchange.use_big_blocks + examples/basic_evm_use_big_blocks.py
# Run: uv run --no-project --python 3.12 --with hyperliquid-python-sdk==0.24.0 python script/hl_big_blocks.py on|off|status
import getpass, json, os, sys, urllib.request
from eth_account import Account
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants

API = constants.TESTNET_API_URL            # hard-coded: never MAINNET_API_URL
RPC = os.environ.get("HYPEREVM_TESTNET_RPC", "https://rpc.hyperliquid-testnet.xyz/evm")
KEYSTORE = os.path.expanduser(os.environ.get("DEPLOYER_KEYSTORE", "~/.foundry/keystores/wi-deployer"))

def using_big_blocks(addr: str) -> bool:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_usingBigBlocks", "params": [addr]}).encode()
    req = urllib.request.Request(RPC, body, {"content-type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=20))["result"]

cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
acct = Account.from_key(Account.decrypt(json.load(open(KEYSTORE)), getpass.getpass("keystore password: ")))
print("deployer", acct.address, "usingBigBlocks:", using_big_blocks(acct.address))
if cmd in ("on", "off"):
    print(Exchange(acct, API).use_big_blocks(cmd == "on"))   # expect {'status': 'ok', 'response': {'type': 'default'}}
    print("usingBigBlocks now:", using_big_blocks(acct.address))
```
If the response is an error mentioning the user or account, the deployer is not yet a HyperCore user. Send it testnet USDC on HyperCore first (runbook step 4).

### Makefile testnet targets (owner-only targets print a warning; dry run by default)
```make
TESTNET_RPC      ?= https://rpc.hyperliquid-testnet.xyz/evm
DEPLOYER_ACCOUNT ?= wi-deployer
DEPLOYER_ADDRESS ?=
BIGBLOCKS = uv run --no-project --python 3.12 --with hyperliquid-python-sdk==0.24.0 python script/hl_big_blocks.py
BIG_GAS  = $$(( $$(cast to-dec $$(cast rpc eth_bigBlockGasPrice --rpc-url $(TESTNET_RPC) | tr -d '"')) * 3 ))
TN_SIM = FOUNDRY_PROFILE=hyperevm_testnet forge script --rpc-url $(TESTNET_RPC) --sender $(DEPLOYER_ADDRESS)
TN     = $(TN_SIM) --account $(DEPLOYER_ACCOUNT)

testnet-preflight:   # read-only, no key needed
	cast chain-id --rpc-url $(TESTNET_RPC)                       # 998
	cast balance $(DEPLOYER_ADDRESS) --ether --rpc-url $(TESTNET_RPC)
	cast rpc eth_usingBigBlocks $(DEPLOYER_ADDRESS) --rpc-url $(TESTNET_RPC)
	$(TN_SIM) script/Deploy.s.sol --disable-block-gas-limit       # simulation only (no --broadcast): gas per tx
bigblocks-on:  ; $(BIGBLOCKS) on
bigblocks-off: ; $(BIGBLOCKS) off
deploy-testnet:      # OWNER ONLY. Big blocks must be ON.
	$(TN) script/Deploy.s.sol --broadcast --slow --disable-block-gas-limit \
	  --with-gas-price $(BIG_GAS) --timeout 300 --verify --verifier sourcify
configure-testnet:   # OWNER ONLY. Big blocks OFF.
	$(TN) script/Configure.s.sol --broadcast --slow
smoke-testnet:
	FOUNDRY_PROFILE=hyperevm_testnet forge script script/Smoke.s.sol --rpc-url $(TESTNET_RPC)
```
`deploy-anvil` should follow the same two-script flow: default 30M block → Deploy → `cast rpc evm_setBlockGasLimit 0x2dc6c0` → Configure → E2E.

### OracleAdapter core
Compiled and tested in a scratch project against OZ 5.7 with `EIP712("wi-oracle","1")`:
- The happy path finalizes.
- `getFinal` reverts before finalize.
- A report signed under chain 31337 reverts `BadSigner` after `vm.chainId(998)`.
- 1,000 fuzzed tampered values revert.
- `vm.eip712HashStruct(typeString, abi.encode(...))` equals the contract's struct hash.
```solidity
// Source: OZ 5.7 EIP712/ECDSA usage pattern
bytes32 constant REPORT_TYPEHASH =
    keccak256("Report(bytes32 indexId,uint32 day,int64 value,uint16 revision,uint64 asOf)");
struct Obs { int64 value; uint16 revision; uint64 asOf; bool posted; bool finalized; }
mapping(bytes32 => mapping(uint32 => Obs)) internal obs;

function post(bytes32 indexId, uint32 day, int64 value, uint16 revision, uint64 asOf, bytes calldata sig) external {
    Obs storage o = obs[indexId][day];
    uint256 dayEnd = (uint256(day) + 1) * 1 days;
    if (o.finalized) revert Finalized();
    if (asOf < dayEnd || asOf > block.timestamp) revert BadAsOf();          // no value for an unfinished day / future
    if (block.timestamp - asOf > maxReportAge) revert Stale();
    if (block.timestamp >= dayEnd + revisionWindow) revert WindowClosed();
    if (o.posted && revision <= o.revision) revert NotNewer();
    bytes32 digest = _hashTypedDataV4(keccak256(abi.encode(REPORT_TYPEHASH, indexId, day, value, revision, asOf)));
    if (!isSigner[ECDSA.recover(digest, sig)]) revert BadSigner();
    (o.value, o.revision, o.asOf, o.posted) = (value, revision, asOf, true);
    emit Posted(indexId, day, value, revision);
}
function finalize(bytes32 indexId, uint32 day) external {
    Obs storage o = obs[indexId][day];
    if (!o.posted || o.finalized) revert NothingToFinalize();
    if (block.timestamp < (uint256(day) + 1) * 1 days + revisionWindow) revert WindowOpen();
    o.finalized = true;
    emit Finalized(indexId, day, o.value);
}
function getFinal(bytes32 indexId, uint32 day) external view returns (int64) {
    Obs storage o = obs[indexId][day];
    if (!o.finalized) revert NotFinal();
    return o.value;
}
```

### BatchAuction clear + claim core
```solidity
uint256 constant TICKS = 99; uint256 constant TICK = 10_000; uint256 constant UNIT = 1_000_000;
struct Level { uint128 bid; uint128 offer; }                       // one slot per tick
struct Book  { uint64 cutoff; bool cleared; uint8 pStar; uint8 tb; uint8 to; uint128 qStar; uint128 mb; uint128 mo; }
struct Order { address trader; bytes32 market; bool isBid; uint8 tick; bool claimed; uint128 qty; uint128 ahead; }
mapping(bytes32 => Level[TICKS + 1]) internal levels;              // ticks 1..99

function placeOrder(bytes32 m, bool isBid, uint8 tick, uint128 qty) external whenNotPaused nonReentrant returns (uint256 id) {
    Book storage b = books[m];
    if (b.cutoff == 0 || block.timestamp >= b.cutoff) revert Closed();
    if (tick == 0 || tick > TICKS || qty == 0) revert BadOrder();
    usdc.safeTransferFrom(msg.sender, address(this), uint256(qty) * (isBid ? tick : 100 - tick) * TICK);
    Level storage l = levels[m][tick];
    uint128 ahead = isBid ? l.bid : l.offer;
    if (isBid) l.bid = ahead + qty; else l.offer = ahead + qty;
    orders[id = ++nextId] = Order(msg.sender, m, isBid, tick, false, qty, ahead);
}

function clear(bytes32 m) external nonReentrant {
    Book storage b = books[m];
    if (b.cutoff == 0 || block.timestamp < b.cutoff) revert Open();
    if (b.cleared) revert Cleared();
    b.cleared = true;
    uint256[TICKS + 2] memory D; uint256[TICKS + 1] memory O;       // D[p] = bids at ticks >= p
    for (uint256 p = TICKS; p >= 1; --p) { Level memory l = levels[m][p]; D[p] = D[p + 1] + l.bid; O[p] = l.offer; }
    uint256 S; uint256 bestV; uint256 bestImb = type(uint256).max; uint256 lo; uint256 hi;
    for (uint256 p = 1; p <= TICKS; ++p) {
        S += O[p];
        uint256 v = D[p] < S ? D[p] : S;
        uint256 imb = D[p] > S ? D[p] - S : S - D[p];
        if (v > bestV || (v == bestV && v != 0 && imb < bestImb)) { (bestV, bestImb, lo, hi) = (v, imb, p, p); }
        else if (v == bestV && v != 0 && imb == bestImb) { hi = p; }
    }
    if (bestV == 0) return;                                          // nothing crosses: all orders refund in full
    uint256 tb = TICKS; while (D[tb] < bestV) --tb;                  // highest bid tick reaching Q*
    uint256 below; uint256 to = 1; while (below + O[to] < bestV) { below += O[to]; ++to; }  // lowest offer tick
    b.pStar = uint8((lo + hi) / 2); b.qStar = uint128(bestV);        // assign fields one by one: a 6-tuple
    b.tb = uint8(tb); b.mb = uint128(bestV - D[tb + 1]);             // assignment is "stack too deep" (hit in the probe)
    b.to = uint8(to); b.mo = uint128(bestV - below);
    usdc.safeTransfer(address(pm), bestV * UNIT);                    // market collateral: exactly Q* × $1
    pm.fundMarket(m, bestV * UNIT);
}

function claim(uint256 id) external nonReentrant {
    Order storage o = orders[id]; Book storage b = books[o.market];
    if (!b.cleared) revert NotCleared();
    if (o.claimed) revert Claimed();
    o.claimed = true;
    uint256 fill;
    if (b.qStar != 0) {
        if (o.isBid) fill = o.tick > b.tb ? o.qty : (o.tick == b.tb ? _slice(b.mb, o.ahead, o.qty) : 0);
        else         fill = o.tick < b.to ? o.qty : (o.tick == b.to ? _slice(b.mo, o.ahead, o.qty) : 0);
    }
    uint256 escrow = uint256(o.qty) * (o.isBid ? o.tick : 100 - o.tick) * TICK;
    uint256 cost   = fill * (o.isBid ? b.pStar : 100 - b.pStar) * TICK;   // cost ≤ escrow because tick ≥ p* (bid) / ≤ p* (offer)
    if (fill != 0) pm.recordFill(o.market, o.trader, o.isBid, fill);
    if (escrow > cost) usdc.safeTransfer(o.trader, escrow - cost);
}
function _slice(uint256 marginal, uint256 ahead, uint256 qty) private pure returns (uint256) {
    if (marginal <= ahead) return 0;
    uint256 left = marginal - ahead; return left < qty ? left : qty;
}
```
The costs of all filled orders add up to exactly `Q*·p*·TICK + Q*·(100−p*)·TICK = Q*·UNIT`, which is the amount moved at `clear`. After every order in a market has claimed, the auction's balance for that market is exactly 0.

**Checked in a scratch project (not the repo), using this exact clear/claim logic with a stub PolicyManager:**
- 3,000 fuzz runs of up to 40 random orders, with forced clustering at ticks 40–42 to create ties.
- Result: long == short == `qStar`, collateral == `qStar·1e6`, auction balance 0 after all claims, and no fill breaks its limit price.
- A hand case also passed: bids 10 @ 60 vs offers 5 @ 40 gives `p* = 50`, `tb = 60`, `to = 40`, FIFO fill 5.
- Gas (isolated calls): `clear` 473,753 worst case (all 99 ticks populated both sides); `placeOrder` 125–177k.

### PoolVault waterfall core
Compiles against OZ 5.7 in the scratch project, including a vault that deploys both share tokens in its constructor.
```solidity
function reserve(uint256 amount) external onlyPM {
    if ((reserved + amount) * 10_000 > capital() * capBps) revert ExposureCap();
    reserved += amount;
}
function creditPremium(uint256 amount) external onlyPM {          // USDC already transferred in by PolicyManager
    uint256 s = amount * seniorPremiumBps / 10_000;
    seniorAssets += s; juniorAssets += amount - s;
}
function settle(uint256 released, uint256 loss, address to) external onlyPM nonReentrant {
    reserved -= released;                                          // loss ≤ released: payout ≤ max payout
    uint256 j = loss < juniorAssets ? loss : juniorAssets;          // junior absorbs first
    uint256 s = loss - j;                                           // senior only after junior is exhausted
    juniorAssets -= j; seniorAssets -= s;                           // underflow reverts; unreachable under the cap
    if (loss != 0) usdc.safeTransfer(to, loss);
    emit LossAbsorbed(loss, j, s);
}
function deposit(Tranche t, uint256 assets) external whenNotPaused nonReentrant returns (uint256 shares) {
    IShare tok = t == Tranche.Senior ? IShare(address(senior)) : IShare(address(junior));
    uint256 a = t == Tranche.Senior ? seniorAssets : juniorAssets;
    shares = Math.mulDiv(assets, tok.totalSupply() + 1e6, a + 1);   // OZ ERC-4626 virtual offset (10**6)
    usdc.safeTransferFrom(msg.sender, address(this), assets);
    if (t == Tranche.Senior) seniorAssets += assets; else juniorAssets += assets;
    tok.mint(msg.sender, shares);
}
```

### Invariant handler skeleton (forge-std 1.16.2)
```solidity
contract PoolHandler is Test {
    uint256 public seniorHitWhileJuniorPositive;           // must stay 0
    mapping(uint256 => uint256) public paidPerPolicy;       // ≤ maxPayout, set once
    uint256 public settleSuccesses;
    // actions: deposit(tranche, amt, actor) · buy(units, market) [quote signed with vm.sign(quoterPk, digest)]
    //          postAndFinalize(market, x) [vm.warp past window] · settle(policySeed) · requestWithdraw · claimWithdraw
    function settle(uint256 seed) external {
        uint256 id = bound(seed, 1, pm.lastPolicyId());
        (uint256 j0, uint256 s0) = (pool.juniorAssets(), pool.seniorAssets());
        try pm.settlePolicy(id) returns (uint256 paid) {
            if (paidPerPolicy[id] != 0 && paid != 0) revert("paid twice");
            paidPerPolicy[id] += paid; settleSuccesses++;
            if (pool.seniorAssets() < s0 && pool.juniorAssets() != 0) seniorHitWhileJuniorPositive++;
            j0;                                              // (j0 used in a richer check: junior drop == min(loss, j0))
        } catch {}
    }
}
contract PoolInvariants is StdInvariant, Test {
    function setUp() public { /* deploy; handler = new PoolHandler(...); targetContract(address(handler)); */ }
    function invariant_exposureCap() public view { assertLe(pool.reserved() * 10_000, pool.capital() * pool.capBps()); }
    function invariant_juniorFirst() public view { assertEq(handler.seniorHitWhileJuniorPositive(), 0); }
    function invariant_poolHoldsItsLedger() public view {
        assertEq(usdc.balanceOf(address(pool)), pool.seniorAssets() + pool.juniorAssets()); // handler never donates
    }
}
```

### Wallet / viem chain config for testnet (Phase 10 reference)
```ts
// viem 2.57.1 exports hyperliquidEvmTestnet (id 998, no explorer, no multicall3 entry). Multicall3 IS deployed.
import { defineChain } from 'viem'
import { hyperliquidEvmTestnet } from 'viem/chains'
export const wiTestnet = defineChain({
  ...hyperliquidEvmTestnet,
  contracts: { multicall3: { address: '0xcA11bde05977b3631167028862bE2a173976CA11' } },
})
// wallet_addEthereumChain: { chainId: '0x3e6', chainName: 'Hyperliquid EVM Testnet',
//   nativeCurrency: { name: 'HYPE', symbol: 'HYPE', decimals: 18 },
//   rpcUrls: ['https://rpc.hyperliquid-testnet.xyz/evm'] }   // no blockExplorerUrls (none reliable)
```

## Money-Failure Tests (Research Q5): only these

Per AGENTS.md: these five and nothing else. No mirror tests, no tests asserting constants or wiring.

| # | Failure that loses money | Test form | Handler actions / inputs | Assertion (property, not restatement) |
|---|--------------------------|-----------|--------------------------|----------------------------------------|
| M1 | Clearing mints or burns value | Invariant (AuctionHandler) + parity fixture | `placeOrder(actor, side, tick∈[1,99], qty∈[1,1e6])`, `warpPastCutoff`, `clear`, `claim(orderSeed)` across 2–3 markets | (a) `usdc.balanceOf(auction) == ghostEscrowIn − ghostRefunds − Σ Q*·1e6` (exact). (b) After all claims in a cleared market: Σ long fills == Σ short fills == `qStar`, and `pm.marketCollateral(m) == qStar·1e6`. (c) No filled bid with tick < p*, no filled offer with tick > p*. (d) Never an unfilled bid marketable at p* and an unfilled offer marketable at p* at the same time. (e) `AuctionParity.t.sol`: for each case in `fixtures/auction_cases.json` (from the Phase 7 engine), on-chain `(pStar, qStar, fill per order)` equals the engine's exactly. |
| M2 | Waterfall hits senior while junior still has capital (see Open Q4 on the phrasing) | Invariant (PoolHandler) | deposits both tranches, buys, oracle post+finalize with fuzzed `x`, settles, withdrawals | (a) Ghost counter "senior decreased while junior > 0 after the loss" == 0. (b) On each loss, junior drop == `min(loss, juniorBefore)`. (c) `usdc.balanceOf(pool) == seniorAssets + juniorAssets` (exact in the handler world). |
| M3 | Exposure cap exceeded | Invariant (PoolHandler) + fuzz on auction escrow | same as M2 plus `claimWithdraw` | (a) `reserved·1e4 ≤ capital·capBps` after every call, including withdrawals and losses. (b) Each auction order's escrow ≥ its worst-case loss (tick·1e4 or (100−tick)·1e4 per unit), so positions are fully collateralized. |
| M4 | Settlement on stale, unsigned, tampered, replayed or unfinal oracle values | Fuzz + unit tests (`OracleSettlement.t.sol`) | `vm.sign` with fuzzed non-signer keys; fuzz-mutate each report field after signing; `vm.chainId(998)` on a 31337-signed report; `asOf` < dayEnd, > now, older than `maxReportAge`; revision ≤ last; post after window; settle before finalize | Every one reverts with its specific error. `settlePolicy` before `finalize` reverts. After finalize, no later report changes `getFinal`. |
| M5 | Double settlement / double claim | Invariant (PoolHandler, AuctionHandler) + unit | repeated `settlePolicy(id)`, `claimPosition(m)`, `claim(orderId)` with random ids | Paid per policy ≤ `units·1e6` and set at most once. A second call reverts. Σ payouts per market ≤ `marketCollateral` funded (per-market underflow = revert). |

**Foundry patterns:**
- Handler-based invariants (`targetContract(handler)`), with ghost variables in the handler.
- `bound()` for inputs, and `try/catch` in handlers with `fail_on_revert = false`.
- `vm.warp` for windows (or `[invariant] max_time_delay` if a handler wants random time jumps).
- `vm.sign(pk, digest)` for reports and quotes; `vm.eip712HashStruct` to cross-check digests against the engine.
- Persisted failures replay automatically (`failure_persist_dir`).

### Pre-registered acceptance rules (written before any number is produced)
- **R1** M1–M5 invariants hold at `runs = 256, depth = 100`, and fuzz at `runs = 1000`, with zero counterexamples. Any counterexample is a blocker, not a flaky test.
- **R2** Auction parity. The fixture comes from the Phase 7 engine and has ≥ 50 cases, including no-cross, one-sided, all-at-one-tick, volume ties, imbalance ties, and marginal ticks on both sides. Integer equality is required on every field. If the fixture is not ready, the parity test is skipped and the deviation recorded. It must not be replaced by a Solidity-generated fixture, which would be a mirror.
- **R3** Gas. Every non-deploy external function's worst case in `forge test --gas-report` is ≤ 2,000,000. `clear` with all 99 ticks populated on both sides is ≤ 1,500,000.
- **R4** Size. Every contract's runtime is < 24,576 B and its initcode < 49,152 B (`forge build --sizes`).
- **R5** Anvil E2E artifact:
  - Deploy at a 30M block gas limit, then `evm_setBlockGasLimit 3000000`.
  - Configure, then run one auction (≥ 3 orders per side incl. a marginal-tick split), one pool policy, oracle post → finalize → settle, and all claims.
  - Every step succeeds under the 3M limit.
  - It writes `deployments/31337.json` and a balances JSON. Σ MockUSDC across all actors and contracts is unchanged except for explicit mints.
- **R6** Testnet (owner-run). All contracts verified on Sourcify (full or partial match); `Smoke.s.sol` read-only checks pass; `eth_usingBigBlocks(deployer)` = false at the end.

## Owner Runbook Outline (for 08-05 to write as `contracts/RUNBOOK.md`)

0. **Needs.** Foundry 1.8.x, uv, ~30 min, and Rabby (or MetaMask) holding an address that has deposited on Hyperliquid **mainnet** (the faucet requires it). Nothing here touches mainnet funds.
1. **Two addresses.**
   - **A** = your mainnet-deposited wallet. Browser only; used just to claim the faucet and forward testnet funds.
   - **B** = a fresh deployer created by you, `cast wallet new`, then `cast wallet import wi-deployer --interactive`.
   - B never holds mainnet value, which satisfies "never use a key that holds real value". Agents never create or see either key.
2. **Faucet.** Connect A to `https://app.hyperliquid-testnet.xyz`, claim 1,000 mock USDC at `/drip`.
3. **Gas for B.** On the testnet app, A buys ~1 testnet HYPE on HYPE/USDC spot, uses "Transfer to/from EVM" to move it to A's EVM balance, then sends 0.5 HYPE on chain 998 to B from Rabby (add a custom testnet: chain 998, RPC above, symbol HYPE). Alternative: Chainstack faucet (1 HYPE/24 h; Chainstack API key + 0.08 ETH on Ethereum mainnet at the requesting address).
4. **Make B a HyperCore user** (needed for big blocks). From A on the testnet app, send ~5 USDC to B on HyperCore. The new-account activation fee of 1 USDC applies.
5. **Preflight.** `make testnet-preflight DEPLOYER_ADDRESS=0xB…`. Expect chain id 998, ≥ 0.05 HYPE, `false`, and a gas table in which no transaction needs > 30M.
6. **Big blocks ON.** `make bigblocks-on`. Expect `{'status': 'ok', …}` and then `true`.
7. **Deploy.** `make deploy-testnet DEPLOYER_ADDRESS=0xB…`. Expect about a minute per contract; Sourcify verification at the end; `deployments/998.json` written. If interrupted, rerun with `--resume` appended.
8. **Big blocks OFF.** `make bigblocks-off`, then check `false`.
9. **Configure.** `make configure-testnet`. Optional env first: `ORACLE_SIGNER`, `QUOTER`, `HOUSE_MM` (addresses only; the signing keys stay with you or the engine host).
10. **Smoke.** `make smoke-testnet`. Links for each contract: `https://repo.sourcify.dev/998/<address>`.
11. **Hand back.** Push-notify the seat. The seat commits `deployments/998.json`; Phase 9/10 flip `CHAIN_MODE=testnet`.

**Troubleshooting:**

| Symptom | Fix |
|---------|-----|
| "exceeds block gas limit" | `--disable-block-gas-limit` missing, or big blocks not on |
| Transaction pending > 2 min | Gas price below the big-block base fee: rerun (fee is recomputed from `eth_bigBlockGasPrice`) with `--resume` |
| Error 10055 | Nonce or funds at the Core/EVM boundary |
| "Unsupported Chain IDs: 998" | Harmless |
| Sourcify failure | `forge verify-contract <addr> <path>:<Name> --chain 998 --verifier sourcify` |
| Plan B: B cannot become a Core user | Small-block-only deploy with `--gas-estimate-multiplier 110` (works only if every contract simulates ≤ ~2.7M gas) |

## HyperEVM Ecosystem Notes for the Pitch (Research Q6)

- **No insurance protocol on HyperEVM (as far as DefiLlama shows).** 195 protocols list "Hyperliquid L1" on DefiLlama (2026-09-30). None is in the Insurance category, and none of DefiLlama's 31 insurance protocols (Nexus Mutual, Sherlock, Ensuro, Nayms, Neptune Mutual, …) lists Hyperliquid L1. Nothing weather-related showed up. MEDIUM: DefiLlama coverage is not complete, and "not found" is not proof of absence.
- **Prediction markets live on HyperCore, not HyperEVM.** HIP-4 outcome markets launched 2026-05-02. They became permissionless on 2026-08-29 for deployers staking 500k HYPE; Outcome.xyz was first. They settle in USDH, and the docs describe `settleFraction` scalar settlement, the same shape as our unit. We found no weather markets on HIP-4 (LOW for that negative). On HyperEVM itself, DefiLlama's only "Prediction Market" entry is Perfect Pool (bracket games, ~$10 TVL).
- **Nearest neighbours.**
  - Options / structured products: Rysk V12 (~$41.6M TVL), Derive V2, Hypercall (~$1.0M), Hypersurface (~$0.46M).
  - Vault infra: Lagoon ERC-7540 vaults, e.g. "Nova NLP, a permissioned USDC Lagoon vault on HyperEVM that backs Nova markets".
  - ERC-4626 USDC vaults are common (Felix/Morpho curators).
  - Hyperliquid's own HLP (~$183M TVL) is the precedent for "house market-maker vault seeds liquidity". It is the easiest analog for the junior-tranche-plus-house-MM story in the crypto-native deck.
- **Gas.** HYPE pays gas and fees are burned. At 0.1 gwei a full protocol deploy costs < 0.01 HYPE, under $1 even at mainnet prices (HYPE ≈ $88 on 2026-09-28 per the defi-options memo, [est.]).
- **Wallets.**
  - Rabby supports HyperEVM mainnet as an integrated network (Hyperliquid FAQ recommends it). Testnets are added via "Custom Testnet", since Rabby dropped native testnet support.
  - MetaMask works as a custom network but has a documented error ("Invalid transaction envelope type 0x2 … included a gasPrice"). Demo with Rabby; have wagmi send explicit EIP-1559 fields.
- **viem names.** Testnet is `hyperliquidEvmTestnet` (id 998). Mainnet is `hyperEvm`, aliased `hyperliquid` (id 999).
- **Momentum signals** (LOW, news only): Kinetiq's Elysium L2 testnet (2026-09-22) settles on HyperEVM. HIP-3* permissioned perps were announced 2026-09-03 (per defi-options memo).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Foundry/solc default EVM paris→cancun→prague | `osaka` default (Foundry 1.8.3, solc 0.8.3x) | by 2026 | Must pin `cancun` for HyperEVM |
| OZ EIP712 stored long name/version in storage | Name and version must fit ShortString (≤ 31 bytes) | OZ 5.7.0 (2026-07-29) | Keep EIP-712 names short ("wi-oracle", "wi-policy") |
| OZ ERC1967Proxy allowed uninitialized deploys | Must initialize during construction | OZ 5.6.0 | Irrelevant (no proxies) |
| Single HyperEVM block type | Dual blocks (1 s / 3M, 60 s / 30M), per-address opt-in | HyperEVM 2025, still current | Deploy sequencing above |
| HIP-4 curated only | Permissionless behind 500k HYPE stake | 2026-08-29 | Partner-only path (PROJECT out of scope) |
| purrsec as testnet explorer | Dead; no current testnet explorer | observed 2026-09-30 | Sourcify + cast |
| Rabby built-in testnets | Custom Testnet | 2024 | Add chain 998 manually |

**Deprecated/outdated:**
- `DEPLOYER_PRIVATE_KEY` env pattern: use `--account` keystores.
- Git-submodule `forge install`: 08-01 uses `--no-git` vendoring (keep).
- `testnet.purrsec.com` in any config or doc.

## Open Questions

1. **Junior tranche asset.**
   - What we know: the owner ruling says token = junior first-loss capital + governance. The 08-01 stub leaves "USDC vs WI deposit" to SPEC.
   - What's unclear: whether WI is the junior share (USDC in, WI out; recommended), or a separately issued token staked as first loss (Aave Safety Module style).
   - Recommendation: build USDC-in / WI-share. Payouts are USDC, there is no testnet WI market to sell staked WI into, and staked-token first loss is wrong-way risk (a heatwave loss dumps the token when the pool needs it). Phase 14 can add a fixed-supply allocation story on top. Confirm in SPEC 07-01.
2. **Revision window W, anchor, and the no-report fallback.** Calendar-anchored `dayEnd + W` is recommended. W comes from Phase 3/7 (nClimGrid prelim timing). The fallback is void and refund. It needs a SPEC ruling; contracts take W as a constructor argument.
3. **Auction allocation rule.** Price-time at the marginal tick is recommended because it is exact. If SPEC picks pro-rata, the contract needs a dust sink (pool) and M1(b) changes to "|long − short| ≤ orders at the marginal tick, dust to pool". The Python engine must match either way.
4. **Meaning of "waterfall never pays junior before senior loss absorption is exhausted."**
   - Read as the loss rule: senior absorbs nothing until junior is exhausted. M2 tests exactly that.
   - If the owner meant an income rule (a senior coupon paid before junior earns anything), SPEC must define the coupon, and M2 adds "junior income accrues only after the senior coupon is met".
   - Flag to the owner.
5. **Oracle signer and quoter keys on testnet.** These are unfunded signing keys the Phase 9 engine uses. Per the rules the owner creates them. The default is `deployer` for both, which is fine for the demo but ties the engine to the deployer key. Recommend the owner creates two signing-only keys and passes their addresses as `ORACLE_SIGNER` / `QUOTER`.
6. **Does the owner have a mainnet-deposited address?** Memory suggests he uses Hyperliquid (hl-mm), but this is unconfirmed. If not, the faucet is closed. Options: someone else's testnet account sends testnet USDC to B; or the small-block Plan B, with EVM gas from Chainstack (needs 0.08 ETH on Ethereum mainnet at the requesting address).
7. **HyperEVM treatment of a >3M gas-limit transaction from a small-block address** (rejected vs stuck) and **whether EIP-170/3860 apply** unchanged. Unverified (LOW). Avoided by design.
8. **House-MM participation in auctions.** Either an ordinary wallet funded with MockUSDC, or orders funded from pool free capital. Recommendation for Phase 8: ordinary wallet (no pool-order path). Revisit in Phase 9.

## Sources

### Primary (HIGH confidence)
- Hyperliquid docs, HyperEVM (chain ids, RPCs, Cancun, fees): https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/hyperevm
- Dual-block architecture (3M/1 s, 30M/60 s, `evmUserModify`, Core-user precondition, 8-nonce mempool): https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/hyperevm/dual-block-architecture
- JSON-RPC (latest-only methods, getLogs limits, `eth_bigBlockGasPrice`, `eth_usingBigBlocks`): https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/hyperevm/json-rpc
- Testnet faucet (mainnet-deposit precondition, 1,000 mock USDC): https://hyperliquid.gitbook.io/hyperliquid-docs/onboarding/testnet-faucet
- How to use the HyperEVM (wallet add, `0x2222…` HYPE transfer, explorers): https://hyperliquid.gitbook.io/hyperliquid-docs/onboarding/how-to-use-the-hyperevm
- HyperEVM Tools (faucets, explorers, RPCs, big-block tools): https://hyperliquid.gitbook.io/hyperliquid-docs/builder-tools/hyperevm-tools
- Activation gas fee: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/activation-gas-fee
- Gas FAQ (MetaMask type-0x2 issue, Rabby): https://hyperliquid.gitbook.io/hyperliquid-docs/support/faq/hyperevm-issues/gas-problem-on-evm
- HIP-4 outcome markets (settleFraction): https://hyperliquid.gitbook.io/hyperliquid-docs/hyperliquid-improvement-proposals-hips/hip-4-outcome-markets
- hyperliquid-python-sdk 0.24.0 `use_big_blocks` + example: https://github.com/hyperliquid-dex/hyperliquid-python-sdk/blob/0.24.0/hyperliquid/exchange.py and https://github.com/hyperliquid-dex/hyperliquid-python-sdk/blob/master/examples/basic_evm_use_big_blocks.py
- Foundry v1.8.3 source (default `evm_version = Osaka`, invariant defaults, `disable_block_gas_limit`, script flags, `transaction_timeout = 120`): https://github.com/foundry-rs/foundry/tree/v1.8.3/crates
- Foundry releases (v1.8.3, 2026-09-15): https://github.com/foundry-rs/foundry/releases
- Solidity 0.8.37 docs (EVM targets, osaka default) and bug lists: https://github.com/argotorg/solidity/blob/v0.8.37/docs/using-the-compiler.rst, https://github.com/argotorg/solidity/blob/develop/docs/bugs_by_version.json
- OpenZeppelin Contracts 5.7.0 changelog: https://github.com/OpenZeppelin/openzeppelin-contracts/blob/v5.7.0/CHANGELOG.md
- forge-std v1.16.2 `Vm.sol`: https://github.com/foundry-rs/forge-std/blob/v1.16.2/src/Vm.sol
- viem 2.57.1 chain definitions: https://github.com/wevm/viem/blob/viem%402.57.1/src/chains/definitions/hyperliquidEvmTestnet.ts
- Sourcify chains API (998 supported): https://sourcify.dev/server/chains
- Etherscan V2 chainlist (999 only): https://api.etherscan.io/v2/chainlist
- Chainlink HyperEVM testnet RPC guide: https://docs.chain.link/ccip/tools-resources/network-specific/hyperevm-testnet-rpc
- Live reads (this session, read-only): testnet via `rpcs.chain.link/hyperevm/testnet` (chain id, gas prices, gas-limit histogram, `eth_getCode` of system contracts, forge dry-run); mainnet via `rpc.hyperliquid.xyz/evm` (gas-limit histogram, `eth_usingBigBlocks`, historical-tag behaviour). Local anvil experiments (130% multiplier failure, `evm_setBlockGasLimit`, contract sizes/deploy gas).

### Secondary (MEDIUM confidence)
- Chainstack testnet faucet requirements: https://faucet.chainstack.com/hyperliquid-testnet-faucet
- KeeperHub issue (no explorer API for 998, 2026-09-15): https://github.com/KeeperHub/keeperhub/issues/2473
- DefiLlama protocols API (categories/TVL on Hyperliquid L1, 2026-09-30): https://api.llama.fi/protocols
- TS SDK `evmUserModify` schema: https://github.com/nktkas/hyperliquid/blob/main/src/api/exchange/_methods/evmUserModify.ts
- Rabby HyperEVM integration: https://x.com/Rabby_io/status/1924815018803028093; Rabby custom testnets: https://x.com/Rabby_io/status/1775136418425118879
- HypeRPC Blockscout testnet (stalled at 2026-08-03): https://explore-testnet.hyperpc.app/
- Chainstack CoreWriter/Foundry note: https://docs.chainstack.com/docs/hyperliquid-corewriter

### Tertiary (LOW confidence)
- HIP-4 launch dates and Outcome.xyz: https://www.coingecko.com/learn/hyperliquid-hip3-hip4-tokenized-stocks-and-prediction-markets, https://chainstack.com/hyperliquid-hip4-vs-polymarket-2026/
- Elysium L2 testnet (2026-09-22): https://www.kucoin.com/news/flash/hyperliquid-s-first-l2-network-elysium-testnet-launched
- purrsec.com spam page: single probe this session
- Internal: `~/Desktop/defi-options/.planning/phases/05-venue-and-mm-design/05-HYPERLIQUID-HOSTING.md` (HYPE price, HIP-3*)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH. Versions come from GitHub releases/PyPI/npm today and the scaffold builds with them.
- Chain facts / big blocks: HIGH. Official docs, live RPC reads, and gotchas reproduced locally. Faucet preconditions come from the docs and the vendor page; the owner's eligibility is unknown.
- Architecture:
  - MEDIUM-HIGH for the auction and oracle. Their core snippets were compiled and fuzzed in a scratch project: conservation, limits, replay, tamper.
  - MEDIUM for the pool waterfall. The core compiles with 2 share tokens deployed in the constructor; it is not fuzzed yet.
  - MEDIUM for PolicyManager: reasoned only.
  - Core runtime sizes (scratch): auction 5.2 KB, oracle 3.5 KB, pool 2.8 KB (6.1 KB initcode). Full contracts will be larger but should stay far below 24 KB.
  - All of it depends on SPEC 07-01 rulings (Open Q1–4).
- Pitfalls: HIGH for G1–G13 (verified); LOW for G14–G15.
- Ecosystem: LOW–MEDIUM. DefiLlama plus news.

**Research date:** 2026-09-30
**Valid until:** 2026-10-14 for chain/explorer/faucet facts (fast-moving: explorers died within weeks); 2026-10-30 for the tool versions and patterns.
