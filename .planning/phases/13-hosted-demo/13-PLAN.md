---
phase: 13-hosted-demo
plan: 01-03 (single worker run)
type: execute
depends_on: ["09-LEDGER","10","11"]
files_modified: [apps/portal/*, scripts/{deploy-portal.sh,seed-demo.py,smoke-demo.mjs}, reports/demo/*]
---
<objective>PORT-04: portal deployed to Vercel (`wi-portal`, production alias) in sim mode pointing at the `wi-engine` alias; the pinned `demo` world seeded (three businesses with opposite exposures: the Phase 12 fixture merchants, a junior seed, a house MM schedule, one advanced day with a cleared auction and one settlement); a five-minute demo script the owner can follow; a Playwright smoke at the public URL proving upload → recommend → buy → auction → settle; screenshots.</objective>
<context>@.planning/phases/09-engine-api-chain-modes/09-SUMMARY.md (engine alias) @.planning/phases/09-engine-api-chain-modes/09-RESEARCH.md Pattern 1 (two GA projects, rewrite to the production alias, never a per-deployment URL) @apps/portal @scripts/deploy-engine.sh (mirror its git-less deploy) @AGENTS.md. Vercel CLI logged in as ehfuzzz. Never echo env values.</context>
<tasks>
<task type="auto"><name>Task 1: deploy portal</name><files>scripts/deploy-portal.sh, apps/portal/next.config.ts</files><action>Create/select project `wi-portal` (framework nextjs), set ENGINE_ORIGIN + CHAIN_MODE=sim env, deploy --prod, print alias.</action><verify>curl alias → 200; /api/v1/health proxied → mode sim.</verify><done>Live.</done></task>
<task type="auto"><name>Task 2: seed demo world + script</name><files>scripts/seed-demo.py, reports/demo/DEMO-SCRIPT.md</files><action>Seed via the admin routes; DEMO-SCRIPT.md: 5 minutes, what to click, what to say (plain words, no "insurance"), what each number means, what is simulated.</action><verify>demo world state matches the script's numbers.</verify><done>Seeded.</done></task>
<task type="auto"><name>Task 3: smoke + screenshots + notify</name><files>scripts/smoke-demo.mjs, reports/demo/screenshots/*</files><action>Playwright (channel chrome) at the public alias through the whole loop; save screenshots; write reports/demo/SMOKE.md with timings.</action><verify>smoke passes at the alias.</verify><done>Proof.</done></task>
</tasks>
<output>`.planning/phases/13-hosted-demo/13-SUMMARY.md` (≤ 40 lines) with both aliases — the seat sends the owner the push notification.</output>
