"""Kalshi bracket-ladder mapper: brackets, representative values, replicating quantities for capped calls
and puts, executable ask at a decision time (forward fill over sparse hourly candles, both candle schemas),
ladder pricing with fees, and order-book depth. Shared by the Phase 2 evaluation and the Phase 7 engine.

Conventions (docs/CONVENTIONS.md §5-6, 07-RESEARCH Pattern 8, 05-RESEARCH Pitfall 6):
- `between` f..c covers the integers f..c inclusive; representative value (f + c) / 2.
- `greater` f means T ≥ f + 1 (strictly greater than f); representative value f + 1.
- `less` c means T ≤ c − 1 (strictly less than c); representative value c − 1 (ins1 used c: off by one).
- Ask at t = the last hourly candle whose end is ≤ t. No candle after t is ever read.
- No offer: no candle ≤ t, null/non-positive ask, or ask ≥ 0.99 with bid < 0.90 (null bid = 0).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, Sequence

import numpy as np

from .fees import fee_unrounded, kalshi_fee

INF = math.inf
NO_OFFER_ASK = 0.99
NO_OFFER_BID = 0.90


# ------------------------------------------------------------------ payoffs

def call_payout(T: float, K: float, cap: float = 6.0) -> float:
    """Capped linear heat call per $1/°F unit: min(max(T − K, 0), cap)."""
    return float(min(max(T - K, 0.0), cap))


def put_payout(T: float, K: float, cap: float = 6.0) -> float:
    """Capped linear cold put per $1/°F unit: min(max(K − T, 0), cap)."""
    return float(min(max(K - T, 0.0), cap))


def payoff_fn(kind: str, K: float, cap: float = 6.0) -> Callable[[float], float]:
    if kind == "call":
        return lambda T: call_payout(T, K, cap)
    if kind == "put":
        return lambda T: put_payout(T, K, cap)
    raise ValueError(kind)


# ------------------------------------------------------------------ brackets

@dataclass(frozen=True)
class Bracket:
    ticker: str
    strike_type: str            # between | greater | less
    floor: float | None
    cap: float | None

    @property
    def lo(self) -> float:
        """Lowest integer the bracket covers (−inf for `less`)."""
        if self.strike_type == "between":
            return float(self.floor)
        if self.strike_type == "greater":
            return float(self.floor) + 1.0
        return -INF

    @property
    def hi(self) -> float:
        """Highest integer the bracket covers (+inf for `greater`)."""
        if self.strike_type == "between":
            return float(self.cap)
        if self.strike_type == "less":
            return float(self.cap) - 1.0
        return INF

    @property
    def rep(self) -> float:
        """Representative integer-°F value used to size the replicating portfolio."""
        if self.strike_type == "between":
            return (float(self.floor) + float(self.cap)) / 2.0
        if self.strike_type == "greater":
            return float(self.floor) + 1.0
        if self.strike_type == "less":
            return float(self.cap) - 1.0
        raise ValueError(self.ticker)

    @property
    def open_ended(self) -> bool:
        return self.strike_type in ("greater", "less")

    def contains(self, T: float) -> bool:
        return self.lo <= T <= self.hi

    @property
    def sort_key(self) -> float:
        return self.lo if self.strike_type != "less" else -INF


def bracket_from_market(m: Mapping) -> Bracket | None:
    """Build a Bracket from a market row/dict (API or cache columns). None if strikes are unusable."""
    st = m.get("strike_type")
    fl, cp = m.get("floor_strike"), m.get("cap_strike")
    fl = None if fl is None or (isinstance(fl, float) and math.isnan(fl)) else float(fl)
    cp = None if cp is None or (isinstance(cp, float) and math.isnan(cp)) else float(cp)
    tk = m.get("market_ticker") or m.get("ticker")
    if st == "between" and fl is not None and cp is not None and cp >= fl:
        return Bracket(tk, st, fl, cp)
    if st == "greater" and fl is not None:
        return Bracket(tk, st, fl, None)
    if st == "less" and cp is not None:
        return Bracket(tk, st, None, cp)
    return None


class Ladder:
    """One event's brackets, sorted low → high."""

    def __init__(self, brackets: Iterable[Bracket]):
        self.brackets: list[Bracket] = sorted(brackets, key=lambda b: (b.sort_key, b.hi))

    def __len__(self) -> int:
        return len(self.brackets)

    def validate(self) -> str | None:
        """None if the brackets are disjoint and contiguous integer ranges; else a reason string."""
        bs = self.brackets
        if len(bs) < 2:
            return "fewer than 2 brackets"
        for a, b in zip(bs, bs[1:]):
            if b.lo <= a.hi:
                return f"overlap {a.ticker} / {b.ticker}"
            if b.lo != a.hi + 1:
                return f"gap {a.ticker} / {b.ticker}"
        return None

    def second_floor(self) -> float:
        """ins1 strike rule: the floor of the second bracket (sorted by floor, `less` first)."""
        b = self.brackets[1]
        return b.lo

    def by_ticker(self) -> dict[str, Bracket]:
        return {b.ticker: b for b in self.brackets}

    def top_rep(self) -> float:
        return self.brackets[-1].rep

    def bracket_of(self, T: float) -> Bracket | None:
        for b in self.brackets:
            if b.contains(T):
                return b
        return None


