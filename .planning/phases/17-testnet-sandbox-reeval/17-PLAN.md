---
phase: 17-testnet-sandbox-reeval
plan: 01-03
type: execute
depends_on: ["08","12","13", "owner: deploy + Square token"]
---
<objective>Owner-hand tail: (17-01) after the owner runs contracts/RUNBOOK.md, verify deployments/998.json, run smoke-testnet read-only, flip the engine and portal to testnet, record addresses in PROJECT.md; (17-02) after `export SQUARE_SANDBOX_ACCESS_TOKEN` lands, run 12-02 (seed sandbox, A5–A6), add the token to Vercel env; (17-03) once the hl-mm recorder has ≥ 14 days of books, re-run Phase 2 depth/cost tables on real books, refresh EVALUATION.md §9, and write the pilot-prep + mainnet-readiness checklist from the legal memo's gates.</objective>
<context>@contracts/RUNBOOK.md @.planning/phases/12-pos-connect/12-RESEARCH.md (12-02 steps, A5–A6) @reports/pitch/15-LEGAL-OPTIONS-MEMO.md (gates) @.planning/PROJECT.md</context>
<tasks>
<task type="checkpoint:human-action" gate="blocking"><what>Owner runs the testnet deploy and pastes the Square sandbox token (with `export`).</what><resume-signal>"deployed" / "square token in"</resume-signal></task>
<task type="auto"><name>17-01 testnet flip</name><files>.env, PROJECT.md, deployments/998.json</files><action>Per objective.</action><verify>portal at the alias shows testnet mode; a wallet buy returns needs_signature.</verify><done>Testnet.</done></task>
<task type="auto"><name>17-02 sandbox</name><action>Per objective.</action><verify>A5–A6 pass.</verify><done>Sandbox.</done></task>
<task type="auto"><name>17-03 re-evaluation + checklist</name><action>Per objective.</action><verify>EVALUATION.md §9 updated with real-book depth; checklist file exists.</verify><done>Tail.</done></task>
</tasks>
