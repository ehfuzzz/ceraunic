"""OLS with Newey-West (Bartlett, maxlags=7) HAC covariance, numpy only.

Matches statsmodels `OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": 7})` (its default:
no small-sample correction); the eval run checks this on real units and records the max abs
difference in results.json. Rows must be in date order.
"""
from __future__ import annotations

import numpy as np

MAXLAGS = 7
MIN_EVENT_DAYS = 5   # PREREG C9: heat / wet need >= 5 nonzero days to be identified


def select_columns(X: np.ndarray, names: list[str], protect=("const",)) -> list[int]:
    """Indices of columns to keep: drop constant columns, then greedily drop columns that are
    linear combinations of the ones already kept (order = design order)."""
    keep: list[int] = []
    for j, n in enumerate(names):
        col = X[:, j]
        if n not in protect and np.ptp(col) == 0:
            continue
        trial = keep + [j]
        if np.linalg.matrix_rank(X[:, trial], tol=1e-8 * max(1.0, np.abs(X[:, trial]).max())) == len(trial):
            keep = trial
    return keep


def hac_meat(Xe: np.ndarray, maxlags: int = MAXLAGS) -> np.ndarray:
    S = Xe.T @ Xe
    for lag in range(1, maxlags + 1):
        w = 1.0 - lag / (maxlags + 1.0)
        G = Xe[lag:].T @ Xe[:-lag]
        S += w * (G + G.T)
    return S


def ols_hac(y: np.ndarray, X: np.ndarray, maxlags: int = MAXLAGS) -> dict:
    n, k = X.shape
    XtX_inv = np.linalg.inv(X.T @ X)
    beta = XtX_inv @ (X.T @ y)
    resid = y - X @ beta
    S = hac_meat(X * resid[:, None], maxlags)
    cov = XtX_inv @ S @ XtX_inv          # statsmodels default: no small-sample correction
    return {"beta": beta, "cov": cov, "resid": resid, "n": n, "k": k,
            "ssr": float(resid @ resid)}


def ssr_only(y: np.ndarray, X: np.ndarray) -> float:
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ beta
    return float(r @ r)


def fit_unit(ly: np.ndarray, X: np.ndarray, names: list[str], offset: np.ndarray | None = None) -> dict:
    """Fit one unit on its estimation rows. ly = log sales (finite rows only). Returns the
    coefficient dict, standard errors, identification flags and the fit object."""
    yy = ly if offset is None else ly - offset
    keep = select_columns(X, names)
    Xk = X[:, keep]
    kn = [names[j] for j in keep]
    f = ols_hac(yy, Xk)
    se = np.sqrt(np.clip(np.diag(f["cov"]), 0, None))
    coef = dict(zip(kn, f["beta"]))
    ses = dict(zip(kn, se))
    ident = {}
    for leg, col in (("heat", "heat"), ("wet", "wet")):
        j = names.index(col)
        ident[leg] = bool(col in coef and np.count_nonzero(X[:, j]) >= MIN_EVENT_DAYS)
    return {"coef": coef, "se": ses, "ident": ident, "keep": kn, "resid": f["resid"],
            "n": f["n"], "k": f["k"], "ssr": f["ssr"]}
