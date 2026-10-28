"""CLI revision measurement (PREREG M4; 04-RESEARCH Pattern 7).

Every NWS Daily Climate Report (CLI) issuance for the five settlement stations from the IEM AFOS
archive. A product is preliminary if it carries "VALID TODAY AS OF" / "VALID AS OF" (the 4-5 PM
same-day report). Settlement vintage for day D = the latest non-preliminary product for D issued
at or before D+1 12:00Z; comparison = the latest non-preliminary product for D in the archive.

CLI: uv run python -m wi.oracle.revision pull   (writes data/raw/iem_afos_cli/<PIL>_<YEAR>.txt.gz)
"""
from __future__ import annotations

import datetime as dt
import gzip
import re
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw" / "iem_afos_cli"
PILS = {"NYC": "CLINYC", "EWR": "CLIEWR", "TTN": "CLITTN", "MDW": "CLIMDW", "MIA": "CLIMIA"}
URL = "https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py"
TZ = {"EDT": -4, "EST": -5, "CDT": -5, "CST": -6}
MONTHS = {m: i for i, m in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}
FULLM = {m: i for i, m in enumerate(["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST",
                                      "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"], 1)}


def pull(years=range(2021, 2027), sleep: float = 1.0) -> None:
    import requests
    RAW.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = "weather-insurance-research/0.1 (read-only)"
    for st, pil in PILS.items():
        for y in years:
            dest = RAW / f"{pil}_{y}.txt.gz"
            if dest.exists():
                continue
            r = s.get(URL, params=dict(pil=pil, sdate=f"{y}-04-30", edate=f"{y}-10-15", limit=9999, fmt="text",
                                       order="asc"), timeout=120)
            r.raise_for_status()
            dest.write_bytes(gzip.compress(r.content))
            print(st, y, len(r.content), flush=True)
            time.sleep(sleep)


_WMO = re.compile(r"^CDUS\d\d\s+K\w{3}\s+(\d{2})(\d{2})(\d{2})(?:\s+(\w{3}))?\s*$", re.M)
_LOCAL = re.compile(r"^\s*(\d{3,4})\s+(AM|PM)\s+(EDT|EST|CDT|CST)\s+\w{3}\s+(\w{3})\s+(\d{1,2})\s+(\d{4})", re.M)
_FOR = re.compile(r"CLIMATE SUMMARY FOR\s+([A-Z]+)\s+(\d{1,2})\s+(\d{4})")
_MAX = re.compile(r"^\s*MAXIMUM\s+(-?\d+|MM)R?\b", re.M)


def parse_products(text: str) -> pd.DataFrame:
    """One row per CLI product: issued_utc, day (local climate date), prelim, tmax, correction."""
    starts = [m.start() for m in _WMO.finditer(text)]
    rows = []
    for a, b in zip(starts, starts[1:] + [len(text)]):
        p = text[a:b]
        w = _WMO.search(p)
        lm = _LOCAL.search(p)
        fm = _FOR.search(p)
        if not (lm and fm):
            continue
        hhmm = lm.group(1).zfill(4)
        hh, mm = int(hhmm[:2]) % 12, int(hhmm[2:])
        if lm.group(2) == "PM":
            hh += 12
        local = dt.datetime(int(lm.group(6)), MONTHS[lm.group(4)], int(lm.group(5)), hh, mm)
        issued = (local - dt.timedelta(hours=TZ[lm.group(3)])).replace(tzinfo=dt.UTC)
        day = dt.date(int(fm.group(3)), FULLM.get(fm.group(1), 0) or 1, int(fm.group(2)))
        prelim = bool(re.search(r"VALID (TODAY )?AS OF", p))
        # the first MAXIMUM after the TEMPERATURE header is the day's high
        tpos = p.find("TEMPERATURE (F)")
        mx = _MAX.search(p, tpos if tpos >= 0 else 0)
        tmax = None
        if mx and mx.group(1) != "MM":
            tmax = int(mx.group(1))
        rows.append(dict(issued_utc=issued, day=pd.Timestamp(day), prelim=prelim, tmax=tmax,
                         correction=(w.group(4) or "") if w else "", corrected_text="CORRECTED" in p[:600]))
    return pd.DataFrame(rows)


def load_all() -> pd.DataFrame:
    out = []
    for st, pil in PILS.items():
        for p in sorted(RAW.glob(f"{pil}_*.txt.gz")):
            df = parse_products(gzip.decompress(p.read_bytes()).decode("latin-1"))
            df["station"] = st
            out.append(df)
    return pd.concat(out, ignore_index=True)


def settlement_vintage(products: pd.DataFrame, n_days: int = 1, hour_utc: int = 12) -> pd.DataFrame:
    """Per (station, day): value of the latest non-preliminary product issued <= D+n 12:00Z, and of
    the latest non-preliminary product in the archive. Never reads a product issued after the cut."""
    f = products[~products["prelim"] & products["tmax"].notna()].copy()
    f["cut"] = f["day"].dt.tz_localize("UTC") + pd.Timedelta(days=n_days, hours=hour_utc)
    f = f.sort_values("issued_utc")
    before = f[f["issued_utc"] <= f["cut"]].groupby(["station", "day"]).last()[["tmax", "issued_utc"]]
    latest = f.groupby(["station", "day"]).last()[["tmax", "issued_utc"]]
    n = f.groupby(["station", "day"]).size().rename("n_final_products")
    j = latest.join(before, lsuffix="_latest", rsuffix="_settle", how="left").join(n)
    return j.reset_index()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "pull":
        pull()
