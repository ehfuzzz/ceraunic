# Phase 9: Engine API, chain modes, house MM - Research

**Researched:** 2026-09-30
**Domain:** Hosting and API design for the engine behind the portal; `CHAIN_MODE` adapters (`sim` | `anvil` | `testnet`); house-MM scheduling; wallet stack on HyperEVM testnet; public-URL smoke test
**Confidence:** MEDIUM-HIGH overall. Hosting and limit facts are HIGH: they come from docs fetched today and from checks run on this Mac. Two things are MEDIUM because they are unmeasured until the first deploy: Python cold start on Vercel and the exact bundle layout. HyperEVM testnet RPC reachability is LOW (it failed from this Mac today).

## Summary

**Decision: Option B, hosted on Vercel's Python runtime.** A FastAPI app imports `wi.engine` directly. It deploys as its own Vercel project (`wi-engine`, framework `fastapi`) from a slim, git-less assembled bundle. The portal is a second Vercel project (Next.js 16) and proxies `/api/v1/*` to it with a Next rewrite, so the browser sees one origin. State lives in a new Upstash Redis database; the owner's Upstash account is already Pay-As-You-Go, and the first 10 databases are free. This keeps one engine implementation: the Phase 7 integer event reducer *is* the sim ledger, and the Phase 5 estimator runs unchanged. It also uses only accounts and CLIs that are already logged in on this Mac (Vercel as `ehfuzzz`, Upstash CLI), so nothing waits on the owner before a public URL exists.

The alternatives lose on concrete facts:
- **Option A (TypeScript port):** it would port a reducer and an estimator that Phases 7 and 5 are still writing, and money paths would drift between the two.
- **Cloud Run:** needs a GCP project with billing. `gcloud` is logged in, but the only projects belong to text311 and "My First Project". A new project is an owner-hand step.
- **Fly.io:** no `flyctl` on this Mac, no account, and every org needs a card on file.
- **Render:** the CLI is installed but its token returns 401, and free web services sleep after 15 minutes idle, with about 1 minute to wake.

**No daemon is needed for the house MM.** The sim clock is explicit state (a replay of historical days). The house-MM step runs inside `POST /sim/advance` and the auction `clear`, at the Phase 7 house cutoff (02:30Z), and is idempotent per tick key. A wall-clock cadence, if wanted, comes from an Upstash QStash schedule; Vercel Hobby cron runs once a day at most. Every write returns an **Execution envelope**:
- `done` in `sim` mode, and in `anvil` mode where the server signs with anvil's public keys.
- `needs_signature` in `testnet` mode, carrying a list of txs the browser signs through wagmi. The testnet engine process holds no private key at all, and a startup guard refuses to boot if one is present.

**Primary recommendation:** Build `src/wi/api/` as a FastAPI wrapper over `wi.engine`, with a `Ledger` protocol (`SimLedger` on Upstash, `EvmLedger` on web3.py) and one Execution-envelope write path. Deploy it as the `wi-engine` Vercel project behind a portal rewrite, and prove it with the MBC Playwright (channel `chrome`) at the production alias.

## Decision matrix: where the engine API runs

Checked on this Mac today: `vercel whoami` = ehfuzzz (CLI 50.13.2; latest is 61.1.0). `gcloud` is logged in (projects: nyc-civic-terminal, text311-spatial-tiles, My First Project). `render` 2.7.1 returns `401 Unauthorized`. There is no `flyctl`. `upstash` CLI 0.3.0 is logged in: DB `mainbrain` is PAYG and active, `mile-buy-club` is archived. `anvil`/`forge` 1.8.3 are in `~/.foundry/bin`.

| Criterion | A: TS engine in Next.js route handlers | **B-V: FastAPI on Vercel Python (recommended)** | B-CR: FastAPI on Cloud Run | C: FastAPI on Fly / Render |
|---|---|---|---|---|
| Time to public URL | Fast once the port exists; the port is the long pole | Fast: same Vercel login, `framework: fastapi` preset, no new account | Blocked on owner: new GCP project + billing link (don't reuse text311's projects); then `gcloud run deploy --source` | Blocked on owner: Fly signup + card; Render re-login |
| One engine, no drift | **No.** Ports the Phase 7 reducer (auction, pool waterfall, payoffs) and the Phase 5 estimator to TS; needs parity vectors on every change | **Yes.** `import wi.engine` | Yes | Yes |
| House-MM scheduler | Vercel cron: Hobby = once/day, ±59 min; Pro = per-minute. Or QStash, or lazy tick | Same as A. Not needed for the demo: the MM step runs inside advance/clear | Cloud Scheduler (3 free jobs per billing account) + Cloud Run jobs | Long-running loop, but Render free sleeps after 15 min; always-on needs a paid instance |
| Long-lived state | Upstash | Upstash (snapshot + event log per world) | Upstash (or Firestore) | Upstash; local disk is lost on Render free spin-down |
| Cold start | Node, small | Python. Measured imports on this Mac: fastapi 0.19 s, numpy 0.05 s, scipy.stats 0.67 s, web3 0.55 s. Lazy-import scipy/web3/statsmodels; Fluid compute reuses warm instances | Container start + imports; min-instances=1 removes it at a cost | Render free about 1 min after idle |
| Cost | Hobby + Upstash PAYG ($0.20 per 100K commands) | Same | Free tier 180k vCPU-s, 360k GiB-s, 2M req/month, but needs a billing account | Fly: card required; Render free with sleep, or paid |
| Secrets | Vercel env | Vercel env; testnet holds no keys | Secret Manager / env + IAM | Platform env |
| Limits that bite | 250 MB bundle | 500 MB Python bundle (the full project venv is **535 MB**, so ship a slim bundle); 4.5 MB request body; 300 s max duration (Hobby) | 32 MiB request (training knowledge, LOW) | — |

**Why not A.** The engine is the numerical reference, and Phase 7 makes it an integer event reducer whose money algorithm must match Solidity through parity vectors (07-RESEARCH "Key insight"). A TS port would be a third implementation of clearing, escrow and waterfall. It would also be written against a spec being frozen in the same 2 days, which is exactly the drift AGENTS.md calls silent money corruption. Phase 5's portal estimator (OLS + stored `priors.json`) runs server-side in Python at no extra cost.

**Why not Cloud Run now.** It works technically, but it waits on the owner to create a project and link billing. Keep it as the fallback host: the same FastAPI app runs there unchanged (`gcloud run deploy --source services/engine-api`). Revisit if any of these happen:
1. Python p50 cold start in the smoke test is above about 3 s after warm-up.
2. The slim bundle cannot stay under 500 MB.
3. The team needs a true always-on loop before Phase 17.

**Vercel Services (Beta).** Docs describe a Next.js frontend and a FastAPI backend in one project with `services` + service rewrites. It is Beta, marked "Permissions Required: Services (Beta)". It is not needed; consolidate later if wanted. Use two GA projects now. The account already has a frontend/API project pair (`best-before` / `best-before-api`).

## Standard Stack

### Core (engine API, Python)
| Library | Version | Purpose | Why standard |
|---|---|---|---|
| Python | 3.14 (Vercel offers 3.12 default, 3.13, 3.14) | Runtime | Matches `.python-version` and the Phase 5/7 venv |
| fastapi | 0.142.1 | HTTP layer; generates OpenAPI from pydantic | Vercel zero-config preset; OpenAPI becomes the TS types |
| pydantic | 2.13.5 | Request/response models (camelCase aliases) | Already a dep; the Phase 7 event models use it |
| upstash-redis | 1.8.0 | REST Redis client: `Redis.from_env()`, `set(nx=, px=)`, `eval()` | Serverless-safe (HTTP); verified in a venv today |
| web3 | 8.0.0 | `EvmLedger`: reads, `encode_abi`, anvil-key sends | Verified today against local anvil (sign + send + receipt) |
| eth-account | 0.14.0 | Anvil signers; Phase 7 EIP-712 reports | Already chosen by Phase 7 |
| numpy / scipy | 2.5.3 / 1.18.1 | Engine pricing only; lazy-import scipy | Phase 7 core deps |
| pandas / statsmodels | 3.0.6 / 0.15.0 | Only the elasticity endpoint (Phase 5 `design.py` + OLS); lazy import | Phase 5 reference; fits the 500 MB budget |
| uvicorn | 0.54.0 | Local dev server only | — |

