"""Stand-in daily demand series for EVAL-06 (plan 05), pulled without storing raw trips.

Disk is tight on this Mac, so every source is aggregated to unit-day on the way in:
  G1 Citi Bike   one monthly (or yearly) zip at a time -> start-station-day counts -> zip deleted
  G2 Divvy       same, docked (non-null start station id) starts
  G3 CTA 'L'     Socrata 5neh-572f, station-day `rides` (already daily)
  G4 Chicago taxi Socrata wrvz-psew (<2024) / ajtu-isnz (2024-), server-side SoQL group-by
                 pickup_community_area x day: sum(fare), count(*)
  G5 NYC TLC     DuckDB httpfs over the monthly yellow + green Parquet (remote column reads),
                 PULocationID x day: sum(fare_amount), count(*)

Business day = the local wall-clock date of the trip start (the sources publish naive local
times; the date of a naive local timestamp is the local calendar date, so no tz round trip is
needed; see PREREG C3). A free-disk guard runs before every download: a download is skipped,
and the run stops, if it would leave less than MIN_FREE_BYTES free.

Run: uv run python -m wi.data.sales {citibike,divvy,cta,chitaxi,tlc,all}
Outputs: data/cache/sales_daily/<source>/*.parquet and data/cache/sales_daily/manifest.jsonl
"""
from __future__ import annotations

import datetime as dt
import io
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.csv as pacsv
import requests

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data" / "cache" / "sales_daily"
TMP = ROOT / "data" / "raw" / "sales_tmp"
MANIFEST = OUT / "manifest.jsonl"
MIN_FREE_BYTES = 3 * 1024**3

START = dt.date(2022, 7, 1)
BIKE_END = dt.date(2026, 6, 30)
SOCRATA_END = dt.date(2026, 8, 31)
TLC_END = dt.date(2024, 12, 31)

CITIBIKE_URL = "https://s3.amazonaws.com/tripdata/"
DIVVY_URL = "https://divvy-tripdata.s3.amazonaws.com/"
SOCRATA = "https://data.cityofchicago.org/resource/"
TLC_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data/"


class DiskLow(RuntimeError):
    pass


def free_bytes() -> int:
    out = subprocess.run(["df", "-k", "/"], capture_output=True, text=True, check=True).stdout
    return int(out.strip().splitlines()[-1].split()[3]) * 1024


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_manifest(rec: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rec = {"ts_utc": utcnow(), **rec}
    with MANIFEST.open("a") as f:
        f.write(json.dumps(rec) + "\n")
    print(json.dumps(rec), flush=True)


def head_size(url: str) -> int:
    r = requests.head(url, timeout=60)
    r.raise_for_status()
    return int(r.headers.get("Content-Length", 0))


def guard(size: int, what: str) -> None:
    free = free_bytes()
    if free - size < MIN_FREE_BYTES:
        raise DiskLow(f"{what}: {free/1e9:.2f} GB free, download {size/1e9:.2f} GB would leave < 3 GB")


def months(a: dt.date, b: dt.date):
    y, m = a.year, a.month
    while (y, m) <= (b.year, b.month):
        yield y, m
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)


# ------------------------------------------------------------------ bikeshare (zip at a time)

BIKE_COLS = ["started_at", "start_station_id"]
BIKE_COLS_NAMED = ["started_at", "start_station_id", "start_station_name"]
_NAMED = {"on": False}


def _agg_csv_stream(fobj, name: str, acc: list[pa.Table]) -> int:
    """Stream one trip CSV; append (station, date, n) partial aggregates to acc. Returns rows read.
    Named mode (Divvy): unit = start station name (Divvy recoded station ids to CHI##### in 2025),
    unit_id = the id seen with it."""
    cols = BIKE_COLS_NAMED if _NAMED["on"] else BIKE_COLS
    ro = pacsv.ReadOptions(block_size=64 << 20)
    co = pacsv.ConvertOptions(include_columns=cols,
                              column_types={c: pa.string() for c in cols},
                              strings_can_be_null=True)
    rdr = pacsv.open_csv(fobj, read_options=ro, convert_options=co)
    n = 0
    for batch in rdr:
        t = pa.Table.from_batches([batch])
        n += t.num_rows
        t = t.filter(pc.is_valid(t["start_station_id"]))
        t = t.filter(pc.not_equal(t["start_station_id"], ""))
        day = pc.utf8_slice_codeunits(t["started_at"], 0, 10)
        one = pa.array([1] * t.num_rows, pa.int64())
        if _NAMED["on"]:
            nm = pc.utf8_trim_whitespace(pc.fill_null(t["start_station_name"], ""))
            t = pa.table({"unit": nm, "unit_id": t["start_station_id"], "date": day, "n": one})
            acc.append(t.group_by(["unit", "unit_id", "date"]).aggregate([("n", "sum")]).rename_columns(["unit", "unit_id", "date", "n"]))
        else:
            t = pa.table({"unit": t["start_station_id"], "date": day, "n": one})
            acc.append(t.group_by(["unit", "date"]).aggregate([("n", "sum")]).rename_columns(["unit", "date", "n"]))
    return n


