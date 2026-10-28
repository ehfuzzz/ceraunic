# Data manifest (single source of truth for what exists)

Last consolidated 2026-09-30 (plan 01-06) from the 01-01, 01-02 and 01-03 reports. One table per dataset below: source, URL pattern, coverage, rows, bytes on disk, md5 or manifest file, pulled_utc, known gaps. Per-station and per-series detail tables follow the index. Raw files live under `data/raw/` and derived Parquet under `data/cache/` (both gitignored, re-pullable); manifests under `data/manifests/` are committed. Day, close-time and settlement conventions live only in `docs/CONVENTIONS.md`; this file does not restate them. `make data` runs the pulls in order and skips what exists (01-06); a row marked PLANNED has not been pulled. `scripts/pull_kalshi.py datamd` appends a Kalshi section in the old layout; do not run it on this file, edit D1 and the Kalshi detail by hand.

Dataset status: D1-D6 pulled; D7-D10 planned in 01-04 (not pulled at the time of writing); D11-D12 open (recorder not present yet; sales and Census pulls belong to 01-05 and Phases 4-5).

## D1. Kalshi markets and hourly candles (plan 01-02)

| field | value |
|---|---|
| source | Kalshi Trade API v2, keyless, read-only (live `/markets` plus archived `/historical/markets`) |
| URL pattern | `https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=S`, `/historical/markets?series_ticker=S`, candles `/series/S/markets/T/candlesticks?period_interval=60` (live) and `/historical/markets/T/candlesticks?period_interval=60` (archived); cutoff `GET /historical/cutoff` (2026-08-01 at pull time) |
| coverage | 61 series in the five cities, earliest NYC high 2021-07-18 (KXHIGHNY0) and 2021-08-07 (KXHIGHNY), CHI high 2021-08-20, MIA high 2023-05-12; last close dates run to 2027-01-01 (open markets) |
| rows | `markets.parquet` 34,495 markets; `candles.parquet` 1,113,358 candle rows (tz-aware UTC) |
| bytes on disk | raw JSON about 511 MB in 34,495 candle files under `data/raw/kalshi/series/<SERIES>/` (per-series bytes in the detail table); `data/cache/kalshi/markets.parquet` 1,825,855 B, `candles.parquet` 17,163,695 B |
| md5 / manifest | `data/manifests/kalshi-series.csv` (series list with counts; md5 0c861aac288a7ee56ba67827fca78e26); `markets.parquet` md5 57cdebbdb964fefb16bd210712288d42; `candles.parquet` md5 6c8453f403dedded70d6b400921d0db1; no per-file md5 for raw JSON (writes are atomic, tmp then rename) |
| pulled_utc | 2026-09-30 07:54Z to 10:24Z, consolidated 10:27Z |
| known gaps | 6-8 newest markets per series not yet traded (no candles); no ladder in the API on NY 2021-08-19, 2021-12-26/27, 2023-12-24, CHI 2021-09-20, 2021-12-26/27, 2023-12-24, MIA 2023-12-24; legacy strikes rebuilt from ticker (`strike_source`); hourly-directional series (about 99,000 markets) NOT pulled; `KXRAIN` (multi-city daily rain binary, from 2026-07-15) and `KXRAINWKND` are NOT pulled: they list with an empty city and `in_scope` False in `kalshi-series.csv`, so the five-city filter skipped them (daily rain history is `KXRAINNYC` only; a fix is to map their per-city market tickers, outside plan 01-06); no order-book history (see D11) |

## D2. Kalshi weather series list (plan 01-02)

| field | value |
|---|---|
| source | `GET /series` (no category filter), then the weather filter in `src/wi/data/kalshi.py` |
| URL pattern | `https://api.elections.kalshi.com/trade-api/v2/series` |
| coverage | 14,494 series listed, 441 weather-like, 61 in the five cities (counts filled for those 61) |
| rows | 441 (`data/manifests/kalshi-series.csv`) |
| bytes on disk | 31,158 B |
| md5 / manifest | the file itself; md5 0c861aac288a7ee56ba67827fca78e26 |
| pulled_utc | 2026-09-30 (two `discover` runs of about 61 s each, last before 10:27Z) |
| known gaps | legacy pre-KX series tickers list zero markets on their own; `KXMIASNOWM` is titled "Chicago Snowfall Monthly" in the list but resolves on Miami |

## D3. IEM ASOS daily summaries, 26 stations (plan 01-03)

