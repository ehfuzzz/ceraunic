"""Design registry: D0, G1-P, G1-N, G1-P*, G1-N*, C1-N, R-A, R-P, R-N, R-A-PC, R-N-PC, P-A, P-A-IDW.

For one (variable, market, truth point b) this builds, on the evaluation units (calendar days for
temperature, Mon-Sun weeks for rain), the exposure E_b, the station leg H_S and the residual r of every
design (03-RESEARCH Pre-registration Draft, "Designs"). Same-source spreads throughout, except G1-*
(the ins2 cell-minus-ASOS form, continuity only).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from wi.eval03 import align
from wi.eval03.indexes import (H_rain, H_temp, disc_mean, fit_pc1, idw_weights, nearest, network_mean,
                               weighted_index, wet)

DESIGNS = ["D0", "G1-P", "G1-N", "G1-P*", "G1-N*", "C1-N", "R-A", "R-P", "R-N", "R-A-PC", "R-N-PC", "P-A", "P-A-IDW"]
ROLE = {d: "eligible" for d in DESIGNS}
ROLE.update({"D0": "baseline", "G1-P*": "continuity", "G1-N*": "continuity", "R-A-PC": "exploratory",
             "R-N-PC": "exploratory"})


@dataclass
class Config:
    markets: tuple
    truth: dict          # variable -> market -> [codes]
    network: dict        # variable -> market -> [codes]
    outer: dict          # variable -> market -> [codes]
    coords: dict         # code -> (lat, lon)
    county: dict         # code -> county name
    awos: set = field(default_factory=set)
    train: tuple = ("2024-01-01", "2024-12-31")
    test: tuple = ("2025-01-01", "2026-08-31")
    draws: int = 2000
    block_days: int = 14
    block_weeks: int = 2
    seed: int = 20260930
    min_pay_days: int = 60
    min_pay_weeks: int = 20
    quorum: float = 0.6
    disc_km: float = 30.0
    lam: float = 0.25
    cap_temp: float = 6.0
    cap_rain: float = 3.0
    premium: dict = field(default_factory=dict)   # market -> station-leg 24 h ask premium per unit-day
    extras: bool = True


@dataclass
class Data:
    """Daily panels on the CLI calendar day (grids already shifted by align.py)."""
    T: pd.DataFrame                  # station tmax, degF (after the data-quality source choice)
    P: pd.DataFrame                  # station precip, inches
    NT: pd.DataFrame                 # nClimGrid cell containing each station
    NP: pd.DataFrame
    PT: pd.DataFrame                 # PRISM cell containing each station (NaN column where none pulled)
    PP: pd.DataFrame
    disc: dict                       # (source, S) -> {"T","P": days x cells, "lat","dist": arrays}
    CT: pd.DataFrame                 # nClimGrid county averages, days x county
    CP: pd.DataFrame
    prism_rel: pd.Series | None = None   # PRISM tmax release (grid count) per day
    ladder: dict | None = None       # market -> DataFrame(index=day, K, X) settled Kalshi rule-A rows


@dataclass
class Opts:
    """Main run = defaults. Sensitivities flip one field."""
    rounded: bool = True
    linear: bool = False
    strike: str = "trailing"          # trailing | fixed_monthly | kalshi
    disc_km: float | None = None
    metro_incl_S: bool = True
    net_override: dict | None = None  # market -> network list (radius sensitivity)


# ------------------------------------------------------------------------------------------ units
def to_units(df: pd.DataFrame, unit: str) -> pd.DataFrame:
    if unit in ("day", "wetday"):
        return df
    if unit == "week":
        g = df.resample("W-SUN")
        return g.sum(min_count=7).where(g.count() == 7)
    if unit == "month":
        g = df.resample("ME")
        n_days = pd.Series(g.size().index.days_in_month, index=g.size().index)
        return g.sum(min_count=1).where(g.count().eq(n_days, axis=0))
    raise ValueError(unit)


def unit_windows(index: pd.DatetimeIndex, unit: str, cfg: Config) -> tuple[np.ndarray, np.ndarray]:
    """Boolean masks (train, test). Weeks are labelled by their Sunday and must lie fully inside the window."""
    tr0, tr1 = map(pd.Timestamp, cfg.train)
    te0, te1 = map(pd.Timestamp, cfg.test)
    if unit == "week":
        start = index - pd.Timedelta(days=6)
        return ((start >= tr0) & (index <= tr1)), ((start >= te0) & (index <= te1))
    if unit == "month":
        start = index.to_period("M").to_timestamp()
        return ((start >= tr0) & (index <= tr1)), ((start >= te0) & (index <= te1))
    return ((index >= tr0) & (index <= tr1)), ((index >= te0) & (index <= te1))


class Units:
    """All panels of one variable on one unit."""

    def __init__(self, data: Data, variable: str, unit: str):
        self.variable, self.unit = variable, unit
        tv = variable == "temperature"
        pick = (lambda a, b: a if tv else b)
        self.st = to_units(pick(data.T, data.P), unit)
        self.index = self.st.index
        self.n = to_units(pick(data.NT, data.NP), unit).reindex(self.index)
        self.p = to_units(pick(data.PT, data.PP), unit).reindex(self.index)
        self.cty = to_units(pick(data.CT, data.CP), unit).reindex(self.index)
        self.disc = {}
        for key, d in data.disc.items():
            self.disc[key] = dict(X=to_units(pick(d["T"], d["P"]), unit).reindex(self.index), lat=d["lat"], dist=d["dist"])
        self.rel = data.prism_rel.reindex(self.index) if (data.prism_rel is not None and unit == "day") else None


def payout_fn(cfg: Config, U: Units, market: str, opts: Opts, data: Data):
    """f(x) -> payout array on U.index for this market (strike is per market-day, same for every design)."""
    if U.variable == "temperature":
        TS = U.st[market]
        if opts.strike == "trailing":
            K = align.trailing_strike(data.T[market]).reindex(U.index).to_numpy()
        elif opts.strike == "fixed_monthly":
            tr = data.T[market].loc[cfg.train[0]:cfg.train[1]]
            km = np.floor(tr.groupby(tr.index.month).mean())
            K = km.reindex(U.index.month).to_numpy()
        elif opts.strike == "kalshi":
            lad = data.ladder[market] if data.ladder and market in data.ladder else None
            K = (lad["K"].reindex(U.index).to_numpy() if lad is not None else np.full(len(U.index), np.nan))
        else:
            raise ValueError(opts.strike)
        _ = TS
        return lambda x: H_temp(np.asarray(x, float), K, cfg.cap_temp, opts.rounded, opts.linear)
    if U.unit == "wetday":
        return lambda x: wet(np.asarray(x, float))
    if U.unit == "month":
        return lambda x: np.floor(np.asarray(x, float) * 100 + 0.5) / 100
    return lambda x: H_rain(np.asarray(x, float), cfg.cap_rain, opts.rounded)


def _col(df: pd.DataFrame, c) -> np.ndarray:
    return df[c].to_numpy(float) if c in df.columns else np.full(len(df), np.nan)


def market_level(cfg: Config, U: Units, market: str, f, opts: Opts) -> dict:
    """Residuals that do not depend on b (grid regional factors), with their fitted objects."""
    S = market
    radius = opts.disc_km or cfg.disc_km
    out, meta = {}, {}
    tr_mask, _ = unit_windows(U.index, U.unit, cfg)
    for src, cell_panel, key in (("prism", U.p, "R-P"), ("nclimgrid", U.n, "R-N")):
        d = U.disc.get((src, S))
        if d is None:
            out[key] = np.full(len(U.index), np.nan)
            continue
        idx = disc_mean(d["X"], d["lat"], d["dist"], radius, cfg.quorum)
        out[key] = f(idx.to_numpy()) - f(_col(cell_panel, S))
        meta[key] = {"cells": int((d["dist"] <= radius).sum()), "radius_km": radius}
    d = U.disc.get(("nclimgrid", S))
    if d is not None:
        sel = d["dist"] <= radius
        X = d["X"].loc[:, sel]
        fit = fit_pc1(X, U.n[S] if S in U.n.columns else pd.Series(np.nan, index=U.index),
                      U.index[tr_mask].min().strftime("%Y-%m-%d") if tr_mask.any() else cfg.train[0], cfg.train[1])
        idx = weighted_index(X, fit["w"], cfg.quorum)
        out["R-N-PC"] = f(idx.to_numpy()) - f(_col(U.n, S))
        w = fit["w"]
        meta["R-N-PC"] = {"n_inputs": int(len(w)), "n_pos": int((w > 0).sum()), "w_max": float(w.max()),
                          "pc1_share": fit["share"], "fit_first": fit["fit_first"], "fit_last": fit["fit_last"],
                          "n_fit": fit["n_fit"], "eff_n": float(1.0 / (w ** 2).sum()) if (w ** 2).sum() > 0 else None,
                          "fallback": fit["fallback"]}
    else:
        out["R-N-PC"] = np.full(len(U.index), np.nan)
    return {"r": out, "meta": meta}


def pair(cfg: Config, U: Units, variable: str, market: str, b: str, f, mk: dict, opts: Opts) -> dict:
    """E, H_S and every design's residual for one (market, point)."""
    S = market
    net = (opts.net_override or {}).get(market, cfg.network[variable][market])
    net = [j for j in net if j not in cfg.awos]
    E = f(_col(U.st, b))
    HS = f(_col(U.st, S))
    fS_st = HS
    r, meta, zero = {}, {}, {}
    n = len(U.index)
    r["D0"] = np.zeros(n)
    r["G1-P"] = f(_col(U.p, b)) - f(_col(U.p, S))
    r["G1-N"] = f(_col(U.n, b)) - f(_col(U.n, S))
    r["G1-P*"] = f(_col(U.p, b)) - fS_st
    r["G1-N*"] = f(_col(U.n, b)) - fS_st
    kb, kS = cfg.county.get(b), cfg.county.get(S)
    if kb == kS:
        r["C1-N"] = np.where(np.isnan(E), np.nan, 0.0)
        zero["C1-N"] = "same county as S"
    else:
        r["C1-N"] = f(_col(U.cty, kb)) - f(_col(U.cty, kS))
    meta["C1-N"] = {"county_b": kb, "county_S": kS}
    # regional factor on the ASOS network, LOO
    members = [j for j in net if j != b] + ([S] if opts.metro_incl_S else [])
    m_idx = network_mean(U.st, members, exclude=b, quorum=cfg.quorum)
    r["R-A"] = f(m_idx.to_numpy()) - fS_st
    meta["R-A"] = {"members": sorted(j for j in members if j != b)}
    # frozen PC1 weights, LOO: inputs = network minus b (S's own residual column is identically zero)
    tr_mask, _ = unit_windows(U.index, U.unit, cfg)
    pc_in = [j for j in net if j != b and j != S and j in U.st.columns]
    if pc_in:
        fit = fit_pc1(U.st[pc_in], U.st[S], U.index[tr_mask].min().strftime("%Y-%m-%d") if tr_mask.any() else cfg.train[0],
                      cfg.train[1])
        idx = weighted_index(U.st[pc_in], fit["w"], cfg.quorum)
        r["R-A-PC"] = f(idx.to_numpy()) - fS_st
        meta["R-A-PC"] = {"w": {k: round(float(v), 4) for k, v in fit["w"].items()}, "pc1_share": fit["share"],
                          "fit_first": fit["fit_first"], "fit_last": fit["fit_last"], "n_fit": fit["n_fit"],
                          "fallback": fit["fallback"]}
    else:
        r["R-A-PC"] = np.full(n, np.nan)
    r["R-P"], r["R-N"], r["R-N-PC"] = mk["r"]["R-P"], mk["r"]["R-N"], mk["r"]["R-N-PC"]
    # station pair and IDW, LOO: candidates = (network minus b) plus S
    cand = sorted(set([j for j in net if j != b] + [S]))
    (jstar, dstar), = nearest(cand, cfg.coords, b, 1)
    if jstar == S:
        r["P-A"] = np.where(np.isnan(E), np.nan, 0.0)
        zero["P-A"] = "S is the nearest station"
    else:
        r["P-A"] = f(_col(U.st, jstar)) - fS_st
    meta["P-A"] = {"partner": jstar, "partner_km": round(dstar, 1)}
    w = idw_weights(cand, cfg.coords, b, 3, 2.0)
    r["P-A-IDW"] = f(weighted_index(U.st.reindex(columns=list(w.index)), w, cfg.quorum).to_numpy()) - fS_st
    meta["P-A-IDW"] = {"w": {k: round(float(v), 4) for k, v in w.items()}}
    return {"E": E, "HS": HS, "r": r, "meta": meta, "zero": zero}
