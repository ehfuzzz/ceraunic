"""Kalshi daily-high ladder mapping and hedge-time quotes for EVAL-06.

DUPLICATION NOTE (for the seat to merge): Phase 2's src/wi/eval/ladder.py and fees.py did not exist
when EVAL-06 was pre-registered (13:22Z); they appeared at ~13:23Z while this run was in progress.
Bracket semantics and the scalar fee now delegate to them when importable (fallback below is the
same rule). What stays here: the vectorised quote lookup with the pre-registered 6 h staleness
limit (PREREG C15; Phase 2's QuoteSeries.at has no staleness limit) and the sell-side no-bid rule.
The rule (07-RESEARCH Pattern 8, CONVENTIONS §5):
  - bracket integer sets: between f..c inclusive; greater f -> T >= f+1; less c -> T <= c-1
    (ins1 used c for the bottom bracket; off by one)
  - representative value r_b: (f+c)/2 between, f+1 greater, c-1 less
  - price at horizon H: close of the last hourly candle with end time <= close_time - H, at most
    6 h stale; buy-side no-offer = ask missing/stale, ask >= 0.99 with bid < 0.90, or ask <= 0;
    sell-side no-bid (mirror) = bid missing/stale, bid <= 0.01 with ask > 0.10
  - taker fee per order = ceil-to-cent(0.07 * C * P * (1 - P))
  - payout from the Kalshi `result` (TWC-settled), never recomputed from CLI
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
QUOTES = ROOT / "data" / "cache" / "elasticity" / "ladder_quotes.parquet"
HORIZONS_H = (24, 30, 12)
STALE_H = 6
SERIES = ("KXHIGHNY", "KXHIGHCHI", "KXRAINNYC")


try:  # Phase 2 shared modules (preferred)
    from wi.eval.fees import kalshi_fee as _p2_fee
    from wi.eval.ladder import Bracket as _P2Bracket
    PHASE2 = True
except ImportError:  # pragma: no cover
    PHASE2 = False


def kalshi_fee(contracts: float, price: float) -> float:
    c = abs(contracts)
    if c == 0 or not (0 < price < 1):
        return 0.0
    if PHASE2:
        return _p2_fee(c, price)
    # round to 1e-9 first so float noise (0.0700000001 cents) does not add a cent
    return math.ceil(round(0.07 * c * price * (1 - price) * 100, 9)) / 100


def bracket_bounds(strike_type: str, floor, cap) -> tuple[float, float]:
    """Inclusive integer bounds [lo, hi] of a daily-high bracket (inf for open ends)."""
    if PHASE2:
        b = _P2Bracket("x", strike_type, None if strike_type == "less" else float(floor),
                       None if strike_type == "greater" else float(cap))
        if strike_type not in ("between", "greater", "less"):
            raise ValueError(strike_type)
        return b.lo, b.hi
    if strike_type == "between":
        return float(floor), float(cap)
    if strike_type == "greater":
        return float(floor) + 1, math.inf
    if strike_type == "less":
        return -math.inf, float(cap) - 1
    raise ValueError(strike_type)


def rep_value(strike_type: str, floor, cap) -> float:
    if PHASE2 and strike_type in ("between", "greater", "less"):
        return _P2Bracket("x", strike_type, None if strike_type == "less" else float(floor),
                          None if strike_type == "greater" else float(cap)).rep
    if strike_type == "between":
        return (float(floor) + float(cap)) / 2
    if strike_type == "greater":
        return float(floor) + 1
    if strike_type == "less":
        return float(cap) - 1
    raise ValueError(strike_type)


def ladder_is_partition(rows: pd.DataFrame) -> bool:
    """True if the event's brackets tile the integers: one `less`, contiguous betweens, one `greater`."""
    b = sorted(bracket_bounds(r.strike_type, r.floor_strike, r.cap_strike) for r in rows.itertuples())
    if not b or b[0][0] != -math.inf or b[-1][1] != math.inf:
        return False
    for (lo1, hi1), (lo2, hi2) in zip(b, b[1:]):
        if lo2 != hi1 + 1:
            return False
    return True


def no_offer_buy(ask, bid) -> bool:
    if ask is None or not np.isfinite(ask) or ask <= 0:
        return True
    return bool(ask >= 0.99 and (bid is None or not np.isfinite(bid) or bid < 0.90))