def quantities(ladder: Ladder, payoff: Callable[[float], float], units: float = 1.0,
               step: float | None = None) -> dict[str, float]:
    """YES contracts per rung replicating `units` × payoff: q_b = units × payoff(rep_b).
    step: round each q_b to this contract step (None = keep fractional, per-unit analysis)."""
    out: dict[str, float] = {}
    for b in ladder.brackets:
        q = units * payoff(b.rep)
        if step:
            q = round(q / step) * step
        if q > 0:
            out[b.ticker] = q
    return out


def ladder_payout(ladder: Ladder, winner: str, payoff: Callable[[float], float], units: float = 1.0) -> float:
    """What the replicating portfolio pays when bracket `winner` settles YES: units × payoff(rep_winner)."""
    return units * payoff(ladder.by_ticker()[winner].rep)


# ------------------------------------------------------------------ candles and the ask at t

def _num(x) -> float | None:
    if x is None or x == "":
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def normalize_candle(raw: Mapping) -> tuple[int, float | None, float | None]:
    """(end_period_ts, yes_ask_close, yes_bid_close) from a raw API candle of either schema:
    historical `{"yes_ask": {"close": "0.42"}}` or live `{"yes_ask": {"close_dollars": "0.4200"}}`.
    Already-normalised dicts with `yes_ask_close` / `yes_bid_close` are accepted too."""
    ts = int(raw["end_period_ts"])
    if "yes_ask_close" in raw or "yes_bid_close" in raw:
        return ts, _num(raw.get("yes_ask_close")), _num(raw.get("yes_bid_close"))
    a, b = raw.get("yes_ask") or {}, raw.get("yes_bid") or {}
    ask = _num(a.get("close_dollars", a.get("close")))
    bid = _num(b.get("close_dollars", b.get("close")))
    return ts, ask, bid


class QuoteSeries:
    """Sparse hourly quotes for one market, sorted by candle end (UTC epoch seconds)."""

    __slots__ = ("ts", "ask", "bid")

    def __init__(self, ts: Sequence[int], ask: Sequence[float | None], bid: Sequence[float | None]):
        order = np.argsort(np.asarray(ts, dtype=np.int64), kind="stable")
        self.ts = np.asarray(ts, dtype=np.int64)[order]
        self.ask = np.asarray([np.nan if v is None else v for v in ask], dtype=float)[order]
        self.bid = np.asarray([np.nan if v is None else v for v in bid], dtype=float)[order]

    @classmethod
    def from_raw(cls, candles: Iterable[Mapping]) -> "QuoteSeries":
        rows = [normalize_candle(c) for c in candles]
        return cls([r[0] for r in rows], [r[1] for r in rows], [r[2] for r in rows])

    def at(self, t: int) -> tuple[float, float, int] | None:
        """(ask, bid, candle_end) of the last candle ending at or before t; None if there is none."""
        i = int(np.searchsorted(self.ts, t, side="right")) - 1
        if i < 0:
            return None
        return float(self.ask[i]), float(self.bid[i]), int(self.ts[i])


