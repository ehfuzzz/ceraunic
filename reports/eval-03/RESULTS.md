# EVAL-02 / EVAL-03 results: geography basis and the residual bake-off

- Rules frozen verbatim in `PREREG.md` at **2026-09-30T15:40:52Z**.
- Data-quality check run at 16:03:13Z (`dq.md`, and tables.md section 1), before any HE was computed.
- First HE run at 16:04Z. The final `results.json` is from `uv run python scripts/eval03.py --all` (about 15 s).
- Re-run 2026-10-02T08:27:30Z, after the PRISM re-pull that resolved deviation 1. Every number below is from that run. What moved, old to new, is in `.planning/phases/03-geography-residual-bakeoff/03-REPULL-SUMMARY.md`.
- Two runs give byte-identical `results.json` apart from `meta.written_utc`.
- Numbers are in `results.json`, every table is in `tables.md`, figures are in `figures/`, and the Phase 7 index spec is in `residual-spec.md`.

**Setup.** The test window is 2025-01-01..2026-08-31: 608 days, or 86 Mon-Sun weeks for rain. Train is 2024. Truth is the held-out ASOS station (leave-one-out): 37 temperature pairs and 26 rain pairs within 50 km. All 63 pairs pass the inclusion rule.

**Units.** One temperature unit pays $1 per °F above a trailing strike, capped at $6 a day. One rain unit pays $1 per inch of weekly total, capped at 3 in.

**Statistics.** HE = 1 − Var(E − H_S − r)/Var(E). ΔHE is measured against the station leg alone on the same days. The CIs come from a joint circular block bootstrap: 14-day blocks (2-week blocks for rain), 2,000 draws, seed 20260930, with the same resampled calendar for every pair and market.

## Verdicts (pre-registered rule vs result)

| question | rule | result | verdict |
|---|---|---|---|
| EVAL-02 temperature | none (descriptive) | pooled median HE(D0) **0.807 [0.785, 0.845]**; by market NYC 0.78, EWR 0.78, TTN 0.87, MDW 0.84, MIA 0.67 | the station leg alone removes about 80 % of local heat-payout variance within 50 km |
| EVAL-02 rain (weekly) | none | **0.491 [0.380, 0.658]**; NYC 0.67, EWR 0.63, TTN 0.47, MDW 0.69, MIA 0.13 | rain basis is large, and in Miami the station tells you little |
| EVAL-03 temperature | P1 ΔHE ≥ +0.10 with CI > 0; P2 ≥ 70 % of pairs and ≥ 4/5 markets; P3 η ≥ 0.5; P4 settleable | best ΔHE: G1-P +0.061 [0.044, 0.075], P-A-IDW +0.052 [0.037, 0.065], R-A +0.033 [0.020, 0.044] | **nothing survives** (all fail P1). C1-N and R-P are KILLED (ΔHE ≤ 0) |
| EVAL-03 rain (weekly) | same, P2 needs ≥ 3/5 markets | G1-P +0.229 [0.119, 0.318], η 0.76; R-A +0.110 [0.055, 0.181], η 0.79 | **G1-P and R-A survive; winner G1-P** (HE 0.808 vs 0.696; paired diff +0.112 [0.032, 0.238]) |
| Q2: PC1 vs equal weights | PC1 adopted only if HE higher by ≥ 0.03 with CI excluding 0 | ASOS temperature −0.055 [−0.080, −0.034]; nClimGrid temperature −0.047 [−0.067, −0.022]; ASOS rain −0.290 [−0.434, −0.119]; nClimGrid rain +0.011 [−0.067, 0.024] | **not adopted anywhere**. Frozen PC1 is worse than equal weights, as the 1/N literature predicts |
| Insurance-grade flag (HE ≥ 0.70, not gating) | | rain G1-P 0.808; temperature D0 already 0.807, best 0.875 | met by the rain winner and by every temperature design except C1-N and the PC1 variants |

Every design now runs on all 37 temperature and all 26 rain pairs. On 2026-09-30, G1-P ran on only 27 and 19, because Phase 1 had kept no PRISM cell at 9 points (deviation 1); the 2026-10-02 re-pull added those cells, and the pairs already evaluated did not move. The 7 added rain pairs are the ones where the station leg does worst, so the pooled numbers shifted: G1-P's ΔHE rose from +0.186 to +0.229, while its HE fell from 0.864 to 0.808 (the station leg alone falls from 0.658 to 0.491 on the same pairs).

