---
phase: 07-protocol-spec-engine
plan: 02-06 (single worker run)
type: execute
depends_on: ["07-01"]
files_modified: [src/wi/engine/*, scripts/engine_fixture_run.py, tests/engine/*, contracts/test/fixtures/*.json, reports/engine/fixture-run/*]
---
<objective>The reference engine per docs/SPEC.md: pure integer event reducer with hash-chained log and snapshots; pricing/risk + margin; auction (import src/wi/auction/clear.py from Phase 4 if present and identical to SPEC, else implement and note); pool ledgers + waterfall + epochs + WI staking haircut; oracle adapter (fixed vintage, revision windows, void); Kalshi paper-hedging (ins1 rule at recorded books/candles with fees); house-MM quoting; RFQ; end-to-end fixture run producing a manifest; parity vectors for Foundry.</objective>
<context>@docs/SPEC.md (the law) @.planning/phases/07-protocol-spec-engine/07-CONTEXT.md @.planning/phases/07-protocol-spec-engine/07-RESEARCH.md (Patterns 8, 9, 11; Pitfalls 1, 10, 17) @src/wi/engine/units.py @src/wi/eval/ladder.py + fees.py if Phase 2 wrote them (reuse) @reports/eval-04-05/handoff.json if present (caps) @reports/eval-03/residual-spec.md if present (index registry) @AGENTS.md
Rule: no pandas/xarray/netCDF4/pyarrow/matplotlib imports at module level under src/wi/engine.</context>
<tasks>
<task type="auto"><name>Task 1: reducer core + events + invariants</name><files>src/wi/engine/{events.py,state.py,reducer.py,log.py,invariants.py}</files>
<action>Event catalogue from SPEC §13 as frozen dataclasses (ints only); State with canonical JSON + sha256; apply() asserting SPEC invariants I1..In after every event; JSONL log with prev-hash chain; snapshot/replay (snapshot k + tail = full replay hash).</action>
<verify>replay property on a random event stream (seeded) gives equal hashes.</verify><done>Core.</done></task>
<task type="auto"><name>Task 2: markets, auction, policies, hedge, oracle</name><files>src/wi/engine/{markets.py,auction.py,policy.py,hedge.py,oracle.py,pricing.py,margin.py}</files>
<action>Scalar-unit markets + payout mapping; auction placement/escrow/clear/claim per SPEC §5 (identical rule to Phase 4's function — assert parity on 4,000 random books); policies with signed quotes, δ, residual-leg order, downsizing; paper Kalshi replication + fills + fees (books then candles); oracle reports/finalize/void per source W; pricing (fair, half-spread, caps → house schedule) and margin caps.</action>
<verify>SPEC worked examples reproduce exactly (auction 6-order example; heat call K=88; residual ±5).</verify><done>Mechanics.</done></task>
<task type="auto"><name>Task 3: pool + staking + house MM + RFQ + fixture run + parity vectors</name><files>src/wi/engine/{pool.py,staking.py,house_mm.py,rfq.py}, scripts/engine_fixture_run.py, contracts/test/fixtures/{auction_cases,payoff_cases,waterfall_cases,oracle_cases}.json, reports/engine/fixture-run/MANIFEST.json</files>
<action>Pool ledgers/waterfall/caps/epoch queue; WI staking haircut; house-MM tick (idempotent per tick key); RFQ flow; the 30-day one-metro fixture run (SPEC §14 timeline, NYC + LGA residual, two businesses with opposite exposure, house seeding, one heat wave, one void) writing MANIFEST.json (inputs sha256, params hash, event counts, final hash, snapshot hashes, invariant results, per-day P&L CSV) and the four parity vector files. Tests: only money-failure modes (conservation under random clears, waterfall never pays junior before senior loss is exhausted... per AGENTS.md), and the replay property.</action>
<verify>`uv run python scripts/engine_fixture_run.py` writes MANIFEST.json; `uv run pytest tests/engine -q` passes.</verify><done>Engine complete.</done></task>
</tasks>
<output>`.planning/phases/07-protocol-spec-engine/07-SUMMARY.md` (≤ 60 lines) incl. any SPEC ambiguities you resolved (list them so 08/09 can follow).</output>
