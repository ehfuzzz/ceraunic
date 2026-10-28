"""Census ZIP Code Business Patterns 2023 detail -> small-business establishment counts.

File: zbp23detail.zip (NAICS 2017 codes; 2,974,116 rows). Size classes n<5 .. n1000; "N" marks a
suppressed cell. Imputation (04-RESEARCH Pattern 1): gap = est - sum(reported), spread over the
suppressed cells at most 2 per cell, remainder to the smallest suppressed class. Keep classes
< 50 employees (midpoints 2.5, 7, 14.5, 34.5).
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

SIZE = ["n<5", "n5_9", "n10_19", "n20_49", "n50_99", "n100_249", "n250_499", "n500_999", "n1000"]
MID = np.array([2.5, 7, 14.5, 34.5, 74.5, 174.5, 374.5, 749.5, 1500.0])
SMALL = 4


def read_detail(path: Path, naics6: set[str]) -> pd.DataFrame:
    """Rows of the ZBP detail file whose naics is in naics6 (all size classes, raw strings)."""
    parts = []
    with zipfile.ZipFile(path) as z:
        with z.open("zbp23detail.txt") as fh:
            for chunk in pd.read_csv(fh, dtype=str, encoding="latin-1", chunksize=400_000,
                                     keep_default_na=False):
                parts.append(chunk[chunk["naics"].isin(naics6)])
    return pd.concat(parts, ignore_index=True)


def impute_sizes(df: pd.DataFrame, method: str = "proportional") -> tuple[np.ndarray, dict]:
    """Return (n_rows x 9) imputed establishment counts per size class, plus totals for the log.

    method="research": 04-RESEARCH rule (equal spread over suppressed cells, <= 2 each, remainder
    to the smallest suppressed class). It sends most suppressed establishments into the 50+ classes
    (CBP employment check ~10x too high), so it is kept only for the deviation log (D2).
    method="proportional" (used): the gap is spread over the row's suppressed cells in proportion
    to the NAICS's national distribution of reported establishments by size class.
    """
    est = df["est"].astype(int).to_numpy()
    size = df[SIZE].replace("N", np.nan).astype(float)
    hidden = size.isna().to_numpy()
    vals = size.fillna(0.0).to_numpy()
    gap = np.clip(est - vals.sum(axis=1), 0, None)
    if method == "research":
        nh = hidden.sum(axis=1)
        per = np.where(nh > 0, np.minimum(2.0, gap / np.where(nh > 0, nh, 1)), 0.0)
        vals = vals + hidden * per[:, None]
        rest = np.clip(est - vals.sum(axis=1), 0, None)
        has = hidden.any(axis=1)
        first = hidden.argmax(axis=1)
        idx = np.flatnonzero(has)
        vals[idx, first[idx]] += rest[idx]
    else:
        rep = pd.DataFrame(vals, columns=SIZE).groupby(df["naics"].to_numpy()).sum()
        share = rep.div(rep.sum(axis=1).replace(0, np.nan), axis=0).fillna(1.0 / len(SIZE))
        w = share.reindex(df["naics"].to_numpy()).to_numpy() * hidden
        ws = w.sum(axis=1)
        # rows whose suppressed classes carry zero national weight: fall back to equal weights
        w = np.where(ws[:, None] > 0, w, hidden.astype(float))
        ws = w.sum(axis=1)
        vals = vals + np.where(ws[:, None] > 0, w / np.where(ws > 0, ws, 1)[:, None], 0.0) * gap[:, None]
    log = dict(rows=int(len(df)), est_total=int(est.sum()), reported_before=float(size.fillna(0).to_numpy().sum()),
               after_imputation=float(vals.sum()), suppressed_cells=int(hidden.sum()))
    return vals, log


def small_business_long(df: pd.DataFrame, vals: np.ndarray) -> tuple[pd.DataFrame, dict]:
    base = df[["zip", "naics", "stabbr", "cty_name"]].reset_index(drop=True)
    rows = []
    for k in range(SMALL):
        part = base.copy()
        part["size"] = SIZE[k]
        part["employees"] = MID[k]
        part["est"] = vals[:, k]
        rows.append(part)
    out = pd.concat(rows, ignore_index=True)
    out = out[out["est"] > 0].reset_index(drop=True)
    total = vals.sum()
    small = vals[:, :SMALL].sum()
    emp_all = (vals * MID[None, :]).sum()
    emp_small = (vals[:, :SMALL] * MID[None, :SMALL]).sum()
    log = dict(est_all_sizes=float(total), est_small=float(small), est_share_dropped=float(1 - small / total) if total else 0.0,
               emp_all_sizes_mid=float(emp_all), emp_share_dropped=float(1 - emp_small / emp_all) if emp_all else 0.0)
    return out, log
