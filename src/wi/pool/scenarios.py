"""Long-history weather scenarios for the pool (04-RESEARCH Pattern 4, PREREG "Forecast proxy").

GHCN-Daily TMAX (by_station csv.gz, long format) -> whole degF per station and date; Midway
spliced from O'Hare + monthly (MDW - ORD) offset before its record starts; R-A metro mean with a
60 % quorum; persistence forecast proxy (3-harmonic climatology + AR(1) on detrended anomalies)
that generates the historical ladder strike K and the scenario fair value mu. Per-unit P&L for a
house LONG one $1/degF unit: station leg u = H(T;K) - mu, residual leg v = r - mu_r.
"""
from __future__ import annotations

import gzip
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
GHCN_DIR = ROOT / "data" / "raw" / "ghcnd_eval04"

GHCN_ID = {"NYC": "USW00094728", "EWR": "USW00014734", "TTN": "USW00014792", "MDW": "USW00014819",
           "ORD": "USW00094846", "MIA": "USW00012839", "LGA": "USW00014732", "JFK": "USW00094789",
           "TEB": "USW00094741", "CDW": "USW00054743", "HPN": "USW00094745", "FRG": "USW00054787",
           "SMQ": "USW00054785", "DYL": "USW00054786", "PNE": "USW00094732", "WRI": "USW00014706",
           "VAY": "USW00093780", "LOT": "USC00117457", "PWK": "USW00004838", "DPA": "USW00094892",
           "OPF": "USW00012882", "HWO": "USW00092809", "HST": "USW00012826", "FLL": "USW00012849",
           "FXE": "USW00012885"}
# Phase 3 temperature networks (03-RESEARCH Q5). JRB, MMU, GYY have no GHCN TMAX record -> absent.
NETWORK = {"NYC": ["LGA", "JRB", "TEB", "EWR", "JFK", "CDW", "MMU", "HPN", "FRG"],
           "EWR": ["JRB", "NYC", "TEB", "CDW", "MMU", "LGA", "JFK", "SMQ"],
           "TTN": ["DYL", "PNE", "WRI", "VAY", "SMQ"],
           "MDW": ["ORD", "GYY", "LOT", "PWK", "DPA"],
           "MIA": ["OPF", "HWO", "HST", "FLL", "FXE"]}
SETTLE = ["NYC", "EWR", "TTN", "MDW", "MIA"]
WARM = (5, 6, 7, 8, 9)
CAP = 6.0


def H(T, K, cap: float = CAP):
    return np.clip(np.asarray(T, float) - np.asarray(K, float), 0.0, cap)


def load_tmax(code: str) -> pd.Series:
    """Whole-degF TMAX by date; values with a quality flag are dropped."""
    gid = GHCN_ID[code]
    p = GHCN_DIR / f"{gid}.csv.gz"
    if not p.exists():
        return pd.Series(dtype=float)
    df = pd.read_csv(p, header=None, names=["id", "date", "el", "v", "m", "q", "s", "t"], dtype=str,
                     keep_default_na=False)
    df = df[(df["el"] == "TMAX") & (df["q"] == "")]
    c = df["v"].astype(int) / 10.0
    f = np.floor(c * 9.0 / 5.0 + 32.0 + 0.5)   # tenths degC back to the original whole degF
    s = pd.Series(f.to_numpy(), index=pd.to_datetime(df["date"], format="%Y%m%d"), name=code)
    return s[~s.index.duplicated()].sort_index()


def _splice(target: pd.Series, donor: pd.Series, start_year: int = 1998) -> tuple[pd.Series, dict]:
    """Fill `target` before its continuous record (from start_year or its first value) with
    donor + monthly mean (target - donor) offset fitted on the overlap through 2020."""
    t = target[target.index.year >= start_year].dropna()
    start = t.index.min()
    j = pd.concat([t, donor], axis=1, keys=["t", "d"]).dropna()
    j = j[j.index.year <= 2020]
    off = (j["t"] - j["d"]).groupby(j.index.month).mean()
    pre = donor[donor.index < start]
    spliced = np.round(pre + off.reindex(pre.index.month).to_numpy())
    return pd.concat([spliced, t]).sort_index(), dict(record_start=str(start.date()),
                                                    offset_by_month={int(k): round(float(v), 3) for k, v in off.items()})


def settlement_series(tmax: dict[str, pd.Series]) -> tuple[dict[str, pd.Series], dict]:
    """Settlement-station TMAX. MDW before its record (1997) = ORD + monthly offset (PREREG).
    TTN's GHCN record is continuous only from 1998 (one stray 1945 year): before that, NE
    Philadelphia PNE (27.7 km, 1945-) + monthly offset (deviation D3)."""
    out = {k: tmax[k] for k in SETTLE}
    out["MDW"], i_m = _splice(tmax["MDW"], tmax["ORD"], 1997)
    out["TTN"], i_t = _splice(tmax["TTN"], tmax["PNE"], 1998)
    return out, dict(MDW_from_ORD=i_m, TTN_from_PNE=i_t)


