---
phase: 16-decks
plan: 01-03 (single worker run)
type: execute
depends_on: ["06","13","14","15"]
files_modified: [reports/pitch/{DECK-crypto.md,DECK-fintech.md,NARRATIVE.md,DEMO-WALKTHROUGH.md}]
---
<objective>PITCH-03 content: narrative + slide-by-slide outlines (title, one message, the evidence line with its source key, visual to use) for two decks — crypto-native (token story leads: pool-capital token, on-chain venue, Hyperliquid ecosystem, evidence as proof of demand) and fintech/insurtech (product story leads: parametric weather cover for small businesses, the evaluation numbers, the legal route, token secondary) — plus a demo walkthrough. The seat renders the decks from these outlines with the Slides artifact type.</objective>
<context>@reports/EVALUATION.md @reports/pitch/14-TOKEN-POOL-MEMO.md @reports/pitch/15-LEGAL-OPTIONS-MEMO.md @reports/demo/DEMO-SCRIPT.md + screenshots @.planning/PROJECT.md @.planning/OWNER-RULINGS.md (the ask: pre-seed $500k–$1.5M) (READ FULLY; both decks are in the owner's voice; honest about unproven claims; banned vocabulary) @AGENTS.md
Rules: no "45 pools"-style inflation, no invented traction, every number carries its source key; the legal fork is on a slide in both decks; Kalshi named only as the hedge venue (note the data-terms question).</context>
<tasks>
<task type="auto"><name>Task 1: NARRATIVE.md</name><files>reports/pitch/NARRATIVE.md</files><action>The one-page story for each audience; what we proved, what we did not, what the money buys.</action><verify>banned-word grep clean.</verify><done>Story.</done></task>
<task type="auto"><name>Task 2: two outlines</name><files>reports/pitch/DECK-crypto.md, reports/pitch/DECK-fintech.md</files><action>12–15 slides each in the outline format above; shared evidence slides reused verbatim.</action><verify>every evidence line has a source key.</verify><done>Outlines.</done></task>
<task type="auto"><name>Task 3: walkthrough</name><files>reports/pitch/DEMO-WALKTHROUGH.md</files><action>Presenter notes for the live demo synced to the deck.</action><verify>matches DEMO-SCRIPT.md numbers.</verify><done>Done.</done></task>
</tasks>
<output>`.planning/phases/16-decks/16-SUMMARY.md` (≤ 30 lines).</output>