### Portal side (already scaffolded by 10-01; keep)
| Library | Version | Purpose | Note |
|---|---|---|---|
| next | 16.3.7 | Portal; rewrite `/api/v1/*` to the engine | Latest stable (docs page version 16.3.7) |
| wagmi | **2.19.5 (pinned by 10-01)** | Wallet connect + tx sending (`wagmi/actions`) | Latest is 3.7.7; do not migrate in the window |
| viem | 2.57.1 | Chains (`hyperliquidEvmTestnet`, `anvil`) | Verified exports today |
| @tanstack/react-query | 5.104.0 | wagmi peer | — |
| openapi-typescript (dev) | 7.13.0 | Generate `engine-schema.d.ts` from FastAPI's `/api/v1/openapi.json` | Contract-first, no hand-written types |
| openapi-fetch | 0.17.0 | Typed fetch client over the generated `paths` | Tiny; no codegen runtime |

### Infra / tooling (present on this Mac)
| Tool | Version | Use |
|---|---|---|
| Vercel CLI | 50.13.2 local; use `npx -y vercel@latest` (61.1.0) | Deploy both projects; FastAPI preset needs ≥ 48.1.8 |
| Upstash CLI | 0.3.0 (logged in, PAYG) | `upstash redis create -n wi-demo -r us-east-1` (seat or owner action; produces a credential) |
| anvil / forge | 1.8.3 (`~/.foundry/bin`) | Local `anvil` mode; `make -C contracts anvil deploy-anvil` |
| Playwright | 1.59.1 in `~/Mile Buy Club/node_modules` | Smoke test. **Bundled Chromium is not installed; use `channel: 'chrome'`** (verified today) |

### Alternatives considered
| Instead of | Could use | Tradeoff |
|---|---|---|
| Two Vercel projects + rewrite | Vercel Services (one project) | One deploy and one domain, but Beta; untested with the old CLI |
| Vercel Python | Cloud Run | Always-on option, Cloud Scheduler; waits on an owner-created GCP project |
| web3.py in the API | viem in Next.js route handlers | A second server runtime. Only worth it if the engine were TS (Option A) |
| Plain wagmi + injected | RainbowKit 2.2.11 | Its peer is `wagmi ^2.9.0`, so it works with the pinned 2.19.5 but blocks wagmi 3. It adds a modal nobody needs for injected-only |
| Plain wagmi + injected | ConnectKit 1.9.2 | Peer `react 17.x \|\| 18.x`; the portal is on React 19. **Do not use** |
| Plain wagmi + injected | Reown AppKit 1.8.24 / WalletConnect | Needs a Reown projectId (owner account). Skip in v1 |
| JSON rows for sales upload | multipart `UploadFile` | Multipart needs `python-multipart` and hits the 4.5 MB body cap sooner. Phase 12's `SalesPanel` is already JSON |

**Installation:**
```bash
# engine (repo root pyproject gets these; the deploy bundle gets a slim copy)
uv add fastapi==0.142.1 upstash-redis==1.8.0 web3==8.0.0 eth-account==0.14.0
uv add --group dev uvicorn==0.54.0
# portal
pnpm -C apps/portal add openapi-fetch@0.17.0
pnpm -C apps/portal add -D openapi-typescript@7.13.0
```

## Architecture Patterns

### Recommended project structure
```
src/wi/engine/            # Phase 7 (pure). Rule for Phase 9: nothing the API imports may import
                          # pandas/xarray/netCDF4/matplotlib/pyarrow at module level (lazy inside functions)
src/wi/api/               # Phase 9
├── app.py                # FastAPI app, /api/v1 routers, startup guards
├── models.py             # pydantic wire models (camelCase aliases) = the OpenAPI contract
├── envelope.py           # Execution[T], TxRequest
├── store.py              # Upstash: world lock, snapshot + event log, idempotency; MemoryStore for tests/local
├── ledger/base.py        # Ledger protocol (buy_policy, post_order, clear, deposit, withdraw, positions, settlements)
├── ledger/sim.py         # SimLedger: engine reducer state per world (Upstash)
├── ledger/evm.py         # EvmLedger: web3.py; signers = anvil keys | {} (testnet)
├── clock.py              # sim clock: emits Phase 7 scheduler events for the next day(s)
├── house_mm.py           # tick(world|chain) -> TickResult; calls wi.engine.house_mm / hedge
├── snapshot_data.py      # loads demo-data/*.json.gz (ladders, CLI values, priors) - no parquet at runtime
└── jobs.py               # CLI: `python -m wi.api.jobs tick|advance|scenario ...`
services/engine-api/      # static deploy files: app.py (re-export), pyproject.toml (slim), vercel.json, .python-version
scripts/build-demo-snapshot.py   # Phase 1 parquet -> data/demo/*.json.gz (window chosen by the planner)
scripts/deploy-engine.sh  # assemble git-less slim bundle in $TMPDIR, import check, vercel deploy --prod
scripts/smoke-demo.mjs    # API loop + UI loop at a URL (MBC Playwright, channel chrome)
tests/api/scenario_nyc_3d.json + golden/  # mode-parity scenario (sim vs anvil)
apps/portal/src/lib/engine-schema.d.ts    # generated
apps/portal/src/lib/api.ts                # keep EngineApi method names; bodies call openapi-fetch
apps/portal/src/lib/execute.ts            # runs Execution envelopes (wagmi actions)
```

### Pattern 1: Deploy topology (two GA Vercel projects, one browser origin)
**What:** `wi-portal` (Next.js, `framework: nextjs`) and `wi-engine` (FastAPI, `framework: fastapi`). The portal's `next.config.ts` rewrites `/api/v1/:path*` to `${ENGINE_ORIGIN}/api/v1/:path*`. `ENGINE_ORIGIN` is the engine's **production alias** (for example `https://wi-engine.vercel.app`), never a per-deployment URL: those are SSO-gated and 302 to login (MBC lesson). Portal-local routes (`/api/pos/*` from Phase 12) are untouched, because the rewrite only matches `/api/v1`.
**When:** Now. Phase 13-01 creates both projects; Phase 9 owns the engine one.
**Deploy:** assemble a git-less copy and `vercel deploy --prod` from it. This is the MBC `deploy-demo.sh` pattern: it sidesteps the git-author seat block and root-level junk uploads.

### Pattern 2: `CHAIN_MODE` switch + `Ledger` protocol + startup guards
**What:** `CHAIN_MODE` is read once in `src/wi/api/app.py`. `sim` → `SimLedger(store)`. `anvil`/`testnet` → `EvmLedger(mode)`. Routes call only the `Ledger` protocol, so behaviour differs by adapter, not by `if mode` in handlers. The engine is the **source of truth for the mode**: the portal reads `GET /api/v1/config`. The portal's build-time `CHAIN_MODE` (10-01) stays for the header pill, plus a "portal/engine mode mismatch" banner if the two differ.
**Guards (refuse to boot):**
- `testnet` with any env var matching `PRIVATE_KEY|MNEMONIC`.
- `anvil` with `VERCEL=1` (anvil is local-only).
- `sim` with `VERCEL=1` but no `UPSTASH_REDIS_REST_URL`, because in-memory state is per instance.

### Pattern 3: Execution envelope (one write path, three modes)
**What:** Every mutating endpoint returns `Execution[T] = {mode, status: "done"|"needs_signature", result?: T, txs: TxRequest[]}`.
- `sim`: the engine applies events and returns `done`.
- `anvil`: the server signs with anvil's public keys and returns `done`. With `ANVIL_SERVER_SIGNS_USERS=0` it returns `needs_signature` instead, so the wallet path can be tested locally with MetaMask on 31337 before the owner deploys.
- `testnet`: returns `needs_signature` with ordered txs, e.g. `[MockUSDC.approve, PolicyManager.buy]`. The portal runs them with `wagmi/actions` (`switchChain` → `sendTransaction` → `waitForTransactionReceipt`), then calls `POST /api/v1/tx/{hash}/confirm` to get the resulting object.
**Why:** "No UI change on flip" becomes literal. Components call `api.buyPolicy()` and render the same states; only the envelope's status differs. The portal needs no ABIs (the API builds calldata with `contract.encode_abi`).

