# 01-04 summary: gridded weather + GHCN-Daily

Status: complete except one PRISM file (tmax 2026-08-01, rate-limit refusal, see Deviations). One OBJECTION raised and resolved (disk floor, below). No git operations run.

## Accomplishments
- nClimGrid-Daily: 33 monthly files (2024-01..2026-09) streamed from NCEI, subset to 40 km discs around NYC, EWR, TTN, MDW, MIA, deleted (Jul/Aug/Sep 2026 reused from disk, kept as the plan says). Each file read from memory, so a raw file was never on disk next to an extracted copy.
- nClimGrid county averages (tmax, tmin, prcp), 33 months, joined on the state-prefixed county name.
- PRISM 4 km tmax and ppt, 1,003 days each (2024-01-01..2026-09-29), 2.5 s between files, zip read in memory, deleted after subsetting. Release number (grid count) per day per variable in every row.
- nClimGrid prelim vintages from the AWS mirror: 50 of 148 tarballs (every 3rd, 2.14 GB of 6.18 GB; the plan's 2.5 GB rule), 50 distinct `vintage_created` (2026-04-21..2026-09-28).
- GHCN-Daily: 33 stations, full record, F tenths / hundredths of an inch, flags kept.
- Docs: new section in `data/manifests/DATA.md` (layout, limits, gaps, accuracy numbers).

## Files
- Code: `src/wi/data/grids.py`, `src/wi/data/ghcnd.py`, `scripts/pull_grids.py`
- Manifests (committed): `data/manifests/grids.csv` (2,187 rows, every row has url, bytes, md5, fetched_utc, version), `data/manifests/ghcnd.csv` (36 rows), `data/manifests/ghcnd-stations-resolved.csv`, `data/manifests/DATA.md` (appended)
- Outputs (gitignored): `data/cache/grid_disc/`, `data/cache/grid_county/nclimgrid_county_daily.parquet`, `data/cache/vintages/nclimgrid_prelim.parquet`, `data/cache/ghcnd/*.parquet`, `data/cache/prism_days/`, `data/cache/prism_stn/` (2026-07-15 tmax + ppt station lists)

## Row counts (grid_disc)
| station | nClimGrid cells / rows / days | PRISM cells / rows / days |
|---|---|---|
| NYC | 240 / 240,000 / 1,000 | 299 / 299,897 / 1,003 |
| EWR | 255 / 255,000 / 1,000 | 297 / 297,891 / 1,003 |
| TTN | 307 / 307,000 / 1,000 | 305 / 305,915 / 1,003 |
| MDW | 236 / 236,000 / 1,000 | 256 / 256,768 / 1,003 |
| MIA | 175 / 175,000 / 1,000 | 206 / 206,618 / 1,003 |

- nClimGrid label_day 2024-01-01..2026-09-26, cli_day 2023-12-31..2026-09-25 (974 scaled days, 26 prelim). PRISM label_day 2024-01-01..2026-09-29, cli_day 2023-12-31..2026-09-28 (release 8 on 821 days, 1-7 on the newest days).
- County: 5 counties x 1,000 days = 5,000 rows. Vintages: 977,678 rows, 50 vintages. GHCN: 33 files, 640,122 rows.

## Verification
- `pd.read_parquet('data/cache/grid_disc/source=nclimgrid')` works (source/station are stored in each file as the same dictionary type the hive partition uses, so a directory read merges cleanly).
- GHCN vs NWS CLI high, 335 days 2025-10-01..2026-08-31: NYC 100 %, EWR 99.7 %, TTN 99.7 %, MDW 100 %, MIA 100 % (target 95 %).
- Vintages: 50 distinct `vintage_created` (target 30). GHCN stations: 33 (target 30).
- PRISM spot check (plan): NYC cell label 2026-07-30 tmax 81.2 F vs official 2026-07-29 80 F, difference 1.2 F (limit 3 F).
- Nearest-cell tmax vs CLI high over the whole window (NYC / EWR / TTN / MDW / MIA), RMSE in F: nClimGrid 2.05 / 2.13 / 1.85 / 2.32 / 1.30, PRISM 1.89 / 2.27 / 1.56 / 2.16 / 1.10; bias nClimGrid +0.74 / -0.95 / +0.60 / -0.21 / +0.21, PRISM -0.30 / -1.65 / -0.03 / -0.46 / -0.07. These join on cli_day = label_day - 1. ins2's 1.1-1.7 was the scaled file on a shorter window; I did not chase the gap.
- `data/raw/prism` holds no files; `du -sh data/raw` = 783 MB (under 1.5 GB; most of it is other workers' Kalshi/census data, my share is the three kept nClimGrid files, 156 MB).

## Deviations
1. cli_day starts 2023-12-31, not 2024-01-01: the plan windows label_day from 2024-01-01 and cli_day = label_day - 1. (cli_day 2024-01-01 is present, from label 2024-01-02.)
2. PRISM tmax 2026-08-01 is missing. The research pass had downloaded that exact file earlier the same day, and PRISM refuses a second copy inside 24 h (non-zip reply; the loop did not retry it). Its ppt file is in, tmax is NaN for that day in the parquet with a null release. Fill: `uv run python scripts/pull_grids.py prism` after about 2026-10-01 15:00Z; everything else is cached, so only that one file is requested.
3. PRISM 2026-09-30 not published at pull time (label day ends 12Z that day); the loop stopped asking after the first refusal in September.
4. Vintages sampled every 3rd (the plan's own fallback when the total exceeds 2.5 GB). The tarballs hold only the days up to their end date, so each vintage is month-to-date.
5. Only the `*_prelim_*` tarballs were taken (plan text). The superseded `*_complete_*` tarballs and `access/grids/2026/*-prelim.nc` for Apr-Aug were not pulled; they would give the prelim-to-final comparison directly if a later phase wants it.
6. GHCN ids: research ids were kept where within 3 km of the IEM coordinates; TEB, HPN, FRG, ISP, CDW, PWK, DPA, UGN, TMB, HWO came from the research list, SMQ, HST, FXE, DYL, PNE, VAY, WRI by coordinate lookup. No current GHCN-Daily TMAX record within 2.5 km exists for MMU, GYY, BLM, JRB (dropped). LOT resolves to `USC00117457` (Romeoville WFO coop, 1.0 km; not an ASOS, flagged in the resolved table). Four extras added to reach 33: JOLIET USW00014834, LAKEHURST USW00014780, PHL USW00013739, POMPANO USW00092805.
7. GHCN access CSVs end 2026-09-22 (about a week of publication lag); LAKEHURST ends 2026-03-12.
8. Raw GHCN CSVs and the two inventory files were deleted after conversion (manifest `retained=no`) to ease disk; all re-pullable.
9. The county parquet carries tmin as well as tmax and prcp (cheap, same files).
10. The PRISM zip contains the station list per day; only 2026-07-15 was kept, as national files (not cut per disc).

## OBJECTION (disk floor), resolved
What: free disk fell under the 3 GiB floor twice while PRISM ran, reaching 0.35 GiB at 14:44Z. Evidence: `OBJECTION: disk floor hit` lines from the guard; manifest of my own footprint is about 8.7 MB of grid parquet plus 2 x 3 MB PRISM files in flight. Cause was another worker's 3.8 GB temp bundle (per the coordinator), not these pulls. Action: the guard stopped the PRISM process each time (no download was started below the floor); the retry loop resumed it automatically once `df` showed at least 3 GiB (it then ran to completion). Nothing outside my own files was deleted. Final free disk 21.7 GiB.

## Disk
- Before: 5,611,872 KB free (5.35 GiB) at start. After: 22,710,760 KB free (21.66 GiB), so the free-space check (start minus 1 GB) holds; my net footprint is about +25 MB of cache and unchanged raw.
- Minimum seen: 365,496 KB (another worker's bundle).

## Open for later phases
- Fill the 2026-08-01 PRISM tmax file after 2026-10-01 15:00Z.
- September 2026 nClimGrid scaled file is expected about 2026-10-06. `pull_nclimgrid_months` prefers a local file, so move `data/raw/nclimgrid/ncdd-202609-grd-prelim.nc` out of the way (its md5 is in `grids.csv`; CONVENTIONS section 3 says to keep prelim files) and run `uv run python scripts/pull_grids.py nclimgrid`; the 202609 part files are then rewritten with status `scaled`.
- Keep snapshotting prelim vintages and PRISM grid counts going forward (PRISM keeps no old versions).
