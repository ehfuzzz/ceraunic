"""Unit-day panels G1-G5 from the streamed sales aggregates, joined to settlement-station weather.

Business day = local wall-clock date (PREREG C3). A unit missing on a day has y = 0 (inactive).
Weather is joined on the NWS climate day with the same calendar date (no shift: both are local
days; the one-hour DST offset of the climate day is accepted and documented).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SALES = ROOT / "data" / "cache" / "sales_daily"


@dataclass(frozen=True)
class Group:
    gid: str
    label: str
    sector: str
    city: str
    station: str          # weather station key in weather_daily.parquet
    heat_series: str
    rain_series: str | None
    source: str
    floor: float          # eligibility floor on the median daily count (PREREG C6)
    weather_class: str
    origins_primary: str
    origins_replication: str | None
    origins_lc: tuple[str, ...]


GROUPS = {
    "G1": Group("G1", "NYC-bike (Citi Bike start-station starts)", "bike", "NYC", "NYC", "KXHIGHNY", "KXRAINNYC",
                "citibike", 20, "weather-heavy upper bound", "2025-01-01", "2024-01-01",
                ("2024-07-01", "2025-01-01", "2025-07-01")),
    "G2": Group("G2", "CHI-bike (Divvy docked starts)", "bike", "CHI", "MDW", "KXHIGHCHI", None,
                "divvy_named", 20, "weather-heavy upper bound", "2025-01-01", "2024-01-01",
                ("2024-07-01", "2025-01-01", "2025-07-01")),
    "G3": Group("G3", "CHI-transit (CTA 'L' station entries)", "transit", "CHI", "MDW", "KXHIGHCHI", None,
                "cta", 100, "weather-light", "2025-01-01", "2024-01-01",
                ("2024-07-01", "2025-01-01", "2025-07-01")),
    "G4": Group("G4", "CHI-taxi (community-area fare $)", "taxi", "CHI", "MDW", "KXHIGHCHI", None,
                "chitaxi", 30, "moderate", "2025-01-01", "2024-01-01",
                ("2024-07-01", "2025-01-01", "2025-07-01")),
    "G5": Group("G5", "NYC-taxi (TLC zone fare $)", "taxi", "NYC", "NYC", "KXHIGHNY", "KXRAINNYC",
                "tlc", 30, "moderate", "2024-01-01", None, ("2023-07-01", "2024-01-01")),
}


def load_long(g: Group) -> pd.DataFrame:
    """Long unit-day frame: unit, date, y (the measure) and cnt (the count used for the floor)."""
    d = SALES / g.source
    files = sorted(d.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"no sales files for {g.source}")
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    if g.source in ("citibike", "divvy", "divvy_named"):
        if g.source == "citibike":
            # some monthly files write station 7596.10 as "7596.1"; normalise to two decimals
            u = df["unit"].astype(str)
            df["unit"] = u.where(~u.str.match(r"^\d+\.\d$"), u + "0")
        df = df.groupby(["unit", "date"], as_index=False)["n"].sum()
        df["y"] = df["n"].astype(float)
        df["cnt"] = df["y"]
    elif g.source == "cta":
        df["y"] = df["n"].astype(float)
        df["cnt"] = df["y"]
    else:  # taxi: fare dollars, trip count for the floor; TLC yellow + green summed per zone-day
        df = df.groupby(["unit", "date"], as_index=False)[["fare", "trips"]].sum()
        df["y"] = df["fare"].astype(float)
        df["cnt"] = df["trips"].astype(float)
    df["unit"] = df["unit"].astype(str)
    df["date"] = pd.to_datetime(df["date"])
    return df[["unit", "date", "y", "cnt"]]


@dataclass
class Panel:
    group: Group
    dates: np.ndarray          # datetime64[D], contiguous
    units: np.ndarray          # str
    Y: np.ndarray              # days x units, 0 = inactive
    CNT: np.ndarray            # days x units
    tmax: np.ndarray           # weather on each panel date (NaN if missing)
    prcp: np.ndarray
    snow: np.ndarray
    tmax_prev: np.ndarray      # previous calendar day
    prcp_prev: np.ndarray


def weather_series(station: str) -> pd.DataFrame:
    w = pd.read_parquet(ROOT / "data" / "cache" / "elasticity" / "weather_daily.parquet")
    w = w[w.station == station].copy()
    w["date"] = pd.to_datetime(w["date"])
    return w.set_index("date").sort_index()


def build_panel(gid: str) -> Panel:
    g = GROUPS[gid]
    df = load_long(g)
    d0, d1 = df["date"].min(), df["date"].max()
    dates = pd.date_range(max(d0, pd.Timestamp("2022-07-01")), d1, freq="D")
    wide = df.pivot_table(index="date", columns="unit", values="y", aggfunc="sum").reindex(dates).fillna(0.0)
    cnt = df.pivot_table(index="date", columns="unit", values="cnt", aggfunc="sum").reindex(dates).fillna(0.0)
    cnt = cnt[wide.columns]
    w = weather_series(g.station)
    prev = dates - pd.Timedelta(days=1)
    return Panel(g, dates.values.astype("datetime64[D]"), wide.columns.values.astype(str),
                 wide.values, cnt.values,
                 w["tmax_f"].reindex(dates).values, w["prcp_in"].reindex(dates).values,
                 w["snow_in"].reindex(dates).values,
                 w["tmax_f"].reindex(prev).values, w["prcp_in"].reindex(prev).values)


def write_panel_parquet(p: Panel) -> dict:
    """Long panel with weather joined (the artifact the plan names), and row counts."""
    n_d, n_u = p.Y.shape
    long = pd.DataFrame({
        "unit": np.tile(p.units, n_d),
        "date": np.repeat(p.dates, n_u),
        "y": p.Y.ravel(), "cnt": p.CNT.ravel(),
    })
    long = long[long.y > 0]
    wx = pd.DataFrame({"date": p.dates, "tmax_f": p.tmax, "prcp_in": p.prcp, "snow_in": p.snow})
    long = long.merge(wx, on="date", how="left")
    out = SALES / f"panel_{p.group.gid}.parquet"
    long.to_parquet(out, index=False)
    return {"group": p.group.gid, "rows_active": int(len(long)), "units_total": int(n_u),
            "first": str(p.dates[0]), "last": str(p.dates[-1]), "days": int(n_d), "path": str(out.relative_to(ROOT))}


def manifest_summary() -> list[dict]:
    m = SALES / "manifest.jsonl"
    return [json.loads(l) for l in m.read_text().splitlines()] if m.exists() else []
