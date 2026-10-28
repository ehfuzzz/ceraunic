# 12-01 SUMMARY: POS connect on fixtures (PORT-03)

Status: done, uncommitted (workers never commit). Everything runs on fixtures; no Square account, token or network call was used.

## Acceptance (pre-registered in 12-RESEARCH.md, run with `pnpm pos:accept`)
- A1 fixture exactness: PASS. 1,200 rows, 0 cents / 0 order / 0 category differences vs truth-daily.csv, duplicates 0.
- A2 CSV parity: PASS. csv-export.csv panel byte-identical to the Square panel (11 closed days zero-filled from omitted CSV rows).
- A3 offline: PASS. Whole pull ran with globalThis.fetch replaced by a throwing stub, 0 calls; mode "fixture", host "fixture".
- A4 exclusions: PASS. returns 461/461, gift-card lines 315/315, custom-amount lines 3,356/3,356, OPEN/CANCELED seen by adapter 0 (1,062 + 500 planted, removed by the fixture's state filter).
- Fixture pull time (informational): 5.6 to 5.9 s for 107k orders, 109 pages (target 15 s).
- Checks are not vacuous: bucketing by UTC date fails A1 (1,196 mismatches); not skipping gift-card lines fails A1 and A2. Both reverted.
- Quirks exercised in the run: one planted 429 (SDK retried) and one short page before the end.

## Built
- src/lib/sales/{types,dates,validate,serialize,csv-source}.ts and square/{source,aggregate,fixture-fetch,fixture-files,generate}.ts (interface verbatim from research).
- scripts/gen-square-fixtures.ts (`pnpm gen:fixtures`), scripts/pos-accept.ts (`pnpm pos:accept`); root package.json forwards both.
- fixtures/square/: params, locations, catalog, sample-orders, truth-daily (1,200 rows), csv-export (1,189 rows), station-tmax (1,200 rows), MANIFEST. Two generator runs give identical hashes for every file.
- Route `src/app/api/pos/square/route.ts` (nodejs): POST {locationIds,start,end,includeCategories} returns SalesPanel; mode resolved from env and echoed. Added GET (locations + mode) for the card. A present token that fails is a 502, never a fallback; the token is redacted from errors.
- Onboard: `ConnectSquareCard` (mode badge, locations, 30-day preview table, design tokens).
- Deps: square@46.0.0 (exact), tsx (dev).

## Deviations / notes
- Weather: official_daily.parquet covers 2025-08-27..2026-09-29 for NYC/MDW/MIA; 4 of 1,200 rows (2026-09-30 x3, MIA 2026-04-11 null) carry the previous day, flagged `src=carried_forward` in station-tmax.csv and in MANIFEST.tmax_source.
- csv-source.ts was written here (Phase 10-02 had not landed). CSV location ids are matched by local key (prefix "square:"/"csv:" stripped); parity compares on that key. 10-02 should adopt or amend.
- Order count floor of 8 per open day so the planted edge-time / DST-hour orders always exist.
- Vercel: fixtures are read with fs at runtime; the hosted demo (Phase 13) needs `outputFileTracingIncludes` for apps/portal/fixtures/square in next.config.ts (not touched here).
- `next dev` smoke test auto-generated agent-rules files; I deleted them. Expect it again on any dev run.
- Not done (12-02): sandbox seeding, recorded pages, A5/A6.
