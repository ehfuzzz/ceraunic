# Localized weather insurance on Kalshi station ladders: evaluation report

Codename `weather-insurance`. Evidence milestone v0.1 (EVAL-07). Built by `make report` from the phase results files listed in Appendix C; every number in the prose is listed with its source key in Appendix B.

## The short version

- **The station ladders track the exposure.** Bought as a replicating ladder, Kalshi's daily high-temperature contracts in New York, Chicago and Miami pay out in line with a capped heat cover at the settlement station: HE_cover 0.95 [0.95, 0.96] pooled over 4,462 city-days since 2022, and about the same in every year.
- **But at 24 hours they are expensive, and they hedge only the forecast miss.** The 24 h ask already contains tomorrow's forecast. On 2025+ days (a post-hoc pool) the premium-inclusive HE, HE_ladder, is 0.37 [0.33, 0.42]; over all years it is −0.32, worse than doing nothing, because 2023-24 markups were noisy. The pre-registered T1 fails on price: overround 24.6 % against a 20 % bar. Today's market is cheaper (9.7 % on 2025+ days), but that is a post-hoc reading.
- **Netting is modest and rests on priors.** Under the frozen sector priors, 40 % of gross hedge units cancel inside one station-day auction and the M1 test passes with the minimum of 3 stations out of five. If sectors mostly move together, netting falls to 1.9 %. The pre-registered consequence is that the pitch must not lead with netting.
- **Capital leverage holds only with daily forecast repricing.** The pool needs 0.126 of capital per $ of 30-day notional (both legs; 0.25 for the station leg alone), under the 0.35 bar. If the cover is priced before the forecast is known, the station-leg number is 0.36, over the bar.
- **Learning a business's sensitivity failed its bar on public proxies.** Out of sample, the learned hedge took 0.072 (NYC bikeshare) and 0.053 (Chicago bikeshare) of daily revenue-surprise variance, against a 0.20 bar, and about nothing for transit and taxi. At real 24 h asks the NYC bike hedge keeps 0.006. These datasets are stand-ins for retail sales, not retail sales; whether a café's weather sensitivity is learnable and hedgeable is untested.
- **Geography and the residual contract (Phase 3).** At held-out points near the settlement stations, the station leg alone reaches a pooled median HE of 0.81 for temperature (against 0.95 at the station itself). Winning residual design: none survived for temperature, G1-P for rain (§6).


## 1. Question and setup

The brief asks whether a small business can hedge the weather at its own address with Kalshi's liquid station contracts plus a small residual contract, better than doing nothing and cheaper than a bespoke contract. This report pulls together the numbers from the evaluation phases that answer parts of that. Each phase froze its rules (sample, method, pass/fail thresholds) before producing a number and logged every change afterwards. §3 lists all of them.

The policy under test is the ins1 heat cover: it pays $1 for each °F the daily high at the settlement station goes above a strike K, capped at 6 °F. The hedge is the Kalshi daily high-temperature ladder that replicates it, bought at real hourly YES asks with Kalshi's taker fee, 24 h, 12 h or 2 h before the market closes.

Two hedge-effectiveness numbers appear throughout, and they answer different questions:
- **HE_cover** = 1 − var(exposure − ladder payout) / var(exposure). Does the ladder's payout track the loss?
- **HE_ladder** = 1 − var(exposure − (ladder payout − premium − fees)) / var(exposure). After paying the price at the decision time, is the buyer's result steadier than doing nothing?

HE = 1 removes all the variance, 0 removes none, and below 0 adds variance. Brackets after a number are 95 % bootstrap intervals (5-95 % for Phase 5); point estimates decide pass or fail.

| phase | brief item | results | status |
|---|---|---|---|
| Phase 2 | EVAL-01 station hedge quality | reports/eval-01/ | done |
| Phase 3 | EVAL-02 geography basis, EVAL-03 residual bake-off | reports/eval-03/ | done |
| Phase 4 | EVAL-04 netting, EVAL-05 pool economics | reports/eval-04-05/ | done |
| Phase 5 | EVAL-06 learning a business's sensitivity | reports/eval-06/ | done, with seat rulings made after the results |

## 2. Data

All data is free and was pulled keyless and read-only. The full manifest, with URLs, bytes, md5s and pull times, is data/manifests/DATA.md; the day and settlement conventions live only in docs/CONVENTIONS.md.

- **Kalshi markets and hourly candles** (61 weather series in the five cities; 34,495 markets and 1,113,358 candle rows). Phase 2 used every settled daily high ladder for New York (2022-04-27 to 2026-09-28), Chicago/Midway (same span), Miami (from 2023-05-11), and EWR and TTN (from 2026-08-26), plus 1,053 daily rain binaries.
- **Order books.** Kalshi keeps no book archive. The hl-mm recorder's S3 prefix was not readable from this Mac when Phase 2 ran (anonymous access denied, the default profile's session expired), so depth comes from one snapshot: 2026-09-29 (ins1 pull; exact UTC time not stored in the file) for the 2026-09-30 ladders.
- **NWS climate reports (CLI)** for the five settlement stations (6,832 rows, 2023 onward), used as the settlement-grade value where Kalshi's own value is missing; IEM ASOS daily summaries for 26 stations; the IEM AFOS archive of every CLI issuance (10,054 products) for the revision test.
- **GHCN-Daily** station records back to the 1950s for the capital scenarios (the joint five-station history starts in 1959; the two-leg book uses 2000-2025, deviation D3).
- **Census ZIP Business Patterns 2023 and SUSB 2022** for the business population: 1,109,492 small establishments in the priors' sectors, 33,702 population rows.
- **nClimGrid-Daily prelim vintages** from the AWS mirror (50 vintages) for the gridded revision measurement.
- **Sales stand-ins (Phase 5).** Citi Bike (2,562 stations), Divvy (2,494), CTA 'L' (144), Chicago taxi (77 community areas) and NYC TLC taxi (261 zones), daily from 2022-07-01. Raw trips were streamed and aggregated, never stored.
- **Grids for Phase 3** (PRISM 4 km cells, nClimGrid, GHCN-D nearby stations; DATA.md D7-D10). Phase 1 kept 40 km discs around each settlement station and Phase 3 topped up station cells and county averages. Some truth points sat outside those discs and had no PRISM cell (Phase 3 deviation 1); a PRISM re-pull on 2026-10-02 added those cells, so the PRISM designs now run on every pair (§6).

Conventions that matter for reading the numbers: the join key is the NWS climate day (midnight to midnight local standard time); every decision time is computed from each market's own close time, never a constant; the settled value is Kalshi's expiration value, then the CLI; a grid labelled D describes calendar day D−1; and the fee formula (0.07 × C × P × (1 − P) per order, rounded up to the cent) is medium confidence because Kalshi's fee PDF could not be fetched.

## 3. Pre-registration ledger

Every test below was written down before the phase produced a number. The verdict column is read from the phase's results.json, not typed by hand. Fails are listed with the passes.

| phase / req | test | rule (frozen) | frozen (UTC) | result | verdict |
|---|---|---|---|---|---|
| 2 / EVAL-01 | T1 | liquid ladders, rule A, 24 h, pooled: HE_cover ≥ 0.85 and overround ≤ 20 % | 2026-09-30T13:22:08Z | HE_cover 0.95, overround 24.6 % | FAIL |
| 2 / EVAL-01 | T1b | HE_ladder reported, no threshold (expected about 0.5) | 2026-09-30T13:22:08Z | −0.32 pooled | below expectation (no bar) |
| 2 / EVAL-01 | T2 | thin ladders fail if 24 h overround > 100 % | 2026-09-30T13:22:08Z | EWR 241 %, TTN 266 % | FAIL (both) |
| 2 / EVAL-01 | T3 | daily rain binary: Brier(clim) − Brier(mid) ≥ 0.02 at 24 h | 2026-09-30T13:22:08Z | gain 0.141 | PASS |
| 2 / EVAL-01 | T4 | liquid ladders: 24 h no-offer share ≤ 10 % in every city-year from 2024 | 2026-09-30T13:22:08Z | worst MIA 2024 13.7 % | FAIL |
| 2 / EVAL-01 | check | ins1 reproduction within 5 % (premium, payout) | 2026-09-30T13:22:08Z | premium −0.1 %, payout 1.2 % | PASS |
| 4 / EVAL-04 | M1 | netting ratio ≥ 0.25 at ≥ 3 of 5 stations | 2026-09-30T13:26:00Z | 3 of 5 | MATERIAL |
| 4 / EVAL-04 | M2 | null netting < 0.10 → pitch must not lead with netting | 2026-09-30T13:26:00Z | null pooled 0.019 | the pitch must not lead with netting |
| 4 / EVAL-05 | M3 | C_30 / 30-day pool notional ≤ 0.35 | 2026-09-30T13:26:00Z | 0.126 | LEVERAGE STORY HOLDS |
| 4 / EVAL-05 | M4 | CLI payout-moving revisions ≤ 2 % of units | 2026-09-30T13:26:00Z | 0.0 % | ACCEPTABLE |
| 4 / EVAL-05 | M5 | Kupiec two-sided on 1-day VaR99 not rejected at 5 % | 2026-09-30T13:26:00Z | 1 exceedance in 599 days, p = 0.011 | REJECTED (too few exceedances (conservative)) |
| 5 / EVAL-06 | T1 | group mu_heat and mu_wet nonzero at 95 % (G1, G2); fail = stop | 2026-09-30T13:22:04Z | G1 mu_heat CI [−0.0001, 0.0006]; G2 both nonzero | G1 FAIL, G2 PASS (G1 stop overruled post hoc, see rulings) |
| 5 / EVAL-06 | T2 | A3 median HE_cover heat+rain ≥ 0.20, LB > 0, ≥ 70 % units > 0 (G1, G2) | 2026-09-30T13:22:04Z | G1 0.072, G2 0.053 | G1 FAIL, G2 FAIL |
| 5 / EVAL-06 | T3 | A3 median HE_ladder > 0 with LB > 0 and cost ≤ 25 % of payout | 2026-09-30T13:22:04Z | G1 0.006 (cost 32 %); G2 0.001 | G1 FAIL, G2 FAIL |
| 5 / EVAL-06 | T4 | A3 − A1 ≥ 0.02 with LB > 0 at n = 60-180, fewer negative units; no harm at 365 | 2026-09-30T13:22:04Z | G1 at n = 180: 0.016 | G1 FAIL, G2 FAIL, G3 FAIL, G4 FAIL, G5 FAIL |
| 5 / EVAL-06 | T5 | days of history n* (descriptive) | 2026-09-30T13:22:04Z | G1 own 120 / EB 30; G2 own 60 / EB 30; G3-G5 none | descriptive |
| 5 / EVAL-06 | P1 | placebo: mu insignificant and median HE_cover ≤ 0.02; fail invalidates T2-T5 | 2026-09-30T13:22:04Z | HE ≤ 0.02 in every group; DL mu 'significant' in every group | G1 FAIL, G2 FAIL, G3 FAIL, G4 FAIL, G5 FAIL (by the letter; passes on the day-block interval adopted post hoc) |
| 3 / EVAL-03 | P1-P4 (temperature) | design survives if gain, breadth, efficiency and settleability all pass | 2026-09-30T15:40:52Z | winner: none survived | see §6 |
| 3 / EVAL-03 | P1-P4 (rain) | design survives if gain, breadth, efficiency and settleability all pass | 2026-09-30T15:40:52Z | winner: G1-P | see §6 |

*Source: verdict keys `verdicts.*` in reports/eval-01, eval-04-05 and eval-06 results.json; rule text quoted from each PREREG.md; freeze times from each results.json meta*

### Deviations, with timestamps

Changes made after a freeze, in the order the phases logged them. "After numbers" means the change was made after the phase had seen at least one result. The seat's rulings on Phase 5 were made after the results and are reported as post hoc.

