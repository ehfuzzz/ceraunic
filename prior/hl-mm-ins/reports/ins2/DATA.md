# ins2 data manifest (downloaded 2026-09-30 05:56Z, plain curl, no key)

NOAA NCEI nClimGrid-Daily v1-0-0 (1/24 degree ≈ 4-5 km, CONUS), monthly NetCDF4, variables tmax/tmin/prcp/tavg (only tmax used).
Index: https://www.ncei.noaa.gov/data/nclimgrid-daily/access/grids/2026/ (directory listing shows exactly one data file per month).

| URL | bytes | md5 | version |
|---|---|---|---|
| https://www.ncei.noaa.gov/data/nclimgrid-daily/access/grids/2026/ncdd-202607-grd-scaled.nc | 57,115,170 | c1936678cdaec2b121724e4210a35b4c | scaled ("complete"), created 2026-09-06 |
| https://www.ncei.noaa.gov/data/nclimgrid-daily/access/grids/2026/ncdd-202608-grd-scaled.nc | 57,244,383 | 312e899ce28b25298f96104f50980598 | scaled ("complete"), created 2026-09-06 |
| https://www.ncei.noaa.gov/data/nclimgrid-daily/access/grids/2026/ncdd-202609-grd-prelim.nc | 49,100,699 | f321fef7991baff873ce39fd242acf3a | prelim, 2026-09-01..09-26 only, created 2026-09-28 (GHCN-Daily 3.34-upd-2026092718) |
| https://www.ncei.noaa.gov/data/nclimgrid-daily/access/grids/2026/ncdd-202607-version.txt | 224 | | |
| https://www.ncei.noaa.gov/data/nclimgrid-daily/access/grids/2026/ncdd-202608-version.txt | 224 | | |
| https://www.ncei.noaa.gov/data/nclimgrid-daily/access/grids/2026/ncdd-202609-version.txt | 222 | | |
| https://www.ncei.noaa.gov/data/nclimgrid-daily/access/grids/2026/ncdd-202609-grd-scaled.nc | 404 (not yet published) | | probe by scripts/ins2/revision.py |

Total downloaded: 163,460,252 bytes of grids + 670 bytes of version files = 163,460,922 bytes (156 MB on disk; < 1 GB). The monthly files are whole-CONUS
(no server-side subsetting on this path), so the bounding-box subset is done locally: `scripts/ins2/extract.py` writes `var/ins2/cells.npz`
(203 KB; the 1,206 land cells with data within 40 km of the five stations, all days Jul 1 - Sep 30 by grid label). PRISM was not used.

Other inputs (already in the repo): `reports/ins1/rows.json` (272 city-days: ladder K, ladder payout, NWS ASOS max H_nws) and `reports/ins1/iem-*.csv`.
Python package added to ~/Desktop/hl-mm/.venv: netCDF4 (and its dependencies cftime, certifi).
