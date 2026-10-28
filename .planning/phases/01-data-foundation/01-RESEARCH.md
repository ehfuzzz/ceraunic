# Phase 1: Data foundation - Research

**Researched:** 2026-09-30 (07:45Z–08:40Z, live probes from this Mac)
**Domain:** Data access for Kalshi weather markets, US station and gridded weather (IEM/NWS CLI, GHCN-D, nClimGrid-Daily, PRISM, Stage IV/MRMS), public demand proxies, Census business counts
**Confidence:** HIGH for access paths and history coverage (every path below was fetched and the response recorded); MEDIUM for licence and throughput estimates; LOW where flagged

## Summary

Every source the evaluation needs can be pulled without an account, with two exceptions. The **Census data API now requires a key on every request**, so use the keyless bulk ZBP/CBP files. **Kaggle sets** (Rossmann, Favorita) need `~/.kaggle/kaggle.json`, which is not on this Mac, so they are owner-hand and ranked low anyway. Kalshi's keyless API has settled markets and hourly bid/ask candles back to the first market of each series: NYC high from 2021-08-06, Chicago from 2021-08-19, Miami from 2023-05-11. Markets that settled before the moving **historical cutoff (now 2026-08-01)** are served only by `/historical/*` endpoints. That is why ins1 found only 68 days: it used the live endpoints. Old tickers (`HIGHNY-*`, `HIGHCHI-*`, `HIGHMIA-*`, `RAINNYC-*`) sit under the KX series ticker in the historical endpoint. Querying `series_ticker=HIGHNY` returns nothing.

Four findings change the plan compared with what PROJECT.md assumes:

1. **nClimGrid does have a vintage archive, on the AWS Open Data mirror.** `s3://noaa-nclimgrid-daily-pds/archive/2026/` holds 148 daily prelim tarballs (2026-04-21 → today, 6.2 GB) plus superseded "complete" versions. `access/grids/2026/` keeps old prelim `.nc` files for 2026-04 through 2026-08. So prelim → scaled revision risk can be measured now for about April–September 2026. ins2's "no vintage archive" statement is wrong for the mirror, though right for NCEI itself.
2. **IEM `daily.py` max/min at Central Park differs from the NWS CLI (the settlement value) on 43.5 % of 2025 days**, almost always 1 °F low. From 2025-10 on it matches exactly. Any pre-Oct-2025 station comparison built on `daily.py` has a fake basis built in. Use IEM's parsed CLI (`json/cli.py`), Kalshi's `expiration_value`, or GHCN-Daily (357/363 matches) instead.
3. **The settlement source and the close time changed mid-history.** NWS CLI was the source for markets closing up to 2026-08-14. From 2026-08-15, markets settle on "The Weather Company" figure for the same CLI station, and closes move to a fixed 05:00Z (06:00Z Chicago). Earlier closes were 23:59 local clock time. **Chicago daily rain (KXRAIN) settles at O'Hare (CLIORD)**, while Chicago temperature and monthly rain settle at Midway.
4. **Daily rain on Kalshi is a single binary ">0 inches" per city-day** (KXRAIN since 2026-07-16; KXRAINNYC 2021–22 and 2025-01–2026-07), not a ladder. Rain ladders exist only monthly (NYC since Feb 2024, Chicago since Jun 2025, Miami since Nov 2025).

**Primary recommendation:** Build every station and grid join on the CLI day (midnight to midnight local standard time) keyed to Kalshi's `expiration_value`. Pull Kalshi through the historical plus live tiers at ≤4 requests/s with a shared token bucket. Snapshot the nClimGrid AWS vintages today, before the mirror prunes them.

## Standard Stack

### Data sources (all keyless unless marked)
| Source | Endpoint root | Purpose | Confidence |
|---|---|---|---|
| Kalshi Trade API v2 | `https://api.elections.kalshi.com/trade-api/v2` | series/markets/settlements/hourly candles/trades/books | HIGH (probed) |
| IEM parsed NWS CLI | `https://mesonet.agron.iastate.edu/json/cli.py` | settlement-grade daily high/low/precip per CLI station | HIGH (probed) |
| IEM AFOS text archive | `https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py` | every CLI issuance (5 pm prelim, 2 am final, corrections) | HIGH (probed) |
| IEM ASOS daily | `https://mesonet.agron.iastate.edu/cgi-bin/request/daily.py` | nearby-station daily max/min/precip (see pitfall 2) | HIGH (probed) |
| NOAA GHCN-Daily | `https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/access/{ID}.csv` | CLI-consistent daily TMAX/TMIN/PRCP for all first-order stations | HIGH (probed) |
| nClimGrid-Daily (NCEI) | `https://www.ncei.noaa.gov/data/nclimgrid-daily/access/grids/{YYYY}/` | 1/24° daily grids, current version only | HIGH (probed) |
| nClimGrid-Daily (AWS mirror) | `s3://noaa-nclimgrid-daily-pds/` (`--no-sign-request`) | same plus retained prelim/complete vintages | HIGH (listed) |
| PRISM (web service) | `https://services.nacse.org/prism/data/get/us/4km/{var}/{YYYYMMDD}` | 4 km daily tmax/ppt/tmin grids | HIGH (probed) |
| PRISM (file tree) | `https://data.prism.oregonstate.edu/time_series/us/an/4km/{var}/daily/{YYYY}/` | same files as a browsable directory | HIGH (listed) |
| Stage IV (IEM archive) | `https://mesonet.agron.iastate.edu/archive/data/{YYYY}/{MM}/{DD}/stage4/` | radar+gauge precip, hourly and 12Z–12Z 24 h | HIGH (listed) |
| MRMS (IEM mtarchive / AWS) | `https://mtarchive.geol.iastate.edu/{YYYY}/{MM}/{DD}/mrms/ncep/`, `s3://noaa-mrms-pds/CONUS/` | radar QPE 1 h/24 h/72 h Pass2 | HIGH (listed) |
| Census ZBP/CBP bulk | `https://www2.census.gov/programs-surveys/cbp/datasets/2023/` | establishments by NAICS × ZIP (2023 latest; 2024 folder empty) | HIGH (downloaded) |
| Census data API | `https://api.census.gov/data/{yr}/cbp` | **needs key: owner-hand** | HIGH (302 → missing_key.html) |
| Citi Bike / Divvy S3 | `https://s3.amazonaws.com/tripdata/`, `https://divvy-tripdata.s3.amazonaws.com/` | station-day demand proxies | HIGH (listed + sample) |
| NYC TLC | `https://d37ci6vzurychx.cloudfront.net/trip-data/` | taxi zone-day demand | HIGH (HEAD) |
| Socrata (Chicago, NY) | `data.cityofchicago.org`, `data.ny.gov`, `data.cityofnewyork.us` | CTA, MTA, bike counters, Chicago taxi | HIGH/MEDIUM (probed) |
| hl-mm recorder | `s3://hlmm-reduced-5325/kalshi-weather-books/` | recorded order books | prefix **not present yet** at 08:0xZ; this Mac's AWS CLI can list the bucket |

### Python (already in `pyproject.toml`; nothing new required for the core)
| Library | Purpose | Note |
|---|---|---|
| requests + urllib3 `Retry` | all HTTP with backoff on 429/503 | built-in retry adapter, no hand-rolled loops |
| netCDF4 / xarray | nClimGrid `.nc`, PRISM via `?format=nc` | avoids adding rasterio/GDAL for PRISM COGs |
| pyarrow + duckdb | Parquet partitions, trip-data aggregation, manifests | duckdb reads TLC parquet and zipped CSV fast |
| pandas / numpy | panel assembly, haversine discs | |
| hashlib, zoneinfo (stdlib) | md5 manifests; local-clock vs LST conversions | |

### Supporting (only if Phase 3 needs calendar-day gridded rain)
| Library | Purpose | When |
|---|---|---|
| `eccodes` (pip wheel) + `cfgrib` | read Stage IV / MRMS GRIB | only for hourly Stage IV/MRMS; not needed for nClimGrid/PRISM. MEDIUM: wheel availability on py3.14/arm64 not checked |