The winner did not change, but its margins narrowed. Over R-A, the other survivor, G1-P is ahead by +0.112 HE [0.032, 0.238] (+0.094 [0.027, 0.183] on the old 19 pairs). Over P-A-IDW, which fails P1 but has the next-highest HE, the lead is +0.062 [−0.008, 0.229] (`verdicts.winner_vs_runner_up.rain`), a CI that now includes zero (it was +0.079 [0.011, 0.192] on the old 19). The pre-registered winner rule picks the survivor with the highest HE, so the verdict stands. What we can't say any more is that G1-P beats the best failing design by a clear margin.

`bakeoff_matched_prism_pairs` was built for the 19-pair comparison. With every pair present it now repeats `bakeoff` exactly.

## EVAL-02: the station leg alone, against distance

`figures/eval02_he0_vs_distance.png` (and the report's fig8). For temperature, HE(D0) is mostly 0.70-0.93 across 7-48 km (full range 0.48-0.93), and the distance slope is weak. The worst points are not the farthest ones:
- JFK (0.65 from NYC, 0.48 from EWR): a sea-breeze site.
- North Perry HWO (0.53), Fort Lauderdale Exec FXE (0.61).
- JRB (0.71), even at 9 km.

In the outer ring (50-110 km) the median is 0.71. Rain falls off fast and unevenly: LGA 0.89 at 7.5 km, but FRG 0.12 at 47 km, SMQ 0.05 at 43 km, and every Miami point 0.13-0.34, with FXE at −0.83.

These numbers sit well above ins1's raw 0.1-0.6 for three reasons:
- Every station that could be checked is on CLI or GHCN-D values, which removes IEM's fake basis of about 0.5-1 °F (see data quality).
- The strike trails the recent mean.
- The window is 20 months, not one summer.

The Kalshi-ladder sensitivity shows how much the strike choice matters. With Kalshi's own strike (second-bracket floor, set near the forecast) and the binned ladder as the station leg, HE(D0) falls to 0.36 (NYC), 0.47 (MDW) and 0.27 (MIA). Payouts near the strike are sensitive to a 1-2 °F local difference.

## EVAL-03: what each design does

**Temperature** (tables.md section 3):

| design | HE | ΔHE [CI] | pairs > 0 | markets > 0 | η | sd(r) | verdict |
|---|---|---|---|---|---|---|---|
| D0 station only | 0.807 | 0 | | | | | baseline |
| G1-P PRISM cell spread | 0.875 | +0.061 [0.044, 0.075] | 100 % | 5 | 0.47 | 0.85 | FAILS P1, P3 |
| G1-N nClimGrid cell spread | 0.848 | +0.022 [0.010, 0.031] | 76 % | 4 | 0.40 | 0.65 | FAILS P1, P3 |
| C1-N county average | 0.806 | 0.000 [−0.003, 0.000] | 45 % | 3 | −0.07 | 0.70 | KILLED |
| R-A ASOS metro mean | 0.849 | +0.033 [0.020, 0.044] | 76 % | 5 | 0.498 | 0.66 | FAILS P1, P3 |
| R-P / R-N grid disc mean | 0.838 / 0.830 | −0.001 / +0.001 | 49 / 54 % | 2 / 3 | ≈ 0 | 0.47 / 0.37 | KILLED / FAILS |
| P-A nearest station | 0.842 | +0.010 [0.000, 0.026] | 66 % | 4 | 0.25 | 1.06 | FAILS |
| P-A-IDW 3-station IDW | 0.867 | +0.052 [0.037, 0.065] | 78 % | 5 | 0.66 | 0.79 | FAILS P1 only |

The station leg already carries most of the heat signal within 50 km. Every residual adds at most about 0.05-0.06 of HE.

The regional-factor designs are single contracts per market, so they can only remove the part of the basis that all points share. That shared part is small for heat. R-P and R-N (a grid disc mean minus the cell at S) are about zero. R-A helps a bit, because the ASOS network includes stations that sit where the points are.

The per-business designs (G1-P, P-A-IDW) do best. G1-P's temperature gain is an upper bound: every truth station was a PRISM tmax input on the one station list we kept.

**Rain, weekly** (tables.md section 3):

| design | HE | ΔHE [CI] | pairs > 0 | markets > 0 | η | sd(r) | verdict |
|---|---|---|---|---|---|---|---|
| D0 | 0.491 | 0 | | | | | baseline |
| G1-P | 0.808 | +0.229 [0.119, 0.318] | 96 % | 5 | 0.76 | 0.41 | **SURVIVES, winner** |
| G1-N | 0.647 | +0.091 [0.043, 0.113] | 88 % | 5 | 1.73 | 0.18 | FAILS P1 (by 0.009) |
| C1-N | 0.618 | +0.005 [0.000, 0.034] | 75 % | 4 | 0.72 | 0.16 | FAILS P1 |
| R-A | 0.696 | +0.110 [0.055, 0.181] | 92 % | 5 | 0.79 | 0.28 | **SURVIVES** |
| R-P | 0.635 | +0.073 [0.014, 0.134] | 65 % | 4 | 0.73 | 0.24 | FAILS P1, P2 |
| R-N | 0.537 | +0.029 [0.011, 0.044] | 88 % | 5 | 2.47 | 0.07 | FAILS P1 |
| P-A | 0.614 | +0.001 [0.000, 0.038] | 72 % | 3 | 0.42 | 0.41 | FAILS |
| P-A-IDW | 0.746 | +0.089 [0.034, 0.137] | 85 % | 5 | 0.67 | 0.28 | FAILS P1 |

PRISM's radar-aided daily precipitation, summed over a week, tracks the rain at a nearby airport much better than the settlement gauge does. The weekly residual is also efficient: 76 % of the variance handed to the pool removes business variance.

nClimGrid (station-only, heavily smoothed) has η above 1, so its spread is too small: it points the right way but under-sizes the basis. That is the dry, smooth bias the NCEI guide warns about.

## Does anything beat ins2's per-cell nClimGrid residual, and why

ins2's design is G1-N* here: the cell payout minus the ASOS station payout. In ins2 it failed on every one of 1,206 cells, with cell-residual correlation 0.74-0.83.

On our data G1-N* reproduces that correlation: the mean pairwise residual correlation is 0.70-0.80 for temperature and 0.63-0.94 for rain (`concentration.<var>.<MKT>.G1-N*.mean_pair_corr`). The same-source spread G1-N cuts it to 0.13-0.35 (temperature) and −0.15-0.51 (rain). κ falls from 0.74-0.83 to 0.30-0.44 for temperature. Efficiency doubles: η goes from 0.19 to 0.40. That confirms the mechanism in 03-RESEARCH: the shared term (grid at S minus the ASOS at S) sat in every ins2 residual.

Removing that term is not enough for temperature. G1-N gains only +0.022, and G1-N* +0.038 but with η 0.19, so it hands the pool 1.09 unit-days of residual s.d. for it. Neither passes.

Designs that beat ins2's form:
- Temperature: G1-P (+0.061, η 0.47) and P-A-IDW (+0.052, η 0.66) beat it on both gain and efficiency. None of them reaches the bar.
- Rain: G1-P (+0.229) and R-A (+0.110) beat G1-N* (+0.044, η 0.09) by a wide margin, and both survive.

Two things carry them:
- Aggregation in time: weekly, not daily.
- A better source: PRISM blends radar with CoCoRaHS gauges; nClimGrid uses stations only.

ins2 was daily, temperature-only, used a grid cell as truth, and mixed sources.

## Cross-market point: EWR and TTN via the NYC ladder

EWR's own ladder fits well (HE_cover 0.95, Phase 2) but costs 8.93 per unit-day at 24 h, a 241 % overround. The liquid NYC ladder costs 3.25 per unit-day (2025-26). Hedging an EWR exposure with the NYC station leg alone gives HE 0.762 at EWR:

| via NYC plus | HE at EWR | HE at TTN |
|---|---|---|
| nothing (D0) | 0.762 | 0.789 |
| R-A | 0.837 | 0.831 |
| P-A-IDW | 0.867 | 0.835 |
| G1-P | 0.845 | 0.891 |

A residual loading of about 0.16-0.24 per unit-day at λ = 0.25 on top of 3.25 is still far cheaper than 8.93. You give up about 0.08-0.11 of HE against EWR's own ladder. So, as ins1 and Phase 2 said, a business near Newark or Trenton is better served by NYC plus a residual. None of these residuals meets the pre-registered bar across all pairs, so today that residual would be an RFQ contract.

## Sensitivities (never gating; tables.md section 5)

- **Kalshi-ladder sub-sample** (binned ladder leg, Kalshi's strike; NYC/MDW/MIA, 22 pairs):
  - ΔHE G1-P +0.161, P-A-IDW +0.147, R-A +0.066.
  - With a forecast-centred strike the geography basis is larger, and the residual matters more. P-A-IDW would clear P1 here. This is the strongest argument for an RFQ temperature residual.
- **May-Sep:**
  - Temperature: G1-P +0.089, P-A-IDW +0.065. Still under +0.10.
  - Rain: G1-P +0.357, R-A +0.144.
  - Rain residuals are worth most in the convective season.
- **PRISM grid count 8 only:** temperature G1-P +0.054; rain G1-P +0.213. The winner holds on final grids.
- **Post-hoc, IEM-clean era** (2025-10 to 2026-08, deviation 5):
  - Rain: G1-P +0.150, R-A +0.108.
  - Temperature: G1-P +0.054, R-A +0.032.
  - The rain winner's gain is smaller in the most recent months (+0.150 against +0.229 over the whole window), which are also the provisional-grid months. It stays ahead of R-A there; before the re-pull it did not (+0.102 against +0.108).
- **Network radius:** at 30 km, R-A drops to +0.024 (temperature) and +0.072 (rain). At 70 km: +0.013 (temperature) and +0.115 (rain). The pre-registered 50 km lists are close to the best for temperature.
- **Metro mean excluding S:** R-A goes to +0.029 (temperature) and +0.072 (rain). Including S helps.
- **Unrounded, linear uncapped, fixed monthly strike:** no verdict changes. The linear payout shrinks every ΔHE to ≤ 0.02. Daily highs co-move far more than capped payouts do, so the station leg alone already explains almost all of the linear exposure's variance, and a residual has little left to remove.
- **β fitted on 2024** (upper bound of a sized overlay): temperature best is +0.067 (P-A). Rain G1-P is +0.228. No temperature design reaches +0.10 even sized.
- **Grid disc 15/40 km:** R-P and R-N stay at about 0.
- **CoCoRaHS truth:** not run (Phase 1 did not pull it).

## EVAL-02 extras (descriptive; tables.md section 6)

- **Alignment.** Nearest-cell tmax against the station value, median RMSE, aligned (grid label D+1 = calendar D) vs unaligned:
  - nClimGrid 2.08 vs 7.31 °F. PRISM 1.90 vs 7.44 °F. Miami 1.1-2.1 vs 3.1-4.2 °F.
  - Correlation aligned 0.97-0.997.
  - The D+1 rule in align.py holds for both grids. Which grid is closer to the ASOS calendar day is roughly a tie: PRISM is slightly better at most sites.
- **Station-leg HE at every land cell within 40 km** (ins2 re-run on both grids, aligned, 20-month window):
  - Temperature medians 0.61-0.89 (MIA lowest). Rain 0.39-0.79.
  - ins2's median cell HE of 0.20-0.57 came from one summer, the ladder K rule, and nClimGrid only.
- **PRISM contamination** (the only kept list, 2026-07-15; deviation 2):
  - Every truth station was a PRISM tmax input that day.
  - For precipitation, only NYC, OPF, SMQ and TEB (ASOS or COOP) and CKZ and IGQ (mesonet gauges within 1.5 km) matched.
  - PRISM temperature results at truth points are therefore upper bounds. The rain results are mostly not contaminated by the truth gauge itself.
- **Rain secondary.**
  - Daily wet-day false-negative rate (point wet, hedge pays < 0.5): D0 0.145. R-A cuts it by 56 %, P-A-IDW by 39 %, G1-P by 14 %.
  - Monthly totals: HE 0.68 (D0), 0.85 (G1-P), 0.86 (G1-N), 0.78 (R-A). At monthly aggregation even nClimGrid works.

## Deviations (all logged with UTC time in `deviations.json` and results.json `deviations`)

1. **15:51:37Z**: No PRISM cell was pulled for 9 points (10 temperature pairs, 7 rain pairs). Phase 1 kept only 40 km discs around each S, and PRISM refuses a re-download inside 24 h. G1-P and G1-P* use the remaining pairs. Every design is also reported on the same pairs, and the winner holds there.
   - **Resolved 2026-10-02** (re-run 08:27:30Z): `scripts/phase3_repull.sh` pulled the cell at each of the 9 points (2008 daily PRISM files, each requested once) and re-ran eval03. G1-P and G1-P* now run on all 37 / 26 pairs. Verdicts are unchanged except the details listed in the paragraph under the verdict table and in 03-REPULL-SUMMARY.md. Vintage check: the fresh files matched the Phase 1 disc cache at every disc cell on every day except 2026-09-26 (release 1 then, release 2 now), which is outside the train and test windows.
2. **15:51:37Z**: PRISM contamination is measured on one day, not as a share of test days.
3. **15:51:37Z**: Non-CLI stations are checked against GHCN-D and switched if they fail the 2 % test (03-PLAN instruction; not in the frozen text).
4. **16:03:41Z**: GHCN-D has no 2024 data for HST, WRI and JOT. PC1 inputs with < 50 % train coverage get weight 0, instead of dropping every train day. Decided after the data-quality table and before any HE.
5. **16:03:41Z**: Added one post-hoc descriptive sensitivity (the IEM-clean era).
6. **2026-10-02T09:27:02Z, open**: the Phase 1 disc cache has no PRISM tmax for label 2026-08-01 (CLI day 2026-07-31), so G1-P, G1-P* and R-P drop that one temperature test day. Filling it needs a second download of a file fetched on 2026-10-02, which PRISM's daily limit rules out until 2026-10-03; the command is in `deviations.json`.

**Choices made while implementing (not rule changes):**
- Rounding is half-up. The PREREG says "round".
- The P2 market median is over pairs whose residual is not identically zero. A market where every pair is zero counts as "not > 0".
- For D0, η, sd(r) and L are reported as exact zeros (it hands nothing to the pool), so the report builder does not print n/a.
- Zero-by-construction pairs are computed from geometry. This also zeroes pairs the research list missed: C1-N at CDW (EWR market, Essex County) and at IGQ and 06C (Cook County).
- The optional 2026-01-01 reconstitution was not run.
- The truth and network lists stay exactly as in Q5, even where GHCN-D coverage fell below 90 % after the switch (JOT test coverage 88 %).
- nClimGrid values from prelim files are dropped (the PREREG says scaled files only). This removes calendar day 2026-08-31 from nClimGrid designs.

## Data quality (tables.md section 1; run before any HE)

tmax:
- Every checked station fails the 2 % tmax check.
- Before 2025-10, IEM is 0.4-0.9 °F low on 39-68 % of days. From 2025-10 it differs on 0-9 %.
- So the CLI stations use CLI tmax: NYC, LGA, JFK, EWR, TTN, ISP, MDW, ORD, LOT, PWK, DPA, UGN, MIA, FLL.
- The USW stations use GHCN-D tmax: TEB, CDW, HPN, FRG, SMQ, DYL, PNE, WRI, VAY, JOT, OPF, TMB, HWO, HST, FXE, DJT.

Precipitation:
- Stays on IEM everywhere. Mismatch is 0-1.5 %; TTN is highest at 1.5 %.

Stations left on IEM, unchecked:
- JRB, MMU, GYY, LOM, CKZ, IGQ, 06C (and BLM in the outer ring) have no reference series.

Rain gauges that look weak but pass the rule:
- JRB: 53 paying weeks against 78 at LGA.
- HWO: 25 paying weeks.
- FXE: 44 paying weeks.
- These drive the three worst rain HE(D0) values.

## Caveats

- Truth is airports. Midtown, the Loop and Brickell are only proxied (JRB is the one quasi-interior point, and its gauge is weak). Real businesses may see more basis than this.
- 20 test months. TTN rain has 2 pairs, so it is pooled, not judged alone.
- Central Park runs cool against its neighbours. The R-A residual at NYC points has mean +0.09 to +0.23 per unit-day, so the house would pay on average unless the residual is priced on recent data (Phase 4 finding).
- The rain station leg (weekly total at S) has no liquid Kalshi hedge. Kalshi lists a daily binary and illiquid monthly ladders.
- PRISM's count-2 to count-8 revisions are not measured (no archive). The evaluation used mostly final grids.

## For Phase 4's two-leg capital (it used R-A as a placeholder)

- **Temperature: no residual survives,** so the standard product has no listed residual leg.
  - Phase 4's two-leg C_30 ($412k) against the station leg alone ($416k) shows the residual leg adds little capital.
  - Its "+$1,062/day from the NYC residual" P&L line belongs to an RFQ book, not the listed product.
  - Re-run with (a) station leg only as the listed product, and (b) an RFQ residual book modelled on P-A-IDW. P-A-IDW has a larger per-contract sd (0.79 against 0.66 for R-A) but diversifies more across businesses (κ 0.54-0.78, against 0.83-0.96 for R-A's single contract).
- **Rain:** Phase 4 found rain netting ≈ 0. The listed rain residual is G1-P weekly, one contract per business cell: sd 0.41 per unit-week, κ 0.43-0.67, mean about 0.
  - Phase 4 has no weekly rain leg at all. Adding one, with the station leg carried by the house, is new capital to size.

## What the report now shows

`make report` fills §5-6 of reports/EVALUATION.md with no "n/a" from Phase 3 keys, and fig8 renders. The §3 ledger row now shows temperature winner "n/a" (the `str` format of a null), where §6 correctly says "none survived". The builder issues are listed in 03-SUMMARY.md.
