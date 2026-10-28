# EVAL-02 / EVAL-03 pre-registration (frozen)

**Frozen at: 2026-09-30T15:40:52Z** (UTC, from `date -u`), before any evaluation number was computed.

Source: `.planning/phases/03-geography-residual-bakeoff/03-RESEARCH.md` lines 356-417 (section "Pre-registration Draft"), copied verbatim below; sha256 of those lines (first 16 hex): `99fb9b7c581eef57`. Nothing below the rule was edited. Every later change is logged with a UTC time in `reports/eval-03/deviations.json`, `results.json` (`deviations`) and RESULTS.md.

---

## Pre-registration Draft (03-01 freezes this verbatim with a UTC timestamp before any evaluation number)

**Questions.** EVAL-02: how much variance of a local weather exposure the settlement-station leg alone removes at nearby points. EVAL-03: which residual designs add hedge effectiveness out of sample, at what residual variance and indicative premium, and whether they are settleable.

**Sample.**
- Calendar days (LST) 2024-01-01 to 2026-08-31. **Train** 2024-01-01..2024-12-31 (weights, PCA, fitted-β sensitivity only). **Test** 2025-01-01..2026-08-31 (608 days; about 86 Mon–Sun weeks). Every reported pass/fail metric is test-window.
- nClimGrid: scaled files only. PRISM AN91d 4 km: grid count recorded per day. Primary uses all days; a sensitivity uses grid count 8 days only.
- Kalshi sub-sample: test-window city-days with settled KXHIGH* ladders (ins1 rows plus the Phase 1 extension). Secondary table with the binned ladder payout replacing H(T_S), and the ins1 K rule.

**Stations.** Settlement S ∈ {NYC, EWR, TTN, MDW, MIA}. Truth points, networks and outer rings exactly as in the Q5 tables. Inclusion rule: online IEM ASOS/AWOS within 50 km of S with ≥ 90 % coverage in both windows. Outer-ring points (50–110 km) are reported but not in pass tests.

**Station values.** IEM daily summary `max_tmpf` / `precip` (as in ins1). Before evaluation, at each CLI station compare IEM against CLI on the full window. If they differ on more than 2 % of days (tmax, integer °F) or more than 2 % of days (precip, 0.01 in), that station switches to CLI values. This check produces data-quality numbers only and is run before any HE.

**Exposure and payouts.**
- Temperature: E_b,t = H(T_b,t; K_t) with H(T;K) = min(max(round(T) − K, 0), 6) $ per $1/°F unit. K_t = floor(mean of T_S over t−7..t−1) (point-in-time, settlement station, same for every point and design in the market-day). Station leg = H(T_S,t; K_t).
- Rain (primary): weekly totals R_w (Mon–Sun calendar weeks, inches); E = min(R_b,w, 3.00). Station leg = min(R_S,w, 3.00). Grids: labels Tue–Mon, mm/25.4.
- Rain (secondary): daily wet-day indicator (≥ 0.01 in, same threshold for every source); monthly totals (descriptive).

**Designs** (residual r_b,t in payout units; the business holds station leg + r):

| ID | Design | Residual | Eligible for verdict |
|---|---|---|---|
| D0 | Station only | 0 | baseline |
| G1-P | Per-cell PRISM spread | H(P[c(b)]) − H(P[c(S)]) | yes |
| G1-N | Per-cell nClimGrid spread | H(N[c(b)]) − H(N[c(S)]) | yes |
| G1-P*, G1-N* | Per-cell vs ASOS (ins2 form) | H(G[c(b)]) − H(T_S) | continuity only |
| C1-N | nClimGrid county-average spread (published CSV) | H(N_cty[k(b)]) − H(N_cty[k(S)]) | yes |
| R-A | Regional factor, ASOS network, equal weight, LOO | H(mean_{N∪S∖b} T) − H(T_S) | yes |
| R-P, R-N | Regional factor, grid disc 30 km around S, equal (cos-lat) weight | H(mean_disc G) − H(G[c(S)]) | yes |
| R-A-PC, R-N-PC | Same as R-A / R-N with frozen PC1 weights (train, LOO, clipped, Σw = 1) | as above | exploratory (answers Q2) |
| P-A | Station pair, LOO: nearest of (N∖b) ∪ {S}; r = 0 if S is nearest | H(T_j*) − H(T_S) | yes |
| P-A-IDW | IDW (p = 2) of the 3 nearest in (N∖b) ∪ {S} | H(Σ w T) − H(T_S) | yes |