### Pattern 4: Sim world = engine reducer state in Upstash, one world per visitor
**What:** Keys `wi:w:{world}:snap` (canonical state JSON + seq + sha256) and `wi:w:{world}:events` (RPUSH, Phase 7 hash-chained JSONL lines). `wi:w:{world}:lock` is a SET NX PX mutex. `wi:w:{world}:idem:{key}` caches write results for 24 h.

Each write runs these steps:
1. Lock the world.
2. Restore the snapshot.
3. Build the events with the engine.
4. `Engine.apply` each event; invariants are asserted inside `apply`.
5. Save the snapshot and append the events in one pipeline.
6. Unlock.

The world id travels in the header `X-WI-World`. The portal keeps it in localStorage and creates it with `POST /sim/worlds` from template `demo-5-cities`. Visitor worlds expire after 7 days. The owner's `demo` world is pinned and can be reset by admin.
**Why:** One public URL must not let one visitor corrupt the owner's live demo. The reducer, not the API, owns every state transition, so there is no second implementation of money logic.

### Pattern 5: Sim clock + house-MM step (no daemon)
**What:** The sim clock is a replayed historical calendar held in world state. `POST /sim/advance {days}` walks the Phase 7 daily timeline and applies each scheduler event from the bundled snapshot data:
1. House cutoff 02:30Z: the house MM posts its quote schedule.
2. Public cutoff 03:00Z: clear.
3. Hedge at T−24h.
4. Oracle fetch at D+1 12:00Z.
5. Finalize at D+2.
6. Epoch 12:30Z.

`house_mm.tick()` is one pure step keyed by `(world, simTs)`, so a retried tick is a no-op. It is called from `advance`, from `clear` (if the house quote for that auction is missing), from `POST /admin/house-mm/tick`, and from the CLI.
**Wall clock (optional):** a QStash schedule (free: 1,000 messages/day, 10 schedules) POSTs `/api/v1/admin/house-mm/tick` with the admin header. Vercel Hobby cron is at most daily, ±59 min, which is fine only for a daily settlement read. Nothing in the 5-minute demo depends on a timer; the presenter clicks "advance day".

### Pattern 6: Testnet key split (the API never holds the owner's key)
| Role | Sim | Anvil (public test keys) | Testnet |
|---|---|---|---|
| Deployer/admin | — | acct #0 `0xf39F…2266` (Makefile already uses it) | **Owner's key, owner's shell only** (`make deploy-testnet`) |
| House MM / pool agent | engine | acct #1 `0x7099…79C8` | Owner-generated role key, owner-run loop (`python -m wi.api.jobs house-mm --mode testnet`); Phase 17 |
| Oracle reporter (EIP-712 signer) | engine | acct #2 `0x3C44…93BC` | Owner-run script signs reports; anyone submits (Phase 7) |
| Keeper (clear/finalize/epoch) | engine | acct #3 `0x90F7…b906` | Permissionless: any connected wallet from the admin page |
| Users | demo address | accts #4–#9 (server-signed) or MetaMask | User's wallet via wagmi; faucet = user calls the open `MockUSDC.mint` |

In testnet mode, the engine's only chain powers are reading and building calldata. Derive anvil keys from the standard mnemonic `test test test test test test test test test test test junk` (paths m/44'/60'/0'/0/i). The addresses above were verified today.

### Pattern 7: Chain reads on HyperEVM (docs-driven)
HyperEVM JSON-RPC limits that shape the design:
- `eth_call`, `eth_getBalance`, `eth_getCode` and `eth_getStorageAt` work on the **latest block only**.
- `eth_getLogs` is capped at **50 blocks** (about 50 s at 1 s blocks).
- `rpc.hyperliquid.xyz/evm` allows 100 requests/min per IP; the docs say RPC rate limits match the API server. Vercel functions share egress IPs.

Design around them:
1. Never index positions from logs. Phase 8 exposes enumerable views plus one **Lens/Reader view contract** that returns a user's positions, orders, pool state and settlements in a single `eth_call`.
2. Cache reads in Upstash for 5 s (`wi:chain:{chainId}:{key}`).
3. Take the RPC from `HYPEREVM_RPC_URL`, with an optional provider list (Alchemy, QuickNode, Chainstack are listed as HyperEVM RPC providers; accounts are owner-hand).
4. Keep every user tx small. Fast blocks are 1 s / **3M gas**; slow blocks are 1 min / 30M gas and need the sender's HyperCore `evmUserModify {usingBigBlocks: true}` flag.
5. Cap orders per auction in testnet mode, so a permissionless `clear` fits under 3M gas.

### Pattern 8: Contract-first OpenAPI → generated TS
FastAPI serves `/api/v1/openapi.json` from `models.py`. The portal runs `openapi-typescript http://127.0.0.1:8787/api/v1/openapi.json -o src/lib/engine-schema.d.ts` and wraps `openapi-fetch` inside the existing `EngineApi` facade: 10-01 froze the method names; bodies and shapes change. 09-01 ships `models.py` + stub routes returning fixture data **first**, so Phases 10 and 11 build against the real contract while the ledger is being written.

### Pattern 9: TS server code, if any (research question 2)
- Next.js route handlers (`app/**/route.ts`, `export async function POST(request: Request)`) are **bundled by Next**, so the owner's `.js`-extension gotcha does **not** apply to them. The gotcha applies to standalone Vercel `api/*.ts` functions in a `"type": "module"` package, which Vercel transpiles without bundling (mainbrain's layout).
- Do not add a root `api/` folder to the portal project: those files would build as standalone functions, where the gotcha applies.
- In Next 16, `context.params` is a Promise.
- If a route needs Redis, use mainbrain's pattern: `export const redis = Redis.fromEnv()` in a server-only module (`@upstash/redis` 1.39.0).
- The portal needs no Upstash in this design.

### Anti-patterns to avoid
- **One global sim state on a public URL.** Visitors overwrite the demo. Use worlds.
- **In-memory state in a serverless function.** Each instance has its own copy and state vanishes. Guard at boot.
- **Floats for money on the wire.** Sim and chain disagree by rounding. Use integer USDC base units (`…E6`).
- **Two sources of truth for the mode.** Portal and engine drift. The engine's `/config` wins.
- **The API "helpfully" signing testnet txs with an env key.** That violates the owner rule. The testnet guard makes it impossible.
- **Positions from `eth_getLogs` on HyperEVM.** 50-block windows at 100 req/min cannot cover history.
- **Shipping the whole project venv.** It is 535 MB (pyarrow 123, scipy 83, netCDF4 57, statsmodels 52, pandas 50 MB) against a 500 MB limit and slow cold starts.

## API Contract (OpenAPI outline, shared by sim / anvil / testnet)

**Conventions**
- Base path `/api/v1`. JSON camelCase (pydantic `alias_generator=to_camel`, `populate_by_name=True`).
- Money = integer USDC base units, suffix `E6` (1,000,000 = $1; JS-safe up to about $9e9).
- Temperatures in tenths of °F (`…TenthsF`), rain in hundredths of an inch, days as `YYYY-MM-DD` climate days, timestamps ISO-8601 `Z`. These are the Phase 7 unit table.
- Addresses are EIP-55 checksummed on output and accepted in any case on input (normalized at the boundary).
- Headers:
  - `X-WI-World` (sim; default `demo`).
  - `Idempotency-Key` (all POST writes; 24 h replay of the first result).
  - `X-Admin-Token` (admin routes; `secrets.compare_digest`).
- Errors: RFC 9457 `application/problem+json` `{type,title,status,detail,code}`.
- Every write returns `200` with an `Execution`.