| field | value |
|---|---|
| source | Iowa Environmental Mesonet `daily.py`, keyless |
| URL pattern | `https://mesonet.agron.iastate.edu/cgi-bin/request/daily.py?network=<NET>&stations=<ID>&sts=<YYYY-01-01>&ets=<YYYY-12-31>&format=csv` (calendar-year chunks) |
| coverage | 2023-01-01 to 2026-09-29, 1,368 rows per station |
| rows | 35,568 (26 stations x 1,368) |
| bytes on disk | 5,411,471 B raw (`data/raw/iem/<ST>.csv`, 26 files) |
| md5 / manifest | none per file; per-station bytes and gap counts in the detail table below; ins1 `iem-*.csv` held only station, day, max_temp_f |
| pulled_utc | 2026-09-30 07:53Z to 08:18Z |
| known gaps | tmax differs from the NWS CLI before 2025-10 (see `docs/CONVENTIONS.md` section 8); precip missing for MMU, GYY, BLM, HST; TMB 137 missing tmax; PBI is IEM id DJT; 2026-09-30 partial day excluded |

## D4. NWS official daily climate (CLI) and CF6, five settlement stations (plan 01-03)

| field | value |
|---|---|
| source | IEM parsed NWS products, keyless |
| URL pattern | `https://mesonet.agron.iastate.edu/json/cli.py?station=<KNYC, KEWR, KTTN, KMDW or KMIA>&year=<Y>&fmt=csv` and `.../json/cf6.py?station=<ICAO>&year=<Y>&fmt=csv` |
| coverage | 2023-01-01 to 2026-09-29, 1,365 to 1,368 rows per station |
| rows | 6,832 CLI rows (1366 + 1366 + 1367 + 1368 + 1365) |
| bytes on disk | CLI + CF6 raw 1,870,362 B (`data/raw/iem/cli/<ST>_<ICAO>_{cli,cf6}.csv`) |
| md5 / manifest | none per file; per-station table below |
| pulled_utc | 2026-09-30 07:53Z to 08:18Z |
| known gaps | 2 to 3 days per station not issued or not parsed, not filled; MIA 6 NaN highs; only the final IEM copy is stored, no issuance vintages (`afos/retrieve.py` would give them) |

## D5. Derived station tables (plan 01-03)

| field | value |
|---|---|
| source | built from D3 and D4 by `src/wi/data/iem.py` |
| URL pattern | n/a (local) |
| coverage | as D3 and D4 |
| rows | `stations_daily.parquet` 35,568; `official_daily.parquet` 6,832; `stations.csv` one row per (station, settlement station) |
| bytes on disk | `stations_daily.parquet` 137,255 B; `official_daily.parquet` 64,415 B; `stations.csv` 2,087 B |
| md5 / manifest | `stations_daily.parquet` 177c1523c0ae607c0a92724e7270b220; `official_daily.parquet` 1d4c13b5064a35900e2b4bc42b99965c; `stations.csv` 2f784fea62bd35ccf0931d36c74406bc |
| pulled_utc | built 2026-09-30 about 08:18Z |
| known gaps | inherited from D3 and D4; `precip_trace` flag marks 0.0001 in |

## D6. Imported ins2 grids: nClimGrid Jul and Aug 2026 scaled, Sep 2026 prelim (plan 01-01)

| field | value |
|---|---|
| source | copies from the hl-mm worktrees of files NCEI published; originals untouched, no network used |
| URL pattern | `https://www.ncei.noaa.gov/data/nclimgrid-daily/access/grids/2026/ncdd-YYYYMM-grd-scaled.nc or -prelim.nc` |
| coverage | 2026-07-01 to 2026-09-2x (September prelim, about 2 days behind) |
| rows | 3 `.nc` files plus `data/cache/ins2/cells.npz` (ins2 cell table) |
| bytes on disk | 57,115,170 + 57,244,383 + 49,100,699 B for the `.nc` files; `cells.npz` 203,088 B |
| md5 / manifest | `data/manifests/imported-2026-09-30.md` (md5 per file; matches `prior/hl-mm-ins/reports/ins2/DATA.md`) |
| pulled_utc | 2026-09-30 (copy); files created by NCEI per their `version.txt` |
| known gaps | `ncdd-202609-grd-scaled.nc` not yet published (expected about 2026-10-06); the ins1 candle cache was not found and is superseded by D1 |

## D7. nClimGrid-Daily 40 km disc subsets, 2024-01..2026-09 (plan 01-04) - PLANNED

