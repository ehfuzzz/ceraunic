"""Kalshi trading fee (quadratic taker fee). Shared by the Phase 2 evaluation and the Phase 7 engine.

fee per order = ceil to the cent of rate × C × P × (1 − P), C = contracts in the order, P = price in dollars.
rate = 0.07 for series with `fee_type: quadratic, fee_multiplier: 1` (KXHIGH*, KXRAIN*). Confidence MEDIUM:
several secondary sources and Kalshi's worked example (0.07 × 0.055 × 0.945 per contract) agree; the official
fee PDF could not be fetched (04-RESEARCH Pitfall 7, 07-RESEARCH Pattern 8).
"""
from __future__ import annotations

import math

TAKER_RATE = 0.07


def fee_unrounded(contracts: float, price: float, rate: float = TAKER_RATE) -> float:
    """Model fee before the per-order cent rounding."""
    if contracts <= 0 or price <= 0 or price >= 1:
        return 0.0
    return rate * contracts * price * (1.0 - price)


def kalshi_fee(contracts: float, price: float, rate: float = TAKER_RATE) -> float:
    """Fee for one order, rounded UP to the next cent.

    The product is rounded to 1e-9 dollars-in-cents first so binary float noise (0.07·100·0.25·100 =
    175.00000000000003) does not add a phantom cent; a true fraction of a cent always rounds up."""
    raw = fee_unrounded(contracts, price, rate)
    if raw <= 0:
        return 0.0
    return math.ceil(round(raw * 100.0, 9)) / 100.0


def order_fees(orders: dict[str, tuple[float, float]], rate: float = TAKER_RATE) -> float:
    """Sum of per-order fees for {ticker: (contracts, price)}; each rung is its own order."""
    return sum(kalshi_fee(c, p, rate) for c, p in orders.values())
