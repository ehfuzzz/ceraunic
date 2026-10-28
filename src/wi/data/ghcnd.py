"""GHCN-Daily station records (plan 01-04 task 3b).

Full period of record per station from the NCEI access CSVs
(https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/access/<ID>.csv).
Station ids for the settlement and nearby ASOS stations come from 01-RESEARCH / 03-RESEARCH where
given; the rest are looked up in ghcnd-stations.txt + ghcnd-inventory.txt by IEM coordinates
(within 2 km, must carry TMAX, USW* preferred). The resolved table is written to
data/manifests/ghcnd-stations-resolved.csv.

Units: TMAX/TMIN in degF tenths, PRCP and SNOW in hundredths of an inch (GHCN stores tenths of
degC and tenths of mm). Flags kept per element: measurement (m), quality (q), source (s);
TMAX/TMIN also keep the observation time (hhmm, local).
"""
from __future__ import annotations

import io
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from wi.data.grids import (MANIFESTS, RAW, CACHE, UA, check_disk, get, haversine_km, manifest_append,
                           md5_bytes, utcnow)

BASE = "https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily"
RAW_DIR = RAW / "ghcnd"
OUT_DIR = CACHE / "ghcnd"
IEM_NETWORKS = ["NY_ASOS", "NJ_ASOS", "IL_ASOS", "IN_ASOS", "FL_ASOS", "PA_ASOS"]

# code -> GHCN id when the research notes give one (verified against coordinates below)
KNOWN = {
    "NYC": "USW00094728", "EWR": "USW00014734", "TTN": "USW00014792", "MDW": "USW00014819",
    "MIA": "USW00012839", "ORD": "USW00094846", "LGA": "USW00014732", "JFK": "USW00094789",
    "FLL": "USW00012849", "OPF": "USW00012882", "PBI": "USW00012844",
    "TEB": "USW00094741", "HPN": "USW00094745", "FRG": "USW00054787", "ISP": "USW00004781",
    "CDW": "USW00054743", "PWK": "USW00004838", "DPA": "USW00094892", "UGN": "USW00014880",
    "TMB": "USW00012888", "HWO": "USW00092809",
}
LOOKUP = ["MMU", "SMQ", "GYY", "LOT", "HST", "FXE", "JRB", "DYL", "PNE", "VAY", "WRI", "BLM"]
IEM_ALIAS = {"PBI": "DJT"}
# GHCN-only extras: USW stations within ~70 km of a settlement station with no IEM counterpart in
# the brief (found in ghcnd-inventory.txt, TMAX through 2026). Not used as settlement inputs.
EXTRA = {"JOLIET": "USW00014834", "LAKEHURST": "USW00014780", "PHL": "USW00013739",
         "POMPANO": "USW00092805"}
ELEMENTS = ["TMAX", "TMIN", "PRCP", "SNOW"]


def iem_coords() -> dict[str, tuple[float, float, str]]:
    out: dict[str, tuple[float, float, str]] = {}
    for net in IEM_NETWORKS:
        r = get(f"https://mesonet.agron.iastate.edu/api/1/network/{net}.json")
        for row in json.loads(r.text)["data"]:
            out.setdefault(row["id"], (float(row["latitude"]), float(row["longitude"]), row["name"]))
        time.sleep(1.0)
    return out


def fetch_text(url: str, dest: Path, dataset: str) -> str:
    check_disk()
    r = get(url)
    if r.status_code != 200:
        raise RuntimeError(f"{url}: HTTP {r.status_code}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    manifest_append("ghcnd", dict(dataset=dataset, url=url, local_path=str(dest), bytes=len(r.content),
                    md5=md5_bytes(r.content), http_status="200", fetched_utc=utcnow(),
                    source_version=r.headers.get("Last-Modified", ""), retained="yes"))
    return r.text


def load_stations_and_inventory() -> tuple[pd.DataFrame, pd.DataFrame]:
    st_p, inv_p = RAW_DIR / "ghcnd-stations.txt", RAW_DIR / "ghcnd-inventory.txt"
    if not st_p.exists():
        fetch_text("https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-stations.txt", st_p, "ghcnd_stations_list")
    if not inv_p.exists():
        fetch_text("https://www.ncei.noaa.gov/pub/data/ghcn/daily/ghcnd-inventory.txt", inv_p, "ghcnd_inventory")
    st = pd.read_fwf(st_p, colspecs=[(0, 11), (12, 20), (21, 30), (31, 37), (38, 40), (41, 71)], header=None,
                     names=["id", "lat", "lon", "elev", "state", "name"])
    inv = pd.read_fwf(inv_p, colspecs=[(0, 11), (12, 20), (21, 30), (31, 35), (36, 40), (41, 45)], header=None,
                      names=["id", "lat", "lon", "element", "first", "last"])
    return st, inv


