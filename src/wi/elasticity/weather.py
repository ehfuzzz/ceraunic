"""Settlement-station daily weather for EVAL-06: NWS CLI (2023+) spliced onto NOAA RCC-ACIS (all years).

KNYC (NYC groups) and KMDW (Chicago groups). CLI wins where both exist (PREREG C1).
Trace ('T') -> 0.0 and flagged. Output: data/cache/elasticity/weather_daily.parquet with
station, date (local climate day), tmax_f, prcp_in, snow_in, prcp_trace, src.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "data" / "cache" / "elasticity" / "weather_daily.parquet"
RAW = ROOT / "data" / "raw" / "acis"
STATIONS = {"NYC": ("KNYC", "NYC_KNYC_cli.csv"), "MDW": ("KMDW", "MDW_KMDW_cli.csv")}
ACIS = "https://data.rcc-acis.org/StnData"


def _num(v):
    if v in (None, "", "M", "S"):
        return np.nan
    if v == "T":
        return 0.0
    try:
        return float(str(v).rstrip("A"))
    except ValueError:
        return np.nan


def pull_acis(station: str, sdate: str = "1990-01-01", edate: str = "2026-09-29") -> pd.DataFrame:
    sid = STATIONS[station][0]
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / f"{sid}.json"
    if not path.exists():
        r = requests.get(ACIS, params={"sid": sid, "sdate": sdate, "edate": edate,
                                       "elems": "maxt,pcpn,snow", "output": "json"}, timeout=120)
        r.raise_for_status()
        path.write_text(r.text)
    d = json.loads(path.read_text())
    rows = d["data"]
    df = pd.DataFrame(rows, columns=["date", "maxt", "pcpn", "snow"])
    out = pd.DataFrame({
        "station": station,
        "date": pd.to_datetime(df["date"]).dt.date,
        "tmax_f": df["maxt"].map(_num),
        "prcp_in": df["pcpn"].map(_num),
        "snow_in": df["snow"].map(_num),
        "prcp_trace": df["pcpn"].eq("T"),
        "src": "acis",
    })
    return out


def load_cli(station: str) -> pd.DataFrame:
    fn = ROOT / "data" / "raw" / "iem" / "cli" / STATIONS[station][1]
    c = pd.read_csv(fn, dtype=str)
    return pd.DataFrame({
        "station": station,
        "date": pd.to_datetime(c["valid"]).dt.date,
        "tmax_f": c["high"].map(_num),
        "prcp_in": c["precip"].map(_num),
        "snow_in": c["snow"].map(_num),
        "prcp_trace": c["precip"].eq("T"),
        "src": "nws_cli",
    })


def ord_snow() -> pd.DataFrame:
    """KMDW has no snowfall observation (CLI and ACIS both missing); Chicago's official snowfall
    is measured at O'Hare, so the Chicago snow control uses KORD snowfall (EVAL-06 deviation 1)."""
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / "KORD_snow.json"
    if not path.exists():
        r = requests.get(ACIS, params={"sid": "KORD", "sdate": "1990-01-01", "edate": "2026-09-29",
                                       "elems": "snow", "output": "json"}, timeout=120)
        r.raise_for_status()
        path.write_text(r.text)
    d = json.loads(path.read_text())
    df = pd.DataFrame(d["data"], columns=["date", "snow"])
    return pd.DataFrame({"date": pd.to_datetime(df["date"]).dt.date, "snow_ord": df["snow"].map(_num)})


def build() -> dict:
    frames, report = [], {}
    for st in STATIONS:
        a = pull_acis(st)
        c = load_cli(st).dropna(subset=["tmax_f"])
        j = a.merge(c, on="date", suffixes=("_a", "_c"))
        report[st] = {
            "overlap_days": int(len(j)),
            "tmax_equal_share": float((j.tmax_f_a == j.tmax_f_c).mean()),
            "prcp_equal_share": float((np.abs(j.prcp_in_a - j.prcp_in_c) < 0.005).mean()),
            "wet_flag_equal_share": float(((j.prcp_in_a >= 0.01) == (j.prcp_in_c >= 0.01)).mean()),
            "acis_rows": int(len(a)), "acis_first": str(a.date.min()), "cli_rows": int(len(c)),
        }
        keep_a = a[~a.date.isin(set(c.date))]
        f = pd.concat([keep_a, c], ignore_index=True).sort_values("date")
        if st == "MDW":
            f = f.drop(columns=["snow_in"]).merge(ord_snow().rename(columns={"snow_ord": "snow_in"}), on="date", how="left")
            report[st]["snow_source"] = "KORD (ACIS) - KMDW has no snowfall"
        frames.append(f)
    w = pd.concat(frames, ignore_index=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    w.to_parquet(OUT, index=False)
    return report


def load() -> pd.DataFrame:
    return pd.read_parquet(OUT)


if __name__ == "__main__":
    rep = build()
    (OUT.parent / "weather_report.json").write_text(json.dumps(rep, indent=1))
    print(json.dumps(rep, indent=1))
