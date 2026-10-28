# 14-04: SPEC-example test pinned to 2000, PoolVault default 30 (2026-09-30)
1. `tests/engine/test_spec_examples.py::test_waterfall_and_haircut_examples`: one added line after `st = led.state` sets `st["params"]["seniorPremiumBps"] = 2000` with the comment "SPEC §8.3 illustration is at 2000; v0 default is 30 (SPEC §18 2026-09-30)". Engine default and SPEC untouched.
2. `contracts/src/PoolVault.sol` line 32: `seniorPremiumBps` initial value 2000 -> 30 (matches SPEC §17 and Configure.s.sol). Parity fixtures carry their own bps per case, so nothing needed reverting.
- `uv run pytest tests/engine -q` -> `19 passed in 8.46s`
- `forge build -q` -> no output (clean). `forge test -q` prints nothing on success, so the plain `forge test` summary line is: `Ran 13 test suites in 14.59s (25.91s CPU time): 31 tests passed, 0 failed, 0 skipped (31 total tests)`
- No git commands run; src/wi/api and tests/api not touched.