| field | value |
|---|---|
| source | NCEI nClimGrid-Daily scaled grids and county averages |
| URL pattern | `https://www.ncei.noaa.gov/data/nclimgrid-daily/access/grids/{YYYY}/ncdd-{YYYYMM}-grd-scaled.nc`, `.../access/averages/{YYYY}/{tmax or prcp}-{YYYYMM}-cty-scaled.csv` |
| coverage | target 2024-01-01 to 2026-09-2x, five stations |
| rows | PLACEHOLDER: fill from `data/cache/grid_disc/source=nclimgrid` |
| bytes on disk | PLACEHOLDER (raw `.nc` deleted after subsetting, except the three 2026 files in D6) |
| md5 / manifest | `data/manifests/grids.csv` (planned) |
| pulled_utc | PLACEHOLDER |
| known gaps | PLACEHOLDER |

## D8. PRISM 4 km tmax and ppt disc subsets (plan 01-04) - PLANNED

| field | value |
|---|---|
| source | PRISM Group, Oregon State University, https://prism.oregonstate.edu, accessed <date> (citation required) |
| URL pattern | `https://services.nacse.org/prism/data/get/us/4km/{tmax or ppt}/{YYYYMMDD}?format=nc` |
| coverage | target 2024-01-01 to 2026-09-30 |
| rows | PLACEHOLDER: fill from `data/cache/grid_disc/source=prism` |
| bytes on disk | PLACEHOLDER (raw zips deleted after subsetting) |
| md5 / manifest | `data/manifests/grids.csv` (planned); grid count per day recorded |
| pulled_utc | PLACEHOLDER |
| known gaps | PLACEHOLDER; PRISM keeps no prior versions |

## D9. nClimGrid prelim vintages, AWS mirror (plan 01-04) - PLANNED

| field | value |
|---|---|
| source | `s3://noaa-nclimgrid-daily-pds/archive/2026/` (no-sign-request) |
| URL pattern | `nclimgrid-daily_v1-0-0_prelim_s<YYYYMMDD>_e<YYYYMMDD>_c<YYYYMMDD>.tar.gz` |
| coverage | target prelim tarballs from 2026-04-21 (148 listed at research time) |
| rows | PLACEHOLDER: `data/cache/vintages/nclimgrid_prelim.parquet` |
| bytes on disk | PLACEHOLDER (tarballs deleted after subsetting) |
| md5 / manifest | `data/manifests/grids.csv` (planned) |
| pulled_utc | PLACEHOLDER |
| known gaps | PLACEHOLDER; the mirror may prune vintages, research valid about 2026-10-07 |

## D10. GHCN-Daily station records (plan 01-04) - PLANNED

| field | value |
|---|---|
| source | NOAA NCEI GHCN-Daily |
| URL pattern | `https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/access/{ID}.csv` |
| coverage | target at least 30 stations, full record (1869 onward where it exists) |
| rows | PLACEHOLDER: `data/cache/ghcnd/<station>.parquet` |
| bytes on disk | PLACEHOLDER |
| md5 / manifest | `data/manifests/ghcnd.csv` (planned) |
| pulled_utc | PLACEHOLDER |
| known gaps | PLACEHOLDER; no current USW record for BLM, MMU, GYY |

## D11. Kalshi order-book recorder (hl-mm session) - NOT PULLED

| field | value |
|---|---|
| source | `s3://hlmm-reduced-5325/kalshi-weather-books/` (owned by the hl-mm session; read-only here) |
| URL pattern | S3 prefix above |
| coverage | none yet: prefix was not present at 08:0xZ on 2026-09-30 |
| rows | PLACEHOLDER |
| bytes on disk | 0 |
| md5 / manifest | PLACEHOLDER |
| pulled_utc | not pulled |
| known gaps | Kalshi keeps no book archive; until this exists executable prices come from hourly candle asks |

## D12. Sales stand-ins and business mix (plan 01-05, Phases 4-5) - PLANNED

| field | value |
|---|---|
| source | Citi Bike, Divvy, NYC TLC, Census ZBP/CBP bulk (keyless); Kaggle sets are owner-hand |
| URL pattern | `https://s3.amazonaws.com/tripdata/`, `https://divvy-tripdata.s3.amazonaws.com/{YYYYMM}-divvy-tripdata.zip`, `https://www2.census.gov/programs-surveys/cbp/datasets/2023/` |
| coverage | PLACEHOLDER |
| rows | PLACEHOLDER: `data/cache/sales_daily/` |
| bytes on disk | PLACEHOLDER |
| md5 / manifest | PLACEHOLDER (`data/manifests/sales.csv` planned) |
| pulled_utc | PLACEHOLDER |
| known gaps | demand proxies are trip counts, not revenue; timestamps are local clock time |

