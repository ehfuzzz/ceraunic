"""Kalshi station leg on history: ladder geometry, quotes at a horizon, fair value, paper hedge.

Conventions (docs/CONVENTIONS.md 5-6, 07-RESEARCH Pattern 8): K = floor of the second bracket;
rung value v = midpoint ("between"), floor + 1 ("greater"), cap - 1 ("less"); contracts per $1/degF
unit = H(v); prices = YES ask / bid close of the last hourly candle ending <= close - horizon;
no-offer = ask >= 0.99 and bid < 0.90 (or ask <= 0); taker fee = ceil-to-cent(0.07*C*P*(1-P)).
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
SERIES = {"KXHIGHNY": "NYC", "KXHIGHTEWR": "EWR", "KXHIGHTTTN": "TTN", "KXHIGHCHI": "MDW", "KXHIGHMIA": "MIA"}
CAP = 6.0


def H(T, K):
    return np.clip(np.asarray(T, float) - np.asarray(K, float), 0.0, CAP)


def rung_value(stype: str, floor: float, cap: float) -> float:
    if stype == "between":
        return (floor + cap) / 2.0
    if stype == "greater":
        return floor + 1.0
    return cap - 1.0


def rung_low(stype: str, floor: float, cap: float) -> float:
    return -999.0 if stype == "less" else floor


def load_rungs(months=(5, 6, 7, 8, 9)) -> pd.DataFrame:
    m = pd.read_parquet(ROOT / "data" / "cache" / "kalshi" / "markets.parquet",
                        columns=["series_ticker", "event_ticker", "market_ticker", "event_date", "strike_type",
                                 "floor_strike", "cap_strike", "result", "settled", "close_time"])
    m = m[m["series_ticker"].isin(SERIES) & m["settled"] & m["event_date"].dt.month.isin(months)].copy()
    m["station"] = m["series_ticker"].map(SERIES)
    m["v"] = [rung_value(t, f, c) for t, f, c in zip(m.strike_type, m.floor_strike, m.cap_strike)]
    m["low"] = [rung_low(t, f, c) for t, f, c in zip(m.strike_type, m.floor_strike, m.cap_strike)]
    g = m.groupby("event_ticker")
    m["n_rungs"] = g["market_ticker"].transform("size")
    m["n_yes"] = g["result"].transform(lambda s: int((s == "yes").sum()))
    m = m.sort_values(["event_ticker", "low"])
    m["rank"] = m.groupby("event_ticker").cumcount()
    k = m[m["rank"] == 1].set_index("event_ticker")["floor_strike"]
    m["K"] = m["event_ticker"].map(k)
    m["Hv"] = H(m["v"], m["K"])
    return m.reset_index(drop=True)


def quotes_at(rungs: pd.DataFrame, candles: pd.DataFrame, hours_before: float, tag: str) -> pd.DataFrame:
    """Attach ask/bid (and last trade) of the last candle ending <= close - hours_before."""
    tgt = rungs[["market_ticker", "close_time"]].copy()
    tgt["t"] = (tgt["close_time"] - pd.Timedelta(hours=hours_before)).astype("datetime64[ms, UTC]")
    c = candles[["market_ticker", "ts", "yes_ask_close", "yes_bid_close"]].dropna(subset=["ts"]).copy()
    c["ts"] = c["ts"].astype("datetime64[ms, UTC]")
    tgt = tgt.sort_values("t")
    c = c.sort_values("ts")
    j = pd.merge_asof(tgt, c, left_on="t", right_on="ts", by="market_ticker", direction="backward")
    j = j.set_index("market_ticker")
    out = rungs.copy()
    out[f"ask_{tag}"] = out["market_ticker"].map(j["yes_ask_close"])
    out[f"bid_{tag}"] = out["market_ticker"].map(j["yes_bid_close"])
    out[f"cts_{tag}"] = out["market_ticker"].map(j["ts"])
    a, b = out[f"ask_{tag}"], out[f"bid_{tag}"]
    out[f"valid_{tag}"] = a.notna() & b.notna() & (a > 0) & ~((a >= 0.99) & (b < 0.90))
    return out


def fair_value(rungs: pd.DataFrame, tag: str) -> pd.DataFrame:
    """Per event: mu = sum(mid*Hv)/sum(mid), all-rungs-valid flag, overround at asks."""
    r = rungs.assign(mid=(rungs[f"ask_{tag}"] + rungs[f"bid_{tag}"]) / 2.0)
    r["midH"] = r["mid"] * r["Hv"]
    r["askH"] = r[f"ask_{tag}"] * r["Hv"]
    g = r.groupby("event_ticker")
    out = pd.DataFrame({f"mu_{tag}": g["midH"].sum() / g["mid"].sum(), f"allvalid_{tag}": g[f"valid_{tag}"].all(),
                        f"premask_{tag}": g["askH"].sum(), f"sum_mid_{tag}": g["mid"].sum()})
    return out


def fee(contracts: int, price: float) -> float:
    """Kalshi taker fee for one order: ceil to the cent of 0.07*C*P*(1-P)."""
    if contracts <= 0:
        return 0.0
    return math.ceil(round(0.07 * contracts * price * (1 - price) * 100, 9)) / 100.0


def hedge_pnl(event_rungs: pd.DataFrame, n_units: float, side: int, tag: str) -> tuple[float, float, int]:
    """Paper hedge of `n_units` $1/degF units. side=+1 buys the ladder (YES at asks), -1 sells it
    (YES at bids). Returns (P&L incl. fees and Kalshi payout, fees, contracts)."""
    pnl, fees, n_c = 0.0, 0.0, 0
    for hv, a, b, res in zip(event_rungs["Hv"], event_rungs[f"ask_{tag}"], event_rungs[f"bid_{tag}"], event_rungs["result"]):
        c = int(round(n_units * hv))
        if c <= 0:
            continue
        pay = 1.0 if res == "yes" else 0.0
        px = a if side > 0 else b
        f = fee(c, px)
        pnl += side * c * (pay - px) - f
        fees += f
        n_c += c
    return pnl, fees, n_c