### Alternatives Considered
| Instead of | Could use | Tradeoff |
|---|---|---|
| IEM `json/cli.py` for settlement stations | Kalshi `expiration_value` | identical where present (0/71 mismatches, NYC 2026); missing on ~3–4 % of historical events; use both |
| IEM `daily.py` for nearby stations | GHCN-D per-station CSV | GHCN-D matches CLI; lag ~8 days; °C tenths (round-trip rounding gave 6/363 mismatches) |
| PRISM COG (`.tif`) | `?format=nc` | nc reads with netCDF4 already installed; same 2-downloads-per-file-per-24 h limit |
| Census API | ZBP bulk `zbp23detail.zip` | bulk is keyless, 15.7 MB zip / 291 MB txt; no employment counts at ZIP level (size-class counts only) |

**Installation:** none for the core. Optional: `uv add eccodes cfgrib` (only if Stage IV/MRMS is pulled).

## Kalshi weather inventory (five cities) — verified 2026-09-30

Pulled by paginating `/markets?series_ticker=S` (live tier) and `/historical/markets?series_ticker=S` (historical tier). Tickers were deduplicated: 48 KXHIGHNY tickers appear in both tiers. "Events" means market-days. Series discovery used `/series` with no category filter: 14,494 series, 18 MB, 3 s. The `category=Climate and Weather` filter misses the 2021 prequel series filed under "World".

