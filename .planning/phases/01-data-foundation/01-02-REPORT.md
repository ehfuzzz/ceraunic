# 01-02 Kalshi history: report

Worker: worker. Date: 2026-09-30. Keyless, read-only, no orders, no key sent. Nothing staged or committed.

## Deliverables

- `src/wi/data/kalshi.py`: series list + weather/city filter, markets (live + archived), hourly candles, raw writer, consolidation.
- `scripts/pull_kalshi.py`: typer CLI with `discover`, `pull --series A,B | --all-weather [--include-hourly]`, `consolidate`, `datamd`.
- `data/manifests/kalshi-series.csv` (441 weather-like series, 61 in the five cities; counts filled for those 61).
- `data/manifests/DATA.md`: Kalshi section appended (per-series table and notes). The file already existed from plan 01-03; I only appended.
- Raw: `data/raw/kalshi/series/<SERIES>/{markets.json,<TICKER>.candles.json,pull-log.json}` (511 MB, 34,495 candle files, gitignored).
- Cache: `data/cache/kalshi/markets.parquet` (34,495 rows, 1.8 MB), `candles.parquet` (1,113,358 rows, 17 MB). All timestamps tz-aware UTC. Columns include `series_ticker, event_ticker, market_ticker, city` (+ `floor_strike, cap_strike, strike_source, event_date, legacy_prefix, settled, result, open/close/expiration/settlement times` in markets; `ts` = candle end, bid/ask/price OHLC, volume, open_interest in candles).

## Endpoint shapes (base `https://api.elections.kalshi.com/trade-api/v2`)

```
curl -s "$B/series"                                                     # all 14,494 series in one response (no cursor)
curl -s "$B/historical/cutoff"                                          # {"market_settled_ts":"2026-08-01T00:00:00Z",...}
curl -s "$B/markets?series_ticker=KXHIGHNY&limit=1000&cursor=$C"        # live: markets closed after the cutoff + open ones
curl -s "$B/historical/markets?series_ticker=KXHIGHNY&limit=1000&cursor=$C"   # archived, back to 2021-08
curl -s "$B/series/KXHIGHNY/markets/KXHIGHNY-26SEP28-T71/candlesticks?start_ts=1790517600&end_ts=1790661600&period_interval=60"   # live candles
curl -s "$B/historical/markets/KXHIGHNY-26FEB14-T47/candlesticks?start_ts=<open>&end_ts=<close+3600>&period_interval=60"         # archived candles
```

- The ins1 call (`/series/S/markets/T/candlesticks`) returns 404 for any market settled before 2026-08-01. Those need `/historical/...`. The code routes by close time against `/historical/cutoff` and falls back to the other route on 404.
- Live candles use `*_dollars`/`*_fp` keys; historical use bare `open/high/low/close/volume`. Both normalised to floats in dollars.
- Candle window per market is `open_time` to `min(close_time, now) + 1 h`, in 4,500-candle chunks (cap is 5,000). Sparse: hours with no quote are absent.
- `/series` does not paginate; the code still follows a cursor if one appears. The batch `/markets/candlesticks` returned nothing for archived tickers, so one request per market (about 1.0-1.5 requests each).

## Series inventory (five cities)

