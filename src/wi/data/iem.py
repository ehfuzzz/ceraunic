"""IEM (Iowa Environmental Mesonet) station weather pulls.

Public, keyless reads from mesonet.agron.iastate.edu only. Sequential requests with
small sleeps; transient "server over capacity" answers are retried with backoff.

Sources
- ASOS daily summaries: /cgi-bin/request/daily.py (same service ins1 used; the ins1 CSVs are
  this service's `var=max_temp_f` style output). Day = station local calendar date label; the
  backend docs say airport stations are summarised over standard time (1 AM to 1 AM DST).
- NWS official daily climate: /json/cli.py (CLI, final daily climate report) and
  /json/cf6.py (CF6 monthly preliminary table). Neither is under /api/1/nws/...; the
  /api/1/ OpenAPI has no cli/cf6 route (probed 2026-09-30), the /json/ endpoints do.

Run: `uv run python -m wi.data.iem` (writes data/raw/iem, data/cache/weather).
"""
from __future__ import annotations

import datetime as dt
import io
import math
import time
from pathlib import Path

import pandas as pd
import requests

BASE = "https://mesonet.agron.iastate.edu"
DAILY_URL = BASE + "/cgi-bin/request/daily.py"
CLI_URL = BASE + "/json/cli.py"
CF6_URL = BASE + "/json/cf6.py"
NETWORK_URL = BASE + "/api/1/network/{network}.json"
UA = "weather-insurance-prototype/0.1 (research; keyless public reads)"
SLEEP_S = 1.0

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw" / "iem"
CACHE = ROOT / "data" / "cache" / "weather"

START = "2023-01-01"

# requested station code -> (group, settlement-station code(s))
GROUPS: dict[str, list[str]] = {
    "NY": ["NYC", "LGA", "JFK", "TEB", "HPN", "FRG", "ISP"],
    "NJ": ["EWR", "TTN", "CDW", "MMU", "BLM", "SMQ"],
    "IL": ["MDW", "ORD", "PWK", "DPA", "UGN", "GYY"],
    "FL": ["MIA", "FLL", "OPF", "TMB", "HWO", "PBI", "HST"],
}
SETTLEMENT_FOR_GROUP = {"NY": ["NYC"], "NJ": ["EWR", "TTN"], "IL": ["MDW"], "FL": ["MIA"]}
# IEM network search order per requested station (the brief's state grouping is not the IEM
# network: TEB is NJ_ASOS, GYY is IN_ASOS). Resolved against the network tables at run time.
NETWORKS = ["NY_ASOS", "NJ_ASOS", "IL_ASOS", "IN_ASOS", "FL_ASOS"]
# Requested code -> IEM station id when IEM renamed it. PBI (Palm Beach Intl, KPBI) is carried
# as DJT in IEM's FL_ASOS table (verified: PBI returns "No stations found").
IEM_ALIAS = {"PBI": "DJT"}
# Settlement station -> ICAO id used by the NWS CLI/CF6 products.
SETTLEMENT_ICAO = {"NYC": "KNYC", "EWR": "KEWR", "TTN": "KTTN", "MDW": "KMDW", "MIA": "KMIA"}


def _get(url: str, params: dict, tries: int = 12) -> str:
    last = ""
    for i in range(tries):
        r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=120)
        body = r.text
        if r.status_code == 200 and "over capacity" not in body[:200] and not body.startswith("ERROR"):
            return body
        last = f"HTTP {r.status_code}: {body[:120]!r}"
        time.sleep(min(10 * (i + 1), 60))
    raise RuntimeError(f"{url} {params} failed after {tries} tries: {last}")


def network_table(network: str) -> pd.DataFrame:
    import json

    body = _get(NETWORK_URL.format(network=network), {})
    df = pd.DataFrame(json.loads(body)["data"])
    df["network"] = network
    return df


def resolve_stations() -> pd.DataFrame:
    """Requested stations -> IEM id, name, lat, lon, network. Missing ones are omitted."""
    tabs = []
    for n in NETWORKS:
        tabs.append(network_table(n))
        time.sleep(SLEEP_S)
    tab = pd.concat(tabs, ignore_index=True)
    rows = []
    for group, codes in GROUPS.items():
        for code in codes:
            iem_id = IEM_ALIAS.get(code, code)
            hit = tab[(tab["id"] == iem_id) & tab["online"]]
            if hit.empty:
                continue
            h = hit.iloc[0]
            rows.append(dict(station=code, iem_id=iem_id, name=h["name"], lat=h["latitude"],
                             lon=h["longitude"], network=h["network"], group=group))
    return pd.DataFrame(rows)


def fetch_daily(iem_id: str, network: str, sts: str = START, ets: str | None = None) -> str:
    """One station, full default column set as CSV text. Pulled in calendar-year chunks: a single
    multi-year request was answered "server over capacity" repeatedly on 2026-09-30, year-sized
    requests went through."""
    ets = ets or dt.date.today().isoformat()
    a, b = dt.date.fromisoformat(sts), dt.date.fromisoformat(ets)
    frames = []
    for y in range(a.year, b.year + 1):
        lo, hi = max(a, dt.date(y, 1, 1)), min(b, dt.date(y, 12, 31))
        txt = _get(DAILY_URL, dict(network=network, stations=iem_id, sts=lo.isoformat(),
                                   ets=hi.isoformat(), format="csv"))
        frames.append(pd.read_csv(io.StringIO(txt), dtype=str, keep_default_na=False))
        time.sleep(SLEEP_S)
    return pd.concat(frames, ignore_index=True).to_csv(index=False)


