# Phase 3 re-pull prep (deviation 1)

Prepared 2026-09-30. Nothing was downloaded from PRISM while preparing this; everything below was dry-run against what is on disk.

## Run it

    cd ~/weather-insurance
    bash scripts/phase3_repull.sh              # on or after 2026-10-01T15:40:00Z
    bash scripts/phase3_repull.sh --dry-run    # any time: gate status + files it would fetch, writes nothing

Before the gate it exits 4 with "too early" and fetches nothing (checked 2026-09-30T20:45Z). It never commits.

Steps it runs: (b) `pull_grids.py prism --points reports/eval-03/repull_points.json`, (c) `uv run python scripts/eval03.py --all`, (d) `make report`, (e) `python3 scripts/build_decks.py`, (f) old -> new table against `var/phase3-repull/results.before.json` (snapshot of results.json taken before the pull, kept on re-runs; full list in `var/phase3-repull/changes.tsv`) and the file:line list of hand-written text.

Idempotent: the extra cells are cached per (var, day) in `data/cache/prism_days_extra/`; a cached day is never fetched again; the 24 h gate is per file, read from `data/manifests/grids.csv`. If the pull exits 5 (some days still inside their 24 h window or not published), run the script again; it stops before eval03.

Expected runtime: about 2005 files x (2.5 s sleep + download), so about 2 h 20 min (Phase 1's original pull ran 13:18Z to 15:36Z). eval03, `make report`, `build_decks` add about 1 to 2 minutes. About 2005 CONUS files go through `data/raw/prism` and are deleted after each day; disk need is small (extra cache is 9 cells x 2005 files, well under 100 MB); free space now is 34 GB.

## What is pulled

`reports/eval-03/repull_points.json`: 9 points (CKZ, DPA, FRG, FXE, HPN, JOT, LOM, PWK, SMQ) in 9 unique PRISM cells, worth 10 temperature and 7 rain pairs. Point-to-station distances (km): CKZ-TTN 42.1, DPA-MDW 43.3, FRG-NYC 47.2, FXE-MIA 48.1, HPN-NYC 38.8, JOT-MDW 46.1, LOM-TTN 41.2, PWK-MDW 39.3, SMQ-EWR 42.7 (SMQ also TTN 40.5). The file lists each cell id, i/j index and lat/lon. The equivalent disc is `--radius-km 50` (615 extra cells); the points list is the default because it is 9 cells, not 615.

PRISM has no sub-grid download: every file is the whole CONUS grid for one (variable, day). So "only what is missing" means only the 9 cells are kept, not that fewer files are fetched. The cache Phase 1 built holds only 40 km discs, so the new cells cannot come from it; what is reused is the disc cache for the S cell (same-source spread) and the per-file 24 h gate.

## Dry-run output (2026-09-30, before the gate)

    PRISM dry run [extra cells from reports/eval-03/repull_points.json: 9 cells, 2024-01-01..2026-09-30]: 2008 files in window
      cached (skipped): 0
      would fetch: 3   from a local zip (no network): 0   blocked by the 24 h rule: 2005
      24 h rule: earliest file eligible 2026-10-01T13:23:27Z, last file eligible 2026-10-01T15:41:22Z
      fetch        tmax 2026-08-01  .../prism/data/get/us/4km/tmax/20260801?format=nc
      fetch        ppt  2026-09-30  .../ppt/20260930?format=nc
      fetch        tmax 2026-09-30  .../tmax/20260930?format=nc
      blocked_24h  ppt  2024-01-01  ...  (eligible 2026-10-01T13:26:53Z)
      ... (1996 more)
      blocked_24h  tmax 2026-09-29  ...  (eligible 2026-10-01T15:41:18Z)

`cached (skipped): 0` is correct: the extra cache does not exist yet. The 3 "fetch" files were not fetched in Phase 1 (tmax 2026-08-01 is missing from the Phase 1 cache; 2026-09-30 is the newest day), so the 24 h rule does not block them. The last file becomes eligible at 15:41:22Z, 82 s after the 15:40 gate; files are requested in date order at the original pace, so each one is reached well after its own eligibility (a file that is still early is reported as blocked and the script exits 5 for a re-run).

`uv run python scripts/pull_grids.py prism --dry-run` (no points) still prints only the default Phase 1 plan; `data/manifests/grids.csv` md5 was 65b8673d91a2722ace1551cd45c602f1 before and after every dry run and after the full test suite.

## Hand-written places that quote pair counts (fix after the run)

The numbers come from keys (`{{e03:...}}`) in build_report.py, so those update themselves. The prose does not. Old counts: G1-P temperature 27 of 37 pairs, rain 19 of 26 pairs; after the run these should be 37 of 37 and 26 of 26 (if every point gets a cell). Sentences like "no PRISM cell was pulled for the rest (deviation 1)" become wrong. The script prints the live list (`python3 scripts/phase3_repull_diff.py handwritten OLD NEW`); the list as of today:

Generators (fix in the source, then rerun `make report` / `build_decks.py`):
- `scripts/build_report.py:1029-1030` (table caption "G1-P has no PRISM cell at some points, Phase 3 deviation 1"), `:1058` (pair sentence "G1-P runs on X of Y rain pairs ... no PRISM cell was pulled"), `:1263` (Phase 1 kept 40 km discs, deviation 1 note). Appear in `reports/EVALUATION.md:45, 331, 351, 353, 584`.
- `scripts/build_decks.py:99, 148, 149, 157, 158` (appear in `reports/pitch/DECK-crypto.md:219, 227, 228`, `DECK-fintech.md:217, 225, 226`, and `DEMO-WALKTHROUGH.md:44`).
- `scripts/render_decks.py:140` ("+0.19, on 19 of 26 pairs"), `:146` ("rain G1-P +0.186 on 19/26 pairs"). This file is hand-written and is not regenerated by build_decks; the Slides artifacts need republishing after it is edited.

Hand-written, no generator:
- `reports/pitch/14-TOKEN-POOL-MEMO.md:125` (weekly rain design "run on 19 of 26 station pairs"), `:314` (footnote with +0.061 / +0.052 / +0.186 and pair counts), `:241`.
- `reports/eval-03/RESULTS.md:21, 26, 51, 70, 154` (pair counts, "no PRISM cell was pulled for the rest", the 15:51:37Z deviation log entry, and every G1-P number at 19/27 pairs; lines 22-24, 52-57, 71-77, 92-93, 120, 131 quote the old headline numbers and will move with them).
- `reports/eval-03/residual-spec.md:9, 41, 49, 79` (19 of 26, 27 of 37, "7 of 26 rain pairs have no PRISM cell", spec numbers for G1-P; also 42, 71, 80-81, 97, 104).
- `reports/eval-03/deviations.json` deviation 1 text (resolve it, do not delete: pre-registration discipline says the deviation and its fix stay on the record).

Planning text: `.planning/PROJECT.md:28`, `.planning/STATE.md:66`, `.planning/HANDOFF.md:77, 79`, `03-SUMMARY.md:10, 11, 17, 31`, `03-FILL-SUMMARY.md:22`.

Not affected: 37 (temperature) and 26 (rain) pair counts for the station leg alone (EVAL-02, D0, R-A, P-A-IDW) do not depend on PRISM.

## Read before running

OBJECTION (brief vs reality, part 1): `.planning/HANDOFF.md:17` says a default `pull_grids.py prism` re-run after the gate would fetch the 9 points. It would not: the default pull only writes the 40 km discs, so the 9 points stay without a cell. Use `scripts/phase3_repull.sh` (or `pull_grids.py prism --points ...`).

OBJECTION (part 2): "reuse the cache for everything already on disk" cannot cover the new cells; no cached day contains them (see "What is pulled"). Also, the brief's raw day 2026-07-15 in `data/raw/prism` does not exist (the raw dirs are empty), so tests use a synthetic PRISM zip.

Open points for the seat:
1. Vintage mix. The b cell comes from the new pull, the S cell from Phase 1 (old pull). PRISM revises recent days, so G1-P's same-source spread could mix vintages. The pull counts days whose fresh disc cells differ from the Phase 1 cache (`disc_cells_changed`, printed as "days whose fresh disc cells differ from the Phase 1 cache"). If that count is not 0, look before trusting the new G1-P.
2. tmax 2026-08-01 is absent from the default disc cache, which already affects the existing G1-P temperature (CLI day 2026-07-31). The extra pull fetches it for the 9 cells only; filling the default discs with `pull_grids.py prism --start 2026-08-01 --end 2026-08-01` would change existing numbers beyond the geography gap, so it was left alone.
3. The outer-ring G1-P stays unavailable (4 pairs).
4. eval03 reads the extras only for points that have no disc cell, so it is unchanged until the extras are assembled (verified: results.json identical except `written_utc` before any extras exist).

## Correction 2026-09-30T22:22:33Z (from 03-GAPFILL)
PRISM's actual rule (its error body): a file may be downloaded at most **twice per Pacific-time day**, and repeat offenses may get the IP blocked. So eligibility resets at Pacific midnight = 2026-10-01T07:00Z, not per-file 24 h. The gate in phase3_repull.sh (≥ 15:40Z) stays as a conservative bound. Rules for the run: request each file at most once; never retry a refusal the same Pacific day; a non-zip body = refusal (the puller already logs `notzip`). The 2026-08-01 tmax disc gap is also retryable from 07:00Z; it is not in the 9-cell pull — run the default `pull_grids.py prism` once after the script, per HANDOFF.
