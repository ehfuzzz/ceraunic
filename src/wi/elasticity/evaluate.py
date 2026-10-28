"""EVAL-06 evaluation core: eligibility, K profile, per-unit fits, EB arms, baseline F/U,
hedge legs, HE_cover / HE_ladder with a joint moving-block bootstrap.

Point-in-time rule: every fitted object (scale, K, fits, priors, climatology, F) is computed from
rows strictly before the origin. The only hedge-window inputs are the scoring series (y, weather,
Kalshi quotes/results) and, for A4 (oracle, a bound), the fit on the scored days. Eligibility
(PREREG §1) looks at activity through origin + 365, as pre-registered (a survivorship caveat).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field, replace

import numpy as np
import pandas as pd

from . import design as D
from .fit import MIN_EVENT_DAYS, fit_unit, select_columns, ssr_only
from .hedge import DayLadder, DayRain, day_ladder, day_rain, ladder_leg, rain_leg
from .panel import GROUPS, Panel, weather_series
from .shrink import dl, loo_priors, pm, shrink

K_GRID = tuple(range(75, 93))
N_GRID = (30, 60, 90, 120, 180, 270, 365, 545, 730)
BOOT_DRAWS = 2000
BLOCK = 7
SEED = 20260930
SCALE_TARGET = 1500.0


@dataclass(frozen=True)
class Cfg:
    cap: float = 10.0
    target: str = "log"          # log | level | ppml
    thin: bool = False
    horizon: int = 24
    exclude_susp: bool = False
    eb: str = "dl"               # dl | pm
    depth_cap: int | None = None
    placebo_year: int | None = None
    boot: int = BOOT_DRAWS


# ----------------------------------------------------------------------------- weather helpers

def wx_arrays(station: str, dates: np.ndarray, placebo_year: int | None = None) -> dict:
    """Weather for each date (and the previous calendar day). Placebo: same month-day of another
    year (Feb 29 -> Feb 28)."""
    w = weather_series(station)
    ds = pd.to_datetime(dates)
    if placebo_year is not None:
        md = [(d.month, 28 if (d.month == 2 and d.day == 29) else d.day) for d in ds]
        ds = pd.to_datetime([dt.date(placebo_year, m, dd) for m, dd in md])
    prev = ds - pd.Timedelta(days=1)
    return {"tmax": w["tmax_f"].reindex(ds).values, "prcp": w["prcp_in"].reindex(ds).values,
            "snow": w["snow_in"].reindex(ds).values, "tmax_prev": w["tmax_f"].reindex(prev).values,
            "prcp_prev": w["prcp_in"].reindex(prev).values}


def climatology(station: str, dates: np.ndarray, origin: np.datetime64, K: float, cap: float) -> dict:
    """E_clim of every weather design column for each date: mean over years origin.year-30 ..
    origin.year-1, calendar days within +/-7 of the day of year (PREREG C2). Pre-origin only."""
    w = weather_series(station)
    idx = w.index
    oy = pd.Timestamp(origin).year
    years = range(oy - 30, oy)
    terms = D.weather_terms(w["tmax_f"].values, w["prcp_in"].values, w["snow_in"].values,
                            w["tmax_f"].reindex(idx - pd.Timedelta(days=1)).values,
                            w["prcp_in"].reindex(idx - pd.Timedelta(days=1)).values, K, cap)
    tf = pd.DataFrame(terms, index=idx)
    nan_t = w["tmax_f"].isna().values
    nan_p = w["prcp_in"].isna().values
    for c in ("tlin", "heat", "heat_l1"):
        tf.loc[nan_t, c] = np.nan
    for c in ("wet", "heavy", "wet_l1"):
        tf.loc[nan_p, c] = np.nan
    tf = tf[tf.index < pd.Timestamp(origin)]
    out = {c: np.empty(len(dates)) for c in D.WEATHER_COLS}
    cache: dict[tuple[int, int], np.ndarray] = {}
    for i, d in enumerate(pd.to_datetime(dates)):
        md = (d.month, 28 if (d.month == 2 and d.day == 29) else d.day)
        if md not in cache:
            days = []
            for y in years:
                c0 = pd.Timestamp(dt.date(y, *md))
                days += [c0 + pd.Timedelta(days=k) for k in range(-7, 8)]
            sub = tf.reindex(pd.DatetimeIndex(days))
            cache[md] = sub.mean(skipna=True).values
        vals = cache[md]
        for j, c in enumerate(tf.columns):
            out[c][i] = vals[j]
    out["n_years"] = len(set(tf.index.year) & set(years))
    return out


# ----------------------------------------------------------------------------- fitting

def _hac_var_coef(Xk, A, E, jj, maxlags=7):
    z = Xk @ A[:, jj]
    Zm = z[:, None] * E
    v = (Zm ** 2).sum(0)
    for lag in range(1, maxlags + 1):
        v += 2 * (1 - lag / (maxlags + 1)) * (Zm[lag:] * Zm[:-lag]).sum(0)
    return v


def fit_many(Yfit: np.ndarray, X: np.ndarray, names: list[str], offset: np.ndarray | None = None) -> dict:
    """OLS + HAC(7) for many units sharing the rows of X. Yfit: R x U with NaN where a unit's row
    is excluded (zero sales in log models). Units with no NaN are solved in one batch; the rest
    one by one. Returns full-width coefficient matrix (0 for dropped columns), se for heat and wet
    (inf when dropped / not identified), identification flags and Duan smearing."""
    R, U = Yfit.shape
    P = len(names)
    coef = np.zeros((U, P))
    se = {c: np.full(U, np.inf) for c in ("heat", "wet")}
    ident = {c: np.zeros(U, bool) for c in ("heat", "wet")}
    smear = np.ones(U)
    ssr = np.zeros(U)
    nobs = np.zeros(U, int)
    xok = np.isfinite(X).all(1)
    Yv = Yfit if offset is None else Yfit - offset
    full = np.isfinite(Yv[xok]).all(0)
    j_heat, j_wet = names.index("heat"), names.index("wet")
    if full.any():
        Xc = X[xok]
        keep = select_columns(Xc, names)
        Xk = Xc[:, keep]
        A = np.linalg.inv(Xk.T @ Xk)
        Yc = Yv[xok][:, full]
        Bk = A @ (Xk.T @ Yc)
        E = Yc - Xk @ Bk
        cf = np.zeros((P, Yc.shape[1]))
        cf[keep] = Bk
        coef[full] = cf.T
        for c, j in (("heat", j_heat), ("wet", j_wet)):
            if j in keep:
                v = _hac_var_coef(Xk, A, E, keep.index(j))
                se[c][full] = np.sqrt(np.clip(v, 0, None))
                ident[c][full] = np.count_nonzero(Xc[:, j]) >= MIN_EVENT_DAYS
        smear[full] = np.exp(E).mean(0)
        ssr[full] = (E ** 2).sum(0)
        nobs[full] = Xk.shape[0]
    for u in np.where(~full)[0]:
        rows = xok & np.isfinite(Yv[:, u])
        if rows.sum() < len(names) + 5:
            continue
        f = fit_unit(Yv[rows, u], X[rows], names)
        for c, v in f["coef"].items():
            coef[u, names.index(c)] = v
        for c in ("heat", "wet"):
            if c in f["se"]:
                se[c][u] = f["se"][c]
            ident[c][u] = f["ident"][c]
        smear[u] = np.exp(f["resid"]).mean()
        ssr[u] = f["ssr"]
        nobs[u] = f["n"]
    for c in ("heat", "wet"):
        se[c] = np.where(ident[c], se[c], np.inf)
    return {"coef": coef, "names": names, "se": se, "ident": ident, "smear": smear, "ssr": ssr, "nobs": nobs}


def fit_ppml(Y: np.ndarray, X: np.ndarray, names: list[str]) -> dict:
    import statsmodels.api as sm
    R, U = Y.shape
    P = len(names)
    coef = np.zeros((U, P))
    se = {c: np.full(U, np.inf) for c in ("heat", "wet")}
    xok = np.isfinite(X).all(1)
    keep = select_columns(X[xok], names)
    kn = [names[j] for j in keep]
    for u in range(U):
        rows = xok & np.isfinite(Y[:, u])
        try:
            r = sm.GLM(Y[rows, u], X[rows][:, keep], family=sm.families.Poisson()).fit(
                cov_type="HAC", cov_kwds={"maxlags": 7})
        except Exception:
            continue
        coef[u, keep] = r.params
        for c in ("heat", "wet"):
            if c in kn and np.count_nonzero(X[rows, names.index(c)]) >= MIN_EVENT_DAYS:
                se[c][u] = r.bse[kn.index(c)]
    return {"coef": coef, "names": names, "se": se,
            "ident": {c: np.isfinite(se[c]) for c in se}, "smear": np.ones(U)}


# ----------------------------------------------------------------------------- context

@dataclass
class Ctx:
    gid: str
    origin: np.datetime64
    n_max: int
    cfg: Cfg
    units: np.ndarray
    Ys: np.ndarray              # all panel days x eligible units, scaled
    dates: np.ndarray
    i0: int                     # index of origin in dates
    K: float
    k_profile: dict
    hedge_idx: np.ndarray
    wx_real: dict               # weather over all panel dates
    wx_est: dict                # weather used for fitting (placebo swaps it)
    clim: dict
    fits: dict = field(default_factory=dict)       # n -> fit_many result
    F: np.ndarray | None = None
    U: np.ndarray | None = None
    elig_log: dict = field(default_factory=dict)
    susp: np.ndarray | None = None


def eligibility(p: Panel, origin: np.datetime64, n_max: int) -> tuple[np.ndarray, dict]:
    i0 = int(np.where(p.dates == origin)[0][0])
    a, b = i0 - n_max, i0 + 365
    if a < 0 or b > len(p.dates):
        raise ValueError(f"{p.group.gid}: window {n_max} before {origin} + 365 not in panel "
                         f"({p.dates[0]}..{p.dates[-1]})")
    act = (p.Y[a:b] > 0).mean(0)
    med = np.median(p.CNT[a:i0], axis=0)
    ok_act = act >= 0.98
    ok_vol = med >= p.group.floor
    cand = ok_act & ok_vol
    # level-break diagnostic on the estimation window (PREREG C7)
    Y = p.Y[a:i0][:, cand]
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.log(Y) - np.log(Y.sum(1, keepdims=True))
    r = np.where(np.isfinite(r), r, np.nan)
    rs = pd.DataFrame(r)
    fwd = rs[::-1].rolling(28, min_periods=20).median()[::-1]     # median over [t, t+28)
    back = rs.rolling(28, min_periods=20).median().shift(1)       # median over [t-28, t)
    jump = (fwd - back).abs().max(axis=0).values
    brk = np.zeros(len(cand), bool)
    brk[np.where(cand)[0]] = jump > np.log(2)
    elig = cand & ~brk
    log = {"units_in_panel": int(p.Y.shape[1]), "active_98": int(ok_act.sum()),
           "volume_floor": int((ok_act & ok_vol).sum()), "level_break_excluded": int(brk.sum()),
           "eligible": int(elig.sum()), "window": [str(p.dates[a]), str(p.dates[b - 1])],
           "break_units": list(p.units[brk][:50])}
    return np.where(elig)[0], log


def k_profile(Yl: np.ndarray, dates, wx, K_grid, cap, t0) -> tuple[float, dict]:
    """Group profile SSR over K (full n = 365 model, all eligible units)."""
    out = {}
    for K in K_grid:
        X, names = D.design(dates, wx["tmax"], wx["prcp"], wx["snow"], wx["tmax_prev"], wx["prcp_prev"],
                            K, cap, t0=t0, fourier=True)
        xok = np.isfinite(X).all(1)
        Xc = X[xok]
        keep = select_columns(Xc, names)
        Xk = Xc[:, keep]
        Yc = Yl[xok]
        full = np.isfinite(Yc).all(0)
        tot = 0.0
        if full.any():
            B, *_ = np.linalg.lstsq(Xk, Yc[:, full], rcond=None)
            tot += float(((Yc[:, full] - Xk @ B) ** 2).sum())
        for u in np.where(~full)[0]:
            rr = np.isfinite(Yc[:, u])
            tot += ssr_only(Yc[rr, u], Xk[rr])
        out[int(K)] = tot
    Kbest = min(out, key=out.get)
    return float(Kbest), out


def build_ctx(p: Panel, origin: str, n_max: int, cfg: Cfg, thin_rng=None) -> Ctx:
    o = np.datetime64(origin, "D")
    idx, elog = eligibility(p, o, n_max)
    i0 = int(np.where(p.dates == o)[0][0])
    Y = p.Y[:, idx].astype(float)
    if cfg.thin:
        rng = thin_rng or np.random.default_rng(SEED)
        m = Y[i0 - 365:i0].mean(0)
        pr = np.minimum(1.0, 150.0 / np.maximum(m, 1e-9))
        Y = rng.binomial(np.rint(Y).astype(np.int64), pr[None, :]).astype(float)
    scale = SCALE_TARGET / Y[i0 - 365:i0].mean(0)
    Ys = Y * scale[None, :]
    wx_real = {"tmax": p.tmax, "prcp": p.prcp, "snow": p.snow, "tmax_prev": p.tmax_prev, "prcp_prev": p.prcp_prev}
    wx_est = wx_real if cfg.placebo_year is None else wx_arrays(p.group.station, p.dates, cfg.placebo_year)
    est = slice(i0 - 365, i0)
    Yl = np.log(np.where(Ys[est] > 0, Ys[est], np.nan))
    wsub = {k: v[est] for k, v in wx_est.items()}
    K, prof = k_profile(Yl, p.dates[est], wsub, K_GRID, cfg.cap, t0=p.dates[i0 - 365])
    hedge_idx = np.arange(i0, i0 + 365)
    clim = climatology(p.group.station, p.dates[hedge_idx], o, K, cfg.cap)
    ctx = Ctx(p.group.gid, o, n_max, cfg, p.units[idx], Ys, p.dates, i0, K, prof, hedge_idx,
              wx_real, wx_est, clim, elig_log=elog)
    # suspension / closure flags over the hedge window (PREREG C25)
    tot = pd.Series(Y.sum(1), index=pd.to_datetime(p.dates))
    med = pd.Series(np.nan, index=tot.index)
    for k in range(7):
        s = tot[tot.index.dayofweek == k]
        med.loc[s.index] = s.shift(1).rolling(8, min_periods=4).median()
    ctx.susp = (tot.values < 0.25 * med.values)[hedge_idx]
    return ctx


def design_at(ctx: Ctx, n: int, wx: dict | None = None):
    """Design over the n estimation days before the origin (trend/fourier per PREREG §3)."""
    wx = ctx.wx_est if wx is None else wx
    rows = slice(ctx.i0 - n, ctx.i0)
    dates = ctx.dates[rows]
    fourier = n >= 365
    t0 = dates[0] if n >= 120 else None
    X, names = D.design(dates, wx["tmax"][rows], wx["prcp"][rows], wx["snow"][rows],
                        wx["tmax_prev"][rows], wx["prcp_prev"][rows], ctx.K, ctx.cfg.cap,
                        t0=t0, fourier=fourier)
    return X, names, rows


def fit_n(ctx: Ctx, n: int, target: str | None = None) -> dict:
    target = target or ctx.cfg.target
    key = (n, target)
    if key in ctx.fits:
        return ctx.fits[key]
    X, names, rows = design_at(ctx, n)
    Ys = ctx.Ys[rows]
    offset = None
    if n < 365:
        f365 = fit_n(ctx, 365, "log")
        fc = [f365["names"].index(c) for c in D.FOURIER_COLS]
        G = f365["coef"][:, fc]                       # units x 6
        U = G.shape[0]
        loo = (G.sum(0, keepdims=True) - G) / max(U - 1, 1)
        FT = np.column_stack([D.fourier_terms(ctx.dates[rows])[c] for c in D.FOURIER_COLS])
        offset = FT @ loo.T                           # rows x units
    if target == "log":
        Yfit = np.log(np.where(Ys > 0, Ys, np.nan))
        f = fit_many(Yfit, X, names, offset)
    elif target == "level":
        if n < 365:
            raise ValueError("levels sizing is a primary-split (n = 365) sensitivity only")
        f = fit_many(Ys.copy(), X, names, None)
    elif target == "ppml":
        f = fit_ppml(Ys, X, names)
    else:
        raise ValueError(target)
    f["n"] = n
    ctx.fits[key] = f
    return f


def baseline(ctx: Ctx) -> None:
    """F_t (climatological-weather forecast, trend frozen at origin, Duan smearing) and U_t from
    the unit's longest-history log model at this origin (PREREG C14)."""
    f = fit_n(ctx, ctx.n_max, "log")
    hd = ctx.dates[ctx.hedge_idx]
    t0 = ctx.dates[ctx.i0 - ctx.n_max]
    cal = D.calendar_terms(hd, t0, True, trend_at=ctx.origin)
    cols = {**cal, **{c: ctx.clim[c] for c in D.WEATHER_COLS}}
    Xf = np.column_stack([cols[c] for c in f["names"]])
    ctx.F = np.exp(Xf @ f["coef"].T) * f["smear"][None, :]
    ctx.U = ctx.Ys[ctx.hedge_idx] - ctx.F


