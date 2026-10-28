# @wi/portal

The weather-insurance web app. Next.js 16 (App Router), Tailwind v4, wagmi v2 + viem, injected wallet only (MetaMask, Rabby).

## Run

From the repo root:

```
pnpm install
pnpm portal:dev      # http://localhost:3000
pnpm portal:build
pnpm --filter @wi/portal lint
```

Node 22 and pnpm 10.

## Env vars

| Name | Values | Default | What it does |
|------|--------|---------|--------------|
| `CHAIN_MODE` | `sim`, `anvil`, `testnet` | `sim` | Which chain the app talks to. Read only in `src/lib/chain-mode.ts`; shown as the pill in the header. `sim` needs no wallet. `anvil` is `127.0.0.1:8545` (chain 31337). `testnet` is HyperEVM testnet (chain 998). |
| `NEXT_PUBLIC_RPC_URL` | URL | unset | Optional RPC override for the active chain (`anvil` or `testnet`). |

Example: `CHAIN_MODE=anvil pnpm portal:dev`. `CHAIN_MODE` is inlined at build time (see `next.config.ts`), so set it before `portal:build` too.

## Layout

- `src/lib/chain-mode.ts`: the `CHAIN_MODE` switch.
- `src/lib/chains.ts`: chain definitions and the wagmi config. HyperEVM testnet comes from `viem/chains` (`hyperliquidEvmTestnet`). Values to re-check in Phase 8 research are marked `verify`.
- `src/lib/api.ts`: typed engine-API client. Phase 9 replaces the function bodies and keeps the names and types.
- `src/components/`: header, connect button, chain pill, side nav, placeholder page.
- `src/app/globals.css`: all design tokens, light and dark by `prefers-color-scheme`.

## Stubbed

- Every function in `src/lib/api.ts` returns a placeholder (`placeholder: true`); nothing calls an engine.
- `/app/onboard`, `coverage`, `trade`, `pool`, `admin` are one-line placeholder pages.
- Wallet connect works with an injected wallet, but no transaction is sent anywhere.
- No WalletConnect (no project id by design).

## Note for agents working in this app
Next 16 differs from older training data (APIs, conventions, file structure). Before writing code here, read the relevant guide under `apps/portal/node_modules/next/dist/docs/` and heed deprecation notices. (create-next-app's own AGENTS.md said this; it was removed so it does not shadow the repo's root AGENTS.md.)
