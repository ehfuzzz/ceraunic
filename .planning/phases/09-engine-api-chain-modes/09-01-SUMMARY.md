---
phase: 09-engine-api-chain-modes
plan: 01
status: complete (verified locally on :8787; server stopped)
---
# 09-01 Summary: fixture API contract

## What shipped
- `src/wi/api/`: `app.py` (31 paths under `/api/v1`, `create_app(mode, env)`, boot guards, RFC 9457 problems), `models.py` (camelCase pydantic wire models), `envelope.py` (Wire, Address, Execution, TxRequest, ApiError), `store.py` (MemoryStore, per-world lock), `fixtures.py` (deterministic sha256-derived data: 5 stations, per-station residual contract, quotes, house quotes, a fixture clearing rule, scheduler events, pool baseline).
- Sim worlds (`X-WI-World`, default `demo`), `Idempotency-Key` on POST writes (same key + different body = 422), `X-Admin-Token` (env `ADMIN_TOKEN`; local default `dev-admin`, none on Vercel).
- Execution envelope on every write (`done` in sim). Writes mutate the in-memory world so GETs reflect them (balances, locks, policies, orders, clearing, pool epochs at 12:30Z, settlements final at D+2 12:00Z).
- `anvil`/`testnet` boot and serve `/health` and `/config` only; every other route returns 503 `RPC_UNAVAILABLE` until the EVM ledger (09-03).
- Guards: testnet + any `*PRIVATE_KEY*`/`*MNEMONIC*` env, anvil on Vercel, sim on Vercel without `UPSTASH_REDIS_REST_URL`.
- `services/engine-api/`: `app.py` re-export, slim `pyproject.toml` (fastapi, pydantic, upstash-redis, web3), `vercel.json` (`framework: fastapi`), `.python-version` 3.14.
- Portal: `engine-schema.d.ts` generated (`pnpm gen:api`), `api.ts` rewritten on `openapi-fetch` (old method names kept; `newWorld`, `health`, `config`, `auctions`, `pool`, etc. added; shapes now wire shapes, money `...E6`), `execute.ts` (`done` returns result, `needs_signature` throws NotImplementedError for Phase 10), `next.config.ts` rewrite `/api/v1/:path*` -> `ENGINE_ORIGIN` (default `http://127.0.0.1:8787`).
- `tests/api/scenario_nyc_3d.json` (37 steps) + `run_scenario.py`; `tests/api/test_api.py` (6 tests).

## Verified
- `curl /api/v1/health` -> `{ok:true, mode:"sim"}`; openapi lists 31 paths.
- `uv run python tests/api/run_scenario.py http://127.0.0.1:8787` exits 0; two runs give identical normalised dumps.
- `pytest tests/api`: 9 passed (6 tests, one parametrised). Mutation-checked: clearing that mints 1 unit, idempotency body check removed, settlement time gate removed each fail a test.
- Portal `pnpm build` and `pnpm lint` pass; `tsc --noEmit` clean. A node script through the facade returned `mode sim` both directly and through `next start` rewrite (port 3457, stopped).

## Notes for 09-02..05
- Fixtures, not engine: premiums, clearing, payouts and pool NAV (fixed 1.0) are placeholders. `fixtures.clear_auction` follows the Phase 7 rule but is a stand-in. The business-ladder policy pays the same station-style payout in fixtures (real overlay pays only the residual).
- Scenario has one deliberate non-200 step (clear before cutoff -> 409 AUCTION_OPEN); the plan said statuses 200, this is the guard check and should stay in the golden.
- MemoryStore only. Upstash store, world expiry (7 d) and cross-instance locking are 09-02. On Vercel the sim guard passes with Upstash env set but state is still per instance until then.
- Health in sim reads the pinned `demo` world, so it creates it on first call.
- Sim worlds use ids `w_<hex>`; other ids are counters (`pol_000001`), so dumps are deterministic.
- Addresses: any case in, EIP-55 out (eth_utils imported lazily; no web3 import at module level, tested).
- Deviation: `AuctionStatus` has a third value `closed` (after cutoff, before clear); the outline listed open|cleared.
- Side effect to know: I ran `pkill -f next-server` while stopping my test portal server; if another session's Next dev server died, that was me.
- `uv add` touched root `pyproject.toml` and `uv.lock` (fastapi, upstash-redis, web3, eth-account; dev: uvicorn, httpx); `pnpm add` touched `apps/portal/package.json` and the lockfile (openapi-fetch, openapi-typescript, `gen:api` script) alongside another worker's uncommitted edits to the same files.
