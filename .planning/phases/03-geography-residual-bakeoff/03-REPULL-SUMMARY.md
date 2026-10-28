# Phase 3 PRISM re-pull: summary (deviation 1 resolved)

Worker: worker, 2026-10-02. Nothing committed; the seat commits. No PRISM request was made during the write-up (only `pull_grids.py prism --dry-run`, which reads disk only).

## What ran
- `bash scripts/phase3_repull.sh`, 2026-10-02 06:21:16Z to about 08:27Z, exit 0 (log `var/phase3-repull/run-2026-10-02.log`).
- (b) 2008 PRISM daily files (tmax and ppt, 2024-01-01..2026-09-30), each requested once, kept only at the 9 cells in `reports/eval-03/repull_points.json` (CKZ, DPA, FRG, FXE, HPN, JOT, LOM, PWK, SMQ) in `data/cache/prism_days_extra/`; 2008 rows appended to `data/manifests/grids.csv`.
- (c) `uv run python scripts/eval03.py --all` (results.json `meta.written_utc` 2026-10-02T08:27:30Z). (d) `make report`. (e) `python3 scripts/build_decks.py`. (f) old -> new table and the file:line list.
- Baseline `var/phase3-repull/results.before.json`; full change list `var/phase3-repull/changes.tsv` (1,311 leaves). Both are in the gitignored `var/`, so the headline numbers are copied below.

## Old -> new headline (reports/eval-03/results.json)

| key | 2026-09-30 | 2026-10-02 |
|---|---|---|
| `bakeoff.rain.G1-P.n_pairs` | 19 | 26 |
| `bakeoff.rain.G1-P.pooled_median_dhe` [`dhe_ci`] | +0.186 [0.085, 0.274] | +0.229 [0.119, 0.318] |
| `bakeoff.rain.G1-P.pooled_median_he` [`he_ci`] | 0.864 [0.789, 0.921] | 0.808 [0.734, 0.903] |
| `bakeoff.rain.G1-P.pooled_median_he0_same_pairs` | 0.658 | 0.491 |
| `bakeoff.rain.G1-P.pooled_median_eta` | 0.67 | 0.76 |
| `bakeoff.rain.G1-P.share_pairs_dhe_pos` | 95 % | 96 % |
| `bakeoff.rain.G1-P.sd_r_median` / `L_median` | 0.37 / 0.09 | 0.41 / 0.10 |
| `bakeoff.rain.G1-P*.pooled_median_dhe` [`dhe_ci`] | +0.111 [−0.016, 0.241] | +0.176 [0.041, 0.297] |
| `bakeoff.temperature.G1-P.n_pairs` | 27 | 37 |
| `bakeoff.temperature.G1-P.pooled_median_dhe` [`dhe_ci`] | +0.061 [0.039, 0.074] | +0.061 [0.044, 0.075] |
| `bakeoff.temperature.G1-P.pooled_median_he` | 0.854 | 0.875 |
| `bakeoff.temperature.G1-P.pooled_median_eta` | 0.47 | 0.47 |
| `verdicts.winner_vs_next_survivor.rain` (G1-P vs R-A) | +0.168 [0.082, 0.259] | +0.112 [0.032, 0.238] |
| `verdicts.winner_vs_runner_up.rain` (G1-P vs P-A-IDW) | +0.119 [0.045, 0.251] | +0.062 [−0.008, 0.229] |
| `verdicts.winner_vs_runner_up.temperature` | P-A-IDW vs G1-P, +0.014 [−0.016, 0.031] | G1-P vs P-A-IDW, +0.008 [−0.015, 0.031] |
| `sensitivities.rain.may_sep.G1-P` ΔHE | +0.272 | +0.357 |
| `sensitivities.rain.posthoc_iem_clean_era_2025_10_on.G1-P` ΔHE | +0.102 (R-A +0.108) | +0.150 (R-A +0.108) |
| `sensitivities.temperature.may_sep.G1-P` ΔHE | +0.074 | +0.089 |