# ----------------------------------------------------------------------------- arms

def priors_for(ctx: Ctx, n: int, leg: str, method: str) -> tuple[np.ndarray, np.ndarray]:
    f = fit_n(ctx, n)
    pool = f if n >= 365 else fit_n(ctx, 365)
    b, s = f["coef"][:, f["names"].index(leg)], f["se"][leg]
    pb, ps = pool["coef"][:, pool["names"].index(leg)], pool["se"][leg]
    pv = np.where(np.isfinite(ps), ps ** 2, np.nan)
    return loo_priors(np.where(np.isfinite(pv), pb, np.nan), np.where(np.isfinite(pv), pv, np.nan), method)


def arm_betas(ctx: Ctx, n: int) -> dict:
    f = fit_n(ctx, n)
    out = {}
    res = {}
    for leg in ("heat", "wet"):
        b = f["coef"][:, f["names"].index(leg)]
        s = f["se"][leg]
        idf = f["ident"][leg]
        mu, t2 = priors_for(ctx, n, leg, ctx.cfg.eb)
        bt, B = shrink(np.where(idf, b, np.nan), np.where(idf, s, np.inf), mu, t2)
        res[leg] = {"A1": np.where(idf, b, 0.0), "A2": mu, "A3": bt, "B": B, "tau2": t2, "ident": idf}
    for arm in ("A1", "A2", "A3"):
        out[arm] = (res["heat"][arm], res["wet"][arm])
    out["_detail"] = res
    return out


