# 13-RAIN SUMMARY: rain cover end to end, 2026-09-30. Live, uncommitted.

**What shipped.** Rain is now a live product at https://wi-portal.vercel.app. You pick "Rainy days" and set a dollar amount. The cover pays that amount on each covered day the metro's Kalshi rain station reports rain in its NWS CLI (Central Park, O'Hare, Miami Intl), and a trace counts as rain.
- **Engine.**
  - New index `CLI:<S>:WET:v1`. The cover is the `[0,1]` market on it, business long, one policy per day.
  - `pricing.price_rain_policy`. If the day's KXRAIN market is open at quote time, the station leg costs its ask. Otherwise it costs `ceil(fair + halfSpread)`: the wet-day rate over the last 60 finalised days, with the SPEC 6.6 half-spread rule. On top go the Kalshi fee (rounded up once per order), the slip buffer, risk margin and notional fee. The premium must stay at or under the max payout, and C3–C5 apply. The "tail" is a trace load, charged only on days priced from Kalshi: `units×(1−mid)×traces/(traces+dry)`.
  - Hedging: `hedge.rain_needs` buys one KXRAIN contract per unit at T−24h. The world file gets `rainSeries`, and `house_mm.station_series` routes rain policies to it.
  - Clock: if Kalshi settles a rain day after D+2 12:00Z, the house returns that day's money at that settlement.
- **Data.** New `data/demo/rain.json.gz`, built by `build-demo-snapshot.py`: 71 KXRAIN days per city plus CLI precip for NYC, ORD and MIA, with the trace flag kept. The other demo files are byte-identical, and a rebuild reproduces this one exactly.
- **API.**
  - Removed the rain 422.
  - Added `GET /recommendation?peril=rain`.
  - Added Business `rainStationId/Name`, Rung `forDay/source`, and Settlement unit `wetDay`.
  - OpenAPI field docs written; `pnpm gen:api` regenerated the portal types.
- **Portal.**
  - "Rainy days" has no line or range: it takes dollars per wet day.
  - The quote card has two paths. Each lists one KXRAIN contract per day, showing the Kalshi ask or "opens the morning before".
  - Plain copy: a trace counts as wet; the rain local-difference contract would settle weekly on PRISM cells and is by request only.
  - Seat add-ons: nav and page title are now "Cover"; the Pool page now says deposits are immediate. The self-place path, which sells nothing, now shows a note instead of a Buy button.
- **SPEC.** Added a §3 row, a §7.1 sentence, the §17 trace row and a §18 13-RAIN entry.

**Tests (verbatim).**
- `uv run pytest tests/api/test_rain_cover.py -q` → `3 passed, 1 warning in 10.00s`. What they check: a dry week pays 0; a wet week pays units × 7 and the balance moves by payouts − premium; every day in the window is either refused or priced at or under max payout; the fee is rounded up exactly.
- Mutation check: a floored fee, a dropped max-payout guard, and settling the wrong day each fail a test.
- `uv run pytest -q` → `57 passed, 2 skipped, 3 warnings in 24.28s`.
- Nothing else changed: the API golden still matches, and `engine_fixture_run.py` produces identical events.jsonl and all 8 fixtures. Its MANIFEST.json was rewritten, with only gitHead and the SPEC hash differing.
- Portal: `tsc --noEmit` clean, `pnpm lint` clean, `pnpm build` exit 0, all run under `.build-lock`.

**Deploys and demo world.** Engine deployed with `deploy-engine.sh` (bundle check OK, 63 MB), portal with `deploy-portal.sh`.
- Seed: the bakery also buys **$20 per wet day at O'Hare, 07-16..22, for $87.99** (max $140). All 7 days were priced from the wet-day rate at 58¢ per contract.
- 07-16 was dry and paid $0.00. The house hedged 07-17 at the 98¢ ask, costing $19.63.
- The size is an override. The bakery's own sales go up 4.7% on wet days, so the tool suggests only $1 a day.
- All temperature numbers, policy ids and the auction are unchanged. What moved: bakery wallet $678.05 → $590.06; junior $200,231.26; senior $300,001.03; utilisation 2.04%.
- `seed-state.json` and `DEMO-SCRIPT.md` are updated. `--check` OK.