---

# Detail: IEM station weather (D3-D5)

Pulled 2026-09-30, 07:53Z to 08:18Z (UTC), keyless public GETs from mesonet.agron.iastate.edu, sequential, 1 s sleep, calendar-year chunks. Code: `src/wi/data/iem.py` (`uv run python -m wi.data.iem`). Raw CSVs are gitignored and re-pullable; this manifest is committed.


### URLs
- ASOS daily summary: `https://mesonet.agron.iastate.edu/cgi-bin/request/daily.py?network=<NET>&stations=<IEM_ID>&sts=<YYYY-01-01>&ets=<YYYY-12-31 or 2026-09-29>&format=csv` (default columns: max/min temp, dewpoint, precip, wind, rh, climo, snow, feel, srad). Column set and service match the ins1 `iem-*.csv` files (those held only station, day, max_temp_f).
- Station tables: `https://mesonet.agron.iastate.edu/api/1/network/{NY,NJ,IL,IN,FL}_ASOS.json`
- NWS official daily climate (CLI, final daily report): `https://mesonet.agron.iastate.edu/json/cli.py?station=<KNYC|KEWR|KTTN|KMDW|KMIA>&year=<2023..2026>&fmt=csv`
- NWS CF6 (monthly preliminary table): `https://mesonet.agron.iastate.edu/json/cf6.py?station=<ICAO>&year=<year>&fmt=csv`
- There is no `/api/1/nws/cf6.json` or `/api/1/nws/cli.json` (404; absent from `/api/1/openapi.json`). The `/json/` endpoints above are the working ones.

### Station notes
- TEB is in `NJ_ASOS` (not NY); GYY is in `IN_ASOS`; all other stations are in the network of their state. PBI is carried by IEM as `DJT` in `FL_ASOS` (`PBI` returns "No stations found"); raw file `PBI.csv` holds station id DJT. No requested station was dropped.
- Date coverage, all 26 stations: 2023-01-01 to 2026-09-29 (1,368 rows each). 2026-09-30 excluded (partial day).
- No max/min observation-count or coverage column exists in `daily.py` (nor in `/api/1/daily.json`). Coverage here means non-missing daily values, below.

### Rows and gaps per station (IEM daily)
| station | network | rows | first | last | raw bytes | tmax NaN | tmin NaN | precip NaN |
|---|---|---|---|---|---|---|---|---|
| NYC | NY_ASOS | 1368 | 2023-01-01 | 2026-09-29 | 208374 | 0 | 0 | 0 |
| LGA | NY_ASOS | 1368 | 2023-01-01 | 2026-09-29 | 209509 | 0 | 0 | 0 |
| JFK | NY_ASOS | 1368 | 2023-01-01 | 2026-09-29 | 208205 | 0 | 0 | 0 |
| TEB | NJ_ASOS | 1368 | 2023-01-01 | 2026-09-29 | 209683 | 0 | 0 | 5 |
| HPN | NY_ASOS | 1368 | 2023-01-01 | 2026-09-29 | 209484 | 0 | 0 | 44 |
| FRG | NY_ASOS | 1368 | 2023-01-01 | 2026-09-29 | 208580 | 2 | 2 | 17 |
| ISP | NY_ASOS | 1368 | 2023-01-01 | 2026-09-29 | 208197 | 0 | 0 | 0 |
| EWR | NJ_ASOS | 1368 | 2023-01-01 | 2026-09-29 | 209578 | 0 | 0 | 0 |
| TTN | NJ_ASOS | 1368 | 2023-01-01 | 2026-09-29 | 207905 | 0 | 0 | 0 |
| CDW | NJ_ASOS | 1368 | 2023-01-01 | 2026-09-29 | 208471 | 2 | 2 | 3 |
| MMU | NJ_ASOS | 1368 | 2023-01-01 | 2026-09-29 | 201931 | 0 | 0 | 1069 |
| BLM | NJ_ASOS | 1368 | 2023-01-01 | 2026-09-29 | 202930 | 66 | 66 | 596 |
| SMQ | NJ_ASOS | 1368 | 2023-01-01 | 2026-09-29 | 207480 | 0 | 0 | 8 |
| MDW | IL_ASOS | 1368 | 2023-01-01 | 2026-09-29 | 211759 | 0 | 0 | 0 |
| ORD | IL_ASOS | 1368 | 2023-01-01 | 2026-09-29 | 209609 | 0 | 0 | 0 |
| PWK | IL_ASOS | 1368 | 2023-01-01 | 2026-09-29 | 211579 | 0 | 0 | 1 |
| DPA | IL_ASOS | 1368 | 2023-01-01 | 2026-09-29 | 212038 | 14 | 14 | 12 |
| UGN | IL_ASOS | 1368 | 2023-01-01 | 2026-09-29 | 212158 | 0 | 0 | 0 |
| GYY | IN_ASOS | 1368 | 2023-01-01 | 2026-09-29 | 202524 | 14 | 14 | 1130 |
| MIA | FL_ASOS | 1368 | 2023-01-01 | 2026-09-29 | 208969 | 0 | 1 | 0 |
| FLL | FL_ASOS | 1368 | 2023-01-01 | 2026-09-29 | 208187 | 1 | 0 | 2 |
| OPF | FL_ASOS | 1368 | 2023-01-01 | 2026-09-29 | 209069 | 3 | 4 | 4 |
| TMB | FL_ASOS | 1368 | 2023-01-01 | 2026-09-29 | 202694 | 137 | 138 | 27 |
| HWO | FL_ASOS | 1368 | 2023-01-01 | 2026-09-29 | 208462 | 40 | 39 | 39 |
| PBI (IEM DJT) | FL_ASOS | 1368 | 2023-01-01 | 2026-09-29 | 208347 | 0 | 0 | 0 |
| HST | FL_ASOS | 1368 | 2023-01-01 | 2026-09-29 | 205749 | 5 | 5 | 425 |

