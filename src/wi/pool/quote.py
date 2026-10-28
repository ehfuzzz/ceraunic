"""House market-maker quote schedule (04-RESEARCH Pattern 5; PREREG "House quotes").

Prices are scalar ticks (cents of $1). `rng_width` converts $/unit of the business-facing
contract to scalar: 6 for the $1/degF capped heat cover, 12 for the [-6, +6] residual.
charge per unit-day = (CoC/365) * dES, dES = Euler co-ES99 of one unit in the 30-day rolled book.
"""
from __future__ import annotations

import math


def inner_ticks(mu_scalar: float, charge_sell: float, charge_buy: float, rng_width: float) -> tuple[int, int]:
    """(bid_tick, ask_tick) around the fair value mu (scalar, in [0, 1]); charges in $ per unit."""
    fair_c = 100.0 * mu_scalar
    ask = max(math.ceil(fair_c + 100.0 * charge_sell / rng_width - 1e-9), math.floor(fair_c) + 1)
    bid = min(math.floor(fair_c - 100.0 * charge_buy / rng_width + 1e-9), math.ceil(fair_c) - 1)
    return max(1, min(99, bid)), max(1, min(99, ask))


def schedule(bid_tick: int, ask_tick: int, capacity_usd: float, levels: int = 3) -> list[tuple[bool, int, int]]:
    """House orders (is_bid, tick, qty): `levels` ticks each side, one third of capacity each.
    Full collateral per scalar unit: 1 - p for an offer, p for a bid."""
    out = []
    per = capacity_usd / levels
    for k in range(levels):
        t = ask_tick + k
        if 1 <= t <= 99:
            q = int(per // (1.0 - t / 100.0))
            if q > 0:
                out.append((False, t, q))
        t = bid_tick - k
        if 1 <= t <= 99:
            q = int(per // (t / 100.0))
            if q > 0:
                out.append((True, t, q))
    return out