def metro_mean(tmax: dict[str, pd.Series], station: str, settle: pd.Series, quorum: float = 0.6) -> pd.Series:
    """Equal-weight mean over the listed network + S; NaN where < quorum of listed inputs present."""
    members = NETWORK[station]
    cols = {m: tmax[m] for m in members if m in tmax and len(tmax[m])}
    cols[station] = settle
    df = pd.DataFrame(cols)
    n_list = len(members) + 1
    ok = df.notna().sum(axis=1) >= quorum * n_list
    return df.mean(axis=1).where(ok).round(1)


def _harmonics(doy: np.ndarray, k: int = 3) -> np.ndarray:
    w = 2 * np.pi * doy / 365.25
    cols = [np.ones_like(w)]
    for i in range(1, k + 1):
        cols += [np.cos(i * w), np.sin(i * w)]
    return np.column_stack(cols)


@dataclass
class ProxyModel:
    station: str
    fit_years: tuple[int, int]
    detrend: bool
    trend_per_year: float
    clim_coef: np.ndarray
    phi: float
    resid_by_month: dict[int, np.ndarray] = field(repr=False)

    def clim(self, dates: pd.DatetimeIndex) -> np.ndarray:
        return _harmonics(dates.dayofyear.to_numpy(float)) @ self.clim_coef

    def shift(self, dates: pd.DatetimeIndex) -> np.ndarray:
        """Additive shift that moves a value in year y to the 2026 level."""
        if not self.detrend:
            return np.zeros(len(dates))
        return self.trend_per_year * (2026 - dates.year.to_numpy(float))


def fit_proxy(T: pd.Series, station: str, years: tuple[int, int], detrend: bool = True) -> ProxyModel:
    s = T[(T.index.year >= years[0]) & (T.index.year <= years[1])].dropna()
    warm = s[s.index.month.isin(WARM)]
    b = 0.0
    if detrend:
        ym = warm.groupby(warm.index.year).mean()
        ym = ym[warm.groupby(warm.index.year).size() >= 120]
        b = float(np.polyfit(ym.index.to_numpy(float), ym.to_numpy(float), 1)[0])
    sd = s + (b * (2026 - s.index.year.to_numpy(float)) if detrend else 0.0)
    X = _harmonics(sd.index.dayofyear.to_numpy(float))
    coef, *_ = np.linalg.lstsq(X, sd.to_numpy(float), rcond=None)
    anom = pd.Series(sd.to_numpy(float) - X @ coef, index=sd.index)
    lag = anom.shift(1, freq="D").reindex(anom.index)
    m = anom.index.month.isin(WARM) & lag.notna().to_numpy()
    a, l_ = anom[m].to_numpy(), lag[m].to_numpy()
    phi = float((a * l_).sum() / (l_ * l_).sum())
    eps = pd.Series(a - phi * l_, index=anom.index[m])
    resid = {mo: eps[eps.index.month == mo].to_numpy() for mo in WARM}
    return ProxyModel(station, years, detrend, b, coef, phi, resid)


def mu_H(F: np.ndarray, K: np.ndarray, months: np.ndarray, model: ProxyModel) -> np.ndarray:
    """Scenario fair value E[H(round(F + eps); K)] over the month's empirical residuals."""
    out = np.empty(len(F))
    for mo in WARM:
        idx = np.flatnonzero(months == mo)
        if not len(idx):
            continue
        e = model.resid_by_month[mo]
        # F - K lies in [3, 4) up to float error; evaluate on a grid of offsets and interpolate
        off = F[idx] - K[idx]
        grid = np.linspace(off.min() - 0.01, off.max() + 0.01, 41)
        vals = np.array([np.clip(np.floor(g + e + 0.5), 0.0, CAP).mean() for g in grid])
        out[idx] = np.interp(off, grid, vals)
    return out


def proxy_days(T: pd.Series, model: ProxyModel, years: tuple[int, int]) -> pd.DataFrame:
    """Warm-season days in `years` with the proxy forecast F, strike K, integer T (2026 level), mu."""
    s = T.dropna()
    sh = pd.Series(model.shift(s.index), index=s.index)
    sd = s + sh
    anom = sd - model.clim(sd.index)
    lag = anom.shift(1, freq="D").reindex(anom.index)
    d = pd.DataFrame({"T_raw": s, "T": np.floor(sd + 0.5), "shift": sh, "lag": lag})
    d = d[(d.index.year >= years[0]) & (d.index.year <= years[1]) & d.index.month.isin(WARM)].dropna()
    d["F"] = model.clim(d.index) + model.phi * d["lag"]
    d["K"] = np.floor(d["F"] - 3.5 + 0.5)
    d["mu"] = mu_H(d["F"].to_numpy(), d["K"].to_numpy(), d.index.month.to_numpy(), model)
    d["H"] = H(d["T"], d["K"])
    d["u"] = d["H"] - d["mu"]
    return d
