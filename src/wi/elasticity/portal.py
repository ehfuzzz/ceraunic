"""Portal elasticity engine: estimate(sales_rows, weather_rows, priors) -> hedge prescription.

numpy + stdlib only at call time (no pandas, no statsmodels), so the engine API can call it and a
TypeScript port can match it on a fixture. Same design (wi.elasticity.design), same OLS + HAC(7)
(wi.elasticity.fit), same credibility shrinkage (wi.elasticity.shrink) as the EVAL-06 evaluation.

sales_rows:   [{"date": "YYYY-MM-DD", "sales": float}, ...]   one row per business day
weather_rows: [{"date": "YYYY-MM-DD", "tmax_f": float, "prcp_in": float, "snow_in": float}, ...]
              NWS climate-report values at the Kalshi settlement station; must include the day
              before the first sales day (lags). Trace precipitation = 0.0.
priors:       the parsed priors.json (whole file) or one group's entry; pass group="G1" etc. to
              pick from the whole file.

Model by history length n (days with sales): n >= 365 own Fourier(3) + trend; 120 <= n < 365
group seasonal offset + level + trend; n < 120 group seasonal offset + level (PREREG §3).
"""
from __future__ import annotations

import datetime as dt
import math

import numpy as np

from .design import FOURIER_COLS, design, fourier_terms
from .fit import fit_unit
from .shrink import shrink


def _prior_entry(priors: dict, group: str | None) -> dict:
    if "groups" in priors:
        if group is None:
            raise ValueError("pass group= (e.g. 'G1') when giving the whole priors.json")
        return priors["groups"][group]
    return priors


def estimate(sales_rows: list[dict], weather_rows: list[dict], priors: dict, group: str | None = None,
             recent_days: int = 28) -> dict:
    pr = _prior_entry(priors, group)
    K, cap = float(pr["K"]), float(pr["cap"])
    wx = {}
    for r in weather_rows:
        d = dt.date.fromisoformat(str(r["date"])[:10])
        wx[d] = (float(r.get("tmax_f", math.nan)), float(r.get("prcp_in", math.nan)),
                 float(r.get("snow_in", 0.0) if r.get("snow_in") is not None else 0.0))
    rows = sorted(((dt.date.fromisoformat(str(r["date"])[:10]), float(r["sales"])) for r in sales_rows),
                  key=lambda t: t[0])
    one = dt.timedelta(days=1)
    keep = [(d, y) for d, y in rows if y > 0 and d in wx and (d - one) in wx
            and np.isfinite(wx[d][0]) and np.isfinite(wx[d][1])]
    n_rows = len(keep)
    if n_rows < 30:
        raise ValueError(f"need at least 30 sales days with weather, got {n_rows}")
    # history length n = calendar span of the sales history (the evaluation's window length),
    # not the count of usable rows (zero-sales or missing-weather days do not shorten it)
    n = (rows[-1][0] - rows[0][0]).days + 1
    dates = np.array([d for d, _ in keep], dtype="datetime64[D]")
    y = np.array([v for _, v in keep])
    T = np.array([wx[d][0] for d, _ in keep]); P = np.array([wx[d][1] for d, _ in keep])
    S = np.array([wx[d][2] for d, _ in keep])
    Tp = np.array([wx[d - one][0] for d, _ in keep]); Pp = np.array([wx[d - one][1] for d, _ in keep])
    fourier = n >= 365
    t0 = dates[0] if n >= 120 else None
    X, names = design(dates, T, P, S, Tp, Pp, K, cap, t0=t0, fourier=fourier)
    ok = np.isfinite(X).all(1)
    offset = None
    if not fourier:
        g = np.array([float(pr["seasonal_offset"][c]) for c in FOURIER_COLS])
        FT = np.column_stack([fourier_terms(dates)[c] for c in FOURIER_COLS])
        offset = (FT @ g)[ok]
    f = fit_unit(np.log(y[ok]), X[ok], names, offset)
    out = {"n_days": n, "n_rows_fit": n_rows, "K": K, "cap": cap, "model": "own_fourier" if fourier else "group_offset",
           "prior_group": pr.get("gid", group), "prior_learned": bool(pr.get("learned", True))}
    for leg in ("heat", "wet"):
        ident = f["ident"][leg]
        b = f["coef"].get(leg, 0.0) if ident else float("nan")
        s = f["se"].get(leg, float("inf")) if ident else float("inf")
        mu, t2 = float(pr[f"mu_{leg}"]), float(pr[f"tau2_{leg}"])
        bt, B = shrink(np.array([b]), np.array([s]), np.array([mu]), np.array([t2]))
        out[leg] = {"beta_own": None if not ident else float(b), "se_own": None if not ident else float(s),
                    "identified": bool(ident), "prior_mu": mu, "prior_tau2": t2,
                    "beta_shrunk": float(bt[0]), "credibility_B": float(B[0])}
    mode = pr.get("portal_mode", "always_shrink")
    n_star = pr.get("n_star_own")
    use_own = mode == "own_ols_after_n_star" and n_star is not None and n >= n_star
    bh = out["heat"]["beta_own"] if use_own and out["heat"]["identified"] else out["heat"]["beta_shrunk"]
    bw = out["wet"]["beta_own"] if use_own and out["wet"]["identified"] else out["wet"]["beta_shrunk"]
    recent = float(np.mean(y[-recent_days:]))
    out["prescription"] = {
        "mode": mode, "used": "own" if use_own else "shrunk",
        "advisory_only": bool(pr.get("advisory_only", False)),
        "recent_mean_daily_sales": recent,
        "heat_usd_per_degF": recent * (-bh),          # > 0: buy the ladder (short heat); < 0: sell
        "heat_contracts_per_bracket_rule": "q_b = round(heat_usd_per_degF * clip(r_b - K, 0, cap))",
        "rain_contracts": recent * (1 - math.exp(bw)),  # > 0: buy the daily rain YES
    }
    return out
