"""Hedge legs for EVAL-06: policy frame (exact payoff vs climatology) and execution frame
(rounded Kalshi contracts at 24 h asks/bids with fees, paid on the Kalshi result).

Shapes: days x units for h and P&L; days x B for bracket arrays (B = max brackets, zero-padded).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .design import capped_hinge
from .ladder_shim import load_quotes


@dataclass
class DayLadder:
    """Heat ladder per hedge day at one horizon: bracket payoff weights, prices, winner."""
    G: np.ndarray        # days x B, g(r_b) (0 on padding)
    ASK: np.ndarray      # days x B
    BID: np.ndarray
    NOBUY: np.ndarray    # days x B bool (buy-side no-offer)
    NOSELL: np.ndarray   # days x B bool
    WIN: np.ndarray      # days x B bool (Kalshi result = yes)
    avail: np.ndarray    # days bool (a complete, settled ladder listed)


@dataclass
class DayRain:
    ask: np.ndarray
    bid: np.ndarray
    nobuy: np.ndarray
    nosell: np.ndarray
    yes: np.ndarray      # float 0/1
    avail: np.ndarray


def _nobuy(ask, bid):
    a = np.asarray(ask, float)
    b = np.asarray(bid, float)
    bad = ~np.isfinite(a) | (a <= 0)
    return bad | ((a >= 0.99) & (~np.isfinite(b) | (b < 0.90)))


def _nosell(ask, bid):
    a = np.asarray(ask, float)
    b = np.asarray(bid, float)
    bad = ~np.isfinite(b) | (b <= 0)
    return bad | ((b <= 0.01) & (~np.isfinite(a) | (a > 0.10)))


def day_ladder(series: str, dates: np.ndarray, K: float, cap: float, horizon: int = 24,
               quotes: pd.DataFrame | None = None) -> DayLadder:
    q = load_quotes() if quotes is None else quotes
    q = q[(q.series_ticker == series) & q.event_ok]
    idx = {d: i for i, d in enumerate(pd.to_datetime(dates).date)}
    q = q[q["date"].isin(idx)]
    B = 8
    n = len(dates)
    G = np.zeros((n, B)); ASK = np.full((n, B), np.nan); BID = np.full((n, B), np.nan)
    WIN = np.zeros((n, B), bool); avail = np.zeros(n, bool); pad = np.ones((n, B), bool)
    for d, g in q.groupby("date"):
        i = idx[d]
        if g["event_ticker"].nunique() > 1:
            # a relisted second ladder on the same date (seen once: HIGHCHI-2-24FEB28): use the
            # event quoted at the decision time (most non-missing asks), ties -> last ticker
            score = g.groupby("event_ticker")[f"ask_{horizon}"].apply(lambda s: s.notna().sum())
            best = sorted(score[score == score.max()].index)[-1]
            g = g[g["event_ticker"] == best]
        g = g.sort_values("rep")
        k = len(g)
        G[i, :k] = capped_hinge(g["rep"].values, K, cap)
        ASK[i, :k] = g[f"ask_{horizon}"].values
        BID[i, :k] = g[f"bid_{horizon}"].values
        WIN[i, :k] = (g["result"] == "yes").values
        pad[i, :k] = False
        avail[i] = True
    NOBUY = _nobuy(ASK, BID) & ~pad
    NOSELL = _nosell(ASK, BID) & ~pad
    return DayLadder(G, ASK, BID, NOBUY, NOSELL, WIN, avail)


def day_rain(series: str | None, dates: np.ndarray, horizon: int = 24, quotes: pd.DataFrame | None = None) -> DayRain:
    n = len(dates)
    ask = np.full(n, np.nan); bid = np.full(n, np.nan); yes = np.zeros(n); avail = np.zeros(n, bool)
    if series is not None:
        q = load_quotes() if quotes is None else quotes
        q = q[q.series_ticker == series]
        idx = {d: i for i, d in enumerate(pd.to_datetime(dates).date)}
        for r in q.itertuples():
            i = idx.get(r.date)
            if i is None:
                continue
            ask[i] = getattr(r, f"ask_{horizon}")
            bid[i] = getattr(r, f"bid_{horizon}")
            yes[i] = 1.0 if r.result == "yes" else 0.0
            avail[i] = True
    return DayRain(ask, bid, _nobuy(ask, bid), _nosell(ask, bid), yes, avail)


def fee(q: np.ndarray, p: np.ndarray) -> np.ndarray:
    """Kalshi taker fee per order, ceil to the cent of 0.07 * |q| * P * (1 - P)."""
    c = np.abs(q)
    pp = np.where(np.isfinite(p), p, 0.0)
    raw = np.round(0.07 * c * pp * (1 - pp) * 100, 9)
    return np.where((c > 0) & (pp > 0) & (pp < 1), np.ceil(raw) / 100, 0.0)


def ladder_leg(h: np.ndarray, L: DayLadder, depth_cap: int | None = None) -> dict:
    """h: days x units ($ per degF). Returns premium (incl. fees; negative = received), payout,
    unhedgeable mask, side masks. Rounded contracts q_b = round(h * g(r_b))."""
    q = np.rint(h[:, :, None] * L.G[:, None, :])
    if depth_cap is not None:
        q = np.clip(q, -depth_cap, depth_cap)
    need = q != 0
    bad = ((q > 0) & L.NOBUY[:, None, :]) | ((q < 0) & L.NOSELL[:, None, :])
    unhedge = bad.any(axis=2) | (~L.avail[:, None] & need.any(axis=2))
    active = need.any(axis=2) & ~unhedge
    q = np.where(active[:, :, None], q, 0.0)
    ask = np.where(np.isfinite(L.ASK), L.ASK, 0.0)[:, None, :]
    bid = np.where(np.isfinite(L.BID), L.BID, 0.0)[:, None, :]
    cost = np.where(q > 0, q * ask + fee(q, ask), 0.0) + np.where(q < 0, q * bid + fee(q, bid), 0.0)
    prem = cost.sum(axis=2)
    pay = (q * L.WIN[:, None, :]).sum(axis=2)
    fees = (np.where(q > 0, fee(q, ask), 0.0) + np.where(q < 0, fee(q, bid), 0.0)).sum(axis=2)
    buy = active & (q.sum(axis=2) > 0)
    sell = active & (q.sum(axis=2) < 0)
    return {"prem": prem, "pay": pay, "fees": fees, "unhedge": unhedge, "active": active,
            "buy": buy, "sell": sell, "contracts": np.abs(q).sum(axis=2)}


def rain_leg(hw: np.ndarray, R: DayRain, depth_cap: int | None = None) -> dict:
    q = np.rint(hw)
    if depth_cap is not None:
        q = np.clip(q, -depth_cap, depth_cap)
    need = q != 0
    bad = ((q > 0) & R.nobuy[:, None]) | ((q < 0) & R.nosell[:, None])
    unhedge = need & (bad | ~R.avail[:, None])
    active = need & ~unhedge
    q = np.where(active, q, 0.0)
    ask = np.where(np.isfinite(R.ask), R.ask, 0.0)[:, None]
    bid = np.where(np.isfinite(R.bid), R.bid, 0.0)[:, None]
    f = np.where(q > 0, fee(q, ask), 0.0) + np.where(q < 0, fee(q, bid), 0.0)
    prem = np.where(q > 0, q * ask, 0.0) + np.where(q < 0, q * bid, 0.0) + f
    pay = q * R.yes[:, None]
    return {"prem": prem, "pay": pay, "fees": f, "unhedge": unhedge, "active": active,
            "buy": active & (q > 0), "sell": active & (q < 0), "contracts": np.abs(q)}
