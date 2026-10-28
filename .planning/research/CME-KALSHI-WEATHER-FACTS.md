# CME vs Kalshi weather: facts pass (2026-10-24, read-only)

Owner idea 10-24: "big players use cme small players use kalshi pm. What id we created a deep learning model to make on both by trading their correlations or pairs trades". Owner follow-up: "see if the CME actually reflects whether it actually turns out, or if it just reflects its participants' need to hedge."

Method: no WebFetch tool in this worker, and cmegroup.com refuses curl (HTTP/2 reset). CME pages and the CME JSON endpoints were read through the r.jina.ai reader proxy with User-Agent research-bot. Databento: sections 1-7 used metadata calls only (`get_cost`, `get_record_count`, `symbology.resolve`); section 8 adds the seat-approved $0.24 pull. Free data downloaded: GHCN-Daily for 3 stations (33 MB) and IEM CLI/ASOS (~1.3 MB). Scripts and outputs: `.planning/research/cme-first-look/`. Scripts use repo-relative paths via `common.py`; raw inputs live in gitignored `data/raw/cme-weather/`, and `fetch_free.py`, `fetch_acis.py` and `db_pull.py` re-create them. Tags: **[read]** = on the page or in the data today; **[calc]** = computed here; **[UNVERIFIED]** = from memory, no source seen today.