# ----------------------------------------------------------------------------- scoring

@dataclass
class Legs:
    X: np.ndarray
    EX: np.ndarray
    W: np.ndarray
    PW: np.ndarray
    L: DayLadder
    R: DayRain
    ok: np.ndarray        # scored-day mask
    summer: np.ndarray


def legs_for(ctx: Ctx) -> Legs:
    g = GROUPS[ctx.gid]
    hi = ctx.hedge_idx
    hd = ctx.dates[hi]
    T = ctx.wx_real["tmax"][hi]
    P = ctx.wx_real["prcp"][hi]
    X = D.capped_hinge(T, ctx.K, ctx.cfg.cap)
    W = (P >= 0.01).astype(float)
    ok = np.isfinite(T) & np.isfinite(P)
    if ctx.cfg.exclude_susp:
        ok &= ~ctx.susp
    months = pd.to_datetime(hd).month
    summer = (months >= 6) & (months <= 9)
    L = day_ladder(g.heat_series, hd, ctx.K, ctx.cfg.cap, ctx.cfg.horizon)
    R = day_rain(g.rain_series, hd, ctx.cfg.horizon)
    return Legs(np.where(ok, X, 0.0), ctx.clim["heat"], np.where(ok, W, 0.0), ctx.clim["wet"], L, R, ok, summer)


