# contracts/ (weather-insurance, codename)

Foundry project for the on-chain side of the protocol (docs/SPEC.md is the law; Phase 8). Target:
HyperEVM testnet (chain 998, Cancun); local dev on anvil (31337). solc 0.8.37, `evm_version = cancun`,
OpenZeppelin 5.7.0 and forge-std 1.16.2 vendored under `lib/` without git (`make install` restores).

## Contracts (`src/`)

| Contract | Role (SPEC section) |
|---|---|
| `PolicyManager` | markets with derived times, house-quoted policies (EIP-712 `Quote`), bind/downsizing, settlement and void, strips, RFQ (`RfqQuote`, maker margin), auction/RFQ positions and their claims (2, 4, 6, 10) |
| `BatchAuction` | open tick-bucketed uniform-price call auction per market; `clear` is O(99), `claim` O(1); 200 public orders max, 20 per address, ≥ 1 USDC escrow each, house exempt (5) |
| `PoolVault` | all claim-paying USDC; senior (`SeniorShare`, 12 dp) and junior (internal) ledgers; junior-first waterfall; caps C1/C2; request-then-claim withdrawals; house deployment per day; `closeDay` -> WI haircut (8) |
| `WIToken` / `WIStaking` | fixed-supply WI (burnable); staking with cooldown, pro-rata burn haircut capped per day (8.7) |
| `OracleAdapter` | reporter-signed `Report`s, per-index fetch/dispute/void windows, finalize, void (9) |
| `Lens` | read-only: a user's policies, orders, positions, pool and staking state in one eth_call |
| `MockUSDC` | 6-dp test USDC with an open faucet (testnet/anvil only) |
| `lib/Payoff.sol`, `lib/BindMath.sol` | the scalar unit L(x); bind downsizing math |

Admin: Ownable2Step on every protocol contract; pause stops new risk only (buyPolicy, buyStripDay,
openStrip, placeOrder, acceptRfq, deposits, fundHouse, stake), never claims, settlement, finalize,
withdrawals or returns. No proxies.

## Commands (from `contracts/`)

```
make build           # forge build --sizes
make test            # money-failure invariants, directed edge cases, gas budget, engine parity
make anvil-e2e       # throwaway anvil: deploy (30M) -> block gas limit 3M -> configure -> smoke -> 5-phase E2E -> gas table
make gas-report      # forge test --gas-report
```
Testnet is owner-only: see `RUNBOOK.md` (`testnet-preflight`, `bigblocks-on`, `deploy-testnet`,
`bigblocks-off`, `configure-testnet`, `smoke-testnet`).

## Tests (`test/`)

Only money failures and parity (AGENTS.md testing rules): `AuctionInvariants` (value conservation,
limits, max volume, escrow split, double claims), `PoolInvariants` (junior first, caps, cash identity,
bind identities, paid once), `OracleSettlement` (stale/unsigned/tampered/foreign/replayed/unfinal),
`StakingHaircut`, `MoneyEdges`, `GasBudget`, and `parity/*` which replay the Phase 7 engine's
`test/fixtures/*.json` with exact integer equality (skipped with a message if a file is absent; never
regenerate fixtures from Solidity).

## Scripts (`script/`)

`Deploy.s.sol` (CREATE only, writes `deployments/<chainId>.json`), `Configure.s.sol` (wiring, roles,
params, seed, indices, demo markets; idempotent), `Smoke.s.sol` (read-only checks), `E2E.s.sol` +
`Warp.s.sol` (anvil only), `hl_big_blocks.py` (testnet-only big-block toggle), `anvil_e2e.sh`,
`gas_table.py`.
