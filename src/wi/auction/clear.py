"""Uniform-price call auction clearing: THE one rule shared by Phase 4 (history simulation),
Phase 7 (wi.engine) and Phase 8 (Solidity BatchAuction.clear / claim).

Standard library only, integers only (no floats, no pandas): the engine API bundle imports this.

THE CLEARING RULE (fixed 2026-09-30; 07-CONTEXT item 2, 08-RESEARCH Pattern 2)
-------------------------------------------------------------------------------
Instrument. One fully collateralised scalar unit per market: long receives L(x) in [0, UNIT] base
units, short receives UNIT - L(x); UNIT = 1_000_000 (= $1). Prices are integer ticks t in 1..99
cents; TICK = 10_000 base units. A bid at tick t escrows t*TICK per unit; an offer at tick t
escrows (100 - t)*TICK per unit. Quantities are positive integers (MIN_QTY = 1).

Price. With D[p] = total bid qty at ticks >= p and S[p] = total offer qty at ticks <= p, scan
p = 1..99 in ascending order and choose p* that
  1. maximises executable volume V(p) = min(D[p], S[p]); then
  2. minimises imbalance |D[p] - S[p]|; then
  3. takes the midpoint of the tied range, floor((lo + hi) / 2), where lo / hi are the first /
     last ticks that achieve the best (V, imbalance) pair. The tied range is contiguous because
     V is unimodal and D - S is monotone.
If the best V is 0 nothing trades and every order is refunded in full. Q* = V(p*).

Allocation: price-time priority at the marginal tick.
  tb = highest tick with D[tb] >= Q*; mb = Q* - D[tb + 1]   (marginal bid fill)
  to = lowest tick with S[to] >= Q*;  mo = Q* - S[to - 1]   (marginal offer fill)
  Each order carries `ahead` = qty already queued at its (side, tick) when it arrived (arrival
  order = the order of the input sequence). A bid fills qty if tick > tb, clamp(mb - ahead, 0,
  qty) if tick == tb, else 0. Offers mirror this at `to` (tick < to fills fully).
  tb >= p* >= to, so no fill violates its limit.

Cash. Everyone trades at p*: a filled bid pays fill * p* * TICK, a filled offer posts
fill * (100 - p*) * TICK; each order gets back escrow - cost. Therefore
  sum(bid fills) == sum(offer fills) == Q*   and   sum(costs) == Q* * UNIT   exactly;
the auction moves Q* * UNIT of collateral to the market and nothing is minted or burned.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

UNIT = 1_000_000
TICK = 10_000
TICKS = 99


@dataclass(frozen=True)
class Order:
    oid: int
    is_bid: bool
    tick: int
    qty: int


@dataclass(frozen=True)
class ClearResult:
    p_star: int            # 0 when nothing trades
    q_star: int
    tb: int
    mb: int
    to: int
    mo: int
    fills: tuple[int, ...]     # aligned with the input order sequence
    escrow: tuple[int, ...]    # base units escrowed per order
    cost: tuple[int, ...]      # base units kept per order (paid or posted at p*)

    @property
    def refund(self) -> tuple[int, ...]:
        return tuple(e - c for e, c in zip(self.escrow, self.cost))


def _check(o: Order) -> None:
    for name in ("oid", "tick", "qty"):
        v = getattr(o, name)
        if isinstance(v, bool) or not isinstance(v, int):
            raise TypeError(f"order {name} must be int, got {type(v).__name__}")
    if not isinstance(o.is_bid, bool):
        raise TypeError("order is_bid must be bool")
    if not 1 <= o.tick <= TICKS:
        raise ValueError(f"tick {o.tick} outside 1..{TICKS}")
    if o.qty < 1:
        raise ValueError("qty must be >= 1")


def escrow_of(o: Order) -> int:
    return o.qty * (o.tick if o.is_bid else 100 - o.tick) * TICK


def clear(orders: Sequence[Order]) -> ClearResult:
    """Clear one market's call auction under THE rule in the module docstring."""
    bid_lvl = [0] * (TICKS + 2)
    off_lvl = [0] * (TICKS + 2)
    ahead: list[int] = []
    for o in orders:
        _check(o)
        lvl = bid_lvl if o.is_bid else off_lvl
        ahead.append(lvl[o.tick])
        lvl[o.tick] += o.qty
    escrow = tuple(escrow_of(o) for o in orders)

    # D[p] = bids at ticks >= p (D[100] = 0); S accumulates offers at ticks <= p.
    D = [0] * (TICKS + 2)
    for p in range(TICKS, 0, -1):
        D[p] = D[p + 1] + bid_lvl[p]
    S = 0
    best_v, best_imb, lo, hi = 0, None, 0, 0
    for p in range(1, TICKS + 1):
        S += off_lvl[p]
        v = D[p] if D[p] < S else S
        imb = D[p] - S if D[p] > S else S - D[p]
        if v > best_v or (v == best_v and v != 0 and imb < best_imb):
            best_v, best_imb, lo, hi = v, imb, p, p
        elif v == best_v and v != 0 and imb == best_imb:
            hi = p
    n = len(orders)
    if best_v == 0:
        return ClearResult(0, 0, 0, 0, 0, 0, (0,) * n, escrow, (0,) * n)

    q = best_v
    p_star = (lo + hi) // 2
    tb = TICKS
    while D[tb] < q:
        tb -= 1
    mb = q - D[tb + 1]
    below, to = 0, 1
    while below + off_lvl[to] < q:
        below += off_lvl[to]
        to += 1
    mo = q - below

    fills = []
    cost = []
    for o, a in zip(orders, ahead):
        if o.is_bid:
            if o.tick > tb:
                f = o.qty
            elif o.tick == tb:
                f = min(max(mb - a, 0), o.qty)
            else:
                f = 0
            c = f * p_star * TICK
        else:
            if o.tick < to:
                f = o.qty
            elif o.tick == to:
                f = min(max(mo - a, 0), o.qty)
            else:
                f = 0
            c = f * (100 - p_star) * TICK
        fills.append(f)
        cost.append(c)
    return ClearResult(p_star, q, tb, mb, to, mo, tuple(fills), escrow, tuple(cost))


def curves(orders: Sequence[Order]) -> tuple[list[int], list[int]]:
    """Aggregate demand D[p] and supply S[p] for p = 1..99 (index 0 unused), for reporting."""
    bid_lvl = [0] * (TICKS + 2)
    off_lvl = [0] * (TICKS + 2)
    for o in orders:
        (bid_lvl if o.is_bid else off_lvl)[o.tick] += o.qty
    D = [0] * (TICKS + 2)
    for p in range(TICKS, 0, -1):
        D[p] = D[p + 1] + bid_lvl[p]
    S = [0] * (TICKS + 2)
    for p in range(1, TICKS + 1):
        S[p] = S[p - 1] + off_lvl[p]
    return D[: TICKS + 1], S[: TICKS + 1]