| phase | id | time (UTC; 2026-09-30 unless dated) | relative to numbers | what changed | effect |
|---|---|---|---|---|---|
| Phase 2 (eval-01) | 1 | 13:31Z | after the first run (13:29Z) | Settled value filled from the NWS CLI high where Kalshi's expiration_value is empty and the CLI lies in the settled bracket (2025-10 to 2026-01, NWS era). | none: strict frozen sample gives the same T1 and T4 verdicts |
| Phase 2 (eval-01) | 2 | 13:28Z | before the first run | Ladder validity check added (brackets disjoint and contiguous); a few legacy 2022 events excluded. | none |
| Phase 2 (eval-01) | 3 | 13:28Z | before the first run | Rain Brier sample clarified: all quoted markets; cost and HE on executable markets only. | none |
| Phase 2 (eval-01) | 4 | 13:30Z | pre-registered conditional | Trace days settle YES in more than half the cases, so wet = precip > 0 including trace. | as registered; the rain cover later dropped trace as wet (§4, §11) |
| Phase 2 (eval-01) | 5 | 13:25Z | before the first run | KXRAINNY excluded (settles on the Hudson River Pier 26 gauge). | none |
| Phase 2 (eval-01) | 6 | 13:34Z | after numbers | Post-hoc descriptive pool 'liquid 2025+' added to the tables. | not a verdict; this report labels it post hoc everywhere |
| Phase 2 (eval-01) | 7 | (caveat) | no change | Rule-B strike uses day t−1's final CLI high, which at the 24 h decision exists only as the preliminary. | none (sets the strike, not a price) |
| Phase 4 (eval-04-05) | D1 | 13:26Z | in PREREG | Hedge-day sample rule written in place of Phase 2's (not frozen then); six-rung ladders start in 2023. | none |
| Phase 4 (eval-04-05) | D2 | 13:33Z | before any netting number | Suppressed ZBP cells spread by the national size distribution (the research rule put most establishments in the 50+ classes). | population changes; rules unchanged |
| Phase 4 (eval-04-05) | D3 | 13:35Z | during the run | TTN filled from PNE before 1998; joint history from 1959; two-leg capital uses 2000-2025 only. | defines the capital sample |
| Phase 4 (eval-04-05) | D4 | 13:40Z | during the run | EWR/TTN May-Aug book by ratio; house co-ES on the absorb-all book. | none stated |
| Phase 4 (eval-04-05) | D5 | 13:41Z | seat request after Phase 2 | Climatology-priced capital sensitivity added. | not in M3; station-leg CPC 0.36 under it (§7) |
| Phase 4 (eval-04-05) | D6 | 13:43-13:44Z | after seeing the NYC residual markout | Two residual fair-value sensitivities (ladder-conditional, trailing 5 years). | primary rule kept |
| Phase 4 (eval-04-05) | D7 | 13:46Z | during the run | nClimGrid prelim-vs-scaled measured once plan 01-04 wrote vintages. | descriptive; M4 is CLI only |
| Phase 5 (eval-06) | 1 | ~13:25Z | before numbers | Chicago snow control from O'Hare (KMDW has no snowfall). | none |
| Phase 5 (eval-06) | 2 | ~13:25Z | before numbers | Midway climatology uses the years it has (record starts 1997). | none |
| Phase 5 (eval-06) | 3 | 13:43Z | before any G2 number | Divvy units keyed by station name (ids recoded in 2025). | none |
| Phase 5 (eval-06) | 4 | 13:44Z | before any G1 number | Citi Bike station-id normalisation. | none |
| Phase 5 (eval-06) | 5 | 13:47Z | after trial runs for G3 and G5 | Missing precipitation dropped instead of coded dry. | at most a few days; no direction |
| Phase 5 (eval-06) | 6 | ~13:40Z | mid-run | Ladder shim delegates to Phase 2's ladder.py / fees.py; keeps 6 h staleness and sell-side no-bid rules. | none |
| Phase 5 (eval-06) | 7 | build time | before numbers | Closed-form EB and HAC in numpy (checked against statsmodels). | none |
| Phase 5 (eval-06) | 8 | ~13:34Z | after a G3 trial number | Supplementary joint day-block bootstrap interval for mu. | adopted post hoc as the primary interval by the seat (see rulings) |
| Phase 5 (eval-06) | trial | 13:33-13:47Z | before the final run | 100-200-draw trial runs for G3, G5, G1. | no threshold, sample, arm or metric changed |
| Phase 5 (eval-06) | 9 | 14:03Z | after the first full run | Two CHI ladders on 2024-02-28: use the one quoted at the decision time. | one winter day, no heat payout |
| Phase 5 (eval-06) | 10 | 13:46Z | implementation | Portal history length uses the calendar span. | none |
| Seat rulings on Phase 5 (05-SEAT-RULINGS.md) | R1 | 15:20Z | post hoc (seat) | Day-block bootstrap adopted as the primary interval for every mu; DL interval kept as the pre-registered one. P1 passes on it. | P1 read as pass; reported both ways |
| Seat rulings on Phase 5 (05-SEAT-RULINGS.md) | R2 | 15:20Z | post hoc (seat) | Pre-registered 'stop' on G1's T1 fail overruled: the join is sound, the instrument cannot fit Citi Bike's shape. G1 results stand, flagged. | G1 results reported, flagged |
| Seat rulings on Phase 5 (05-SEAT-RULINGS.md) | R3 | 15:20Z | post hoc (seat) | priors.json keeps the registered T4 rule (own OLS after n*); always-shrink is a candidate for the next pre-registration. | none |
| Seat rulings on Phase 5 (05-SEAT-RULINGS.md) | R4 | 15:20Z | post hoc (seat) | Portal elasticity advisory only; decks may not claim a learned hedge beats doing nothing. | follows PREREG §10 |
| Phase 6 (this report) | E1 | 14:16Z (machine clock) | report assembly | Phase 3 had not landed at first assembly; §5-6 were templates. They filled from reports/eval-03/results.json on the rebuild after Phase 3 landed (results written 16:14Z). | none; EVAL-02/03 now covered |
| Phase 6 (this report) | E4 | 14:25Z (machine clock) | report assembly | Clock note: this Mac read 14:16-14:25Z while the report was built, but 05-SEAT-RULINGS.md and STATE.md carry times up to 15:25Z. One of the two clocks is about an hour off; the phase freeze and write times in the results files are internally consistent (freeze before results in every phase). | none on verdicts |
| Phase 6 (this report) | E2 | 14:16Z | report assembly | PROJECT.md has no separate 'Evaluation' paragraph; the checklist used is the EVAL-01..07 requirement lines plus the Core Value sentence. | none |
| Phase 6 (this report) | E3 | 14:16Z | report assembly | pandoc is not installed on this Mac, so the export is HTML, not PDF. | none |
| Phase 3 (eval-03) |  | 2026-09-30T15:51:37Z |  | G1-P and G1-P* (PRISM per-cell) cannot be computed at HPN, FRG (NYC), SMQ (EWR, TTN), LOM, CKZ (TTN), PWK, DPA, JOT (MDW) and FXE (MIA) for temperature, nor at HPN, FRG, SMQ, PWK, DPA, FXE for rain: Phase 1 kept only 40 km PRISM discs around each settlement station, and PRISM refuses a second download of the same file inside 24 h (the whole archive was pulled 2026-09-30 13:20-15:36Z). Those pairs are left out of the G1-P/G1-P* pooled statistics, and G1-N is also reported on the same reduced pair set so the two grids compare like for like. Pre-freeze version: every pair. Fill: re-pull PRISM after 2026-10-01 15:40Z with a wider disc and re-run. | RESOLVED 2026-10-02: The original text above is kept as logged. On 2026-10-02 (06:21-08:27Z) scripts/phase3_repull.sh pulled the PRISM cell containing each of the 9 points (reports/eval-03/repull_points.json; 2008 daily files, 2024-01-01..2026-09-30, each requested once; cells kept in data/cache/prism_days_extra) and re-ran eval03.py --all. G1-P and G1-P* now run on all 37 temperature and all 26 rain pairs (were 27 and 19), so bakeoff_matched_prism_pairs now holds the full pair set. The 46 G1-P / G1-P* pairs already evaluated (27 temperature, 19 rain) did not move (their per-pair values are identical); only the new pairs were added. What changed: rain G1-P pooled median dHE +0.186 [0.085, 0.274] -> +0.229 [0.119, 0.318], HE 0.864 -> 0.808; rain winner unchanged (G1-P), survivors unchanged (G1-P, R-A); G1-P vs R-A HE diff +0.168 [0.082, 0.259] -> +0.112 [0.032, 0.238]; G1-P vs the runner-up P-A-IDW +0.119 [0.045, 0.251] -> +0.062 [-0.008, 0.229] (CI now includes 0); rain G1-P* P1 False -> True (still fails P3, continuity only); temperature G1-P dHE +0.061 unchanged (CI [0.044, 0.075]), still fails P1 and P3, nothing survives; temperature runner-up G1-P -> P-A-IDW (G1-P now has the highest HE, 0.875). Vintage check: the fresh files matched the Phase 1 disc cache at every disc cell on every day except 2026-09-26 (tmax and ppt; Phase 1 had release 1, the re-pull got release 2), which is outside the train and test windows. Full table: var/phase3-repull/changes.tsv; write-up: .planning/phases/03-geography-residual-bakeoff/03-REPULL-SUMMARY.md. |
| Phase 3 (eval-03) |  | 2026-09-30T15:51:37Z |  | PRISM .stn.csv contamination is measured on the single station list Phase 1 kept (2026-07-15, tmax and ppt), not as a share of test days; the other daily lists were discarded with the grid zips and cannot be re-downloaded inside 24 h. |  |
| Phase 3 (eval-03) |  | 2026-09-30T15:51:37Z |  | Station-value rule extended per 03-PLAN: at a non-CLI station with a GHCN-D USW record, IEM is compared with GHCN-D and replaced by GHCN-D if they differ on more than 2 % of days (same thresholds as the CLI check). Stations with neither (JRB, MMU, GYY, LOM, CKZ, IGQ, 06C; BLM in the outer ring) stay on IEM, unchecked. |  |
| Phase 3 (eval-03) |  | 2026-09-30T16:03:41Z |  | Data-quality result (before any HE): every checked station fails the 2 % tmax check (IEM 0.4-0.9 F low on 39-68 % of days before 2025-10, 0-9 % after), so all CLI stations use CLI tmax and all non-CLI stations with a USW record use GHCN-D tmax; precip stays on IEM everywhere (0-1.5 % mismatch). The GHCN-D records for HST, WRI and JOT are empty in 2024 (train coverage 0 %), so these three have no train data. Frozen PC1 fits therefore give zero weight to any input with less than 50 % train coverage (HST in the MIA network, WRI in the TTN network) instead of dropping every train day. Decided before any HE was computed. |  |
| Phase 3 (eval-03) |  | 2026-09-30T16:03:41Z |  | Added one post-hoc descriptive sensitivity, never gating: test window restricted to 2025-10-01..2026-08-31, the period in which IEM equals the CLI (CONVENTIONS section 8). Reason: seven stations have neither CLI nor GHCN-D (JRB, MMU, GYY, LOM, CKZ, IGQ, 06C) and stay on IEM, which is biased low before 2025-10 at every station where it could be checked. |  |
| Phase 3 (eval-03) |  | 2026-10-02T09:27:02Z |  | Data gap, not yet filled: the Phase 1 PRISM disc cache has no tmax file for label 2026-08-01 (CLI day 2026-07-31), so every design that uses the PRISM cell at S (G1-P, G1-P*, R-P) drops that one test day for temperature. The 2026-10-02 re-pull fetched that file for the 9 extra cells only; filling the discs needs one more download of the same file, and PRISM allows at most 2 downloads of a file per Pacific-time day and threatens IP blocks, so it was left for 2026-10-03. Fill: after 2026-10-03T08:33Z (PRISM's Pacific-day reset is 07:00Z, but the puller's own 24 h gate holds this file until 08:24:38Z; `pull_grids.py prism --dry-run` shows the plan without network) run `uv run python scripts/pull_grids.py prism` once, then `uv run python scripts/eval03.py --all`, and compare results.json before and after (the same pull also fetches ppt and tmax 2026-09-30, outside the windows). (logged after the last eval03 run) | OPEN |

*Source: deviation logs in reports/eval-01/PREREG.md, reports/eval-04-05/RESULTS.md, reports/eval-06/RESULTS.md, .planning/phases/05-elasticity-learning/05-SEAT-RULINGS.md; condensed wording*


## 4. Station hedge quality (EVAL-01)

**The payout works.** Across all years and all three liquid cities, the replicating ladder's payout tracks the capped heat cover at the settlement station with HE_cover 0.95. Binning (the ladder pays in 2 °F steps, the cover is linear) costs little: RMSE 0.42 per unit. The settled value matches the NWS climate report on all but 0.2 % of 3,822 city-days since 2023.

| ladder | city-days | executable | premium | payout | overround | fee | HE_cover | HE_ladder |
|---|---|---|---|---|---|---|---|---|
| liquid NY+CHI+MIA | 4,462 | 3,966 | 4.73 [4.51, 4.94] | 3.79 | 24.6 % [21.4 %, 27.9 %] | 0.19 | 0.95 [0.95, 0.96] | −0.32 [−0.47, −0.20] |
| liquid 2025+ (post hoc) | 1,907 | 1,904 | 4.00 [3.84, 4.16] | 3.65 | 9.7 % [7.7 %, 11.7 %] | 0.18 | 0.96 [0.95, 0.96] | 0.37 [0.33, 0.42] |
| NY (Central Park) | 1,612 | 1,435 | 4.07 [3.84, 4.32] | 3.11 | 31.0 % [26.7 %, 35.9 %] | 0.17 | 0.96 [0.95, 0.96] | −0.23 [−0.36, −0.10] |
| CHI (Midway) | 1,615 | 1,444 | 4.56 [4.32, 4.80] | 3.66 | 24.7 % [21.0 %, 28.8 %] | 0.19 | 0.96 [0.95, 0.96] | −0.34 [−0.52, −0.19] |
| MIA | 1,235 | 1,087 | 5.80 [5.60, 5.99] | 4.88 | 19.0 % [15.3 %, 22.9 %] | 0.23 | 0.93 [0.92, 0.94] | −0.59 [−0.97, −0.25] |
| EWR (thin) | 34 | 34 | 8.93 [5.61, 12.23] | 2.62 | 241.2 % [71.2 %, 428.1 %] | 0.19 | 0.95 [0.93, 0.97] | −7.39 [−9.44, −1.27] |
| TTN (thin) | 34 | 33 | 8.87 [5.28, 12.23] | 2.42 | 265.7 % [79.2 %, 511.2 %] | 0.17 | 0.90 [0.77, 0.94] | −13.94 [−20.05, −2.73] |

*Source: reports/eval-01/results.json `temperature.pooled[rule=A,h=24,...]` and `temperature.city[rule=A,h=24,...]`; per $1/°F unit, fees excluded from premium and overround; 95 % 7-day block bootstrap*

**The price is the problem, and it depends on the year.** T1 needed HE_cover ≥ 0.85 and overround ≤ 20 %. It fails on the second half: 24.6 % [21.4 %, 27.9 %] pooled. The pooled number mixes three markets. In 2023-24 the ladders were marked up heavily and often could not be bought at all; from 2025 they are close to fair. The 2025+ pool below was added after seeing the numbers (deviation 6) and is not a verdict.

| city-year | city-days | overround | spread cost / unit | no-offer share | HE_cover | HE_ladder |
|---|---|---|---|---|---|---|
| NY 2022 | 246 | 17.7 % | 0.27 | 6.5 % | 0.89 | 0.31 [0.11, 0.48] |
| NY 2023 | 364 | 44.4 % | 1.25 | 31.0 % | 0.96 | −0.19 [−0.49, 0.14] |
| NY 2024 | 366 | 46.9 % | 1.18 | 12.8 % | 0.95 | −0.16 [−0.50, 0.21] |
| NY 2025 | 365 | 16.4 % | 0.36 | 0.3 % | 0.96 | 0.40 [0.33, 0.47] |
| NY 2026 | 271 | 13.2 % | 0.15 | 0.0 % | 0.97 | 0.36 [0.28, 0.42] |
| CHI 2022 | 248 | 12.0 % | 0.34 | 9.7 % | 0.89 | 0.30 [0.11, 0.49] |
| CHI 2023 | 364 | 41.8 % | 1.38 | 27.7 % | 0.96 | −0.50 [−0.91, −0.17] |
| CHI 2024 | 367 | 34.1 % | 1.15 | 12.3 % | 0.96 | −0.62 [−1.17, 0.03] |
| CHI 2025 | 365 | 14.2 % | 0.43 | 0.3 % | 0.96 | 0.37 [0.30, 0.46] |
| CHI 2026 | 271 | 6.4 % | 0.15 | 0.0 % | 0.95 | 0.49 [0.41, 0.55] |
| MIA 2023 | 234 | 32.9 % | 1.43 | 41.5 % | 0.95 | −0.66 [−2.17, 0.14] |
| MIA 2024 | 366 | 38.8 % | 1.31 | 13.7 % | 0.92 | −1.23 [−2.03, −0.33] |
| MIA 2025 | 365 | 7.1 % | 0.37 | 0.3 % | 0.93 | 0.45 [0.31, 0.53] |
| MIA 2026 | 270 | 2.4 % | 0.16 | 0.0 % | 0.93 | 0.59 [0.48, 0.68] |

*Source: reports/eval-01/results.json `temperature.city_year[rule=A,h=24,city,year]`*

![HE_cover and HE_ladder by city-year, strike rule A, 24 h before close (reports/eval-01/results.json `temperature.city_year`; error bars 95 % block bootstrap).](figures/fig1_he_by_year.png)

