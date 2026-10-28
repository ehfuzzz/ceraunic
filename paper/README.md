# Paper: Can exchange-traded weather contracts hedge parametric cover for small businesses?

Working paper by Ehfaz Zoha (Princeton University). Draft for review, October 2026. Not posted anywhere yet.

This folder holds the paper and nothing else. Every number in it was already computed by the project's phase scripts. Writing the paper did not re-run any script, pull any data or change any result.

## Files

| file | what it is |
|---|---|
| `main.pdf` | the paper (18 pages) |
| `main.tex` | the LaTeX source (`article` class, natbib) |
| `refs.bib` | references (entered from memory; check each one before posting) |
| `figures/*.png` | figures, copied unchanged from `reports/figures/` and `reports/eval-03/figures/` |
| `NUMBERS.md` | every number in the paper, with the file and key it comes from |
| `README.md` | this file |

## Build the PDF

`main.pdf` is built from `main.tex` with Tectonic 0.17.0. To rebuild it, use either of these:

```bash
cd paper && tectonic main.tex
```

```bash
cd paper && latexmk -pdf main.tex
```

## Which script reproduces what

All commands run from the repository root. They read the free public data cached under `data/` (pulled by `make data`; see `data/manifests/DATA.md` for URLs, sizes and checksums). Each phase's rules were frozen in its `PREREG*.md` before the script first produced a number.

| paper item | results file | script | rules |
|---|---|---|---|
| Table 2 (station ladder), Figures 1-2, rain binary numbers in Section 6.1, T1-T4 | `reports/eval-01/results.json`, `sensitivity_trace_dry.json`, `trace_kxrain_2026.json` | `uv run python scripts/eval02.py --all` | `reports/eval-01/PREREG.md` |
| Table 3 (geography basis), Figure 3 | `reports/eval-03/results.json` (`eval02.*`) | `uv run python scripts/eval03.py --all` | `reports/eval-03/PREREG.md` |
| Table 4 (rain bake-off), Figures 4-5, temperature bake-off numbers in Section 6.3 | `reports/eval-03/results.json` (`bakeoff.*`, `verdicts.*`) | `uv run python scripts/eval03.py --all` (after `uv run python scripts/pull_grids.py prism --points reports/eval-03/repull_points.json` has fetched the extra PRISM cells) | `reports/eval-03/PREREG.md`; deviations in `reports/eval-03/deviations.json` |
| Table 5 (capital), Figure 6, netting, M1-M5, house P&L (Section 6.4) | `reports/eval-04-05/results.json`, `handoff.json` | `uv run python scripts/eval04.py --all` | `reports/eval-04-05/PREREG.md` |
| Junior-layer returns (Section 6.4) | `reports/eval-04-05/junior_returns.json` | `uv run python scripts/eval04_junior.py` | `reports/eval-04-05/PREREG-junior.md` |
| Weekly rain book (Section 6.4, ledger R1-R5) | `reports/eval-04-05/rain_book.json` | `uv run python scripts/eval04_rain.py` | `reports/eval-04-05/PREREG-rain.md` |
| Learning tests (Section 6.5, ledger T1-T4, P1) | `reports/eval-06/results.json` | `uv run python scripts/eval05.py --all` | `reports/eval-06/PREREG.md`; post-hoc rulings in `reports/EVALUATION.md` §3 (deviations table) |
| Figures (all) | the results files above | `make report` (= `uv run python scripts/build_report.py`) rebuilds `reports/figures/`; `scripts/eval03.py --all` rebuilds `reports/eval-03/figures/` | none (formatting only) |
| Table 1 and Appendix A (ledger) | verdict keys in each results file | none (read by hand from the files above) | each PREREG |

Notes on naming: the script numbers are one behind the evaluation numbers. `eval02.py` writes `reports/eval-01/`, `eval05.py` writes `reports/eval-06/`, and `eval04.py` writes `reports/eval-04-05/`.

`reports/EVALUATION.md` is the longer technical report the paper is drawn from. Its Appendix B maps every number in that report to a results-file key.

## Known open items

- One PRISM temperature test day (CLI day 2026-07-31) is still missing for the PRISM residual designs (Phase 3 deviation 6, open). Filling it and re-running `eval03.py --all` could move the temperature PRISM-design numbers slightly; it does not affect the rain results.
- Kalshi's record for the New York daily-high series now names The Weather Company as the settlement source. The station-leg numbers were measured against the NWS climate report and have not been re-checked for dates after the change.
