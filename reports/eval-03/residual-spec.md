# Residual index spec for Phase 7 (from EVAL-03)

Written 2026-09-30 from `reports/eval-03/results.json` (rules frozen 15:40:52Z in PREREG.md); numbers updated 2026-10-02 from the re-run after the PRISM re-pull (deviation 1, resolved). Every number below is a test-window (2025-01-01..2026-08-31) figure from that file. "Unit" means $1 of payout per °F (temperature) or per inch of weekly rain (rain).

## What survived

| variable | listed residual | why |
|---|---|---|
| Rain, weekly totals | **WI-<MKT>-PRISM-RAINW v1** (design G1-P, winner) | Survives P1-P4 on all 26 pairs. Beats the other survivor (R-A) by +0.11 HE [0.03, 0.24]. Its lead over P-A-IDW, which fails P1, is +0.06 [−0.01, 0.23], so not clearly ahead of the best failing design. |
| Rain, weekly totals | WI-<MKT>-METRO-RAINW v1 (design R-A, alternate) | Also survives P1-P4. One contract per market and no grid revision risk. Use it if the PRISM count-2 revisions turn out large, or if PRISM's terms or download limits rule out oracle use. |
| Temperature, daily | **none** | No design clears P1 (ΔHE ≥ +0.10). Phase 7 ships station-only heat cover, plus bespoke residuals by RFQ at a stated premium (PREREG rule). The RFQ reference formula is P-A-IDW (below). |

## 1. WI-<MKT>-PRISM-RAINW v1 (G1-P, weekly rain)

```
Index      WI-<MKT>-PRISM-RAINW v1, listed <date>
Inputs     PRISM AN91d 4 km daily precipitation (https://services.nacse.org/prism/data/get/us/4km/ppt/YYYYMMDD),
           two cells fixed at listing: c(b), the cell containing the business location, and c(S), the cell
           containing the settlement station. Cell ids for S (results.json `cells.prism_cell`): NYC 40.7917_-73.9583,
           EWR 40.6667_-74.1667, TTN 40.2917_-74.8333, MDW 41.7917_-87.7500, MIA 25.7917_-80.3333.
Week       Calendar Mon-Sun (LST). On PRISM labels that is Tue..Mon (a PRISM day is 12Z-12Z, labelled by its end
           date; docs/CONVENTIONS.md section 3; src/wi/eval03/align.py).
Formula    R_c,w = sum of the 7 daily values (mm) / 25.4, rounded half up to 0.01 in.
           Residual r_w = min(R_c(b),w, 3.00) - min(R_c(S),w, 3.00)   ($ per $1/in unit; can be negative)
           Station leg = min(R_S,w, 3.00), R_S = NWS CLI weekly total at S (0.01 in; trace = 0).
Quorum     All 7 labels present in the snapshot. Otherwise the residual leg voids for that week and the station
           leg still pays.
Timing     Provisional: grid count 1 (about 1 day after the Monday label). Final: the values at grid count 2
           (about 5 days after the Monday label, so within 7 days of the week's end). The oracle downloads once,
           archives the file with its md5 and grid count, and publishes the two cell values.
Revisions  Final at the count-2 snapshot. Later PRISM releases (counts 3-8) are ignored ("conclusively presumed
           accurate", as in RMA's PRF).
Changes    c(b) and c(S) never change during a policy. Cell ids are re-checked each 1 Jan against the PRISM grid
           definition.
Licence    PRISM terms (2026): free reproduction with attribution (PRISM Group, Oregon State University,
           https://prism.oregonstate.edu, access date). Downloads are limited to 2 per file per 24 h, so the
           oracle must fetch each day exactly once.
```

**Evaluation numbers** (`bakeoff.rain.G1-P`, `bakeoff_matched_prism_pairs.rain`):
- Pooled median HE 0.808 [0.734, 0.903] on all 26 pairs. On the same pairs the station leg alone gives 0.491.
- ΔHE +0.229 [0.119, 0.318]. ΔHE > 0 at 96 % of pairs and in all 5 markets.
- η 0.76, β 0.88. sd(r) 0.41 unit-weeks, mean(r) −0.01.
- Loading at λ = 0.25: 0.10 per unit-week (0.04 at λ = 0.10, 0.21 at λ = 0.50). Cost per HE point 0.44.
- Distinct cells among the truth points: NYC 8, EWR 7, TTN 2, MDW 4, MIA 5. In production there is one residual contract per business cell.
- Book concentration κ 0.43-0.67. Mean pairwise residual correlation 0.30-0.59, against 0.47-0.76 for the mixed-source G1-P*.

**Caveats that travel with this spec**
- Until 2026-10-02, 7 of 26 rain pairs had no PRISM cell (HPN, FRG, SMQ×2, PWK, DPA, FXE; deviation 1). The re-pull added them. They are the pairs where the station leg does worst, and G1-P's ΔHE is above the old pooled median at all 7, so the pooled ΔHE rose (+0.186 to +0.229) while the pooled HE fell (0.864 to 0.808). The spec is now evaluated at all 26 truth points, still only within 50 km of the five stations.
- The evaluation used final PRISM values (grid count 8) for 2025-01..about 2026-03, and counts 1-7 after that. Settlement would use count 2. The size of the count-2 to count-8 revision is unknown, because PRISM keeps no old versions. Snapshot counts going forward (Phase 1 open item) and measure it before a mainnet listing.
- The gain is seasonal. May-Sep ΔHE is 0.36; the Oct 2025-Aug 2026 window gives 0.15. The winter weeks and the provisional months are weaker.
- Truth contamination: on the one kept station list (2026-07-15), PRISM's ppt inputs included the gauges at NYC, OPF, SMQ, TEB, CKZ and IGQ, but not most other ASOS gauges. At those points the numbers are an upper bound.
- No liquid Kalshi instrument replicates the weekly station leg. Kalshi has a daily "> 0 in" binary and illiquid monthly ladders (Phase 2). The house carries the station leg or hedges it with daily binaries; this spec covers only the residual.