def hedge_sizes(ctx: Ctx, bh: np.ndarray, bw: np.ndarray, sizing: str = "semi") -> tuple[np.ndarray, np.ndarray]:
    if sizing == "semi":
        h = ctx.F * (-bh[None, :])
        hw = ctx.F * (1 - np.exp(bw[None, :]))
    elif sizing == "level":      # levels-model coefficients are already $ per unit
        h = np.broadcast_to(-bh[None, :], ctx.F.shape).copy()
        hw = np.broadcast_to(-bw[None, :], ctx.F.shape).copy()
    else:
        raise ValueError(sizing)
    return h, hw


def pnl(ctx: Ctx, lg: Legs, h: np.ndarray, hw: np.ndarray, ladder: bool = True) -> dict:
    zc_heat = h * (lg.X - lg.EX)[:, None]
    zc_rain = hw * (lg.W - lg.PW)[:, None]
    if not ladder:
        return {"zc_heat": zc_heat, "zc_rain": zc_rain}
    lad = ladder_leg(h, lg.L, ctx.cfg.depth_cap)
    rn = rain_leg(hw, lg.R, ctx.cfg.depth_cap)
    zl_heat = lad["pay"] - lad["prem"]
    zl_rain = rn["pay"] - rn["prem"]
    return {"zc_heat": zc_heat, "zc_rain": zc_rain, "zl_heat": zl_heat, "zl_rain": zl_rain,
            "lad": lad, "rain": rn}


