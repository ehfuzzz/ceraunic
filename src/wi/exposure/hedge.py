"""Prior exposure -> signed hedge units on the $1/degF capped heat cover (04-RESEARCH Pattern 2).

exposure_i(T) = daily_rev_i * e_T/100 * max(T - T0, 0)   (linear daily_rev*e_T/100*T when T0 is "—")
h_i = -slope of the min-variance regression of exposure on H(T;K) over 1951-2020 warm-season days
of the station, per calendar month, K from the forecast-proxy rule. Because exposure is linear in
daily_rev*e_T, h_i = -(daily_rev_i * e_T/100) * w[station, month, T0] with
w = Cov(max(T-T0,0), H) / Var(H). Positive h = buys heat cover (bid on H).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def unit_weights(days: dict[str, pd.DataFrame], t0_values: list[float]) -> pd.DataFrame:
    """w per (station, month, T0) from proxy days (columns T, H; DatetimeIndex)."""
    rows = []
    for st, d in days.items():
        for mo, g in d.groupby(d.index.month):
            Hh = g["H"].to_numpy(float)
            vH = Hh.var(ddof=1)
            for t0 in t0_values:
                x = g["T"].to_numpy(float) if np.isnan(t0) else np.maximum(g["T"].to_numpy(float) - t0, 0.0)
                w = float(np.cov(x, Hh, ddof=1)[0, 1] / vH) if vH > 0 else 0.0
                rows.append(dict(station=st, month=int(mo), T0=t0, w=w, n_days=len(g)))
    return pd.DataFrame(rows)


def signed_units(daily_rev: np.ndarray, e_T: np.ndarray, w: np.ndarray) -> np.ndarray:
    return -(daily_rev * e_T / 100.0) * w