Total raw ASOS bytes 5,411,471. Precip NaN is large for MMU (1069), GYY (1130), BLM (596), HST (425): those sites do not report a precip gauge for much of the period; do not use their precip.

### NWS official daily (CLI) for settlement stations
| station | ICAO | rows | first | last | high NaN | CLI bytes | CF6 bytes |
|---|---|---|---|---|---|---|---|
| NYC | KNYC | 1366 | 2023-01-01 | 2026-09-29 | 0 | 246276 | 137237 |
| EWR | KEWR | 1366 | 2023-01-01 | 2026-09-29 | 0 | 253719 | 146191 |
| TTN | KTTN | 1367 | 2023-01-01 | 2026-09-29 | 0 | 244052 | 144764 |
| MDW | KMDW | 1368 | 2023-01-01 | 2026-09-29 | 0 | 200704 | 125318 |
| MIA | KMIA | 1365 | 2023-01-01 | 2026-09-29 | 6 | 228097 | 144004 |

CLI raw files: `data/raw/iem/cli/<ST>_<ICAO>_{cli,cf6}.csv` (1,870,362 bytes total). Days missing from CLI (2-3 per station) are days the product was not issued/parsed; not filled.

### Derived (gitignored, in data/cache/weather/)
- `stations_daily.parquet` (35,568 rows; 137,255 bytes): station, date_local, tmax_f, tmin_f, precip_in, tmax_missing, tmin_missing, precip_missing, precip_trace, src.
- `stations.csv` (2,087 bytes): station, iem_id, name, lat, lon, network, group, settlement, distance_km (haversine). Long format: EWR/TTN and the NJ stations have one row per NJ settlement station.
- `official_daily.parquet` (64,415 bytes): station (settlement code), date_local, high_f, low_f, precip_in, high_time, low_time, src (nws_cli). Not requested in the brief; added for the settlement-source comparison.


---

# Detail: Kalshi (D1-D2)

Written 2026-09-30T10:27Z (plan 01-02).

Source: keyless Kalshi trade-api v2 (live `/markets` + archived `/historical/markets`, hourly candles). Raw JSON under `data/raw/kalshi/series/<SERIES>/` (gitignored); consolidated to `data/cache/kalshi/markets.parquet` and `candles.parquet` (UTC). Series list: `data/manifests/kalshi-series.csv`.