*Figure: HE_cover and HE_ladder by city-year, strike rule A, 24 h before close (reports/eval-01/results.json `temperature.city_year`; error bars 95 % block bootstrap).*

![Overround of the replicating ladder at the 24 h ask by city-year (reports/eval-01/results.json `temperature.city_year`); dashed line = the T1 bar.](figures/fig2_overround_by_year.png)

*Figure: Overround of the replicating ladder at the 24 h ask by city-year (reports/eval-01/results.json `temperature.city_year`); dashed line = the T1 bar.*

**Why HE_ladder is so much lower than HE_cover.** Bought 24 h ahead, the ask already knows tomorrow's forecast. A buyer swaps the weather swing for a price swing of about the same size and keeps only the forecast miss. On 2025+ days that leaves HE_ladder 0.37, close to the 0.5 ins1 suggested; pooled over the noisy 2023-24 markups it is −0.32. At 2 h the price already knows the answer, so HE_ladder is 0.01 on 2025+ days. The gap HE_cover − HE_ladder (0.58 on 2025+ days) is the forecast-level risk. On the default path, where the business buys one fixed-price policy and the house hedges daily, the house carries that risk; §7 prices it.

| pool | horizon | premium | overround | fee / unit | spread / unit | total load (with fees) | no-offer | HE_cover | HE_ladder |
|---|---|---|---|---|---|---|---|---|---|
| liquid, all years | 24 h | 4.73 | 24.6 % | 0.195 | 0.69 | 29.7 % | 11.1 % | 0.95 | −0.32 |
| liquid, all years | 12 h | 4.89 | 30.1 % | 0.161 | 0.83 | 34.4 % | 14.1 % | 0.95 | −0.74 |
| liquid, all years | 2 h | 4.10 | 7.5 % | 0.020 | 0.19 | 8.1 % | 13.7 % | 0.95 | −0.13 |
| liquid 2025+ (post hoc) | 24 h | 4.00 | 9.7 % | 0.179 | 0.29 | 14.6 % | 0.2 % | 0.96 | 0.37 |
| liquid 2025+ (post hoc) | 12 h | 4.11 | 12.8 % | 0.149 | 0.36 | 16.9 % | 0.0 % | 0.96 | 0.08 |
| liquid 2025+ (post hoc) | 2 h | 3.82 | 4.8 % | 0.017 | 0.11 | 5.3 % | 0.1 % | 0.96 | 0.01 |
| thin EWR+TTN | 24 h | 8.90 | 252.8 % | 0.183 | 3.72 | 260.1 % | 1.5 % | 0.94 | −9.69 |
| thin EWR+TTN | 12 h | 7.78 | 198.7 % | 0.170 | 3.07 | 205.2 % | 7.4 % | 0.94 | −8.05 |
| thin EWR+TTN | 2 h | 3.04 | 13.4 % | 0.023 | 0.20 | 14.3 % | 10.3 % | 0.93 | −0.01 |

*Source: reports/eval-01/results.json `temperature.pooled[rule=A,h,pool]`*

**Fixed strike.** A policy with a strike set in advance (rule B: the trailing 7-day mean) fits the ladder less well: the high settles outside the ladder's range on 3.1 % of days and the ladder buys nothing at all on 27 % of days. HE_ladder is −0.75 pooled, −0.20 on 2025+ days, because more of the exposure is predictable level that the 24 h price charges for.

| pool | overround | HE_cover | HE_ladder | ladder buys nothing (unspanned days) | tail outside ladder (days) | payout lost to the tail |
|---|---|---|---|---|---|---|
| liquid, all years | 28.1 % | 0.97 | −0.75 | 26.8 % | 3.1 % | 2.6 % |
| liquid 2025+ (post hoc) | 11.0 % | 0.97 | −0.20 | 21.6 % | 2.1 % | 1.6 % |

*Source: reports/eval-01/results.json `temperature.pooled[rule=B,h=24,pool]`*

**Thin ladders.** EWR and TTN (T2) fail as ins1 said: 241 % and 266 % overround at 24 h, on 34 days each. They are only executable near the close. A business near Newark or Trenton should be hedged on the NYC ladder plus a residual (Phase 3).

**Liquidity.** T4 fails on 2024 alone: the worst city-year, MIA 2024, had no offer on at least one needed rung on 13.7 % of days. In 2025 and 2026 it is at most 0.3 %. Depth rests on one book snapshot: at ≤ 3c of slippage the thinnest needed rung caps a policy at 33 units in New York, 54 in Chicago and 55 in Miami, i.e. a few dozen dollars per °F per city-day.

| ladder | K | contracts per unit | thinnest rung (contracts within 3c) | deepest rung | max units at ≤ 3c |
|---|---|---|---|---|---|
| KXHIGHNY-26SEP30 | 72 | 19.5 | 82 | 754 | 33 |
| KXHIGHCHI-26SEP30 | 69 | 19.5 | 129 | 531 | 54 |
| KXHIGHMIA-26SEP30 | 82 | 19.5 | 254 | 647 | 55 |
| KXHIGHLAX-26SEP30 | 78 | 19.5 | 178 | 376 | 38 |

*Source: reports/eval-01/results.json `depth.ladders.<ticker>` (one snapshot, prior/hl-mm-ins/reports/ins1/books.json)*

**Settlement source.** Against the official climate report, the settlement leg is almost exact:

| city | settle source | city-days (2023+) | CLI ≠ settled value | CLI outside settled bracket |
|---|---|---|---|---|
| CHI | NWS | 1,257 | 0.2 % | 0.0 % |
| CHI | TWC | 46 | 0.0 % | 0.0 % |
| EWR | TWC | 34 | 0.0 % | 0.0 % |
| MIA | NWS | 1,109 | 0.2 % | 0.1 % |
| MIA | TWC | 46 | 2.2 % | 2.2 % |
| NY | NWS | 1,250 | 0.1 % | 0.0 % |
| NY | TWC | 46 | 0.0 % | 0.0 % |
| TTN | TWC | 34 | 0.0 % | 0.0 % |
| all | all | 3,822 | 0.2 % | 0.1 % |

*Source: reports/eval-01/results.json `mismatch[city,settle_source]`*

**Rain.** The daily "any rain" binary passes T3 easily: the market's 24 h Brier score is 0.106 against 0.247 for climatology. It costs $1.20 per $1 of payout at the 24 h ask including fees, and for a wet-day exposure HE_cover is 0.83 but HE_ladder only 0.27, the same forecast effect as for heat. Trace days settle YES 62 % of the time, but that is the all-series figure: it pools 91 trace days across every rain series in the sample (1,053 markets, 2021 to 2026), mostly from the older KXRAINNYC series. The KXRAIN series the house hedges with behaved differently. From July to September 2026 it settled all 26 trace days NO, all 94 measurable-rain days YES and all 96 dry days NO, across 216 settled markets in New York, Chicago and Miami (reports/eval-01/trace_kxrain_2026.md). So the rain cover pays on measurable rain only (0.01 in or more) and counts a trace as dry. The cover and the hedge treat a trace the same way. With the rule the product actually uses (trace = dry), HE_wet is 0.76 as HE_cover (primary 0.83) and 0.23 as HE_ladder (primary 0.27) at 24 h, and the Brier gain over climatology is 0.143 (primary 0.141). The market's own Brier score does not use the wet rule and stays at 0.106, so T3 still passes. The primary numbers stay as registered; this is a labelled sensitivity run (reports/eval-01/sensitivity_trace_dry.md). Monthly rain ladders are not usable as insurance yet: at the start of the month most strikes have no offer.

| horizon | markets quoted | Brier (market mid) | Brier (climatology) | gain | cost per $1 payout (with fees) | no-offer | wet-day HE_cover | wet-day HE_ladder |
|---|---|---|---|---|---|---|---|---|
| 24 h | 1,038 | 0.106 | 0.247 | 0.141 [0.128, 0.152] | 1.20 | 10.8 % | 0.83 [0.74, 0.91] | 0.27 [0.19, 0.35] |
| 12 h | 1,051 | 0.065 | 0.248 | 0.182 [0.171, 0.192] | 1.19 | 5.5 % | 0.84 [0.76, 0.92] | 0.19 [0.12, 0.26] |
| 2 h | 1,052 | 0.021 | 0.248 | 0.227 [0.217, 0.236] | 1.13 | 0.8 % | 0.85 [0.77, 0.92] | 0.11 [0.07, 0.15] |

*Source: reports/eval-01/results.json `rain_daily.horizons.<h>`*

| series | time | strikes | no-offer share | median spread ($) | Brier (mid) |
|---|---|---|---|---|---|
| KXRAINNYCM | 1st of month 12:00Z | 199 | 47 % | 0.25 | 0.165 |
| KXRAINNYCM | close − 24 h | 199 | 1 % | 0.01 | 0.011 |
| KXRAINCHIM | 1st of month 12:00Z | 77 | 64 % | 0.08 | 0.136 |
| KXRAINCHIM | close − 24 h | 77 | 0 % | 0.01 | 0.003 |
| KXRAINMIAM | 1st of month 12:00Z | 70 | 49 % | 0.07 | 0.157 |
| KXRAINMIAM | close − 24 h | 70 | 0 % | 0.01 | 0.017 |

*Source: reports/eval-01/results.json `rain_monthly.<series>|<time>`*

![Daily rain binary: Brier score of the market mid vs leave-year-out climatology by horizon (reports/eval-01/results.json `rain_daily.horizons`).](figures/fig3_rain_brier.png)

*Figure: Daily rain binary: Brier score of the market mid vs leave-year-out climatology by horizon (reports/eval-01/results.json `rain_daily.horizons`).*

**Against ins1.** ins1 found HE 0.86-0.94 and overpay up to 17 % on 272 city-days in the 2026 summer and passed T1. The same engine reproduces ins1's New York premium and payout within 1.2 % (check in §3). On the full history the fit holds and the price does not: ins1 looked at the cheapest stretch the market has had. ins1's "overpay" for New York divides by the premium; on the payout basis used here it is 21 %. ins1 counted 5 settlement mismatches in 272 days (1.8 %), but against IEM ASOS, which ran about half a degree low before 2025-10; against the CLI the mismatch is 0.2 %. ins1 put depth at 5-20 units without sizing by rung; the rung-level sizing gives more.

| ladder | ins1: HE / overround (68 or 34 days, 2026) | this report: HE_cover / overround, full history | this report: 2026 only |
|---|---|---|---|
| NYC | 0.94 / 21 % | 0.96 / 31 % | 0.97 / 13 % |
| CHI | 0.94 / 7 % | 0.96 / 25 % | 0.95 / 6 % |
| MIA | 0.86 / 0 % | 0.93 / 19 % | 0.93 / 2 % |
| EWR | 0.96 / 241 % | 0.95 / 241 % | same days as ins1 |
| TTN | 0.90 / 266 % | 0.90 / 266 % | same days as ins1 |

*Source: prior/hl-mm-ins/reports/ins1/README.md (Results table and geography line; 68/34 city-days from 2026-07-24) (ins1 overround recomputed on the payout basis, premium ÷ payout − 1); reports/eval-01/results.json `temperature.city[...]`, `temperature.city_year[...,year=2026]`*


## 5. Geography basis (EVAL-02)

Phase 3 pre-registration frozen 2026-09-30T15:40:52Z; results written 2026-10-02T08:27:30Z.

**Station leg alone at nearby points (D0).** Pooled median HE at held-out truth points within 50 km: temperature 0.81 [0.78, 0.84], rain (weekly) 0.49 [0.38, 0.66]. Compare the station itself in §4 (HE_cover 0.95).

| market | median HE(D0), temperature | median HE(D0), rain weekly |
|---|---|---|
| NYC | 0.78 | 0.67 |
| EWR | 0.78 | 0.63 |
| TTN | 0.87 | 0.47 |
| MDW | 0.84 | 0.69 |
| MIA | 0.67 | 0.13 |

*Source: reports/eval-03/results.json `eval02.<variable>.by_market.<MKT>.median_he0`*

![Geography basis: HE of the station leg at held-out points vs distance (reports/eval-03/results.json `eval02.points`).](figures/fig8_geography.png)

*Figure: Geography basis: HE of the station leg at held-out points vs distance (reports/eval-03/results.json `eval02.points`).*

Prior evidence for comparison (ins1 raw HE at nearby airports, ins2 nearest-cell HE):

| nearby station hedged with the settlement ladder | raw HE (ins1) |
|---|---|
| LGA | 0.21 |
| JFK | 0.13 |
| TTN via EWR | 0.46 |
| EWR via TTN | −0.06 |
| ORD via MDW | 0.64 |
| FLL | 0.08 |
| OPF | 0.46 |

*Source: prior/hl-mm-ins/reports/ins1/README.md (Results table and geography line; 68/34 city-days from 2026-07-24)*

| station | days | cells | HE at the station | median cell HE | nearest-cell HE | nearest cell (km) | residual correlation between cells |
|---|---|---|---|---|---|---|---|
| NYC | 65 | 240 | 0.93 | 0.57 | 0.60 | 1.2 | 0.77 |
| EWR | 31 | 259 | 0.96 | 0.45 | 0.71 | 1.1 | 0.83 |
| TTN | 31 | 307 | 0.91 | 0.53 | 0.53 | 0.7 | 0.74 |
| MDW | 65 | 239 | 0.95 | 0.44 | 0.54 | 2.3 | 0.80 |
| MIA | 65 | 161 | 0.89 | 0.20 | 0.37 | 2.5 | 0.76 |

*Source: prior/hl-mm-ins/reports/ins2/results.json `<station>.*` (nClimGrid, per-cell exposure hedged with the station ladder, 2026-07-23..09-25)*


## 6. Residual designs (EVAL-03)

Phase 3 pre-registration frozen 2026-09-30T15:40:52Z; results written 2026-10-02T08:27:30Z.

**Verdict.** Winner, temperature: none survived. Winner, rain: G1-P. PC1 weights versus equal weights: HE difference −0.055 [−0.080, −0.034], adopted: no.

Temperature, daily:

