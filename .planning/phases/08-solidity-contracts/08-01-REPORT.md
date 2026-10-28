# 08-01 Report - Foundry scaffold, MockUSDC, token, interfaces

Status: done. Only `contracts/` and this report were touched.

## Versions
- forge / anvil 1.8.3 (cae51ad, 2026-09-15)
- solc 0.8.28 (pinned via `solc_version`; auto-downloaded, compiled fine), evm `cancun`, optimizer on (200 runs)
- OpenZeppelin Contracts v5.7.0 (latest v5.x tag found via `git ls-remote`; its ERC20/Ownable pragma is ^0.8.20, so 0.8.28 is fine)
- forge-std: latest master at install time (installed by `forge init`)

## Install method
`forge init . --no-git --force --empty` (in a non-empty `contracts/` holding only `.gitkeep`), then `forge install OpenZeppelin/openzeppelin-contracts@v5.7.0 --no-git --shallow`. `--no-git` exists in 1.8.3, so no soldeer or manual vendoring was needed. Deps are plain clones with the `.git` dir removed, in `contracts/lib/`, git-ignored by `contracts/.gitignore` (committing ~thousands of OZ files is not worth it). `make install` restores them. `remappings.txt`: `@openzeppelin/contracts/=lib/openzeppelin-contracts/contracts/`, `forge-std/=lib/forge-std/src/`.

Git state check: `git status --porcelain` at the repo root shows new untracked files under `contracts/` only (`.gitignore`, `Makefile`, `README.md`, `deployments/`, `foundry.toml`, `remappings.txt`, `script/`, `src/`); no `.gitmodules`, no tracked file modified. Other untracked paths (`apps/`, `package.json`, `pnpm-*`, `scripts/pull_kalshi.py`, `src/wi/data/*`) belong to other agents. `contracts/.gitkeep` left in place.

## Build output
```
Compiling 28 files with Solc 0.8.28
Solc 0.8.28 finished in 1.55s
Compiler run successful!
```
No warnings. `forge test`: "No tests found in project" (zero tests by design, no mirror tests). `FOUNDRY_PROFILE=hyperevm_testnet forge config` resolves `eth_rpc_url = "${HYPEREVM_TESTNET_RPC}"` and chain_id 998 (forge prints it as the named chain `hyperliquid-testnet`). Both carry `// verify: Phase 8 research`.

## Deliverable notes
- `foundry.toml` has no `eth_rpc_url` in `default` on purpose: setting one makes `forge test` fork it (first attempt failed with connection refused). The Makefile passes `--rpc-url` for anvil.
- `fs_permissions` grants read-write on `./deployments` only.
- Interfaces are stubs, shapes only: `IPolicyManager` (Policy struct with buyer, stationId, indexId, PayoutType enum, strike, cap, units, premium, day, status; createPolicy, settlePolicy, getPolicy), `IBatchAuction` (Order, ClearingResult; submitOrder, runAuction(stationId, day), getResult), `IPoolVault` (Senior/Junior tranche, depositSenior/depositJunior, requestWithdraw/withdraw, absorbLoss, creditPremium), `IOracleAdapter` (postValue with signature, finalize, getFinal). Units/scales, junior deposit asset (USDC vs WI), revision policy and clearing rule are open for SPEC.md.
- `WIToken` takes `initialOwner` in its constructor (deployer for now).
- `make deploy-testnet` checks env, prints a warning that the owner runs it, uses `FOUNDRY_PROFILE=hyperevm_testnet`, `--slow`. Not run.

## Anvil deploy proof
Started `anvil --chain-id 31337`, ran `make deploy-anvil` (anvil's public first-account key), then stopped anvil (no anvil process left). Script: "ONCHAIN EXECUTION COMPLETE & SUCCESSFUL". `contracts/deployments/31337.json`:
```
{ "MockUSDC": "0x5FbDB2315678afecb367f032d93F642f64180aa3",
  "WIToken":  "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
  "chainId": 31337,
  "deployer": "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266" }
```
Addresses are deterministic for a fresh anvil (nonces 0 and 1). `broadcast/`, `cache/`, `out/` are git-ignored; the `deployments/31337.json` file is not ignored (seat decides whether to commit it; it is only valid for a fresh anvil).

## Not done / caveats
- Testnet deploy not run (owner-run). Chain id 998 and RPC unverified (Phase 8 research).
- Big-block mode is noted in README and Makefile comments only; nothing in this plan exercises it.

## OBJECTION
None.