def no_bid_sell(ask, bid) -> bool:
    if bid is None or not np.isfinite(bid) or bid <= 0:
        return True
    return bool(bid <= 0.01 and (ask is None or not np.isfinite(ask) or ask > 0.10))


def price_at(candles: pd.DataFrame, decision_ts: pd.Timestamp) -> tuple[float, float]:
    """(ask, bid) at a decision time from one market's candles (ts = candle END, UTC).
    Uses only candles ending at or before decision_ts, at most STALE_H hours old."""
    c = candles[(candles["ts"] <= decision_ts) & (candles["ts"] > decision_ts - pd.Timedelta(hours=STALE_H))]
    if c.empty:
        return (np.nan, np.nan)
    last = c.loc[c["ts"].idxmax()]
    return float(last["yes_ask_close"]), float(last["yes_bid_close"])


def quotes_at(mk: pd.DataFrame, c: pd.DataFrame, H: int) -> tuple[np.ndarray, np.ndarray]:
    """Vectorised price_at for many markets: for each (market_ticker, close_time) row, the
    yes ask/bid close of the last candle with ts <= close_time - H hours and ts > that - 6 h.
    c: market_ticker, ts (candle end, UTC), yes_ask_close, yes_bid_close."""
    d = mk[["market_ticker", "close_time"]].reset_index(drop=True).copy()
    d["_row"] = np.arange(len(d))
    d["dec"] = (d["close_time"] - pd.Timedelta(hours=H)).astype("datetime64[us, UTC]")
    d = d.sort_values("dec")
    cc = c.rename(columns={"ts": "cts"}).copy()
    cc["cts"] = cc["cts"].astype("datetime64[us, UTC]")
    cc = cc.sort_values("cts")
    j = pd.merge_asof(d, cc, left_on="dec", right_on="cts", by="market_ticker", direction="backward",
                      tolerance=pd.Timedelta(hours=STALE_H) - pd.Timedelta(microseconds=1))
    j = j.sort_values("_row")
    return j["yes_ask_close"].to_numpy(float), j["yes_bid_close"].to_numpy(float)


def build_quotes(start="2023-01-01", end="2026-06-30") -> pd.DataFrame:
    """One row per market (KXHIGHNY/KXHIGHCHI brackets, KXRAINNYC) with bounds, result and
    ask/bid at each horizon. Vectorised with merge_asof (same rule as price_at)."""
    m = pd.read_parquet(ROOT / "data/cache/kalshi/markets.parquet")
    m = m[m.series_ticker.isin(SERIES) & m.settled & (m.event_date >= start) & (m.event_date <= end)].copy()
    c = pd.read_parquet(ROOT / "data/cache/kalshi/candles.parquet",
                        columns=["market_ticker", "ts", "yes_ask_close", "yes_bid_close"])
    c = c[c.market_ticker.isin(set(m.market_ticker))].sort_values("ts")
    c["ts"] = c["ts"].astype("datetime64[us, UTC]")
    out = m[["series_ticker", "event_ticker", "market_ticker", "event_date", "strike_type",
             "floor_strike", "cap_strike", "result", "close_time"]].copy()
    for H in HORIZONS_H:
        a, b = quotes_at(out[["market_ticker", "close_time"]], c, H)
        out[f"ask_{H}"] = a
        out[f"bid_{H}"] = b
    heat = out.series_ticker != "KXRAINNYC"
    out.loc[heat, "rep"] = [rep_value(r.strike_type, r.floor_strike, r.cap_strike) for r in out[heat].itertuples()]
    ok = {}
    for ev, g in out[heat].groupby("event_ticker"):
        ok[ev] = ladder_is_partition(g) and (g.result == "yes").sum() == 1
    out["event_ok"] = out["event_ticker"].map(ok).fillna(out.series_ticker == "KXRAINNYC")
    out["date"] = out["event_date"].dt.date
    QUOTES.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(QUOTES, index=False)
    return out


def load_quotes() -> pd.DataFrame:
    return pd.read_parquet(QUOTES)


if __name__ == "__main__":
    q = build_quotes()
    print(q.groupby("series_ticker").agg(markets=("market_ticker", "size"), events=("event_ticker", "nunique"),
                                         ok=("event_ok", "mean"), ask24_nan=("ask_24", lambda s: s.isna().mean())))
