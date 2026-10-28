# 09-LAPSE: API lapse and cancel for withdrawals (follow-up to 08-HARDEN #6)
- Epoch (`clock._epoch`): a request past `claimableAt + withdrawClaimWindow` is lapsed via `pool.lapse_withdraw` (shares back to the LP, no USDC); inside the window it is claimed as before. No more "deferred (ClaimWindowClosed)" forever.
- `POST /api/v1/pool/withdraw/{request_id}/cancel` body `{owner}`: engine `check_cancel` enforces owner (403 FORBIDDEN) and pre-maturity (409 NOT_CANCELLABLE); unknown id 404; second cancel 409. Same owner-in-body model as the other pool routes (the API has no sessions). Testnet: calldata-only `PoolVault.cancelWithdraw(id)`; the contract checks msg.sender.
- `QueueTicket` gained `requestId` and `claimBy` (claimableAt + 3 d); `status` is now queued | processed | cancelled | lapsed. Golden unchanged (no regeneration).
- Anvil mirror: `_WithdrawCancelled` (owner sends) and `_WithdrawLapsed` (keeper sends) replay on PoolVault and are checked field by field; `tx_confirm` reports both as `withdrawal` objects. Proven on a real anvil by the new `test_anvil_withdraw_cancel_and_lapse_are_mirrored_on_chain` (chain == engine, no drift).
- Portal (`PoolBoard.tsx`, `PoolMoneyForms.tsx`, `lib/api.ts`, regenerated `engine-schema.d.ts` from the app's OpenAPI with `openapi-typescript`, diff is only the new route/fields): "Claim by" column, Cancel button on your own queued withdrawals while sim time < maturity, copy about the 3-day window.
- Tests (tests/api/test_api.py): a request the epoch cannot pay (house junior, JuniorMinimum) lapses at the first epoch past claimBy, shares return, event log is exactly Requested then Lapsed; cancel works before maturity, refused after (409 NOT_CANCELLABLE), refused for a non-owner (403), not repeatable.
- `uv run pytest tests/api -q` (golden included): `20 passed, 3 skipped, 3 warnings in 10.91s` (3 skipped = anvil tests, run separately); `uv run pytest tests/engine -q`: `19 passed in 7.89s`.
- `bash scripts/anvil-scenario.sh`: `3 passed, 20 deselected, 4 warnings in 41.36s`. Stopped by PID; `contracts/broadcast` and `contracts/deployments` restored from a copy afterwards.
- Portal: `pnpm exec tsc --noEmit` no output (clean), `pnpm lint` clean, `ENGINE_ORIGIN=http://127.0.0.1:8787 pnpm build` ok, 11 routes (same Turbopack tracing warnings in `sales/square/fixture-files.ts` as before); run under a mkdir `.build-lock` at the repo root, removed.
- Files: src/wi/api/{app,clock,models,views}.py, src/wi/api/ledger/{base,sim,evm,mirror}.py, tests/api/test_api.py, apps/portal/src/{components/PoolBoard.tsx,components/PoolMoneyForms.tsx,lib/api.ts,lib/engine-schema.d.ts}.
- Redeploy: yes, API and portal both (new route, new view fields, new epoch behavior). No state migration: old closed requests render as "processed"; a demo-world request stuck past its window lapses at the next epoch. Not deployed.
- Note: the brief's path `09-engine-api/` does not exist; this file is in `09-engine-api-chain-modes/`. FYI `withdrawClaimWindow` is read from engine params, so the view's `claimBy` follows it.

## Deploy after 09-LAPSE (2026-09-30T19:36Z)
- Deploy ids: engine `wi-engine-dznmgyl45-ehfaz-zohas-projects` (alias wi-engine.vercel.app), portal `wi-portal-pf69u3it9-ehfaz-zohas-projects` (alias wi-portal.vercel.app). Bundle checks passed; health `{"ok":true,"mode":"sim",...,"simTime":"2026-07-18T20:00:00Z"}`.
- Check 1: `GET /api/v1/openapi.json` on the engine lists `/api/v1/pool/withdrawals`, `/api/v1/pool/withdraw/{request_id}/cancel` and `claimBy` (1 hit each). `/openapi.json` is 404 because the app mounts it under /api/v1.
- Check 2: `/app/pool` HTML has no "Claim by" (client rendered); the chunk `/_next/static/immutable/chunks/3dcb6nxmcqewu.js` served by wi-portal.vercel.app contains "Claim by".
- Check 3: `seed-demo.py --check` -> `check: OK, the demo world matches reports/demo/seed-state.json`; no reseed.
- Smoke: `SMOKE PASS`, 15/15, 17.9 s; every seeded and private-world number identical to the previous run (bakery $613.93, pool $200,221.06 / $300,001.00, B8 balance $717.30).
- Screenshots: only 04-seeded-pool.png kept new (new withdraw copy about the 3-day claim-by window; withdrawals list empty, so no Claim by column visible). The other 15 restored from backup (re-rendered bytes differ, visible numbers do not).
- Disk after: `df -h /` 26Gi free (11Gi used, 31%).