```yaml
openapi: 3.1.0
info: { title: weather-insurance engine API, version: 0.1.0 }
paths:
  # meta
  /api/v1/health:              { get: { returns: Health } }          # {ok, mode, chainId?, engineVersion, specHash, simTime?}
  /api/v1/config:              { get: { returns: Config } }          # {mode, chain{id,name,rpcUrl,explorerUrl?}, contracts{name:address},
                                                                      #  stations[], contracts listed for auction, schedule{houseCutoffUtc:"02:30",publicCutoffUtc:"03:00"},
                                                                      #  limits{maxOrdersPerAuction,maxSalesRows,maxBodyBytes}}
  # sim world (409 MODE_NOT_SIM in anvil/testnet)
  /api/v1/sim/worlds:          { post: { body: {template?: "demo-5-cities"}, returns: {worldId, simTime} } }
  /api/v1/sim/worlds/{worldId}/reset: { post: { admin: when worldId == "demo", returns: {worldId, simTime} } }
  /api/v1/sim/advance:         { post: { body: {days: 1..10}, returns: {simTime, events: EventSummary[]} } }
  /api/v1/sim/clock:           { get:  { returns: {simTime, nextEvents: EventSummary[]} } }
  # accounts
  /api/v1/accounts/{address}/balances: { get: { returns: Balances } }   # {usdcE6, lockedE6, seniorShares, juniorShares}
  /api/v1/faucet:              { post: { body: {address, amountE6}, returns: Execution<Balances> } }  # testnet: MockUSDC.mint tx
  # onboarding + elasticity
  /api/v1/businesses:          { post: { body: {name, lat, lon, zip?, naics?, owner: Address}, returns: Business } }
                                                                      # Business {businessId, city, settlementStation, locationIndex, residualContractId}
  /api/v1/businesses/{id}:     { get: { returns: Business } }
  /api/v1/businesses/{id}/sales: { post: { body: {source: csv|square|fixture, rows: [{date, grossSalesCents, orderCount?}]},
                                           returns: SalesSummary } }  # {rows, firstDate, lastDate, gaps, warnings[]}; <= limits.maxSalesRows
  /api/v1/businesses/{id}/elasticity: { post: { returns: Elasticity } } # {heat{beta,se,n}, wet{beta,se,n}, shrinkWeight,
                                                                      #  prior{sector,mu,tau2,learned:boolean}, origin, method}
  /api/v1/businesses/{id}/recommendation: { get: { returns: Recommendation } }
                                                                      # {peril, strikeTenthsF, capTenthsF, unitsPerDay, maxDailyPremiumE6,
                                                                      #  path:"house-hedge", heEstimate, rationale[]}
  # quotes + policies (both hedge-leg paths)
  /api/v1/quotes:              { post: { body: QuoteRequest, returns: Quote } }
      # QuoteRequest {businessId, peril: heat|cold|rain, strikeTenthsF, capTenthsF, units, startDay, endDay,
      #               path: house-hedge|business-ladder}
      # Quote {quoteId, expiresAt, premiumE6, stationLegE6, residualLegE6, feesE6, maxPayoutE6, heEstimate,
      #        stationLeg{series, asOf, rungs[{ticker, qty, askCents}], overroundBp},
      #        residualLeg{contractId, qty, fairPriceE6, halfSpreadE6},
      #        ladderForBusiness?: rungs[]   # business-ladder path: instructions only; we never place Kalshi orders
      # }
  /api/v1/policies:            { post: { body: {quoteId, holder: Address}, idem: true, returns: Execution<Policy> },
                                 get:  { query: {holder}, returns: Policy[] } }
      # Policy {policyId, businessId, path, days[], units, premiumE6, maxPayoutE6, status: active|settled|expired, settlements[]}
  /api/v1/policies/{policyId}: { get: { returns: Policy } }
  # residual auctions (one per contractId x day; Phase 7 keys by contract id, not station)
  /api/v1/auctions:            { get: { query: {day?, status?: open|cleared}, returns: AuctionSummary[] } }
  /api/v1/auctions/{auctionId}: { get: { returns: Auction } }         # {..., book{bids[],asks[]} aggregated, houseQuote?{bidE6,askE6,maxQty}, result?}
  /api/v1/auctions/{auctionId}/orders: { post: { body: {trader, side: buy|sell, qty, limitPriceE6}, idem: true, returns: Execution<Order> } }
  /api/v1/auctions/{auctionId}/orders/{orderId}: { delete: { query: {trader}, returns: Execution<Order> } }
  /api/v1/auctions/{auctionId}/clear: { post: { returns: Execution<ClearingResult> } }
      # permissionless after publicCutoff; sim: 409 AUCTION_OPEN before cutoff unless X-Admin-Token
      # ClearingResult {priceE6, filledQty, fills[{orderId,trader,side,qty}], poolFilledQty,
      #                 conservation{longLockedE6, shortLockedE6, ok}}
  # pool (queued to epochs per Phase 7)
  /api/v1/pool:                { get: { returns: PoolState } }
      # {seniorAssetsE6, juniorAssetsE6, seniorShares, juniorShares, seniorRateBp, utilizationBp, lockedE6, freeE6,
      #  exposureByContract[], queue{deposits[],withdrawals[]}, navHistory[]}
  /api/v1/pool/deposits:       { post: { body: {owner, tranche: senior|junior, amountE6}, idem: true, returns: Execution<QueueTicket> } }
  /api/v1/pool/withdrawals:    { post: { body: {owner, tranche, shares}, idem: true, returns: Execution<QueueTicket> } }
  # positions + settlements
  /api/v1/positions:           { get: { query: {owner}, returns: Positions } }
      # {balances, policies[], residuals[{contractId,day,side,qty,entryPriceE6,lockedE6}], lp[{tranche,shares,valueE6}], openOrders[]}
  /api/v1/settlements:         { get: { query: {owner, fromDay?, toDay?}, returns: Settlement[] } }
      # {refId, kind: policy|residual, day, index, value, unit, source, vintageHash, status: pending|reported|final|disputed, payoutE6}
  # house MM + oracle (admin)
  /api/v1/admin/house-mm:      { get: { admin: true, returns: {quotes[], inventory[], hedges[{series,day,rungs,costE6,payoutE6?}], pnlE6, capsUsed} } }
  /api/v1/admin/house-mm/tick: { post: { admin: true, body: {asOf?}, returns: TickResult } }   # {tickKey, quotesPosted, hedgesPlaced, events[]}; idempotent
  /api/v1/admin/oracle:        { get: { admin: true, returns: OracleRow[] } }                   # {index, day, value, source, vintageHash, fetchedAt, status}
  /api/v1/admin/oracle/report: { post: { admin: true, body: {index, day}, returns: Execution<OracleRow> } }  # testnet: 409 OWNER_SCRIPT
  # testnet tx follow-up
  /api/v1/tx/{hash}/confirm:   { post: { returns: {status, blockNumber, objects[]} } }         # reads receipt, busts read cache
  /api/v1/openapi.json:        { get: {} }
components:
  Execution<T>: {mode: sim|anvil|testnet, status: done|needs_signature, result?: T, txs: TxRequest[]}
  TxRequest:    {chainId: int, to: Address, data: Hex, value: string /*wei*/, description: string}
  Problem.code: [VALIDATION, NOT_FOUND, QUOTE_EXPIRED, AUCTION_OPEN, AUCTION_CLOSED, MODE_NOT_SIM, MODE_READ_ONLY,
                 OWNER_SCRIPT, WORLD_BUSY, MARGIN_EXCEEDED, CAP_EXCEEDED, INSUFFICIENT_BALANCE, POOL_UTILIZATION,
                 ORDER_LIMIT, RPC_UNAVAILABLE]
```

**Mapping to the 10-01 `EngineApi` facade (names kept, shapes change):**
- `quote` → `POST /quotes`.
- `buyPolicy` → `POST /policies`.
- `postOrder` → `POST /auctions/{id}/orders`.
- `runAuction` → `POST /auctions/{id}/clear`.
- `poolDeposit` / `poolWithdraw` → `POST /pool/deposits` / `POST /pool/withdrawals`.
- `positions` / `settlements` → the two GETs.
- `uploadSales` → `POST /businesses/{id}/sales`. The portal parses the CSV into Phase 12's `SalesPanel` client-side.

Deliberate deviations from the stub:
- `number` USDC becomes `…E6` integers.
- `txHash?` becomes the Execution envelope.
- `Placeholder` is dropped.
- `HedgePath` keeps `"house-hedge" | "business-ladder"`.

## Parity strategy