| design | what | pairs | pooled median HE | ΔHE | ΔHE 95 % CI | pairs ΔHE > 0 | markets ΔHE > 0 | η | sd(r) | loading L (λ = 0.25) | settleable | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D0 | station only (baseline) | 37 | 0.81 | 0.000 | [0.000, 0.000] | 0 % | 0 | 0.00 | 0.00 | 0.00 | yes | baseline |
| G1-P | per-cell PRISM spread | 37 | 0.87 | 0.061 | [0.044, 0.075] | 100 % | 5 | 0.47 | 0.85 | 0.21 | yes | FAILS |
| G1-N | per-cell nClimGrid spread | 37 | 0.85 | 0.022 | [0.010, 0.031] | 76 % | 4 | 0.40 | 0.65 | 0.16 | yes | FAILS |
| G1-P* | per-cell PRISM vs ASOS (ins2 form, continuity) | 37 | 0.90 | 0.088 | [0.066, 0.120] | 97 % | 5 | 0.45 | 1.09 | 0.27 | yes | continuity |
| G1-N* | per-cell nClimGrid vs ASOS (continuity) | 37 | 0.86 | 0.038 | [0.010, 0.064] | 68 % | 4 | 0.19 | 1.09 | 0.27 | yes | continuity |
| C1-N | nClimGrid county-average spread | 37 | 0.81 | 0.000 | [−0.003, 0.000] | 45 % | 3 | −0.07 | 0.70 | 0.17 | yes | KILLED |
| R-A | regional factor, ASOS network, equal weight | 37 | 0.85 | 0.033 | [0.020, 0.044] | 76 % | 5 | 0.50 | 0.66 | 0.16 | yes | FAILS |
| R-P | regional factor, PRISM disc | 37 | 0.84 | −0.001 | [−0.007, 0.009] | 49 % | 2 | −0.02 | 0.47 | 0.12 | yes | KILLED |
| R-N | regional factor, nClimGrid disc | 37 | 0.83 | 0.001 | [−0.004, 0.007] | 54 % | 3 | 0.02 | 0.37 | 0.09 | yes | FAILS |
| R-A-PC | R-A with frozen PC1 weights (exploratory) | 37 | 0.79 | −0.025 | [−0.035, −0.002] | 38 % | 1 | −0.19 | 0.91 | 0.23 | yes | exploratory |
| R-N-PC | R-N with frozen PC1 weights (exploratory) | 37 | 0.78 | −0.048 | [−0.062, −0.030] | 24 % | 1 | −0.84 | 0.64 | 0.16 | yes | exploratory |
| P-A | nearest station pair | 37 | 0.84 | 0.010 | [0.000, 0.026] | 66 % | 4 | 0.25 | 1.06 | 0.26 | yes | FAILS |
| P-A-IDW | IDW of 3 nearest stations | 37 | 0.87 | 0.052 | [0.037, 0.065] | 78 % | 5 | 0.66 | 0.79 | 0.20 | yes | FAILS |

*Source: reports/eval-03/results.json `bakeoff.temperature.<DESIGN>` (pairs = `.n_pairs`; G1-P has a PRISM cell at every point since the 2026-10-02 re-pull, Phase 3 deviation 1, resolved)*

Rain, weekly totals:

| design | what | pairs | pooled median HE | ΔHE | ΔHE 95 % CI | pairs ΔHE > 0 | markets ΔHE > 0 | η | sd(r) | loading L (λ = 0.25) | settleable | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D0 | station only (baseline) | 26 | 0.49 | 0.000 | [0.000, 0.000] | 0 % | 0 | 0.00 | 0.00 | 0.00 | yes | baseline |
| G1-P | per-cell PRISM spread | 26 | 0.81 | 0.229 | [0.119, 0.318] | 96 % | 5 | 0.76 | 0.41 | 0.10 | yes | SURVIVES |
| G1-N | per-cell nClimGrid spread | 26 | 0.65 | 0.091 | [0.043, 0.113] | 88 % | 5 | 1.73 | 0.18 | 0.05 | yes | FAILS |
| G1-P* | per-cell PRISM vs ASOS (ins2 form, continuity) | 26 | 0.74 | 0.176 | [0.041, 0.297] | 81 % | 5 | 0.34 | 0.51 | 0.13 | yes | continuity |
| G1-N* | per-cell nClimGrid vs ASOS (continuity) | 26 | 0.62 | 0.044 | [−0.041, 0.204] | 62 % | 4 | 0.09 | 0.48 | 0.12 | yes | continuity |
| C1-N | nClimGrid county-average spread | 26 | 0.62 | 0.005 | [0.000, 0.034] | 75 % | 4 | 0.72 | 0.16 | 0.04 | yes | FAILS |
| R-A | regional factor, ASOS network, equal weight | 26 | 0.70 | 0.110 | [0.055, 0.181] | 92 % | 5 | 0.79 | 0.28 | 0.07 | yes | SURVIVES |
| R-P | regional factor, PRISM disc | 26 | 0.63 | 0.073 | [0.014, 0.134] | 65 % | 4 | 0.73 | 0.24 | 0.06 | yes | FAILS |
| R-N | regional factor, nClimGrid disc | 26 | 0.54 | 0.029 | [0.011, 0.044] | 88 % | 5 | 2.47 | 0.07 | 0.02 | yes | FAILS |
| R-A-PC | R-A with frozen PC1 weights (exploratory) | 26 | 0.41 | −0.089 | [−0.206, 0.020] | 38 % | 3 | −0.22 | 0.50 | 0.13 | yes | exploratory |
| R-N-PC | R-N with frozen PC1 weights (exploratory) | 26 | 0.55 | 0.013 | [−0.012, 0.039] | 58 % | 3 | 0.42 | 0.12 | 0.03 | yes | exploratory |
| P-A | nearest station pair | 26 | 0.61 | 0.001 | [0.000, 0.038] | 72 % | 3 | 0.42 | 0.41 | 0.10 | yes | FAILS |
| P-A-IDW | IDW of 3 nearest stations | 26 | 0.75 | 0.089 | [0.034, 0.137] | 85 % | 5 | 0.67 | 0.28 | 0.07 | yes | FAILS |

*Source: reports/eval-03/results.json `bakeoff.rain.<DESIGN>` (pairs = `.n_pairs`; G1-P has a PRISM cell at every point since the 2026-10-02 re-pull, Phase 3 deviation 1, resolved)*

G1-P runs on 26 of 26 rain pairs and 37 of 37 temperature pairs. Until the 2026-10-02 PRISM re-pull it ran on fewer, because Phase 1 had kept no PRISM cell at some truth points (deviation 1, now resolved); every design now runs on the same pairs. Against R-A, the other rain survivor and the alternate, G1-P is ahead by 0.112 HE [0.032, 0.238]. Against P-A-IDW, which fails P1 but has the next-highest HE, its lead is 0.062 [−0.008, 0.229], a CI that includes zero. The rain gain is concentrated in May-Sep, PRISM's revisions from the early to the final grid are not measured, and the weekly station leg has no liquid Kalshi hedge.

**What this means for the product (seat ruling 2026-09-30).** Temperature cover ships as the station leg alone, with residuals only by RFQ; P-A-IDW is the reference formula for those quotes. Phase 4's capital (§7) used R-A as its residual leg because it ran before this bake-off; it was not re-run. For temperature the station-leg-alone C_30 of $416k is the figure, next to $412k for the two-leg book. For rain the residual design is G1-P with R-A as the alternate; the weekly two-leg rain book has been capitalised but not built (§7).

## 7. Netting and pool capital (EVAL-04, EVAL-05)

Phase 4 built a synthetic business population around each settlement station from Census ZIP Business Patterns and published sector weather sensitivities, had 2 % of small establishments hedge every warm-season day, ran one uniform-price auction per station-leg-day on real Kalshi-era days, and measured what the pool is left holding. The residual leg in these runs is R-A ("metro minus station" on the ASOS network), picked before Phase 3 ran. Phase 3 (§6) found no temperature residual that clears its bar, so the listed temperature product is the station leg alone (C_30 $416k, next to $412k for the two-leg book below). Phase 4 has no weekly rain leg, so the rain residual Phase 3 picked is not in these numbers.

**Netting.** With the central priors, 40 % of gross units cancel (Miami 0.65, Central Park 0.36, Midway 0.32). EWR (0.21) and TTN (0.13) miss the bar on September 2026 alone. M1 passes with the minimum of three stations out of five. Across 1,000 prior draws the pooled number ranges 0.22-0.56, and 67 % of draws still pass M1. But if sector sensitivities are mostly common (the best US daily evidence points that way), netting falls to 0.019 (M2), and rain nets to about zero because almost every sector loses on wet days. Netting inside one ZIP is roughly half the station number (0.22 at Central Park), so the station, not the neighbourhood, is the natural pool.

| station | NR central priors | NR under the null | NR p10-p90 (1,000 prior draws) | NR inside one ZIP | participants (2 %) | leftover units / day | leftover max payout / day |
|---|---|---|---|---|---|---|---|
| NYC | 0.36 | 0.013 | 0.19-0.53 | 0.22 | 1,008 | 4,426 | $27k |
| EWR | 0.21 | 0.011 | 0.12-0.38 | 0.11 | 319 | 1,730 | $10k |
| TTN | 0.13 | 0.005 | 0.06-0.24 | 0.03 | 166 | 1,171 | $7k |
| MDW | 0.32 | 0.014 | 0.16-0.50 | 0.18 | 455 | 2,144 | $13k |
| MIA | 0.65 | 0.054 | 0.39-0.81 | 0.20 | 244 | 798 | $5k |
| pooled | 0.40 | 0.019 | 0.22-0.56 | n/a | n/a | n/a | n/a |

*Source: reports/eval-04-05/results.json `netting.{central,null,ensemble,zip_level,participants.p2,leftover_units_per_day}`*

![Share of gross hedge units that cancel inside one station-day auction (reports/eval-04-05/results.json `netting.{central,ensemble,null}`).](figures/fig4_netting.png)

*Figure: Share of gross hedge units that cancel inside one station-day auction (reports/eval-04-05/results.json `netting.{central,ensemble,null}`).*

**What the pool carries.** Under the central priors the long-heat businesses (liquor and convenience stores, snack bars, HVAC contractors) outweigh the short-heat ones everywhere, so the house ends up buying heat cover. Around Central Park that leaves about 4,426 $1/°F units a day, $27k of maximum payout, against a Kalshi hedge capped at 5 units per city-day. The house cannot lay the flow off at today's depth; capital, not hedging, is the business.

**The auction works mechanically.** Every station-leg-day cleared, most hedger units filled, and the clearing price sat under a cent (scalar) below Kalshi-implied fair value because the leftover is on the sell side. The clearing function conserved units and cash in its property test on random books (tests/test_clear_money.py).

| station (station leg) | auction days | no-trade share | clearing − fair (scalar cents) | hedger units filled | house share of fills | internalised | Kalshi hedge units / day |
|---|---|---|---|---|---|---|---|
| NYC | 542 | 0 % | −0.83 | 92 % | 76 % | 36 % | 5.0 |
| EWR | 34 | 0 % | −0.70 | 94 % | 87 % | 21 % | 0.0 |
| TTN | 33 | 0 % | −0.77 | 94 % | 93 % | 13 % | 0.0 |
| MDW | 571 | 0 % | −0.68 | 92 % | 79 % | 32 % | 5.0 |
| MIA | 543 | 0 % | −0.49 | 92 % | 46 % | 65 % | 4.9 |

*Source: reports/eval-04-05/results.json `auction.<station>/station`*

**Capital.** Revaluing the pool's average book on joint-date history, the 30-day capital is $412k: the worst historical 30-day window, which binds ahead of the 30-day ES99 of $269k. That is 0.126 per $ of pool notional (M3 passes) and 0.25 of full collateral. The junior layer at ES95 is $206k, 50 % of C_30. Three things make the headline look better than it is. The residual leg has a large notional and small risk, so it inflates the denominator: the station leg alone is 0.25. The scenarios price the cover daily at a forecast-based fair value; priced before the forecast is known (deviation D5), the station leg needs 0.36, over the bar, and both legs 0.18. And the worst-window floor rests on 26 joint seasons for the two-leg book. So the leverage story holds only if the cover is repriced every day off the forecast.

| book | seasons | C (h = 1) | C (h = 5) | C_30 | ES99 (30 d) | binding | junior ES95 (30 d) | C_30 / notional | C_30 / full collateral |
|---|---|---|---|---|---|---|---|---|---|
| both legs (headline, M3) | 26 | $35k | $128k | $412k | $269k | worst_window | $206k | 0.126 | 0.25 |
| station leg only | 64 | $29k | $146k | $416k | $278k | worst_window | $217k | 0.251 | 0.47 |
| both legs, priced at climatology (D5) | 26 | $36k | $159k | $577k | $438k | worst_window | $337k | 0.177 | 0.35 |
| station leg, priced at climatology (D5) | 64 | $29k | $146k | $597k | $438k | worst_window | $340k | 0.360 | 0.68 |

*Source: reports/eval-04-05/results.json `capital.deploy_detrended.<book>.H{1,5,30}`*

![30-day pool capital per $ of pool notional; orange = cover priced before the forecast is known (deviation D5) (reports/eval-04-05/results.json `capital.deploy_detrended.*.H30.CPC_notional`).](figures/fig5_capital.png)

*Figure: 30-day pool capital per $ of pool notional; orange = cover priced before the forecast is known (deviation D5) (reports/eval-04-05/results.json `capital.deploy_detrended.*.H30.CPC_notional`).*

**Backtest (M5).** The capital model's 1-day VaR99, fit on 1951-2020, was beaten 1 time in 599 Kalshi-era days against 6 expected. Kupiec rejects (p = 0.011) in the conservative direction: the persistence forecast in the scenarios is worse than the market's forecast, so the model over-reserves. The worst realised 30-day loss was $104k against a backtest C_30 of $417k.

**Season basis and the junior layer (added 2026-09-30; modelled).** C_30 covers a 30-day window, and a whole summer can lose more. Phase 4's junior add-on replays 26 seasons: the worst modelled summer (2009) loses $731k on the simulated book, against C_30 of $412k. On a season basis the same capital carries 0.56 of the simulated book, which is 0.22 of capital per $ of pool notional against 0.126 on the 30-day basis (M3). SPEC now caps writing at capital ÷ worst modelled season loss and always states both horizons. With senior paid 20 % of kept margin (SPEC's 30 bps of gross premium approximates this) and a 10 % treasury cut, the junior layer's modelled return on its $206k is 43 % in the median season, −144 % in a one-in-twenty season (−293 % resampling whole summers) and −332 % in the worst historical season (2009). Past a total loss the junior layer is gone and senior pays. These come from a 7-day block bootstrap on the capital scenario, not from observed seasons (reports/eval-04-05/junior_returns.md).

**House markouts are not a result to lean on.** Pooled house P&L after the Kalshi hedge was $1,154 a day [$610, $1,710]. Almost all of it comes from the residual legs ($1,060 per pooled day), mostly Central Park's ($1,382 a day on the days it traded), and that is a pricing artefact: Central Park reads cool against its airport neighbours and the gap has grown, so a long climatology underprices the residual. Priced on the trailing five years, pooled house P&L drops to $384 a day. The station legs net to about $94 per pooled day: the house loses at NYC, EWR and TTN and wins at Midway and Miami, which follows the sign of the Kalshi mid's bias in each city. The worst day is 15 times the mean daily P&L; ins1's sell-side test found worst days 9-19 times the mean, so the tail shape is familiar. Pool return on C_30 was 47 % a season in the primary run and 19 % with the trailing-five-year residual price; neither is a pre-registered verdict.

