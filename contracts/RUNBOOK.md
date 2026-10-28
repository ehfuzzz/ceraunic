# Testnet deploy runbook (owner)

This puts the weather-insurance contracts on **HyperEVM testnet (chain 998)**. You run every step that
signs anything. Agents hold no keys. Nothing here touches mainnet funds. Budget about 30-45 minutes.

## 0. What you need

- Foundry 1.8.x (`forge --version`), `uv`, and this repo. Run everything from `contracts/`.
- A browser wallet (Rabby is easiest) holding an address that has **deposited on Hyperliquid mainnet**
  at some point. The testnet faucet only pays addresses with a mainnet deposit.
- Optional: `make anvil-e2e` first. It runs the whole flow on a throwaway local chain in about 2 minutes,
  so you see what a good run looks like.

## 1. Two addresses

- **A** = your mainnet-deposited wallet. Browser only. It claims the faucet and forwards testnet funds.
- **B** = a fresh deployer that never holds real value:
  ```
  cast wallet new                                   # note the address and private key
  cast wallet import wi-deployer --interactive      # paste the key, set a password
  cast wallet address --account wi-deployer         # prints B
  ```
  From here on `DEPLOYER_ADDRESS=0xB...` means this address.

## 2. Faucet (A)

Connect A at https://app.hyperliquid-testnet.xyz and claim 1,000 mock USDC at `/drip`.

## 3. Gas for B

On the testnet app, with A: buy about 1 testnet HYPE on the HYPE/USDC spot market, use
"Transfer to/from EVM" to move it to A's EVM balance, then send **0.5 HYPE** to B on chain 998 from Rabby
(add a custom testnet: chain id 998, RPC `https://rpc.hyperliquid-testnet.xyz/evm`, symbol HYPE, no
explorer). A full deploy + configure costs well under 0.01 HYPE; the rest is headroom.

## 4. Make B a HyperCore user (needed for big blocks)

From A on the testnet app, send **about 5 USDC to B on HyperCore** (not the EVM). A new account pays a
1 USDC activation fee. Without this, `make bigblocks-on` fails with a user/account error.

## 5. The six steps

```
export DEPLOYER_ADDRESS=0xB...
make testnet-preflight      # read-only: chain id 998, B's HYPE balance, big blocks false, deploy dry run
make bigblocks-on           # prompts for the keystore password; expect status ok, then "usingBigBlocks now: True"
make deploy-testnet         # 8 CREATE txs, ~1 min each in big blocks; Sourcify verification at the end
make bigblocks-off          # expect "usingBigBlocks now: False"
make configure-testnet      # ~40 small txs, ~1 s each: wiring, roles, params, seed, demo markets
make smoke-testnet          # read-only checks; prints capital, junior, senior, WI staked
```

What each step expects:
- **preflight** prints `998`, a balance of at least 0.05, `false`, and a gas line per transaction. Three
  deploys are too big for a 3M small block: PolicyManager about 5.1M gas, PoolVault 3.2M, Lens 2.5M
  (forge asks for 130 % of that). That is why big blocks are needed for the deploy only.
- **deploy-testnet** refuses to run if big blocks are off. It writes `deployments/998.json`. If it stops
  half way, run `make deploy-testnet EXTRA=--resume`.
- **configure-testnet** refuses to run if big blocks are still on. It runs as B (the owner) and:
  wires the contracts, sets roles, sets SPEC §17 params, registers 10 indices (NYC/LGA/JFK/EWR CLI,
  station pairs, rain), mints MockUSDC to B and seeds the pool (junior 10,000, senior 40,000), stakes
  1,000,000 WI, and creates 8 demo markets for tomorrow (UTC). It is safe to re-run; done steps are
  skipped. Re-run it on later days (or set `DEMO_DAYS=7` once) to get markets for more days.
- **smoke-testnet** sends nothing. It fails loudly on the first wrong wiring, role or money identity.

### Optional: separate role keys (recommended before Phase 9)

By default B is also the house, the quoter, the oracle reporter and the treasury. To split them, create
signing keys yourself (`cast wallet new`), keep the keys, and pass only the **addresses** before
`make configure-testnet`:
```
HOUSE=0x... QUOTER=0x... REPORTER=0x... TREASURY=0x... make configure-testnet
```
The house gets 100,000 MockUSDC. Keep the house and demo wallets out of big-block mode (every tx from a
big-block address waits ~60 s).

## 6. What to send back to the seat

- `contracts/deployments/998.json` (addresses, `startBlock`, roles, demo market ids).
- The last ~15 lines of `make smoke-testnet`.
- Optional: `contracts/broadcast/Deploy.s.sol/998/run-latest.json` (tx hashes). **Do not send anything
  from `contracts/cache/`** (forge keeps "sensitive values" there) and never send a key or keystore.

Verified sources: `https://repo.sourcify.dev/998/<address>`. There is no working testnet explorer
(purrsec is dead; do not use it). Use `cast` for transactions.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `exceeds block gas limit` or `tx.gas_limit > env.block.gas_limit` | Big blocks are off, or `--disable-block-gas-limit` was dropped (G2, G3). `make bigblocks-status`, then `make bigblocks-on`. |
| Deploy tx pending more than 2 minutes | Gas price below the big-block base fee (G5). `make deploy-testnet EXTRA=--resume`; the price is re-read from `eth_bigBlockGasPrice` × 3. |
| Forge timeout while waiting for a receipt | Big-block txs take ~60 s; the target already sets `--timeout 300` (G13). `make deploy-testnet EXTRA=--resume`. |
| "Unsupported Chain IDs: 998 ... might not work (EIP-3855)" | Harmless (G8). HyperEVM is Cancun, which has PUSH0. |
| `invalid opcode` at runtime on testnet only | Bytecode compiled for osaka. `forge config \| grep evm_version` must say cancun (G1); `foundry.toml` pins it. |
| Error code 10055 | Nonce or funds at the HyperCore/HyperEVM boundary (G11). Check B's HYPE on the EVM side, wait a block, retry. |
| `nonce too high` / txs dropped in a batch | The mempool keeps only the next 8 nonces per address (G4). The targets use `--slow`; never fire extra txs from B while a step runs. |
| `cast chain` fails with "invalid block height: 0" | Use `cast chain-id` (G6). Historical block tags are answered with latest state on HyperEVM, so pinned forks are not point-in-time. |
| Log queries return nothing / errors | `eth_getLogs` allows at most 50 blocks per query (G7). Start from `startBlock` in `deployments/998.json`. |
| `bigblocks-on` says the user does not exist | B is not a HyperCore user yet: step 4. |
| `make configure-testnet` says big blocks are still ON | `make bigblocks-off`, wait for `False`. |
| Sourcify verification failed | `forge verify-contract <address> src/<File>.sol:<Name> --chain 998 --verifier sourcify` per contract. |
| HyperCore precompile / CoreWriter calls | None of these contracts call them (G9); anvil has none either. |
| Timestamps look odd around a block | Small and big blocks interleave and can share a timestamp (G10). Contracts use `block.timestamp` only. |
| An old key once sent pre-EIP-155 txs | Do not use it (G12). A fresh `cast wallet new` key is fine. |
| Plan B (no HyperCore account for B) | Not available as built: PolicyManager needs ~5.1M gas to deploy, above a 3M small block even at `--gas-estimate-multiplier 110`. Ask the seat to split PolicyManager first. |