| series | city | markets | settled | first close | last close | candle rows |
|---|---|---|---|---|---|---|
| KXHIGHNY | NY | 9,664 | 9,646 | 2021-08-07 | 2026-10-02 | 246,157 |
| KXHIGHNY0 (legacy `HIGHNY0-`, 2021-07) | NY | 21 | 21 | 2021-07-18 | 2021-08-06 | 346 |
| KXHIGHCHI | CHI | 9,661 | 9,643 | 2021-08-20 | 2026-10-02 | 248,165 |
| KXHIGHMIA | MIA | 7,432 | 7,414 | 2023-05-12 | 2026-10-02 | 188,661 |
| KXHIGHTEWR | EWR | 222 | 204 | 2026-08-27 | 2026-10-02 | 6,648 |
| KXHIGHTTTN | TTN | 222 | 204 | 2026-08-27 | 2026-10-02 | 6,440 |
| KXLOWTNYC | NY | 1,758 | 1,740 | 2025-12-14 | 2026-10-02 | 62,454 |
| KXLOWTCHI | CHI | 1,758 | 1,740 | 2025-12-14 | 2026-10-02 | 62,511 |
| KXLOWTMIA | MIA | 1,758 | 1,740 | 2025-12-14 | 2026-10-02 | 63,210 |
| KXLOWTEWR | EWR | 222 | 204 | 2026-08-27 | 2026-10-02 | 5,734 |
| KXLOWTTTN | TTN | 222 | 204 | 2026-08-27 | 2026-10-02 | 5,296 |
| KXRAINNYC (daily) | NY | 895 | 895 | 2021-09-09 | 2026-07-16 | 19,913 |
| KXRAINNY | NY | 31 | 31 | 2021-08-02 | 2021-09-03 | 644 |
| KXRAINNYCM (monthly) | NY | 224 | 199 | 2024-03-01 | 2027-01-01 | 66,572 |
| KXRAINNYCW (weekly) | NY | 4 | 0 | 2026-10-05 | 2026-10-05 | 61 |
| KXRAINDNYC | NY | 1 | 1 | 2026-09-20 | 2026-09-20 | 172 |
| KXRAINSNYC (rainstorm) | NY | 10 | 10 | 2026-09-28 | 2026-09-28 | 697 |
| KXRAINCHIM (monthly) | CHI | 84 | 77 | 2025-07-01 | 2026-10-01 | 32,884 |
| KXRAINMIAM (monthly) | MIA | 86 | 70 | 2025-12-01 | 2026-10-01 | 39,412 |
| KXSNOWNY | NY | 17 | 17 | 2021-12-26 | 2022-02-20 | 479 |
| KXSNOWNYM (monthly) | NY | 91 | 91 | 2021-12-03 | 2025-03-03 | 15,037 |
| KXNYCSNOWM | NY | 28 | 28 | 2025-12-15 | 2026-04-01 | 16,752 |
| KXNYCSNOWXMAS | NY | 1 | 1 | 2025-12-26 | 2025-12-26 | 325 |
| KXCHISNOWM | CHI | 35 | 35 | 2025-12-09 | 2026-04-01 | 13,294 |
| KXCHISNOWXMAS | CHI | 1 | 1 | 2025-12-26 | 2025-12-26 | 323 |
| KXMIASNOWM | MIA | 12 | 12 | 2026-01-01 | 2026-04-01 | 4,718 |
| KXMINNYC | NY | 6 | 6 | 2021-12-02 | 2022-04-01 | 801 |
| KXHURNYC / KXHURMIA | NY / MIA | 13 / 15 | 13 / 15 | 2022-12 | 2024-12 | 1,171 / 4,446 |
| KXEMERGENCYMIA | MIA | 1 | 1 | 2023-12-01 | 2023-12-01 | 35 |

Bytes on disk, pull timestamps and per-series gaps are in `data/manifests/DATA.md`. Totals: 34,495 markets (34,263 finalized, 60 closed, 104 active, 68 not yet open), 1,113,358 candle rows, 511 MB raw.

Legacy check: the pre-KX series `HIGHNY`, `HIGHCHI`, `HIGHMIA`, `HIGHNY0`, `RAINNY`, `RAINNYC`, `SNOWNY`, `SNOWNYM`, `MINNYC`, etc. exist in `/series` but list zero markets on their own in both `/markets` and `/historical/markets`. The legacy markets are served under the KX `series_ticker`: `HIGHNY-21AUG06-T86` comes back from `series_ticker=KXHIGHNY` (flag `legacy_prefix`: NY 5,416, CHI 5,413, MIA 3,184 markets). Only `KXHIGHNY0` (`HIGHNY0-21JUL17-T90`) is a separate 21-market legacy series; it was pulled.

## How far back, per city

| city | daily high ladder | daily low ladder | rain | snow |
|---|---|---|---|---|
| NY (Central Park) | 2021-08-06 (1,879 event days) | 2025-12-14 | daily 2021-08 (KXRAINNY), 2021-09 to 2026-07 (KXRAINNYC); monthly 2024-03; week/storm 2026-09 | 2021-12 (monthly 2021-12 to 2025-03, then 2025-12 to 2026-04) |
| CHI (Midway) | 2021-08-19 (1,866 days) | 2025-12-14 | monthly 2025-07 | monthly 2025-12 |
| MIA | 2023-05-11 (1,239 days) | 2025-12-14 | monthly 2025-12 | monthly 2026-01 |
| EWR | 2026-08-26 (37 days) | 2026-08-26 | none | none |
| TTN | 2026-08-26 (37 days) | 2026-08-26 | none | none |

