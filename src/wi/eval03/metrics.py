"""Metrics for EVAL-02 / EVAL-03: HE, dHE, beta, eta, sd(r), concentration kappa, loading L, and the joint
circular block bootstrap (03-RESEARCH Pattern 4 and "Inference").

HE uses wi.eval.hedge.he (Phase 2). The circular block resampler is new here: Phase 2's block_weights
draws non-circular blocks; the Phase 3 pre-registration asks for circular ones.
"""
from __future__ import annotations

import math

import numpy as np

from wi.eval.hedge import he

STAT_COLS = 7  # m, e, e2, u, u2, c, c2


def point_stats(E: np.ndarray, HS: np.ndarray, r: np.ndarray, mask: np.ndarray) -> dict:
    """Test-window statistics for one (pair, design); days with any missing input are dropped."""
    m = mask & ~(np.isnan(E) | np.isnan(HS) | np.isnan(r))
    e, h, rr = E[m], HS[m], r[m]
    n = int(m.sum())
    out = {"n": n, "n_pay": int((e > 0).sum()), "var_E": float(np.var(e)) if n else float("nan")}
    if n < 3 or np.var(e) <= 0:
        out.update(he=float("nan"), he0=float("nan"), dhe=float("nan"), beta=float("nan"), eta=float("nan"),
                   sd_r=float(np.std(rr)) if n else float("nan"), mean_r=float(np.mean(rr)) if n else float("nan"))
        return out
    u = e - h
    he1, he0 = he(e, h + rr), he(e, h)
    vr = float(np.var(rr))
    beta = float(np.cov(u, rr, bias=True)[0, 1] / vr) if vr > 0 else float("nan")
    out.update(he=he1, he0=he0, dhe=he1 - he0, beta=beta, eta=2 * beta - 1 if vr > 0 else float("nan"),
               sd_r=math.sqrt(vr), mean_r=float(np.mean(rr)))
    return out


def stat_columns(E, HS, r, mask) -> np.ndarray:
    """Per-unit sufficient statistics [U, 7] (zeros where the unit is not used)."""
    m = mask & ~(np.isnan(E) | np.isnan(HS) | np.isnan(r))
    e = np.where(m, E, 0.0)
    u = np.where(m, E - HS, 0.0)
    c = np.where(m, E - HS - r, 0.0)
    return np.stack([m.astype(float), e, e * e, u, u * u, c, c * c], axis=1)


def circular_block_counts(n_units: int, draws: int, block: int, seed: int) -> np.ndarray:
    """[draws, n_units] resample counts: ceil(n/block) circular blocks per draw, starts uniform on 0..n-1."""
    rng = np.random.default_rng(seed)
    nb = math.ceil(n_units / block)
    starts = rng.integers(0, n_units, size=(draws, nb))
    idx = ((starts[:, :, None] + np.arange(block)[None, None, :]) % n_units).reshape(draws, -1)[:, :n_units]
    W = np.zeros((draws, n_units), dtype=np.float64)
    rows = np.repeat(np.arange(draws), n_units)
    np.add.at(W, (rows, idx.ravel()), 1.0)
    return W


def he_from_sums(T: np.ndarray) -> dict:
    """T [..., 7] weighted sums -> he, he0 (same units), dhe."""
    n = T[..., 0]
    with np.errstate(invalid="ignore", divide="ignore"):
        vE = T[..., 2] / n - (T[..., 1] / n) ** 2
        vu = T[..., 4] / n - (T[..., 3] / n) ** 2
        vc = T[..., 6] / n - (T[..., 5] / n) ** 2
        ok = (n >= 3) & (vE > 1e-12)
        he1 = np.where(ok, 1 - vc / vE, np.nan)
        he0 = np.where(ok, 1 - vu / vE, np.nan)
    return {"he": he1, "he0": he0, "dhe": he1 - he0}


def concentration(rs: list[np.ndarray]) -> dict:
    """kappa = Var(sum r_b) / (sum sd(r_b))^2 and the ins2 ratio Var(sum)/sum Var, on units where all are present."""
    if not rs:
        return {"kappa": float("nan"), "ins2_ratio": float("nan"), "n_units": 0}
    R = np.stack(rs, axis=1)
    R = R[~np.isnan(R).any(axis=1)]
    if len(R) < 3:
        return {"kappa": float("nan"), "ins2_ratio": float("nan"), "n_units": int(len(R))}
    sds = R.std(axis=0)
    tot = R.sum(axis=1).var()
    den = sds.sum() ** 2
    sv = (sds ** 2).sum()
    ok = sds > 0
    if ok.sum() >= 2:
        C = np.corrcoef(R[:, ok], rowvar=False)
        iu = np.triu_indices(len(C), 1)
        mpc = float(np.mean(C[iu]))
    else:
        mpc = float("nan")
    return {"kappa": float(tot / den) if den > 0 else float("nan"),
            "ins2_ratio": float(tot / sv) if sv > 0 else float("nan"), "mean_pair_corr": mpc, "n_units": int(len(R))}


def pct_ci(x: np.ndarray, q=(2.5, 97.5)) -> list[float]:
    x = x[np.isfinite(x)]
    if not len(x):
        return [float("nan"), float("nan")]
    lo, hi = np.percentile(x, q)
    return [float(lo), float(hi)]
