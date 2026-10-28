# Phase 6 summary: evaluation report (EVAL-07)

Worker: worker, 2026-09-30 14:16-14:30Z (machine clock). Nothing committed or staged; no git commands run.

## What shipped
- `reports/EVALUATION.md` (short version, §1-11, Appendix A figures, B key map, C rebuild + input md5s) and `reports/EVALUATION.html` (self-contained, figures embedded). pandoc is not installed, so there is no PDF; the builder uses pandoc automatically once it is.
- `reports/figures/fig1..fig7*.png` (HE by city-year, overround by city-year, rain Brier, netting, capital, elasticity, learning curve); fig8 (geography) is built only when Phase 3 lands.
- `scripts/build_report.py`: reads only the results files and plots them; it computes no new statistics. Prose templates contain no result numbers. Every number is a `{{src:key|fmt}}` placeholder, and each one that renders is listed in Appendix B with its results.json key (179 in this build). Quoted non-results sources are labelled as such: the ins1 README table, DATA.md counts, and PREREG thresholds. A missing key raises, so there are no silent defaults. A lint pass flags any digit in the prose that sits outside a placeholder; the result is currently clean. Tables are code-built and name their source path in a caption. Two consecutive runs gave byte-identical output.
- `Makefile` target `report` (`uv run python scripts/build_report.py`).
- `.planning/phases/06-evaluation-report/06-EVAL03-CONTRACT.md`: the eval-03 results.json keys that §5-6 read (written by the build). **Seat: hand this to the Phase 3 worker.**

## How to rebuild
`make report`. To refresh numbers, re-run a phase script (eval02/eval04/eval05/eval03), then `make report`.

## Waiting on Phase 3
- §5 (EVAL-02) and §6 (EVAL-03) show a "Phase 3 pending" banner, the pre-registered pass rule (P1-P4, winner/PC1 rule, quoted as `pre:` constants from 03-RESEARCH), and the prior ins1/ins2 evidence clearly labelled. The short version, the §1 status table, the §3 ledger row, the §10 pilot line and the §11 checklist also switch automatically.
- I tested the Phase 3 path with a partial scratch fixture: it renders, missing keys show as n/a and are listed in Appendix C, and fig8 builds. The real eval-03 key names are not known yet. If Phase 3 uses other names, the fix is the contract file or the builder's `t_e03_*` / `sec5` / `sec6` functions.

## Headline as written (all numbers from results.json keys)
HE_cover 0.95 (liquid ladders, 24 h); HE_ladder 0.37 on 2025+ days (post hoc) and −0.32 over all years; T1 fails on price (overround 24.6 % against a 20 % bar). Netting: M1 passes at the minimum (3 of 5 stations); it is 0.019 under the null, so the pitch must not lead with it. Capital: C_30/notional 0.126 (0.25 for the station leg alone, 0.36 if priced at climatology), so leverage holds only with daily repricing. Elasticity: T2 fails (0.072 and 0.053 against 0.20), and the stand-ins are not retail sales. The seat's Phase 5 rulings are reported as post hoc.

## Gaps against the brief (also §11 of the report)
- Checklist source: PROJECT.md has no separate "Evaluation paragraph". I used the Core Value sentence plus the EVAL-01..07 lines (deviation E2).
- "Cheaper than a bespoke contract" is not measured: we have no bespoke quotes.
- No recorded order books: the S3 recorder was unreadable, so depth comes from one ins1 snapshot.
- EVAL-02/03 are pending Phase 3. Phase 4's residual leg is still the R-A placeholder, so the two-leg capital needs a re-run if Phase 3 picks another design.
- Rossmann/M5 were not used, PRISM revisions were not measured, and the markouts are simulated and partly a pricing artefact.
- Clock note (deviation E4): this Mac read 14:16-14:25Z, but 05-SEAT-RULINGS.md and STATE.md carry times up to 15:25Z. One clock is about an hour off. Freeze-before-results holds inside every phase's own files.
- No unit tests were added. The builder only formats and plots, fails loudly on missing keys, and the prose lint covers the "number without a key" risk.
