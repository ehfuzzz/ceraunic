---
phase: 11-trading-dashboards
plan: 01-03 (single worker run)
status: complete for sim; staking panel is a stub (no engine routes)
---
# 11 Summary: trade, pool, admin pages

## What shipped (apps/portal, all new files except the three page.tsx stubs replaced)
- Trade (`/app/trade`): 15 auctions listed with day, cutoff, status, house bid/ask and aggregated book; status filter; per-auction book, order form (buy/sell, units, limit in cents with live basis and collateral readout), open orders with cancel, clear button (permissionless after cutoff, admin override in sim when a token is set), clearing result with a conservation check recomputed in the browser (long + short locked must equal filled units x $1). Every price shows the cents tick and the signed basis in degrees F. Collapsible explainer of uniform-price clearing.
- Pool (`/app/pool`): senior/junior assets, shares, value per share, senior rate; utilisation bar; SVG NAV-per-share chart; exposure by contract; deposit and withdraw forms; queue table with your tickets shaded; plain-words "junior loses first" text; WI staking panel.
- Admin (`/app/admin`): token typed once, kept in sessionStorage (`wi.admin.token`); sim clock with advance 1-10 days and "new private world"; house-MM quotes, inventory, paper Kalshi hedges per rung, P&L, caps used, "run a tick"; oracle table and report form; engine/portal mode-mismatch banner (also on trade and pool).
- Support: `lib/trading-{format,store,api,queries}.ts`, components `Trade*`, `Pool*`, `Admin*`, `TradingKit`. No shared files edited (api.ts, layout, globals, package.json untouched); cancel/clear/admin/clock calls live in `lib/trading-api.ts` on the same client and Execution envelope.

## Verification (fixture API :8788, portal :3011, both stopped by PID)
- `pnpm exec tsc --noEmit`: clean at the end (it failed twice mid-run on Phase 10's in-progress files, then cleared). `pnpm lint`: clean.
- `pnpm build` (under .build-lock): first two attempts failed on Phase 10 files (`core/CoverageFlow.tsx` missing `./BuyPanel`, `./QuoteCompare`); third passed, all routes prerendered. Build prints Turbopack tracing warnings from `lib/sales/square/fixture-files.ts` (Phase 12, not mine).
- End-to-end Playwright-driven run (script in the session scratchpad, not committed; Chrome channel, dev server then `next start`): new sim world, faucet, place buy, cancel, place buy and sell, admin token, tick (10 quotes), early admin clear (price 46c, 5 units, long $2.30 + short $2.70 = $5.00, conservation matches), advance 1 day, oracle report (tmax:KNYC 2025-07-14 95.4 F), pool deposit queued, closed-auction filter. Screenshots: `reports/portal/{trade-list,trade-detail,trade-cleared,admin-top,admin-full,pool}.png` (from the final `next start` run).
- No Playwright spec added: Phase 10 had not created `tests/smoke.spec.ts` / `playwright.config.ts` by the end. No unit tests (none guard a silent-corruption path the e2e run does not).

## Deviations and notes
- WI staking: the API has no staking routes and `contracts/src` has no WIStaking, so the panel states the rules (30% per-event cap, cooldown still cuttable, stakers earn nothing in v0) with stake/cooldown disabled and an honest empty history. Needs an API route before it can be real.
- Signed basis price is computed in the portal (-R + 2R*p, R = `rangeTenthsF`/10) because the API has no basis-view field; 07-CONTEXT says the engine should expose it. `capsUsed` is shown as a fraction of cap x100 (fixtures return 0.0; scale unconfirmed). `docs/SPEC.md` does not exist; used 07-CONTEXT.
- Trader address: connected wallet first; in sim with no wallet the visitor picks or generates an address (localStorage `wi.trade.address`). Phase 10 may want to unify this.
- Next dev blocks 127.0.0.1 origins (HMR), so browser runs used `localhost:3011`. `next dev` generated agent-rules files; deleted. Fixture clear in a cross case priced a sell at 46c above the seller's 25c ask (seller gets the clearing price by design; buyer limit 40 did not fill).
- Flagged: `next dev` and Phase 10's server share `.next/`; I stopped mine before building.