## Findings that touch `docs/CONVENTIONS.md` (for the seat; I did not edit it)

1. Close times are not constant. KXHIGHNY: 03:59Z (EDT) / 04:59Z (EST) through 2026-08-14, then 05:00Z from 2026-08-15. KXHIGHCHI: 03:59Z/04:59Z through 2024 (same as NY, Eastern-time close), 04:59Z/05:59Z in 2025, mostly 05:59Z in 2026 to 2026-08-14, then 06:00Z. The convention "Chicago closes 06:00Z, others 03:59Z" holds only for the newest 294 Chicago markets, and NY/MIA are 03:59Z only in EDT months; use `close_time` from `markets.parquet`, not a constant.
2. Settlement source changes in the rules text. `rules_primary` names the NWS Climatological Report (Central Park, Midway, Miami) for markets closing up to 2026-08-14 and The Weather Company from 2026-08-15 (294 markets per city so far). NY before 2022-03-05 and Chicago before 2025-03-06 use older wording (no source named). The ins1 TWC-vs-NWS mismatch sample (since 2026-07-24) therefore mostly covers the NWS-rule era, not TWC. Worth a line in section 4 and in any Phase 2 mismatch count.
3. Legacy temperature markets have no floor/cap in the API. Rebuilt from ticker and subtitle, `strike_source = "ticker"` (2,871 markets); validated against `expiration_value` and `result`: 17,316/17,316 consistent on API strikes, 99.85% on rebuilt strikes. Three early exceptions (for example `HIGHCHI-21OCT01-T84`, `>84°`, value 84, result yes) look like early-market rule quirks, left as is.
4. Missing ladder days in the API (not pull errors): NY 2021-08-19, 2021-12-26/27, 2023-12-24; CHI 2021-09-20, 2021-12-26/27, 2023-12-24; MIA 2023-12-24.
5. `KXMIASNOWM` is titled "Chicago Snowfall Monthly" in `/series`; its rules resolve on Miami snowfall. City taken from the ticker.

## Run

- Wall time about 2 h 30 min: pull 07:54Z to 10:24Z on 2026-09-30, plus two 61 s `discover` runs, a 14 s `consolidate`. About 44,000 requests, 4 worker threads behind a shared 5 req/s limiter (observed 3.5-4.2 req/s), backoff on 429/5xx/network errors. Zero candle errors, zero 404-on-both.
- One incident: the laptop data volume hit 100% full at 08:56Z (1.4 GB free, not caused by this pull; raw is 511 MB) and the first pull process died mid-KXHIGHCHI on ENOSPC. Writes are atomic (tmp then rename), so nothing partial remained (all 34k JSON files parse). I added a wait-and-retry on ENOSPC to `write_json`, resumed, and the resume logic skipped 4,125 already-written settled CHI markets. The volume had 6.2 GB free afterwards. The free space on this disk is tight; other plans writing large files (nClimGrid, PRISM) may hit the same.
- Resume rule as specified: skip a market whose candle file exists and whose market is settled; unsettled markets are re-pulled every run (the final pass re-pulled 18 per big series).

## OBJECTION (scope, one item)

What: I did not pull the hourly-directional series `KXTEMPNYCH` (63,328 markets), `KXTEMPNYCHS` (4,700), `KXTEMPCHIH` (15,553), `KXTEMPCHIHS` (4,710), `KXTEMPMIAH` (11,050): about 99,000 short-lived "up or down this hour" markets, all from 2026-03 onward.
Evidence: one request per market at 5 req/s is about 6 to 7 hours and 1+ GB of raw JSON (this disk was at 100% during the run); the brief lists "low temp, rain, snow, monthly" as the extra series, and these are a different product (hourly direction, no ladder), not an insurance primitive.
Alternative: `uv run python scripts/pull_kalshi.py pull --all-weather --include-hourly` pulls them resume-safely; or pull one (`--series KXTEMPNYCHS`, 4,700 markets, about 20 min) for a liquidity check. Everything else in the brief is done.

Also not done: no tests (per brief); `.planning/` untouched except this report; nothing added to git.