Only G1-P / G1-P* numbers and things built from them moved. The 46 G1-P pairs already evaluated (27 temperature, 19 rain) have identical per-pair values; only the 17 new pairs were added. The 7 new rain pairs all have ΔHE above the old pooled median (they are the pairs where the station leg does worst), which is why ΔHE went up while HE went down. For temperature the 10 new pairs split 5 above / 5 below the old median, so the pooled ΔHE is exactly unchanged.

## Verdict changes (bars from PREREG.md, unchanged)
Every verdict-level field that changed (`verdicts.*`, P1-P4, winners):
1. `verdicts.rules.rain.G1-P*.P1` (= `bakeoff.rain.G1-P*.P1`): False -> True. G1-P* still fails P3 (η 0.34 < 0.5) and is a continuity design, so its outcome stays FAILS / continuity.
2. `verdicts.runner_up.temperature`: G1-P -> P-A-IDW, and `winner_vs_runner_up.temperature.designs` swapped to [G1-P, P-A-IDW]. With no winner, "top" is the highest-HE design, now G1-P (0.875 vs 0.867). Nothing survives either way; the HE gap is +0.008 [−0.015, 0.031].
3. `verdicts.winner_vs_runner_up.rain`: +0.119 [0.045, 0.251] -> +0.062 [−0.008, 0.229]. G1-P's HE lead over P-A-IDW (which fails P1) is no longer clear of zero. The winner rule picks the highest-HE survivor and does not test this gap, so the verdict stands, but the text no longer says G1-P clearly beats the best failing design.
4. `verdicts.winner_vs_next_survivor.rain` (G1-P vs R-A): +0.168 [0.082, 0.259] -> +0.112 [0.032, 0.238]. Still clear of zero.
5. `verdicts.best_if_none.temperature` numbers moved (HE 0.854 -> 0.875, CI [0.044, 0.075]); design still G1-P, P1 and P3 still fail.

Unchanged: `verdicts.winner.rain` = G1-P; `verdicts.winner.temperature` = null (nothing clears +0.10); `verdicts.survivors` = rain [G1-P, R-A], temperature []; every other P1-P4 flag; PC1 not adopted. No design passed or failed where it did not before, apart from the G1-P* P1 flag above.

## Vintage flag ("days whose fresh disc cells differ from the Phase 1 cache: 2")
- What the count is: the number of extra-cache files (one per variable and day) whose `disc_cells_changed` > 0. The two files are **tmax 2026-09-26 and ppt 2026-09-26**: one calendar day, counted once per variable.
- Why: Phase 1 fetched that day on 2026-09-30 as PRISM release 1 (created 20260927-0425); the re-pull got release 2 (created 20261001-0423). 1,219 of 1,494 tmax disc cells and 1,012 of 1,494 ppt disc cells differ.
- Size of the differences: cannot be known from disk. The puller stores only the count (`src/wi/data/grids.py`, `_prism_day_extra`); the fresh disc values were not kept and the zip was deleted. The release-1 values of the 9 new cells never existed on disk either. Getting the size would need another download, which this pass did not make.
- Does it touch the evaluation: no. Label 2026-09-26 is calendar day 2026-09-25, and eval03 reindexes every grid to days ending 2026-08-31 (`src/wi/eval03/run.py`; train 2024, test 2025-01-01..2026-08-31). No pair uses that day.
- Every other day: on all 2,003 other files that Phase 1 also has, the fresh file matched the Phase 1 cache at every one of the 1,494 disc cells, and release number and creation stamp match too. So within the windows the new cells and the station cells come from the same PRISM vintage. Three files have no Phase 1 counterpart (tmax 2026-08-01, tmax and ppt 2026-09-30).
- Worst case: zero effect, so no eval03 re-run was needed to bound it. **The new G1-P numbers can be trusted as they stand** on the vintage question. (The usual caveat stays: PRISM count-2 to count-8 revisions are unmeasured.)