| Series | Underlying | Settlement station and source | First market day → last | Events / markets | Candles verified | Notes |
|---|---|---|---|---|---|---|
| **KXHIGHNY** (+`HIGHNY-*` tickers ≤ 2024-10-23) | daily high | Central Park (CLINYC). NWS CLI until closes ≤ 2026-08-14, then TWC "for CLINYC" | 2021-08-06 → 2026-09-30 (open) | 1,878 / 9,658 | 2021, 2023, 2026 | 144/365/364/366/365/274 events 2021…2026 |
| KXHIGHNY0 (category World) | daily high | Central Park | 2021-07-17 → 2021-08-05 | 21 / 21 | not tested | prequel, single strike per day |
| **KXHIGHCHI** (+`HIGHCHI-*`) | daily high | **Midway (CLIMDW)**; NWS → TWC as above | 2021-08-19 → open | 1,866 / 9,655 | 2022, 2025 | |
| **KXHIGHMIA** (+`HIGHMIA-*`) | daily high | Miami Intl (CLIMIA); NWS → TWC | 2023-05-11 → open | 1,238 / 7,426 | 2023 | |
| KXHIGHTEWR | daily high | Newark (CLIEWR), TWC | 2026-08-26 → open | 36 / 216 | ins1 | live tier only |
| KXHIGHTTTN | daily high | Trenton (CLITTN), TWC | 2026-08-26 → open | 36 / 216 | ins1 | live tier only |
| KXLOWTNYC / KXLOWTCHI / KXLOWTMIA | daily low | CLINYC / CLIMDW / CLIMIA; NWS → TWC 2026-08-15 | 2025-12-13 → open | 292 / 1,752 each | 2025-12 | |
| KXLOWTEWR / KXLOWTTTN | daily low | CLIEWR / CLITTN, TWC | 2026-08-26 → open | 36 / 216 each | not tested | |
| KXLOWNY, KXLOWNYC, KXLOWCHI, KXLOWMIA, HIGHNY, HIGHCHI, HIGHMIA (as series) | — | — | — | 0 markets | — | listed, empty |
| **KXRAINNYC** (+`RAINNYC-*`) | daily rain, binary > 0 in | Central Park, NWS | 2021-09-08 → 2022-08-22, then 2025-01 → 2026-07-15 | 869 / 895 | 2021 | **gap 2022-09 to 2024-12** |
| **KXRAIN** (multi-city) | daily rain, binary > 0 in, one market per city-day | TWC; NYC=CLINYC, **CHI=CLIORD (O'Hare)**, MIA=CLIMIA, EWR=CLIEWR, TTN=CLITTN | NYC/CHI/MIA 2026-07-15 → open (73 d); EWR/TTN 2026-08-27 → open (35 d) | 289 markets (5 cities) | not tested | replaces KXRAINNYC |
| KXRAINWKND | weekend rain, binary | TWC; includes CLINYC, CLIORD, CLIMIA, CLIEWR, CLITTN | 2026-08-22 → open | 7 weekends / 31 (5 cities) | — | |
| KXRAINNYCW, KXRAINDNYC, KXRAINSNYC | weekly / one-off | NYC | 2026-09 only | 1 event each | — | too thin to use |
| KXRAINNY (World) | daily rain | **Hudson River Pier 26 gauge**, not Central Park | 2021-08-02 → 2021-09-02 | 31 | — | **exclude** (different station) |
| **KXRAINNYCM** (+`RAINNYCM-*`) | monthly rain ladder | Central Park | Feb 2024 → Dec 2026 (listed) | 35 / 224 | 2024 | |
| KXRAINCHIM | monthly rain ladder | Midway (CLIMDW) mostly; 7 markets at CLIORD | Jun 2025 → open | 12 / 84 | — | check station per event |
| KXRAINMIAM | monthly rain ladder | CLIMIA | Nov 2025 → open | 11 / 86 | — | |
| KXSNOWNYM (+`SNOWNYM-*`), KXNYCSNOWM, KXCHISNOWM (O'Hare), KXMIASNOWM | monthly snow | NWS | 2021-12 → 2026-04 (seasonal) | 17 / 4 / 5 / 4 events | — | winter only |
| KXSNOWNY, KX*SNOWXMAS, KXMINNYC | one-offs | NWS | 2021–2025 | ≤ 8 events | — | ignore |
| KXTEMPNYCH / KXTEMPCHIH / KXTEMPMIAH / KXTEMPNYCHS / KXTEMPCHIHS | hourly temperature | AccuWeather → TWC → Synoptic (varies) | 2026-03-10 → open | ~100k markets | — | **out of scope** (hourly, not daily cover); skip |
| KXHURMIA / KXHURNYC / KXHURNJ, KXEMERGENCYMIA | seasonal hurricane | NWS | 2022–2024 | 2–3 events each | — | not local daily cover |

Market mechanics (HIGH, from the market objects):
- Daily markets open at 14:00Z or 15:00Z on the day before and live about 38 h. Close-time history is shown below.
- `result` and `expiration_value` (the settlement number) sit on each settled market. `expiration_value` is empty on some markets in 2022–2025. At event level only 64–73 of about 1,870 events lack it; derive those from `result` + strikes.
- Close time in UTC changed over history. **Never hard-code it.** Use `close_time`.
  - NY/MIA: 23:59 ET clock time (03:59Z in EDT, 04:59Z in EST) until 2026-07, then a fixed 05:00Z from 2026-08.
  - CHI: 23:59 ET until early 2025, then 23:59 CT (04:59Z/05:59Z), then a fixed 06:00Z from 2026-08.

### Keyless rate limit (measured, 2026-09-30 ~08:00Z)
Docs cover only authenticated tiers: Basic is 200 read tokens/s at 10 tokens per request. Unauthenticated limits are not documented, and a 429 carries no `Retry-After` header. Measured against `/historical/markets/{t}/candlesticks`:

| target rate | ok / 429 |
|---|---|
| 5 req/s sequential | 38 / 2 |
| 8 req/s | 40 / 24 |
| 10 req/s | 40 / 40 |
| 20 parallel burst | ~10–18 ok, then 429 |

**Plan for ≤4 req/s sustained per IP, shared by every worker on this Mac, with 429 backoff.** MEDIUM: this is a single measurement, and the limit is probably per IP.

## Architecture Patterns

### Recommended data layout (extends the existing `data/{raw,cache,manifests}`)
```
data/
├── raw/                          # re-pullable, gitignored
│   ├── kalshi/{series.json, markets/<SERIES>.jsonl.gz, candles/<SERIES>/<YYYY>.jsonl.gz}
│   ├── iem/{asos_daily/<STN>.csv, cli/<STN>_<YYYY>.json}
│   ├── ghcnd/<USW-ID>.csv
│   ├── nclimgrid/{grids/ncdd-YYYYMM-grd-*.nc, vintages/<tar name>}   # tars deleted after subsetting
│   ├── prism/{tmax,ppt,tmin}/<YYYY>/                                 # zips deleted after subsetting
│   ├── sales/{citibike,divvy,tlc,cta,...}/
│   └── census/{zbp23detail.zip, cbp23co.zip, gaz_zcta.zip}
├── cache/                        # derived subsets (Parquet), gitignored
│   ├── kalshi_candles/series=<S>/year=<Y>/part.parquet
│   ├── station_daily/            # one row per (station, cli_day), source column
│   ├── grid_disc/source=<nclimgrid|prism>/station=<S>/  # 40 km discs, cell_id, label_day, cli_day
│   ├── vintages/                 # (source, cell, label_day, vintage_created, value)
│   └── sales_daily/              # (dataset, unit_id, lat, lon, local_day, count)
└── manifests/                    # committed: one CSV row per downloaded file
```

### Pattern 1: One manifest row per downloaded file
**What:** Every fetcher appends `(dataset, url, local_path, bytes, md5, http_status, fetched_utc, source_version)` to `data/manifests/<dataset>.csv`. `source_version` is the NCEI `version.txt` line, the PRISM grid count / release date, the nClimGrid tar `cYYYYMMDD`, or the Kalshi cutoff at fetch time.
**When:** always. The Phase 1 artefact test asserts on manifests and row counts, per the AGENTS.md testing rules.

### Pattern 2: A two-tier Kalshi fetch driven by `/historical/cutoff`
**What:** Read `GET /historical/cutoff` (currently `market_settled_ts = 2026-08-01T00:00:00Z`). Markets settled before it go to `/historical/markets/{t}/candlesticks`, one ticker per request. Later or open markets go to `GET /markets/candlesticks?market_tickers=…` (≤100 tickers, ≤10,000 candles per call). Normalize the two schemas (below) into one Parquet table.
**When:** candles and market lists. The cutoff moves, so re-read it on every run.

### Pattern 3: The CLI day is the join key
**What:** Every observation gets a `cli_day` = midnight–midnight **local standard time** (EST = UTC−5, CST = UTC−6, fixed offsets, no DST), because that is how NWS CLI (and so Kalshi) defines the day.
- Station sources (CLI, GHCN-D first-order) are already on the CLI day.
- Grids: `cli_day = label_day − 1` for both nClimGrid and PRISM tmax (verified; see pitfalls).
- Precip grids are 12Z–12Z and cannot be mapped exactly (pitfall 6).
- Sales: aggregate on local clock day, then document the 1 h DST offset (or aggregate on LST).
**When:** every join. Put it in `docs/CONVENTIONS.md` once (plan 01-06).

### Pattern 4: Stream, subset, delete for grids and bulk trips
**What:** Download one grid file or trip zip, extract the 40 km disc cells (grids) or aggregate to unit-day counts (trips), write Parquet, record md5 in the manifest, delete the raw file.
**Why:** keeps disk usage down. PRISM tmax+ppt is about 9 GB for 2021–2026; Citi Bike is about 23 GB.

### Anti-Patterns to Avoid
- **Querying `series_ticker=HIGHNY`** (or HIGHCHI/HIGHMIA/RAINNYC): returns 0. Old tickers are under the KX series.
- **Using only `/markets`:** it silently drops everything settled before the cutoff. That is ins1's 68-day sample.
- **Using `/markets/candlesticks` (batch) for historical tickers:** returns `{"markets":[]}` with HTTP 200. It fails silently.
- **Treating IEM `daily.py` max/min as the settlement value before 2025-10.**
- **Hard-coding close times, "Chicago = 06:00Z", or "source = NWS".** All three changed in 2025–2026.
- **Discovering series with `?category=Climate and Weather` only:** misses KXHIGHNY0 and KXRAINNY, filed under "World".
- **Re-downloading PRISM files in a loop:** a file downloaded twice in 24 h is blocked for the rest of the period, and repeated excess can get the IP blocked.

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---|---|---|---|
| Retry/backoff on 429/503 | custom sleep loops | `requests.Session` + `HTTPAdapter(max_retries=urllib3.util.Retry(total=8, backoff_factor=2, status_forcelist=[429,500,502,503,504]))` + a process-wide token bucket | Kalshi sends no Retry-After; IEM returns 503 "server over capacity" and 429 "Too many requests from your IP" |
| Kalshi order-book history | a local book recorder | hl-mm recorder on AWS Tokyo → `s3://hlmm-reduced-5325/kalshi-weather-books/` | owner-approved, already running; Kalshi keeps no book archive |
| Settlement values | re-deriving highs from METAR/ASOS | Kalshi `expiration_value` + IEM `json/cli.py` (+ AFOS text for the issuance history) | exact settlement numbers; covers the TWC era, which has no public archive |
| CLI-consistent history for non-settlement stations | IEM `daily.py` pre-2025-10 | GHCN-D per-station CSV (USW IDs below) | matches CLI 357/363 days at NYC in 2025 |
| Grid cell lookup | own lat/lon math | xarray `.sel(lat=…, lon=…, method="nearest")` + vectorised haversine for discs | grids are regular lat/lon (nClimGrid 1/24°, PRISM 2.5′ NAD83) |
| ZIP centroids for CBP | geocoding | Census ZCTA gazetteer `2025_Gaz_zcta_national.zip` (952 KB) | keyless, official |
| DST/LST handling | manual offsets per date | `zoneinfo.ZoneInfo("America/New_York")` for clock time; `timezone(timedelta(hours=-5/-6))` for LST | the CLI day is LST all year |
| Revision history for nClimGrid | "wait until Oct 6 and diff" | AWS mirror vintages (`archive/2026/*prelim*`, superseded `*complete*`) | first-publication vs final is measurable today for Apr–Sep 2026 |

**Key insight:** in this domain the hard part is *which number, for which day, as known when*, not the download. Every shortcut above has already produced a wrong basis or a silent empty result in this project or in ins1/ins2.

## Common Pitfalls

### Pitfall 1: The historical cutoff hides most of Kalshi's history
**What goes wrong:** `/markets?series_ticker=KXHIGHNY&status=settled` returns only markets settled after 2026-08-01 plus open ones: 420 markets / 70 days. The history (9,286 markets back to 2021) is only on `/historical/markets`.
**How to avoid:** Use Pattern 2. Dedupe tickers across tiers. On a 404 from one tier, retry the other.
**Warning signs:** a series whose first market date is about a week before the cutoff.

### Pitfall 2: IEM ASOS daily max/min is not the CLI value before Oct 2025
**What goes wrong:** Central Park, 2025. `daily.py` `max_temp_f` ≠ CLI high on 158/363 days (122 of them IEM 1 °F lower, 17 at 2 °F lower); low ≠ on 113 days. Monthly mismatches were 15–26 days/month Jan–Aug 2025, 7 in Sep 2025, and **0 from Oct 2025 through Sep 2026**. Precip matched on every day. The same bias at nearby stations would inflate the geography basis in EVAL-02/03 for 2021–2025.
**How to avoid:**
- Settlement stations: `expiration_value` → IEM `json/cli.py`.
- Nearby stations with a CLI (LGA, JFK, ISP, EWR, TTN, ORD, MDW, PWK, DPA, UGN, FLL, MIA; confirmed via `geojson/cli.py?dt=2025-07-15`): IEM CLI JSON.
- Other stations (HPN, FRG, TEB, CDW, OPF, TMB, HWO, DJT): GHCN-D.
- Keep `daily.py` only for 2025-10+ or for precip.
**Warning signs:** a mean nearby-minus-settlement offset of about +1 °F that vanishes after Oct 2025.
**Note:** the files another worker has already written to `data/raw/iem/*.csv` come from `daily.py` (2023-01 → 2026-09) and carry this bias before 2025-10.

### Pitfall 3: Settlement source and close time switched in Aug 2026
**What goes wrong:** Markets closing ≤ 2026-08-14 settle on the NWS CLI. From 2026-08-15 they settle on TWC's figure for the same CLI station ("according to The Weather Company"), with a fixed 05:00Z close (06:00Z Chicago). ins1's 272 city-days straddle the switch. TWC values have no public archive.
**How to avoid:** Carry a `settle_source` column (`NWS`/`TWC`) parsed from `rules_primary`. Store `expiration_value` as the truth. Report NWS-vs-TWC mismatches separately (ins1: 0/68 NYC, 1/68 CHI, 3/68 MIA).

### Pitfall 4: Chicago uses two different stations
**What goes wrong:** Chicago temperature (KXHIGHCHI, KXLOWTCHI) and monthly rain (KXRAINCHIM, mostly) settle at **Midway**. Daily rain (KXRAIN-…-CHI), weekend rain and monthly snow settle at **O'Hare**.
**How to avoid:** Keep a per-market station column parsed from `rules_primary` (the `CLI\w{3}` token). Never assume a per-city station.

### Pitfall 5: Hourly candles are sparse, and the two tiers use different schemas
**What goes wrong:**
- Hours with no quote/trade change are omitted. Examples: HIGHMIA-23MAY12-T87 has 16 candles over a 38 h life, the last at 21:00Z with close at 03:59Z; the live KXHIGHNY-26SEP20-T78 has 36 of about 39.
- Historical candles use `yes_ask.close`, `volume`, `open_interest`. Live/batch candles use `yes_ask.close_dollars`, `volume_fp`, `open_interest_fp`.
- The price block is null when there are no trades.
**How to avoid:**
- Normalize both schemas.
- For "ask at t−24h/12h/2h", take the last candle with `end_period_ts ≤ t` (a forward fill, no look-ahead). On the live endpoint pass `include_latest_before_start=true`.
- Treat ask = 1.00 with bid < 0.90 as "no offer" (the ins1 rule).
- Order books (`/markets/{t}/orderbook`) list **bids only**: `yes_dollars` and `no_dollars`. YES ask = 1 − best NO bid.
**Confidence:** MEDIUM that "missing candle means no change". This is observed behaviour, not documented.

### Pitfall 6: Grid day conventions
**What goes wrong:**
- **nClimGrid** day = "24-hour period ending in the early morning of the specified day". ins2 measured it: label D vs calendar D−1 RMSE 1.1–1.7 °F against 4.2–5.2 °F unshifted.
- **PRISM** day = 1200 UTC–1200 UTC, day-ending label (the 2 Jul grid covers 12Z 1 Jul → 12Z 2 Jul).
- **Verified today for PRISM tmax:** nearest 4 km cell at NYC/EWR/TTN/MDW/MIA/LGA/JFK, 2026-07-29..08-03 (n = 42). Label D vs station calendar D−1 gives RMSE **1.07 °F**, bias 0.00; unshifted gives 4.27 °F.
- So for both grids, calendar day D = label D+1.
- Precip: PRISM/Stage IV 24 h = 12Z–12Z (07:00–07:00 EST), so a CLI calendar-day rain total straddles two grid labels. nClimGrid prcp mixes station observation times.
**How to avoid:**
- tmax/tmin: shift the label by one day for both grids.
- Precip: either accept the 12Z–12Z window and report it as a basis, or build calendar-day sums from hourly Stage IV (`ST4.YYYYMMDDHH.01h.grib`) / MRMS 01H, 05Z→05Z EST and 06Z→06Z CST.

### Pitfall 7: Revision lifecycle (the revision-risk source)
- **nClimGrid** (from `version.txt` dates and the AWS archive):
  - The prelim file for the open month is updated daily, about 2 days behind (e20260926 created 09-28).
  - The first "complete/scaled" file comes at about the 4th–7th of M+1. It is re-created at M+2 and again at M+3, sometimes several times (June 2026: c0706, c0806, c0904, c0905, c0906).
  - Frozen after about M+3, with occasional reprocessing years later (2023-07 re-created 2026-05-12).
  - "Scaled" means adjusted to the monthly nClimGrid.
  - NCEI keeps only the current file. **The AWS mirror keeps the vintages** (see Code Examples).
- **PRISM:**
  - Grid count 1 about 24 h after the day ends; count 2 at +5 days; count 3 at the monthly update (about the 15th–22nd of M+1; the 20260801 file shows release history 08-02, 08-06, 09-22); counts 4–8 at the next five monthly updates.
  - Count 8 is final ("data older than six months are considered stable").
  - **PRISM keeps no prior versions** ("each time a PRISM dataset is reproduced, the older version is overwritten"; FAQ). Revision can only be measured going forward by snapshotting.
  - Legacy file names carried "early/provisional/stable". That FTP tree was deprecated 2025-09-30; the new files carry `PRISM_DATASET_RELEASE_NUMBER` in `info.txt` and via the `gridCount` service. The exact early/provisional/stable ↔ grid-count mapping is LOW confidence; use grid count.
- **NWS CLI:** a 5 pm "VALID TODAY AS OF 0400 PM" preliminary, the final issuance about 2 am, and occasional corrections (Jan 1 2026 re-issued 11:06 am Jan 2). IEM `json/cli.py` points at the latest product id. `afos/retrieve.py` returns all issuances.

### Pitfall 8: Shared-IP throttling across parallel workers
**What goes wrong:** IEM returned 503 "server over capacity" and 429 "Too many requests from your IP" while another worker pulled one station per minute. Kalshi 429s above ~5 req/s. PRISM blocks repeat downloads.
**How to avoid:** Give each source a single fetch process (or a file-lock token bucket in `src/wi/http.py`). IEM: sequential, ≥ 60 s between bulk requests. Kalshi: ≤ 4 req/s total. PRISM: ≥ 2 s between files, never the same file twice in 24 h. Also: IEM can return an error body with HTTP 200 (e.g. `ERROR: station: PBI not found in network: FL_ASOS`), so validate the CSV header.

### Pitfall 9: Station ID drift
Palm Beach International is **DJT** in IEM's `FL_ASOS` table (PBI "not found"), and Kalshi uses `CLIDJT`. Use DJT, GHCN `USW00012844`. GYY and MMU have precip missing on 841/1003 and 801/1003 days since 2024: temperature only. BLM is missing tmax on 46 and precip on 410 days, and GHCN has no current USW record for it: drop BLM or use it for temperature only.

### Pitfall 10: Demand proxies are counts, and trip timestamps are local
Citi Bike, Divvy and TLC timestamps are naive local clock time (`2026-01-31 09:13:09.018`). None of the keyless near-station datasets is revenue: they are trips/entries. EVAL-06 must say "demand proxy". Divvy zips can have a wrong inner filename (`202601-divvy-tripdata.zip` contains `202501-divvy-tripdata.csv` with 2026 data): trust the rows, not the name. Citi Bike `202604` is 165 MB against about 900 MB in neighbouring months: check for missing days.

## Code Examples

All commands below were run 2026-09-30 and returned what is noted.

### Kalshi: historical cutoff, series, markets (both tiers)
```bash
B=https://api.elections.kalshi.com/trade-api/v2
curl -s "$B/historical/cutoff"
# {"market_settled_ts":"2026-08-01T00:00:00Z","trades_created_ts":"2026-08-01T00:00:00Z",...}
curl -s "$B/series" > series.json                     # 14,494 series, 18 MB (no category filter)
curl -s "$B/series/KXHIGHNY"                          # settlement_sources: The Weather Company
curl -s "$B/historical/markets?series_ticker=KXHIGHNY&limit=1000"          # + &cursor=… ; 9,286 markets, HIGHNY-21AUG06… → KXHIGHNY-26JUL30…
curl -s "$B/markets?series_ticker=KXHIGHNY&limit=1000"                     # live tier: 420 markets from 2026-07-24
curl -s "$B/events?series_ticker=KXHIGHNY&status=settled&limit=200"        # event level, strike_date, settlement_sources
```

### Kalshi: candlesticks
```bash
# historical tier (settled before cutoff), one ticker per call, period_interval ∈ {1,60,1440}
curl -s "$B/historical/markets/HIGHNY-21AUG06-T86/candlesticks?start_ts=1628100000&end_ts=1628400000&period_interval=60"
# -> {"ticker":…,"candlesticks":[{"end_period_ts":1628179200,"yes_ask":{"close":"0.7900",…},"yes_bid":{…},"price":{…},"volume":"0.00","open_interest":"0.00"},…]}  (18 candles)

# live tier, single market
curl -s "$B/series/KXHIGHNY/markets/KXHIGHNY-26SEP20-T78/candlesticks?start_ts=1789826400&end_ts=1789970400&period_interval=60&include_latest_before_start=true"
# -> fields yes_ask.close_dollars, volume_fp, open_interest_fp

# live tier, batch (≤100 tickers, ≤10,000 candles total; returns [] for historical tickers)
curl -s "$B/markets/candlesticks?market_tickers=KXHIGHNY-26SEP20-T78,KXHIGHNY-26SEP20-B76.5&start_ts=1789826400&end_ts=1789966800&period_interval=60"
```

### Kalshi: trades and order book (keyless)
```bash
curl -s "$B/historical/trades?ticker=HIGHNY-23JUL31-T85&limit=1000"   # prints back to 2023; + cursor
curl -s "$B/markets/trades?ticker=KXHIGHNY-26SEP30-T79&limit=1000"
curl -s "$B/markets/KXHIGHNY-26SEP30-T79/orderbook?depth=5"
# {"orderbook_fp":{"no_dollars":[["0.9500","155.00"],…],"yes_dollars":[]}}  — bids only
```

### IEM: parsed CLI, CLI text, CF6, ASOS daily
```bash
curl -s "https://mesonet.agron.iastate.edu/json/cli.py?station=KNYC&year=2026"    # results[]: valid, high, low, precip, snow, product id
#   stations verified 2021 full year: KNYC KEWR KTTN KMDW KMIA KORD (365 rows each)
curl -s "https://mesonet.agron.iastate.edu/geojson/cli.py?dt=2025-07-15&fmt=csv"  # every CLI station for one day
curl -s "https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py?pil=CLINYC&sdate=2026-09-27T00:00Z&edate=2026-09-29T00:00Z&fmt=text&limit=20"
curl -s "https://mesonet.agron.iastate.edu/api/1/nwstext/202601021606-KOKX-CDUS41-CLINYC"
curl -s "https://mesonet.agron.iastate.edu/json/cf6.py?station=KNYC&year=2026"    # CF6 monthly-form daily rows (hdd/cdd/precip/snow)
curl -s "https://mesonet.agron.iastate.edu/cgi-bin/request/daily.py?network=NY_ASOS&stations=NYC&stations=LGA&stations=JFK&year1=2026&month1=9&day1=25&year2=2026&month2=9&day2=27&format=csv"
#   one network per call; repeat &stations=; networks NY_ASOS NJ_ASOS IL_ASOS IN_ASOS FL_ASOS
```

### GHCN-Daily (CLI-consistent, all first-order stations)
```bash
curl -s "https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/access/USW00094728.csv"  # Central Park, 17.8 MB, to 2026-09-22
# TMAX/TMIN tenths °C, PRCP tenths mm; F = round(TMAX/10*9/5+32)
```
Station IDs, current through 2026 per `ghcnd-inventory.txt`:
- NYC USW00094728, LGA USW00014732, JFK USW00094789, HPN USW00094745, FRG USW00054787, ISP USW00004781
- EWR USW00014734, TTN USW00014792, TEB USW00094741, CDW USW00054743
- MDW USW00014819, ORD USW00094846, PWK USW00004838, DPA USW00094892, UGN USW00014880
- MIA USW00012839, FLL USW00012849, OPF USW00012882, TMB USW00012888, HWO USW00092809, DJT USW00012844
- No current USW: BLM (1962–63 only), MMU, GYY.

### nClimGrid-Daily: current files and vintages
```bash
# current version, NCEI (2021-08 … 2026-08 scaled verified by HEAD/listing; ~57-61 MB each)
curl -O "https://www.ncei.noaa.gov/data/nclimgrid-daily/access/grids/2024/ncdd-202407-grd-scaled.nc"
curl -s "https://www.ncei.noaa.gov/data/nclimgrid-daily/access/grids/2024/ncdd-202407-version.txt"
#   "complete for 2024-07-01 through 2024-07-31 created on 2024-10-19 … GHCN-Daily 3.31-upd-2024101819"
# vintages, AWS Open Data (no key)
aws s3 ls s3://noaa-nclimgrid-daily-pds/archive/2026/ --no-sign-request
#   nclimgrid-daily_v1-0-0_prelim_s20260901_e20260904_c20260906.tar.gz … (148 prelim tars since 2026-04-21, 6.2 GB)
#   nclimgrid-daily_v1-0-0_complete_s20260601_e20260630_c20260706/…0806/…0904/…0905/…0906.tar.gz
aws s3 ls s3://noaa-nclimgrid-daily-pds/access/grids/2026/ --no-sign-request
#   ncdd-202604…202608-grd-prelim.nc still present next to the -scaled.nc files
# each tar: ncdd-YYYYMM-grd-<status>.nc + 36 area-average CSVs (cen/cty/div/ste/wfo…) + version.txt
```

### PRISM daily 4 km
```bash
curl -s -OJ "https://services.nacse.org/prism/data/get/us/4km/tmax/20260801?format=nc"   # prism_tmax_us_25m_20260801.zip, 3.19 MB (nc 1.49 MB + stn.csv 1.69 MB)
curl -s "https://services.nacse.org/prism/data/get/releaseDate/us/4km/tmax/20260801/20260805?json=true"
#   [["2026-08-01","2026-09-22","tmax","3","https://…/20260801"],…]
curl -s "https://services.nacse.org/prism/data/get/gridCount/us/tmax/20260801"            # 3
# same files as a directory tree (ppt ~1.5 MB/day, tmax ~3.2 MB/day):
#   https://data.prism.oregonstate.edu/time_series/us/an/4km/{tmax,ppt,tmin}/daily/{YYYY}/prism_{var}_us_25m_{YYYYMMDD}.zip
# netCDF: variables lat(621), lon(1405), Band1 float32 °C / mm, _FillValue −9999, NAD83
```

### Stage IV / MRMS (keyless)
```bash
# Stage IV 12Z–12Z 24 h (~0.42 MB) and hourly (~0.19 MB) GRIB1, back to at least 2021-08
https://mesonet.agron.iastate.edu/archive/data/2026/09/27/stage4/ST4.2026092712.24h.grib
https://mesonet.agron.iastate.edu/archive/data/2026/09/27/stage4/ST4.2026092718.01h.grib
# MRMS Pass2 QPE (GRIB2.gz, ~3.4 MB per 24 h file)
https://mtarchive.geol.iastate.edu/2026/09/27/mrms/ncep/MultiSensor_QPE_24H_Pass2/MultiSensor_QPE_24H_Pass2_00.00_20260927-120000.grib2.gz
aws s3 ls s3://noaa-mrms-pds/CONUS/MultiSensor_QPE_24H_Pass2_00.00/20260927/ --no-sign-request
```
The NOMADS `pcpanl/prod/` listing returned no entries (not needed).

### Census business counts (keyless bulk; the API needs a key)
```bash
curl -s -D - -o /dev/null "https://api.census.gov/data/2023/cbp?get=NAME,NAICS2017,ESTAB&for=zip%20code:10019&NAICS2017=722515"
#   HTTP 302, X-DataWebAPI-KeyError: 1, Location: …/missing_key.html ("A valid key must be included with each data API request")
curl -O "https://www2.census.gov/programs-surveys/cbp/datasets/2023/zbp23detail.zip"   # 15.7 MB -> zbp23detail.txt 291 MB
#   "zip","name","naics","est","n<5","n5_9",…,"city","stabbr","cty_name"   ("N" = suppressed)
curl -O "https://www2.census.gov/programs-surveys/cbp/datasets/2023/cbp23co.zip"       # county × NAICS with emp/payroll, 12.9 MB
curl -O "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_zcta_national.zip"  # ZCTA centroids
```

### Demand proxies
```bash
curl -s "https://s3.amazonaws.com/tripdata/?list-type=2"          # Citi Bike: YYYYMM-citibike-tripdata.zip (NYC), JC-YYYYMM-… (Jersey City/Hoboken)
curl -s "https://divvy-tripdata.s3.amazonaws.com/?list-type=2"    # Divvy: YYYYMM-divvy-tripdata.zip
#   both: ride_id,rideable_type,started_at,ended_at,start_station_name,start_station_id,…,start_lat,start_lng,…,member_casual
curl -sI "https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2026-07.parquet"   # 61.7 MB; 2026-08 → 403 (≈2-month lag)
curl -s "https://data.cityofchicago.org/resource/5neh-572f.json?\$limit=2&\$order=date%20DESC"  # CTA 'L' daily entries, to 2026-07-31
curl -s "https://data.cityofchicago.org/resource/ajtu-isnz.json?\$select=max(trip_start_timestamp),count(*)"  # Chicago taxi 2024-: 18.1M rows, to 2026-09-01
curl -s "https://data.ny.gov/resource/5wq4-mkjj.json?\$limit=1"   # MTA subway hourly 2025-; to 2026-09-16 (a 1-day $group query took 210 s)
curl -s "https://data.cityofnewyork.us/resource/uczf-rk3c.json?\$select=min(date),max(date),count(*)"  # NYC DOT bike counters 2012-08 → 2026-01-28 only
```

## Stand-in sales datasets, ranked

Ranking criteria, in order: daily granularity; a point location near a Kalshi settlement station; weather sensitivity; download size. "Keyless" means verified today.

| Rank | Dataset | Granularity / location | Near which ladder | Weather sensitivity | Size (2024-01 →) | Keyless | Licence |
|---|---|---|---|---|---|---|---|
| 1 | **Divvy** station-day | trip-level, station lat/lon, local time | Chicago (Midway is ~10–15 km from the Loop; stations near MDW exist) | strong (heat, rain, cold) | 32 zips, 0.6 GB | yes | Lyft data licence: use "in your product or service … for any lawful purpose"; no stand-alone redistribution (verified on divvybikes.com) |
| 1 | **Citi Bike** station-day (NYC + JC) | trip-level, station lat/lon | Central Park (stations within 1–5 km); JC/Hoboken ~13 km from EWR | strong | NYC 32 zips ≈ 23 GB (≈ 0.4–1.05 GB/month); JC 95 MB | yes | same Lyft licence family (MEDIUM: Citi Bike page not fetched) |
| 3 | **NYC TLC** yellow+green zone-day | trip-level, 263 taxi zones (incl. LGA/JFK zones) | Central Park, LGA, JFK | moderate (rain raises taxi demand) | ≈ 63 MB/month → ≈ 2 GB to 2026-07 (FHVHV +0.48 GB/month, optional) | yes | TLC makes no accuracy claims; public |
| 4 | **CTA 'L'** station-day entries | station-day, station location | Chicago (Midway Orange Line terminal) | mild | ~1.3M rows via Socrata CSV export (~tens of MB) | yes (throttled without app token) | City of Chicago open data |
| 5 | **Chicago taxi trips 2024-** | community-area-day via SoQL `$group` | Chicago | moderate | 18.1M rows; aggregate server-side | yes | open data |
| 6 | **NYC DOT bike counters** | 15-min counts at ~41 counters | NYC | strong | small | yes | open data; **stale after 2026-01-28** |
| 7 | **MTA subway hourly** | station-complex-hour | NYC | mild | huge; server-side daily $group ≈ 210 s per day queried | yes | open data; heavy |
| 8 | Capital Bikeshare | station-day | DC (not one of the five) | strong | 0.66 GB | yes | Lyft licence; only if a DC ladder is added |
| 9 | M5 (Walmart) | item-store-day, **state-level location only** (CA/TX/WI) | none | weak link | 50 MB zip via `github.com/Nixtla/m5-forecasts/raw/main/datasets/m5.zip` (HTTP 206) | yes (mirror) | LOW: Kaggle competition terms; paper method demo only |
| — | Rossmann, Favorita | store-day, Germany / Ecuador | none | — | — | **owner-hand**: `~/.kaggle/kaggle.json` absent (`ls` → No such file) | Kaggle rules |
| — | Iowa liquor sales | store-day $ | none (Iowa) | — | — | `data.iowa.gov/resource/m3tr-qhgy.json` now returns the "Iowa Data Hub" web app, not SODA JSON: **unverified, drop** | — |
| — | Miami | — | Miami | — | — | **no keyless daily point-level proxy found**. Only lead: "Tri-Rail Station Ridership Data" (Palm Beach TPA, ArcGIS Hub; granularity unchecked) | gap |

**Recommendation for plan 01-05:**
- Pull Divvy (all of 2024-01 → 2026-08), Citi Bike JC plus NYC 2025-01 → 2026-08 (≈ 14 GB, streamed and aggregated), TLC yellow+green 2024-01 → 2026-07, and the CTA 'L' daily.
- Skip MTA, M5 and Kaggle in Phase 1.
- Record Miami as a known gap. EVAL-06 runs on NYC and Chicago.

## Data manifest plan

Throughput assumes this Mac's link at about 10–30 MB/s from S3/CloudFront, one fetch process per source, and the throttles above. Sizes are transferred bytes. Most raw files are deleted after subsetting (Pattern 4).

| # | Dataset | URL pattern | Scope | Size estimate | Fetch time estimate | Licence note | Needs owner? | Confidence |
|---|---|---|---|---|---|---|---|---|
| K1 | Kalshi series list | `$B/series` | all 14,494 | 18 MB | 5 s | Kalshi API terms (product redistribution: open question) | no | HIGH |
| K2 | Kalshi markets (both tiers) | `$B/historical/markets?series_ticker=S` + `$B/markets?series_ticker=S` | ~30 in-scope series (excl. hourly) | ~110 MB JSON (hourly series add 190 MB, skip) | 2–5 min | same | no | HIGH |
| K3 | Kalshi hourly candles, historical tier | `$B/historical/markets/{t}/candlesticks?period_interval=60` | ≈ 33,500 markets (NY/CHI/MIA high 2021→, low, rain, monthly) | ≈ 330 MB JSON (≈ 40 MB gz) | ≈ 2.3 h at 4 req/s. Do 2024-01→ first (≈ 1.6 h), then 2021–23 | same | no | HIGH (path), MEDIUM (time) |
| K4 | Kalshi hourly candles, live tier | `$B/markets/candlesticks?market_tickers=…` | ≈ 3,000 markets since 2026-07-24 | ≈ 30 MB | < 1 min (≈ 30 batch calls) | same | no | HIGH |
| K5 | Kalshi trade prints (optional) | `$B/historical/trades?ticker=`, `$B/markets/trades?ticker=` | core daily series | unknown (paginated) | hours; only if Phase 2 needs prints | same | no | MEDIUM |
| K6 | Recorded order books | `s3://hlmm-reduced-5325/kalshi-weather-books/{books,settlements,candles,discovery}/date=…/` | from recorder start | grows daily | `aws s3 sync` minutes | internal | no (schema pending from hl-mm) | LOW (prefix absent at 08:0xZ) |
| W1 | IEM parsed CLI | `https://mesonet.agron.iastate.edu/json/cli.py?station=K{STN}&year={Y}` | 13 CLI stations × 2021–2026 | ≈ 78 × 0.45 MB ≈ 35 MB | 15–80 min (≥ 10–60 s spacing) | IEM free service, cite; underlying NWS public domain | no | HIGH |
| W2 | CLI issuance text (optional) | `…/cgi-bin/afos/retrieve.py?pil=CLI{STN}&sdate=&edate=&fmt=text&limit=9999` | 6 settlement stations | ~50 MB | 10–30 min | NWS public domain | no | HIGH |
| W3 | GHCN-Daily station CSVs | `https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/access/{USW-ID}.csv` | 21 stations | ≈ 200 MB | 1–3 min | NOAA public domain | no | HIGH |
| W4 | IEM ASOS daily | `…/cgi-bin/request/daily.py?network=…&stations=…` | 24 stations, 2021-08 → | ≈ 5 MB | ≈ 25 min at 1 req/min (2023→ already on disk from another worker) | IEM free | no | HIGH (with pitfall 2) |
| G1 | nClimGrid-Daily scaled + current prelim | `https://www.ncei.noaa.gov/data/nclimgrid-daily/access/grids/{YYYY}/ncdd-{YYYYMM}-grd-{scaled\|prelim}.nc` (or `s3://noaa-nclimgrid-daily-pds/access/grids/…`) | 2021-08 → 2026-09 (62 files) | ≈ 3.6 GB (3 already on disk) | 5–15 min | NOAA public domain | no | HIGH |
| G2 | nClimGrid vintages | `s3://noaa-nclimgrid-daily-pds/archive/2026/*_prelim_*.tar.gz`, superseded `*_complete_*`, `access/grids/2026/ncdd-2026{04..08}-grd-prelim.nc` | Apr–Sep 2026 | ≈ 6.2 GB + ~1.5 GB + 0.33 GB | 10–30 min; **do today**: the mirror may prune | NOAA public domain | no | HIGH (listed), MEDIUM (persistence) |
| G3 | PRISM 4 km tmax + ppt | `https://services.nacse.org/prism/data/get/us/4km/{tmax\|ppt}/{YYYYMMDD}?format=nc` (or the file tree) | 2021-08-01 → yesterday (≈ 1,885 days × 2) | ≈ 8.9 GB (tmax 3.2 MB + ppt 1.5 MB per day) | ≈ 3 h at 1 file / 2 s. 2024-01→ first (≈ 4.7 GB, ≈ 1.5 h) | Free to reproduce/distribute with citation "PRISM Group, Oregon State University, https://prism.oregonstate.edu, accessed <date>"; no warranty | no | HIGH |
| G4 | PRISM tmin | same, `tmin` | 2025-12 → (low ladders) | ≈ 1 GB | ≈ 20 min | same | no | HIGH |
| G5 | PRISM grid-count / release dates | `…/releaseDate/us/4km/{var}/{start}/{end}?json=true` | same range | < 1 MB | 1 min | same | no | HIGH |
| G6 | Stage IV 24 h (optional) | `https://mesonet.agron.iastate.edu/archive/data/{Y}/{M}/{D}/stage4/ST4.{YYYYMMDD}12.24h.grib` | 2021-08 → | ≈ 0.8 GB | ≈ 30 min polite | NOAA public domain | no | HIGH (path) |
| G7 | Stage IV hourly for calendar-day rain (optional) | `…/stage4/ST4.{YYYYMMDDHH}.01h.grib` | days with rain markets only | ≈ 4.5 MB/day → ≈ 8.5 GB full | hours; only if Phase 3 asks | NOAA public domain | no | HIGH (path), needs eccodes |
| S1 | Divvy | `https://divvy-tripdata.s3.amazonaws.com/{YYYYMM}-divvy-tripdata.zip` | 2024-01 → 2026-08 | 0.6 GB | 2–5 min | Lyft data licence (product use OK, no stand-alone resale) | no | HIGH |
| S2 | Citi Bike JC + NYC | `https://s3.amazonaws.com/tripdata/JC-{YYYYMM}-citibike-tripdata.csv.zip`, `…/{YYYYMM}-citibike-tripdata.zip` | JC 2024-01→; NYC 2025-01 → 2026-08 | 0.1 + ≈ 14 GB | 15–60 min (stream + aggregate) | Lyft licence (MEDIUM) | no | HIGH |
| S3 | NYC TLC yellow + green | `https://d37ci6vzurychx.cloudfront.net/trip-data/{yellow\|green}_tripdata_{YYYY-MM}.parquet` + `/misc/taxi_zone_lookup.csv` | 2024-01 → 2026-07 | ≈ 2 GB | 3–10 min | public, no accuracy warranty | no | HIGH |
| S4 | CTA 'L' daily | `https://data.cityofchicago.org/api/views/5neh-572f/rows.csv?accessType=DOWNLOAD` | full | tens of MB | 1–5 min (Socrata 503s seen; retry) | City of Chicago terms | no | MEDIUM (export URL not probed; SODA JSON worked) |
| S5 | Rossmann / Favorita | Kaggle | — | — | — | Kaggle rules | **yes** (kaggle.json + rule acceptance) | HIGH that it's blocked |
| C1 | ZBP 2023 detail | `https://www2.census.gov/programs-surveys/cbp/datasets/2023/zbp23detail.zip` | all US ZIPs × NAICS | 15.7 MB | < 1 min | public domain | no | HIGH |
| C2 | CBP 2023 county | `…/2023/cbp23co.zip` | county × NAICS, emp, payroll | 12.9 MB | < 1 min | public domain | no | HIGH |
| C3 | ZCTA gazetteer | `https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_zcta_national.zip` | centroids | 0.95 MB | < 1 min | public domain | no | HIGH |
| C4 | Census CBP API | `https://api.census.gov/data/2023/cbp?…&key=` | — | — | — | — | **yes** (API key); not needed given C1–C3 | HIGH |

Total transferred for the recommended core (K1–K4, W1, W3, G1–G5, S1–S3, C1–C3): ≈ 45 GB. The minimum on-disk footprint after subsetting is ≈ 2–4 GB. Wall-clock time is about 4–5 h if each source gets its own process, dominated by Kalshi candles (throttle) and PRISM (politeness).

## Pre-registered Phase 1 acceptance checks (write into 01-06 PLAN before running)

These are data-integrity gates, not evaluation results. The thresholds are set here, before any value is computed.

1. **Settlement truth.** For NWS-era events (close ≤ 2026-08-14) with a non-empty `expiration_value`, the mismatch rate against IEM CLI high/low must be ≤ 1 % per series. Failure means stop and investigate the day mapping. TWC-era mismatches are reported, not gated.
2. **Grid day alignment (reproduce ins2, extend to PRISM).** For each of NYC, EWR, TTN, MDW, MIA, compute the nearest-cell tmax RMSE against CLI high over every Kalshi-history day in the pulled window. RMSE(calendar D = label D+1) must be lower than RMSE(label D) for **5/5 stations and both grids**. Otherwise no grid enters Phase 3.
3. **Candle coverage.** ≥ 95 % of settled markets in KXHIGHNY/CHI/MIA (2024-01 →) have at least one candle with `end_period_ts` ≤ close − 2 h. Report the share with a candle inside the 24 h window.
4. **Station series.** Every settlement station has ≥ 99 % non-missing CLI high/precip over its Kalshi window. Nearby stations below 95 % precip coverage are marked temperature-only (currently GYY, MMU, BLM).
5. **Manifests.** Every file in `data/raw` has a manifest row with md5. A second `make data` run downloads 0 bytes for closed months and closed markets (idempotence).
6. **UTC.** All stored timestamps are UTC ISO-8601 or epoch seconds. Local-day columns are explicitly named (`cli_day`, `local_day`).

## State of the Art

| Old approach | Current approach | When changed | Impact |
|---|---|---|---|
| Kalshi settled markets on `/markets` | `/historical/*` for markets settled before a moving cutoff | cutoff now 2026-08-01 | must query both tiers |
| `HIGHNY-*` tickers | `KXHIGHNY-*` (same series_ticker KXHIGHNY) | 2024-10-24 | old tickers only via the KX series |
| Settlement "NWS Climatological Report" | "The Weather Company" for the same CLI station | markets closing from 2026-08-15 | TWC has no public archive; keep `expiration_value` |
| Close 23:59 local clock | fixed 05:00Z (ET cities) / 06:00Z (Chicago) | 2026-08 | read `close_time` |
| KXRAINNYC daily binary | KXRAIN multi-city daily binary (TWC) | 2026-07-15 | Chicago rain at O'Hare |
| PRISM web service v1, BIL, "early/provisional/stable" names | new service `services.nacse.org/prism/data/get/…`, COG default, `?format=nc`, grid count 1–8 | Mar 2025; old FTP tree deprecated 2025-09-30 | use grid count for vintage |
| PRISM 800 m paid | 800 m free (FAQ, "As of March 2025"); the same FAQ still mentions fees | 2025 | 4 km is enough here |
| Census API keyless (≤ 500/day) | key required for every data request | observed 2026-09-30 | use bulk files |
| IEM daily max from METARs | matches CLI from 2025-10 | ~Sep 2025 | pre-2025-10 values biased |

## Open Questions

1. **Recorder schema and first timestamp.** The S3 prefix did not exist at 08:0xZ. Plan 01-02 should build the reader against the README when it lands, with a fixture from the hl-mm message.
2. **Kalshi keyless limit.** Measured at about 5 req/s. It is unclear whether it is per IP or also per endpoint. Recommendation: one Kalshi fetch process, 4 req/s, back off on 429.
3. **Does a missing hourly candle mean "no change"?** This is observed, not documented. Recommendation: forward-fill, and cross-check a sample of days against recorded books once the recorder has data.
4. **How long the AWS mirror keeps nClimGrid vintages.** The NCEI readme says prelim files are removed once scaled exists, and the mirror has not removed them yet. Recommendation: copy the station-disc subsets of every vintage today, then add a daily snapshot job (prelim tar + PRISM grid count 1/2) so revision history accumulates.
5. **PRISM early/provisional/stable ↔ grid count mapping.** The legacy names are not documented in the current docs. Recommendation: define revision in terms of grid count (1 → 2 → 3 → 8).
6. **Licences for a product (not the paper).**
   - PRISM terms allow free reproduction with citation, with no warranty and no SLA.
   - NOAA sources are public domain.
   - IEM is a university service, not an oracle.
   - Kalshi market-data redistribution terms were not retrieved (kalshi.com returned 429).
   - Lyft data forbids stand-alone redistribution.
   - Hand the Kalshi and Lyft questions to Phase 15.
7. **Miami demand proxy.** None was found keyless. Recommendation: EVAL-06 runs on NYC and Chicago, and Miami is stated as a gap unless the owner has a source.
8. **eccodes wheel on Python 3.14/arm64.** Not checked. Only matters if Stage IV/MRMS is needed.
9. **IEM coverage for OPF, TMB, HWO, DJT since 2024.** Unverified: IEM returned 429 while another worker was pulling. The stations exist in the `FL_ASOS` table (archive since ≥ 1999), and GHCN-D has them through 2026.

## Sources

### Primary (HIGH confidence, fetched 2026-09-30)
- Kalshi API probes: `/historical/cutoff`, `/series`, `/series/KXHIGHNY`, `/markets`, `/historical/markets`, `/events`, `/historical/markets/{t}/candlesticks`, `/series/{s}/markets/{t}/candlesticks`, `/markets/candlesticks`, `/markets/{t}/orderbook`, `/historical/trades`, `/markets/trades`
- https://docs.kalshi.com/getting_started/historical_data — historical endpoints and cutoff
- https://docs.kalshi.com/api-reference/market/get-market-candlesticks — "Candlesticks for markets that settled before the historical cutoff are only available via GET /historical/markets/{ticker}/candlesticks"
- https://docs.kalshi.com/api-reference/market/batch-get-market-candlesticks — ≤100 tickers, ≤10,000 candles, no auth
- https://docs.kalshi.com/api-reference/historical/get-historical-market-candlesticks
- https://docs.kalshi.com/getting_started/rate_limits — tiers, 10 tokens/request, no Retry-After
- https://prism.oregonstate.edu/documents/PRISM_downloads_web_service.pdf (26 Mar 2025) — URL syntax, formats, download limits, releaseDate, gridCount
- https://prism.oregonstate.edu/documents/PRISM_update_schedule.pdf — grid counts 1–8, "PRISM Day … ending at 1200 UTC"
- https://prism.oregonstate.edu/documents/PRISM_datasets.pdf — AN91d, day-ending naming, ppt uses ST4/MRMS
- https://prism.oregonstate.edu/terms/ — free reproduction with citation
- https://prism.oregonstate.edu/faq/ — "older version is overwritten", explorer bulk up to 500 points
- https://prism.oregonstate.edu/calendar/list.php — live release list
- https://data.prism.oregonstate.edu/readme.txt — new directory structure; old tree deprecated 2025-09-30
- https://www.ncei.noaa.gov/data/nclimgrid-daily/access/grids/{2021..2026}/ listings and version.txt files
- https://www.ncei.noaa.gov/data/nclimgrid-daily/doc/nclimgrid-daily_v1-0-0_readme-web.txt — prelim/scaled definitions, archive tars
- `aws s3 ls s3://noaa-nclimgrid-daily-pds/{access,archive}/ --no-sign-request` — vintage inventory
- https://mesonet.agron.iastate.edu/json/cli.py, /geojson/cli.py, /cgi-bin/afos/retrieve.py, /api/1/nwstext/, /json/cf6.py, /cgi-bin/request/daily.py, /geojson/network/*.geojson
- https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-stations.txt, ghcnd-inventory.txt, per-station access CSVs
- IEM Stage IV archive and mtarchive MRMS listings; `s3://noaa-mrms-pds`
- https://www2.census.gov/programs-surveys/cbp/datasets/2023/ (zbp23detail.zip downloaded and inspected); api.census.gov 302 → missing_key.html
- S3 listings of `tripdata`, `divvy-tripdata`, `capitalbikeshare-data`; Divvy 202601 and JC 202602 samples inspected
- https://divvybikes.com/data-license-agreement — licence grant and prohibitions
- https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page — URL pattern, 2-month lag
- Socrata catalog API and resources 5neh-572f, jyb9-n7fm, ajtu-isnz, 5wq4-mkjj, uczf-rk3c

### Secondary (MEDIUM)
- Keyless Kalshi rate limit: own measurement (one session, one IP)
- IEM daily-vs-CLI mismatch: own computation, Central Park only (2025–2026), not yet checked at other stations
- PRISM tmax day alignment: own computation, 7 stations × 6 days
- ins2 README/DATA.md (hl-mm, 2026-09-30) — nClimGrid day alignment, file md5s (cross-checked: AWS ETag of ncdd-202607-grd-scaled.nc = c1936678…, matching DATA.md)

### Tertiary (LOW)
- M5 mirror licence status; the PRISM early/provisional/stable mapping; Citi Bike licence text (assumed the same as Divvy's Lyft licence); Tri-Rail ridership granularity
- WebSearch was unavailable for this session (budget exhausted), so there was no broad ecosystem search beyond direct fetches

## Metadata

**Confidence breakdown:**
- Kalshi inventory and endpoints: HIGH. Every series was paginated and candles were spot-checked in 2021–2026.
- Station weather (CLI/GHCN/IEM): HIGH. The daily.py bias was measured directly.
- Gridded weather (nClimGrid/PRISM paths, lifecycle, day definition): HIGH. Vintage persistence on AWS is MEDIUM.
- Stage IV/MRMS: HIGH for paths, MEDIUM for tooling.
- Sales proxies: HIGH for access. MEDIUM for licences. Miami is a real gap.
- Census: HIGH (key requirement observed; bulk path downloaded).
- Throughput estimates: MEDIUM.

**Research date:** 2026-09-30
**Valid until:** about 2026-10-07 for Kalshi (the cutoff moves, and series and sources change often) and the nClimGrid mirror vintages; 30 days for the rest