def offer_status(q: tuple[float, float, int] | None) -> str:
    """'ok' or the no-offer reason: 'no_candle', 'null_ask', 'no_offer_rule'."""
    if q is None:
        return "no_candle"
    ask, bid, _ = q
    if math.isnan(ask) or ask <= 0:
        return "null_ask"
    bid = 0.0 if math.isnan(bid) else bid
    if ask >= NO_OFFER_ASK and bid < NO_OFFER_BID:
        return "no_offer_rule"
    return "ok"


@dataclass
class LegPrice:
    premium: float          # Σ q × ask per unit (fees excluded)
    spread: float           # Σ q × (ask − mid)
    fee: float              # per-order cent-rounded fee at the reference size, per unit
    fee_raw: float          # unrounded model fee per unit
    n_needed: int
    n_missing: int
    reasons: dict[str, int]
    max_stale_s: int
    executable: bool


def price_leg(qty: Mapping[str, float], quotes: Mapping[str, tuple[float, float, int] | None], t: int,
              ref_units: float = 10.0, contract_step: float | None = 1.0) -> LegPrice:
    """Price per-unit rung quantities `qty` at the quotes observed at time t.

    Fees are cent-rounded per rung order at a reference policy of `ref_units` units (C = ref_units × q,
    rounded to `contract_step`), then divided by ref_units so they read per unit."""
    prem = spread = fee = fee_raw = 0.0
    reasons: dict[str, int] = {}
    missing = 0
    stale = 0
    for tk, q in qty.items():
        qt = quotes.get(tk)
        st = offer_status(qt)
        if st != "ok":
            missing += 1
            reasons[st] = reasons.get(st, 0) + 1
            continue
        ask, bid, cts = qt
        bid = 0.0 if math.isnan(bid) else bid
        prem += q * ask
        spread += q * (ask - (ask + bid) / 2.0)
        c = ref_units * q
        if contract_step:
            c = round(c / contract_step) * contract_step
        fee += kalshi_fee(c, ask) / ref_units
        fee_raw += fee_unrounded(q, ask)
        stale = max(stale, t - cts)
    return LegPrice(prem, spread, fee, fee_raw, len(qty), missing, reasons, stale, missing == 0 and len(qty) > 0)


# ------------------------------------------------------------------ order books

def book_yes_asks(orderbook: Mapping) -> list[tuple[float, float]]:
    """YES ask levels [(price, qty)] best first, from a Kalshi book that lists bids only:
    YES ask = 1 − NO bid at the same quantity. Accepts `orderbook_fp` / `orderbook` wrappers and
    `no_dollars` (fixed-point strings) or `no` (cents) arrays. Levels are sorted explicitly: recorded
    arrays are ascending with the best NO bid last."""
    ob = orderbook.get("orderbook_fp") or orderbook.get("orderbook") or orderbook
    if ob.get("no_dollars") is not None:
        lv = [(float(p), float(q)) for p, q in ob.get("no_dollars") or []]
    else:
        lv = [(float(p) / 100.0, float(q)) for p, q in ob.get("no") or []]
    lv = [(round(1.0 - p, 4), q) for p, q in lv if q > 0]
    return sorted(lv, key=lambda x: x[0])


def depth_within(asks: list[tuple[float, float]], within: float = 0.03) -> tuple[float | None, float]:
    """(best ask, contracts offered at prices ≤ best ask + within)."""
    if not asks:
        return None, 0.0
    best = asks[0][0]
    return best, sum(q for p, q in asks if p <= best + within + 1e-9)


def max_units(qty: Mapping[str, float], depth: Mapping[str, float]) -> float:
    """Largest policy (units) fillable from `depth` contracts per rung: min_b depth_b / q_b."""
    vals = [depth.get(tk, 0.0) / q for tk, q in qty.items() if q > 0]
    return min(vals) if vals else 0.0
