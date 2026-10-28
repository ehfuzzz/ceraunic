# ins2 V1 — does a NOAA grid-cell settlement plus a station ladder close the geography basis?

Pre-registered 2026-09-30 05:58Z in reports/S4-RESULTS.md ("Pre-registered: ins2 V1"). Rule unchanged. Worker run 2026-09-30, worktree `ins2`, nothing committed.
Data manifest: DATA.md. Code: scripts/ins2/{extract,analyze,revision}.py. Raw outputs: results.json/.txt.

## Verdict: FAIL on both legs, by a wide margin, and test 3 is unavailable

- Leg A (per-cell HE ≥ own-station HE − 0.1 for ≥ 70 % of cells): **0 of 1,206 cells** (needs ≥ 844). Best single cell in each station is 0.24–0.41 below its own station.
- Leg B (pooled/individual variance ratio < 0.5): ratios **120–226**, i.e. 0.74–0.82 of the number of cells. The rule is not close.
- Test 3 (prelim-vs-final revision): **unavailable** (see below).

## Per-station table (calendar days 2026-07-23..09-25 that exist in both ins1 and the grid; EWR/TTN start 08-26)

| station | days | cells | HE station | median cell HE | share of cells within 0.1 of station HE | variance ratio (pooled / Σ individual) [95 % day-bootstrap] | revision share |
|---|---|---|---|---|---|---|---|
| NYC Central Park | 65 | 240 | 0.935 | 0.568 | 0 % | 184 [167, 197] | unavailable |
| Newark EWR | 31 | 259 | 0.957 | 0.453 | 0 % | 211 [191, 226] | unavailable |
| Trenton TTN | 31 | 307 | 0.913 | 0.534 | 0 % | 226 [185, 252] | unavailable |
| Chicago Midway (Kalshi's Chicago station) | 65 | 239 | 0.947 | 0.438 | 0 % | 190 [166, 207] | unavailable |
| Miami MIA | 65 | 161 | 0.889 | 0.204 | 0 % | 120 [105, 129] | unavailable |
| all five, cell-weighted | | 1,206 | | | 0 % | 127 (31 days with all five ladders; discs of NYC and EWR overlap) | |

Supplementary numbers (not part of the rule): 90th-percentile cell HE 0.62 / 0.64 / 0.59 / 0.50 / 0.33 (NYC/EWR/TTN/MDW/MIA); best cell HE 0.68 / 0.71 / 0.63 / 0.54 / 0.48; share of cells within 0.3 of the station HE 5 % / 5 % / 2 % / 0 % / 0 %; the cell nearest the station (0.7–2.5 km) has HE 0.60 / 0.71 / 0.53 / 0.54 / 0.37; median cell HE after an in-sample offset/ratio fit 0.58 / 0.66 / 0.57 / 0.49 / 0.46; mean pairwise correlation of cell−station residuals 0.77 / 0.83 / 0.74 / 0.80 / 0.76; RMS residual 1.1–1.9 payout units per $1/F (per day).

## How the tests were run (choices made before the first number was produced)

- Exposure at a cell = min(max(T_cell − K, 0), 6) $ per $1/F unit, T_cell = nClimGrid tmax converted to °F and rounded to an integer; K, the station-ladder payout (`ladder_pay`, binned Kalshi payout) and the station ASOS exposure `H_nws` are the ins1 values from reports/ins1/rows.json. HE = 1 − var(exposure − ladder payout)/var(exposure); own-station HE uses `H_nws` on the same days as the cells. Unrounded cell temperatures give the same 0 % share.
- Test 2 residual = H(cell) − H(station ASOS), summed over all cells each day; ratio = var(daily sum)/Σ var(cell). Using H(cell) − ladder payout instead gives 125–236, the same.
- Cells: every nClimGrid cell centre within 40 km (great circle) of the station coordinates with data on all days (ocean cells are masked: 161 of 259 around Miami, 239 of 316 around Midway). Each cell is compared with its own station's ladder; discs of NYC and EWR overlap.

## Deviations and things you would otherwise trip over

1. **Chicago uses Midway, not O'Hare.** The brief lists ORD; ins1 found Kalshi Chicago settles at Midway (CLIMDW). ORD is inside the 40 km disc.
2. **Day alignment.** Each nClimGrid-Daily value is documented as "the 24-hour period ending in the early morning of the specified day". Comparing the nearest cell with ASOS calendar-day max: grid label D vs ASOS D gives RMSE 4.6/4.7/4.2/5.2/2.3 °F (NYC/EWR/TTN/MDW/MIA, corr 0.57–0.74); label D vs ASOS D−1 gives 1.7/1.6/1.1/1.6/1.1 °F (corr 0.92–0.98). All results use calendar day D = grid label D+1. The unaligned run (`results_label_day_unshifted.*`) is worse (median cell HE −0.96 to −0.09) and is kept only as evidence.
3. **Coverage.** The September prelim file stops at label 09-26, so ins1's 09-26, 09-27 and 09-28 city-days (15 of 272) have no grid value; n above is 65/31/31/65/65 (not 68/34/34/68/68).
4. Dataset: nClimGrid-Daily only; PRISM was not downloaded.

## Test 3, prelim vs final: unavailable

NCEI serves exactly one file per month at a time: `-grd-scaled.nc` for closed months (Jul, Aug), `-grd-prelim.nc` for the open month (Sep, 2026-09-01..26). There is no vintage archive, so first-publication vs T+5 days cannot be reconstructed for any ins1 day. I kept the Sep prelim (md5 in DATA.md). `scripts/ins2/revision.py` will download the Sep scaled file when NCEI publishes it (Aug's appeared 6 days after month end, so about 2026-10-06) and report the share of cell-days whose integer $1/F payout bin moves. That number will be prelim(created 09-28, 2 to 27 days old) vs scaled, not first-publication vs T+5, and the code path after the download is untested (only the HTTP 404 branch has run).

## Caveats

- **Interpolation from the same stations.** nClimGrid is built from GHCN-Daily station reports, including the Central Park, EWR, TTN, MDW and MIA ASOS records; cells near a station largely reproduce that station, so the test cannot see true point-to-point geography, only how the interpolation and the observation-day convention differ from the ladder's settlement source. Yet the nearest cell alone (0.7-2.5 km away) has HE 0.37-0.71 against 0.89-0.96 for the station: a large part of the gap is day definition and interpolation noise (nearest-cell RMSE vs ASOS 1.1-1.8 °F even after alignment, coop stations on early-morning observation times), not distance. A settlement source that is not calendar-day aligned with the ladder's is itself a basis the overlay would carry.
- **The variance criterion is nearly unreachable as written.** For N cells with mean residual correlation ρ the ratio is about 1 + (N−1)ρ; < 0.5 needs negative correlation. Residuals around one station share the station's own error (ρ 0.74–0.83), so the ratio sits at 0.74–0.82 × N. Even dividing by N (the pooled book of average residual, not run as a rule) the diversification is at most 26 %. This does not change the verdict; Leg A fails independently.
- **Temperature only.** Rain (V5 in ins1's ins2 note) was not tested. Convective rain is where interpolation error is largest and where a grid may look better or worse than temperature; nothing here speaks to it.
- **Sample.** 65 days for NYC/MDW/MIA, 31 for EWR/TTN, one summer-to-early-autumn stretch with a 6 °F cap on the payout, so many days pay zero. Ratios are bootstrapped by day (2,000 draws) and cells share the same days, so cells are not independent samples; the 0 % share is not sensitive to that (bootstrap upper bound 0–2 %).
- The ladder used for the hedge is the ins1 binned payout, so HE includes binning error (same as the ins1 own-station numbers, which it is compared against).