def _walk_zip(zf: zipfile.ZipFile, acc: list[pa.Table], members: list[str], depth: int = 0) -> int:
    rows = 0
    for info in zf.infolist():
        nm = info.filename
        if nm.startswith("__MACOSX") or info.is_dir() or "/._" in nm or nm.startswith("._"):
            continue
        if nm.lower().endswith(".zip") and depth < 2:
            with zf.open(info) as f:
                inner = zipfile.ZipFile(io.BytesIO(f.read()))
            rows += _walk_zip(inner, acc, members, depth + 1)
        elif nm.lower().endswith(".csv"):
            members.append(nm)
            with zf.open(info) as f:
                rows += _agg_csv_stream(f, nm, acc)
    return rows


def pull_bike_zip(system: str, key: str, url_base: str, done: set[str]) -> None:
    if key in done:
        return
    url = url_base + key
    size = head_size(url)
    guard(size, key)
    TMP.mkdir(parents=True, exist_ok=True)
    path = TMP / key
    t0 = time.time()
    subprocess.run(["curl", "-sS", "--fail", "--retry", "5", "-o", str(path), url], check=True)
    got = path.stat().st_size
    acc: list[pa.Table] = []
    members: list[str] = []
    try:
        with zipfile.ZipFile(path) as zf:
            rows = _walk_zip(zf, acc, members)
    finally:
        path.unlink(missing_ok=True)
    keys = ["unit", "unit_id", "date"] if _NAMED["on"] else ["unit", "date"]
    tab = pa.concat_tables(acc).group_by(keys).aggregate([("n", "sum")]).rename_columns(keys + ["n"])
    df = tab.to_pandas()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df = df.dropna(subset=["date"])
    df = df[(df["date"] >= START) & (df["date"] <= BIKE_END)]
    od = OUT / system
    od.mkdir(parents=True, exist_ok=True)
    df.to_parquet(od / (key.replace(".zip", "") + ".parquet"), index=False)
    log_manifest({"source": system, "url": url, "bytes_streamed": got, "rows_read": rows,
                  "rows_out": len(df), "members": members, "seconds": round(time.time() - t0, 1),
                  "free_gb_after": round(free_bytes() / 1e9, 2)})


def _done_keys(system: str) -> set[str]:
    if not MANIFEST.exists():
        return set()
    out = set()
    for line in MANIFEST.read_text().splitlines():
        r = json.loads(line)
        if r.get("source") == system and r.get("rows_out") is not None:
            out.add(r["url"].rsplit("/", 1)[-1])
    return out


def citibike_keys() -> list[str]:
    keys = ["2022-citibike-tripdata.zip", "2023-citibike-tripdata.zip"]
    keys += [f"{y}{m:02d}-citibike-tripdata.zip" for y, m in months(dt.date(2024, 1, 1), BIKE_END)]
    return keys


def divvy_keys() -> list[str]:
    return [f"{y}{m:02d}-divvy-tripdata.zip" for y, m in months(START, BIKE_END)]


def pull_citibike() -> None:
    done = _done_keys("citibike")
    for k in citibike_keys():
        pull_bike_zip("citibike", k, CITIBIKE_URL, done)


def pull_divvy() -> None:
    """Divvy by station NAME (ids were recoded to CHI##### in 2025; EVAL-06 deviation 3)."""
    _NAMED["on"] = True
    try:
        done = _done_keys("divvy_named")
        for k in divvy_keys():
            pull_bike_zip("divvy_named", k, DIVVY_URL, done)
    finally:
        _NAMED["on"] = False


# ------------------------------------------------------------------ Socrata

def socrata(dataset: str, params: dict, tries: int = 6) -> list[dict]:
    url = SOCRATA + dataset + ".json"
    err = None
    for k in range(tries):
        try:
            r = requests.get(url, params=params, timeout=600)
            if r.status_code == 200:
                return r.json()
            err = f"HTTP {r.status_code} {r.text[:200]}"
        except requests.RequestException as e:
            err = str(e)
        time.sleep(min(60, 2 ** (k + 1)))
    raise RuntimeError(f"socrata {dataset}: {err}")