| series | city | markets | settled | first close | last close | candle rows | markets with candles | bytes on disk | last pull (UTC) | gaps / errors |
|---|---|---|---|---|---|---|---|---|---|---|
| KXCHISNOWM | CHI | 35 | 35 | 2025-12-09 | 2026-04-01 | 13294 | 35 | 4313991 | 2026-09-30T09:53:06 | none |
| KXCHISNOWXMAS | CHI | 1 | 1 | 2025-12-26 | 2025-12-26 | 323 | 1 | 110514 | 2026-09-30T09:53:06 | none |
| KXEMERGENCYMIA | MIA | 1 | 1 | 2023-12-01 | 2023-12-01 | 35 | 1 | 13945 | 2026-09-30T09:53:06 | none |
| KXHIGHCHI | CHI | 9661 | 9643 | 2021-08-20 | 2026-10-02 | 248165 | 9655 | 106728804 | 2026-09-30T09:53:11 | 6 markets with no candle rows |
| KXHIGHMIA | MIA | 7432 | 7414 | 2023-05-12 | 2026-10-02 | 188661 | 7426 | 81378755 | 2026-09-30T09:53:16 | 6 markets with no candle rows |
| KXHIGHNY | NY | 9664 | 9646 | 2021-08-07 | 2026-10-02 | 246157 | 9658 | 105258442 | 2026-09-30T09:53:21 | 6 markets with no candle rows |
| KXHIGHNY0 | NY | 21 | 21 | 2021-07-18 | 2021-08-06 | 346 | 21 | 150917 | 2026-09-30T09:53:27 | none |
| KXHIGHTEWR | EWR | 222 | 204 | 2026-08-27 | 2026-10-02 | 6648 | 216 | 2922196 | 2026-09-30T09:53:32 | 6 markets with no candle rows |
| KXHIGHTTTN | TTN | 222 | 204 | 2026-08-27 | 2026-10-02 | 6440 | 216 | 2833665 | 2026-09-30T09:53:35 | 6 markets with no candle rows |
| KXHURMIA | MIA | 15 | 15 | 2022-12-01 | 2024-12-01 | 4446 | 15 | 1453933 | 2026-09-30T09:53:42 | none |
| KXHURNYC | NY | 13 | 13 | 2022-12-01 | 2024-12-01 | 1171 | 13 | 402901 | 2026-09-30T09:53:47 | none |
| KXLOWTCHI | CHI | 1758 | 1740 | 2025-12-14 | 2026-10-02 | 62511 | 1752 | 26330496 | 2026-09-30T10:01:17 | 6 markets with no candle rows |
| KXLOWTEWR | EWR | 222 | 204 | 2026-08-27 | 2026-10-02 | 5734 | 216 | 2580407 | 2026-09-30T10:02:12 | 6 markets with no candle rows |
| KXLOWTMIA | MIA | 1758 | 1740 | 2025-12-14 | 2026-10-02 | 63210 | 1752 | 26622779 | 2026-09-30T10:09:40 | 6 markets with no candle rows |
| KXLOWTNYC | NY | 1758 | 1740 | 2025-12-14 | 2026-10-02 | 62454 | 1752 | 26489645 | 2026-09-30T10:17:01 | 6 markets with no candle rows |
| KXLOWTTTN | TTN | 222 | 204 | 2026-08-27 | 2026-10-02 | 5296 | 216 | 2431443 | 2026-09-30T10:17:57 | 6 markets with no candle rows |
| KXMIASNOWM | MIA | 12 | 12 | 2026-01-01 | 2026-04-01 | 4718 | 12 | 1531437 | 2026-09-30T10:18:00 | none |
| KXMINNYC | NY | 6 | 6 | 2021-12-02 | 2022-04-01 | 801 | 6 | 268415 | 2026-09-30T10:18:01 | none |
| KXNYCSNOWM | NY | 28 | 28 | 2025-12-15 | 2026-04-01 | 16752 | 28 | 5471084 | 2026-09-30T10:18:07 | none |
| KXNYCSNOWXMAS | NY | 1 | 1 | 2025-12-26 | 2025-12-26 | 325 | 1 | 111053 | 2026-09-30T10:18:10 | none |
| KXRAINCHIM | CHI | 84 | 77 | 2025-07-01 | 2026-10-01 | 32884 | 84 | 11183784 | 2026-09-30T10:18:31 | none |
| KXRAINDNYC | NY | 1 | 1 | 2026-09-20 | 2026-09-20 | 172 | 1 | 73617 | 2026-09-30T10:18:32 | none |
| KXRAINMIAM | MIA | 86 | 70 | 2025-12-01 | 2026-10-01 | 39412 | 86 | 13359811 | 2026-09-30T10:18:56 | none |
| KXRAINNY | NY | 31 | 31 | 2021-08-02 | 2021-09-03 | 644 | 31 | 267041 | 2026-09-30T10:19:05 | none |
| KXRAINNYC | NY | 895 | 895 | 2021-09-09 | 2026-07-16 | 19913 | 895 | 8476852 | 2026-09-30T10:23:00 | none |
| KXRAINNYCM | NY | 224 | 199 | 2024-03-01 | 2027-01-01 | 66572 | 216 | 21965653 | 2026-09-30T10:23:55 | 8 markets with no candle rows |
| KXRAINNYCW | NY | 4 | 0 | 2026-10-05 | 2026-10-05 | 61 | 4 | 29496 | 2026-09-30T10:23:56 | none |
| KXRAINSNYC | NY | 10 | 10 | 2026-09-28 | 2026-09-28 | 697 | 10 | 276422 | 2026-09-30T10:24:00 | none |
| KXSNOWNY | NY | 17 | 17 | 2021-12-26 | 2022-02-20 | 479 | 17 | 187671 | 2026-09-30T10:24:04 | none |
| KXSNOWNYM | NY | 91 | 91 | 2021-12-03 | 2025-03-03 | 15037 | 91 | 4999741 | 2026-09-30T10:24:28 | none |