| market | house P&L after hedge, $/day | 95 % CI | $ per unit-day | worst day | win rate |
|---|---|---|---|---|---|
| NYC station | −$546 | [−$1,054, −$38] | −0.14 | −$17,182 | 44 % |
| NYC residual | $1,382 | [$1,136, $1,653] | 0.77 | −$6,994 | 86 % |
| EWR station | −$854 | [−$1,389, −$174] | −0.54 | −$5,142 | 38 % |
| EWR residual | −$275 | [−$427, −$65] | −0.42 | −$2,570 | 47 % |
| TTN station | −$590 | [−$1,286, $54] | −0.54 | −$3,709 | 33 % |
| TTN residual | −$48 | [−$189, $42] | −0.07 | −$666 | 41 % |
| MDW station | $412 | [$170, $648] | 0.22 | −$9,034 | 60 % |
| MDW residual | −$237 | [−$340, −$148] | −0.29 | −$7,113 | 32 % |
| MIA station | $305 | [$244, $364] | 0.49 | −$3,540 | 73 % |
| MIA residual | $75 | [$29, $127] | 0.25 | −$1,224 | 51 % |
| pooled | $1,154 | [$610, $1,710] |  | −$17,410 | 58 % |

*Source: reports/eval-04-05/results.json `markouts.<station>/<leg>.hedged`, `markouts.pooled.hedged`*

**Fees.** At 10 bps of notional on hedger fills, the protocol earns $22k a season on the simulated flow; a rule that takes half of each hedger's price improvement earns 0.40 % of notional ($90k a season), because hedger limits carry up to a quarter of loading and the uniform price hands most of it back.

| fee rule | per $ of hedger notional | per season |
|---|---|---|
| 10 bps of notional (primary) | 0.10 % | $22k |
| 25 bps | 0.25 % | $56k |
| 50 bps | 0.50 % | $112k |
| 50 % of price improvement, capped | 0.40 % | $90k |

*Source: reports/eval-04-05/results.json `fees.<rule>`*

**A weekly rain book (added 2026-09-30; modelled).** Rain was run as its own two-leg book: wet-day cover, a station leg on the daily Kalshi rain markets and a residual leg on PRISM grid cells (reports/eval-04-05/rain_book.json; rules frozen in PREREG-rain.md first). Almost nothing nets: 0.003 of units cancel, because nearly every sector loses on wet days. At 2 % take-up the pool is short $282k of payout on each wet day across the five cities. Kalshi's daily rain markets can absorb about 704 contracts a day against about 205,019 needed, so they are roughly 291 times too thin to lay it off. That depth is a volume proxy (10 % of pre-cutoff volume), because no rain order-book history exists. The house carries it. The 30-day capital is $1,082k on the 2024-26 window, against $412k for Phase 4's heat book. That is 0.17 of 30-day notional, and $1,469k for the station leg on 1999-2025. The whole-season figure is $2,505k. The residual leg adds little capital: ×1.00 as priced, ×1.08 if the house wrote every residual unit. With senior paid out of the margin we keep, the junior layer returns 12 % in a median May-Sep season and −147 % in a one-in-twenty one. The three-season test fails under all four splits (−236 % at the fifth percentile on the kinder one). The two observed full years were positive on that rule (102 % in 2025, 45 % in 2026), but they are mostly New York and short.

## 8. Learning a business's sensitivity (EVAL-06)

Phase 5 asked whether a year of daily sales is enough to learn how weather moves a business's revenue, prescribe a heat call plus a wet-day binary, and cut next year's revenue surprise. No public retail sales panel sits near a Kalshi city, so it used stand-ins: bikeshare station starts, transit entries and pooled taxi fares. **These are demand proxies, not a shop's revenue.** Bikeshare is far more weather-driven than a café, so its numbers are an upper bound, not a small-business estimate. The product hypothesis, that a café's heat and rain sensitivity is learnable and hedgeable, is untested on real sales; that is what a pilot is for.

**T2 fails in both bike groups, in both hedge years.** The empirical-Bayes hedge (A3) removes 0.072 [0.056, 0.091] of daily revenue-surprise variance for Citi Bike and 0.053 [0.026, 0.077] for Divvy, about a third of the 0.20 bar. Transit and taxi get about nothing. Almost all of the bike cover comes from the rain leg; the summer heat-only number is 0.001 for Citi Bike. The limit is the instruments, not the estimator: an oracle fitted on the hedge year itself reaches only 0.115 (G1) and 0.063 (G2). A heat call above K plus a wet-day binary misses cold-side temperature, rain amount, lags and ordinary noise.

| group | origin | units | K (°F) | HE_cover heat+rain (A3) | units > 0 | heat only (Jun-Sep) | oracle A4 | replication (origin 2024) |
|---|---|---|---|---|---|---|---|---|
| G1 NYC bike (Citi Bike) | 2025-01-01 | 980 | 75 | 0.072 [0.056, 0.091] | 100 % | 0.001 | 0.115 | 0.081 |
| G2 CHI bike (Divvy) | 2025-01-01 | 191 | 75 | 0.053 [0.026, 0.077] | 88 % | 0.009 | 0.063 | 0.103 |
| G3 CHI transit (CTA) | 2025-01-01 | 140 | 80 | 0.009 [0.003, 0.018] | 97 % | 0.020 | 0.020 | −0.019 |
| G4 CHI taxi | 2025-01-01 | 41 | 84 | −0.001 [−0.003, 0.001] | 39 % | −0.002 | 0.003 | −0.001 |
| G5 NYC taxi (TLC) | 2024-01-01 | 82 | 75 | −0.006 [−0.016, 0.000] | 12 % | −0.009 | 0.005 | n/a |

*Source: reports/eval-06/results.json `verdicts.T2.<G>`, `groups.<G>.primary.{origin,eligibility,K,arms.A4}`, `groups.<G>.replication.arms.A3`; medians across units, 5-95 % day-block bootstrap*

![Out-of-sample HE of the learned hedge by stand-in group, median across units (reports/eval-06/results.json `verdicts.T2`, `verdicts.T3`).](figures/fig6_elasticity.png)

*Figure: Out-of-sample HE of the learned hedge by stand-in group, median across units (reports/eval-06/results.json `verdicts.T2`, `verdicts.T3`).*

**T3 fails too.** At real 24 h Kalshi asks with fees, the Citi Bike hedge keeps HE_ladder 0.006 [−0.003, 0.014], and the buy side cost 32 % of payout over the hedge year, over the 25 % cap. The same forecast effect as in §4: the 24 h ask keeps about 0.08 of the cover, and the gap (0.066 for G1) is forecast-level risk that the default house-hedge path would carry.

**T1 fails for Citi Bike, and the seat overruled the pre-registered stop.** The wet-day effect is large and precise (the wet-day effect on starts is −10.5 %), but the heat slope above K = 75 °F is indistinguishable from zero, because Citi Bike starts rise, stay flat through the hot range and drop only on the hottest days, and one slope above K averages that to nothing. The pre-registration said a T1 fail means stop. The seat ruled after the results that the join is sound and the instrument is the problem, so the G1 results stand with a flag (post hoc, 05-SEAT-RULINGS.md).

**P1 fails by the letter; the seat adopted a corrected interval after the results.** The placebo (another year's weather on the same sales) gives a median HE at or below 0.02 in every group, so the controls are not passing seasonality off as weather. But the pre-registered DerSimonian-Laird interval calls the placebo group means "significant" everywhere, because it treats units as independent while every unit in a city shares the same weather days. A joint day-block bootstrap (Deviation 8, added after a trial number) puts every placebo mean across zero and keeps the real wet effects significant (Citi Bike −0.150 to −0.067). The seat adopted it as the primary interval, post hoc. Under it, Divvy's heat mean also loses significance.

| group | placebo median HE_cover | placebo mu_wet, DL interval (pre-registered) | placebo mu excludes 0 on the day-block interval (Deviation 8) | P1 by the letter |
|---|---|---|---|---|
| G1 | −0.035 | [0.023, 0.029] | no | FAIL |
| G2 | 0.012 | [−0.022, −0.008] | no | FAIL |
| G3 | −0.004 | [0.012, 0.017] | no | FAIL |
| G4 | −0.001 | [−0.001, 0.013] | no | FAIL |
| G5 | 0.002 | [0.002, 0.013] | no | FAIL |

*Source: reports/eval-06/results.json `verdicts.P1.<G>`, `groups.<G>.placebo.mu_day_block_bootstrap_supplementary`*

**T4 fails by the letter, but shrinkage never hurt the bike groups.** The pre-registered rule needed empirical Bayes to beat own-history estimates by 0.02 at every short history. The gain falls under that at n = 180 for Citi Bike (0.016) and at n = 120 and n = 180 for Divvy. Yet empirical Bayes was ahead at every history length in G1-G4, and it cut the share of Citi Bike stations with a negative HE at n = 60 from 24 % to 0.4 %. The portal ships the registered rule (own estimates after n*); "always shrink" is the candidate for the next pre-registration (seat ruling, post hoc).

| group | A3 − A1, n = 60 | n = 90 | n = 120 | n = 180 | n = 365: A3 vs A1 | units with HE < 0 at n = 60: own → EB |
|---|---|---|---|---|---|---|
| G1 | 0.039 | 0.087 | 0.043 | 0.016 | 0.089 vs 0.085 | 23.7 % → 0.4 % |
| G2 | 0.022 | 0.034 | 0.019 | 0.013 | 0.067 vs 0.060 | 19.0 % → 8.9 % |
| G3 | 0.006 | 0.014 | 0.022 | 0.009 | 0.001 vs −0.002 | 65.2 % → 32.3 % |
| G4 | 0.009 | 0.005 | 0.008 | 0.003 | −0.001 vs −0.002 | 76.1 % → 59.3 % |
| G5 | 0.034 | 0.021 | 0.007 | 0.008 | −0.012 vs −0.014 | 85.5 % → 89.7 % |

*Source: reports/eval-06/results.json `verdicts.T4.<G>.short_n.<n>` and `.n365_A{1,3}`*

**T5 (days of history).** For bikes, own estimates clear the descriptive bar from 120 days of history (Citi Bike) and 60 (Divvy); with a sector prior the bar is met from day one. Transit and taxi never clear it.

![Learning curve pooled over origins (reports/eval-06/results.json `groups.<G>.learning_curve.pooled`); dashed line = the T2 bar.](figures/fig7_learning_curve.png)

*Figure: Learning curve pooled over origins (reports/eval-06/results.json `groups.<G>.learning_curve.pooled`); dashed line = the T2 bar.*

**What the pre-registered kill rule says.** T2 failed for both bike groups, so the portal shows the elasticity as advisory only and the decks may not claim that a learned hedge beats doing nothing. What can be said honestly: rain sensitivity is real and learnable for bikeshare, and a wet-day hedge learned from a year of sales took between 5 % and 10 % out of daily revenue-surprise variance out of sample, in two cities and two hedge years. The replication year (origin 2024) gives the same picture (0.081 and 0.103).

## 9. Costs, liquidity, revisions, capital

The brief lists these four as the ways a hedge can fail even when the payout fits. One table each; every cell is read from a results.json path named under the table.

### 9.1 Costs

| instrument | premium / unit | overround (ex fees) | spread cost / unit | fee / unit | total load |
|---|---|---|---|---|---|
| Heat ladder, liquid, all years, 24 h | 4.73 | 24.6 % | 0.69 | 0.195 | 29.7 % |
| Heat ladder, liquid 2025+ (post hoc), 24 h | 4.00 | 9.7 % | 0.29 | 0.179 | 14.6 % |
| Heat ladder, liquid, all years, 2 h | 4.10 | 7.5 % | 0.19 | 0.020 | 8.1 % |
| Heat ladder, thin EWR+TTN, 24 h | 8.90 | 252.8 % | 3.72 | 0.183 | 260.1 % |
| Daily rain binary, 24 h (per $1 payout) |  | 18.1 % |  |  | 20.3 % |
| Learned hedge G1, 24 h asks, buy side (hedge year 2025) |  |  |  |  | 32.0 % |

*Source: reports/eval-01/results.json `temperature.pooled[...]`, `rain_daily.horizons.24.cost_per_dollar_payout{,_ex_fee}` (load = cost − 1); reports/eval-06/results.json `verdicts.T3.G1.cost_ratio`*

### 9.2 Liquidity

| measure | NY / NYC | CHI / MDW | MIA |
|---|---|---|---|
| heat ladder 24 h no-offer, 2023 | 31.0 % | 27.7 % | 41.5 % |
| heat ladder 24 h no-offer, 2024 | 12.8 % | 12.3 % | 13.7 % |
| heat ladder 24 h no-offer, 2025 | 0.3 % | 0.3 % | 0.3 % |
| heat ladder 24 h no-offer, 2026 | 0.0 % | 0.0 % | 0.0 % |
| max units at ≤ 3c slippage (one 2026-09-29 snapshot) | 33 | 54 | 55 |
| monthly rain ladder no-offer at month start | 47 % | 64 % | 49 % |
| pool leftover units / day (2 % participation) vs Kalshi hedge cap per city-day | 4,426 vs 5 | 2,144 vs 5 | 798 vs 5 |

*Source: reports/eval-01/results.json `temperature.city_year[...].no_offer_share`, `depth.ladders`, `rain_monthly`; reports/eval-04-05/results.json `netting.leftover_units_per_day`; hedge cap from eval-04-05 PREREG*

### 9.3 Revisions and settlement source

The station leg settles cleanly: settle on the latest final CLI at D+1 12:00Z and nothing later changed a payout. The same-day preliminary report differs from the final on 10.5 % of days, so settlement must wait for D+1. Gridded data is different: an nClimGrid prelim value five days after the label differs from the scaled file by at least half a degree on 64 % of cell-days, so anything settled on nClimGrid must wait for the scaled file. PRISM revisions were not measured (PRISM keeps no prior versions).

| revision measure | share | sample |
|---|---|---|
| Kalshi settled value vs NWS CLI high (2023+) | 0.16 % | 3,822 city-days |
| CLI final at D+1 12:00Z vs latest CLI (payout moves ≥ $0.50 / unit, M4) | 0.0 % | 4,573 station-days; 73 with a reissued final |
| Same-day preliminary CLI vs final (high differs) | 10.5 % | so N ≥ D+1 |
| Station-days with no final CLI by D+1 12:00Z | 8 | needs a retry rule |
| CLI settle value vs later GHCN-D TMAX | 0.09 % |  |
| nClimGrid prelim (label + 5 d) vs scaled: Tmax moves ≥ 0.5 °F | 64 % | 155,264 cell-days; mean absolute change 0.77 °F |
| nClimGrid prelim vs scaled: wet-day flag flips | 2.9 % |  |

*Source: reports/eval-01/results.json `mismatch`; reports/eval-04-05/results.json `revision.*` (the 'no final by D+1' count sums `revision.missing_final_by_D1_12Z` over stations)*

### 9.4 Capital and the house's P&L

The capital table is in §7; the per-horizon numbers are repeated here with the house's P&L after the Kalshi paper hedge, because the brief asks for them together.

| book | seasons | C (h = 1) | C (h = 5) | C_30 | ES99 (30 d) | binding | junior ES95 (30 d) | C_30 / notional | C_30 / full collateral |
|---|---|---|---|---|---|---|---|---|---|
| both legs (headline, M3) | 26 | $35k | $128k | $412k | $269k | worst_window | $206k | 0.126 | 0.25 |
| station leg only | 64 | $29k | $146k | $416k | $278k | worst_window | $217k | 0.251 | 0.47 |
| both legs, priced at climatology (D5) | 26 | $36k | $159k | $577k | $438k | worst_window | $337k | 0.177 | 0.35 |
| station leg, priced at climatology (D5) | 64 | $29k | $146k | $597k | $438k | worst_window | $340k | 0.360 | 0.68 |

*Source: reports/eval-04-05/results.json `capital.deploy_detrended.<book>.H{1,5,30}`*

| house P&L measure (after the Kalshi hedge, fees in) | value |
|---|---|
| mean house P&L per day, primary run | $1,154 [$610, $1,710] |
| same, residual priced on the trailing 5 years (D6, after numbers) | $384 |
| same, residual priced off the ladder plus metro-minus-station deltas (D6) | $1,543 |
| same, auction cutoff 2 h before close | $1,008 |
| same, cost of capital 6 % | $1,128 |
| same, cost of capital 30 % | $1,205 |
| station legs only, per pooled day (derived) | $94 |
| worst day / worst 5 days / worst 30 days | −$17,410 / −$45,938 / −$104,387 |
| max drawdown | $131,459 |
| days | 599 |

*Source: reports/eval-04-05/results.json `markouts.pooled.hedged`, `auction_variants.<variant>.mo_hedged_mean_daily`; station-leg row = Σ `markouts.<station>/station.hedged.total` / `markouts.pooled.hedged.n_days`*


## 10. What the numbers mean for the product

**The station leg is a real payout, and it is sold at the forecast.** If a business near Central Park, Midway or Miami airport wants money on hot days, the Kalshi ladder pays it: the payout tracks the loss about 0.95 of the way and settles on the official number. What the ladder cannot do is sell tomorrow's heat at last month's price. Bought the day before, it only moves the forecast miss, which on today's market is about 0.37 of the variance. A business that buys the ladder itself (the fallback path) gets that, not 0.95.

**So the default product has to be one fixed-price policy with the house hedging daily, and the house is then an insurer carrying forecast risk.** That is where the 0.95 comes from. The capital to carry it looks affordable only if the house reprices every day off the forecast (0.25 of notional on the station leg); priced once up front it is 0.36. And the house cannot pass the flow to Kalshi: at 2 % participation the leftover around Central Park is about 4,426 units a day against a hedge cap of 5. The protocol is a capitalised pool that uses Kalshi for pricing and some hedging, not a pass-through.

**Netting is a bonus, not the pitch.** It is material only under our sector priors and nearly vanishes if businesses respond to weather alike. The decks should lead with the pool.

**The "we learn your sensitivity" step is not proven.** On the best stand-ins we have, it found a real rain effect and almost no usable heat effect, and it removed a small share of revenue noise. The portal should say the estimate is advisory. The only way to test the actual claim is a pilot with real sales from a few weather-exposed shops.

**Where it stands for a first pilot.** Rain-day cover on Kalshi's daily binary is the cleanest thing to sell (the market beats climatology easily, at about a 20 % load), with a trace counted as dry, the way the Kalshi contract settles. Heat cover near a liquid station works on the payout side, with the forecast risk priced into a fixed premium. Away from the station, the residual bake-off (§6) gives temperature winner: none survived. So heat cover ships as the station leg alone (C_30 $416k against $412k for Phase 4's two-leg book), with residuals by RFQ quoted on P-A-IDW. For rain the winner is G1-P (ΔHE 0.229 on 26 of 26 pairs), with R-A the alternate; the weekly two-leg rain book is sized in §7 but not built yet.

