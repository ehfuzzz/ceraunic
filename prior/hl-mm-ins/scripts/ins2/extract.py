"""ins2: subset nClimGrid-Daily tmax to cells within 40 km of each settlement station.
Reads var/ins2/raw/*.nc, writes var/ins2/cells.npz. Run from the worktree root:
  PYTHONPATH=src ~/Desktop/hl-mm/.venv/bin/python scripts/ins2/extract.py
"""
import glob, os, datetime as dt, json
import numpy as np, netCDF4 as nc

RAW = "var/ins2/raw"; OUT = "var/ins2/cells.npz"
# settlement stations (ARP coordinates; sub-km differences are irrelevant at 4 km cells)
STATIONS = {
    "NYC": (40.7789, -73.9692),   # Central Park (KNYC)
    "EWR": (40.6895, -74.1745),
    "TTN": (40.2767, -74.8135),
    "MDW": (41.7868, -87.7524),   # Kalshi Chicago settles at Midway (ins1 correction); ORD ~ 20 km away is inside the disc
    "MIA": (25.7959, -80.2870),
}
RADIUS_KM = 40.0

def hav(lat0, lon0, lat, lon):
    R = 6371.0088
    p0, p = np.radians(lat0), np.radians(lat)
    a = np.sin((p - p0) / 2) ** 2 + np.cos(p0) * np.cos(p) * np.sin(np.radians(lon - lon0) / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))

out = {}
epoch = dt.date(1800, 1, 1)
files = sorted(glob.glob(f"{RAW}/ncdd-*-grd-*.nc"))
meta = {}
for name, (la0, lo0) in STATIONS.items():
    days, vint, cols = [], [], None
    for f in files:
        d = nc.Dataset(f)
        lat = d["lat"][:].astype(float); lon = d["lon"][:].astype(float)
        if cols is None:
            LA, LO = np.meshgrid(lat, lon, indexing="ij")
            D = hav(la0, lo0, LA, LO)
            ii, jj = np.where(D <= RADIUS_KM)
            cols = (ii, jj, D[ii, jj], LA[ii, jj], LO[ii, jj])
            tmax = []
        ii, jj = cols[0], cols[1]
        t = d["time"][:]
        arr = d["tmax"][:, :, :]  # masked/NaN, degC
        arr = np.ma.filled(arr.astype(float), np.nan)
        for k, tv in enumerate(t):
            days.append((epoch + dt.timedelta(days=int(tv))).isoformat())
            vint.append("prelim" if "prelim" in f else "scaled")
            tmax.append(arr[k, ii, jj])
        d.close()
    out[f"{name}_tmaxC"] = np.array(tmax)
    out[f"{name}_dist"] = cols[2]; out[f"{name}_lat"] = cols[3]; out[f"{name}_lon"] = cols[4]
    out[f"{name}_days"] = np.array(days); out[f"{name}_vint"] = np.array(vint)
    valid = np.isfinite(out[f"{name}_tmaxC"]).all(axis=0)
    meta[name] = dict(cells_in_disc=int(len(cols[2])), cells_valid_all_days=int(valid.sum()),
                      first_day=days[0], last_day=days[-1], nearest_cell_km=float(cols[2].min()))
np.savez_compressed(OUT, **out)
print(json.dumps(meta, indent=1)); print(os.path.getsize(OUT), "bytes ->", OUT)
