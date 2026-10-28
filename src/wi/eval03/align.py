"""The only place Phase 3 day conventions live (docs/CONVENTIONS.md section 3; 03-RESEARCH Pitfall 1).

- Grid label D (nClimGrid-Daily and PRISM AN91d) represents calendar (CLI, LST) day D - 1:
  cli_day = label_day - 1 day. So calendar day X is read from grid label X + 1.
- Weekly rain: calendar weeks Mon-Sun (pandas "W-SUN", labelled by the Sunday). On grid labels that
  is Tue-Mon. A week counts only if all 7 calendar days are present.
- Trailing strike: K_t = floor(mean of T_S over t-7..t-1), strictly before t.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

GRID_LAG = pd.Timedelta(days=1)


def grid_label_for_calendar_day(d: dt.date) -> dt.date:
    return d + dt.timedelta(days=1)


def cli_day_from_label(label) -> pd.Series:
    """Grid label dates (date objects or strings) -> the calendar day they represent (Timestamp)."""
    s = label if isinstance(label, pd.Series) else pd.Series(label)
    return pd.to_datetime(s) - GRID_LAG


def week_of(day: pd.Series | pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Calendar Mon-Sun week, labelled by its Sunday."""
    d = pd.DatetimeIndex(pd.to_datetime(day))
    return d + pd.to_timedelta((6 - d.dayofweek) % 7, unit="D")


def weekly_total(p: pd.Series) -> pd.Series:
    """p: calendar-day series (DatetimeIndex). Mon-Sun totals; NaN unless all 7 days are present."""
    return p.resample("W-SUN").sum(min_count=7).where(p.resample("W-SUN").count() == 7)


def grid_weekly_labels(week_sunday: pd.Timestamp) -> pd.DatetimeIndex:
    """The 7 grid labels (Tue..Mon) that make up calendar week Mon..Sun ending on week_sunday."""
    mon = week_sunday - pd.Timedelta(days=6)
    return pd.date_range(mon, week_sunday) + GRID_LAG


def trailing_strike(ts: pd.Series) -> pd.Series:
    """K_t = floor(mean of T_S over t-7..t-1) on a daily DatetimeIndex; needs all 7 prior days."""
    s = ts.asfreq("D")
    m = s.shift(1).rolling(7, min_periods=7).mean()
    return np.floor(m)