## 11. Caveats and gaps

**Caveats that apply to the numbers above.**
- Executable prices come from hourly candles, not order books. A missing hour is read as "no change". Median staleness at 24 h is about an hour (1.0 h).
- Depth is one top-of-book snapshot from 2026-09-29. Nothing about depth in 2022-25 or intraday.
- The fee formula is medium confidence and applied in every year.
- The 2025+ pool, the climatology-priced capital row and the residual fair-value sensitivities were added after seeing numbers. They are labelled wherever they appear.
- Phase 4's sector priors are low confidence; M1 passes with the minimum number of stations; EWR and TTN rest on one September.
- The capital tail is one worst window on 26 joint seasons (both legs); overlapping windows are not independent.
- Phase 4's residual leg is R-A, picked before Phase 3. No temperature residual cleared Phase 3's bar and the rain residual is a weekly PRISM design, so the two-leg capital describes a book the product will not list. It was not re-run (seat ruling 2026-09-30). The weekly rain book was sized separately (§7).
- The rain book's history counted a trace as wet, and it was not rerun after the rain cover switched to measurable rain only (§4). Its verdicts (no netting, depth far too thin, junior fails) do not turn on trace days.
- The rain book (§7) rests on a 32-month two-leg history. Its residual leg is paid on weekly wet-day counts, which Phase 3 did not test (it scored inches), and the Kalshi depth is a guess at 10 % of volume, not an order book.
- Phase 5's datasets are stand-ins, one hedge year per split, and every unit in a city shares the same weather days, so the effective sample is about a summer of days, not hundreds of units.
- Phase 5's P1 and T1 readings and its G1 stop rely on seat rulings made after the results.

**Gaps against the brief.** Each line of the brief's evaluation list (.planning/PROJECT.md, Core Value plus EVAL-01..07), where this report answers it, and what is missing:

| brief line (.planning/PROJECT.md) | where | status |
|---|---|---|
| Core Value: better than doing nothing | §4, §8 | partly: yes for HE_cover at the station; at 24 h asks only on 2025+ days; not shown for a learned business hedge |
| Core Value: cheaper than a bespoke contract | §9, §11 | NOT measured: we have no bespoke quotes to compare against |
| EVAL-01 five cities, temperature and rain | §4 | covered; EWR/TTN on 34 days each; rain = daily binary + monthly ladders |
| EVAL-01 hourly candles + recorded order books | §4, §9 | candles yes; recorded books NO (S3 recorder not readable), one ins1 snapshot only |
| EVAL-01 HE, overround, spread, depth, binning, settlement mismatch | §4, §9 | covered (depth from one snapshot) |
| EVAL-02 geography basis at nearby stations and grid points | §5 | covered (Phase 3) |
| EVAL-03 residual bake-off (per-cell PRISM + nClimGrid, regional factor, pairs; temp + rain) | §6 | covered (Phase 3) |
| EVAL-04 netting at zip / station / metro (CBP NAICS×zip × elasticities) | §7 | covered; priors LOW confidence; ZBP 2023 used for CBP |
| EVAL-04 what the batch auction leaves for the pool | §7 | covered (simulated flow, 2 % participation) |
| EVAL-05 capital for the tail / correlated heatwave days | §7, §9 | covered for the two-leg book with R-A (picked before Phase 3); temperature lists the station leg alone; weekly two-leg rain book sized in §7 (modelled, not built) |
| EVAL-05 house-MM markouts, trading costs | §7, §9 | covered in simulation; markouts partly a pricing artefact |
| EVAL-05 revision risk (prelim vs final) | §9 | covered for CLI; nClimGrid measured on 2026 vintages; PRISM not measured |
| EVAL-06 elasticity from stand-in sales (Citi Bike, Divvy, Rossmann, M5 or similar) | §8 | covered on bikeshare/transit/taxi; Rossmann and M5 NOT used (not near a Kalshi city) |
| EVAL-06 OOS HE vs no hedge vs pooled; days-of-history curve | §8 | covered; T2 fails |
| EVAL-07 rules before results, every number traced, one-command rebuild | §3, Appendix B-C | covered; PDF only if pandoc exists (HTML here) |

*Source: .planning/PROJECT.md Core Value and Active EVAL-01..07*


## Appendix A. Figures

Built by this script into reports/figures/ (embedded in the sections above):

- `figures/fig1_he_by_year.png`: HE_cover and HE_ladder by city-year, strike rule A, 24 h before close (reports/eval-01/results.json `temperature.city_year`; error bars 95 % block bootstrap).
- `figures/fig2_overround_by_year.png`: Overround of the replicating ladder at the 24 h ask by city-year (reports/eval-01/results.json `temperature.city_year`); dashed line = the T1 bar.
- `figures/fig3_rain_brier.png`: Daily rain binary: Brier score of the market mid vs leave-year-out climatology by horizon (reports/eval-01/results.json `rain_daily.horizons`).
- `figures/fig4_netting.png`: Share of gross hedge units that cancel inside one station-day auction (reports/eval-04-05/results.json `netting.{central,ensemble,null}`).
- `figures/fig5_capital.png`: 30-day pool capital per $ of pool notional; orange = cover priced before the forecast is known (deviation D5) (reports/eval-04-05/results.json `capital.deploy_detrended.*.H30.CPC_notional`).
- `figures/fig6_elasticity.png`: Out-of-sample HE of the learned hedge by stand-in group, median across units (reports/eval-06/results.json `verdicts.T2`, `verdicts.T3`).
- `figures/fig7_learning_curve.png`: Learning curve pooled over origins (reports/eval-06/results.json `groups.<G>.learning_curve.pooled`); dashed line = the T2 bar.
- `figures/fig8_geography.png`: Geography basis: HE of the station leg at held-out points vs distance (reports/eval-03/results.json `eval02.points`).

