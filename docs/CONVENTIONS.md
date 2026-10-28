# Point-in-time and payout conventions (v2)

v2 written 2026-09-30 after the Phase 1 research and pulls (plan 01-06). This file is the single place where day, close-time and settlement conventions live. Every later phase (data pulls, evaluation, engine, oracle adapter) follows it; code comments point here instead of restating it. If a convention changes, record the deviation here with a date; do not edit silently.

Sources: `.planning/PROJECT.md`; `.planning/phases/01-data-foundation/01-RESEARCH.md` (cited as R1 with section or pitfall number); `01-02-REPORT.md` and `01-03-REPORT.md`; `.planning/phases/07-protocol-spec-engine/07-RESEARCH.md` (R7); `.planning/phases/03-geography-residual-bakeoff/03-RESEARCH.md` (R3); `prior/hl-mm-ins/reports/ins1/README.md`, `prior/hl-mm-ins/reports/ins2/README.md`, `prior/hl-mm-ins/reports/ins1/analyze.py`, `prior/hl-mm-ins/PREREG-EXCERPTS.md`. Section numbers 1-8 are unchanged from v1; 9-13 are new.

## 1. Time and the CLI day

- All timestamps are UTC (`datetime` with `tzinfo=UTC`, epoch seconds, or ISO-8601 with `Z`). No naive datetimes, no local-time dates in joins. Trip data (Citi Bike, Divvy, TLC) arrives as naive local clock time; convert before joining (R1 Pitfall 10).
- **The CLI day is the join key everywhere.** It is midnight to midnight local standard time: EST = UTC-5 (NYC, EWR, TTN, MIA), CST = UTC-6 (Chicago), fixed offsets all year, no DST. Build it with `timezone(timedelta(hours=-5))` / `-6`, never `America/New_York` (R1 Pattern 3, Don't Hand-Roll; R7 Pitfall 2). In summer the window is 01:00 to 01:00 local clock time.
- A "market day" is the date in the Kalshi event ticker (`KXHIGHNY-26SEP28` is 2026-09-28). It is the NWS climate day, not derived from the close time.
- Horizons before close are measured from the market's `close_time` (section 2), in UTC.
- Station sources (NWS CLI, GHCN-D first-order stations, IEM `daily.py`) are already on the CLI day. Grids are shifted by section 3. Sales data is aggregated on the local clock day and the 1 h DST offset is documented, or aggregated on LST.

## 2. Kalshi close times

Close times changed over the history. **Never hard-code a close time, and never write "Chicago closes 06:00Z, the others 03:59Z". Always read `close_time` from the market object** (`markets.parquet`). Sources: R1 "Market mechanics" and Pitfall 3; 01-02 report finding 1; R7 Pitfall 2. The switch dates below were read off `data/cache/kalshi/markets.parquet` on 2026-09-30 (first market close date with the new value, `KXHIGHNY` / `KXHIGHCHI` / `KXHIGHMIA`).

| period (by `close_time` date) | NY / MIA / EWR / TTN daily | CHI daily |
|---|---|---|
| start to 2026-03-18 | 23:59 **ET** wall clock: 03:59Z in EDT (mid-Mar to early Nov), 04:59Z in EST. Seen: 03:59Z until 2021-11-08, 04:59Z until 2022-03-14, and so on each year | 23:59 ET until 2025-02-20 (same UTC values as NY); from 2025-02-21 23:59 **CT**: 05:59Z in CST, 04:59Z in CDT |
| 2026-03-19 to 2026-08-14 | fixed 04:59Z all year (= 23:59 EST) | fixed 05:59Z all year (= 23:59 CST) |
| 2026-08-15 onward | fixed **05:00Z** (= 00:00 EST) | fixed **06:00Z** (= 00:00 CST) |

- Only the last row coincides with the end of the CLI day (midnight LST) in every month. Before it, the EDT-season close is 03:59Z, an hour before the CLI day ends, and the other closes are one minute short of it. Hedge-decision times must come from `close_time` per market; a join keyed on a constant mis-times the decision by an hour or a minute (R7 Pitfall 2).
- Deviation from the plan brief, 2026-09-30: the brief (and R1) put the switch to a fixed close at "2026-07/08". The pulled markets show two steps: a fixed 23:59-EST-equivalent close from 2026-03-19, then 00:00 LST from 2026-08-15. The 2021-11-27 markets close at 16:59Z (one-off, also present in NY and CHI); treat any off-pattern close as data, read it, do not correct it. MIA has a few one-off closes in 2023 (04:29Z, 04:15Z).
- Weekly and monthly rain series show 03:59Z / 04:59Z closes (monthly) and irregular times (first listing day, e.g. 14:13Z); read `close_time` there too (R7 Pitfall 2 reports weekly/monthly at 03:59Z).
- Daily markets open at 14:00Z or 15:00Z on the day before and live about 38 h.

## 3. Grid day labels (nClimGrid and PRISM)

- **Rule: calendar (CLI) day X is read from grid label X+1, for tmax and tmin, for both nClimGrid and PRISM.** Equivalently `cli_day = label_day - 1 day`. Never join grid label D to an ASOS/Kalshi date D. The one implementation lives in `align.py` (R3 "Day alignment"); do not scatter offsets.
- nClimGrid-Daily documents each value as "the 24-hour period ending in the early morning of the specified day". PRISM day is 1200 UTC to 1200 UTC, day-ending label (the 2 Jul grid covers 12Z 1 Jul to 12Z 2 Jul) (R1 Pitfall 6).
- Evidence, nClimGrid (ins2 README, deviation 2): nearest cell vs ASOS calendar-day max, RMSE in degF for NYC / EWR / TTN / MDW / MIA: label D vs ASOS D 4.6 / 4.7 / 4.2 / 5.2 / 2.3 (corr 0.57-0.74); label D vs ASOS D-1 (calendar D = label D+1) 1.7 / 1.6 / 1.1 / 1.6 / 1.1 (corr 0.92-0.98). The unaligned run (`prior/hl-mm-ins/reports/ins2/results_label_day_unshifted.*`) has median cell HE -0.96 to -0.09 and is kept only as evidence.
- Evidence, PRISM tmax (R1 Pitfall 6, measured 2026-09-30): nearest 4 km cell at NYC/EWR/TTN/MDW/MIA/LGA/JFK, 2026-07-29..08-03 (n = 42): label D vs station calendar D-1 gives RMSE 1.07 degF, bias 0.00; unshifted gives 4.27 degF.
- Even aligned, the nearest cell has RMSE 1.1-1.8 degF against ASOS. Treat a grid value as a noisy proxy, not a copy of the station.
- **Precip grids cannot be mapped exactly.** PRISM ppt and Stage IV 24 h are 12Z to 12Z (07:00 to 07:00 EST), so a CLI calendar-day rain total straddles two grid labels; the label D+1 map overlaps the CLI day by about 17 h of 24. nClimGrid prcp mixes station observation times. Either accept the 12Z-12Z window and report it as a basis, or build calendar-day sums from hourly Stage IV / MRMS (05Z to 05Z EST, 06Z to 06Z CST). Weekly rain: calendar Mon-Sun maps to labels Tue-Mon (R3 Pitfall 1).
- The grid vintage (prelim / scaled for nClimGrid, grid count for PRISM) must be stated for any settlement or evaluation on gridded data (section 11).

## 4. Settlement source and value

- **Source by close date (R1 Pitfall 3).** Markets closing on or before 2026-08-14 settle on the NWS Climatological Report (CLI). From closes on 2026-08-15 they settle on The Weather Company (TWC) figure "for the same CLI station", with the fixed close in section 2. NY before 2022-03-05 and Chicago before 2025-03-06 use older rule wording that names no source. Carry a `settle_source` column (`NWS` / `TWC` / empty) parsed from `rules_primary`.
- **`expiration_value` is the truth** for the settled number. It is empty on some markets in 2022-2025 (at event level 64-73 of about 1,870 events lack it); derive those from `result` plus the strikes. Legacy temperature markets carry no `floor_strike` / `cap_strike` in the API; `markets.parquet` rebuilds them from ticker and subtitle (`strike_source = ticker`, 99.85 % consistent with `expiration_value` and `result`) (01-02 report, finding 3).
- TWC values have no public archive. NWS-vs-TWC mismatch counts must be reported separately from NWS-era checks. The ins1 sample (272 city-days since 2026-07-24) mostly covers the NWS-rule era, not TWC (01-02 report, finding 2).
- ins1 sample of settled bracket vs NWS ASOS daily max (IEM) at the same station, 272 city-days:

| ladder | mismatches |
|---|---|
| NYC Central Park | 0 / 68 |
| Chicago Midway | 1 / 68 |
| Miami | 3 / 68 |
| Newark EWR | 0 / 34 |
| Trenton TTN | 1 / 34 |

Total 5 / 272 (1.8 %); Miami is 4.4 % on the raw count. Ladder payout is the truth for the hedge leg; the station value is the truth only for the exposure a business experiences at the airport. Keep both columns (`ladder_pay`, `H_nws`) in every join; never substitute one for the other.
- Settlement-grade values: `expiration_value`, then IEM `json/cli.py` (table `data/cache/weather/official_daily.parquet`), then GHCN-D. IEM `daily.py` only as in section 8.

## 5. Executable prices, candles and the ladder edges

- Use the YES ask and bid from hourly candle closes, never mid, for the price paid.
- **Two candle schemas (R1 Pitfall 5).** The historical tier uses `yes_ask.close`, `volume`, `open_interest`; the live/batch tier uses `yes_ask.close_dollars`, `volume_fp`, `open_interest_fp`. Normalize both to floats in dollars before any join. The price block is null when there are no trades. The batch `/markets/candlesticks` returns `{"markets":[]}` with HTTP 200 for historical tickers; it fails silently.
- **Forward-fill rule for the ask at t-24h / t-12h / t-2h:** take the last candle with `end_period_ts <= t` (t = `close_time` minus the horizon, UTC). No candle after t is ever read. Hours with no quote change are absent (MEDIUM: observed behaviour, not documented), so a missing hour means "unchanged", not "no price". On the live endpoint pass `include_latest_before_start=true`.
- Order books list bids only; YES ask = 1 - best NO bid. Recorded arrays are ascending (best last); sort and parse explicitly and assert best ask >= best bid (R7 Pitfall 4).
- **No-offer rule:** ask >= 99c and bid < 90c (or ask <= 0). The rung cannot be bought; exclude it from the replicating portfolio and report it as a liquidity failure, not as a zero price.
- **Ladder edges:** the top open-ended bracket ("greater than") is valued at its floor + 1; the bottom "less than" bracket is valued at cap - 1 when the exposure is a put. A fixed strike inside the open top bracket gets f(floor+1) = 0 hedge that day (R7 Pitfall 5); report the unhedged-tail share.
- Decision horizons for premium: 24 h, 12 h and 2 h before close. Report all three; 24 h is the headline (pre-registered in ins1 T1).
- Spread cost = sum over contracts of (ask - mid).

## 6. Payout and hedge effectiveness

- Capped linear heat payout per $1 per degF unit: `H(T) = min(max(T - K, 0), 6)`, T the daily high in whole degF. K = floor strike of the ladder's second bracket, so the ladder spans the payoff (ins1).
- Replicating portfolio: for each bracket contract, buy H(bracket midpoint) YES contracts at the YES ask (about 19.5 contracts per $1/degF unit ladder). Top open bracket valued at floor + 1.
- **Two hedge-effectiveness definitions; both must always be reported.**
  - `HE_cover = 1 - var(exposure - payout) / var(exposure)`: ladder payout vs the business loss, ignoring what the ladder cost.
  - `HE_ladder = 1 - var(exposure - (payout - ask premium - fees)) / var(exposure)`: the same with the executable premium and Kalshi fees netted off per day.
  Exposure is the payout H at the location the buyer cares about (`H_nws` at the airport, or H at another station or cell); the hedge leg is `ladder_pay`. HE is computed on the same days for every comparison, any fitted offset or ratio is labelled in-sample, and hold-out days never enter a fitted hedge ratio.
- Binning error = H(T) - ladder payout (piecewise-constant vs linear).

## 7. Stations

- **Settlement stations and what they settle (R1 Pitfall 4).** Chicago temperature (`KXHIGHCHI`, `KXLOWTCHI`) and monthly rain (`KXRAINCHIM`, mostly) settle at **Midway (CLIMDW)**. Chicago daily rain (`KXRAIN` Chicago), weekend rain and monthly snow settle at **O'Hare (CLIORD)**. `KXRAINCHIM` has 7 markets at CLIORD, so keep a per-market station column parsed from `rules_primary` (the `CLI\w{3}` token) and never assume one station per city.
- Other settlement stations: NYC Central Park (CLINYC; `KXHIGHNY`, `KXLOWTNYC`, `KXRAINNYC`, `KXRAINNYCM`), Newark EWR (CLIEWR; `KXHIGHTEWR`), Trenton TTN (CLITTN; `KXHIGHTTTN`), Miami MIA (CLIMIA; `KXHIGHMIA`). Palm Beach is **DJT** (IEM `FL_ASOS` id; `PBI` returns "not found"; Kalshi `CLIDJT`; GHCN `USW00012844`), not PBI (R1 Pitfall 9).
- `KXRAINNY` (2021-08 to 2021-09) settles on the Hudson River Pier 26 gauge, not Central Park: exclude it.
- Nearby comparison stations (IEM ASOS): NYC with LGA and JFK; EWR and TTN with each other; MDW with ORD; MIA with FLL and OPF. Grid cells: cell centres within 40 km great-circle of a settlement station with data on all days (ocean cells are masked).
- Precip is unusable at MMU, GYY, BLM and HST (gauge absent for long stretches); BLM has no current GHCN record (R1 Pitfall 9, 01-03 report).

## 8. IEM daily-summary vs the NWS CLI (plan 01-03, corrected 2026-09-30)

- Source: IEM backend docs for `/cgi-bin/request/daily.py` and `/request/daily.phtml`. The `day` column is a local calendar-date label; for airport ASOS the window is local standard time midnight to midnight, the same window the NWS climate day uses (section 1). The windows match, the values do not.
- **Measured on the pulled tables** (2023-01-01 to 2026-09-29, `stations_daily.parquet` vs `official_daily.parquet`, five settlement stations, tmax):
  - 2023-01 to 2025-09: IEM equals the CLI high on only 32-53 % of station-days per quarter and is lower on 47-67 %, almost always 1 degF (R1 Pitfall 2: Central Park 2025, 158 of 363 days differ, 122 of them 1 degF low, 17 at 2 degF low). Worst in Q2 and Q3, best in Q4 and Q1.
  - **2025-10 to 2026-09: equal on 100 % of station-days in every quarter** (about 1,820 station-days, zero differences). The all-period figure in earlier notes (50-64 % exact, mean -0.4 to -0.6 degF) averages these two regimes; it is not a steady bias.
  - Precipitation agrees within 0.01 in on 99-100 % of days over the whole period.
  - Two single-day outliers (NYC 2024-12-29, 8 degF; EWR 2025-12-07, 19 degF) exist between IEM and CLI; not investigated. A likely cause of the pre-2025-10 gap is unrecorded intra-hour peaks and Celsius rounding in the stored observations; not tested.
- **Rules.** (1) Settlement-grade values come from `expiration_value`, then the CLI table, then GHCN-D (USW ids in R1 "GHCN-Daily"; matches the CLI 357/363 days at Central Park 2025, 6 misses are the degC round trip). Never check a Kalshi settlement against `daily.py` tmax before 2025-10. (2) `daily.py` tmax/tmin is usable as-is from 2025-10 onward, and for precip at any date where the gauge exists. (3) Nearby non-settlement stations before 2025-10: IEM CLI JSON where the station issues a CLI (LGA, JFK, ISP, EWR, TTN, ORD, MDW, PWK, DPA, UGN, FLL, MIA), GHCN-D otherwise (HPN, FRG, TEB, CDW, OPF, TMB, HWO, DJT). Using `daily.py` there builds a fake basis of about +1 degF into the geography comparison for 2021-2025.
- Missing values are kept as NaN with `*_missing` flags; trace precipitation is 0.0001 and flagged `precip_trace`. The last loaded day is the last complete UTC-yesterday; today's partial row is never loaded.

## 9. Kalshi rain and other contract types

- **Daily rain on Kalshi is a single binary "> 0 in" per city-day, not a ladder** (R1 Summary finding 4). Series: `KXRAINNYC` 2021-09 to 2022-08 and 2025-01 to 2026-07-15 (gap 2022-09 to 2024-12); `KXRAIN` (multi-city, one market per city-day, TWC) from 2026-07-15 (NYC/CHI/MIA) and 2026-08-27 (EWR/TTN). Weekend rain (`KXRAINWKND`, from 2026-08-22) is also a binary. `KXRAINNYCW`, `KXRAINDNYC`, `KXRAINSNYC` are one-off 2026-09 events, too thin to use.
- **Rain ladders exist only monthly:** `KXRAINNYCM` (2024-02 onward), `KXRAINCHIM` (2025-06 onward), `KXRAINMIAM` (2025-11 onward).
- Temperature ladders: high (`KXHIGH*`) and low (`KXLOWT*`); the low series start 2025-12-13 (NYC/CHI/MIA) and 2026-08-26 (EWR/TTN). Pre-KX tickers (`HIGHNY-*` etc.) are served under the KX `series_ticker`; `series_ticker=HIGHNY` returns zero markets (R1 Pitfall 1 and Anti-Patterns).
- Series discovery must not filter on `category=Climate and Weather`: it misses `KXHIGHNY0` and `KXRAINNY`, filed under "World".
- Out of scope: hourly-directional series (`KXTEMPNYCH` and relatives, about 99,000 markets), seasonal hurricane and snow one-offs.

## 10. Kalshi taker fee

- Taker fee per order = ceil to the cent of `0.07 x C x P x (1 - P)`, C contracts, P the price in dollars. **Confidence MEDIUM:** several secondary sources agree; the official fee PDF could not be fetched (R7, Open Question 4; HTTP 429 / HTML). Confirm the schedule, the per-order rounding and whether fractional contracts trade before any number built on it leaves the repo.
- Round once per order, not per price level. Five rungs can cost up to 5c of rounding on a policy worth a few dollars (R7 Pitfall 15). ins1 premiums exclude fees and must not be reused as costs.

## 11. Revision lifecycles

Source: R1 Pitfall 7.

- **nClimGrid prelim:** the open-month prelim file is updated daily, about 2 days behind. The first scaled file appears at about the 4th-7th of M+1, is re-created at M+2 and M+3 (June 2026: c0706, c0806, c0904, c0905, c0906), and is frozen after about M+3 with rare later reprocessing. NCEI keeps only the current file. **The AWS mirror (`s3://noaa-nclimgrid-daily-pds/`) keeps prelim and superseded complete vintages** (148 prelim tarballs since 2026-04-21), so first-publication vs final can be measured for about April to September 2026; ins2's "no vintage archive" is true of NCEI only. Keep every prelim file with md5 and the `ncdd-YYYYMM-version.txt` creation date.
- **PRISM:** grid count 1 about 24 h after the day ends, count 2 at about +5 days, count 3 at the monthly update (about the 15th-22nd of M+1), counts 4-8 at the next five monthly updates. Count 8 is final (older than 6 months is stable). **PRISM keeps no prior versions**, so revision can only be measured going forward by snapshotting. Define revision by grid count, not by the legacy early/provisional/stable names (mapping LOW confidence).
- **NWS CLI:** a preliminary at about 5 pm ("VALID TODAY AS OF 0400 PM"), the final at about 2 am, and occasional corrections (1 Jan 2026 re-issued 11:06 am 2 Jan). `json/cli.py` points at the latest product; `afos/retrieve.py` returns every issuance. The dispute window for engine settlement is D+2 12:00Z (R7 Pattern 1).
- Any settlement or evaluation on revised data states which vintage it uses.

## 12. Rate limits and fetching

Source: R1 "Keyless rate limit" and Pitfall 8. Limits are shared across every worker on this Mac; give each source one fetch process.

- **Kalshi:** at most 4 requests per second per IP, shared across workers (measured: 5 req/s gives 2 of 40 429s, 8 req/s gives 24 of 64; no Retry-After header; MEDIUM, single measurement). Back off on 429/5xx.
- **IEM:** sequential, at least 60 s between bulk requests, year-sized chunks (multi-year requests return 503 "server over capacity"). An error body can arrive with HTTP 200 (`ERROR: station: PBI not found ...`); validate the CSV header.
- **PRISM:** at least 2 s between files and never the same file twice in 24 h (the second download is blocked for the rest of the period; repeated excess can get the IP blocked).
- NCEI and the AWS mirror: polite and sequential.
- Disk is tight (6 GB free at 2026-09-30, one full-disk abort already): stream, subset, delete raw grid files (R1 Pattern 4).

## 13. Units and representations

| quantity | stored as |
|---|---|
| temperature | integer degF tenths (`tmax_f_tenths`); whole degF for settlement values |
| precipitation | integer inch hundredths (`prcp_hundredths_in`); trace = 0.0001 in in the IEM float tables, flagged `precip_trace` |
| money on chain and in the engine | integer USDC base units, 1e6 per USDC; floats only inside pricing outputs, rounded explicitly to ticks before becoming events (R7 Pattern 11) |
| Kalshi prices | dollars, 0.01 tick in the candle tables; cents only inside fee arithmetic |
| dates | days since the Unix epoch for on-chain indices; ISO date for `cli_day`, `label_day`, `event_date` |
| timestamps | UTC epoch seconds, or tz-aware UTC in Parquet |

---

Changelog: 2026-09-30 v2 (plan 01-06): CLI day as join key; close times and settlement source made time-varying (read `close_time`, carry `settle_source`); rain contract types, fee, revision, rate-limit and units sections added; section 8 corrected (IEM equals the CLI from 2025-10, not a steady -0.5 degF bias).