def oracle_sizes(ctx: Ctx, lg: Legs, window: str) -> tuple[np.ndarray, np.ndarray]:
    """A4: constant $ ratios from OLS (demeaned, no intercept) of U on the policy legs over the
    scored days of the window. A bound, never a strategy."""
    m = lg.ok & (lg.summer if window == "heat" else True)
    U = ctx.U[m]
    x1 = (lg.X - lg.EX)[m]
    x1 = x1 - x1.mean()
    Uc = U - U.mean(0)
    if window == "heat":
        h = -(x1 @ Uc) / max(x1 @ x1, 1e-12)
        return np.broadcast_to(h, ctx.F.shape).copy(), np.zeros_like(ctx.F)
    x2 = (lg.W - lg.PW)[m]
    x2 = x2 - x2.mean()
    Xm = np.column_stack([x1, x2])
    coef = -np.linalg.solve(Xm.T @ Xm, Xm.T @ Uc)
    return (np.broadcast_to(coef[0], ctx.F.shape).copy(), np.broadcast_to(coef[1], ctx.F.shape).copy())


def boot_counts(n: int, draws: int, L: int = BLOCK, seed: int = SEED) -> np.ndarray:
    rng = np.random.default_rng(seed)
    nb = int(np.ceil(n / L))
    C = np.zeros((draws, n))
    for d in range(draws):
        starts = rng.integers(0, n - L + 1, size=nb)
        ix = (starts[:, None] + np.arange(L)[None, :]).ravel()[:n]
        C[d] = np.bincount(ix, minlength=n)
    return C