Phase figures (built by each phase's script, not rebuilt here):

- [eval-01/figures/depth_hist.png](eval-01/figures/depth_hist.png)
- [eval-01/figures/he_by_year.png](eval-01/figures/he_by_year.png)
- [eval-01/figures/no_offer_share.png](eval-01/figures/no_offer_share.png)
- [eval-01/figures/overround_by_year.png](eval-01/figures/overround_by_year.png)
- [eval-04-05/figures/backtest_var.png](eval-04-05/figures/backtest_var.png)
- [eval-04-05/figures/capital_by_horizon.png](eval-04-05/figures/capital_by_horizon.png)
- [eval-04-05/figures/house_markout_cumulative.png](eval-04-05/figures/house_markout_cumulative.png)
- [eval-04-05/figures/netting_ratio.png](eval-04-05/figures/netting_ratio.png)
- [eval-06/figures/he_by_arm.png](eval-06/figures/he_by_arm.png)
- [eval-06/figures/k_profile_and_temp_bins.png](eval-06/figures/k_profile_and_temp_bins.png)
- [eval-06/figures/learning_curve.png](eval-06/figures/learning_curve.png)
- [eval-03/figures/bakeoff_dhe_rain.png](eval-03/figures/bakeoff_dhe_rain.png)
- [eval-03/figures/bakeoff_dhe_temperature.png](eval-03/figures/bakeoff_dhe_temperature.png)
- [eval-03/figures/eta_vs_sdr.png](eval-03/figures/eta_vs_sdr.png)
- [eval-03/figures/eval02_he0_vs_distance.png](eval-03/figures/eval02_he0_vs_distance.png)

## Appendix B. Key map (every number in the prose)

One row per number rendered in the prose, in order of appearance. `ins1`, `DATA.md` and threshold rows are quoted constants, not results.json keys; each names its file. Table cells are not repeated here: each table names its source path under it.

| # | section | value | source |
|---|---|---|---|
| 1 | front | 0.95 | `reports/eval-01/results.json :: temperature.pooled[rule=A,h=24,pool=liquid NY+CHI+MIA].he_cover.est` |
| 2 | front | [0.95, 0.96] | `reports/eval-01/results.json :: temperature.pooled[rule=A,h=24,pool=liquid NY+CHI+MIA].he_cover` |
| 3 | front | 4,462 | `reports/eval-01/results.json :: temperature.pooled[rule=A,h=24,pool=liquid NY+CHI+MIA].n_citydays` |
| 4 | front | 0.37 | `reports/eval-01/results.json :: temperature.pooled[rule=A,h=24,pool=liquid 2025+ (post-hoc)].he_ladder.est` |
| 5 | front | [0.33, 0.42] | `reports/eval-01/results.json :: temperature.pooled[rule=A,h=24,pool=liquid 2025+ (post-hoc)].he_ladder` |
| 6 | front | −0.32 | `reports/eval-01/results.json :: temperature.pooled[rule=A,h=24,pool=liquid NY+CHI+MIA].he_ladder.est` |
| 7 | front | 24.6 % | `reports/eval-01/results.json :: temperature.pooled[rule=A,h=24,pool=liquid NY+CHI+MIA].overround.est` |
| 8 | front | 20 % | `threshold, reports/eval-01/PREREG.md §7 T1` |
| 9 | front | 9.7 % | `reports/eval-01/results.json :: temperature.pooled[rule=A,h=24,pool=liquid 2025+ (post-hoc)].overround.est` |
| 10 | front | 40 % | `reports/eval-04-05/results.json :: netting.central.pooled` |
| 11 | front | 3 | `reports/eval-04-05/results.json :: verdicts.M1.stations_ge_0p25` |
| 12 | front | 1.9 % | `reports/eval-04-05/results.json :: netting.null.pooled` |
| 13 | front | 0.126 | `reports/eval-04-05/results.json :: verdicts.M3.CPC` |
| 14 | front | 0.25 | `reports/eval-04-05/handoff.json :: capital_per_usd_cover_H30.per_usd_pool_notional_station_leg_only` |
| 15 | front | 0.35 | `threshold, reports/eval-04-05/PREREG.md M3` |
| 16 | front | 0.36 | `reports/eval-04-05/handoff.json :: capital_per_usd_cover_H30.per_usd_pool_notional_clim_priced_station_only` |
| 17 | front | 0.072 | `reports/eval-06/results.json :: verdicts.T2.G1.heat_rain_median` |
| 18 | front | 0.053 | `reports/eval-06/results.json :: verdicts.T2.G2.heat_rain_median` |
| 19 | front | 0.20 | `threshold, reports/eval-06/PREREG.md §8 T2` |
| 20 | front | 0.006 | `reports/eval-06/results.json :: verdicts.T3.G1.ladder_median` |
| 21 | front | 0.81 | `reports/eval-03/results.json :: eval02.temperature.pooled_median_he0` |
| 22 | front | none survived | `reports/eval-03/results.json :: verdicts.winner.temperature` |
| 23 | front | G1-P | `reports/eval-03/results.json :: verdicts.winner.rain` |
| 24 | 1 | 6 | `reports/eval-01/results.json :: meta.cap` |
| 25 | 2 | 61 | `data/manifests/DATA.md D1 coverage` |
| 26 | 2 | 34,495 | `data/manifests/DATA.md D1 rows` |
| 27 | 2 | 1,113,358 | `data/manifests/DATA.md D1 rows` |
| 28 | 2 | 2022-04-27 | `reports/eval-01/results.json :: meta.date_range.NY[0]` |
| 29 | 2 | 2026-09-28 | `reports/eval-01/results.json :: meta.date_range.NY[1]` |
| 30 | 2 | 2023-05-11 | `reports/eval-01/results.json :: meta.date_range.MIA[0]` |
| 31 | 2 | 2026-08-26 | `reports/eval-01/results.json :: meta.date_range.EWR[0]` |
| 32 | 2 | 1,053 | `reports/eval-01/results.json :: rain_daily.n_markets` |
| 33 | 2 | 2026-09-29 (ins1 pull; exact UTC time not stored in the file) for the 2026-09-30 ladders | `reports/eval-01/results.json :: depth.snapshot` |
| 34 | 2 | 6,832 | `data/manifests/DATA.md D4 rows` |
| 35 | 2 | 26 | `data/manifests/DATA.md D3 rows` |
| 36 | 2 | 10,054 | `reports/eval-04-05/results.json :: revision.n_products` |
| 37 | 2 | 1,109,492 | `reports/eval-04-05/results.json :: population.small_business.est_small` |
| 38 | 2 | 33,702 | `reports/eval-04-05/results.json :: population.rows` |
| 39 | 2 | 50 | `reports/eval-04-05/results.json :: revision.nclimgrid_prelim_vs_scaled.n_vintages` |
| 40 | 2 | 2,562 | `reports/eval-06/results.json :: panels.G1.units_total` |
| 41 | 2 | 2,494 | `reports/eval-06/results.json :: panels.G2.units_total` |
| 42 | 2 | 144 | `reports/eval-06/results.json :: panels.G3.units_total` |
| 43 | 2 | 77 | `reports/eval-06/results.json :: panels.G4.units_total` |
| 44 | 2 | 261 | `reports/eval-06/results.json :: panels.G5.units_total` |
| 45 | 2 | 2022-07-01 | `reports/eval-06/results.json :: panels.G1.first` |
| 46 | 4 | 0.95 | `reports/eval-01/results.json :: temperature.pooled[rule=A,h=24,pool=liquid NY+CHI+MIA].he_cover.est` |
| 47 | 4 | 0.42 | `reports/eval-01/results.json :: temperature.pooled[rule=A,h=24,pool=liquid NY+CHI+MIA].binning_rmse` |
| 48 | 4 | 0.2 % | `reports/eval-01/results.json :: mismatch[city=all,settle_source=all].value_mismatch_share` |
| 49 | 4 | 3,822 | `reports/eval-01/results.json :: mismatch[city=all,settle_source=all].n` |
| 50 | 4 | 0.85 | `threshold, reports/eval-01/PREREG.md §7 T1` |
| 51 | 4 | 20 % | `threshold, reports/eval-01/PREREG.md §7 T1` |
| 52 | 4 | 24.6 % | `reports/eval-01/results.json :: temperature.pooled[rule=A,h=24,pool=liquid NY+CHI+MIA].overround.est` |
| 53 | 4 | [21.4 %, 27.9 %] | `reports/eval-01/results.json :: temperature.pooled[rule=A,h=24,pool=liquid NY+CHI+MIA].overround` |
| 54 | 4 | 0.37 | `reports/eval-01/results.json :: temperature.pooled[rule=A,h=24,pool=liquid 2025+ (post-hoc)].he_ladder.est` |
| 55 | 4 | 0.5 | `threshold, reports/eval-01/PREREG.md §7 T1b` |
| 56 | 4 | −0.32 | `reports/eval-01/results.json :: temperature.pooled[rule=A,h=24,pool=liquid NY+CHI+MIA].he_ladder.est` |
| 57 | 4 | 0.01 | `reports/eval-01/results.json :: temperature.pooled[rule=A,h=2,pool=liquid 2025+ (post-hoc)].he_ladder.est` |
| 58 | 4 | 0.58 | `derived: HE_cover − HE_ladder, e01 liquid 2025+ pool, rule A, 24 h` |
| 59 | 4 | 3.1 % | `reports/eval-01/results.json :: temperature.pooled[rule=B,h=24,pool=liquid NY+CHI+MIA].tail_outside_share` |
| 60 | 4 | 27 % | `reports/eval-01/results.json :: temperature.pooled[rule=B,h=24,pool=liquid NY+CHI+MIA].unspanned_share` |
| 61 | 4 | −0.75 | `reports/eval-01/results.json :: temperature.pooled[rule=B,h=24,pool=liquid NY+CHI+MIA].he_ladder.est` |
| 62 | 4 | −0.20 | `reports/eval-01/results.json :: temperature.pooled[rule=B,h=24,pool=liquid 2025+ (post-hoc)].he_ladder.est` |
| 63 | 4 | 241 % | `reports/eval-01/results.json :: verdicts.T2.EWR.overround` |
| 64 | 4 | 266 % | `reports/eval-01/results.json :: verdicts.T2.TTN.overround` |
| 65 | 4 | 34 | `reports/eval-01/results.json :: meta.n_citydays.EWR` |
| 66 | 4 | MIA 2024 | `reports/eval-01/results.json :: verdicts.T4.worst` |
| 67 | 4 | 13.7 % | `reports/eval-01/results.json :: verdicts.T4.worst_share` |
| 68 | 4 | 0.3 % | `reports/eval-01/results.json :: verdicts.T4.per_city_year.NY 2025` |
| 69 | 4 | 33 | `reports/eval-01/results.json :: depth.ladders.KXHIGHNY-26SEP30.max_units_3c` |
| 70 | 4 | 54 | `reports/eval-01/results.json :: depth.ladders.KXHIGHCHI-26SEP30.max_units_3c` |
| 71 | 4 | 55 | `reports/eval-01/results.json :: depth.ladders.KXHIGHMIA-26SEP30.max_units_3c` |
| 72 | 4 | 0.106 | `reports/eval-01/results.json :: rain_daily.horizons.24.brier_market` |
| 73 | 4 | 0.247 | `reports/eval-01/results.json :: rain_daily.horizons.24.brier_clim` |
| 74 | 4 | 1.20 | `reports/eval-01/results.json :: rain_daily.horizons.24.cost_per_dollar_payout` |
| 75 | 4 | 0.83 | `reports/eval-01/results.json :: rain_daily.horizons.24.he_wet.he_cover.est` |
| 76 | 4 | 0.27 | `reports/eval-01/results.json :: rain_daily.horizons.24.he_wet.he_ladder.est` |
| 77 | 4 | 62 % | `reports/eval-01/results.json :: rain_daily.trace_yes_share` |
| 78 | 4 | 91 | `reports/eval-01/results.json :: rain_daily.trace_days` |
| 79 | 4 | 1,053 | `reports/eval-01/results.json :: rain_daily.n_markets` |
| 80 | 4 | 26 | `reports/eval-01/trace_kxrain_2026.json :: trace_days` |
| 81 | 4 | 94 | `reports/eval-01/trace_kxrain_2026.json :: measurable_days` |
| 82 | 4 | 96 | `reports/eval-01/trace_kxrain_2026.json :: dry_days` |
| 83 | 4 | 216 | `reports/eval-01/trace_kxrain_2026.json :: settled_markets` |
| 84 | 4 | 0.01 | `threshold, SPEC §3 and .planning/phases/07-*/07-CONTEXT.md seat ruling 2026-09-30T19:12Z (rain cover pays on CLI precip of 0.01 in or more)` |
| 85 | 4 | 0.76 | `reports/eval-01/sensitivity_trace_dry.json :: rain_daily_dry.horizons.24.he_wet.he_cover.est` |
| 86 | 4 | 0.23 | `reports/eval-01/sensitivity_trace_dry.json :: rain_daily_dry.horizons.24.he_wet.he_ladder.est` |
| 87 | 4 | 0.143 | `reports/eval-01/sensitivity_trace_dry.json :: rain_daily_dry.horizons.24.brier_gain` |
| 88 | 4 | 0.141 | `reports/eval-01/results.json :: rain_daily.horizons.24.brier_gain` |
| 89 | 4 | 0.106 | `reports/eval-01/sensitivity_trace_dry.json :: rain_daily_dry.horizons.24.brier_market` |
| 90 | 4 | 0.86 | `ins1 README: he_lo` |
| 91 | 4 | 0.94 | `ins1 README: he_hi` |
| 92 | 4 | 17 % | `ins1 README: overpay_hi` |
| 93 | 4 | 272 | `ins1 README: n_citydays` |
| 94 | 4 | 1.2 % | `reports/eval-01/results.json :: ins1_check.payout_dev` |
| 95 | 4 | 21 % | `derived: ins1 NYC premium / payout − 1` |
| 96 | 4 | 5 | `ins1 README: mismatch_days` |
| 97 | 4 | 1.8 % | `derived: ins1 5 / 272` |
| 98 | 4 | 5 | `ins1 README: depth_units_lo` |
| 99 | 4 | 20 | `ins1 README: depth_units_hi` |
| 100 | 5 | 0.81 | `reports/eval-03/results.json :: eval02.temperature.pooled_median_he0` |
| 101 | 5 | [0.78, 0.84] | `reports/eval-03/results.json :: eval02.temperature.pooled_median_he0_ci` |
| 102 | 5 | 0.49 | `reports/eval-03/results.json :: eval02.rain.pooled_median_he0` |
| 103 | 5 | [0.38, 0.66] | `reports/eval-03/results.json :: eval02.rain.pooled_median_he0_ci` |
| 104 | 5 | 0.95 | `reports/eval-01/results.json :: temperature.pooled[rule=A,h=24,pool=liquid NY+CHI+MIA].he_cover.est` |
| 105 | 6 | none survived | `reports/eval-03/results.json :: verdicts.winner.temperature` |
| 106 | 6 | G1-P | `reports/eval-03/results.json :: verdicts.winner.rain` |
| 107 | 6 | −0.055 | `reports/eval-03/results.json :: verdicts.pc1_vs_equal.he_diff` |
| 108 | 6 | [−0.080, −0.034] | `reports/eval-03/results.json :: verdicts.pc1_vs_equal.ci` |
| 109 | 6 | no | `reports/eval-03/results.json :: verdicts.pc1_vs_equal.adopted` |
| 110 | 6 | 26 | `reports/eval-03/results.json :: bakeoff.rain.G1-P.n_pairs` |
| 111 | 6 | 26 | `reports/eval-03/results.json :: bakeoff.rain.D0.n_pairs` |
| 112 | 6 | 37 | `reports/eval-03/results.json :: bakeoff.temperature.G1-P.n_pairs` |
| 113 | 6 | 37 | `reports/eval-03/results.json :: bakeoff.temperature.D0.n_pairs` |
| 114 | 6 | 0.112 | `reports/eval-03/results.json :: verdicts.winner_vs_next_survivor.rain.he_diff` |
| 115 | 6 | [0.032, 0.238] | `reports/eval-03/results.json :: verdicts.winner_vs_next_survivor.rain.ci` |
| 116 | 6 | 0.062 | `reports/eval-03/results.json :: verdicts.winner_vs_runner_up.rain.he_diff` |
| 117 | 6 | [−0.008, 0.229] | `reports/eval-03/results.json :: verdicts.winner_vs_runner_up.rain.ci` |
| 118 | 6 | $416k | `reports/eval-04-05/results.json :: capital.deploy_detrended.pooled_station_leg_only.H30.C` |
| 119 | 6 | $412k | `reports/eval-04-05/results.json :: verdicts.M3.C30` |
| 120 | 7 | 2 % | `threshold, reports/eval-04-05/PREREG.md Fixed choices` |
| 121 | 7 | $416k | `reports/eval-04-05/results.json :: capital.deploy_detrended.pooled_station_leg_only.H30.C` |
| 122 | 7 | $412k | `reports/eval-04-05/results.json :: verdicts.M3.C30` |
| 123 | 7 | 40 % | `reports/eval-04-05/results.json :: netting.central.pooled` |
| 124 | 7 | 0.65 | `reports/eval-04-05/results.json :: netting.central.MIA` |
| 125 | 7 | 0.36 | `reports/eval-04-05/results.json :: netting.central.NYC` |
| 126 | 7 | 0.32 | `reports/eval-04-05/results.json :: netting.central.MDW` |
| 127 | 7 | 0.21 | `reports/eval-04-05/results.json :: netting.central.EWR` |
| 128 | 7 | 0.13 | `reports/eval-04-05/results.json :: netting.central.TTN` |
| 129 | 7 | 1,000 | `threshold, reports/eval-04-05/PREREG.md Fixed choices (Priors)` |
| 130 | 7 | 0.22 | `reports/eval-04-05/results.json :: netting.ensemble.pooled.p10` |
| 131 | 7 | 0.56 | `reports/eval-04-05/results.json :: netting.ensemble.pooled.p90` |
| 132 | 7 | 67 % | `reports/eval-04-05/results.json :: netting.ensemble_M1_material_share` |
| 133 | 7 | 0.019 | `reports/eval-04-05/results.json :: netting.null.pooled` |
| 134 | 7 | 0.22 | `reports/eval-04-05/results.json :: netting.zip_level.NYC` |
| 135 | 7 | 4,426 | `reports/eval-04-05/results.json :: netting.leftover_units_per_day.NYC.mean_units` |
| 136 | 7 | $27k | `reports/eval-04-05/results.json :: netting.leftover_units_per_day.NYC.mean_max_payout_usd` |
| 137 | 7 | 5 | `threshold, reports/eval-04-05/PREREG.md Fixed choices (Kalshi paper hedge)` |
| 138 | 7 | $269k | `reports/eval-04-05/handoff.json :: ES99_30d_usd` |
| 139 | 7 | 0.126 | `reports/eval-04-05/results.json :: verdicts.M3.CPC` |
| 140 | 7 | 0.25 | `reports/eval-04-05/handoff.json :: capital_per_usd_cover_H30.C_over_full_collateral` |
| 141 | 7 | $206k | `reports/eval-04-05/handoff.json :: junior_ES95_30d_usd` |
| 142 | 7 | 50 % | `derived: e45h junior_share` |
| 143 | 7 | 0.25 | `reports/eval-04-05/handoff.json :: capital_per_usd_cover_H30.per_usd_pool_notional_station_leg_only` |
| 144 | 7 | 0.36 | `reports/eval-04-05/handoff.json :: capital_per_usd_cover_H30.per_usd_pool_notional_clim_priced_station_only` |
| 145 | 7 | 0.18 | `reports/eval-04-05/handoff.json :: capital_per_usd_cover_H30.per_usd_pool_notional_clim_priced_both_legs` |
| 146 | 7 | 26 | `reports/eval-04-05/results.json :: capital.deploy_detrended.pooled_both_legs.H30.n_seasons` |
| 147 | 7 | 1 | `reports/eval-04-05/results.json :: verdicts.M5.kupiec.x` |
| 148 | 7 | 599 | `reports/eval-04-05/results.json :: verdicts.M5.kupiec.n` |
| 149 | 7 | 6 | `reports/eval-04-05/results.json :: verdicts.M5.kupiec.expected` |
| 150 | 7 | 0.011 | `reports/eval-04-05/results.json :: verdicts.M5.kupiec.p_value` |
| 151 | 7 | $104k | `reports/eval-04-05/results.json :: verdicts.M5.worst_realized_30day_loss` |
| 152 | 7 | $417k | `reports/eval-04-05/results.json :: verdicts.M5.C30_backtest_model` |
| 153 | 7 | 26 | `reports/eval-04-05/junior_returns.json :: model.n_seasons` |
| 154 | 7 | $731k | `derived: −min over seasons of e45j model.weather_pnl_hist (worst modelled season weather loss)` |
| 155 | 7 | $412k | `reports/eval-04-05/junior_returns.json :: model.C30_check` |
| 156 | 7 | 0.56 | `derived: e45j model.C30_check / worst modelled season weather loss (season write cap per unit of the simulated book)` |
| 157 | 7 | 0.22 | `derived: e45 verdicts.M3.CPC × worst modelled season weather loss / e45j model.C30_check` |
| 158 | 7 | 20 % | `reports/eval-04-05/junior_returns.json :: senior_share` |
| 159 | 7 | 10 % | `reports/eval-04-05/junior_returns.json :: treasury_cuts[0]` |
| 160 | 7 | $206k | `reports/eval-04-05/junior_returns.json :: capital.J0` |
| 161 | 7 | 43 % | `reports/eval-04-05/junior_returns.json :: model.splits.margin_t10.boot_median` |
| 162 | 7 | −144 % | `reports/eval-04-05/junior_returns.json :: model.splits.margin_t10.boot_p05_1in20` |
| 163 | 7 | −293 % | `reports/eval-04-05/junior_returns.json :: model.splits.margin_t10.sens_whole_season.p05_1in20` |
| 164 | 7 | −332 % | `reports/eval-04-05/junior_returns.json :: model.splits.margin_t10.hist_worst` |
| 165 | 7 | $1,154 | `reports/eval-04-05/results.json :: markouts.pooled.hedged.mean` |
| 166 | 7 | [$610, $1,710] | `reports/eval-04-05/results.json :: markouts.pooled.hedged.ci95` |
| 167 | 7 | $1,060 | `derived: Σ e45 markouts.<station>/residual.hedged.total over five stations / markouts.pooled.hedged.n_days` |
| 168 | 7 | $1,382 | `reports/eval-04-05/results.json :: markouts.NYC/residual.hedged.mean` |
| 169 | 7 | $384 | `reports/eval-04-05/handoff.json :: house_markout_mean_daily_usd.resid_trailing5` |
| 170 | 7 | $94 | `derived: Σ e45 markouts.<station>/station.hedged.total over five stations / markouts.pooled.hedged.n_days` |
| 171 | 7 | 15 | `derived: ¦e45 markouts.pooled.hedged.worst_day_over_mean¦` |
| 172 | 7 | 9 | `ins1 README: V1.worst_over_mean_lo` |
| 173 | 7 | 19 | `ins1 README: V1.worst_over_mean_hi` |
| 174 | 7 | 47 % | `reports/eval-04-05/results.json :: pool_return.mean_season_return_on_C30` |
| 175 | 7 | 19 % | `reports/eval-04-05/results.json :: pool_return.mean_season_return_on_C30_resid_trailing5` |
| 176 | 7 | $22k | `reports/eval-04-05/results.json :: fees.bps10.per_season_usd` |
| 177 | 7 | 0.40 % | `reports/eval-04-05/results.json :: fees.cow50.per_usd_notional` |
| 178 | 7 | $90k | `reports/eval-04-05/results.json :: fees.cow50.per_season_usd` |
| 179 | 7 | 0.003 | `reports/eval-04-05/rain_book.json :: netting.central.pooled` |
| 180 | 7 | $282k | `derived: Σ rain netting.leftover.<ST>.leftover_units_per_day over NYC, EWR, TTN, MDW, MIA ($1 of payout per unit)` |
| 181 | 7 | 704 | `derived: Σ rain depth.by_city.<ST>.depth_proxy over the five cities (contracts a day)` |
| 182 | 7 | 205,019 | `derived: Σ rain depth.by_city.<ST>.mean_net_short_contracts over the five cities (contracts a day)` |
| 183 | 7 | 291 | `derived: Σ mean_net_short_contracts / Σ depth_proxy, rain depth.by_city, five cities` |
| 184 | 7 | 10 % | `threshold, reports/eval-04-05/PREREG-rain.md (depth proxy = 10 % of pre-cutoff volume)` |
| 185 | 7 | $1,082k | `reports/eval-04-05/rain_book.json :: capital.two_leg_joint.H30.C` |
| 186 | 7 | $412k | `reports/eval-04-05/handoff.json :: C30_usd` |
| 187 | 7 | 0.17 | `reports/eval-04-05/rain_book.json :: R2.CPC` |
| 188 | 7 | $1,469k | `reports/eval-04-05/rain_book.json :: capital.station_long_1999_2025.H30.C` |
| 189 | 7 | $2,505k | `reports/eval-04-05/rain_book.json :: capital.two_leg_joint.H153.C` |
| 190 | 7 | 1.00 | `reports/eval-04-05/rain_book.json :: R3.ratio` |
| 191 | 7 | 1.08 | `reports/eval-04-05/rain_book.json :: D1_absorb_all.ratio30` |
| 192 | 7 | 12 % | `reports/eval-04-05/rain_book.json :: junior.model_MaySep.splits.margin_t10.median` |
| 193 | 7 | −147 % | `reports/eval-04-05/rain_book.json :: junior.model_MaySep.splits.margin_t10.p05_1in20` |
| 194 | 7 | −236 % | `reports/eval-04-05/rain_book.json :: R5.margin_t10.three_season_sum_p05` |
| 195 | 7 | 102 % | `reports/eval-04-05/rain_book.json :: junior.observed_all_year.margin_t10.2025.junior_return` |
| 196 | 7 | 45 % | `reports/eval-04-05/rain_book.json :: junior.observed_all_year.margin_t10.2026.junior_return` |
| 197 | 8 | 0.072 | `reports/eval-06/results.json :: verdicts.T2.G1.heat_rain_median` |
| 198 | 8 | [0.056, 0.091] | `reports/eval-06/results.json :: verdicts.T2.G1.heat_rain_ci` |
| 199 | 8 | 0.053 | `reports/eval-06/results.json :: verdicts.T2.G2.heat_rain_median` |
| 200 | 8 | [0.026, 0.077] | `reports/eval-06/results.json :: verdicts.T2.G2.heat_rain_ci` |
| 201 | 8 | 0.20 | `threshold, reports/eval-06/PREREG.md §8 T2` |
| 202 | 8 | 0.001 | `reports/eval-06/results.json :: verdicts.T2.G1.heat_only_median` |
| 203 | 8 | 0.115 | `reports/eval-06/results.json :: groups.G1.primary.arms.A4.cover_heat_rain_daily.median` |
| 204 | 8 | 0.063 | `reports/eval-06/results.json :: groups.G2.primary.arms.A4.cover_heat_rain_daily.median` |
| 205 | 8 | 0.006 | `reports/eval-06/results.json :: verdicts.T3.G1.ladder_median` |
| 206 | 8 | [−0.003, 0.014] | `reports/eval-06/results.json :: verdicts.T3.G1.ladder_ci` |
| 207 | 8 | 32 % | `reports/eval-06/results.json :: verdicts.T3.G1.cost_ratio` |
| 208 | 8 | 25 % | `threshold, reports/eval-06/PREREG.md §8 T3` |
| 209 | 8 | 0.08 | `reports/eval-06/results.json :: groups.G1.primary.ladder_transferable_share.A3_heat_rain` |
| 210 | 8 | 0.066 | `derived: e06 T2 G1 heat_rain_median − T3 G1 ladder_median` |
| 211 | 8 | −10.5 % | `reports/eval-06/results.json :: verdicts.T1.G1.mu_wet` |
| 212 | 8 | 0.02 | `threshold, reports/eval-06/PREREG.md §8 P1` |
| 213 | 8 | −0.150 | `reports/eval-06/results.json :: groups.G1.primary.mu_day_block_bootstrap_supplementary.wet.p025` |
| 214 | 8 | −0.067 | `reports/eval-06/results.json :: groups.G1.primary.mu_day_block_bootstrap_supplementary.wet.p975` |
| 215 | 8 | 0.02 | `threshold, reports/eval-06/PREREG.md §8 T4` |
| 216 | 8 | 0.016 | `reports/eval-06/results.json :: verdicts.T4.G1.short_n.180.diff` |
| 217 | 8 | 24 % | `reports/eval-06/results.json :: verdicts.T4.G1.short_n.60.share_neg_A1` |
| 218 | 8 | 0.4 % | `reports/eval-06/results.json :: verdicts.T4.G1.short_n.60.share_neg_A3` |
| 219 | 8 | 120 | `reports/eval-06/results.json :: verdicts.T5.G1.n_star_A1` |
| 220 | 8 | 60 | `reports/eval-06/results.json :: verdicts.T5.G2.n_star_A1` |
| 221 | 8 | 5 % | `derived: min of e06 A3 HE_cover heat+rain, G1/G2, primary and replication` |
| 222 | 8 | 10 % | `derived: max of e06 A3 HE_cover heat+rain, G1/G2, primary and replication` |
| 223 | 8 | 0.081 | `reports/eval-06/results.json :: groups.G1.replication.arms.A3.cover_heat_rain_daily.median` |
| 224 | 8 | 0.103 | `reports/eval-06/results.json :: groups.G2.replication.arms.A3.cover_heat_rain_daily.median` |
| 225 | 9 | 10.5 % | `reports/eval-04-05/results.json :: revision.prelim_vs_final_differs_share` |
| 226 | 9 | 64 % | `reports/eval-04-05/results.json :: revision.nclimgrid_prelim_vs_scaled.tmax_moves_ge_0p5F_share` |
| 227 | 10 | 0.95 | `reports/eval-01/results.json :: temperature.pooled[rule=A,h=24,pool=liquid NY+CHI+MIA].he_cover.est` |
| 228 | 10 | 0.37 | `reports/eval-01/results.json :: temperature.pooled[rule=A,h=24,pool=liquid 2025+ (post-hoc)].he_ladder.est` |
| 229 | 10 | 0.25 | `reports/eval-04-05/handoff.json :: capital_per_usd_cover_H30.per_usd_pool_notional_station_leg_only` |
| 230 | 10 | 0.36 | `reports/eval-04-05/handoff.json :: capital_per_usd_cover_H30.per_usd_pool_notional_clim_priced_station_only` |
| 231 | 10 | 2 % | `threshold, reports/eval-04-05/PREREG.md Fixed choices` |
| 232 | 10 | 4,426 | `reports/eval-04-05/results.json :: netting.leftover_units_per_day.NYC.mean_units` |
| 233 | 10 | 5 | `threshold, reports/eval-04-05/PREREG.md Fixed choices (Kalshi paper hedge)` |
| 234 | 10 | 20 % | `derived: e01 rain_daily.horizons.24.cost_per_dollar_payout − 1` |
| 235 | 10 | none survived | `reports/eval-03/results.json :: verdicts.winner.temperature` |
| 236 | 10 | $416k | `reports/eval-04-05/results.json :: capital.deploy_detrended.pooled_station_leg_only.H30.C` |
| 237 | 10 | $412k | `reports/eval-04-05/results.json :: verdicts.M3.C30` |
| 238 | 10 | G1-P | `reports/eval-03/results.json :: verdicts.winner.rain` |
| 239 | 10 | 0.229 | `reports/eval-03/results.json :: bakeoff.rain.G1-P.pooled_median_dhe` |
| 240 | 10 | 26 | `reports/eval-03/results.json :: bakeoff.rain.G1-P.n_pairs` |
| 241 | 10 | 26 | `reports/eval-03/results.json :: bakeoff.rain.D0.n_pairs` |
| 242 | 11 | 1.0 | `reports/eval-01/results.json :: temperature.pooled[rule=A,h=24,pool=liquid NY+CHI+MIA].stale_median_h` |
| 243 | 11 | 26 | `reports/eval-04-05/results.json :: capital.deploy_detrended.pooled_both_legs.H30.n_seasons` |
| 244 | 11 | 32 | `threshold, reports/eval-04-05/rain_book.md Caveats (two-leg history 2024-01..2026-08)` |
| 245 | 11 | 10 % | `threshold, reports/eval-04-05/PREREG-rain.md (depth proxy = 10 % of pre-cutoff volume)` |

## Appendix C. How to rebuild

`make report` runs `uv run python scripts/build_report.py`. It reads the files below, rewrites reports/EVALUATION.md and reports/figures/, and exports reports/EVALUATION.pdf with pandoc if pandoc is installed, otherwise reports/EVALUATION.html (self-contained, figures embedded). It computes no new statistic. To refresh a number, re-run the phase script (scripts/eval02.py, eval04.py, eval05.py, eval03.py) and then `make report`.

| source id | file | written (UTC) | md5 |
|---|---|---|---|
| e01 | reports/eval-01/results.json | 2026-09-30T13:37:29Z | b77fc39e2508facedab4bd4629475f30 |
| e03 | reports/eval-03/results.json | 2026-10-02T08:27:30Z | 98d828d8b2b9a5c0a37c5a2dd933ac48 |
| e45 | reports/eval-04-05/results.json | 2026-09-30T13:48:54Z | 2d98279ba01a8318875415b34ed45d68 |
| e45h | reports/eval-04-05/handoff.json | 2026-09-30T13:48:54Z | 044c2449a429f5ab15453079f86bf506 |
| e45j | reports/eval-04-05/junior_returns.json | 2026-09-30T14:26:00Z | a4ebd429f75b9b8b70c0546e77337266 |
| rain | reports/eval-04-05/rain_book.json | 2026-09-30T18:57:45Z | 1f6a188c9744d5dfe58d1f99c0a4f431 |
| trace | reports/eval-01/trace_kxrain_2026.json |  | 306544a32d14b831f6870a587403fac7 |
| sens | reports/eval-01/sensitivity_trace_dry.json |  | 8a8265a99e3bd87e64dff742a94810fd |
| e06 | reports/eval-06/results.json | 2026-09-30T14:06:51Z | f602ddaa42bae32ac423a224d69c9b1a |
| ins2 | prior/hl-mm-ins/reports/ins2/results.json |  | 48947697e3006a8833c70ca42ded9b46 |

*Source: computed by scripts/build_report.py at build time*

Prose lint: no digit outside a placeholder.