def resolve(codes_known: dict[str, str], lookup: list[str]) -> pd.DataFrame:
    iem = iem_coords()
    st, inv = load_stations_and_inventory()
    tm = inv[inv.element == "TMAX"].set_index("id")
    pr = inv[inv.element == "PRCP"].set_index("id")
    rows = []
    for code in list(codes_known) + lookup:
        iid = IEM_ALIAS.get(code, code)
        if iid not in iem:
            rows.append(dict(code=code, iem_id=iid, ghcn_id="", note="not in IEM network tables"))
            continue
        la, lo, nm = iem[iid]
        d = haversine_km(la, lo, st.lat.to_numpy(float), st.lon.to_numpy(float))
        cand = st.assign(km=d)[d <= 2.5]
        cand = cand[cand.id.isin(tm.index)]
        known = codes_known.get(code)
        pick, note = None, ""
        if known:
            if known in set(st.id):
                krow = st[st.id == known].iloc[0]
                kd = float(haversine_km(la, lo, np.array([krow.lat]), np.array([krow.lon]))[0])
                if known in tm.index and kd <= 3.0:
                    pick, note = known, f"research id, {kd:.2f} km from IEM coords"
                else:
                    note = f"research id {known} failed check (km={kd:.2f}, tmax_in_inventory={known in tm.index})"
        if pick is None:
            if len(cand):
                cand = cand.assign(usw=cand.id.str.startswith("USW"),
                                   first=[int(tm.loc[i, "first"]) for i in cand.id],
                                   last=[int(tm.loc[i, "last"]) for i in cand.id])
                cand = cand[cand["last"] >= 2026]
                if len(cand):
                    cand = cand.sort_values(["usw", "km"], ascending=[False, True])
                    pick = cand.iloc[0].id
                    note = (note + "; " if note else "") + "coordinate match " + "; ".join(
                        f"{r.id} {r.km:.2f}km {r['first']}-{r['last']}" for _, r in cand.head(4).iterrows())
        rows.append(dict(code=code, iem_id=iid, iem_name=nm, iem_lat=la, iem_lon=lo, ghcn_id=pick or "", note=note or "no candidate"))
    for code, gid in EXTRA.items():
        r = st[st.id == gid].iloc[0]
        rows.append(dict(code=code, iem_id="", iem_name=r["name"], iem_lat=r.lat, iem_lon=r.lon, ghcn_id=gid,
                         note="extra USW within ~70 km of a settlement station (inventory search)"))
    df = pd.DataFrame(rows)
    df["ghcn_prcp"] = df.ghcn_id.map(lambda i: bool(i) and i in pr.index)
    return df


def _flags(col: pd.Series) -> pd.DataFrame:
    parts = col.fillna(",,,").astype(str).str.split(",", expand=True).reindex(columns=range(4))
    parts.columns = ["m", "q", "s", "t"]
    return parts.fillna("")


def convert_station(raw_csv: str) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(raw_csv), dtype=str, keep_default_na=False, na_values=[""])
    out = pd.DataFrame({"station_id": df["STATION"], "name": df["NAME"], "lat": df["LATITUDE"].astype(float),
                        "lon": df["LONGITUDE"].astype(float), "date": pd.to_datetime(df["DATE"]).dt.date})
    for el, col in (("TMAX", "tmax"), ("TMIN", "tmin"), ("PRCP", "prcp"), ("SNOW", "snow")):
        if el not in df.columns:
            out[f"{col}_val"] = pd.array([pd.NA] * len(df), dtype="Int32")
            for k in ("m", "q", "s"):
                out[f"{col}_{k}"] = ""
            continue
        v = pd.to_numeric(df[el], errors="coerce")
        if el in ("TMAX", "TMIN"):
            x = np.round(v * 9.0 / 5.0 + 320.0)  # tenths degC -> tenths degF
            name = f"{col}_f_tenths"
        else:
            x = np.round(v / 10.0 / 25.4 * 100.0)  # tenths mm -> hundredths inch
            name = f"{col}_hundredths_in"
        out[name] = x.astype("Int32")
        fl = _flags(df[f"{el}_ATTRIBUTES"]) if f"{el}_ATTRIBUTES" in df.columns else _flags(pd.Series([None] * len(df)))
        for k in ("m", "q", "s"):
            out[f"{col}_{k}"] = fl[k].to_numpy()
        if el in ("TMAX", "TMIN"):
            out[f"{col}_obs_hhmm"] = fl["t"].to_numpy()
    return out


def pull_all() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    res_p = MANIFESTS / "ghcnd-stations-resolved.csv"
    if res_p.exists():
        res = pd.read_csv(res_p, keep_default_na=False)
    else:
        res = resolve(KNOWN, LOOKUP)
        res.to_csv(res_p, index=False)
    print(res[["code", "ghcn_id", "note"]].to_string(), flush=True)
    for code, gid in zip(res.code, res.ghcn_id):
        if not gid:
            continue
        pq = OUT_DIR / f"{gid}.parquet"
        if pq.exists():
            continue
        url = f"{BASE}/access/{gid}.csv"
        raw_p = RAW_DIR / f"{gid}.csv"
        check_disk()
        r = get(url)
        if r.status_code != 200:
            print(code, gid, "HTTP", r.status_code, flush=True)
            continue
        raw_p.write_bytes(r.content)
        df = convert_station(r.text)
        df.insert(0, "code", code)
        df.to_parquet(pq, index=False)
        manifest_append("ghcnd", dict(dataset="ghcnd_station_csv", url=url, local_path=str(raw_p),
                        bytes=len(r.content), md5=md5_bytes(r.content), http_status="200", fetched_utc=utcnow(),
                        source_version=f"last_modified={r.headers.get('Last-Modified','')};rows={len(df)};"
                                       f"{df.date.min()}..{df.date.max()}", retained="yes"))
        print(code, gid, len(df), df.date.min(), df.date.max(), flush=True)
        time.sleep(1.0)