def fetch_official(icao: str, kind: str, years: range) -> str:
    """NWS CLI ('cli') or CF6 ('cf6') daily rows for one station, one request per year, CSV."""
    url = {"cli": CLI_URL, "cf6": CF6_URL}[kind]
    frames = []
    for y in years:
        txt = _get(url, dict(station=icao, year=y, fmt="csv"))
        frames.append(pd.read_csv(io.StringIO(txt), dtype=str, index_col=False))
        time.sleep(SLEEP_S)
    return pd.concat(frames, ignore_index=True).to_csv(index=False)


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(a))


def build_stations_csv(meta: pd.DataFrame) -> pd.DataFrame:
    """Long format: one row per (station, settlement station); NJ stations get an EWR and a TTN row."""
    coords = meta.set_index("station")[["lat", "lon"]]
    rows = []
    for _, m in meta.iterrows():
        for s in SETTLEMENT_FOR_GROUP[m["group"]]:
            rows.append(dict(station=m["station"], iem_id=m["iem_id"], name=m["name"], lat=m["lat"],
                             lon=m["lon"], network=m["network"], group=m["group"], settlement=s,
                             distance_km=round(haversine_km(m["lat"], m["lon"], coords.loc[s, "lat"],
                                                            coords.loc[s, "lon"]), 2)))
    return pd.DataFrame(rows)


def tidy_daily(station: str, csv_text: str) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(csv_text), na_values=["None", "M", ""])
    out = pd.DataFrame({
        "station": station,
        "date_local": pd.to_datetime(df["day"]).dt.date,
        "tmax_f": df["max_temp_f"],
        "tmin_f": df["min_temp_f"],
        "precip_in": df["precip_in"],
    })
    # flags: missing values stay NaN (never zero-filled); IEM stores trace precip as 0.0001
    out["tmax_missing"] = out["tmax_f"].isna()
    out["tmin_missing"] = out["tmin_f"].isna()
    out["precip_missing"] = out["precip_in"].isna()
    out["precip_trace"] = (out["precip_in"] > 0) & (out["precip_in"] < 0.005)
    out["src"] = "iem_daily_asos"
    return out


def tidy_official(station: str, cli_csv: str) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(cli_csv), dtype=str, index_col=False)
    num = lambda c: pd.to_numeric(df[c].replace({"M": None, "T": "0.0001"}), errors="coerce")
    return pd.DataFrame({
        "station": station,
        "date_local": pd.to_datetime(df["valid"]).dt.date,
        "high_f": num("high"),
        "low_f": num("low"),
        "precip_in": num("precip"),
        "high_time": df["high_time"],
        "low_time": df["low_time"],
        "src": "nws_cli",
    })


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "cli").mkdir(exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    # last COMPLETE day: yesterday (UTC date). Today's row is a partial day in every local zone.
    today = dt.datetime.now(dt.UTC).date()
    last_day = today - dt.timedelta(days=1)

    meta = resolve_stations()
    requested = [c for g in GROUPS.values() for c in g]
    dropped = [c for c in requested if c not in set(meta["station"])]
    frames, dropped_empty = [], []
    for _, m in meta.iterrows():
        f = RAW / f"{m['station']}.csv"
        if f.exists() and f.stat().st_size > 0 and pd.read_csv(f)["day"].max() == last_day.isoformat():
            txt = f.read_text()  # resume: already pulled this run-day
        else:
            txt = fetch_daily(m["iem_id"], m["network"], START, last_day.isoformat())
            f.write_text(txt)
        d = tidy_daily(m["station"], txt)
        if d["tmax_f"].notna().sum() == 0:
            dropped_empty.append(m["station"])
            continue
        frames.append(d)
        print(m["station"], m["network"], len(d), d["date_local"].min(), d["date_local"].max())
    daily = pd.concat(frames, ignore_index=True)
    kept = set(daily["station"])
    meta = meta[meta["station"].isin(kept)]
    daily.to_parquet(CACHE / "stations_daily.parquet", index=False)
    build_stations_csv(meta).to_csv(CACHE / "stations.csv", index=False)

    off = []
    for st, icao in SETTLEMENT_ICAO.items():
        cli = fetch_official(icao, "cli", range(2023, today.year + 1))
        (RAW / "cli" / f"{st}_{icao}_cli.csv").write_text(cli)
        cf6 = fetch_official(icao, "cf6", range(2023, today.year + 1))
        (RAW / "cli" / f"{st}_{icao}_cf6.csv").write_text(cf6)
        off.append(tidy_official(st, cli))
        print(st, icao, "cli rows", len(off[-1]))
    pd.concat(off, ignore_index=True).to_parquet(CACHE / "official_daily.parquet", index=False)
    print("dropped (not in IEM network tables):", dropped, "| empty:", dropped_empty)


if __name__ == "__main__":
    main()
