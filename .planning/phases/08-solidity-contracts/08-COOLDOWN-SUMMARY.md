# 08-COOLDOWN SUMMARY — unstakeCooldown 12 days (2026-09-30)

**Files changed (2):** `src/wi/engine/state.py` (DEFAULT_PARAMS `unstakeCooldown` 10 -> 12 * DAY_S) and `contracts/script/Deploy.s.sol` (`UNSTAKE_COOLDOWN_S` default 10 -> 12 days; Configure.s.sol has no cooldown arg). withdrawDelay and houseReturnWindow stay 10.
**Regenerated:** `uv run python scripts/engine_fixture_run.py` (it also writes the 8 parity fixtures via parity.write_all). Result `"ok": true`, 3248 events, finalStateSha256 `ecf1aa34…5fb7` (was `07f7b19c…49f9`). MANIFEST hashes changed as expected: params (unstakeCooldown 864000 -> 1036800, paramsSha256), world.json, events.jsonl, lastEventHash, finalStateSha256, gitHead. All 8 `contracts/test/fixtures/*.json` are byte-identical to before (no fixture case depends on the cooldown).
**pytest:** `uv run pytest tests/engine tests/api -q` -> `34 passed, 2 skipped, 3 warnings in 9.32s`.
**forge:** `Ran 13 test suites in 11.80s (22.43s CPU time): 31 tests passed, 0 failed, 0 skipped (31 total tests)`.
**Golden:** tests/api/golden/scenario_nyc_3d.json unchanged and passes: the API catalog already overrode `unstakeCooldown` to 12 d (`src/wi/api/catalog.py` PARAM_OVERRIDES), which is now redundant with the engine default. I left it in place.
**Text sweep:** src/wi/api, portal, docs show no 10-day unstake text. The portal reads `cooldownDays` from the API, SPEC §9/§17 already say 12. No edits needed.
**Left alone (out of scope):** Solidity tests still build `WIStaking(..., 10 days)` (ProtocolFixture.sol:55, HaircutParity.t.sol:52, WaterfallParity.t.sol:105); they pass and do not exercise the cooldown length against the engine. Bump them if the seat wants test scaffolding aligned.