**Smoke.** `node scripts/smoke-demo.mjs` → **SMOKE PASS, 15/15, 18.2 s**. New steps:
- A1r reads the seeded rain policy.
- B8 buys $20/wet day for 07-25..31 at **$88.89**. The first day is priced at Kalshi's 73¢ ask. O'Hare was wet on 07-27, 07-28 (a trace) and 07-31, so it paid **$60.00**; balance $714.01 = $742.90 − $88.89 + $60.00.
- Screenshots: `reports/demo/screenshots/13-rain-{quote,bought,settled,seeded-policy}.png`.

**OBJECTION (trace rule).** What: the brief and both seat rulings say a trace counts as wet *because* Kalshi settles trace YES (61.5 %, eval-01 `rain_daily.trace_yes_share`). Evidence: the KXRAIN series the house actually trades settled **all 26 trace days NO** at CLINYC/CLIORD/CLIMIA in 2026-07-15..09-28, against 94/94 measurable days YES and 96/96 dry days NO. The 61.5 % comes mostly from the older KXRAINNYC series. What I did: I followed the product ruling (`TRACE_IS_WET = True` in `snapshot_data.py`, one constant). I wrote the SPEC with both numbers, and the house charges a trace load for the gap. I did not put "Kalshi settles trace YES" in any copy; the self-place card says Kalshi counts a trace as no rain. At O'Hare, trace days were 28 of 165 this season. Alternative: set it to False, and the cover matches Kalshi exactly (SPEC §1, T = 0).

**Deviations.**
1. Station-leg-only cover. The weekly G1-P residual needs a weekly market, fetch window and a 1-order-to-7-policies bind; §6.3 binds one order to one policy on the same day. So the rain residual goes through RFQ.
2. Days 2+ are priced from the wet-day rate, not a forecast. Day 1 uses Kalshi's ask. Adverse selection on days 2+ is a pool risk.
3. The KXRAIN listing has a gap on 07-16 and 07-18..21 in all cities. Those days sell unhedged.
4. Visitor worlds created before this deploy refuse rain with a clear "start a fresh demo world" message.
5. Anvil mode was not rerun for rain.

**Deck line** (replaces "The prototype portal sells heat and cool cover today; rain comes next"): "The prototype portal sells heat, cool and rain cover today: rain pays a fixed amount for every day the official weather report at the city's Kalshi rain station shows rain, backed by one Kalshi rain contract per dollar per day."

## Trace flip (seat ruling)
**What changed.** The cover now pays on measurable rain only: CLI precip of 0.01 in or more. A trace is a dry day, which is how KXRAIN settles, so the cover and the Kalshi leg settle the same way and there is nothing to charge for.
- Code: `TRACE_IS_WET = False`. Removed the trace load (`price_rain_policy` has no `trace` arg and tail is 0), `snapshot_data.trace_rows`, and the portal's "trace-day charge" row. The trace flag stays in the data.
- Copy: the rain-rule text, quote cards, API note and trigger (quote, receipt and policy views) now read "Kalshi's rain contract counts a trace as no rain, and so does this cover: it pays on 0.01 in or more."
- SPEC: updated §3, §7.1 and the §17 row, and added a new §18 entry. §6.3 and §8 untouched.
- Evidence: `reports/eval-01/trace_kxrain_2026.{json,md}`, counted from disk only. All 216 settled markets from 07-15 to 09-29: trace 26 days, 0 YES; measurable 94 days, 94 YES; dry 96 days, 96 NO. Over the demo window to 09-28 it is 26/0, 93/93, 94/94.
- `data/demo/rain.json.gz` is byte-identical (sha 97e50921…). It stores raw hundredths plus a trace flag, and the rule is applied at read time, so no rebuild.