Notes on the Kalshi table above (plan 01-02):
- "last pull" is the final resume pass; the full pull ran 2026-09-30 07:54Z to 10:24Z (one disk-full abort at 08:56Z, resumed 08:57Z; no data lost, writes are atomic).
- "markets with no candle rows" are markets not yet traded: status `initialized` (opens later) for the 6-8 newest markets per series. No settled market is missing candles.
- Live `/markets` only serves markets closed after the historical cutoff (2026-08-01); older markets come from `/historical/markets` and `/historical/markets/{ticker}/candlesticks`. Legacy pre-KX tickers (`HIGHNY-21AUG06-T86`, `HIGHCHI-...`, `HIGHMIA-...`) are served under the KX `series_ticker`; the legacy series tickers `HIGHNY`, `HIGHCHI`, `HIGHMIA`, `HIGHNY0`, `RAINNY`, `SNOWNY`, etc. list zero markets on their own. `legacy_prefix` marks them in `markets.parquet` (KXHIGHNY 5,416, KXHIGHCHI 5,413, KXHIGHMIA 3,184).
- Calendar days with no ladder in the API for the temperature series: KXHIGHNY 2021-08-19, 2021-12-26, 2021-12-27, 2023-12-24; KXHIGHCHI 2021-09-20, 2021-12-26, 2021-12-27, 2023-12-24; KXHIGHMIA 2023-12-24. KXHIGHTEWR/TTN and KXLOWT* have no gaps since launch.
- Legacy temperature markets carry no `floor_strike`/`cap_strike` in the API; `markets.parquet` rebuilds them from the ticker (`T<n>`, `B<x.5>`) and subtitle (`strike_source` = `ticker`; `api` otherwise). Checked against `expiration_value` and `result`: api rows 17,316/17,316 consistent, ticker-rebuilt rows 99.85%. Non-temperature series (rain/snow/hurricane) keep NaN strikes where the API has none (450 markets, `strike_source` empty).
- Not pulled: hourly-directional series `KXTEMPNYCH` (63,328 markets), `KXTEMPNYCHS`, `KXTEMPCHIH`, `KXTEMPCHIHS`, `KXTEMPMIAH` (about 99,000 markets, roughly 6 h at 5 req/s). Re-run with `pull --all-weather --include-hourly` if wanted. Weather series in the five cities with zero markets (KXLOWNY, KXLOWNYC, KXLOWCHI, KXLOWMIA, KXSNOWCHIM, KXSNOWNYC, KXRAINMIA, KXHIGHNYD, KXWEEKHT*, KXTEMPCHIMETROHS and all pre-KX names) are listed in `kalshi-series.csv` with empty counts.
- `KXMIASNOWM` is titled "Chicago Snowfall Monthly" in the series list, but its markets resolve on Miami snowfall; city is taken from the ticker (MIA).

## D11 filled 2026-09-30 — Kalshi order-book recorder (hl-mm)
See PROJECT.md "Recorder" for prefix, schema, cadence and the alive check. Not pulled into this repo yet; consumed by 17-03.

# Data manifest (plan 01-04, gridded weather + GHCN-Daily)

Pulled 2026-09-30 (UTC 13:20Z to 15:36Z). Code: `src/wi/data/grids.py`, `src/wi/data/ghcnd.py`, driver `scripts/pull_grids.py` (`nclimgrid | county | prism | assemble-prism | vintages | ghcnd`). Per-file manifests (url, bytes, md5, fetched_utc, source_version, retained): `data/manifests/grids.csv` (2,187 rows), `data/manifests/ghcnd.csv` (36 rows). Raw grid files were streamed, subset and deleted; only the three 2026 nClimGrid files that already existed stay in `data/raw/nclimgrid`.

