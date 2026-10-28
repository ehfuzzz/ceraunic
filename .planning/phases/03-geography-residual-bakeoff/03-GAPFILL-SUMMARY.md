# Phase 3 gap-fill (PRISM tmax 2026-08-01): NOT FILLED, nothing changed

Run 2026-09-30 22:20-22:22Z. The step stopped after the pull; no numbers moved, so the old -> new table is empty.

- Dry run planned exactly 3 files: tmax 2026-08-01, ppt 2026-09-30, tmax 2026-09-30 (2005 cached, 0 blocked). As briefed.
- `pull_grids.py prism` got HTTP 200 for all three but the body was not a zip, so the script logged "notzip" and kept nothing. No npz written for 2026-08-01 or 2026-09-30 (tmax dir still has no 20260801.npz).
- Cause for 2026-08-01 (read from the server's error file): "You have tried to download prism_tmax_us_25m_20260801.zip more than twice in one day (Pacific local time)... repeated offenses may result in your IP address being blocked." Some earlier run today already fetched it twice. I confirmed with one more curl, which was a third request; I made no further requests. The 09-30 files also came back non-zip; reason not read (likely the same cap or not yet published). Do not retry them today.
- Earliest safe retry: after Pacific midnight, 2026-10-01T07:00Z. The 24 h-rule window for the 9-cell re-pull starts 2026-10-01T13:23Z, so the gap-fill can run at 07:00Z-13:00Z tomorrow as a separate step (same command, keep the same backup and steps). Check that no other process fetches 2026-08-01 before then.
- Sanity check: the pull re-assembled the PRISM monthly disc partitions from the unchanged npz cache (mtimes changed, content not). `eval03.py --all` afterwards gave results.json, tables.md and RESULTS.md identical to the backup except `written_utc`. I restored results.json from the backup, so it is byte for byte the old file.
- Verdicts flipped: none. n_pairs unchanged (G1-P temperature still 27 of 37 pairs). Hand-written deck numbers (+0.061 G1-P, +0.052 P-A-IDW, +0.033 R-A, 0.81 station alone, 0.807) still hold, because no input moved.
- `make report`, `build_decks.py`, `phase3_repull_diff.py` not run (nothing to rebuild). grids.csv md5 still 65b8673d91a2722ace1551cd45c602f1.
- Files touched: data/cache/grid_disc/source=prism/station=*/part-*.parquet (re-written, same content), reports/eval-03/results.json (rewritten, then restored). Backup of 8 files: scratchpad gapfill-backup/.
