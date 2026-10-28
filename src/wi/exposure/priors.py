"""Frozen sector priors (reports/eval-04-05/priors_2026-09-30.csv, sha256 in PREREG.md)."""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
PRIORS = ROOT / "reports" / "eval-04-05" / "priors_2026-09-30.csv"
PRIORS_SHA256 = "7c5de5b1f1d0bf353a39fb3f028cb532ce2954ef9cdf801a25921ad40cdf4b00"

PERSIST_W = {"high": 1.5, "medium": 1.0, "low–medium": 0.75, "low": 0.5, "—": 1.0}


def persistence_class(s: str) -> str:
    s = str(s).strip()
    for k in ("low–medium", "high", "medium", "low"):
        if s.startswith(k):
            return k
    return "—"


def load_priors(check_hash: bool = True) -> pd.DataFrame:
    raw = PRIORS.read_bytes()
    if check_hash and hashlib.sha256(raw).hexdigest() != PRIORS_SHA256:
        raise RuntimeError("priors file changed after pre-registration; log a deviation first")
    p = pd.read_csv(PRIORS, dtype={"naics_expanded": str})
    p["T0"] = pd.to_numeric(p["T0_F"], errors="coerce")   # "—" -> NaN = linear exposure
    p["pclass"] = p["persistence"].map(persistence_class)
    return p


def naics_map(p: pd.DataFrame) -> pd.DataFrame:
    """One row per NAICS6 code -> prior row (ZBP rows only; the demo row has no code)."""
    rows = []
    for _, r in p.dropna(subset=["naics_expanded"]).iterrows():
        for code in str(r["naics_expanded"]).split(";"):
            rows.append(dict(naics=code.strip(), row_id=int(r["row_id"])))
    return pd.DataFrame(rows)


def triangular_draws(p: pd.DataFrame, col: str, n: int, seed: int = 20260930) -> np.ndarray:
    """(n, n_rows) triangular(low, central, high) draws, sectors independent, fixed seed."""
    rng = np.random.default_rng(seed)
    lo = p[f"{col}_low"].to_numpy(float)
    mo = p[f"{col}_central"].to_numpy(float)
    hi = p[f"{col}_high"].to_numpy(float)
    out = np.empty((n, len(p)))
    for j in range(len(p)):
        if hi[j] == lo[j]:
            out[:, j] = mo[j]
        else:
            out[:, j] = rng.triangular(lo[j], mo[j], hi[j], size=n)
    return out
