"""Markout summaries with a moving-block bootstrap CI (04-RESEARCH Pattern 6)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def block_ci(x: np.ndarray, block: int = 7, reps: int = 2000, seed: int = 20260930, q=(2.5, 97.5)) -> tuple[float, float]:
    x = np.asarray(x, float)
    n = len(x)
    if n < block * 2:
        return float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    nb = -(-n // block)
    st = rng.integers(0, n - block + 1, size=(reps, nb))
    idx = (st[:, :, None] + np.arange(block)).reshape(reps, -1)[:, :n]
    m = x[idx].mean(axis=1)
    return float(np.percentile(m, q[0])), float(np.percentile(m, q[1]))


def summarize(daily: pd.Series) -> dict:
    x = daily.sort_index().to_numpy(float)
    if len(x) == 0:
        return {}
    lo, hi = block_ci(x)
    s = np.sort(x)
    roll5 = pd.Series(x).rolling(5).sum().min() if len(x) >= 5 else float("nan")
    roll30 = pd.Series(x).rolling(30).sum().min() if len(x) >= 30 else float("nan")
    cum = np.cumsum(x)
    dd = float((np.maximum.accumulate(cum) - cum).max())
    tot = x.sum()
    worst5 = s[:5].sum()
    return dict(n_days=int(len(x)), mean=float(x.mean()), ci95=[lo, hi], median=float(np.median(x)),
                p10=float(np.percentile(x, 10)), p1=float(np.percentile(x, 1)), worst_day=float(s[0]),
                worst_5day=float(roll5), worst_30day=float(roll30), win_rate=float((x > 0).mean()), total=float(tot),
                max_drawdown=dd, worst_day_over_mean=float(s[0] / x.mean()) if x.mean() != 0 else None,
                share_pnl_from_5_worst_days=float(worst5 / tot) if tot != 0 else None)
