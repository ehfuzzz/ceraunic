---
phase: 11-trading-dashboards
plan: 01-03 (single worker run)
type: execute
depends_on: ["09-01","10-01"]
files_modified: [apps/portal/src/app/app/{trade,pool,admin}/**, apps/portal/src/components/**]
---
<objective>PORT-02: Trade — list residual auctions (contract, day, cutoff, house quote, aggregated book), place/cancel orders from any connected wallet (Execution envelope), clear (permissionless after cutoff; admin override in sim), clearing result with conservation check; Pool — tranches, NAV history, utilisation, exposure by contract, deposit/withdraw requests + queue, WI staking panel (stake, cooldown, haircut history); Admin/house-MM — quotes, inventory, Kalshi paper hedges per rung, P&L, caps used, oracle rows + report button (sim/anvil), "advance day" control (sim), engine/portal mode mismatch banner.</objective>
<context>@apps/portal (scaffold + 10 work in progress: coordinate by owning only the trade/, pool/, admin/ routes and new components; do not edit files under onboard/, coverage/, policies/) @apps/portal/src/lib/{api.ts,engine-schema.d.ts,execute.ts} @.planning/phases/09-engine-api-chain-modes/09-RESEARCH.md (API contract) @docs/SPEC.md §5, §8 @AGENTS.md. Run the fixture API locally while building; stop it after.</context>
<tasks>
<task type="auto"><name>Task 1: Trade</name><files>apps/portal/src/app/app/trade/**</files><action>Per objective; prices shown as the business-facing signed basis price AND the scalar tick; a small explainer of uniform-price clearing.</action><verify>place/clear against fixtures; build+lint pass.</verify><done>Trade.</done></task>
<task type="auto"><name>Task 2: Pool + staking</name><files>apps/portal/src/app/app/pool/**</files><action>Per objective; plain-words explanation of who loses first.</action><verify>build+lint.</verify><done>Pool.</done></task>
<task type="auto"><name>Task 3: Admin</name><files>apps/portal/src/app/app/admin/**</files><action>Per objective; admin token entered once and kept in sessionStorage (never in code).</action><verify>advance-day + tick against fixtures; build+lint; add the three pages to the Playwright smoke if 10 has created it (append a spec file, do not edit theirs).</verify><done>Admin.</done></task>
</tasks>
<output>`.planning/phases/11-trading-dashboards/11-SUMMARY.md` (≤ 40 lines) with screenshots under reports/portal/.</output>
