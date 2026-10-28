"""Gridded weather subsets (plan 01-04): nClimGrid-Daily and PRISM 4 km within 40 km of the
five settlement stations, nClimGrid county averages, and nClimGrid prelim vintages.

Stream -> subset -> delete. Never more than one raw grid file on disk per process; the .nc is
read from memory (netCDF4 `memory=`), so a zip/tar is the only raw file at any moment. Free disk
is checked before every download and the pull stops (DiskFloor) under 3 GiB.

Day labels (docs/CONVENTIONS.md section 3): nClimGrid label D and PRISM label D both describe
calendar day D-1, so `cli_day = label_day - 1 day` and calendar day X is read from label X+1.

Units written: tmax/tmin in degF tenths (int), precipitation in hundredths of an inch (int).

CLI: `uv run python scripts/pull_grids.py {nclimgrid|prism|vintages|ghcnd|all}`.
"""
from __future__ import annotations

import csv
import datetime as dt
import fcntl
import hashlib
import io
import re
import shutil
import tarfile
import time
import zipfile
from pathlib import Path

import netCDF4 as nc
import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw"
CACHE = ROOT / "data" / "cache"
MANIFESTS = ROOT / "data" / "manifests"
STATIONS_CSV = CACHE / "weather" / "stations.csv"
DISC = CACHE / "grid_disc"
COUNTY_OUT = CACHE / "grid_county"
VINTAGES = CACHE / "vintages"
PRISM_DAYS = CACHE / "prism_days"  # tiny per-day npz of disc values, makes the pull resumable
PRISM_STN = CACHE / "prism_stn"

UA = "weather-insurance-prototype/0.1 (research; contact via repo owner)"
RADIUS_KM = 40.0
DISK_FLOOR = 3 * 2**30
WINDOW_START = dt.date(2024, 1, 1)
WINDOW_END = dt.date(2026, 9, 30)
EPOCH = dt.date(1800, 1, 1)

NCEI = "https://www.ncei.noaa.gov/data/nclimgrid-daily/access"
PRISM_URL = "https://services.nacse.org/prism/data/get/us/4km/{var}/{ymd}?format=nc"
PRISM_SLEEP = 2.5  # >= 2 s between PRISM files

SETTLEMENT = ["NYC", "EWR", "TTN", "MDW", "MIA"]
# county name column (state-prefixed, NCEI ids are not FIPS) -> settlement station
COUNTIES = {
    "NY: New York County": "NYC",
    "NJ: Essex County": "EWR",
    "NJ: Mercer County": "TTN",
    "IL: Cook County": "MDW",
    "FL: Miami-Dade County": "MIA",
}
MANIFEST_COLS = ["dataset", "url", "local_path", "bytes", "md5", "http_status", "fetched_utc",
                 "source_version", "retained"]


class DiskFloor(RuntimeError):
    pass


def free_bytes() -> int:
    return shutil.disk_usage("/").free


def check_disk() -> None:
    f = free_bytes()
    if f < DISK_FLOOR:
        raise DiskFloor(f"free disk {f/2**30:.2f} GiB below the 3 GiB floor")


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def md5_bytes(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def md5_file(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest_append(name: str, row: dict) -> None:
    """Append one row to data/manifests/<name>.csv (file-locked: several pulls run at once)."""
    MANIFESTS.mkdir(parents=True, exist_ok=True)
    p = MANIFESTS / f"{name}.csv"
    with open(p, "a+", newline="") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0, 2)
        new = f.tell() == 0
        w = csv.DictWriter(f, fieldnames=MANIFEST_COLS)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in MANIFEST_COLS})
        fcntl.flock(f, fcntl.LOCK_UN)


def manifest_has(name: str, url: str) -> bool:
    p = MANIFESTS / f"{name}.csv"
    if not p.exists():
        return False
    with open(p, newline="") as f:
        return any(r["url"] == url for r in csv.DictReader(f))


def get(url: str, *, stream: bool = False, tries: int = 4, timeout: int = 180) -> requests.Response:
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout, stream=stream)
            if r.status_code == 200:
                return r
            if r.status_code in (404, 403):
                return r
            last = f"HTTP {r.status_code}"
            if r.status_code == 429:
                time.sleep(120 * (i + 1))
                continue
        except requests.RequestException as e:
            last = repr(e)
        time.sleep(10 * (i + 1))
    raise RuntimeError(f"GET {url} failed: {last}")


# ---------------------------------------------------------------- discs

def settlement_points() -> dict[str, tuple[float, float]]:
    df = pd.read_csv(STATIONS_CSV)
    out = {}
    for s in SETTLEMENT:
        r = df[(df.station == s) & (df.settlement == s)].iloc[0]
        out[s] = (float(r.lat), float(r.lon))
    return out


