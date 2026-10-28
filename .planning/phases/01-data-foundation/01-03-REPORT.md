# 01-03 report: station weather

Status: complete. No OBJECTION. Pulled 2026-09-30 07:53Z-08:18Z.

## What was built
- `src/wi/data/iem.py` (`uv run python -m wi.data.iem`): resolves stations against the IEM network tables, pulls `daily.py` per station in calendar-year chunks, pulls NWS CLI and CF6 for the five settlement stations, writes raw CSVs and the cache files.
- Service check: ins1's `iem-*.csv` files have no header comments (columns `station,day,max_temp_f`). The service is `https://mesonet.agron.iastate.edu/cgi-bin/request/daily.py` (same default output, columns verified by pulling NYC 2026-07-20 to 07-22: values match the ins1 file, NYC 81 on 07-20).
- Outputs: `data/raw/iem/<STATION>.csv` (26 files, 5.4 MB), `data/raw/iem/cli/` (5 CLI + 5 CF6 files, 1.9 MB), `data/cache/weather/stations_daily.parquet`, `stations.csv`, plus `official_daily.parquet` (extra; CLI highs/lows/precip for the settlement stations).
- `docs/CONVENTIONS.md` section 8 and `data/manifests/DATA.md` (URLs, per-station rows and bytes, timestamp) written.

## Coverage (IEM daily, 2023-01-01 to 2026-09-29, 1,368 days each; full table with bytes in DATA.md)
All 26 requested stations returned data; none dropped. Missing-value counts (tmax / precip):

| group | station: tmax NaN / precip NaN |
|---|---|
| NY | NYC 0/0, LGA 0/0, JFK 0/0, HPN 0/44, FRG 2/17, ISP 0/0 |
| NJ | EWR 0/0, TTN 0/0, TEB 0/5, CDW 2/3, MMU 0/1069, BLM 66/596, SMQ 0/8 |
| IL/IN | MDW 0/0, ORD 0/0, PWK 0/1, DPA 14/12, UGN 0/0, GYY 14/1130 |
| FL | MIA 0/0, FLL 1/2, OPF 3/4, PBI 0/0, HWO 40/39, TMB 137/27, HST 5/425 |

Weak stations: TMB (10 % tmax gaps), BLM (5 %), HWO (3 %); precip is unusable at MMU, GYY, BLM, HST (gauge absent for long stretches).

## Deviations and findings
1. Network codes: TEB is `NJ_ASOS`, GYY is `IN_ASOS`; the brief grouped TEB under NY. Handled by looking each station up across the five tables.
2. PBI: IEM has no `PBI` id; Palm Beach Intl is carried as `DJT` (West Palm Beach) in `FL_ASOS`. Fetched as DJT, stored as `PBI` (`iem_id` column in stations.csv). The station id in `data/raw/iem/PBI.csv` is DJT.
3. Observation coverage: `daily.py` and `/api/1/daily.json` have no max/min observation-count field. Not available. Coverage is reported as non-missing daily values only.
4. Large requests: a single 2023-2026 request per station returned "server over capacity" (HTTP 503) repeatedly; year-sized requests succeeded. The fetcher chunks by year and retries with backoff.
5. Last day loaded is 2026-09-29 (UTC-yesterday); 2026-09-30 is a partial day and excluded.
6. Pandas gotcha fixed: the CLI CSV rows have a trailing comma, so `read_csv` shifted columns into the index; the code uses `index_col=False`.
7. `stations.csv` is long format: one row per (station, settlement station); NJ stations and EWR/TTN have two rows (distance to EWR and to TTN), other stations one.

## CF6 / CLI availability
- `/api/1/nws/cf6.json` and `/api/1/nws/cli.json`: do not exist (404; not in the `/api/1/openapi.json` path list).
- Available instead: `https://mesonet.agron.iastate.edu/json/cli.py` and `/json/cf6.py` (take `station` as a 4-letter ICAO, `year`, `fmt=csv`). Both returned data for KNYC, KEWR, KTTN, KMDW, KMIA from 2023-01-01 to 2026-09-29. CLI rows: NYC 1366, EWR 1366, TTN 1367, MDW 1368, MIA 1365 (MIA has 6 NaN highs). CLI includes the time of the high/low, normals and records; CF6 is the monthly preliminary table.
- Not checked: whether CLI highs are later revised after the first report (only the final IEM copy is stored, no vintages).

## IEM day definition vs the NWS climate day (details in CONVENTIONS.md section 8)
IEM docs: airport stations are summarised over standard time, "1 AM to 1 AM daylight time". That matches the NWS climate day window. Values still differ from the CLI: IEM tmax equals the official high on 50-64 % of days, is within 1 degF on 90-95 %, and averages 0.4-0.6 degF lower; 36-50 % of days are lower, under 1 % higher. By station (exact / within 1 / mean diff): NYC 0.57 / 0.94 / -0.46, EWR 0.57 / 0.93 / -0.51, TTN 0.58 / 0.93 / -0.48, MDW 0.64 / 0.95 / -0.40, MIA 0.50 / 0.90 / -0.60. DST months match slightly worse (54 % exact) than standard-time months (61 %). Outliers: NYC 2024-12-29 (IEM 68, CLI 60), EWR 2025-12-07 (IEM 44, CLI 63); not investigated. The consequence for plans 02 and 03: the IEM ASOS max is not the settlement value even at the settlement stations; use the CLI table for settlement checks.

## OBJECTION
None.
