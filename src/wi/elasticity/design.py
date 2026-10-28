"""Regressors for the elasticity model. numpy + stdlib only: the evaluation and the portal call this.

Columns (PREREG spec + C9):
  const, dow1..dow6 (Mon = base), hol, hol_m1, hol_p1, [trend], [s1 c1 s2 c2 s3 c3],
  tlin = min(T, K), heat = clip(T - K, 0, cap), wet = 1{P >= 0.01}, heavy = 1{P >= 0.50},
  wet_l1, heat_l1 (previous calendar day), snow = 1{snowfall >= 1.0}
T is the NWS climate-report daily high (int degF) at the settlement station; trace precip = 0.0.
Dates are local business days (numpy datetime64[D]); Fourier terms come from the day of year,
never from row position; lags come from the previous calendar day, never the previous row.
"""
from __future__ import annotations

import datetime as dt
from functools import lru_cache

import numpy as np

WEATHER_COLS = ("tlin", "heat", "wet", "heavy", "wet_l1", "heat_l1", "snow")
FOURIER_COLS = ("s1", "c1", "s2", "c2", "s3", "c3")


def capped_hinge(T, K, cap):
    """The contract payoff per $1/degF: min(max(T - K, 0), cap). Also the heat regressor."""
    return np.clip(np.asarray(T, float) - K, 0.0, cap)


# --------------------------------------------------------------------------- holidays

def _nearest_workday(d: dt.date) -> dt.date:
    if d.weekday() == 5:
        return d - dt.timedelta(days=1)
    if d.weekday() == 6:
        return d + dt.timedelta(days=1)
    return d


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    d = dt.date(year, month, 1)
    d += dt.timedelta(days=(weekday - d.weekday()) % 7)
    return d + dt.timedelta(weeks=n - 1)


def _last_weekday(year: int, month: int, weekday: int) -> dt.date:
    d = dt.date(year + (month == 12), 1 if month == 12 else month + 1, 1) - dt.timedelta(days=1)
    return d - dt.timedelta(days=(d.weekday() - weekday) % 7)


@lru_cache(maxsize=None)
def us_holidays(year: int) -> frozenset:
    """US federal holidays (observed, the pandas USFederalHolidayCalendar rules) + Dec 24, Dec 31,
    day after Thanksgiving (retail days)."""
    h = {
        _nearest_workday(dt.date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),            # MLK
        _nth_weekday(year, 2, 0, 3),            # Presidents
        _last_weekday(year, 5, 0),              # Memorial
        _nearest_workday(dt.date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),            # Labor
        _nth_weekday(year, 10, 0, 2),           # Columbus
        _nearest_workday(dt.date(year, 11, 11)),
        _nth_weekday(year, 11, 3, 4),           # Thanksgiving
        _nearest_workday(dt.date(year, 12, 25)),
    }
    if year >= 2021:
        h.add(_nearest_workday(dt.date(year, 6, 19)))
    tg = _nth_weekday(year, 11, 3, 4)
    h |= {dt.date(year, 12, 24), dt.date(year, 12, 31), tg + dt.timedelta(days=1)}
    # New Year's observed on Dec 31 of the prior year is already Dec 31 (retail day)
    return frozenset(h)


def holiday_flags(dates: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ds = [d.astype(dt.date) for d in dates.astype("datetime64[D]")]
    years = {d.year for d in ds} | {d.year - 1 for d in ds} | {d.year + 1 for d in ds}
    H = set().union(*(us_holidays(y) for y in years))
    one = dt.timedelta(days=1)
    hol = np.array([d in H for d in ds], float)
    hol_m1 = np.array([(d + one) in H for d in ds], float)   # day before a holiday
    hol_p1 = np.array([(d - one) in H for d in ds], float)   # day after a holiday
    return hol, hol_m1, hol_p1


# --------------------------------------------------------------------------- weather terms

def weather_terms(tmax, prcp, snow, tmax_prev, prcp_prev, K: float, cap: float) -> dict[str, np.ndarray]:
    tmax = np.asarray(tmax, float)
    prcp = np.asarray(prcp, float)
    prcp_prev = np.asarray(prcp_prev, float)
    snow = np.asarray(snow, float)
    # missing precipitation stays missing (NaN), never "dry"; the row is dropped from the fit
    return {
        "tlin": np.minimum(tmax, K),
        "heat": capped_hinge(tmax, K, cap),
        "wet": np.where(np.isnan(prcp), np.nan, (prcp >= 0.01).astype(float)),
        "heavy": np.where(np.isnan(prcp), np.nan, (prcp >= 0.50).astype(float)),
        "wet_l1": np.where(np.isnan(prcp_prev), np.nan, (prcp_prev >= 0.01).astype(float)),
        "heat_l1": capped_hinge(tmax_prev, K, cap),
        "snow": np.where(np.isnan(snow), 0.0, (snow >= 1.0).astype(float)),
    }


def calendar_terms(dates: np.ndarray, t0: np.datetime64 | None, fourier: bool,
                   trend_at: np.datetime64 | None = None) -> dict[str, np.ndarray]:
    """Calendar columns. trend = years since t0 (None -> no trend); trend_at freezes it (forecasts)."""
    dates = np.asarray(dates).astype("datetime64[D]")
    out: dict[str, np.ndarray] = {"const": np.ones(len(dates))}
    dow = ((dates.astype("int64") + 3) % 7)          # 1970-01-01 was a Thursday -> Mon = 0
    for k in range(1, 7):
        out[f"dow{k}"] = (dow == k).astype(float)
    out["hol"], out["hol_m1"], out["hol_p1"] = holiday_flags(dates)
    if t0 is not None:
        ref = dates if trend_at is None else np.full(len(dates), np.datetime64(trend_at, "D"))
        out["trend"] = (ref - np.datetime64(t0, "D")).astype("int64") / 365.25
    if fourier:
        out.update(fourier_terms(dates))
    return out


def fourier_terms(dates: np.ndarray) -> dict[str, np.ndarray]:
    dates = np.asarray(dates).astype("datetime64[D]")
    years = dates.astype("datetime64[Y]")
    doy = (dates - years.astype("datetime64[D]")).astype("int64") + 1
    out = {}
    for k in range(1, 4):
        out[f"s{k}"] = np.sin(2 * np.pi * k * doy / 365.25)
        out[f"c{k}"] = np.cos(2 * np.pi * k * doy / 365.25)
    return out


def design(dates, tmax, prcp, snow, tmax_prev, prcp_prev, K, cap, t0=None, fourier=True,
           trend_at=None) -> tuple[np.ndarray, list[str]]:
    """Full design matrix (rows = dates) and column names, in a fixed order."""
    cols = calendar_terms(dates, t0, fourier, trend_at)
    cols.update(weather_terms(tmax, prcp, snow, tmax_prev, prcp_prev, K, cap))
    names = list(cols)
    return np.column_stack([cols[n] for n in names]), names