def pull_cta() -> None:
    rows, off = [], 0
    nbytes = 0
    while True:
        chunk = socrata("5neh-572f", {"$select": "station_id,stationname,date,rides",
                                      "$where": f"date >= '{START.isoformat()}T00:00:00'",
                                      "$order": "date,station_id", "$limit": 50000, "$offset": off})
        nbytes += len(json.dumps(chunk))
        rows += chunk
        if len(chunk) < 50000:
            break
        off += 50000
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["n"] = df["rides"].astype(float)
    df = df.rename(columns={"station_id": "unit"})[["unit", "stationname", "date", "n"]]
    # 5neh-572f can carry duplicate station-date rows; sum them (logged)
    dup = int(df.duplicated(["unit", "date"]).sum())
    df = df.groupby(["unit", "date"], as_index=False).agg(n=("n", "sum"), stationname=("stationname", "first"))
    od = OUT / "cta"
    od.mkdir(parents=True, exist_ok=True)
    df.to_parquet(od / "cta_daily.parquet", index=False)
    log_manifest({"source": "cta", "url": SOCRATA + "5neh-572f.json", "bytes_streamed": nbytes,
                  "rows_read": len(rows), "rows_out": len(df), "duplicate_station_days_summed": dup})


def pull_chitaxi() -> None:
    od = OUT / "chitaxi"
    od.mkdir(parents=True, exist_ok=True)
    done = _done_keys("chitaxi")
    for y, m in months(START, SOCRATA_END):
        key = f"{y}-{m:02d}"
        if key in done:
            continue
        ds = "wrvz-psew" if y < 2024 else "ajtu-isnz"
        a = dt.date(y, m, 1)
        b = dt.date(y + (m == 12), 1 if m == 12 else m + 1, 1)
        chunk = socrata(ds, {
            "$select": "pickup_community_area, date_trunc_ymd(trip_start_timestamp) as day, sum(fare) as fare, count(*) as trips",
            "$where": f"trip_start_timestamp >= '{a}T00:00:00' and trip_start_timestamp < '{b}T00:00:00' and pickup_community_area is not null",
            "$group": "pickup_community_area, day", "$limit": 50000})
        df = pd.DataFrame(chunk)
        if len(df):
            df["date"] = pd.to_datetime(df["day"]).dt.date
            df = df.rename(columns={"pickup_community_area": "unit"})
            df["fare"] = df["fare"].astype(float)
            df["trips"] = df["trips"].astype(float)
            df = df[["unit", "date", "fare", "trips"]]
            df.to_parquet(od / f"{key}.parquet", index=False)
        log_manifest({"source": "chitaxi", "url": f"{SOCRATA}{ds}.json#{key}", "bytes_streamed": len(json.dumps(chunk)),
                      "rows_read": int(df["trips"].sum()) if len(df) else 0, "rows_out": len(df)})


# ------------------------------------------------------------------ NYC TLC (DuckDB httpfs)

def pull_tlc() -> None:
    import duckdb
    od = OUT / "tlc"
    od.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    done = _done_keys("tlc")
    for color, tcol in (("yellow", "tpep_pickup_datetime"), ("green", "lpep_pickup_datetime")):
        for y, m in months(START, TLC_END):
            fname = f"{color}_tripdata_{y}-{m:02d}.parquet"
            if fname in done:
                continue
            url = TLC_URL + fname
            a = dt.date(y, m, 1)
            b = dt.date(y + (m == 12), 1 if m == 12 else m + 1, 1)
            t0 = time.time()
            q = f"""
                SELECT PULocationID::VARCHAR AS unit, CAST({tcol} AS DATE) AS date,
                       SUM(fare_amount) AS fare, COUNT(*) AS trips
                FROM read_parquet('{url}')
                WHERE fare_amount > 0 AND {tcol} >= TIMESTAMP '{a}' AND {tcol} < TIMESTAMP '{b}'
                  AND PULocationID NOT IN (264, 265)
                GROUP BY 1, 2"""
            for k in range(5):
                try:
                    df = con.execute(q).df()
                    break
                except Exception as e:  # network hiccup
                    err = e
                    time.sleep(10 * (k + 1))
            else:
                raise RuntimeError(f"tlc {fname}: {err}")
            df["color"] = color
            df.to_parquet(od / fname, index=False)
            try:
                size = head_size(url)
            except requests.RequestException:
                size = None   # CloudFront intermittently answers HEAD with 403
            log_manifest({"source": "tlc", "url": url, "bytes_streamed": size,
                          "bytes_note": "file size; DuckDB reads only the 3 needed column chunks by range request",
                          "rows_read": int(df["trips"].sum()), "rows_out": len(df), "seconds": round(time.time() - t0, 1)})


def main(argv: list[str]) -> int:
    what = argv[1] if len(argv) > 1 else "all"
    jobs = {"cta": pull_cta, "chitaxi": pull_chitaxi, "tlc": pull_tlc, "divvy": pull_divvy, "citibike": pull_citibike}
    order = list(jobs) if what == "all" else [what]
    try:
        for j in order:
            jobs[j]()
    except DiskLow as e:
        log_manifest({"source": "guard", "stopped": str(e)})
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
