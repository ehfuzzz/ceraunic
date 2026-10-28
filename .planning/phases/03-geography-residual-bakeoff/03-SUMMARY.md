# Phase 3 summary: geography basis (EVAL-02) and residual bake-off (EVAL-03)

Worker: worker, 2026-09-30. PREREG frozen verbatim 15:40:52Z; data-quality check 16:03:13Z, before any HE; final run 16:14Z. `uv run python scripts/eval03.py --all` takes about 15 s, and two runs give identical results.json apart from `written_utc`.

**Updated 2026-10-02** after the PRISM re-pull that resolved deviation 1 (re-run 08:27:30Z). The tables below carry the new numbers; the 2026-09-30 values and every change are in `03-REPULL-SUMMARY.md`.

## Verdicts (pre-registered rules; test window 2025-01-01..2026-08-31; 95 % joint circular block bootstrap CIs)
| question | result | verdict |
|---|---|---|
| EVAL-02, station leg alone, temperature (37 pairs) | pooled median HE(D0) 0.807 [0.785, 0.845]; markets 0.67 (MIA) to 0.87 (TTN) | descriptive |
| EVAL-02, rain weekly (26 pairs) | 0.491 [0.380, 0.658]; MIA 0.13 | descriptive |
| EVAL-03 temperature | best ΔHE G1-P +0.061 [0.044, 0.075] (37 pairs), P-A-IDW +0.052 [0.037, 0.065] (passes P2-P4), R-A +0.033 [0.020, 0.044] (η 0.498) | **nothing survives** (all fail P1 ≥ +0.10); C1-N, R-P KILLED |
| EVAL-03 rain weekly | G1-P +0.229 [0.119, 0.318], η 0.76, HE 0.808 (26 pairs); R-A +0.110 [0.055, 0.181], η 0.79, HE 0.696 | **G1-P and R-A survive; winner G1-P** (vs R-A +0.112 HE [0.032, 0.238]; vs the runner-up P-A-IDW, which fails P1, +0.062 [−0.008, 0.229], CI includes 0) |
| Q2: PC1 vs equal weights | ASOS temperature −0.055 [−0.080, −0.034]; rain −0.290 [−0.434, −0.119] | PC1 **not adopted** |
Insurance-grade flag (HE ≥ 0.70): met by rain G1-P. Temperature is already at 0.81 with the station leg alone.

## What wins and why
- Rain: PRISM per-cell weekly spread (same source at the business cell and at S) plus the station leg. Radar-aided PRISM summed over a week tracks nearby gauges; the settlement gauge does not.
- The rain win now rests on all 26 pairs (it was 19 of 26 until the 2026-10-02 re-pull). The gain is concentrated in May-Sep (+0.36); Oct 2025-Aug 2026 gives +0.15. G1-P's HE lead over the best failing design (P-A-IDW) is not significant.
- R-A rain (one ASOS metro contract per market, no revision risk) is the surviving alternate.
- Temperature: within 50 km the station leg already carries most of the signal. Residuals add at most about 0.05-0.06, below the bar.
- With Kalshi's forecast-centred strike (sensitivity), HE(D0) drops to 0.27-0.47 and P-A-IDW adds +0.147. That is the case for RFQ temperature residuals.
- `residual-spec.md`: the filled G1-P spec (PRISM cells, count-2 snapshot at T+5, void if a day is missing), the R-A rain spec, and P-A-IDW as the RFQ reference for temperature.

## Compared with ins2 (per-cell nClimGrid, FAILED)
- ins2's form is G1-N* here, and it reproduces ins2's residual correlation: 0.70-0.80 (temperature) against ins2's 0.74-0.83.
- The same-source spread G1-N cuts it to 0.13-0.35, κ from 0.74-0.83 to 0.30-0.44, and doubles η (0.19 → 0.40). That is the mechanism 03-RESEARCH predicted.
- But G1-N adds only +0.022 for temperature.
- Designs that beat ins2's form: for temperature, G1-P and P-A-IDW on both gain and η (still under the bar); for rain, G1-P and R-A by a wide margin (both survive).
- What changed: weekly aggregation, PRISM's radar and gauge blend, held-out stations as truth (not grid cells), and same-source residuals.

## Deviations (UTC-logged in reports/eval-03/deviations.json)
1. 15:51Z: no PRISM cell for 9 points (10 temperature and 7 rain pairs). Phase 1 kept only 40 km discs, and PRISM blocks re-downloads for 24 h. All designs are also reported on the same pairs; the winner holds. Re-pull after 2026-10-01 15:40Z and re-run.
   **RESOLVED 2026-10-02**: re-pulled the 9 cells (2008 files) and re-ran; G1-P and G1-P* now on 37 / 26 pairs. See `03-REPULL-SUMMARY.md`.
