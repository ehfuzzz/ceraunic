# Phase 3 results.json keys read by scripts/build_report.py

Written by the Phase 6 worker so that §5-6 of reports/EVALUATION.md fill automatically. Keys follow the Phase 3 pre-registration draft (03-RESEARCH.md) and 03-PLAN.md. A missing key renders as n/a and is listed in Appendix C of the report; nothing crashes. Add keys freely; renaming these needs a matching edit in build_report.py.

| key | type | meaning |
|---|---|---|
| `meta.prereg_frozen_utc`, `meta.written_utc` | str | freeze and write times (UTC, ISO) |
| `eval02.<variable>.pooled_median_he0` | float | pooled median HE of the station leg alone (D0) at held-out truth points ≤ 50 km |
| `eval02.<variable>.pooled_median_he0_ci` | [lo, hi] | joint circular block bootstrap 95 % CI |
| `eval02.<variable>.by_market.<MKT>.median_he0` | float | market median HE(D0) |
| `eval02.points` | list of {market, point, variable, dist_km, he0} | one row per (market, truth point, variable); drives the basis-vs-distance figure |
| `bakeoff.<variable>.<DESIGN>.pooled_median_he` | float | pooled median HE with station leg + residual |
| `bakeoff.<variable>.<DESIGN>.pooled_median_dhe`, `.dhe_ci` | float, [lo, hi] | P1 gain and its CI |
| `bakeoff.<variable>.<DESIGN>.share_pairs_dhe_pos`, `.markets_dhe_pos` | float, int | P2 breadth |
| `bakeoff.<variable>.<DESIGN>.pooled_median_eta` | float | P3 efficiency η = 2β − 1 |
| `bakeoff.<variable>.<DESIGN>.sd_r_median`, `.L_median` | float | residual sd and loading L at λ = 0.25 |
| `bakeoff.<variable>.<DESIGN>.settleable` | bool | P4 |
| `bakeoff.<variable>.<DESIGN>.verdict` | str | SURVIVES / FAILS / KILLED / continuity / exploratory / baseline |
| `verdicts.winner.<variable>` | str or null | winning design id, null if none survives |
| `verdicts.pc1_vs_equal.he_diff`, `.ci`, `.adopted` | float, [lo, hi], bool | the Q2 rule |
| `deviations` | list of {utc, what} | every post-freeze change |

`<variable>` ∈ {temperature, rain}. `<MKT>` ∈ {NYC, EWR, TTN, MDW, MIA}. `<DESIGN>` ∈ {D0, G1-P, G1-N, G1-P*, G1-N*, C1-N, R-A, R-P, R-N, R-A-PC, R-N-PC, P-A, P-A-IDW}.