def iid_counts(n: int, draws: int, seed: int = SEED) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.multinomial(n, np.full(n, 1.0 / n), size=draws).astype(float)


def he_units(U: np.ndarray, Z: np.ndarray) -> np.ndarray:
    vu = U.var(0)
    return 1 - (U + Z).var(0) / np.where(vu > 0, vu, np.nan)


def he_boot(U: np.ndarray, Z: np.ndarray, C: np.ndarray) -> dict:
    n = U.shape[0]
    V = U + Z
    m1u, m2u = C @ U / n, C @ (U ** 2) / n
    m1v, m2v = C @ V / n, C @ (V ** 2) / n
    vu = m2u - m1u ** 2
    vv = m2v - m1v ** 2
    heb = 1 - vv / np.where(vu > 0, vu, np.nan)
    med_draws = np.nanmedian(heb, axis=1)
    pt = he_units(U, Z)
    return {"median": float(np.nanmedian(pt)), "p05": float(np.percentile(med_draws, 5)),
            "p95": float(np.percentile(med_draws, 95)), "share_pos": float(np.nanmean(pt > 0)),
            "share_neg": float(np.nanmean(pt < 0)), "n_units": int(np.isfinite(pt).sum()),
            "n_days": int(n), "_draws": med_draws, "_units": pt}


