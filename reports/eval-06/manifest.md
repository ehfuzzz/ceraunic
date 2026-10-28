# EVAL-06 data manifest

Generated 2026-09-30T14:06:51Z. Raw trips were never stored: bikeshare zips were deleted after aggregation, Socrata and TLC were aggregated server-side / by remote column reads. Per-file lines: `data/cache/sales_daily/manifest.jsonl` (gitignored).

| source | files / requests | bytes streamed | rows read (trips or source rows) | unit-day rows out | first URL | last URL |
|---|---|---|---|---|---|---|
| divvy | 48 | 0.87 GB | 23,043,204 | 1,014,327 | https://divvy-tripdata.s3.amazonaws.com/202207-divvy-tripdata.zip | https://divvy-tripdata.s3.amazonaws.com/202606-divvy-tripdata.zip |
| cta | 1 | 0.02 GB | 214,117 | 214,117 | https://data.cityofchicago.org/resource/5neh-572f.json | https://data.cityofchicago.org/resource/5neh-572f.json |
| citibike | 32 | 23.73 GB | 174,941,408 | 2,928,738 | https://s3.amazonaws.com/tripdata/2022-citibike-tripdata.zip | https://s3.amazonaws.com/tripdata/202606-citibike-tripdata.zip |
| chitaxi | 50 | 0.01 GB | 26,988,782 | 116,501 | https://data.cityofchicago.org/resource/wrvz-psew.json#2022-07 | https://data.cityofchicago.org/resource/ajtu-isnz.json#2026-08 |
| tlc | 60 | 1.68 GB (+1 files size unknown) | 99,031,102 | 308,086 | https://d37ci6vzurychx.cloudfront.net/trip-data/yellow_tripdata_2022-07.parquet | https://d37ci6vzurychx.cloudfront.net/trip-data/green_tripdata_2024-12.parquet |
| divvy_named | 48 | 0.87 GB | 23,043,204 | 1,016,305 | https://divvy-tripdata.s3.amazonaws.com/202207-divvy-tripdata.zip | https://divvy-tripdata.s3.amazonaws.com/202606-divvy-tripdata.zip |

TLC bytes are the remote file sizes; DuckDB httpfs fetched only the pickup-time, zone and fare column chunks by HTTP range request. Chicago taxi `rows read` is the trip count summed server-side.

## Weather

NWS CLI (IEM, 2023-01-01..2026-09-29) spliced onto NOAA RCC-ACIS StnData (1990-01-01..). Agreement on the overlap:

```
{
 "NYC": {
  "overlap_days": 1366,
  "tmax_equal_share": 0.9956076134699854,
  "prcp_equal_share": 0.9963396778916545,
  "wet_flag_equal_share": 0.9992679355783309,
  "acis_rows": 13421,
  "acis_first": "1990-01-01",
  "cli_rows": 1366
 },
 "MDW": {
  "overlap_days": 1368,
  "tmax_equal_share": 0.9992690058479532,
  "prcp_equal_share": 0.9970760233918129,
  "wet_flag_equal_share": 0.9985380116959064,
  "acis_rows": 13421,
  "acis_first": "1990-01-01",
  "cli_rows": 1368,
  "snow_source": "KORD (ACIS) - KMDW has no snowfall"
 }
}
```

## Panels (unit-day rows with sales > 0, weather joined)

| group | active unit-days | units | first | last | file |
|---|---|---|---|---|---|
| G1 | 2,868,811 | 2562 | 2022-07-01 | 2026-06-30 | data/cache/sales_daily/panel_G1.parquet |
| G2 | 1,014,420 | 2494 | 2022-07-01 | 2026-06-30 | data/cache/sales_daily/panel_G2.parquet |
| G3 | 211,533 | 144 | 2022-07-01 | 2026-07-31 | data/cache/sales_daily/panel_G3.parquet |
| G4 | 116,496 | 77 | 2022-07-01 | 2026-08-31 | data/cache/sales_daily/panel_G4.parquet |
| G5 | 207,937 | 261 | 2022-07-01 | 2024-12-31 | data/cache/sales_daily/panel_G5.parquet |