2. 15:51Z: PRISM contamination measured on the one kept day (2026-07-15). All truth stations were tmax inputs; few were ppt inputs.
3. 15:51Z: non-CLI stations checked against GHCN-D (per 03-PLAN).
4. 16:03Z: PC1 gives zero weight to inputs with < 50 % train coverage (HST, WRI and JOT have no GHCN-D data in 2024).
5. 16:03Z: one post-hoc descriptive sensitivity (IEM-clean era, 2025-10 on).
6. 2026-10-02T09:27Z, **data gap, not yet filled**: the Phase 1 disc cache has no PRISM tmax for label 2026-08-01 (CLI day 2026-07-31), so G1-P, G1-P* and R-P drop that one temperature test day. The re-pull fetched that file for the 9 extra cells only. Filling the discs needs a second download of the same file, and PRISM allows at most 2 downloads of a file per Pacific-time day and threatens IP blocks, so it waits. Command for later: `uv run python scripts/pull_grids.py prism` once, after 2026-10-03T07:00Z (PRISM's reset) and in practice after 08:33Z (the puller's own 24 h gate holds the file until 08:24:38Z; `--dry-run` shows it without network). Then `uv run python scripts/eval03.py --all` and a before/after comparison of results.json. The same pull also fetches ppt and tmax 2026-09-30, outside the windows.

Data-quality result: all CLI and USW stations switched to CLI or GHCN-D tmax (IEM 0.4-0.9 °F low on 39-68 % of days before 2025-10). Precip stays on IEM. JRB, MMU, GYY, LOM, CKZ, IGQ and 06C stay on unchecked IEM.

## What Phase 4's two-leg capital re-run would change
- Temperature has no listed residual. The listed product is the station leg only: C_30 about $416k against the $412k two-leg figure.
- Phase 4's "+$1,062/day NYC residual" P&L belongs to an RFQ book. The NYC R-A residual mean is +0.09 to +0.23 per unit-day (Central Park cool bias).
- Model the RFQ book on P-A-IDW: sd 0.79 per unit-day, κ 0.54-0.78.
- Rain needs a new weekly two-leg book: G1-P residual sd 0.41 per unit-week, κ 0.43-0.67, mean about 0. The station leg is carried by the house, since Kalshi has no liquid weekly rain ladder.

## What reports/EVALUATION.md now shows (`make report` run)
- §5-6 fill with no "n/a" from Phase 3 keys, and fig8 renders.
- Builder issues (not edited; for the Phase 6 owner):
  - (a) The §3 ledger formats `verdicts.winner.<var>` with `str`, so a null prints "winner: n/a" (§6 uses the `winner` format; build_report.py about line 496).
  - (b) `P3PROD_DONE` (about line 1493) reads "the residual design Phase 3 picked for temperature is none survived" and ignores the rain winner.
  - (c) Static text still calls R-A a placeholder "until Phase 3 picks a design" (§7 intro, limitations, coverage table), Phase 6 deviation E1 says Phase 3 had not landed, and the data note calls the grids "planned".
  - (d) The §6 table has no pair-count column, so G1-P's 19 and 27 pair bases are invisible there. `bakeoff.<var>.G1-P.verdict_note` carries them. (Fixed in 03-FILL; since the 2026-10-02 re-run the pair bases are 26 and 37 and the verdict_note is gone.)

## Files
- `reports/eval-03/`: PREREG.md, dq.md, deviations.json, results.json, tables.md, RESULTS.md, residual-spec.md, figures/{eval02_he0_vs_distance, bakeoff_dhe_temperature, bakeoff_dhe_rain, eta_vs_sdr}.png.
- Code: `src/wi/eval03/`{points, align, sources, indexes, designs, metrics, run}.py, and `scripts/eval03.py` (with --pull, --dq, --all).
- Tests: `tests/test_eval03.py`, the four tests (5 cases). Full suite: 54 passed, 2 skipped. One read-only `git status` was run by mistake at 16:14Z (see the worker report).
- Top-up pulls in data/cache/eval03 (4.2 MB kept): IEM daily for 12 stations, CLI for 9, NCEI county averages for 22 counties, and nClimGrid cells containing each station from 30 monthly grids streamed from memory (about 1.7 GB transferred, none kept). Free disk 25 GiB.
