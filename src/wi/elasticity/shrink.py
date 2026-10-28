"""Empirical-Bayes priors and credibility shrinkage (numpy closed forms).

DerSimonian-Laird ("chi2" in statsmodels.combine_effects) is primary, Paule-Mandel ("iterated")
the sensitivity. tau2 is truncated at 0 (statsmodels' combine_effects can return a small negative
DL tau2; the truncation is the textbook estimator). The eval run compares these closed forms with
combine_effects on real data and records the difference in results.json.

beta_tilde_i = mu + B_i (beta_i - mu), B_i = tau2 / (tau2 + s_i^2)   (Buhlmann credibility)
Units with s = inf (coefficient not identified) get B = 0 -> mu, and never enter a prior.
"""
from __future__ import annotations

import numpy as np


def dl(b: np.ndarray, v: np.ndarray) -> dict:
    b, v = np.asarray(b, float), np.asarray(v, float)
    ok = np.isfinite(b) & np.isfinite(v) & (v > 0)
    b, v = b[ok], v[ok]
    k = len(b)
    if k == 0:
        return {"mu": np.nan, "tau2": np.nan, "se_mu": np.nan, "k": 0}
    w = 1 / v
    mu_fe = (w * b).sum() / w.sum()
    Q = (w * (b - mu_fe) ** 2).sum()
    denom = w.sum() - (w ** 2).sum() / w.sum()
    tau2 = max(0.0, (Q - (k - 1)) / denom) if k > 1 and denom > 0 else 0.0
    ws = 1 / (v + tau2)
    mu = (ws * b).sum() / ws.sum()
    return {"mu": float(mu), "tau2": float(tau2), "se_mu": float(np.sqrt(1 / ws.sum())), "k": int(k)}


def pm(b: np.ndarray, v: np.ndarray, tol: float = 1e-12, maxit: int = 200) -> dict:
    """Paule-Mandel: tau2 solving sum w*(b - mu_w)^2 = k - 1 with w = 1/(v + tau2)."""
    b, v = np.asarray(b, float), np.asarray(v, float)
    ok = np.isfinite(b) & np.isfinite(v) & (v > 0)
    b, v = b[ok], v[ok]
    k = len(b)
    if k < 2:
        return dl(b, v)

    def f(t):
        w = 1 / (v + t)
        mu = (w * b).sum() / w.sum()
        return (w * (b - mu) ** 2).sum() - (k - 1)

    if f(0.0) <= 0:
        tau2 = 0.0
    else:
        lo, hi = 0.0, max(1e-12, np.var(b) * 10 + v.max())
        while f(hi) > 0:
            hi *= 2
        for _ in range(maxit):
            mid = (lo + hi) / 2
            if f(mid) > 0:
                lo = mid
            else:
                hi = mid
            if hi - lo < tol * max(1.0, hi):
                break
        tau2 = (lo + hi) / 2
    w = 1 / (v + tau2)
    mu = (w * b).sum() / w.sum()
    return {"mu": float(mu), "tau2": float(tau2), "se_mu": float(np.sqrt(1 / w.sum())), "k": int(k)}


def loo_priors(b: np.ndarray, v: np.ndarray, method: str = "dl",
               pool_b: np.ndarray | None = None, pool_v: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Leave-one-out prior (mu_-i, tau2_-i) for every unit i.
    pool_b/pool_v (default b, v) are the estimates the prior is built from (e.g. n = 365 fits
    when the unit's own estimate uses n < 365); unit i is left out of the pool by index."""
    pb = np.asarray(b if pool_b is None else pool_b, float)
    pv = np.asarray(v if pool_v is None else pool_v, float)
    n = len(pb)
    mus, taus = np.empty(n), np.empty(n)
    est = dl if method == "dl" else pm
    if method == "dl":
        ok = np.isfinite(pb) & np.isfinite(pv) & (pv > 0)
        w = np.where(ok, 1 / np.where(ok, pv, 1), 0.0)
        bb = np.where(ok, pb, 0.0)
        S1, S2, Sb, Sbb = w.sum(), (w ** 2).sum(), (w * bb).sum(), (w * bb ** 2).sum()
        K = ok.sum()
        for i in range(n):
            wi = w[i]
            s1, s2, sb, sbb = S1 - wi, S2 - wi ** 2, Sb - wi * bb[i], Sbb - wi * bb[i] ** 2
            k = K - (1 if ok[i] else 0)
            if k < 1 or s1 <= 0:
                mus[i], taus[i] = np.nan, np.nan
                continue
            Q = sbb - sb ** 2 / s1
            denom = s1 - s2 / s1
            t2 = max(0.0, (Q - (k - 1)) / denom) if k > 1 and denom > 0 else 0.0
            m = ok.copy()
            m[i] = False
            ws = 1 / (pv[m] + t2)
            mus[i] = (ws * pb[m]).sum() / ws.sum()
            taus[i] = t2
        return mus, taus
    for i in range(n):
        m = np.ones(n, bool)
        m[i] = False
        r = est(pb[m], pv[m])
        mus[i], taus[i] = r["mu"], r["tau2"]
    return mus, taus


def shrink(b: np.ndarray, se: np.ndarray, mu: np.ndarray, tau2: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Credibility-weighted estimate and weight B. se = inf or b = nan -> B = 0 (prior mean)."""
    b = np.asarray(b, float)
    se = np.asarray(se, float)
    v = np.where(np.isfinite(se), se ** 2, np.inf)
    with np.errstate(invalid="ignore", divide="ignore"):
        B = np.where(np.isfinite(v) & np.isfinite(b), tau2 / (tau2 + v), 0.0)
    B = np.where(np.isnan(B), 0.0, B)
    bt = mu + B * (np.where(np.isfinite(b), b, 0.0) - mu)
    return bt, B