def weekly(hd: np.ndarray, ok: np.ndarray, *mats):
    """Sum days by ISO week, keeping weeks whose 7 days are all scored."""
    iso = pd.to_datetime(hd).isocalendar()
    wk = (iso["year"].values * 100 + iso["week"].values)
    keys, inv = np.unique(wk, return_inverse=True)
    cnt = np.bincount(inv, weights=ok.astype(float), minlength=len(keys))
    good = cnt == 7
    out = []
    for M in mats:
        S = np.zeros((len(keys), M.shape[1]))
        np.add.at(S, inv, np.where(ok[:, None], M, 0.0))
        out.append(S[good])
    return out


def score(ctx: Ctx, lg: Legs, h, hw, want_weekly=True, frames=("cover", "ladder"),
          windows=("heat", "heat_rain")) -> dict:
    g = GROUPS[ctx.gid]
    z = pnl(ctx, lg, h, hw, ladder="ladder" in frames)
    hd = ctx.dates[ctx.hedge_idx]
    res = {}
    for window in windows:
        m = lg.ok & (lg.summer if window == "heat" else True)
        U = ctx.U[m]
        if window == "heat":
            zc = z["zc_heat"][m]
            zl = z["zl_heat"][m] if "zl_heat" in z else None
        else:
            zc = (z["zc_heat"] + z["zc_rain"])[m]
            zl = (z["zl_heat"] + (z["zl_rain"] if g.rain_series else 0.0))[m] if "zl_heat" in z else None
        C = boot_counts(int(m.sum()), ctx.cfg.boot)
        for frame, Z in (("cover", zc), ("ladder", zl)):
            if frame not in frames:
                continue
            res[f"{frame}_{window}_daily"] = he_boot(U, Z, C)
            if want_weekly:
                Uw, Zw = weekly(hd[m], np.ones(int(m.sum()), bool), U, Z)
                Cw = iid_counts(Uw.shape[0], ctx.cfg.boot)
                res[f"{frame}_{window}_weekly"] = he_boot(Uw, Zw, Cw)
    res["_pnl"] = z
    return res


def strip(d):
    """Drop private arrays (keys starting with _) for JSON."""
    if isinstance(d, dict):
        return {k: strip(v) for k, v in d.items() if not str(k).startswith("_")}
    if isinstance(d, (np.floating,)):
        return float(d)
    if isinstance(d, (np.integer,)):
        return int(d)
    if isinstance(d, np.ndarray):
        return d.tolist()
    if isinstance(d, list):
        return [strip(x) for x in d]
    return d


