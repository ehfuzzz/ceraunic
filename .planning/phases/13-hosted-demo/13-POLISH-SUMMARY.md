# 13 POLISH SUMMARY: hosted demo polish, 2026-09-30. Done, uncommitted.

**1. Engine: the tail charge now depends on the strike** (SPEC §18 entry "tail charge made strike-dependent", 2026-09-30; one-line pointers added in §6.6 and §7.3).
- `src/wi/engine/pricing.py`: new `tail_charge`, `tail_spreads`, `station_basis_windows`, plus a `tail_windows=` kwarg on `price_policy`. The rule applies only when the whole range lies beyond the end rung's v (put `hi ≤ v_bot`, call `lo ≥ v_top`): `tail = max(units·TICK, min(v0 charge, units·p_end·mean_i u(y_i)))`, with `y_i` = each basis value's distance from its own 60-day finalised window mean. A policy with a basis market uses its own window. A policy AT the settlement station (NYC) pools every PAIR window on that station (LGA/JFK/EWR/TTN). Other policies keep the v0 formula.
- `src/wi/api/quoting.py`: passes the station windows when there is no basis market.
- `tests/api/test_tail_charge.py`: NYC cool put on the 07-16 heat-wave ladder (bottom rung "<89 °F"), lines 88→70 °F. Asserts: premiums never rise as the line moves away; the tail falls strictly until it hits the floor; floor ≤ tail ≤ v0 charge; 75 °F is at the floor. Mutation check: the v0 flat charge, a removed floor and a charge above the v0 cap each fail it.
- `uv run pytest tests/engine tests/api -q` → `34 passed, 2 skipped, 3 warnings in 8.89s`. Full `uv run pytest -q` → `49 passed, 2 skipped`.
- The API golden `tests/api/golden/scenario_nyc_3d.json` was regenerated (`WI_WRITE_GOLDEN=1`). One entry changed: `recommendation B.maxDailyPremiumE6` 1627787 → 387500. No quote or policy money changed.
- `uv run python scripts/engine_fixture_run.py` → `"ok": true, "events": 3248, "finalStateSha256": "07f7b19c…49f9"`, 116/114/2/0, full replay, snapshot replay and second run all hash-equal. **MANIFEST hash changed, as expected** (pricing changed). So did events.jsonl, daily_pnl.csv and `contracts/test/fixtures/{pool,waterfall}_cases.json`. `forge test --match-path test/parity/WaterfallParity.t.sol` → PASS.
- `bash scripts/deploy-engine.sh` → bundle check ok (63 MB), https://wi-engine.vercel.app health ok, specHash 911b9ab6….

**NYC cool-day price per day (360 units, 10 °F cap, week of 07-16), live engine, private world:**

| Line | 75 °F | 80 °F | 85 °F | 86 °F | 87 °F | 88 °F |
|---|---|---|---|---|---|---|
| Before | $46.88 | $46.88 | $46.88 | $46.88 | $46.88 | $46.88 |
| After | $11.16 | $11.16 | $11.16 | $11.86 | $15.61 | $21.92 |

$11.16 is the floor: $3.60 tail (1¢ × 360) + $7.20 risk margin + $0.36 fee. At 85 °F and below, the floor binds. The price moves with the line only in the last 3 °F under the rung edge.

**2. Portal.** `PoolBoard.tsx`: value per share was assets/raw shares. It's now USDC per whole share (1e12 raw), and reads 1.0000 / 1.0010. `CoverageFlow.tsx`: an unpriced suggestion now reads "We can't price this line in this month; try a higher line." For cold cover it says "lower", which is my addition. Wordmark "WI · weather cover" is in `Header.tsx`, on the landing page (`page.tsx`) and in the page titles (`layout.tsx`, trade/admin/pool). The repo codename is unchanged. `pnpm exec tsc --noEmit` clean, `pnpm lint` clean, `pnpm build` (inside a mkdir `.build-lock`, removed afterwards) exit 0, `bash scripts/deploy-portal.sh` ok (/ 200, health sim, Square fixture 3 locations).

**3. Demo world.** `seed-demo.py`: NYC cold 75 °F × 360 now costs $78.12 (was $328.16), wallet $921.88. CHI and MIA are unchanged. Junior $200,193.84, senior $300,000.92, utilisation 2.01%. `--check` OK before and after the smoke. `node scripts/smoke-demo.mjs` → **SMOKE PASS, 13/13, 15.2 s** at https://wi-portal.vercel.app. Screenshots 01–12, SMOKE.md and seed-state.json are regenerated. `DEMO-SCRIPT.md`: the Scoops paragraph now explains the line-dependent price, and the "same whatever line" caveat is gone. The pool table has the new numbers plus a Value per share row, and the 0.0000 warning is gone. Step 3 quotes the new card wording.

**4. Decks.** `scripts/build_decks.py` is the source (its output was byte-identical to both decks before I edited it), so I edited it and re-ran it. {{PORTAL_ALIAS}} is filled, and every `reports/portal/*.png` visual now points to a Phase 13 screenshot (03, 04, 06, 07, 11). `DEMO-WALKTHROUGH.md` was edited by hand: alias, 400 days, "5% on the suggestion card, 7% on the 90 °F quote", $334.95, $743.05, and the fallback screenshots.
- Deviation: the walkthrough's shop is now the Chicago bakery, not an NYC ice-cream shop. The DEMO-SCRIPT live loop is the only one with smoke-verified on-screen numbers. There's no verified NYC full-week balance.

**5. Memo.** `14-TOKEN-POOL-MEMO.md` Appendix E and H now say 12-day unstake cooldown, 10-day withdrawals. I also changed §8 line 130 so it doesn't contradict them. The banned-word grep on the memo, both decks, DEMO-WALKTHROUGH, NARRATIVE and DEMO-SCRIPT found 0 hits.

**Remaining placeholders:** `{{TEAM_LINE}}` in both decks. All "pending Phase 3" lines are untouched.

**Not fixed**
- SPEC §17 still lists `unstakeCooldown` as "10 d each". The seat ruling says 12 (09-LEDGER applies it), so the memo now cites a §17 value the SPEC doesn't show yet.
- The tail spread is a stand-in: the station-gap spread stands in for how far the temperature can land below the lowest rung. The formula is recorded in §18 as a first version.
- On the "You place the Kalshi part" card, "Station leg (Kalshi )" and "Local difference leg (, 0 units)" render blank when there's no residual (visible in 07-recommend-quotes.png). Out of scope.
- Anyone who advances `demo` with the token still moves the shared world (13-SUMMARY item 3). That's operational, not code.
