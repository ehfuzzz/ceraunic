"""Revenue scale: SUSB 2022 receipts per employee (state x NAICS6, all enterprise sizes).

daily_rev = RCPT*1000/EMPL x size-class midpoint / 365. National row (STATE 00) where the state row
is missing, zero, or has no employment.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

FIPS = {"01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE", "11": "DC",
        "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY",
        "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT",
        "31": "NE", "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH",
        "40": "OK", "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT",
        "50": "VT", "51": "VA", "53": "WA", "54": "WV", "55": "WI", "56": "WY"}


def receipts_per_employee(path: Path, naics6: set[str]) -> pd.DataFrame:
    s = pd.read_csv(path, dtype=str, encoding="latin-1")
    s = s[(s["ENTRSIZE"] == "01") & s["NAICS"].isin(naics6)].copy()
    s["RCPT"] = pd.to_numeric(s["RCPT"], errors="coerce").fillna(0)
    s["EMPL"] = pd.to_numeric(s["EMPL"], errors="coerce").fillna(0)
    s["rpe"] = (s["RCPT"] * 1000.0 / s["EMPL"]).where((s["RCPT"] > 0) & (s["EMPL"] > 0))
    nat = s[s["STATE"] == "00"].set_index("NAICS")["rpe"]
    st = s[s["STATE"] != "00"].copy()
    st["stabbr"] = st["STATE"].map(FIPS)
    st = st.dropna(subset=["stabbr"])[["stabbr", "NAICS", "rpe"]].rename(columns={"NAICS": "naics"})
    return st, nat.rename("rpe_nat")


def attach_revenue(pop: pd.DataFrame, st: pd.DataFrame, nat: pd.Series) -> pd.DataFrame:
    out = pop.merge(st, on=["stabbr", "naics"], how="left")
    out = out.merge(nat, left_on="naics", right_index=True, how="left")
    out["rpe_source"] = "state"
    miss = out["rpe"].isna()
    out.loc[miss, "rpe_source"] = "national"
    out.loc[miss, "rpe"] = out.loc[miss, "rpe_nat"]
    out["daily_rev"] = out["rpe"] * out["employees"] / 365.0
    return out.drop(columns=["rpe_nat"])
