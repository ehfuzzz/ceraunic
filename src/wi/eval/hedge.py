"""Hedge effectiveness and the joint calendar-block bootstrap.

HE_cover  = 1 − var(E − X) / var(E)               (payout vs exposure, price ignored)
HE_ladder = 1 − var(E − (X − π − fee)) / var(E)    (payout net of what was paid at the decision time)
Pooled HE demeans within each group (city): 1 − Σ_g n_g var_g(resid) / Σ_g n_g var_g(E).

Bootstrap: blocks of L consecutive calendar days drawn with replacement over the group's date span; one
weight vector per draw is shared by every city in the pool (joint day blocks), so cross-city correlation on
the same dates is kept. Seed and draws are passed in; the evaluation uses seed 20260930, 2,000 draws, L = 7.
"""
from __future__ import annotations

import math

import numpy as np

# column order of the per-day sufficient statistics
STATS = ("n", "E", "EE", "R1", "R1R1", "R2", "R2R2", "prem", "pay", "fee", "spread")


def he(E: np.ndarray, X: np.ndarray) -> float:
    """1 − var(E − X) / var(E) for one group."""
    E = np.asarray(E, float)
    X = np.asarray(X, float)
    v = np.var(E)
    return float("nan") if len(E) < 2 or v <= 0 else float(1.0 - np.var(E - X) / v)


def day_sums(day: np.ndarray, group: np.ndarray, E, X, prem=None, fee=None, spread=None,
             d0: int | None = None, n_days: int | None = None, groups: list | None = None):
    """Per (group, day) sufficient statistics. Returns (S [G, D, k], groups, d0)."""
    day = np.asarray(day, dtype=np.int64)
    E = np.asarray(E, float)
    X = np.asarray(X, float)
    prem = np.zeros_like(E) if prem is None else np.asarray(prem, float)
    fee = np.zeros_like(E) if fee is None else np.asarray(fee, float)
    spread = np.zeros_like(E) if spread is None else np.asarray(spread, float)
    groups = sorted(set(group)) if groups is None else groups
    d0 = int(day.min()) if d0 is None else d0
    n_days = int(day.max()) - d0 + 1 if n_days is None else n_days
    R1 = E - X
    R2 = E - (X - prem - fee)
    cols = np.stack([np.ones_like(E), E, E * E, R1, R1 * R1, R2, R2 * R2, prem, X, fee, spread], axis=1)
    S = np.zeros((len(groups), n_days, len(STATS)))
    gi = {g: i for i, g in enumerate(groups)}
    gidx = np.array([gi[g] for g in group], dtype=np.int64)
    np.add.at(S, (gidx, day - d0), cols)
    return S, groups, d0


def stats_from_sums(T: np.ndarray) -> dict[str, np.ndarray]:
    """T [..., G, k] group totals → pooled statistics (arrays over the leading dims)."""
    n = T[..., 0]
    with np.errstate(invalid="ignore", divide="ignore"):
        ssE = T[..., 2] - np.where(n > 0, T[..., 1] ** 2 / n, 0.0)
        ss1 = T[..., 4] - np.where(n > 0, T[..., 3] ** 2 / n, 0.0)
        ss2 = T[..., 6] - np.where(n > 0, T[..., 5] ** 2 / n, 0.0)
        N = n.sum(-1)
        sE, s1, s2 = ssE.sum(-1), ss1.sum(-1), ss2.sum(-1)
        prem, pay, fee, spr = T[..., 7].sum(-1), T[..., 8].sum(-1), T[..., 9].sum(-1), T[..., 10].sum(-1)
        return {
            "n": N,
            "he_cover": 1.0 - s1 / sE,
            "he_ladder": 1.0 - s2 / sE,
            "premium": prem / N,
            "payout": pay / N,
            "fee": fee / N,
            "spread": spr / N,
            "overround": prem / pay - 1.0,
            "total_load": (prem + fee) / pay - 1.0,
        }


def block_weights(n_days: int, draws: int, L: int = 7, seed: int = 20260930) -> np.ndarray:
    """[draws, n_days] counts: ceil(n_days / L) blocks of L consecutive days per draw, with replacement."""
    rng = np.random.default_rng(seed)
    L = max(1, min(L, n_days))
    nb = math.ceil(n_days / L)
    starts = rng.integers(0, n_days - L + 1, size=(draws, nb))
    idx = (starts[:, :, None] + np.arange(L)[None, None, :]).reshape(draws, -1)
    W = np.zeros((draws, n_days), dtype=np.int32)
    rows = np.repeat(np.arange(draws), idx.shape[1])
    np.add.at(W, (rows, idx.ravel()), 1)
    return W


def bootstrap(S: np.ndarray, draws: int = 2000, L: int = 7, seed: int = 20260930,
              q: tuple[float, float] = (2.5, 97.5)) -> dict[str, dict[str, float]]:
    """Point estimate + percentile CI for every statistic, from per-(group, day) sums S [G, D, k]."""
    point = stats_from_sums(S.sum(axis=1))
    W = block_weights(S.shape[1], draws, L, seed).astype(float)
    Tb = np.einsum("bd,gdk->bgk", W, S)
    boot = stats_from_sums(Tb)
    out = {}
    for k, v in point.items():
        b = boot[k][np.isfinite(boot[k])]
        lo, hi = (np.percentile(b, q) if len(b) else (np.nan, np.nan))
        out[k] = {"est": float(v), "lo": float(lo), "hi": float(hi)}
    return out