**With B (recommended)** there is one off-chain implementation, so parity is about the chain, not about languages.
1. **Engine ↔ Solidity:** Phase 7 already emits `parity/*.json` vectors (orders→fills, payouts, waterfall steps) that Foundry reads with `vm.parseJson`. Phase 9 adds nothing here.
2. **API mode parity (Phase 9's test):** `tests/api/scenario_nyc_3d.json` is one scripted HTTP scenario:
   - create a world, a heat-long business near LGA and a heat-short business near Central Park;
   - quote, buy on both paths, faucet, deposit junior + senior, post orders, advance through cutoff and clear, advance 3 days, read settlements and pool.

   Run it against `sim` and against local `anvil` (server-signed). Normalize responses by dropping ids, tx hashes, timestamps and blockNumber. Assert that every `…E6` field, qty and status equals the committed golden `tests/api/golden/scenario_nyc_3d.json` **exactly**. The golden comes from a sim run and is reviewed once. This catches silent money differences between the reducer and the contracts at the API boundary. It is an end-to-end artifact test, not a mirror test.
3. **Point-in-time check:** the same scenario asserts that the quote for day D uses snapshot asks with `asOf ≤ D 03:00Z − 0` and that no settlement for D exists before simTime D+2 12:00Z. Look-ahead is an AGENTS.md silent-corruption case.

**If the planner overrides to A** (not recommended), the Python engine writes `parity/ts/{quote,clear,waterfall,payoff,elasticity}.json`: input plus expected output, integers for money, 1e-6 relative tolerance for elasticity floats. A vitest suite in `packages/engine-ts` asserts them. `make parity` regenerates the vectors and is a verify step in every plan touching `wi.engine`. Budget a full plan for the port plus one for the estimator.

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---|---|---|---|
| State transitions for sim money | Handler-level balance math in the API | `wi.engine` reducer (`Engine.apply`, invariants inside) | One money algorithm; conservation asserted per event |
| OpenAPI + TS types | Hand-written TS interfaces | FastAPI `/openapi.json` → `openapi-typescript` → `openapi-fetch` | Contract cannot drift from the server |
| Calldata encoding | Manual ABI packing | web3.py `Contract.encode_abi(fn, args=[...])` (verified v8) | Byte-exact; ABIs from `contracts/out` |
| Tx signing (anvil) | Raw RLP | `eth_account.Account.from_key(k).sign_transaction(tx).raw_transaction` (verified) | EIP-1559 fields validated |
| Wallet connect | Custom EIP-1193 plumbing | wagmi 2.19.5 `injected()` (EIP-6963 discovery) + `wagmi/actions` | Already in the 10-01 scaffold |
| Distributed lock | Ad-hoc flags | Redis `SET NX PX` + compare-and-delete Lua via `eval` | Standard single-instance lock; Upstash supports both |
| Scheduling | A sleeping loop in a function | Explicit sim clock; QStash schedule for wall-clock ticks | Serverless has no long-lived process |
| EIP-712 reports | Custom hashing | `eth_account` `encode_typed_data` / `sign_typed_data` (Phase 7) | Matches OZ `EIP712` |
| Browser automation runtime | Downloading browsers | MBC Playwright + `channel: 'chrome'` | Bundled Chromium is absent; Chrome is installed |

**Key insight:** the demo's credibility is that the portal's numbers *are* the paper's engine. Every layer the API adds should be transport (HTTP, envelopes, storage, chain I/O), never logic.

## Common Pitfalls

### Pitfall 1: Shared sim state on a public URL
**What goes wrong:** An investor clicking around empties the pool or cancels the owner's orders mid-pitch. **Why:** One global state. **Avoid:** Per-visitor worlds (`X-WI-World`) plus a pinned `demo` world with admin reset. **Warning sign:** the smoke test passes alone but fails when run twice in parallel.

### Pitfall 2: Lost updates and double-applies
**What goes wrong:** Two concurrent POSTs both read snapshot N and one write is lost; a retried buy charges twice; a retried tick settles twice. **Avoid:** A world lock around restore→apply→save; `Idempotency-Key` on writes; tick keyed by `(world, simTs)`. **Test (money failure):** fire the same buy twice with one key, and two different buys concurrently. Assert one policy in the first case, two in the second, and conserved balances.

### Pitfall 3: Float money across the boundary
**What goes wrong:** The UI shows $12.35, the contract charges 12.349999, and sim ≠ anvil by 1 base unit. **Avoid:** `…E6` integers everywhere on the wire. The engine's `tdiv` rounding (Phase 7) is the only rounding.

### Pitfall 4: Python bundle bloat / heavy imports
**What goes wrong:** Deploy fails at 500 MB, or cold start is multi-second. **Why:** The whole-project venv is 535 MB, and `wi.engine.oracle` may import netCDF4 at the top. **Avoid:** Slim `services/engine-api/pyproject.toml`; lazy imports; the deploy script builds a clean venv from the slim deps and runs `python -X importtime -c "import wi.api.app"`. A `ModuleNotFoundError` (netCDF4, xarray, pyarrow, matplotlib) fails the deploy.

### Pitfall 5: Vercel project gotchas already paid for in MBC
- The framework preset is null when a project is created by CLI, so every route 500s. Set `"framework": "nextjs"` / `"fastapi"` in each `vercel.json` (both slugs verified in the schema).
- Deploying from the working tree hits the git-author seat block. Deploy an assembled git-less copy.
- Per-deployment URLs are SSO-gated. Use production aliases for `ENGINE_ORIGIN` and the smoke test.
- The local CLI is 11 majors behind. Use `npx -y vercel@latest`.

### Pitfall 6: Mode drift between portal and engine
**What goes wrong:** The portal (build-time `CHAIN_MODE=testnet`) shows wallet prompts while the engine is still `sim`, or the reverse. **Avoid:** The engine's `/api/v1/config` is truth; the portal shows a mismatch banner; the flip runbook sets both env vars and redeploys both.

### Pitfall 7: HyperEVM RPC constraints
- The 100 req/min per-IP limit on the official RPC is shared across Vercel egress.
- `eth_call` works on the latest block only.
- `eth_getLogs` is capped at 50 blocks.
- Fast blocks carry 3M gas.

**Avoid:** Lens view contract, a 5 s read cache, and bounded per-tx gas. Cap `maxOrdersPerAuction` in testnet so a clear fits 3M gas; Phase 8 measures gas per order with `forge test --gas-report`. **Warning signs:** 429s from RPC; `clear` reverting out of gas once the book grows.

### Pitfall 8: HyperEVM testnet RPC unreachable (observed today)
From this Mac on 2026-09-30, `rpc.hyperliquid-testnet.xyz` does not resolve through the local resolver. Google and Cloudflare DoH resolve it to 3.170.19.x, but a pinned-IP TLS handshake is reset, with and without the sandbox. Mainnet `rpc.hyperliquid.xyz/evm` answered `0x3e7` normally, and `api.hyperliquid-testnet.xyz/info` answered. **Avoid:** `HYPEREVM_RPC_URL` env with fallbacks; check reachability from a Vercel function (`GET /api/v1/health` in testnet mode reports the RPC chainId) before Phase 17. Nothing in the sim demo depends on it.

### Pitfall 9: Wallet library peer conflicts
- RainbowKit 2.2.11 peers `wagmi ^2.9.0` (blocks wagmi 3).
- ConnectKit 1.9.2 peers React 17/18 (the portal is on React 19).
- wagmi 3 renamed `useAccount`→`useConnection` and made connector SDKs optional peers.

**Avoid:** Stay on the scaffolded wagmi 2.19.5 + `injected()`; no modal library.

### Pitfall 10: Address checksum strictness
viem and web3.py both reject mis-checksummed mixed-case addresses (hit today in a probe). **Avoid:** Normalize at the API boundary (`Web3.to_checksum_address` on input); Redis keys use lowercase.

### Pitfall 11: Request limits
The Vercel function body limit is 4.5 MB (413 `FUNCTION_PAYLOAD_TOO_LARGE`), and it applies through the rewrite. **Avoid:** Sales rows as JSON, capped by `limits.maxSalesRows` (e.g. 5,000 rows is about 200 KB), with the portal checking before POST.

### Pitfall 12: Keys in testnet mode
**What goes wrong:** Someone sets `HOUSE_MM_PRIVATE_KEY` on the Vercel engine "just for the demo". **Avoid:** The boot guard refuses; the house MM on testnet is an owner-run local process in Phase 17. The engine's only testnet writes are `needs_signature` envelopes.

### Pitfall 13: Look-ahead in the sim replay
**What goes wrong:** Quotes for day D use ladders or CLI values recorded after the cutoff, so the demo shows hedge performance that was impossible. **Avoid:** `snapshot_data` lookups take `asOf` and assert `asOf ≤ simTime`; this is part of the parity scenario (Parity 3).

### Pitfall 14: Hobby plan limits
- Cron is once a day, ±59 min.
- Functions max out at 300 s.
- Hobby is "non-commercial personal use only" (fair-use guidelines).

A fundraising demo is a gray area: MBC's investor demo already runs on Hobby, and the Pro plan removes the question. Flag it to the owner; don't block on it.

## Code Examples

### Engine: app, guards, envelope (Python)
```python
# src/wi/api/app.py  (sketch; wire models live in models.py)
from __future__ import annotations
import os, re
from typing import Generic, Literal, TypeVar
from fastapi import FastAPI, Header
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

MODE = os.environ.get("CHAIN_MODE", "sim")
if MODE not in ("sim", "anvil", "testnet"):
    raise RuntimeError(f"CHAIN_MODE={MODE!r}")
if MODE == "testnet" and any(re.search("PRIVATE_KEY|MNEMONIC", k) for k in os.environ):
    raise RuntimeError("testnet engine must hold no keys")          # owner rule, enforced at boot
if MODE == "anvil" and os.environ.get("VERCEL"):
    raise RuntimeError("anvil mode is local-only")
if MODE == "sim" and os.environ.get("VERCEL") and not os.environ.get("UPSTASH_REDIS_REST_URL"):
    raise RuntimeError("sim on Vercel needs Upstash (in-memory state is per instance)")

class Wire(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

T = TypeVar("T")
class TxRequest(Wire):
    chain_id: int
    to: str
    data: str
    value: str = "0"          # wei, decimal string
    description: str
class Execution(Wire, Generic[T]):
    mode: Literal["sim", "anvil", "testnet"]
    status: Literal["done", "needs_signature"]
    result: T | None = None
    txs: list[TxRequest] = []

app = FastAPI(title="weather-insurance engine API", version="0.1.0",
              openapi_url="/api/v1/openapi.json", docs_url="/api/v1/docs")

@app.get("/api/v1/health")
def health() -> dict:
    return {"ok": True, "mode": MODE}
```

### Engine: Upstash world lock + idempotency (Python, upstash-redis 1.8.0 API verified)
```python
# src/wi/api/store.py
import json, secrets, time
from upstash_redis import Redis

_UNLOCK = "if redis.call('get',KEYS[1])==ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end"

class Store:
    def __init__(self, prefix: str = "wi"):
        self.r, self.p = Redis.from_env(), prefix      # UPSTASH_REDIS_REST_URL / _TOKEN

    def _k(self, world: str, *parts: str) -> str:
        return ":".join([self.p, "w", world, *parts])

    def with_world(self, world: str, fn, ttl_ms: int = 15_000):
        key, token = self._k(world, "lock"), secrets.token_hex(8)
        for _ in range(50):                              # ~5 s
            if self.r.set(key, token, nx=True, px=ttl_ms):
                break
            time.sleep(0.1)
        else:
            raise WorldBusy(world)                       # -> 409 WORLD_BUSY
        try:
            snap = self.r.get(self._k(world, "snap"))
            new_snap, events, result = fn(json.loads(snap) if snap else None)   # engine restore/apply/snapshot
            p = self.r.pipeline()
            p.set(self._k(world, "snap"), json.dumps(new_snap, sort_keys=True, separators=(",", ":")))
            for line in events:
                p.rpush(self._k(world, "events"), line)  # Phase 7 canonical hash-chained lines
            p.exec()
            return result
        finally:
            self.r.eval(_UNLOCK, keys=[key], args=[token])

    def idem(self, world: str, idem_key: str | None, compute):
        if not idem_key:
            return compute()
        k = self._k(world, "idem", idem_key)
        if (hit := self.r.get(k)) is not None:
            return json.loads(hit)
        out = compute()
        self.r.set(k, json.dumps(out), ex=86_400)
        return out
```

### Engine: EvmLedger read / anvil send / testnet prepare (Python, web3 8.0.0 verified against anvil)
```python
# src/wi/api/ledger/evm.py
import json, os
from pathlib import Path
from eth_account import Account

ANVIL_MNEMONIC = "test test test test test test test test test test test junk"   # public test mnemonic
ROLES = {"deployer": 0, "house": 1, "oracle": 2, "keeper": 3}

class EvmLedger:
    def __init__(self, mode: str, root: Path = Path(".")):
        from web3 import Web3                      # lazy: sim mode never imports web3 (~0.55 s)
        self.Web3, self.mode = Web3, mode
        rpc = os.environ["HYPEREVM_RPC_URL"] if mode == "testnet" else os.environ.get("ANVIL_RPC_URL", "http://127.0.0.1:8545")
        self.w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 10}))
        self.chain_id = self.w3.eth.chain_id       # 998 or 31337
        dep = json.loads((root / f"contracts/deployments/{self.chain_id}.json").read_text())
        abi = lambda n: json.loads((root / f"contracts/abi/{n}.json").read_text())   # copied from contracts/out at deploy
        self.c = {n: self.w3.eth.contract(address=Web3.to_checksum_address(a), abi=abi(n)) for n, a in dep["contracts"].items()}
        self.signers = {}
        if mode == "anvil":
            Account.enable_unaudited_hdwallet_features()
            self.signers = {r: Account.from_mnemonic(ANVIL_MNEMONIC, account_path=f"m/44'/60'/0'/0/{i}") for r, i in ROLES.items()}

    def positions(self, owner: str):
        return self.c["Lens"].functions.positionsOf(self.Web3.to_checksum_address(owner)).call()   # latest block only

    def write(self, contract: str, fn: str, args: list, *, role: str | None, value: int = 0):
        c = self.c[contract]
        if self.mode == "testnet" or role is None:  # user action, or testnet: browser signs
            return {"status": "needs_signature", "txs": [{"chainId": self.chain_id, "to": c.address,
                    "data": c.encode_abi(fn, args=args), "value": str(value), "description": f"{contract}.{fn}"}]}
        acct = self.signers[role]
        tx = getattr(c.functions, fn)(*args).build_transaction(
            {"from": acct.address, "nonce": self.w3.eth.get_transaction_count(acct.address),
             "chainId": self.chain_id, "value": value})
        h = self.w3.eth.send_raw_transaction(acct.sign_transaction(tx).raw_transaction)
        rcpt = self.w3.eth.wait_for_transaction_receipt(h, timeout=30)
        if rcpt.status != 1:
            raise TxReverted(f"{contract}.{fn}")
        return {"status": "done", "txHash": h.hex()}
```

### Deploy files for `wi-engine`
```json
// services/engine-api/vercel.json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "framework": "fastapi",
  "functions": { "app.py": { "maxDuration": 60,
    "excludeFiles": "{tests/**,**/test_*.py,**/__pycache__/**}" } }
}
```
```toml
# services/engine-api/pyproject.toml  (slim; NOT the repo root pyproject)
[project]
name = "wi-engine-api"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi==0.142.1", "pydantic==2.13.5", "upstash-redis==1.8.0",
  "numpy==2.5.3", "scipy==1.18.1",
  "web3==8.0.0", "eth-account==0.14.0",
  "pandas==3.0.6", "statsmodels==0.15.0",   # elasticity endpoint only (lazy import)
]
```
```python
# services/engine-api/app.py  - Vercel entrypoint (top-level `app`)
from wi.api.app import app  # noqa: F401   (wi/ is copied beside this file by deploy-engine.sh)
```
```bash
# scripts/deploy-engine.sh (outline; MBC deploy-demo.sh pattern)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; OUT="$(mktemp -d)/wi-engine"; mkdir -p "$OUT/contracts/abi"
cp -R "$ROOT/src/wi" "$OUT/wi"; rm -rf "$OUT/wi/data" "$OUT/wi/eval"          # loaders/eval never ship
cp "$ROOT/services/engine-api/"{app.py,pyproject.toml,vercel.json} "$OUT/"; echo 3.14 > "$OUT/.python-version"
mkdir -p "$OUT/demo-data" && cp "$ROOT/data/demo/"*.json.gz "$OUT/demo-data/"
mkdir -p "$OUT/contracts/deployments" && cp "$ROOT/contracts/deployments/"*.json "$OUT/contracts/deployments/"
for n in PolicyManager BatchAuction PoolVault OracleAdapter MockUSDC Lens; do            # names per Phase 8
  jq '.abi' "$ROOT/contracts/out/$n.sol/$n.json" > "$OUT/contracts/abi/$n.json"; done
# import check in a clean venv built from the slim deps (catches netCDF4/xarray/pyarrow leaks)
(cd "$OUT" && uv venv -q .chk && uv pip install -q --python .chk/bin/python -r pyproject.toml \
   && CHAIN_MODE=sim .chk/bin/python -c "import app" && rm -rf .chk)
du -sm "$OUT"
cd "$OUT" && npx -y vercel@latest deploy --prod --yes      # first run: link to project wi-engine
```

### Portal: rewrite + typed client (TS)
```ts
// apps/portal/next.config.ts (add to the 10-01 file)
const ENGINE_ORIGIN = process.env.ENGINE_ORIGIN ?? "http://127.0.0.1:8787";
if (process.env.VERCEL && !process.env.ENGINE_ORIGIN) throw new Error("ENGINE_ORIGIN must be the wi-engine production alias");
const nextConfig: NextConfig = {
  env: { CHAIN_MODE: process.env.CHAIN_MODE ?? "sim" },
  async rewrites() {
    return [{ source: "/api/v1/:path*", destination: `${ENGINE_ORIGIN}/api/v1/:path*` }];
  },
};
```
```ts
// apps/portal/src/lib/engine.ts
// generate: pnpm dlx openapi-typescript http://127.0.0.1:8787/api/v1/openapi.json -o src/lib/engine-schema.d.ts
import createClient from "openapi-fetch";
import type { paths } from "./engine-schema";
export const engine = createClient<paths>({ baseUrl: "" });   // same origin via rewrite
export const worldHeader = () => ({ "X-WI-World": localStorage.getItem("wi.world") ?? "demo" });
// usage: const { data, error } = await engine.POST("/api/v1/quotes", { body, headers: worldHeader() });
```

### Portal: run an Execution envelope (wagmi 2.19.5 / @wagmi/core 2.22.1; exports verified)
```ts
// apps/portal/src/lib/execute.ts
import { getAccount, sendTransaction, switchChain, waitForTransactionReceipt } from "wagmi/actions";
import type { Config } from "wagmi";
type Hex = `0x${string}`;
export type TxRequest = { chainId: number; to: Hex; data: Hex; value: string; description: string };
export type Execution<T> = { mode: "sim" | "anvil" | "testnet"; status: "done" | "needs_signature"; result?: T; txs: TxRequest[] };

export async function execute<T>(config: Config, ex: Execution<T>, confirm: (hash: Hex) => Promise<T>): Promise<T> {
  if (ex.status === "done") return ex.result as T;
  let last: Hex | undefined;
  for (const tx of ex.txs) {                                   // e.g. [MockUSDC.approve, PolicyManager.buy]
    if (getAccount(config).chainId !== tx.chainId) await switchChain(config, { chainId: tx.chainId });
    last = await sendTransaction(config, { to: tx.to, data: tx.data, value: BigInt(tx.value), chainId: tx.chainId });
    const r = await waitForTransactionReceipt(config, { hash: last, chainId: tx.chainId });
    if (r.status !== "success") throw new Error(`${tx.description} reverted`);
  }
  return confirm(last!);                                       // POST /api/v1/tx/{hash}/confirm
}
```

## Playwright smoke at the public URL

**Reuse pattern (verified today):** `createRequire('~/Mile Buy Club/package.json')` → `require('playwright')` (1.59.1). `chromium.launch()` fails because `~/Library/Caches/ms-playwright/chromium_headless_shell-1217` is missing; `chromium.launch({ channel: 'chrome' })` works (it loaded example.com, status 200). There is no repo-level Playwright config in MBC worth copying: `apps/web/playwright.marketing-render.config.ts` is a webServer-based renderer config. Owner practice is plain scripts (`scripts/dev/profile-hero.mjs`), so use a script, not `@playwright/test`.

```js
// scripts/smoke-demo.mjs   URL=https://<portal-prod-alias> ADMIN_TOKEN=... node scripts/smoke-demo.mjs
import { createRequire } from "node:module";
const require = createRequire("~/Mile Buy Club/package.json");
const { chromium } = require("playwright");
const BASE = process.env.URL ?? "http://localhost:3000";
const api = async (p, init = {}) => {
  const r = await fetch(`${BASE}/api/v1${p}`, { ...init, headers: { "content-type": "application/json", ...(init.headers ?? {}) } });
  if (!r.ok) throw new Error(`${p} -> ${r.status} ${await r.text()}`);
  return r.json();
};
// 0) warm + mode
await api("/health"); const h = await api("/health"); if (h.mode !== "sim") throw new Error(`mode ${h.mode}`);
// 1) API loop (fast fail): world -> business -> sales -> elasticity -> quote -> buy -> order -> advance/clear -> settle
const { worldId } = await api("/sim/worlds", { method: "POST", body: JSON.stringify({ template: "demo-5-cities" }) });
const W = { "X-WI-World": worldId };
// ... POST /businesses, /businesses/{id}/sales (fixture rows), /elasticity, /quotes, /policies (Idempotency-Key),
//     /auctions/{id}/orders, /sim/advance {days:3}; assert settlements[0].status === "final" and payoutE6 is an integer
// 2) UI loop with screenshots into reports/demo-smoke/
const browser = await chromium.launch({ headless: true, channel: "chrome" });
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.addInitScript((w) => localStorage.setItem("wi.world", w), worldId);
await page.goto(`${BASE}/app/onboard`);
await page.getByTestId("sales-upload-input").setInputFiles("fixtures/demo/sales-nyc-icecream.csv");
await page.getByTestId("elasticity-beta").waitFor();
await page.getByTestId("quote-total").waitFor();
await page.getByTestId("buy-button").click();
await page.getByTestId("exec-status-done").waitFor();
await page.screenshot({ path: "reports/demo-smoke/03-bought.png", fullPage: true });
// trade -> order-submit; admin -> sim-advance; claims -> settlement-row
await browser.close();
```
**`data-testid` contract to hand to Phases 10/11:** `sales-upload-input`, `elasticity-beta`, `recommend-card`, `quote-total`, `buy-button`, `exec-status-done`, `auction-row`, `order-submit`, `auction-clear`, `sim-advance`, `settlement-row`, `pool-nav`, `mode-pill`, `mode-mismatch-banner`.
**Rules:**
- Hit the production alias.
- Warm up `/health` twice before timed steps.
- Record p50/p95 latency of the API loop in the smoke output. This is the evidence for the "revisit Cloud Run" trigger.
- Run the script twice concurrently once, to prove world isolation (Pitfall 1).

## State of the Art

| Old approach | Current approach | When changed | Impact |
|---|---|---|---|
| Python on Vercel only as `/api/*.py` files | Framework presets (FastAPI zero-config, `tool.vercel.entrypoint`, pyproject + uv.lock), 500 MB bundle, Large Functions up to 5 GB (beta) | 2025–2026 (docs updated 2026) | A FastAPI engine is a first-class Vercel deploy |
| Two projects for frontend + Python backend | `services` in vercel.json (Beta) | 2026 (replaces `experimentalServices`) | Optional later consolidation |
| wagmi 2 (batteries-included connectors) | wagmi 3: connector SDKs are optional peers; `useAccount`→`useConnection`; mutate fns renamed | wagmi 3.x (latest 3.7.7) | Modal libraries lag; stay on 2.19.5 this week |
| Vercel Hobby cron limited in count | 100 cron jobs per project on every plan, but Hobby is still daily-only, ±59 min | 2025–2026 | Cron can't drive an MM loop on Hobby |
| HyperEVM 2M-gas small blocks (training knowledge) | Docs now: fast 1 s / **3M gas**, slow 1 min / 30M gas | Current docs | Slightly more room for user txs |

**Deprecated/outdated:** viem `foundry` chain (use `anvil`); wagmi `useAccount` (deprecated alias in v3); Vercel `experimentalServices` (use `services`).

## Open Questions

1. **HyperEVM testnet RPC reachability.**
   - Known: DoH resolves `rpc.hyperliquid-testnet.xyz`, but the local resolver fails and pinned-IP TLS is reset from this Mac; mainnet RPC works.
   - Unclear: whether this is an outage, a network block, or local.
   - Recommendation: re-check from a Vercel function in 09-04; keep `HYPEREVM_RPC_URL` configurable. Not on the sim-demo critical path.
2. **Multicall3 on testnet.** viem's testnet chain omits `contracts.multicall3` (mainnet has `0xcA11…CA11`), and the RPC couldn't be reached to check. Recommendation: don't depend on it; Phase 8 ships a Lens view contract.
3. **Phase 8 must add read views.** The API needs `positionsOf(owner)`, `ordersOf(auctionId)`, `auction(id)`, `poolState()`, `settlementOf(ref)`, and a Lens aggregate. Relay this to the Phase 8 planner. It also needs per-order clear gas measured against the 3M fast-block limit, to set `maxOrdersPerAuction`.
4. **Who creates cloud resources.** `upstash redis create`, the `wi-engine`/`wi-portal` Vercel projects, `vercel env add` (Upstash token, `ADMIN_TOKEN`), and an optional QStash schedule each create a credential or external resource. AGENTS.md bars workers from this, and config sets `always_confirm_external_services`. Recommendation: the seat does it with one owner OK, or pings the owner. Set a monthly budget on the PAYG Upstash DB.
5. **Money units deviate from the 10-01 stub** (`number` USDC → `…E6` ints). Recommendation: accept; record the deviation in 09-01.
6. **Sim replay window and snapshot contents.** Ladders at T−24h, CLI values and priors for which dates? The window needs 60+ finalised days before the first quoted day (Phase 7 fair value). Recommendation: 09-01 fixes it with Phase 1 manifests; keep the snapshot under about 20 MB of JSON.gz.
7. **Real Python cold start on Vercel.** Only local import times are measured. Recommendation: the 13-03 smoke records it; the Cloud Run fallback trigger is p50 above about 3 s after warm-up.
8. **Vercel plan.** The team is believed to be Hobby (MBC memory): non-commercial clause, daily cron, 300 s. Recommendation: fine for the demo; mention Pro ($20/mo) to the owner as the clean answer.
9. **House MM on testnet** needs an owner-held role key and a local loop (Phase 17). The API design leaves the slot open (`jobs.py house-mm --mode testnet`).

## Sources

### Primary (HIGH confidence)
- Vercel docs (fetched as `.md`, 2026-09-30): `/docs/cron-jobs/usage-and-pricing` (Hobby daily ±59 min; last_updated 2026-07-15), `/docs/functions/runtimes/python` (presets, 3.12/3.13/3.14, pyproject + uv.lock, 500 MB, excludeFiles, `/api` legacy), `/docs/frameworks/backend/fastapi` (entrypoints, CLI ≥ 48.1.8), `/docs/services`, `/services/routing`, `/services/config-reference`, `/services/pricing` (Beta; Hobby 1M service requests), `/docs/functions/limitations` (300 s Hobby, 2 GB, 4.5 MB body, 250/500 MB), `/docs/plans/hobby` + `/docs/limits/fair-use-guidelines` (non-commercial), `https://openapi.vercel.sh/vercel.json` (framework enum includes `fastapi`, `nextjs`; `services` key exists)
- Hyperliquid docs (`.md`): `for-developers/hyperevm` (998 / `rpc.hyperliquid-testnet.xyz/evm`), `hyperevm/dual-block-architecture` (1 s / 3M, 1 min / 30M, `evmUserModify`), `hyperevm/json-rpc` (latest-only calls, getLogs ≤ 50 blocks), `api/rate-limits-and-user-limits` (100 EVM RPC req/min), `builder-tools/hyperevm-tools` (RPC providers, faucets)
- Next.js docs `app/api-reference/file-conventions/route.md` (version 16.3.7; params Promise; segment config)
- wagmi docs: `react/guides/migrate-from-v2-to-v3.md`, `react/guides/ssr.md`, `shared/connectors/mock.md`
- Upstash docs `redis/overall/billing.md` (free 256 MB / 500K cmds / 1 DB; PAYG $0.20 per 100K, first 10 DBs free)
- Google Cloud pricing pages: Cloud Run free tier (180k vCPU-s, 360k GiB-s, 2M req), Cloud Scheduler (3 free jobs per billing account); Render `docs/free` (15-min spin-down, ~1 min wake, 750 h); Fly pricing (card required for all orgs)
- npm registry (2026-09-30): next 16.3.7, wagmi 3.7.7, viem 2.57.1, @rainbow-me/rainbowkit 2.2.11 (peer wagmi ^2.9.0), connectkit 1.9.2 (peer react 17/18), @reown/appkit 1.8.24, @upstash/redis 1.39.0, openapi-typescript 7.13.0, openapi-fetch 0.17.0, @playwright/test 1.63.0, vercel 61.1.0; PyPI: fastapi 0.142.1, upstash-redis 1.8.0, web3 8.0.0, eth-account 0.14.0, pydantic 2.13.5, numpy 2.5.3, scipy 1.18.1, uvicorn 0.54.0
- Local verification on this Mac: viem `hyperliquidEvmTestnet`/`anvil` definitions; web3.py 8 + viem send on anvil 1.8.3; web3 `Contract.encode_abi` signature; upstash-redis `set(nx,px)`/`eval`; anvil key → address mapping; package sizes (project venv 535 MB; slim set 160 MB); import timings; MBC Playwright needs `channel: 'chrome'`; CLI login states (vercel, gcloud, render 401, upstash PAYG, no flyctl); wagmi 2.19.5 / @wagmi/core 2.22.1 action exports in the portal
- Repo: `.planning/phases/10-portal-core/10-01-REPORT.md`, `apps/portal/src/lib/{api,chain-mode,chains}.ts`, `apps/portal/next.config.ts`, `contracts/README.md`, `contracts/foundry.toml`, `.planning/phases/07-protocol-spec-engine/07-RESEARCH.md`, `05-elasticity-learning/05-RESEARCH.md`, `12-pos-connect/12-RESEARCH.md`; mainbrain `server/redis.ts`, `api/*.ts`, `api/tsconfig.json`, `vercel.json` (read-only)

### Secondary (MEDIUM confidence)
- QStash free tier 1,000 messages/day, 10 active schedules (upstash.com pricing page HTML, scraped)
- Next.js external rewrites forwarding custom headers (`X-WI-World`) (established behaviour; verify in 13-01)
- `wi/` importable from the Vercel function root when copied beside `app.py` (cwd = project root per the Python runtime docs; verify on first deploy)

### Tertiary (LOW confidence)
- Cloud Run request size limit (training knowledge)
- Per-order gas for an on-chain uniform-price clear (estimate only; Phase 8 measures)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH. Versions come from npm/PyPI today; key APIs were exercised locally.
- Hosting decision: HIGH on the facts (limits, logins, sizes); MEDIUM on Python cold start in practice (unmeasured on Vercel).
- Architecture (envelope, worlds, key split): MEDIUM-HIGH. It follows the Phase 7 reducer design and HyperEVM docs; untested end to end.
- HyperEVM testnet specifics: MEDIUM. Docs are clear, but the testnet RPC could not be reached from here.
- Pitfalls: HIGH. Most are observed today or were paid for in MBC or mainbrain.

**Research date:** 2026-09-30
**Valid until:** 2026-10-07. Fast-moving: Vercel Services Beta, wagmi 3 ecosystem, testnet RPC status.
