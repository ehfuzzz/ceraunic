.PHONY: sync data report test

sync:
	uv sync

# One command for the Phase 1 pulls, in this order, each step skipping what exists:
#   1. Kalshi: `discover` only if data/manifests/kalshi-series.csv is missing (it rewrites that file);
#      `pull --all-weather` is resume-safe (settled markets with a candle file are skipped, open ones re-pulled).
#   2. IEM station weather: ASOS files already current through UTC-yesterday are reused; CLI/CF6 are re-fetched (small).
#   3. Grids + GHCN-D (plan 01-04): scripts/pull_grids.py, once it exists.
# Run serially (no -j): all sources share one IP and the rate limits in docs/CONVENTIONS.md section 12.
data:
	@test -f data/manifests/kalshi-series.csv || uv run python scripts/pull_kalshi.py discover
	uv run python scripts/pull_kalshi.py pull --all-weather
	uv run python -m wi.data.iem
	@if [ -f scripts/pull_grids.py ]; then uv run python scripts/pull_grids.py; else echo "pull_grids: scripts/pull_grids.py not present yet (plan 01-04); skipped"; fi

# Phase 6 (EVAL-07): rebuild reports/EVALUATION.md + reports/figures/ from the phase results.json files,
# then export reports/EVALUATION.pdf (pandoc, if installed) or reports/EVALUATION.html. Computes no new statistic;
# re-run the phase scripts first to refresh numbers. Sections 5-6 fill from reports/eval-03/results.json once it exists.
report:
	uv run python scripts/build_report.py

test:
	uv run pytest || [ $$? -eq 5 ]  # exit 5 = no tests collected
