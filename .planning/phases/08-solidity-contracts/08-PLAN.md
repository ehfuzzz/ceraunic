---
phase: 08-solidity-contracts
plan: 02-05 (single worker run)
type: execute
depends_on: ["07-01"]
files_modified: [contracts/src/*, contracts/script/*, contracts/test/*, contracts/Makefile, contracts/RUNBOOK.md, contracts/foundry.toml, contracts/deployments/31337.json]
---
<objective>PROT-02 per docs/SPEC.md and 08-RESEARCH: PolicyManager (markets, signed-quote policies, positions, settlement, claims), BatchAuction (open tick-bucketed uniform-price call auction, lazy claims), PoolVault (USDC custody; senior share token + protocol-owned junior ledger; junior-first waterfall; caps; request-then-claim), WIToken fixed supply + WIStaking (pro-rata burn haircut, cooldown), OracleAdapter (EIP-712 reports, calendar revision window, finalize, void), Lens view contract (one eth_call for a user's positions/orders/pool/settlements), MockUSDC; money-failure tests incl. parity against Phase 7 fixtures; deploy/configure/smoke scripts + big-blocks helper + RUNBOOK the owner runs.</objective>
<context>@docs/SPEC.md @.planning/phases/08-solidity-contracts/08-RESEARCH.md (Starting point; Patterns 1–7; Pitfalls; Code Examples foundry.toml + Deploy skeleton; Big blocks sequence; gotchas G1–G15) @.planning/phases/07-protocol-spec-engine/07-CONTEXT.md @contracts/ (08-01 scaffold) @contracts/test/fixtures/*.json if Phase 7 has written them (else write the parity test to read them when present and skip with a clear message) @AGENTS.md
PATH: `export PATH="$HOME/.foundry/bin:$PATH"`. Bump solc to 0.8.37 if available to forge, keep evm_version cancun. Every non-deploy external call ≤ 2.0M gas worst case (test on anvil with gas limit 3M). No submodules; no git commands.</context>
<tasks>
<task type="auto"><name>Task 1: contracts</name><files>contracts/src/{PolicyManager,BatchAuction,PoolVault,SeniorShare,WIToken,WIStaking,OracleAdapter,Lens,MockUSDC}.sol, contracts/src/lib/Payoff.sol</files>
<action>Implement per SPEC + Patterns; Ownable2Step + Pausable per Pattern 6; internal ledgers never balanceOf; ReentrancyGuard on USDC moves; EIP-712 types EXACTLY as SPEC (int64 value, uint32 day…); `forge build --sizes` under EIP-170.</action>
<verify>`forge build` clean; sizes printed in the summary.</verify><done>Contracts.</done></task>
<task type="auto"><name>Task 2: tests (money failures only) + parity</name><files>contracts/test/**</files>
<action>Invariant/fuzz: clearing conserves value exactly and never violates a limit; waterfall junior-first identity; cap enforced on reserve and withdrawal claim; oracle rejects stale/unsigned/foreign-domain/replayed reports and double finalize; settlement reads only getFinal; no double settlement; staking haircut never exceeds cap and burns exactly the pro-rata amount. AuctionParity.t.sol + PayoffParity + WaterfallParity + OracleParity from contracts/test/fixtures via vm.parseJson. Gas test: full E2E under a 3M block on anvil (evm_setBlockGasLimit).</action>
<verify>`forge test` passes (parity tests skip with a message if fixtures absent).</verify><done>Tests.</done></task>
<task type="auto"><name>Task 3: scripts + RUNBOOK</name><files>contracts/script/{Deploy,Configure,Smoke}.s.sol, contracts/script/hl_big_blocks.py, contracts/Makefile, contracts/RUNBOOK.md, contracts/deployments/31337.json</files>
<action>Deploy (CREATE only; vm.writeJson addresses + startBlock), Configure (wiring, roles, params, MockUSDC seed, junior seed, demo markets), Smoke (read-only asserts); hl_big_blocks.py using hyperliquid-python-sdk `use_big_blocks` with a testnet-only guard and `eth_usingBigBlocks` check (do NOT run it; no key exists); Makefile targets per 08-RESEARCH "Recommended sequence" using `--account` keystore, `--slow --disable-block-gas-limit --with-gas-price … --timeout 300 --verify --verifier sourcify`; run the whole flow on anvil end to end and write deployments/31337.json; RUNBOOK.md for the owner: prerequisites (mainnet-deposited address → faucet 1,000 USDC → buy testnet HYPE → transfer to EVM; fund deployer 0.5 HYPE; keystore import), the six make steps, troubleshooting G1–G13, what to send back to the seat (addresses JSON).</action>
<verify>`make deploy-anvil configure-anvil smoke-anvil` (or equivalent names) passes on a local anvil you start and stop.</verify><done>Owner-ready.</done></task>
</tasks>
<output>`.planning/phases/08-solidity-contracts/08-SUMMARY.md` (≤ 60 lines) incl. gas table and sizes.</output>