## Still open
- **Deviation 6 (data gap, OPEN)**: the Phase 1 disc cache has no tmax for label 2026-08-01 (CLI day 2026-07-31), so G1-P, G1-P* and R-P drop that one temperature test day (per-pair `n` 598 vs 599 for D0). The re-pull fetched that file at 08:19:38Z for the 9 extra cells only. PRISM allows 2 downloads of a file per Pacific day and threatens IP blocks, so it waits. Run after 2026-10-03T08:33Z (PRISM resets at 07:00Z, but the puller's own 24 h gate holds the file until 08:24:38Z; `uv run python scripts/pull_grids.py prism --dry-run` confirms without network): `uv run python scripts/pull_grids.py prism` once (it also fetches ppt/tmax 2026-09-30, outside the windows), then `uv run python scripts/eval03.py --all`, diff results.json before/after (`python3 scripts/phase3_repull_diff.py diff OLD NEW`), `make report`, `python3 scripts/build_decks.py`. Check the fetched file's release against the 9-cell copy (release 3, created 20260922-0710).
- results.json `deviations` is a copy of deviations.json made at eval03 run time; it still shows deviation 1 without its resolution until the next eval03 run. The report's deviation table now reads resolutions and later entries from deviations.json, so EVALUATION.md is current.
- Pre-existing, not touched: slide S-G "Not proven" in `render_decks.py` says the best temperature design is +0.05 (P-A-IDW), while the decks' evidence and the memo say best +0.061 (G1-P). This predates the re-pull (G1-P was +0.061 before too); seat's call.
- Phase 17 still waits on the owner.

## Files changed by this pass (on top of the run's own outputs: results.json, tables.md, figures, EVALUATION.md/.html, grids.csv)
- Generators: `scripts/build_report.py` (§6 table captions, §6 pair paragraph rewritten around the full pair set and both paired comparisons, data note on grids, deviation table shows resolutions/new entries from deviations.json, header "time (UTC; 2026-09-30 unless dated)"); `scripts/build_decks.py` (S-G Proven line, heat and rain evidence lines); `scripts/render_decks.py` (S-G Proven bullet and sources line).
- Regenerated: `reports/EVALUATION.md`, `reports/EVALUATION.html`, `reports/pitch/DECK-crypto.md`, `reports/pitch/DECK-fintech.md`.
- Hand-written: `reports/pitch/14-TOKEN-POOL-MEMO.md` (§8 bullet, footnote e03), `reports/pitch/DEMO-WALKTHROUGH.md` (line 44), `reports/eval-03/RESULTS.md`, `reports/eval-03/residual-spec.md`, `reports/eval-03/deviations.json` (deviation 1 RESOLVED with original kept; deviation 6 OPEN added), `.planning/PROJECT.md`, `.planning/STATE.md`, `.planning/HANDOFF.md`, `03-SUMMARY.md`, `03-FILL-SUMMARY.md` (dated note only).

## Slides to republish (do not publish from here)
Only shared slide **S-G**, file id `sg` (`sg.html`), in both decks: crypto slide 14, fintech slide 14. No other slide text in `render_decks.py` changed.

## Stale-hit check
`python3 scripts/phase3_repull_diff.py handwritten var/phase3-repull/results.before.json reports/eval-03/results.json` still lists 64 lines, because it flags any line with a pair count, "deviation 1", or a number that equals an old value. Read one by one, none is stale. They fall into:
- New text that cites the new numbers, mentions deviation 1 as resolved, or quotes old values on purpose as "was ..." (EVALUATION.md 45/332/352/354/585, decks, memo 125/314, walkthrough 44, RESULTS.md 6/27/29/160, residual-spec 3/9/41/49/71, PROJECT.md 28, STATE.md 3, 03-SUMMARY 5/19/34).
- Coincidental number matches (for example 0.119 is now the ΔHE CI low and was the old runner-up gap; 0.789 is TTN's D0 cross-market HE; memo 0.251 is a capital figure; PC1 lines).
- Station-leg pair counts that never depended on PRISM (37 / 26 / 22 pairs; P-A-IDW "all 37 pairs").
- Deliberate historical records: EVALUATION.md 116 and RESULTS.md 159 (deviation 1 original text), 03-SUMMARY 33 (deviation 1 as logged), HANDOFF 77/79 (2026-09-30 plan), 03-FILL-SUMMARY 7/8/9/24 (record of the 2026-09-30 pass, with a dated note on top). Outside the script's list, also historical and left alone: 03-REPULL-PREP.md, 03-GAPFILL-SUMMARY.md, 07-CONSISTENCY.md, 07-CONTEXT.md, 13-RAIN-DOCS-SUMMARY.md.