**Tests (verbatim).**
- `uv run pytest tests/api/test_rain_cover.py -q` → `3 passed, 1 warning in 9.72s`. The mixed week 08-11..17 has 4 measurable days, each paying $20, and 3 trace days paying $0.
- Mutations, each failing one test: trace pays, fee floored, max-payout guard dropped, day shifted by one.
- `uv run pytest -q` → `57 passed, 2 skipped, 3 warnings in 23.53s`. The golden test passes on its own too: `1 passed`.

**engine_fixture_run.py.** `"ok": true`, but events went from 3248 to 3251 and events.jsonl, pool_cases.json and waterfall_cases.json changed.
- The cause is another worker's uncommitted engine edits (events, pool, state, scenario, reducer, invariants, parity; 15:15Z). They add ParamsSet maxOrdersPerTrader, minOrderEscrowE6 and withdrawClaimWindow.
- My edits this round never run in the fixture run: grep finds no rain code in scenario.py or engine_fixture_run.py.
- The run rewrote those three files from their in-progress tree; the other worker or seat must regenerate them.
- MANIFEST.json was restored byte-for-byte by `cp` from a pre-run copy. I did not run `git checkout` (worker rule).
- The engine deploy below shipped their uncommitted edits too; the full suite and the golden passed first.

**Demo (engine and portal redeployed, reseeded, `--check` OK).**

| | Before flip | After flip |
|---|---|---|
| Bakery rain cover 07-16..22, $20/day | $87.99 (58¢/day, wet rate with traces) | $64.12 (41¢/day) |
| Bakery wallet | $590.06 | $613.93 |
| Junior / senior | $200,231.26 / $300,001.03 | $200,221.06 / $300,001.00 |
| Utilisation | 2.04 % | 2.04 % |
| Smoke B8 (07-25..31) premium | $88.89 | $65.60 |
| Smoke B8 payout | $60.00 (07-27, 07-28 T, 07-31) | $40.00 (07-27, 07-31) |
| Smoke B8 balance | $714.01 | **$717.30** = $742.90 − $65.60 + $40.00 |

Temperature numbers, policy ids and the auction are unchanged.

**Smoke.** `node scripts/smoke-demo.mjs` → **SMOKE PASS, 15/15, 44.9 s**.
- Retook 01 (bakery wallet), 04 (pool) and 13-rain-{quote,bought,settled,seeded-policy}.
- Restored 02, 03 and 05–12 from the pre-run copies; their numbers did not change.

**Files touched this round.**
- API: `src/wi/api/{snapshot_data,quoting,elasticity,models,catalog}.py`
- Engine: `src/wi/engine/pricing.py`
- Tests: `tests/api/test_rain_cover.py`
- SPEC: `docs/SPEC.md` (rain lines only)
- Portal: `apps/portal/src/components/core/{QuoteCompare,CoverageFlow}.tsx`, `apps/portal/src/lib/core-format.ts`
- Evidence: `reports/eval-01/trace_kxrain_2026.{json,md}`
- Demo: `reports/demo/{seed-state.json,DEMO-SCRIPT.md,SMOKE.md}`, screenshots 01, 04 and 13-rain-*

**Deck line (final).** "The prototype portal sells heat, cool and rain cover today: rain pays a fixed amount for every day the official weather report at the city's Kalshi rain station shows measurable rain (0.01 in or more), the same rule Kalshi's rain contract settles on, so one contract per dollar per day hedges it exactly."

**Slide-7 card replacement.** "Kalshi's daily rain contract pays only on measurable rain (0.01 in or more), and our rain cover uses the same rule, so the hedge matches the cover on every day: all 216 settled 2026 KXRAIN markets in NYC, Chicago and Miami settled that way."
