"""ins2 test 3: prelim-vs-final bin flips. nClimGrid-Daily exposes ONE version per month at any time (scaled for closed
months, prelim for the open month; no vintage archive), so on 2026-09-30 the comparison is impossible. The Sep-2026 prelim
file (created 2026-09-28, GHCN-Daily 3.34-upd-2026092718) is kept in var/ins2/raw; this script downloads the Sep scaled
file once NCEI publishes it (Aug's appeared 6 days after month end) and counts cell-days whose $1/F payout bin moves.
  PYTHONPATH=src ~/Desktop/hl-mm/.venv/bin/python scripts/ins2/revision.py
Note: the kept prelim is 2-27 days old per day, NOT the first publication and NOT T+5; label it accordingly.
"""
import json, os, sys, urllib.request, urllib.error, datetime as dt
import numpy as np, netCDF4 as nc
URL = "https://www.ncei.noaa.gov/data/nclimgrid-daily/access/grids/2026/ncdd-202609-grd-scaled.nc"
PRE = "var/ins2/raw/ncdd-202609-grd-prelim.nc"; FIN = "var/ins2/raw/ncdd-202609-grd-scaled.nc"
if not os.path.exists(FIN):
    try:
        with urllib.request.urlopen(URL, timeout=600) as r, open(FIN, "wb") as f:
            n = 0
            while chunk := r.read(1 << 20): f.write(chunk); n += len(chunk)
        print("downloaded", URL, n, "bytes")
    except urllib.error.HTTPError as e:
        print(f"UNAVAILABLE: {URL} -> HTTP {e.code}; only the prelim version of September exists, no revision measurable."); sys.exit(0)
ROWS = json.load(open("reports/ins1/rows.json"))
Z = np.load("var/ins2/cells.npz")
SER = {"NYC": "KXHIGHNY", "EWR": "KXHIGHTEWR", "TTN": "KXHIGHTTTN", "MDW": "KXHIGHCHI", "MIA": "KXHIGHMIA"}
H = lambda T, K: np.clip(T - K, 0.0, 6.0)
a, b = nc.Dataset(PRE), nc.Dataset(FIN)
la, lo = a["lat"][:].astype(float), a["lon"][:].astype(float)
ta = [dt.date(1800, 1, 1) + dt.timedelta(days=int(v)) for v in a["time"][:]]
out = {}
for st in SER:
    la0, lo0 = Z[f"{st}_lat"], Z[f"{st}_lon"]
    ii = np.abs(la[:, None] - la0[None, :]).argmin(0); jj = np.abs(lo[:, None] - lo0[None, :]).argmin(0)
    flips = tot = 0
    for r in ROWS:
        if r["ser"] != SER[st] or not r["day"].startswith("2026-09") or r.get("H_nws") is None: continue
        lab = dt.date.fromisoformat(r["day"]) + dt.timedelta(days=1)   # grid label = calendar day + 1 (see README)
        if lab not in ta: continue
        k = ta.index(lab)
        Tp = np.ma.filled(a["tmax"][k, ii, jj].astype(float), np.nan) * 9 / 5 + 32
        Tf = np.ma.filled(b["tmax"][k, ii, jj].astype(float), np.nan) * 9 / 5 + 32
        ok = np.isfinite(Tp) & np.isfinite(Tf)
        flips += int((H(np.round(Tp[ok]), r["K"]) != H(np.round(Tf[ok]), r["K"])).sum()); tot += int(ok.sum())
    out[st] = dict(cell_days=tot, bin_flips=flips, share=flips / tot if tot else None)
json.dump(out, open("reports/ins2/revision.json", "w"), indent=1); print(json.dumps(out, indent=1))
