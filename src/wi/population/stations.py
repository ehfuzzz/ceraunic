"""ZIP -> 2024 ZCTA gazetteer internal point -> nearest settlement station within 40 km."""
from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

# GHCN-Daily inventory coordinates (04-RESEARCH, checked 2026-09-30)
STATIONS = {"NYC": (40.7789, -73.9692), "EWR": (40.6828, -74.1692), "TTN": (40.2769, -74.8158),
            "MDW": (41.7842, -87.7553), "MIA": (25.7881, -80.3169)}
METRO = {"NYC": "NYC-metro", "EWR": "NYC-metro", "TTN": "NYC-metro", "MDW": "CHI", "MIA": "MIA"}


def haversine_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))


def load_zcta(path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(path) as z:
        name = [n for n in z.namelist() if n.endswith(".txt")][0]
        with z.open(name) as fh:
            g = pd.read_csv(fh, sep="\t", dtype={"GEOID": str})
    g.columns = [c.strip() for c in g.columns]
    return pd.DataFrame({"zip": g["GEOID"].str.zfill(5), "lat": g["INTPTLAT"].astype(float),
                         "lon": g["INTPTLONG"].astype(float)})


def assign_station(zcta: pd.DataFrame, max_km: float = 40.0) -> pd.DataFrame:
    names = list(STATIONS)
    lat = np.array([STATIONS[s][0] for s in names])
    lon = np.array([STATIONS[s][1] for s in names])
    d = haversine_km(zcta["lat"].to_numpy()[:, None], zcta["lon"].to_numpy()[:, None], lat[None, :], lon[None, :])
    k = d.argmin(axis=1)
    out = zcta.assign(station=np.array(names)[k], dist_km=d[np.arange(len(d)), k])
    return out[out["dist_km"] <= max_km].reset_index(drop=True)
