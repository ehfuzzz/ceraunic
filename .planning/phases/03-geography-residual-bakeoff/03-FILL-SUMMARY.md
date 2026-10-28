# Phase 3 fill pass (worker, 2026-09-30)

*Note 2026-10-02: this is the record of the 2026-09-30 pass. The "19 of 26" and "+0.094" figures below were right then; the PRISM re-pull changed them (26 of 26, +0.229, G1-P vs R-A +0.112). See `03-REPULL-SUMMARY.md`.*

**Builder (`scripts/build_report.py`), all four 03-SUMMARY bugs fixed:**
- (a) §3 ledger now formats `verdicts.winner.<var>` with `winner`: prints "winner: none survived" / "winner: G1-P".
- (b) `P3PROD_DONE` (§10) rewritten: temperature none survived → station leg alone, C_30 $416k vs $412k two-leg (`@DEP.pooled_station_leg_only.H30.C`, `e45:verdicts.M3.C30`), RFQ on P-A-IDW; rain winner, ΔHE and 19 of 26 pairs from keys, R-A alternate, weekly book not built.
- (c) Placeholder text removed: §6 closing paragraph (pair bases, matched-pair +0.094 [0.027, 0.183] vs R-A, caveats, seat ruling), §7 intro, limitations bullet, §11 coverage row, deviation E1, data note on grids.
- (d) §6 bake-off tables have a `pairs` column (`bakeoff.<var>.<DESIGN>.n_pairs`); caption cites deviation 1.
- `make report`: prose lint "no digit outside a placeholder", 211 traced numbers (was 196), no Phase 3 "n/a"; two builds byte-identical (EVALUATION.md and .html md5). `make test`: 54 passed, 2 skipped.

**Pitch:**
- `scripts/build_decks.py` edited, then re-run (before the edit, its output matched the committed decks byte for byte). E03 was added to the source key list. The note saying lines were pending Phase 3 was replaced. Slide S-D now shows $416k station-only next to $412k two-leg, with an evidence line for each temperature design fail. Slide S-G's Proven column gains 0.81 and the rain pass (19 of 26). Its Not-proven column gains the heat residual fail (+0.061 vs +0.10) and rain basis 0.49 / Miami 0.13, with no hedge and no book yet. S-G evidence lines are keyed to E03.
- DEMO-WALKTHROUGH.md had no pending lines. Added one "if asked" answer at Trade step 5 (heat: no design cleared the bar; rain: passed on 19 of 26, not built), keyed to E03.
- 14-TOKEN-POOL-MEMO.md §8 bullet rewritten (36 → 35 words, main text stays ≤ 2,500) plus footnote `[^e03]` with keys, $416k/$412k, and R-A as pre-Phase-3.
- Banned-word grep (style-guide list) on the four files: 0 hits. "pending Phase 3" grep: 0 hits.

**PROJECT.md:** EVAL-02 and EVAL-03 ticked, one verdict line each.

**Open:**
- The seat's CI [0.79, 0.85] for temperature HE(D0) is a rounding slip. The exact value is [0.7845, 0.8445], so the report, decks and PROJECT.md say [0.78, 0.84].
- Crypto slide 3 and fintech slide 4 still describe the local gap as trading in a daily auction. For heat that is now RFQ. That narrative change is the seat's call, so I didn't touch it.
- Memo §6 still quotes ins2's 0.74-0.83 residual correlation. Phase 3's same-source spread cuts it to 0.13-0.35, which could be added.
- PRISM re-pull after 2026-10-01 15:40Z and re-run is still pending (deviation 1). The deck, memo and report text quoting 19 of 26 will change with it. **Done 2026-10-02**: re-pull and re-run finished, text updated (`03-REPULL-SUMMARY.md`).