def haversine_km(lat0: float, lon0: float, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
    R = 6371.0088
    p0, p = np.radians(lat0), np.radians(lat)
    a = np.sin((p - p0) / 2) ** 2 + np.cos(p0) * np.cos(p) * np.sin(np.radians(lon - lon0) / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def build_discs(lat: np.ndarray, lon: np.ndarray, radius_km: float = RADIUS_KM) -> dict[str, dict]:
    """Flat indices (into the lat x lon grid) of every cell within `radius_km` (default 40) of each station."""
    LA, LO = np.meshgrid(lat.astype(float), lon.astype(float), indexing="ij")
    out = {}
    for s, (la0, lo0) in settlement_points().items():
        D = haversine_km(la0, lo0, LA, LO)
        ii, jj = np.where(D <= radius_km)
        out[s] = dict(ii=ii, jj=jj, dist=D[ii, jj], lat=LA[ii, jj], lon=LO[ii, jj],
                      cell_id=np.array([f"{a:.4f}_{b:.4f}" for a, b in zip(LA[ii, jj], LO[ii, jj])]))
    return out


def f_tenths(c: np.ndarray) -> np.ndarray:
    return np.round((c * 9.0 / 5.0 + 32.0) * 10.0)


def in_hundredths(mm: np.ndarray) -> np.ndarray:
    return np.round(mm / 25.4 * 100.0)


def _as_int(a: np.ndarray, dtype: str) -> pd.array:
    s = pd.Series(a)
    return s.astype("Int32" if dtype == "i4" else "Int16")


def _long_frame(source: str, station: str, disc: dict, days: list[dt.date], tmax, tmin, prcp,
                status: str, rel_tmax=None, rel_ppt=None) -> pd.DataFrame:
    """tmax/tmin/prcp: (ndays, ncells) already in output units (float with NaN)."""
    nd, nc_ = len(days), len(disc["lat"])
    d = np.repeat(np.array(days, dtype="datetime64[D]"), nc_)
    df = pd.DataFrame({
        "source": source,
        "station": station,
        "cell_id": np.tile(disc["cell_id"], nd),
        "lat": np.tile(disc["lat"], nd),
        "lon": np.tile(disc["lon"], nd),
        "dist_km": np.tile(disc["dist"], nd).astype("float32"),
        "label_day": d,
        "cli_day": d - np.timedelta64(1, "D"),
        "tmax_f_tenths": _as_int(tmax.ravel(), "i2"),
        "tmin_f_tenths": _as_int(tmin.ravel(), "i2"),
        "prcp_hundredths_in": _as_int(prcp.ravel(), "i4"),
        "status": status,
    })
    if rel_tmax is not None:
        df["prism_release_tmax"] = np.repeat(np.array(rel_tmax, dtype="float"), nc_)
        df["prism_release_ppt"] = np.repeat(np.array(rel_ppt, dtype="float"), nc_)
        df["prism_release_tmax"] = df["prism_release_tmax"].astype("Int8")
        df["prism_release_ppt"] = df["prism_release_ppt"].astype("Int8")
    else:
        df["prism_release_tmax"] = pd.array([pd.NA] * len(df), dtype="Int8")
        df["prism_release_ppt"] = pd.array([pd.NA] * len(df), dtype="Int8")
    # drop rows with no value at all (ocean cells, days past the prelim end)
    keep = ~(df.tmax_f_tenths.isna() & df.tmin_f_tenths.isna() & df.prcp_hundredths_in.isna())
    df = df[keep.to_numpy()].copy()
    df["label_day"] = pd.to_datetime(df["label_day"]).dt.date
    df["cli_day"] = pd.to_datetime(df["cli_day"]).dt.date
    return df


def write_part(source: str, station: str, ym: str, df: pd.DataFrame) -> Path:
    d = DISC / f"source={source}" / f"station={station}"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"part-{ym}.parquet"
    # source/station are also hive partition keys in the directory name; storing them in the file
    # as dictionary<int32,string> (the type pyarrow infers for partitions) keeps directory reads
    # mergeable while a single file still carries its own source/station.
    import pyarrow as pa
    import pyarrow.parquet as pq
    t = pa.Table.from_pandas(df, preserve_index=False)
    for col in ("source", "station"):
        i = t.schema.get_field_index(col)
        t = t.set_column(i, col, t[col].cast(pa.string()).dictionary_encode().cast(pa.dictionary(pa.int32(), pa.string())))
    pq.write_table(t, p)
    return p


# ---------------------------------------------------------------- nClimGrid monthly

def month_list(start: dt.date, end: dt.date) -> list[str]:
    out, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(f"{y}{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def subset_nclimgrid_nc(ds: nc.Dataset, discs: dict, vintage: str) -> dict[str, dict]:
    """Return {station: dict(days, tmax_f, tmin_f, prcp_in)} for one opened nClimGrid dataset."""
    t = ds["time"][:]
    days = [EPOCH + dt.timedelta(days=int(v)) for v in t]
    out = {}
    arrs = {}
    for v in ("tmax", "tmin", "prcp"):
        arrs[v] = np.ma.filled(ds[v][:, :, :].astype("float64"), np.nan)
    for s, dc in discs.items():
        ii, jj = dc["ii"], dc["jj"]
        out[s] = dict(days=days,
                      tmax=f_tenths(arrs["tmax"][:, ii, jj]),
                      tmin=f_tenths(arrs["tmin"][:, ii, jj]),
                      prcp=in_hundredths(arrs["prcp"][:, ii, jj]))
    return out


def open_nc_bytes(b: bytes) -> nc.Dataset:
    return nc.Dataset("mem.nc", mode="r", memory=b)


def version_line(text: str) -> str:
    return " | ".join(x.strip() for x in text.strip().splitlines() if x.strip())[:300]


def pull_nclimgrid_months(months: list[str] | None = None) -> None:
    months = months or month_list(WINDOW_START, WINDOW_END)
    raw_dir = RAW / "nclimgrid"
    discs = None
    for ym in months:
        y = ym[:4]
        scaled = raw_dir / f"ncdd-{ym}-grd-scaled.nc"
        prelim = raw_dir / f"ncdd-{ym}-grd-prelim.nc"
        ver_local = raw_dir / f"ncdd-{ym}-version.txt"
        # decide which file exists on NCEI (prelim only for the open month)
        if scaled.exists():
            status, path, local = "scaled", scaled, True
        elif prelim.exists():
            status, path, local = "prelim", prelim, True
        else:
            status, path, local = "scaled", None, False
        part_done = all((DISC / "source=nclimgrid" / f"station={s}" / f"part-{ym}.parquet").exists()
                        for s in SETTLEMENT)
        fname = f"ncdd-{ym}-grd-{status}.nc"
        url = f"{NCEI}/grids/{y}/{fname}"
        fetched = None
        if local:
            b = path.read_bytes()
            version = version_line(ver_local.read_text()) if ver_local.exists() else ""
            http = "local"
            fetched = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            retained = "yes"
        else:
            if part_done:
                print(ym, "already subset, skipping")
                continue
            check_disk()
            r = get(url)
            if r.status_code == 404 and status == "scaled":
                status = "prelim"
                fname = f"ncdd-{ym}-grd-prelim.nc"
                url = f"{NCEI}/grids/{y}/{fname}"
                check_disk()
                r = get(url)
            if r.status_code != 200:
                print(ym, "unavailable", r.status_code)
                continue
            b = r.content
            fetched = utcnow()
            http = "200"
            vr = get(f"{NCEI}/grids/{y}/ncdd-{ym}-version.txt")
            version = version_line(vr.text) if vr.status_code == 200 else ""
            retained = "no"
            time.sleep(1.0)
        ds = open_nc_bytes(b)
        if discs is None:
            discs = build_discs(ds["lat"][:], ds["lon"][:])
        sub = subset_nclimgrid_nc(ds, discs, status)
        ds.close()
        rows = 0
        for s in SETTLEMENT:
            s_ = sub[s]
            df = _long_frame("nclimgrid", s, discs[s], s_["days"], s_["tmax"], s_["tmin"], s_["prcp"], status)
            df = df[df.label_day >= WINDOW_START]
            write_part("nclimgrid", s, ym, df)
            rows += len(df)
        manifest_append("grids", dict(dataset="nclimgrid_daily_grid", url=url,
                        local_path=str(path or raw_dir / fname), bytes=len(b), md5=md5_bytes(b),
                        http_status=http, fetched_utc=fetched, source_version=version, retained=retained))
        print(ym, status, len(b), "bytes", rows, "rows", flush=True)
        del b, sub


def parse_county_csv(text: str, var: str) -> pd.DataFrame:
    rows = []
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 7 or parts[2] not in COUNTIES:
            continue
        y, m = int(parts[3]), int(parts[4])
        for k, v in enumerate(parts[6:], start=1):
            try:
                day = dt.date(y, m, k)
            except ValueError:
                continue
            x = float(v) if v not in ("", "NA") else np.nan
            if x <= -99:
                x = np.nan
            rows.append((parts[2], COUNTIES[parts[2]], day, x))
    return pd.DataFrame(rows, columns=["county_name", "station", "label_day", var])


def pull_county_averages(months: list[str] | None = None) -> None:
    months = months or month_list(WINDOW_START, WINDOW_END)
    frames = []
    for ym in months:
        y = ym[:4]
        per_var = []
        for var in ("tmax", "tmin", "prcp"):
            done_status = None
            for status in ("scaled", "prelim"):
                url = f"{NCEI}/averages/{y}/{var}-{ym}-cty-{status}.csv"
                check_disk()
                r = get(url)
                if r.status_code == 200:
                    done_status = status
                    break
                time.sleep(0.5)
            if done_status is None:
                print("county", var, ym, "unavailable")
                continue
            body = r.content
            manifest_append("grids", dict(dataset="nclimgrid_county_avg", url=url,
                            local_path=f"(parsed, not kept) {var}-{ym}-cty-{done_status}.csv",
                            bytes=len(body), md5=md5_bytes(body), http_status="200",
                            fetched_utc=utcnow(), source_version=done_status, retained="no"))
            d = parse_county_csv(body.decode("latin-1"), var)
            d["status"] = done_status
            per_var.append(d)
            time.sleep(0.5)
        if not per_var:
            continue
        m = per_var[0]
        for d in per_var[1:]:
            m = m.merge(d.drop(columns=["status"]), on=["county_name", "station", "label_day"], how="outer")
        frames.append(m)
        print("county", ym, len(m), flush=True)
    df = pd.concat(frames, ignore_index=True)
    df = df[(df.label_day >= WINDOW_START)]
    df["cli_day"] = df.label_day - dt.timedelta(days=1)
    df["source"] = "nclimgrid_county"
    df["tmax_f_tenths"] = f_tenths(df["tmax"].to_numpy(float))
    df["tmin_f_tenths"] = f_tenths(df["tmin"].to_numpy(float))
    df["prcp_hundredths_in"] = in_hundredths(df["prcp"].to_numpy(float))
    for c in ("tmax_f_tenths", "tmin_f_tenths", "prcp_hundredths_in"):
        df[c] = df[c].astype("Int32")
    df = df.drop(columns=["tmax", "tmin", "prcp"])
    # the all-NaN rows (days past the prelim end) carry no information
    df = df[~(df.tmax_f_tenths.isna() & df.tmin_f_tenths.isna() & df.prcp_hundredths_in.isna())]
    COUNTY_OUT.mkdir(parents=True, exist_ok=True)
    df.to_parquet(COUNTY_OUT / "nclimgrid_county_daily.parquet", index=False)
    print("county rows", len(df))


# ---------------------------------------------------------------- PRISM

def parse_info(text: str) -> dict:
    d = {}
    for line in text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            d[k.strip()] = v.strip()
    return d


def _prism_day(var: str, day: dt.date, discs_holder: dict) -> str:
    """Fetch (or reuse a local zip for) one PRISM day/var; write the per-day npz; delete raw."""
    ymd = day.strftime("%Y%m%d")
    npz = PRISM_DAYS / var / f"{ymd}.npz"
    if npz.exists():
        return "cached"
    zpath = RAW / "prism" / var / f"{ymd}.zip"
    zpath.parent.mkdir(parents=True, exist_ok=True)
    url = PRISM_URL.format(var=var, ymd=ymd)
    if zpath.exists():
        fetched = dt.datetime.fromtimestamp(zpath.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        http = "local"
    else:
        check_disk()
        time.sleep(PRISM_SLEEP)
        r = get(url, stream=True)
        if r.status_code != 200:
            return f"http{r.status_code}"
        with open(zpath, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
        fetched, http = utcnow(), "200"
    body = zpath.read_bytes()
    if body[:2] != b"PK":
        zpath.unlink()
        return "notzip"
    zf = zipfile.ZipFile(io.BytesIO(body))
    names = zf.namelist()
    ncn = next(n for n in names if n.endswith(".nc"))
    infon = next(n for n in names if n.endswith(".info.txt"))
    info = parse_info(zf.read(infon).decode("utf-8", "replace"))
    if day == dt.date(2026, 7, 15):
        stn = next((n for n in names if n.endswith(".stn.csv")), None)
        if stn:
            PRISM_STN.mkdir(parents=True, exist_ok=True)
            (PRISM_STN / f"prism_{var}_20260715.stn.csv").write_bytes(zf.read(stn))
    ds = open_nc_bytes(zf.read(ncn))
    lat, lon = ds["lat"][:], ds["lon"][:]
    band = np.ma.filled(ds["Band1"][:, :].astype("float64"), np.nan)
    ds.close()
    band[band <= -9990] = np.nan
    if "d" not in discs_holder:
        discs_holder["d"] = prism_discs_from_local()
    assert len(lat) == 621 and len(lon) == 1405
    assert np.allclose(lat[[0, -1]], [24.08333333333333, 24.08333333333333 + 620 / 24.0], atol=1e-6)
    assert np.allclose(lon[[0, -1]], [-125.0, -125.0 + 1404 / 24.0], atol=1e-6)
    out = {s: band[dc["ii"], dc["jj"]].astype("float32") for s, dc in discs_holder["d"].items()}
    npz.parent.mkdir(parents=True, exist_ok=True)
    rel = int(info.get("PRISM_DATASET_RELEASE_NUMBER", -1))
    np.savez_compressed(npz, release=rel, created=info.get("PRISM_DATASET_CREATE_DATE", ""),
                        version=info.get("PRISM_DATASET_VERSION", ""), **out)
    manifest_append("grids", dict(dataset=f"prism_4km_{var}_daily", url=url, local_path=str(zpath),
                    bytes=len(body), md5=md5_bytes(body), http_status=http, fetched_utc=fetched,
                    source_version=f"release={rel};created={info.get('PRISM_DATASET_CREATE_DATE','')};"
                                   f"dataset={info.get('PRISM_DATASET_TYPE','')}/{info.get('PRISM_DATASET_VERSION','')}",
                    retained="no"))
    zpath.unlink()
    return "ok"


def assemble_prism_month(ym: str, discs: dict) -> int:
    y, m = int(ym[:4]), int(ym[4:])
    days = []
    d = dt.date(y, m, 1)
    while d.month == m:
        if d <= WINDOW_END and ((PRISM_DAYS / "tmax" / f"{d:%Y%m%d}.npz").exists()
                                or (PRISM_DAYS / "ppt" / f"{d:%Y%m%d}.npz").exists()):
            days.append(d)
        d += dt.timedelta(days=1)
    if not days:
        return 0
    rows = 0
    for s in SETTLEMENT:
        nc_ = len(discs[s]["lat"])
        tmax = np.full((len(days), nc_), np.nan)
        prcp = np.full((len(days), nc_), np.nan)
        rt, rp = [], []
        for k, dd in enumerate(days):
            pt = PRISM_DAYS / "tmax" / f"{dd:%Y%m%d}.npz"
            if pt.exists():
                zt = np.load(pt)
                tmax[k] = f_tenths(zt[s].astype(float))
                rt.append(int(zt["release"]))
            else:
                rt.append(-1)
            pp = PRISM_DAYS / "ppt" / f"{dd:%Y%m%d}.npz"
            if pp.exists():
                zp = np.load(pp)
                prcp[k] = in_hundredths(zp[s].astype(float))
                rp.append(int(zp["release"]))
            else:
                rp.append(-1)
        tmin = np.full_like(tmax, np.nan)
        df = _long_frame("prism", s, discs[s], days, tmax, tmin, prcp, "an91d", rt, rp)
        df["prism_release_ppt"] = df["prism_release_ppt"].where(df["prism_release_ppt"] >= 0)
        df["prism_release_tmax"] = df["prism_release_tmax"].where(df["prism_release_tmax"] >= 0)
        write_part("prism", s, ym, df)
        rows += len(df)
    return rows


def pull_prism(start: dt.date = WINDOW_START, end: dt.date = WINDOW_END) -> None:
    holder: dict = {"d": prism_discs_from_local()}
    months = month_list(start, end)
    stop = False
    for ym in months:
        y, m = int(ym[:4]), int(ym[4:])
        d = dt.date(y, m, 1)
        missing = 0
        while d.month == m and d <= end:
            if d >= start:
                for var in ("tmax", "ppt"):
                    res = _prism_day(var, d, holder)
                    if res not in ("ok", "cached"):
                        print("PRISM", var, d, res, flush=True)
                        missing += 1
                        if (res.startswith("http4") or res == "notzip") and d >= dt.date(2026, 9, 1):
                            stop = True  # latest days not published yet: do not ask for later ones
                if stop:
                    break
            d += dt.timedelta(days=1)
        rows = assemble_prism_month(ym, holder["d"])
        print("PRISM", ym, rows, "rows", "missing", missing, flush=True)
        if stop:
            break


def prism_discs_from_local() -> dict:
    """Disc indices rebuilt from the PRISM grid axes (fixed 621 x 1405 grid, NAD83 2.5')."""
    lat = 24.08333333333333 + np.arange(621) / 24.0
    lon = -125.0 + np.arange(1405) / 24.0
    return build_discs(lat, lon)


def assemble_prism_all() -> None:
    discs = prism_discs_from_local()
    for ym in month_list(WINDOW_START, WINDOW_END):
        n = assemble_prism_month(ym, discs)
        print("assemble", ym, n)


# ---------------------------------------------------------------- PRISM extra cells (Phase 3 re-pull)
# Phase 1 kept only the 40 km discs, but a PRISM download is the whole CONUS grid: cells outside the discs
# can only come from a fresh download of each day file. This block keeps just the requested extra cells in a
# separate per-day cache (PRISM_EXTRA_DAYS), so the Phase 1 cache and the default pull are never touched.
# A (var, day) file is fetched only if its extra npz is missing or lacks a requested cell, and never inside
# PRISM's 24 h limit for the same file (checked per file against data/manifests/grids.csv).
PRISM_EXTRA_DAYS = CACHE / "prism_days_extra"
PRISM_EXTRA_OUT = CACHE / "grid_extra" / "prism_extra_cells.parquet"
PRISM_MIN_GAP = dt.timedelta(hours=24, minutes=5)
REPULL_POINTS = ROOT / "reports" / "eval-03" / "repull_points.json"
PRISM_VARS = ("tmax", "ppt")


def prism_axes() -> tuple[np.ndarray, np.ndarray]:
    """Fixed PRISM 4 km axes (621 x 1405, NAD83 2.5')."""
    return 24.08333333333333 + np.arange(621) / 24.0, -125.0 + np.arange(1405) / 24.0


def prism_cell_for(lat: float, lon: float) -> dict:
    """The PRISM cell containing (lat, lon): same containment rule as wi.eval03.sources (centre within 1/48 deg)."""
    la, lo = prism_axes()
    i, j = int(np.argmin(np.abs(la - lat))), int(np.argmin(np.abs(lo - lon)))
    inside = bool(abs(la[i] - lat) <= 1 / 48 + 1e-6 and abs(lo[j] - lon) <= 1 / 48 + 1e-6)
    return dict(cell_id=f"{la[i]:.4f}_{lo[j]:.4f}", i=i, j=j, lat=float(la[i]), lon=float(lo[j]), inside_grid=inside)


def disc_cell_ids() -> set[str]:
    return {c for dc in prism_discs_from_local().values() for c in dc["cell_id"]}


def cells_from_radius(radius_km: float) -> list[dict]:
    """Cells within radius_km of any settlement station that are not already inside a 40 km disc."""
    la, lo = prism_axes()
    inner = disc_cell_ids()
    cells: dict[str, dict] = {}
    for dc in build_discs(la, lo, radius_km).values():
        for ii, jj, cid in zip(dc["ii"], dc["jj"], dc["cell_id"]):
            if cid not in inner and cid not in cells:
                cells[cid] = dict(cell_id=str(cid), i=int(ii), j=int(jj), lat=float(la[ii]), lon=float(lo[jj]))
    return sorted(cells.values(), key=lambda c: c["cell_id"])


def cells_from_points_file(path: Path) -> list[dict]:
    """The `cells` list of a repull_points.json, validated against the PRISM axes; cells already inside a
    40 km disc are dropped (they are in the Phase 1 cache)."""
    import json
    doc = json.loads(Path(path).read_text())
    la, lo = prism_axes()
    inner = disc_cell_ids()
    out = {}
    for c in doc["cells"]:
        i, j = int(c["i"]), int(c["j"])
        want = f"{la[i]:.4f}_{lo[j]:.4f}"
        if c["cell_id"] != want:
            raise SystemExit(f"{path}: cell {c['cell_id']} does not match PRISM index ({i}, {j}) = {want}")
        if want in inner:
            print("note: cell", want, "is already inside a 40 km disc; not re-pulled", flush=True)
            continue
        out[want] = dict(cell_id=want, i=i, j=j, lat=float(la[i]), lon=float(lo[j]))
    return sorted(out.values(), key=lambda c: c["cell_id"])


def prism_fetch_log() -> dict[str, dt.datetime]:
    """url -> time of the latest recorded download of that PRISM file (data/manifests/grids.csv, UTC)."""
    p = MANIFESTS / "grids.csv"
    out: dict[str, dt.datetime] = {}
    if not p.exists():
        return out
    with open(p, newline="") as f:
        for r in csv.DictReader(f):
            if r["dataset"].startswith("prism_4km_") and r["fetched_utc"]:
                t = dt.datetime.strptime(r["fetched_utc"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
                if r["url"] not in out or t > out[r["url"]]:
                    out[r["url"]] = t
    return out


def extra_day_path(var: str, day: dt.date) -> Path:
    return PRISM_EXTRA_DAYS / var / f"{day:%Y%m%d}.npz"


def extra_day_cached(var: str, day: dt.date, ids: set[str]) -> bool:
    p = extra_day_path(var, day)
    if not p.exists():
        return False
    try:
        return ids <= set(np.load(p)["cell_ids"].tolist())
    except Exception:  # truncated file from a killed run: treat as missing
        return False


def plan_prism_extra(cells: list[dict], start: dt.date = WINDOW_START, end: dt.date = WINDOW_END,
                     now: dt.datetime | None = None) -> list[dict]:
    """One row per (day, var): status cached | fetch | fetch_local (zip on disk, no network) | blocked_24h.
    Pure: reads the two caches and the manifest, never the network."""
    now = now or dt.datetime.now(dt.timezone.utc)
    ids = {c["cell_id"] for c in cells}
    last = prism_fetch_log()
    rows = []
    d = start
    while d <= end:
        for var in PRISM_VARS:
            url = PRISM_URL.format(var=var, ymd=f"{d:%Y%m%d}")
            row = dict(var=var, day=d, url=url, eligible_utc=None)
            if extra_day_cached(var, d, ids):
                row["status"] = "cached"
            elif (RAW / "prism" / var / f"{d:%Y%m%d}.zip").exists():
                row["status"] = "fetch_local"
            elif url in last and now < last[url] + PRISM_MIN_GAP:
                row["status"] = "blocked_24h"
                row["eligible_utc"] = (last[url] + PRISM_MIN_GAP).strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                row["status"] = "fetch"
            rows.append(row)
        d += dt.timedelta(days=1)
    return rows


def print_prism_plan(rows: list[dict], label: str, brief: bool = False) -> None:
    by = {}
    for r in rows:
        by.setdefault(r["status"], []).append(r)
    order = {"fetch": 0, "fetch_local": 1, "blocked_24h": 2}
    todo = sorted((r for r in rows if r["status"] in order), key=lambda r: (order[r["status"]], r["day"], r["var"]))
    print(f"PRISM dry run [{label}]: {len(rows)} files in window")
    print(f"  cached (skipped): {len(by.get('cached', []))}")
    print(f"  would fetch: {len(by.get('fetch', []))}   from a local zip (no network): {len(by.get('fetch_local', []))}"
          f"   blocked by the 24 h rule: {len(by.get('blocked_24h', []))}")
    if by.get("blocked_24h"):
        el = sorted(r["eligible_utc"] for r in by["blocked_24h"])
        print(f"  24 h rule: earliest file eligible {el[0]}, last file eligible {el[-1]}")
    shown = todo if not brief or len(todo) <= 12 else todo[:6] + [None] + todo[-6:]
    for r in shown:
        if r is None:
            print(f"  ... ({len(todo) - 12} more)")
        else:
            extra = f"  (eligible {r['eligible_utc']})" if r["eligible_utc"] else ""
            print(f"  {r['status']:<12} {r['var']:<4} {r['day']:%Y-%m-%d}  {r['url']}{extra}")


def prism_extra_missing(cells: list[dict], start: dt.date, end: dt.date) -> list[tuple[str, dt.date]]:
    """(var, day) that the Phase 1 cache has but the extra cache lacks: a re-pull is incomplete until this is empty.
    Days Phase 1 never got (for example tmax 2026-08-01 and days PRISM had not published) are not required."""
    ids = {c["cell_id"] for c in cells}
    out = []
    d = start
    while d <= end:
        for var in PRISM_VARS:
            if (PRISM_DAYS / var / f"{d:%Y%m%d}.npz").exists() and not extra_day_cached(var, d, ids):
                out.append((var, d))
        d += dt.timedelta(days=1)
    return out


def _prism_day_extra(var: str, day: dt.date, cells: list[dict], last: dict) -> str:
    ymd = f"{day:%Y%m%d}"
    ids = {c["cell_id"] for c in cells}
    if extra_day_cached(var, day, ids):
        return "cached"
    zpath = RAW / "prism" / var / f"{ymd}.zip"
    url = PRISM_URL.format(var=var, ymd=ymd)
    kept = zpath.exists()  # a zip that was on disk before this call is never deleted by it
    if kept:
        fetched = dt.datetime.fromtimestamp(zpath.stat().st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        http = "local"
    else:
        if url in last and dt.datetime.now(dt.timezone.utc) < last[url] + PRISM_MIN_GAP:
            return "blocked_24h"
        zpath.parent.mkdir(parents=True, exist_ok=True)
        check_disk()
        time.sleep(PRISM_SLEEP)
        r = get(url, stream=True)
        if r.status_code != 200:
            return f"http{r.status_code}"
        with open(zpath, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
        fetched, http = utcnow(), "200"
    body = zpath.read_bytes()
    if body[:2] != b"PK":
        if not kept:
            zpath.unlink()
        return "notzip"
    zf = zipfile.ZipFile(io.BytesIO(body))
    names = zf.namelist()
    ncn = next(n for n in names if n.endswith(".nc"))
    infon = next(n for n in names if n.endswith(".info.txt"))
    info = parse_info(zf.read(infon).decode("utf-8", "replace"))
    ds = open_nc_bytes(zf.read(ncn))
    lat, lon = ds["lat"][:], ds["lon"][:]
    band = np.ma.filled(ds["Band1"][:, :].astype("float64"), np.nan)
    ds.close()
    band[band <= -9990] = np.nan
    assert len(lat) == 621 and len(lon) == 1405
    assert np.allclose(lat[[0, -1]], [24.08333333333333, 24.08333333333333 + 620 / 24.0], atol=1e-6)
    assert np.allclose(lon[[0, -1]], [-125.0, -125.0 + 1404 / 24.0], atol=1e-6)
    ii = np.array([c["i"] for c in cells])
    jj = np.array([c["j"] for c in cells])
    vals = band[ii, jj].astype("float32")
    # vintage check: the same file re-read at the Phase 1 disc cells against the Phase 1 cache of that day
    n_diff = -1
    old = PRISM_DAYS / var / f"{ymd}.npz"
    if old.exists():
        z = np.load(old)
        n_diff = 0
        for s, dc in prism_discs_from_local().items():
            a, b = band[dc["ii"], dc["jj"]].astype("float32"), z[s]
            n_diff += int(np.sum(~np.isclose(a, b, atol=1e-3, equal_nan=True)))
    rel = int(info.get("PRISM_DATASET_RELEASE_NUMBER", -1))
    npz = extra_day_path(var, day)
    npz.parent.mkdir(parents=True, exist_ok=True)
    tmp = npz.with_name(npz.name + ".part")
    with open(tmp, "wb") as f:
        np.savez_compressed(f, cell_ids=np.array([c["cell_id"] for c in cells]),
                            lat=np.array([c["lat"] for c in cells]), lon=np.array([c["lon"] for c in cells]),
                            vals=vals, release=rel, created=info.get("PRISM_DATASET_CREATE_DATE", ""),
                            version=info.get("PRISM_DATASET_VERSION", ""), disc_cells_changed=n_diff)
    tmp.replace(npz)  # atomic: a killed run leaves no half-written cache file
    manifest_append("grids", dict(dataset=f"prism_4km_{var}_daily", url=url, local_path=str(zpath),
                    bytes=len(body), md5=md5_bytes(body), http_status=http, fetched_utc=fetched,
                    source_version=f"release={rel};created={info.get('PRISM_DATASET_CREATE_DATE','')};"
                                   f"dataset={info.get('PRISM_DATASET_TYPE','')}/{info.get('PRISM_DATASET_VERSION','')};"
                                   f"extra_cells={len(cells)}",
                    retained="yes" if kept else "no"))
    last[url] = dt.datetime.now(dt.timezone.utc)
    if not kept:
        zpath.unlink()
    return "ok"


def pull_prism_extra(cells: list[dict], start: dt.date = WINDOW_START, end: dt.date = WINDOW_END,
                     dry_run: bool = False, brief: bool = False, label: str = "") -> int:
    """Fetch the extra cells for every uncached (var, day); returns a process exit code (0 = complete)."""
    label = label or f"{len(cells)} extra cells, {start}..{end}"
    if dry_run:
        print_prism_plan(plan_prism_extra(cells, start, end), label, brief)
        return 0
    last = prism_fetch_log()
    counts: dict[str, int] = {}
    stop = False
    d = start
    while d <= end and not stop:
        for var in PRISM_VARS:
            res = _prism_day_extra(var, d, cells, last)
            counts[res] = counts.get(res, 0) + 1
            if res not in ("ok", "cached"):
                print("PRISM extra", var, d, res, flush=True)
                if (res.startswith("http4") or res == "notzip") and d >= dt.date(2026, 9, 1):
                    stop = True  # latest days not published yet: do not ask for later ones
        if d.day == 1 or d == end:
            print("PRISM extra", f"{d:%Y-%m}", counts, flush=True)
        d += dt.timedelta(days=1)
    n = assemble_prism_extra(cells)
    short = prism_extra_missing(cells, start, end)
    changed = sum(int(np.load(p)["disc_cells_changed"] > 0) for p in PRISM_EXTRA_DAYS.glob("*/*.npz"))
    print("PRISM extra done:", counts, "assembled rows", n, "days whose fresh disc cells differ from the Phase 1 cache:", changed,
          flush=True)
    if short:
        print(f"INCOMPLETE: {len(short)} (var, day) files that Phase 1 has are still missing, first {short[0]}", flush=True)
        return 5
    return 0


def assemble_prism_extra(cells: list[dict] | None = None) -> int:
    """Long parquet of every extra-cache day: cell_id, lat, lon, label_day, tmax (F tenths), prcp (hundredths in), releases."""
    frames = []
    days: dict[dt.date, dict] = {}
    for var in PRISM_VARS:
        for p in sorted((PRISM_EXTRA_DAYS / var).glob("*.npz")) if (PRISM_EXTRA_DAYS / var).exists() else []:
            z = np.load(p)
            days.setdefault(dt.datetime.strptime(p.stem, "%Y%m%d").date(), {})[var] = z
    want = {c["cell_id"] for c in cells} if cells else None
    for day in sorted(days):
        z = days[day]
        ref = z.get("tmax", z.get("ppt"))
        ids = ref["cell_ids"].tolist()
        n = len(ids)
        tmax = np.full(n, np.nan)
        prcp = np.full(n, np.nan)
        for var, tgt in (("tmax", "t"), ("ppt", "p")):
            if var in z:
                v = dict(zip(z[var]["cell_ids"].tolist(), z[var]["vals"].astype(float)))
                arr = np.array([v.get(i, np.nan) for i in ids])
                if tgt == "t":
                    tmax = f_tenths(arr)
                else:
                    prcp = in_hundredths(arr)
        df = pd.DataFrame({
            "cell_id": ids, "lat": ref["lat"], "lon": ref["lon"],
            "label_day": day,
            "tmax_f_tenths": pd.Series(tmax).astype("Int16"),
            "prcp_hundredths_in": pd.Series(prcp).astype("Int32"),
            "prism_release_tmax": pd.Series([int(z["tmax"]["release"]) if "tmax" in z else np.nan] * n).astype("Int8"),
            "prism_release_ppt": pd.Series([int(z["ppt"]["release"]) if "ppt" in z else np.nan] * n).astype("Int8"),
        })
        if want is not None:
            df = df[df.cell_id.isin(want)]
        frames.append(df[~(df.tmax_f_tenths.isna() & df.prcp_hundredths_in.isna())])
    if not frames:
        return 0
    out = pd.concat(frames, ignore_index=True)
    PRISM_EXTRA_OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(PRISM_EXTRA_OUT, index=False)
    return len(out)


def plan_prism_default(start: dt.date = WINDOW_START, end: dt.date = WINDOW_END) -> list[dict]:
    """What `pull_prism` would request: every (day, var) without a Phase 1 npz (nothing else is ever fetched)."""
    now = dt.datetime.now(dt.timezone.utc)
    last = prism_fetch_log()
    rows = []
    d = start
    while d <= end:
        for var in PRISM_VARS:
            url = PRISM_URL.format(var=var, ymd=f"{d:%Y%m%d}")
            row = dict(var=var, day=d, url=url, eligible_utc=None)
            if (PRISM_DAYS / var / f"{d:%Y%m%d}.npz").exists():
                row["status"] = "cached"
            elif (RAW / "prism" / var / f"{d:%Y%m%d}.zip").exists():
                row["status"] = "fetch_local"
            elif url in last and now < last[url] + PRISM_MIN_GAP:
                row["status"] = "blocked_24h"
                row["eligible_utc"] = (last[url] + PRISM_MIN_GAP).strftime("%Y-%m-%dT%H:%M:%SZ")
            else:
                row["status"] = "fetch"
            rows.append(row)
        d += dt.timedelta(days=1)
    return rows


def missing_points_doc() -> dict:
    """The truth-set points with no PRISM cell in the Phase 1 discs, with the cell that covers each."""
    from wi.eval03 import points as P
    la, lo = prism_axes()
    discs = prism_discs_from_local()
    stations = settlement_points()
    have = disc_cell_ids()
    pts: dict[str, dict] = {}
    for var in ("temperature", "rain"):
        for m, b in P.pairs(var):
            st = P.STATIONS[b]
            cell = prism_cell_for(st.lat, st.lon)
            if cell["cell_id"] in have:
                continue
            e = pts.setdefault(b, dict(id=b, name=st.name, lat=st.lat, lon=st.lon, cell=cell, pairs=[]))
            d_cell = float(haversine_km(stations[m][0], stations[m][1], np.array([cell["lat"]]), np.array([cell["lon"]]))[0])
            e["pairs"].append(dict(variable=var, market=m, settlement_station=m,
                                   station_lat=stations[m][0], station_lon=stations[m][1],
                                   dist_point_to_station_km=round(P.haversine_km(m, b), 2),
                                   dist_cell_centre_to_station_km=round(d_cell, 2)))
    points = sorted(pts.values(), key=lambda e: e["id"])
    cells = {}
    per_station: dict[str, float] = {}
    for e in points:
        c = e["cell"]
        cells[c["cell_id"]] = dict(cell_id=c["cell_id"], i=c["i"], j=c["j"], lat=c["lat"], lon=c["lon"])
        for p in e["pairs"]:
            s = p["settlement_station"]
            per_station[s] = max(per_station.get(s, 0.0), p["dist_cell_centre_to_station_km"])
    need = max(per_station.values())
    radius = float(np.ceil(need))
    cover = {c["cell_id"] for c in cells_from_radius(radius)}
    assert set(cells) <= cover, "suggested radius does not cover every missing cell"
    return dict(
        what="Truth-set points with no PRISM cell in the Phase 1 40 km discs (Phase 3 deviation 1)",
        existing_disc_radius_km=RADIUS_KM,
        n_points=len(points),
        n_pairs_temperature=sum(1 for e in points for p in e["pairs"] if p["variable"] == "temperature"),
        n_pairs_rain=sum(1 for e in points for p in e["pairs"] if p["variable"] == "rain"),
        covering_radius_km_by_settlement_station={k: round(v, 2) for k, v in sorted(per_station.items())},
        covering_radius_km=radius,
        covering_radius_extra_cells=len(cover),
        points=points,
        cells=sorted(cells.values(), key=lambda c: c["cell_id"]),
        note=("A PRISM file is the whole CONUS grid, so pulling these cells means downloading every day file again "
              "(none of the Phase 1 per-day npz files holds them). `--points` keeps only these cells; "
              f"`--radius-km {radius:g}` would keep {len(cover)} cells and covers the same points."))


# ---------------------------------------------------------------- vintages

def list_prelim_tars() -> list[tuple[str, int, str]]:
    import subprocess
    out = subprocess.run(["aws", "s3", "ls", "s3://noaa-nclimgrid-daily-pds/archive/2026/", "--no-sign-request"],
                         capture_output=True, text=True, check=True).stdout
    rows = []
    for line in out.splitlines():
        p = line.split()
        if len(p) == 4 and "_prelim_" in p[3]:
            m = re.search(r"_s(\d{8})_e(\d{8})_c(\d{8})\.tar\.gz$", p[3])
            if m:
                rows.append((p[3], int(p[2]), m.group(3)))
    rows.sort(key=lambda r: (r[2], r[0]))
    return rows


def pull_vintages(step: int = 3, budget_bytes: int = int(2.5e9)) -> None:
    import subprocess
    tars = list_prelim_tars()
    tars = [t for t in tars if t[2] >= "20260421"]
    total = sum(t[1] for t in tars)
    sampled = total > budget_bytes
    sel = tars[::step] if sampled else tars
    # always include the newest vintage
    if tars and tars[-1] not in sel:
        sel.append(tars[-1])
    print(f"{len(tars)} prelim tarballs since 2026-04-21, {total/1e9:.2f} GB; "
          f"sampling every {step if sampled else 1}: {len(sel)} tarballs, {sum(t[1] for t in sel)/1e9:.2f} GB", flush=True)
    VINTAGES.mkdir(parents=True, exist_ok=True)
    tmp = RAW / "nclimgrid" / "vintages"
    tmp.mkdir(parents=True, exist_ok=True)
    discs = None
    frames = []
    out_p = VINTAGES / "nclimgrid_prelim.parquet"
    if out_p.exists():
        frames.append(pd.read_parquet(out_p))
    for name, size, created in sel:
        if manifest_has("grids", f"s3://noaa-nclimgrid-daily-pds/archive/2026/{name}"):
            continue
        check_disk()
        s3 = f"s3://noaa-nclimgrid-daily-pds/archive/2026/{name}"
        local = tmp / name
        r = subprocess.run(["aws", "s3", "cp", s3, str(local), "--no-sign-request", "--only-show-errors"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print("aws cp failed", name, r.stderr[:200])
            continue
        fetched = utcnow()
        md5 = md5_file(local)
        nbytes = local.stat().st_size
        with tarfile.open(local, "r:gz") as tf:
            member = next(m for m in tf.getmembers() if m.name.endswith("-grd-prelim.nc"))
            ver_m = next((m for m in tf.getmembers() if m.name.endswith("version.txt")), None)
            nc_bytes = tf.extractfile(member).read()
            ver = version_line(tf.extractfile(ver_m).read().decode()) if ver_m else ""
        local.unlink()
        ds = open_nc_bytes(nc_bytes)
        if discs is None:
            discs = build_discs(ds["lat"][:], ds["lon"][:])
        t = ds["time"][:]
        days = [EPOCH + dt.timedelta(days=int(v)) for v in t]
        tmax = np.ma.filled(ds["tmax"][:, :, :].astype("float64"), np.nan)
        prcp = np.ma.filled(ds["prcp"][:, :, :].astype("float64"), np.nan)
        ds.close()
        cdate = pd.Timestamp(f"{created[:4]}-{created[4:6]}-{created[6:]}").date()
        parts = []
        for s in SETTLEMENT:
            dc = discs[s]
            tx = f_tenths(tmax[:, dc["ii"], dc["jj"]])
            pr = in_hundredths(prcp[:, dc["ii"], dc["jj"]])
            nd, n = tx.shape
            df = pd.DataFrame({
                "vintage_created": cdate,
                "label_day": np.repeat(np.array(days, dtype="datetime64[D]"), n),
                "station": s,
                "cell_id": np.tile(dc["cell_id"], nd),
                "tmax_f_tenths": pd.Series(tx.ravel()).astype("Int16"),
                "prcp_hundredths_in": pd.Series(pr.ravel()).astype("Int32"),
            })
            df = df[~(df.tmax_f_tenths.isna() & df.prcp_hundredths_in.isna())]
            parts.append(df)
        nv = pd.concat(parts, ignore_index=True)
        nv["label_day"] = pd.to_datetime(nv["label_day"]).dt.date
        frames.append(nv)
        manifest_append("grids", dict(dataset="nclimgrid_prelim_vintage", url=s3,
                        local_path=str(local), bytes=nbytes, md5=md5, http_status="aws-s3-ok",
                        fetched_utc=fetched, source_version=f"created={created};{ver}", retained="no"))
        allv = pd.concat(frames, ignore_index=True)
        allv.to_parquet(out_p, index=False)
        frames = [allv]
        print("vintage", created, name, len(nv), "rows; distinct vintages", allv.vintage_created.nunique(), flush=True)
        del nc_bytes, tmax, prcp