## 2. WI-<MKT>-METRO-RAINW v1 (R-A, weekly rain; alternate)

```
Index      WI-<MKT>-METRO-RAINW v1, listed <date>
Inputs     NWS CLI daily precipitation for CLI stations in the list; NCEI GHCN-D PRCP (USW id) otherwise.
List       NYC {NYC, LGA, TEB, EWR, JFK, CDW, HPN, FRG}   EWR {EWR, NYC, TEB, CDW, LGA, JFK, SMQ}
           TTN {TTN, VAY, SMQ}   MDW {MDW, ORD, LOT, PWK, DPA}   MIA {MIA, OPF, TMB, HWO, FLL, FXE}
           (the evaluated lists also held JRB, which has no GHCN-D or CLI record; it cannot be a settlement input)
Formula    M_w = equal-weight mean of the Mon-Sun totals of the available inputs, rounded to 0.01 in; published
           with the input count. r_w = min(M_w, 3.00) - min(R_S,w, 3.00).
Quorum     >= 60 % of listed inputs with all 7 days; else use the T+7 GHCN-D snapshot; if still short, the
           residual leg voids.
Timing     Provisional T+1 12:00 local after Sunday; final T+7 snapshot; later QC edits ignored.
Changes    List reviewed each 1 Jan using data final by 1 Dec; never changed during a policy.
```

Evaluation numbers (`bakeoff.rain.R-A`, leave-one-out): pooled median HE 0.696 [0.599, 0.771] on all 26 pairs (0.771 on the 19 pairs that had a PRISM cell before the 2026-10-02 re-pull). ΔHE +0.110 [0.055, 0.181], positive at 92 % of pairs and in 5 of 5 markets. η 0.79, sd(r) 0.28, loading 0.07 per unit-week. One contract per market (κ 0.76-0.97, as expected for a single regional factor). It also cuts the daily wet-day false-negative rate by 56 % against the station leg alone (descriptive).

## 3. Temperature: no listed residual; RFQ reference formula

Nothing survives (`verdicts.winner.temperature` = null). The best designs, for the RFQ desk's pricing:

| design | pairs | pooled median HE | ΔHE [95 % CI] | η | sd(r) per unit-day | L (λ = 0.25) | L as % of the station-leg ask | fails |
|---|---|---|---|---|---|---|---|---|
| G1-P (per-cell PRISM spread) | 37 | 0.875 | +0.061 [0.044, 0.075] | 0.47 | 0.85 | 0.21 | 4.2 % | P1, P3 |
| P-A-IDW (3-station IDW) | 37 | 0.867 | +0.052 [0.037, 0.065] | 0.66 | 0.79 | 0.20 | 3.8 % | P1 only |
| R-A (ASOS metro mean) | 37 | 0.849 | +0.033 [0.020, 0.044] | 0.498 | 0.66 | 0.16 | 3.3 % | P1, P3 (by 0.002) |

The station leg alone gives 0.807 [0.785, 0.845].

RFQ reference: **P-A-IDW**. It is the only design that passes P2, P3 and P4 on all 37 pairs, and its data (CLI / GHCN-D) have no revision risk.

```
Formula    I_t = sum_j w_j T_j,t over the 3 listed stations nearest the business (NWS CLI high, GHCN-D TMAX otherwise),
           w_j proportional to d_j^-2 (km, great circle), fixed at sale; rounded half up to whole F.
           r_t = H(I_t; K_t) - H(T_S,t; K_t), H(T;K) = min(max(T - K, 0), 6), the same K_t as the policy.
Quorum     2 of 3 inputs; weights renormalised over those present; else the residual leg voids that day.
Quote      at least the expected residual plus 0.25 x sd(r); indicatively 0.20 per unit-day (3.8 % of the station-leg ask).
```

G1-P's temperature numbers are an upper bound. On the one kept list (2026-07-15), every truth station was a PRISM tmax input.

Cross-market check (`cross_market`): at EWR, the liquid NYC ladder plus P-A-IDW reaches HE 0.867 (station leg alone 0.762). R-A reaches 0.837. EWR's own thin ladder costs 8.93 per unit-day (241 % overround) against 3.25 for NYC. At TTN via NYC the numbers are 0.835 (P-A-IDW) and 0.831 (R-A), from 0.789.

## 4. What Phase 7's index registry should carry

- `WI-*-PRISM-RAINW` (G1-P): the fields above, plus the cell id pair, PRISM grid count at snapshot, file md5, and fetch time (UTC).
- `WI-*-METRO-RAINW` (R-A): the station list, the weight vector (equal), and the input count published each week.
- Temperature: no residual index is listed. The RFQ desk quotes P-A-IDW-style blends as bespoke contracts, with weights and stations written into each contract.
- Never list the frozen-PC1 variants. They lose to equal weights: HE −0.055 [−0.080, −0.034] (temperature, ASOS) and −0.290 [−0.434, −0.119] (rain, ASOS).