## Outputs (gitignored, under data/cache/)
- `grid_disc/source={nclimgrid|prism}/station={NYC|EWR|TTN|MDW|MIA}/part-YYYYMM.parquet`: every cell within 40 km (haversine, station coordinates from `weather/stations.csv`) with data. Columns: source, station, cell_id (`lat_lon`, 4 dp), lat, lon, dist_km, label_day, cli_day (= label_day - 1), tmax_f_tenths, tmin_f_tenths (nClimGrid only), prcp_hundredths_in, status (`scaled`/`prelim`/`an91d`), prism_release_tmax, prism_release_ppt (PRISM grid count 1-8, null for nClimGrid). Discs overlap (NYC/EWR), so a cell can appear under two stations.
- `grid_county/nclimgrid_county_daily.parquet`: NCEI county averages (tmax, tmin, prcp) for New York NY, Essex NJ, Mercer NJ, Cook IL, Miami-Dade FL, joined on the state-prefixed county name (`NY: New York County`, `NJ: Essex County`, ...). The NCEI county ids are not FIPS and "Essex"/"Mercer" exist in two states.
- `vintages/nclimgrid_prelim.parquet`: (vintage_created, label_day, station, cell_id, tmax_f_tenths, prcp_hundredths_in) from every 3rd of the 148 prelim tarballs in `s3://noaa-nclimgrid-daily-pds/archive/2026/` since 2026-04-21 (50 vintages, 2.14 GB transferred of 6.18 GB; the 2.5 GB budget rule). Each vintage holds the month-to-date days it covers.
- `prism_days/{tmax,ppt}/YYYYMMDD.npz`: tiny per-day disc values plus the PRISM release number; the resume point that keeps the same PRISM file from being downloaded twice.
- `prism_stn/prism_{tmax,ppt}_20260715.stn.csv`: PRISM input-station lists for one day (national files, not per disc) for the contamination check.
- `ghcnd/<GHCN-id>.parquet`: 33 stations, full record (1843- for EWR, 1869- NYC), TMAX/TMIN in degF tenths, PRCP/SNOW in hundredths of an inch, measurement/quality/source flags, TMAX/TMIN observation time. Resolved id table with distances: `data/manifests/ghcnd-stations-resolved.csv`.

## Facts and limits
- Window: nClimGrid label_day 2024-01-01..2026-09-26 (September 2026 is the prelim file, last value label 09-26); cli_day therefore 2023-12-31..2026-09-25. PRISM label_day 2024-01-01..2026-09-29 (09-30 not published when pulled), cli_day 2023-12-31..2026-09-28.
- One PRISM file is missing: tmax 2026-08-01. It had already been downloaded once earlier the same day by the research pass, so the service refused a second copy inside 24 h (non-zip reply). Its precipitation file is present. Fill with `uv run python scripts/pull_grids.py prism` after 2026-10-01 15:00Z (only that file is requested; everything else is cached).
- GHCN-Daily access CSVs end 2026-09-22 (2026-09-19 for some; LAKEHURST 2026-03-12): about a week of publication lag. The five settlement stations agree with the NWS CLI high (`official_daily.parquet`) on 99.7-100 % of the 335 days 2025-10-01..2026-08-31 (NYC 100 %, EWR 99.7 %, TTN 99.7 %, MDW 100 %, MIA 100 %; conversion round(TMAX tenths degC x 9/5 + 320) / 10).
- No GHCN-Daily record with a current TMAX exists within 2.5 km of IEM MMU, GYY, BLM or JRB. LOT resolves to `USC00117457` (Romeoville WFO, a coop station 1.0 km away, not an ASOS). Four extra USW stations (JOLIET, LAKEHURST, PHL, POMPANO) were added for the 33.
- PRISM discs hold more cells than nClimGrid discs (coastal cells that nClimGrid masks): NYC 299 vs 240, EWR 297 vs 255, TTN 305 vs 307, MDW 256 vs 236, MIA 206 vs 175.
- PRISM release (grid count) over the window: 821 days at 8 (final), 1-7 for the most recent ~7 months; nClimGrid `status` says `scaled` for 974 days and `prelim` for 26.
- Nearest-cell tmax (cli_day join) vs the NWS CLI high, whole window: nClimGrid RMSE 2.05 / 2.13 / 1.85 / 2.32 / 1.30 degF and PRISM 1.89 / 2.27 / 1.56 / 2.16 / 1.10 (NYC / EWR / TTN / MDW / MIA). Spot check from the plan: PRISM NYC cell label 2026-07-30 = 81.2 degF vs official 2026-07-29 = 80 degF (difference 1.2).
