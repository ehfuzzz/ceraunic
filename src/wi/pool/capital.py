"""Pool capital on long-history scenarios (04-RESEARCH Pattern 4; PREREG "Capital rule").

pnl matrix: rows = warm seasons, columns = May 1 .. Sep 30 (153 days), value = the book's P&L on
that historical date with every station taken from the same date (joint dates keep common shocks).
C_h = min(FC_h, max(ES99(bootstrap h-day loss), max historical h-day window loss)).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SEASON = pd.date_range("2001-05-01", "2001-09-30").strftime("%m-%d")


def es(losses: np.ndarray, alpha: float = 0.99) -> float:
    """Expected shortfall (mean of the worst (1-alpha) share, fractional tail weight)."""
    x = np.sort(np.asarray(losses, dtype=float))[::-1]
    k = len(x) * (1 - alpha)
    m = int(np.floor(k))
    if k <= 0:
        return float(x[0])
    tail = x[:m].sum() + (k - m) * (x[m] if m < len(x) else 0.0)
    return float(tail / k)


def var(losses: np.ndarray, alpha: float = 0.99) -> float:
    return float(np.quantile(np.asarray(losses, float), alpha))


def season_matrix(series: pd.Series, years: list[int]) -> np.ndarray:
    """(n_years, 153) matrix of a daily series; missing days -> NaN."""
    s = series.copy()
    idx = pd.MultiIndex.from_arrays([s.index.year, s.index.strftime("%m-%d")])
    s.index = idx
    s = s[~s.index.duplicated()]
    out = np.full((len(years), len(SEASON)), np.nan)
    for i, y in enumerate(years):
        try:
            row = s.loc[y].reindex(SEASON)
        except KeyError:
            continue
        out[i] = row.to_numpy(float)
    return out


def h_day_losses(pnl: np.ndarray, H: int, block: int = 7, reps: int = 10_000, seed: int = 20260930):
    """Historical overlapping-window losses and joint-date block-bootstrap losses of an H-day
    rolled book. pnl: (n_years, n_days)."""
    rng = np.random.default_rng(seed)
    ny, nd = pnl.shape
    hist = -np.stack([pnl[:, s:s + H].sum(axis=1) for s in range(nd - H + 1)], axis=1).ravel()
    nb = -(-H // block)
    y = rng.integers(0, ny, size=(reps, nb))
    st = rng.integers(0, nd - block + 1, size=(reps, nb))
    paths = np.concatenate([pnl[y[:, b, None], st[:, b, None] + np.arange(block)] for b in range(nb)], axis=1)
    boot = -paths[:, :H].sum(axis=1)
    return hist, boot


def capital(pnl: np.ndarray, H: int, fc_per_day: float, block: int = 7, reps: int = 10_000, seed: int = 20260930) -> dict:
    hist, boot = h_day_losses(pnl, H, block, reps, seed)
    es99, es95 = es(boot, 0.99), es(boot, 0.95)
    worst = float(hist.max())
    fc = H * fc_per_day
    c = min(fc, max(es99, worst, 0.0))
    return dict(H=H, C=c, ES99=es99, VaR99=var(boot, 0.99), ES95_junior=min(es95, c), worst_window=worst, FC=fc,
                binding=("FC" if c == fc else ("worst_window" if worst >= es99 else "ES99")),
                p_loss_gt_junior=float(np.mean(boot > min(es95, c))), p_loss_gt_C=float(np.mean(boot > c)),
                p_hist_gt_C=float(np.mean(hist > c)), n_hist_windows=int(len(hist)), n_seasons=int(pnl.shape[0]))


def co_es(unit_paths: np.ndarray, book_paths: np.ndarray, alpha: float = 0.99) -> np.ndarray:
    """Euler co-ES: mean loss of +1 unit of each contract in the book's worst (1-alpha) paths.
    unit_paths: (n_paths, n_contracts) P&L of one unit held over the horizon; book_paths: (n_paths,)."""
    n_tail = max(1, int(len(book_paths) * (1 - alpha)))
    tail = np.argsort(book_paths)[:n_tail]
    return -unit_paths[tail].mean(axis=0)


def kupiec(n: int, x: int, p: float = 0.01) -> dict:
    """Kupiec POF likelihood-ratio test (two-sided), chi2(1) at 5 % = 3.841."""
    from scipy.stats import chi2
    if n == 0:
        return dict(n=0, x=0, LR=float("nan"), p_value=float("nan"), rejected=False)
    ph = x / n
    ll0 = (n - x) * np.log(1 - p) + x * np.log(p)
    ll1 = ((n - x) * np.log(1 - ph) if x < n else 0.0) + (x * np.log(ph) if x > 0 else 0.0)
    LR = float(-2 * (ll0 - ll1))
    return dict(n=n, x=x, expected=n * p, LR=LR, p_value=float(1 - chi2.cdf(LR, 1)), rejected=bool(LR >= 3.841),
                direction=("too many exceedances (under-reserves)" if x > n * p else "too few exceedances (conservative)"))
