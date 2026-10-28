# 01-06 summary: conventions v2, DATA.md, make data

Worker: worker. Date: 2026-09-30. Nothing staged or committed; nothing downloaded (only local parquet reads).

## Done
- `docs/CONVENTIONS.md` rewritten as v2 in one atomic replace (temp file then `mv`, twice: the second replace applied two corrections below). Sections 1-8 keep their numbers; 9-13 are new (rain contract types, Kalshi fee, revision lifecycles, rate limits, units). All 13 items in the plan are covered, each citing 01-RESEARCH / 07-RESEARCH / 03-RESEARCH sections. One-line changelog at the bottom. `grep -c "05:00Z"` = 1 (verify asked >= 1); the file no longer states 03:59Z as the ET close, it gives 03:59Z only as the EDT-season value of the old clock-time rule.
- `data/manifests/DATA.md` restructured: one key/value table per dataset (D1-D12: source, URL pattern, coverage, rows, bytes, md5/manifest, pulled_utc, known gaps), followed by the retained per-station and per-series detail tables. D1-D6 filled (md5 computed for the parquet files and the series CSV); D7-D10 (01-04) and D11-D12 (recorder, sales/Census) are labelled placeholders.
- `Makefile`: `make data` = `discover` (only if `kalshi-series.csv` is missing) then `pull --all-weather`, then `python -m wi.data.iem`, then `scripts/pull_grids.py` if it exists. `make -n data` prints all of it (verified).

## Deviations and findings (please read)
1. **Close times are more complicated than the plan text.** Read off `markets.parquet`: NY/MIA clock-time 23:59 ET until 2026-03-18 (03:59Z EDT / 04:59Z EST); fixed 04:59Z from 2026-03-19; fixed 05:00Z from 2026-08-15. CHI: ET until 2025-02-20, CT from 2025-02-21, fixed 05:59Z from 2026-03-19, 06:00Z from 2026-08-15. The plan's "until 2026-07" is wrong by the 2026-03-19 step; CONVENTIONS section 2 records the table and the deviation.
2. **IEM daily.py vs CLI is a regime change, not a steady bias.** Checked on the pulled tables: equal on 32-53 % of station-days per quarter through 2025Q3, then 100 % every quarter from 2025Q4 to 2026Q3 (about 1,820 station-days). CONVENTIONS section 8 (previously "-0.4 to -0.6 degF average", from 01-03) was corrected; this agrees with R1 Pitfall 2. The 01-03 all-period average was blending the two regimes.
3. **Pull gap:** `KXRAIN` (multi-city daily rain, from 2026-07-15) and `KXRAINWKND` were NOT pulled. `kalshi-series.csv` has them with empty city and `in_scope` False, so `pull --all-weather` skips them. Daily rain history is therefore `KXRAINNYC` only. Not fixed here (outside this plan); noted in DATA.md D1.
4. Kalshi fee (section 10) stays MEDIUM confidence; the official fee PDF was not fetched (no downloads).
5. `make data` re-fetches IEM CLI/CF6 (5+5 small files) on every run; only the ASOS files are skipped when current. `pull_grids.py` arguments are for 01-04 to define; the Makefile calls it with none. `scripts/pull_kalshi.py datamd` would append an old-layout section to DATA.md; DATA.md says not to run it.
6. `make data` was not executed (it would hit Kalshi for about 100 open-market candle pulls plus IEM); only `make -n data`.

## Verification
- `make -n data` prints the three commands (plus the guarded discover).
- `grep -c "05:00Z" docs/CONVENTIONS.md` = 1; close-time table matches the market data read above.
- No tests added, per AGENTS.md (nothing here can silently corrupt data in isolation).
