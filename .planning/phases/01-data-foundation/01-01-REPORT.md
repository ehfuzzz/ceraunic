# 01-01 report: repo scaffold + import prior work

Status: complete. One small deviation and one missing dataset (below). No OBJECTION.

## Created
- `pyproject.toml` (package `wi`, hatchling, src layout, requires-python >=3.12; deps numpy, pandas, pyarrow, scipy, netCDF4, requests, xarray, matplotlib, statsmodels, duckdb, pydantic, typer; dev group: pytest), `.python-version` = 3.14 (newest installed in `uv python list`; cpython 3.14.0; all deps resolved with wheels), `uv.lock`.
- `src/wi/{__init__,data,eval,engine,util}/__init__.py`.
- `.gitkeep` in `data/raw`, `data/cache`, `data/manifests`, `reports`, `scripts`, `docs`, `contracts`, `apps`, `prior/hl-mm-ins`.
- `prior/hl-mm-ins/`: `reports/ins1/` (all 11 requested files), `scripts/ins2/` (extract, analyze, revision), `reports/ins2/` (README, DATA, results.json plus results.txt, results_label_day_unshifted.json/.txt, revision.txt), `PREREG-EXCERPTS.md` (S4-RESULTS.md lines 1536-1552 ins1 pre-registration, 1553-1555 ins1 results entry, 1623-1626 ins2 V1 pre-registration; verbatim, with line refs), `ATTRIBUTION.md`.
- `docs/CONVENTIONS.md` (all seven requested conventions plus station list).
- `Makefile`: `sync`, `data` (prints Phase 1 plan list), `report` (placeholder), `test` (pytest; treats exit 5 "no tests collected" as success).
- `data/manifests/imported-2026-09-30.md` (path, source, bytes, md5 for every copied file).
- `.gitignore` edit: `data/raw/` and `data/cache/` ignored by content but `.gitkeep` re-included (a plain directory ignore, plus the generic `cache/` rule, would have kept the .gitkeep files out of git). Verified with `git check-ignore`: nc/npz ignored; manifests, rows.json and .gitkeep not ignored.

## Prior data found and copied (cp -p; originals untouched)
| file | bytes | md5 |
|---|---|---|
| data/raw/nclimgrid/ncdd-202607-grd-scaled.nc | 57,115,170 | c1936678cdaec2b121724e4210a35b4c |
| data/raw/nclimgrid/ncdd-202608-grd-scaled.nc | 57,244,383 | 312e899ce28b25298f96104f50980598 |
| data/raw/nclimgrid/ncdd-202609-grd-prelim.nc | 49,100,699 | f321fef7991baff873ce39fd242acf3a |
| data/raw/nclimgrid/ncdd-2026{07,08,09}-version.txt | 224 / 224 / 222 | see manifest |
| data/cache/ins2/cells.npz | 203,088 | 15c994c5bd0fde4250239705909a4186 |

The nc md5s match the ones recorded in ins2 DATA.md. Found only in `~/hl-mm-wt/ins2/var/ins2/` (not in corpus-fix or hl-mm); that worktree is the sole holder.

## Missing
- Kalshi ins1 candle cache (`candles.json`, ~40 MB; `pull_candles.py` writes it to its cwd). Not on disk anywhere under hl-mm or hl-mm-wt/* (searched by filename and by content grep for KXHIGHNY). `data/raw/kalshi/candles-ins1/` holds only a .gitkeep. The derived per-city-day values survive in `rows.json`; plan 01-02 re-pulls candles.
- September final grid `ncdd-202609-grd-scaled.nc`: not published yet (expected about 2026-10-06); not downloaded.

## Deviations and notes
- The 4 extra ins2 outputs (results.txt, results_label_day_unshifted.*, revision.txt) exist only in the `ins2` worktree, not corpus-fix; copied from there and noted in ATTRIBUTION.md. All other files in the two worktrees are identical (`diff -rq`).
- `uv sync` necessarily fetched PyPI packages; no other network use.
- ROADMAP plan 01-01 also lists a "pnpm workspace placeholder"; the brief did not ask for it, so only `apps/.gitkeep` exists.
- Conventions nuance: ins1 reports TWC-vs-NWS mismatch as "0-4 %"; Miami is 3/68 = 4.4 % raw, stated as such in CONVENTIONS.md. Overall 5/272.
- prior scripts still use hl-mm paths (`var/ins2/...`, `candles.json`); not rewired (history/reference).

## Verify
```
cd ~/weather-insurance
uv sync && uv run python -c "import wi, netCDF4, xarray"     # prints nothing
uv run python --version                                       # 3.14.0
make data; make report; make test                             # test: "no tests ran", exit 0
md5 -q data/raw/nclimgrid/*.nc data/cache/ins2/cells.npz      # compare with data/manifests/imported-2026-09-30.md
git check-ignore -v data/raw/nclimgrid/ncdd-202607-grd-scaled.nc data/raw/.gitkeep
find prior/hl-mm-ins -type f | sort
```
