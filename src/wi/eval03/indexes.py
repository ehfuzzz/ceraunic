"""Index formulas for the Phase 3 designs (03-RESEARCH Patterns 1-3).

Every index takes a value panel (rows = evaluation units, i.e. calendar days or Mon-Sun weeks; columns =
stations, cells or counties) and returns one series. Nothing here looks at the held-out point b unless the
caller passes it, and every fitted object records the dates it was fitted on.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def round_half_up(x):
    """Integer rounding used for every settlement-style value (CLI publishes whole degF)."""
    return np.floor(np.asarray(x, float) + 0.5)


def H_temp(T, K, cap: float = 6.0, rounded: bool = True, linear: bool = False):
    """ins1 heat cover, $ per $1/degF unit: min(max(round(T) - K, 0), cap). NaN in -> NaN out.
    linear=True is the 'linear uncapped' sensitivity: T - K."""
    T = np.asarray(T, float)
    K = np.asarray(K, float)
    x = round_half_up(T) if rounded else T
    if linear:
        return x - K
    return np.clip(x - K, 0.0, cap)


def H_rain(R, cap: float = 3.0, rounded: bool = True):
    """Capped weekly total in inches, rounded to 0.01 in (NaN passes through)."""
    R = np.asarray(R, float)
    x = np.floor(R * 100 + 0.5) / 100 if rounded else R
    return np.minimum(x, cap)


def wet(R):
    """Daily wet-day indicator, >= 0.01 in (trace 0.0001 is dry), NaN passes through."""
    R = np.asarray(R, float)
    out = (np.floor(R * 100 + 0.5) >= 1).astype(float)
    out[np.isnan(R)] = np.nan
    return out


def network_mean(X: pd.DataFrame, members: list[str], exclude: str | None = None, quorum: float = 0.6) -> pd.Series:
    """Equal-weight mean over members minus the held-out point; NaN where fewer than ceil(quorum * n) present."""
    cols = [j for j in members if j != exclude and j in X.columns]
    if not cols:
        return pd.Series(np.nan, index=X.index)
    Y = X[cols]
    ok = Y.notna().sum(axis=1) >= int(math.ceil(quorum * len(cols) - 1e-9))
    return Y.mean(axis=1, skipna=True).where(ok)


def weighted_index(X: pd.DataFrame, w: pd.Series, quorum: float = 0.6) -> pd.Series:
    """sum_j w_j X_j / sum_{j present} w_j; NaN where fewer than ceil(quorum * n_{w>0}) inputs present."""
    w = w[w > 0]
    Y = X[list(w.index)]
    present = Y.notna()
    num = (Y.fillna(0.0) * w.values).sum(axis=1)
    den = (present * w.values).sum(axis=1)
    ok = present.sum(axis=1) >= int(math.ceil(quorum * len(w) - 1e-9))
    return (num / den.where(den > 0)).where(ok)


def haversine(a: tuple[float, float], b: tuple[float, float]) -> float:
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(h))


def nearest(candidates: list[str], coords: dict, target: str, k: int = 1) -> list[tuple[str, float]]:
    """k nearest candidates to target (ties broken by code, so the choice is deterministic)."""
    d = sorted((haversine(coords[c], coords[target]), c) for c in candidates if c != target)
    return [(c, dist) for dist, c in d[:k]]


def idw_weights(candidates: list[str], coords: dict, target: str, k: int = 3, p: float = 2.0) -> pd.Series:
    """IDW (power p) over the k nearest candidates; weights sum to 1; geometry only, no data."""
    nn = nearest(candidates, coords, target, k)
    w = pd.Series({c: 1.0 / max(dist, 1e-6) ** p for c, dist in nn})
    return w / w.sum()


def fit_pc1(X: pd.DataFrame, s: pd.Series, fit_start: str, fit_end: str) -> dict:
    """Frozen PC1 weights (03-RESEARCH Pattern 2). X: units x inputs (held-out point already removed by the
    caller), s: the station/cell S on the same units. Only rows inside [fit_start, fit_end] are used; rows
    with any missing input are dropped. Returns the clipped, normalised weights and the fit dates used."""
    idx = X.index[(X.index >= pd.Timestamp(fit_start)) & (X.index <= pd.Timestamp(fit_end))]
    cols = list(X.columns)
    # an input with < 50 % train coverage cannot be fitted: it gets weight 0 (deviation logged 2026-09-30)
    fitted = [c for c in cols if X.loc[idx, c].notna().mean() >= 0.5] if len(idx) else []
    R = X.loc[idx, fitted].sub(s.loc[idx], axis=0)
    R = R.dropna(how="any")
    if len(R) < max(10, 2) or R.shape[1] == 0:
        return {"w": pd.Series(1.0 / len(cols), index=cols), "share": float("nan"), "n_fit": int(len(R)),
                "fit_first": None, "fit_last": None, "fallback": "equal"}
    if R.shape[1] == 1:
        v, share = np.array([1.0]), 1.0
    else:
        vals, vecs = np.linalg.eigh(np.cov(R.to_numpy(), rowvar=False))
        v = vecs[:, -1]
        v = v if v.sum() > 0 else -v
        share = float(vals[-1] / vals.sum()) if vals.sum() > 0 else float("nan")
    w = np.clip(v, 0.0, None)
    w = w / w.sum() if w.sum() > 0 else np.full(len(fitted), 1.0 / len(fitted))
    w = pd.Series(w, index=fitted).reindex(cols).fillna(0.0)
    return {"w": w, "share": share, "n_fit": int(len(R)),
            "fit_first": R.index.min().strftime("%Y-%m-%d"), "fit_last": R.index.max().strftime("%Y-%m-%d"),
            "fallback": None}


def disc_weights(lat: np.ndarray, dist: np.ndarray, radius_km: float) -> np.ndarray:
    """cos-latitude weights for the cells within radius_km (0 outside)."""
    w = np.cos(np.radians(lat)) * (dist <= radius_km)
    return w / w.sum() if w.sum() > 0 else w


def disc_mean(G: pd.DataFrame, lat: np.ndarray, dist: np.ndarray, radius_km: float, quorum: float = 0.6) -> pd.Series:
    w = pd.Series(disc_weights(lat, dist, radius_km), index=G.columns)
    return weighted_index(G, w, quorum)


def fit_beta(u: np.ndarray, r: np.ndarray) -> float:
    m = ~(np.isnan(u) | np.isnan(r))
    if m.sum() < 3 or np.var(r[m]) <= 0:
        return float("nan")
    return float(np.cov(u[m], r[m], bias=True)[0, 1] / np.var(r[m]))


def fit_beta_train(u: np.ndarray, r: np.ndarray, index: pd.DatetimeIndex, train_mask: np.ndarray) -> dict:
    """Sized-overlay sensitivity: beta = Cov(u, r)/Var(r) on the train units only, with the dates it used."""
    m = np.asarray(train_mask, bool) & ~(np.isnan(u) | np.isnan(r))
    beta = fit_beta(np.where(m, u, np.nan), np.where(m, r, np.nan))
    used = index[m]
    return {"beta": beta, "fit_first": used.min().strftime("%Y-%m-%d") if len(used) else None,
            "fit_last": used.max().strftime("%Y-%m-%d") if len(used) else None}