Grid cells are the cells containing the point. Rain uses the same designs on weekly totals.

**Metrics per (market, point, design), test window.**
1. HE = 1 − Var(E − H_S − r)/Var(E); ΔHE = HE − HE(D0). HE(D0) at each point is the EVAL-02 geography-basis number, also shown against distance.
2. β = Cov(u, r)/Var(r) with u = E − H_S; efficiency η = 2β − 1 (computed only where Var(r) > 0).
3. sd(r) and mean(r) per unit-day (per week for rain).
4. Book concentration per market κ = Var(Σ_b r_b)/(Σ_b sd(r_b))² ∈ (0, 1] (1 = no diversification; the production regional factor is a single contract, so κ = 1). Count of distinct residual contracts per market. ins2 variance ratio kept for continuity.
5. Indicative premium loading L = λ·sd(r), λ = 0.25 (sensitivities 0.10 and 0.50). Also as % of the station-leg 24 h ask premium (Phase 2 values; ins1 fallback NYC 1.73, CHI 3.14, MIA 4.79 per unit-day), and cost per HE point L/max(ΔHE, 0.01). Capital is Phase 4's job.
6. Descriptive (EVAL-02 extras, no pass rule): station-leg HE at every land cell within 40 km for both grids, correctly aligned (ins2 re-run on both grids); nearest-cell tmax RMSE and correlation vs ASOS for both grids, both alignments; PRISM `.stn.csv` contamination share per truth point.

**Inclusion per point.** At least 60 paying days (weeks: 20 non-zero) and Var(E) > 0 in the test window; missing inputs drop that day for that design; network means need ≥ 60 % of members present.

**Inference.** Joint circular block bootstrap: 14-day blocks (2-week blocks for weekly rain), 2,000 draws, seed 20260930, the same resampled calendar for every point and market. The pooled statistic is the median over all (market, point) pairs in the ≤ 50 km truth sets.

**Pass rule, temperature.** An eligible design SURVIVES if all of:
- P1 gain: pooled median ΔHE ≥ +0.10 and the bootstrap 95 % CI lower bound > 0.
- P2 breadth: ΔHE > 0 at ≥ 70 % of pairs, and the market-median ΔHE > 0 in ≥ 4 of 5 markets. Pairs where the design's residual is identically zero by construction (pair design where S is nearest; county design within S's county) are left out of the P2 denominator. They stay in the P1 pooled median at ΔHE = 0, because that is the design's real effect there.
- P3 efficiency: pooled median η ≥ 0.5.
- P4 settleable: a deterministic written formula on published data; no parameter changes after sale; a first settlement value within 7 days; a stated revision policy.
- Insurance-grade flag (reported, not gating): pooled median HE ≥ 0.70 (the ins1 T1 bar).
- KILL: pooled median ΔHE ≤ 0. The design is dropped from Phase 7.

**Pass rule, rain (weekly).** Same P1–P4, but P2 needs ≥ 3 of 5 markets (TTN has 2 rain points). Secondary, not gating: daily wet-day false-negative rate (point wet, index-implied hedge dry), relative change vs D0.

**Winner and ties.** Among survivors, the highest pooled median HE. If within 0.02, prefer fewer distinct contracts per market, then lower L. For Q2: PC1 replaces the equal-weight mean only if its pooled median HE is higher by ≥ 0.03 and the paired bootstrap CI of the difference excludes 0. Otherwise the equal-weight mean is the product formula. If nothing survives, the verdict is "no residual design clears the bar". Phase 7 then ships station-only cover plus RFQ bespoke residuals at a stated premium, and the report gives the best design's numbers anyway.

**Sensitivities (reported, never gating).** Unrounded temperatures; linear uncapped T; fixed monthly strike instead of trailing K; May–Sep only; metro mean excluding S; network radius 30 km and 70 km; grid disc 15 km and 40 km; PRISM grid count 8 only; β fitted on train and applied to test (the upper bound of a sized overlay); Kalshi-ladder sub-sample; CoCoRaHS weekly rain truth if Phase 1 pulls it.

**Deviations.** Any change after the freeze is logged in 03-04 with the reason and UTC time, and the pre-freeze version is also reported.