def mu_day_bootstrap(ctx: Ctx, n: int = 365, draws: int = 200) -> dict:
    """Supplementary (not a pre-registered test): CI for the group prior mean that respects the
    shared-weather dependence across units. Estimation days are resampled in 7-day blocks jointly
    for all units, units refit by batch OLS (units with complete rows only), and mu recomputed
    with the original random-effects weights. The DL interval treats units as independent."""
    X, names, rows = design_at(ctx, n)
    Ys = ctx.Ys[rows]
    xok = np.isfinite(X).all(1)
    Yl = np.log(np.where(Ys > 0, Ys, np.nan))[xok]
    Xc = X[xok]
    full = np.isfinite(Yl).all(0)
    if full.sum() < 3:
        return {"skipped": "fewer than 3 complete units"}
    f = fit_n(ctx, n)
    out = {"units_used": int(full.sum()), "draws": draws}
    C = boot_counts(Xc.shape[0], draws, seed=SEED + 1)
    for leg in ("heat", "wet"):
        s = f["se"][leg][full]
        b0 = f["coef"][full, names.index(leg)]
        ok = np.isfinite(s)
        r = dl(b0[ok], s[ok] ** 2)
        w = 1 / (s[ok] ** 2 + r["tau2"])
        mus = []
        for d in range(draws):
            ix = np.repeat(np.arange(Xc.shape[0]), C[d].astype(int))
            Xd = Xc[ix]
            keep = select_columns(Xd, names)
            if names.index(leg) not in keep:
                continue
            B, *_ = np.linalg.lstsq(Xd[:, keep], Yl[ix][:, full], rcond=None)
            bd = B[keep.index(names.index(leg))][ok]
            mus.append(float((w * bd).sum() / w.sum()))
        mus = np.array(mus)
        out[leg] = {"mu": r["mu"], "p025": float(np.percentile(mus, 2.5)), "p975": float(np.percentile(mus, 97.5)),
                    "excludes_zero": bool(np.percentile(mus, 2.5) > 0 or np.percentile(mus, 97.5) < 0)}
    return out


def temp_bin_shape(ctx: Ctx, n: int = 365) -> dict:
    """Diagnostic only (not used for the hedge): 5 degF bins of the daily high in place of
    tlin/heat/heat_l1, base bin 60-64, mean coefficient across units with complete rows."""
    X, names, rows = design_at(ctx, n)
    T = ctx.wx_est["tmax"][rows]
    edges = list(range(40, 100, 5))
    lab = ["<40"] + [f"{a}-{a + 4}" for a in edges[:-1]] + [">=95"]
    b = np.digitize(T, edges)
    drop = {names.index(c) for c in ("tlin", "heat", "heat_l1")}
    base = lab.index("60-64")
    cols = [X[:, j] for j in range(X.shape[1]) if j not in drop]
    nm = [names[j] for j in range(X.shape[1]) if j not in drop]
    for k, l in enumerate(lab):
        if k != base:
            cols.append((b == k).astype(float))
            nm.append(l)
    Xb = np.column_stack(cols)
    xok = np.isfinite(Xb).all(1) & np.isfinite(T)
    Ys = ctx.Ys[rows][xok]
    Yl = np.log(np.where(Ys > 0, Ys, np.nan))
    full = np.isfinite(Yl).all(0)
    keep = select_columns(Xb[xok], nm)
    B, *_ = np.linalg.lstsq(Xb[xok][:, keep], Yl[:, full], rcond=None)
    kn = [nm[j] for j in keep]
    out = {}
    for l in lab:
        if l == "60-64":
            out[l] = {"coef": 0.0, "days": int((b[xok] == base).sum())}
        elif l in kn:
            out[l] = {"coef": float(B[kn.index(l)].mean()), "days": int((b[xok] == lab.index(l)).sum())}
    return out