## 1. CME weather products today
- Product: HDD, CDD and CAT index futures and options. HDD/CDD on 13 US cities plus Essen, London, Amsterdam, Paris. CAT on the 4 European cities and Tokyo. US unit is $20 x index. [read] https://www.cmegroup.com/education/lessons/overview-of-weather-markets
- The slate has 373 weather products: HDD 170, CDD 130, CAT 58, Wind 15. Futures 184, options 189. [read] CME ProductSlate JSON, group=5 (via https://www.cmegroup.com/markets/weather.html)
- Tenors are monthly, seasonal strips (Nov-Mar, Dec-Feb, May-Sep, Jul-Aug) and the Q1-Q4 strips. There is no daily or weekly product. The filing lists "21 monthly contracts of Oct, Nov, Dec, Jan, Feb, Mar, Apr" for HDD. [read] slate above; CME submission 23-177, https://www.cftc.gov/sites/default/files/filings/ptc/23/05/ptc0504231410.pdf; reports/orfe-t5/VENUE-CENSUS.md
- Index: daily average = (max + min)/2 over 0000-2359 LST. HDD = max(0, 65 - avg), CDD = max(0, avg - 65), summed over the calendar month. Data is NWS observations "processed by Speedwell Settlement Services Ltd.", and the final settlement is the Speedwell CME Degree Days Index. [read] 23-177 rule 40301/40303
- US stations (WBAN): Atlanta Hartsfield 13874, Boston Logan 14739, Burbank 23152, Chicago **O'Hare** 94846, Cincinnati/N. Kentucky (CVG) 93814, DFW 03927, Houston **Bush IAH** 12960, Las Vegas 23169, MSP 14922, New York **LaGuardia** 14732, Philadelphia Intl 13739, Portland 24229, Sacramento Executive 23232. [read] 23-177 Exhibit A
- Hours: Globex Sun-Fri 5:00 pm-3:15 pm CT. ClearPort Sun 5:00 pm-Fri 5:45 pm CT. Tick = 1 index point = $20. Trading ends 9:00 am CT on the 2nd business day after the contract month. Block minimum 20 contracts. Non-member exchange fee $1.35/side (2024 filing). [read] 23-177; 24-141 via VENUE-CENSUS.md
- Margins (CME, maintenance, 10-24): NY HDD Oct-26 $480, Nov-26 $1,207, Dec-26 $1,120; Cincinnati HDD Oct-26 $348, Nov-26 $1,060. [read] CmeWS Margins/OUTRIGHT clearingCode=H4, H3. Initial margin for speculators is usually ~110% of maintenance. [UNVERIFIED]
- Volume and OI, trade date Fri 2026-10-23 (prelim): **volume 0 in all 373 products**. Total OI 100,475 (futures 36,475, options 64,000). Only 36 products have any OI. OI by city: NY 21,472; Minneapolis 16,966; Cincinnati 12,099; Atlanta 9,172; Philadelphia 8,800; Burbank 7,250; Dallas 7,118; Chicago 5,098; Boston 4,850; Portland 3,500; Houston 2,900; Essen 1,250; all others 0. Largest lines: MSP HDD Nov strip options 14,766; NY HDD Dec strip options 9,750; Cincinnati HDD monthly futures 8,600. [read] slate JSON
- Notional, rough: 36,475 futures OI x $20 x ~600 HDD ≈ $440M. [calc, rough]
- How often the screen trades: across 26 US monthly HDD/CDD futures roots on Globex there were **87 trades from 2022-10-01 to 2026-10-24** (1,085 since 2010-06) and 19,181 top-of-book updates in those 4 years. [read] Databento `get_record_count`, GLBX.MDP3 `trades` / `mbp-1`, stype parent. So the screen price almost never changes intraday. The OI is built by blocks through ClearPort, with three voice brokers (BGC, Snapper Creek, TP ICAP). [read] VENUE-CENSUS.md. That nearly all volume is block is an inference from the two counts.
- **How the daily settle is set:** Tier 1 is market activity before 15:00 CT. Tier 2: "In the absence of trade info, the 1D movement for the corresponding month of Speedwell will be applied". Tier 3: prior day. Tier 2 applies only in the "forecasting period", which runs from 15 days before the month to month end. [read] https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457413229/Weather
- The 10-19..10-23 settles behave the same way: Oct-26 and Nov-26 move every day with zero volume, and Dec-26 sits flat (NY 700, CHI 930, CVG 819). [read] CmeWS Settlements, products 1151/1186/1145; saved in cme-first-look/cme-settles/
- The free CME settlements API returns only the last 5 trade dates. Older dates come back `"empty":true`. [read]

## 2. Data access (Databento)
- GLBX.MDP3 carries CME weather from 2010-06-06. Parents that resolve: HDD H0-H7, HQ, HR, HS, HW, LP; CDD K0-K7, KP, KQ, KR, KS, KW. Codes match the slate (H4 = NY HDD, K4 = NY CDD, H2/K2 = Chicago, H3 = Cincinnati). [read] `symbology.resolve` (free); slate JSON
- Cost estimates [read, `get_cost`]. The 26-root `statistics` and `trades` pulls were made on 10-24 for section 8:

| pull | records | cost |
|---|---|---|
| `statistics` (settles, OI, cleared volume), H2/H4/K2/K4, 2022-10..2026-10 | 533k | $0.04 |
| `statistics`, all 26 US roots, 2022-10..2026-10 | 3.25M | $0.24 |
| `statistics`, 20 roots, 2010-06..2026-10 | 4.83M | $0.36 |
| `trades`, 26 roots, 2010-06..2026-10 | 1,085 | $0.0014 |
| `mbp-1`, 26 roots, 2022-10..2026-10 | 19,181 | $0.0026 |

- The `trades` schema is Globex only. Blocks show up in `statistics` cleared volume and OI, not as trades. [UNVERIFIED, from MDP3 knowledge]

## 3. Kalshi weather
- 458 series in "Climate and Weather" (daily 122, monthly 71, weekly 19, hourly 14). [read] GET /trade-api/v2/series?category=Climate and Weather
- The series metadata names "The Weather Company" (weather.com/kalshi) as the settlement source, with the station given by its NWS CLI code in the rules: NYC = CLINYC (Central Park), CHI = CLIMDW (Midway), CLIPHL, CLIATL, CLIBOS, CLIDFW, CLIHOU (= **Hobby**, per IEM product CLIHOU vs CLIIAH), CLILAS, CLIMSP, CLIEWR, CLITTN. [read] markets?series_ticker=…, rules_primary; IEM json/cli.py
- Station overlap with CME. **Same station:** Atlanta, Boston, DFW, Las Vegas, MSP, Philadelphia (Kalshi daily high and low ladders), plus Cincinnati CVG through KXHDDCVG. **Different station:** NY (LGA vs Central Park), Chicago (O'Hare vs Midway), Houston (IAH vs Hobby). **No Kalshi series:** Burbank, Portland, Sacramento. [calc from the two station lists]
- **KXHDDCVG** is the only Kalshi degree-day series. It is the Q4 sum of HDD at KCVG (the same station as CME H3), Oct 1-Dec 31 2026, in 9 "below X" rungs from 1,250 to 1,650. Its daily HDD is TWC's published HDD(65), or failing that TWC's "Hourly Mean(F)", by local calendar day. That is **not** CME's (max+min)/2. Volume so far 23,737 contracts; OI ≤ 579 per rung; spreads 3-89 cents. It closes 2027-01-01. [read] markets?series_ticker=KXHDDCVG; terms https://assets.kalshi.com/contract_terms/HDDAREA.pdf
- Median volume per settled daily event (last 32 events, contracts): NY high 160,932; MIA 147,706; CHI 88,461; PHIL 46,295; ATL 43,992; DAL 40,225; BOS 29,779; HOU 28,987; MIN 28,768; LV 24,265; EWR 4,012; TTN 3,367. Low-temp ladders: 3.9k-16.4k (NYC 16,441). Sum of yes asks on the 10-24 events: 1.04-1.11 (EWR 1.38). Mid-rung spreads 1-7 cents. [read/calc] markets endpoint
- Fees: weather series are `fee_type: quadratic`, multiplier 1 (taker 0.07·C·P·(1-P)). [read] series JSON; memory `kalshi-fee-schedule.md`

## 4. The math link
- CDD_month = Σ_d max(0, (Tmax_d + Tmin_d)/2 - 65), and HDD is the mirror. A 1°F error in one day's Tmax moves that day's average by 0.5°F, which is 0.5 DD or $10 per CME contract, while the day stays on one side of 65. [calc from the rule]
- How much one day explains (1996-2025) [calc, bench.py]:

| station, month | sd of month | each day's own variance as share of month | R² of one day's DD vs month total (mean over days) |
|---|---|---|---|
| LGA, Jan HDD | 134 | 0.14/31 | 0.25 |
| LGA, Jul CDD | 77 | 0.13/31 | 0.26 |
| ORD, Jan HDD | 146 | 0.18/31 | 0.19 |
| CVG, Jul CDD | 81 | 0.10/31 | 0.34 |

  One day's own share is under 1%. The R² is large because warm or cold spells last several days.
- What a price implies for the rest of the month, when every remaining day stays below 65: implied mean temp = 65 - (F - K)/n, where F = futures, K = HDD already observed, n = days left. With E[Tmax] and E[Tmin] from Kalshi ladders, a day's expected DD is linear only when the day is far from 65. Near 65 (shoulder months) you need the full distribution.
- 2026-10-23 settles, K through 10-22 [calc, implied.py; GHCN plus CLI]:

| station | settle F | K | F - K over 9 days | implied mean temp | 10-yr normal |
|---|---|---|---|---|---|
| LGA | 160 | 80.5 | 79.5 HDD | 56.2°F | 56.9°F |
| ORD | 173 | 108.0 | 65.0 HDD | 57.8°F | 49.1°F |
| CVG | 145 | 93.0 | 52.0 HDD | 59.2°F | 53.0°F |

  These are Tier-2 marks with OI 0 in Oct-26, so they are Speedwell's forecast, not a traded price.

## 5. Our recorded Kalshi books (s3://hlmm-reduced-5325/recorder/tokyo/kalshi-weather-books/)
- Coverage: 2026-09-30T07:49Z to **2026-10-12T06:57Z** (last `_status` heartbeat; last books segment is 10-12 06:45Z, uploaded 10-19). 13 date partitions. Books: 1,151 objects, 1.23 GB (~100-105 MB per full day). Settlements ~0.37 MB/day, candles ~0.8 MB/day. [read] `aws s3 ls --summarize`, `_status/status.json`
- At the end: 317 series included, 1,036 open markets (458 polled every 60 s, 578 every 5 min), 11.7M book rows, 0 HTTP 429s. Kinds with open markets on 10-11: high_temp 24, low_temp 25, rain 20, snow 12, temp_other 15, hurricane 15, degree_day 1 (KXHDDCVG). [read] status.json; discovery 2026-10-11 summary row
- Cadence and schema: books every 60 s within 48 h of close and every 5 min otherwise. All levels both sides (both are bids). Hourly candles; settlements every 5 min until finalized. [read] README.md at the prefix
- **The recorder is not running.** Instance i-0cb3aefe06643525d is not returned by `describe-instances` (ap-northeast-1, 10-24). We have about 12 days, and no books after 10-12. [read]

## 6. Access
- CME: you need a futures account at an FCM permissioned for CME weather, or a block arranged by one of the three voice brokers and given up to that FCM. The block minimum of 20 contracts is $400 per index point; a Jan contract's sd of ~140 HDD is ~$2,800 per lot and ~$56k per block. [read] VENUE-CENSUS.md; [calc]. Which retail brokers enable H*/K* codes: [UNVERIFIED]
- Kalshi: the owner's account exists, but **every Kalshi bot was stopped by the owner on 10-24 and only the owner restarts them** (memory `owner-all-bots-stopped-2026-10-24.md`). Live tests are capped at tens of dollars and holds at about 1 day (memory `owner-capital-per-test-limit.md`, `owner-short-hold-capital-turnover.md`).

## 7. Does CME weather price the outcome or a hedging premium?
**(a) Published evidence** [read = abstract read today via api.openalex.org; samples were mostly before 2012, when the screen still traded]
- Chincarini, J. Futures Markets (online 2010, vol. 31 2011 [vol UNVERIFIED]), doi 10.1002/fut.20463: 18 US cities, HDD and CDD futures. The market's implied forecast is compared with historical forecasts and NWS 7-day MOS. Finds the market "quite efficient despite its lack of depth". [read; sample years UNVERIFIED]
- Ritter, J. Energy Markets (2013), doi 10.21314/jem.2013.100: CME prices for two monthly indexes "generally outperform the meteorological forecasts in predicting the outcome of the monthly index". [read]
- Ritter, Mußhoff, Odening, J. Derivatives 19(2) (2011), doi 10.3905/jod.2011.19.2.045 (WP doi 10.18452/4271): NY, Minneapolis, Cincinnati, forecasts 13 days ahead. Forecast-augmented models match CME prices better, especially on days with real trading. [read]
- Härdle & López Cabrera, Applied Math. Finance (2012), doi 10.1080/1350486x.2011.591170: the market price of risk implied by CME CAT/HDD/CDD futures "significantly differs from 0", varies in time and changes sign. The WP uses Berlin CAT. [read]
- Hamisultane (HAL, 2007): NY CME futures. A consumption-based model needs "improbably high" risk aversion to fit prices, so a standard risk premium does not explain them. [read]
- "Comparison of temperature models using HDD and CDD futures", J. Risk Finance (doi 10.1108/15265941311301198): backtest on NY, Atlanta, Chicago daily settles, split into in-period and out-of-period. [read]
- Dorfleitner & Wimmer, J. Banking & Finance 34 (2010), doi 10.1016/j.jbankfin.2009.12.004: title confirmed. The finding (index vs daily modelling, forecasts help) is [UNVERIFIED].
- Campbell & Diebold (NBER w10141, 2003; JASA 2005): time-series density forecasts of daily temperature are useful. It does not test futures bias. [read]
- Benth & Šaltytė-Benth, Quant. Finance (2007): CAR/OU pricing with a market price of risk. Theory, not a bias test. Jewson & Brix (2005, book) [UNVERIFIED].
- Net: in 2000-2012 data, prices carried forecast information, sometimes beat forecasts, and showed a nonzero, sign-changing risk price. **None of this covers 2022-26**, when the screen trades about 20 times a year and most settles are Speedwell marks.

**(b) Test design (pre-registered here, before any CME numbers)**
- Sample: H2/H4/H3/K2/K4/K3 (Chicago, NY, Cincinnati), seasons 2022-23 to 2025-26 (main) and 2010-22 (extension). Price = CME daily settle at leads L = 30, 15, 7, 1 days before month end. Outcome = final index (`statistics` final settle), cross-checked against GHCN.
- Metric: e = final - settle. Mean(e) < 0 for HDD means buyers overpay, i.e. a premium paid to sellers. Report the mean with an HAC/block-bootstrap CI clustered by month, plus the sd.
- Benchmarks at the same L: (i) known-to-date + 10-yr daily climatology; (ii) known-to-date + NWS/NBM MOS for the next 7 days (IEM MOS archive, free) + climatology after that.
- **Split days by Databento cleared volume > 0** (blocks or trades, Tier 1) vs mark-only days (Tier 2/3). Only Tier-1 days measure what participants pay. Tier-2 days measure Speedwell's forecast.
- Verdict rule: "hedging pressure" if mean(e) on Tier-1 days has the same sign in at least 2 of 3 cities, its CI excludes 0, and it beats benchmark (ii)'s bias by ≥ 2 SE. "Prices the outcome" if the bias is inside ±1 SE and RMSE(settle) ≤ RMSE(benchmark ii).
- Data: Databento `statistics` $0.04 (4 roots, 4 yrs) or $0.24 (26 roots); map ids with free `symbology.resolve`. Realized: GHCN-Daily, free. Forecasts: IEM MOS, free. **Done in section 8** (seat OK 10-24, $0.24).

**(c) First look (free data only; not the test above)**
- Our index matches CME's. GHCN LGA Sep-26 CDD = **182.0** vs the CME Sep-26 settle of 182.0 on 10-01; ORD 182.5 vs 183.0. GHCN and NWS CLI daily max/min agree on 99.3% (LGA) and 100% (ORD, CVG) of 293 days in 2026. [calc, dd.py; validate.json]
- The noise floor sets how big a premium we could detect. Error = realized - forecast, 2016-26 (HDD Nov-Mar n = 53, CDD Jun-Aug n = 33) [calc, bench.py; bench.csv]:

| | 30-yr climo bias / sd | 10-yr climo bias / sd | to-date+climo, L=15 | L=7 | L=1 |
|---|---|---|---|---|---|
| LGA HDD | -39 / 103 | -25 / 113 | -11 / 70 | -9 / 48 | -1 / 17 |
| ORD HDD | -63 / 131 | -54 / 139 | -26 / 96 | -19 / 65 | -6 / 22 |
| CVG HDD | -53 / 124 | -37 / 133 | -19 / 93 | -18 / 62 | -5 / 21 |
| LGA CDD | +33 / 59 | +11 / 61 | +2 / 41 | +2 / 28 | +1 / 8 |
| ORD CDD | +47 / 49 | +25 / 50 | +10 / 41 | +8 / 29 | +1 / 11 |

- Warming alone makes climatology overstate HDD by 25-63 per month and understate CDD by 11-47. A market priced off climatology would look like it "charges HDD buyers a premium" when nothing but the trend is at work. The baseline must be trend-aware.
- With 4 seasons (n ≈ 20 winter months per city) and a sd of 70-96 at L = 15, one standard error is 16-21 HDD ($320-430 per lot). We can only detect premia above ~35-45 HDD. 2010-26 data roughly halves that.
- October 2026 (in progress): the marks moved off climatology toward a warm end of month in ORD and CVG (table in section 4). Check the final Oct index after 2026-11-03 (2nd business day) against the 10-01 and 10-19..23 marks saved in cme-first-look/cme-settles/.
- CVG Q4, Kalshi vs CME. CME marks give a Q4 total of Oct 145 + Nov 530 + Dec 819 = 1,494. With a 30-yr sd of 192 for Oct 24-Dec 31, that gives P(Q4 < 1,450) ≈ 0.41; 10-yr climatology gives 0.14. Kalshi's "below 1,450" is quoted 0.61/0.64. The Kalshi ladder is non-monotone and stale away from 1,450. Basis, TWC hourly mean vs NWS (max+min)/2 at KCVG, Q4 totals: 2023 -10.7, 2024 +1.5, 2025 +10.4 HDD, daily sd 1.2-1.5. [calc, cvgq4.py, basis.py; IEM ASOS hourly]
- **First-look answer:** with free data the premium question cannot be answered. The key fact is that **most recent CME settles are not market prices**: no trades, so Tier-2 Speedwell 1-day moves or Tier-3 carry-forward. Asking "does the settle predict the outcome" today mostly tests Speedwell's forecast. Hedging pressure, if any, sits in block prices on Tier-1 days, and the $0.04-0.24 Databento pull would isolate those days.

## 8. Corrected rerun (2026-10-24; supersedes the original section 8)

**Verdict: inconclusive on hedging premia. No reliable mean settlement-proxy premium is demonstrated at approximate MDE 77.6 HDD / 34.9 CDD, with only four season clusters per index.** Settlement marks are not negotiated block prices. This analysis cannot identify how much of participants’ actual prices reflects hedging demand. The earlier “trades lean cold” claim is withdrawn.

The repaired activity class requires positive cleared volume, a date inside CME’s forecasting window, and a changed valid settlement. Snapshot-only days, activity with unchanged marks, and out-of-window rows are excluded from scored comparisons. Settlement receipt is limited to the assessment day; later volume reports label activity only. Outcomes use complete ACIS/GHCN months rather than the last post-month mark. Forecast inputs end at their assessment cutoff, and SEs match row-weighted means clustered by season.

The eligible universe is 492 complete-outcome contracts (230 HDD / 262 CDD), with sparse early coverage; fixed-lead paired panels retain 229/262, including 69/64 in the original three cities. The activity sample is 141 HDD days / 70 contracts and 74 CDD days / 39 contracts, four season clusters each. HDD settlement minus outcome is +9.7 DD (SE 18.6, illustrative CI [-49.6,+69.0]); CDD is -3.2 (SE 8.4, CI [-29.8,+23.5]). Normal 2.8×SE shortcuts give 52.2/23.5 DD, but the finite-cluster planning MDE is 77.6/34.9. The CDD settlement-minus-trend estimate is -4.9 (SE 2.4, CI [-12.7,+2.8]); the cold-lean sentence does not survive.

**The pre-registered MOS benchmark was finally run, original cities first.** Every row below has four seasons; nominal L=7 contains actual leads 7–9 and nominal L=1 contains 1–3.

| Original cities | L | Contracts | Settlement bias (SE) | RMSE settle / MOS | Mean-premium MDE DD |
| --- | --- | --- | --- | --- | --- |
| HDD | 7 | 69 | +2.2 (5.2) | 20.4 / 26.2 | 21.8 |
| HDD | 1 | 69 | -0.8 (1.0) | 6.3 / 4.6 | 4.1 |
| CDD | 7 | 64 | +4.7 (1.5) | 17.9 / 15.9 | 6.2 |
| CDD | 1 | 64 | +0.5 (0.7) | 5.5 / 3.9 | 2.7 |

Only HDD L=7 meets the descriptive registered “prices the outcome” inequality; the other cells are inconclusive. Paired squared-error CIs all include zero (MDEs 808/56 DD² for HDD L=7/L=1, 368/59 for CDD). The primary fixed-lead activity class has just one HDD L=7 row and none in the other cells, so the registered participant-price premium test is underpowered to the point of being unavailable. The 13-city secondary settle/MOS RMSEs are HDD 16.3/21.1 at L=7 and 5.6/3.8 at L=1; CDD 15.8/13.4 and 8.5/3.7. This does not establish incremental forecast value for design 2.

The 19 review-flagged extracted-final discrepancies are individually listed and replaced in the rerun; the largest are Dallas Aug-2023 CDD 720→863.5 and Minneapolis Aug-2023 CDD 168→300. All 32 prior differences >1 DD are disclosed. This repairs the outcome definition, without claiming every mismatch was an error in the official CME expiry index. Sacramento Feb/Jun-2026 incomplete outcomes are excluded.

Globex executions are evaluated separately: 39 HDD days (27 contracts, three seasons) give VWAP-minus-outcome -3.3 DD, SE 7.6, approximate MDE 40.5; 23 CDD days (17 contracts, three seasons) give -1.3, SE 4.1, MDE 22.2. These are 5,375 actual screen-traded lots. The residual from cleared volume is not a verified block share.

**Deviations and limits.** This is a reviewed-data repair, not a blind experiment. Relative to 7(b), activity eligibility and receipt timing are tightened, ACIS replaces extracted finals, season clustering replaces month clustering, and incomplete outcomes are dropped rather than backfilled. GFS extended MOS is used instead of NBM; the original-city sample is primary, 13 cities and all-lead activity are secondary; no 2010–22 extension is purchased. Missing volume means no reported positive activity. Burbank’s secondary trend fit has only 13–17 complete years in the trailing 30-year window. MOS initialization timestamps are archived, exact historical publication receipts are not. The settlement can use later intraday weather; a labelled hindsight day-T diagnostic does not establish equal-information-time skill. Current ACIS is not a historical vintage archive. With four clusters, intervals and MDEs are illustrative planning approximations and all inference is direction only.

See the [complete corrected report](cme-first-look/REDO.md) for season counts, actual leads, forecast mapping, every correction, deviations, source links, and reproducible artifacts. Existing data were reused; no paid calls, AWS actions, staging or commits.

<details>
<summary>Original section 8 — SUPERSEDED; retained for audit only</summary>

Every estimate and interpretation below is historical and superseded by the corrected rerun above, including “real trade prices,” the cold-lean claim, the broad Speedwell attribution, the block-share claim and the old MDEs.

## 8. The test, run (Databento pull 2026-10-24)
**Data.** Databento GLBX.MDP3 `statistics` (settles, cleared volume, OI) and `trades` (Globex prints) for all 26 US monthly HDD/CDD roots, 2022-10-01..2026-10-24. Cost re-checked just before the pull: $0.2420 (3.25M + 87 records). Files are 36.2 MB zstd in `data/raw/cme-weather/`. Databento flags 3 degraded days (2022-11-06, 2024-09-18, 2025-09-17). Station data: NOAA RCC-ACIS daily max/min, 1985-2026, for the 13 CME stations (`fetch_acis.py`). Analysis: `premium.py` and `premium_extra.py`; outputs `premium_rows.csv`, `premium_summary.json`, `premium_extra.json`. [read/calc]
- **Our index matches CME's final index.** Over 516 expired contracts, CME final minus ACIS (max+min)/2 sum: mean -0.5, mean absolute 1.0; 93.8% agree within 1 DD. [calc]
- **The three classes, over all pre-expiry contract-days** [calc]:
  - (a) **Real trade**: cleared volume > 0 or a Globex print. 502 days, 209,030 contracts. Only 62 of those days (8,976 contracts) had a Globex print, so **about 96% of traded volume is off-screen (blocks)**.
  - (b) **Mark inside the 15-day window**: 15,022 days. The settle changed on 80% of them.
  - (c) **Stale mark**: 141,877 days. The settle changed on 4%.
  - CME's own "actual vs theoretical" settle flag reads actual on 100% / 99% / 77% of the three classes, so it does not tell them apart.
- **Conventions.** Error e = price - final index; e > 0 means futures buyers paid more than the outcome. "Trend baseline" = observed-to-date plus a detrended burn for the rest of the month (same calendar day ±3 days over the prior 30 years, each year shifted by the station's linear warming slope). "10-yr" = plain 10-year burn. SEs are clustered by calendar month, because cities in the same month share weather.

| class, index, lead | e = price - final (SE) | trend baseline e (SE) | 10-yr e | price - trend baseline (SE) | RMSE price / baseline | months |
|---|---|---|---|---|---|---|
| (b) mark, HDD, 30 d | +18.8 (10.0) | +16.2 (12.4) | +26.4 | +2.6 (7.1) | 76 / 96 | 27 |
| (b) mark, HDD, 15 d | +3.6 (4.6) | +3.8 (9.5) | +9.7 | -0.1 (8.4) | 42 / 68 | 27 |
| (b) mark, HDD, 7 d | +2.2 (1.8) | +4.5 (6.6) | +6.4 | -2.3 (6.9) | 16 / 47 | 27 |
| (b) mark, HDD, 1 d | +0.2 (0.7) | +2.0 (2.4) | +3.0 | -1.8 (2.3) | 5.5 / 17 | 27 |
| (b) mark, CDD, 30 d | -0.4 (5.1) | +0.6 (5.6) | -7.7 | -1.1 (3.7) | 48 / 56 | 24 |
| (b) mark, CDD, 15 d | +5.1 (3.1) | +2.3 (4.6) | -2.1 | +2.8 (3.2) | 30 / 39 | 24 |
| (b) mark, CDD, 7 d | +4.0 (1.2) | +1.7 (2.6) | -1.0 | +2.3 (2.7) | 15 / 26 | 24 |
| (b) mark, CDD, 1 d | +1.4 (0.6) | +0.2 (1.0) | -0.9 | +1.2 (0.9) | 6.6 / 10.5 | 24 |
| (c) stale, HDD, 60 d | +29.3 (14.1) | +13.5 (12.7) | +23.7 | +15.8 (6.9) | 107 / 96 | 25 |
| (c) stale, HDD, 90 d | +25.3 (14.7) | +13.7 (15.1) | +22.1 | +11.5 (4.1) | 103 / 95 | 21 |
| (c) stale, CDD, 60 d | -8.0 (5.8) | +1.5 (5.7) | -7.0 | -9.5 (1.5) | 57 / 56 | 24 |
| (c) stale, CDD, 90 d | -10.5 (5.9) | +0.6 (5.7) | -7.9 | -11.1 (1.3) | 57 / 55 | 23 |
| (a) **trades, HDD, all leads** (291 days, 96 contracts, 109k lots) | **+2.0 (15.2)**; vol-weighted +7.8 | -5.8 (17.3) | -1.4 | **+7.7 (4.5)** | | 25 |
| (a) **trades, CDD, all leads** (211 days, 77 contracts, 100k lots) | **-4.0 (7.6)**; vol-weighted -8.3 | +4.9 (8.5) | -9.7 | **-8.9 (2.4)** | | 20 |

Fixed-lead rows for class (a) have 1-9 contracts each and are in `premium_summary.json`; they are too few to read. Leads 30/15/7/1 always fall inside the window, so class (c) only shows up at 60/90 days. [calc]

**Plain answers (4-year sample, 2022-10..2026-10)**
1. **Real trade prices show no premium against the outcome that this sample can detect.**
   - HDD trades land +2 HDD above the final (SE 15); CDD trades land -4 CDD below (SE 8). Trade prices sit above the final on 50% of HDD trade days and 44% of CDD trade days.
   - **Against our trend forecast, trades lean cold**: HDD priced +8 above it (1.7 SE), CDD priced -9 below it (3.7 SE). If that lean is a premium, it is paid by whoever is long cold (HDD buyers, CDD sellers) to whoever is long warmth. But against the outcome the lean is inside noise. It looks more like traders using less warming than our trend than like hedging pressure.
2. **Yes, the window marks are just the forecast, and a good one.**
   - They are unbiased within 0-5 DD at 15/7/1 days, and correlate 0.99+ with the final.
   - Their RMSE is 35-62% of our climatology baseline's at 15/7/1 days (HDD 42/16/5.5 vs 68/47/17). Speedwell's forecast is far better than climatology.
   - There is one small, significant bias: CDD marks run high, +4.0 at 7 days (3.3 SE) and +1.4 at 1 day.
3. **Stale far-month marks look like plain 10-year normals with no warming adjustment.**
   - HDD marks are +25 to +29 above the outcome, close to the 10-year baseline's +22 to +24. CDD marks are -8 to -10 below, close to the 10-year baseline's -7 to -8.
   - They sit 10-16 DD colder than the trend forecast (HDD: 2.3-2.8 SE; CDD: 6-8 SE).
   - They are not traded prices. Far-month trades (61-120 days) show no HDD lean (+1.0 ± 4.6) but a CDD lean of -14 ± 2.9 against the trend forecast (-1 ± 8 against the outcome).
4. **Minimum detectable premium** (80% power, 5% two-sided, 2.8 x SE):
   - Against the outcome: **about 43 HDD (~$850 per lot, ~5-10% of a winter month) and about 21 CDD** on trade days.
   - Against the trend forecast: 12.5 HDD / 6.7 CDD.
   - For window marks against the outcome: 13 HDD at 15 days, 5 at 7 days.
   - Adding 2010-22 (`statistics` for 2010-26, 20 roots, priced at $0.36 earlier) would roughly double the months and cut these by about 30%.

**Caveats.** "Trade price" here is CME's settle on a day with cleared volume (Tier 1 anchors to that day's activity). It is not the negotiated block price, which MDP3 does not carry. Cleared volume can include EFR/EFP and exercises. Options and seasonal strips are not in this test, and they hold 64k of the 100k weather OI. Four years of mostly warm winters dominate the errors. The trend baseline is ours; its own errors (HDD -6 ± 17, CDD +5 ± 9) are inside noise.

</details>

## What this implies (2-3 trade designs)
1. **Kalshi KXHDDCVG priced off CME H3 marks plus a forecast model.** CME is a free fair-value input; we trade only the Kalshi leg, buying "No" on rungs where Kalshi's mid is far above the CME/model probability (now "below 1,450" at ~0.62 vs ~0.41). Main risks: a 2+ month hold, which breaks the owner's ~1-day hold rule; a thin book (OI ≤ 579 per rung, spreads up to 89 cents); the hourly-mean vs midrange basis (±11 HDD per quarter); and a Dec CME mark frozen at 819 outside the forecast window.
2. **Daily Kalshi ladders in the 6 same-station cities (ATL, BOS, DFW, LAS, MSP, PHL), using the CME/Speedwell current-month 1-day change as a feature.** Back out the implied rest-of-month mean temperature from it, net out Kalshi's implied next-day highs and lows, and trade Kalshi rungs when the two disagree. Main risk: the CME number is a month aggregate published after 15:00 CT from the same NWP runs Kalshi traders see, so it probably adds little. It also needs a daily settle archive (the free API keeps 5 days) or the $0.24 Databento history, and the Kalshi recorder restarted.
3. **True two-venue pair: short a CME monthly HDD block vs long a strip of Kalshi daily high/low ladders, sized by a DL model of the monthly index.** Main risk: the CME leg alone is a 20-lot block (~$56k sd per month) through an FCM, and the screen does not trade. That is three orders of magnitude over the owner's tens-of-dollars live cap. NY and Chicago settle at different stations on the two venues. Not feasible now; the realistic version is design 1 or 2, with CME as a signal and not a leg.
