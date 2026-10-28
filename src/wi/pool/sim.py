"""One market-day of the residual / station-leg call auction on history (PREREG "Auction").

Everything a market-day needs is decided at the cutoff: the fair value mu (from candles ending
<= cutoff, or residual climatology through year D-1), the businesses' signed units (1951-2020
weather only), seeded loadings, and the house schedule. Settlement values enter only in
`settle_market`, after clearing.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from wi.auction.clear import Order, clear
from wi.pool.quote import inner_ticks, schedule


@dataclass
class Leg:
    name: str          # "station" | "residual"
    width: float       # $ range of one business-facing unit: 6 (heat cover) or 12 (residual)
    offset: float      # scalar price = (dollar price + offset) / width: 0 (station) or 6 (residual)


STATION = Leg("station", 6.0, 0.0)
RESIDUAL = Leg("residual", 12.0, 6.0)


def business_orders(h: np.ndarray, leg: Leg, mu: float, spread_scale: np.ndarray | float, loads: np.ndarray,
                    perm: np.ndarray) -> tuple[list[Order], np.ndarray, np.ndarray, np.ndarray]:
    """Orders for businesses with signed units h ($1/degF units; + = buys heat cover).

    Station leg: buyer limit mu(1+l), seller limit mu - l(6-mu). Residual: mu +/- l*MAD.
    Returns (orders in arrival order, is_bid, tick, qty) with arrays aligned to `orders`."""
    qty = np.rint(np.abs(h) * leg.width).astype(np.int64)
    is_bid = h > 0
    if leg.name == "station":
        lim = np.where(is_bid, mu * (1 + loads), mu - loads * (leg.width - mu))
    else:
        lim = np.where(is_bid, mu + loads * spread_scale, mu - loads * spread_scale)
    sc = 100.0 * (lim + leg.offset) / leg.width
    tick = np.where(is_bid, np.floor(sc + 1e-9), np.ceil(sc - 1e-9)).astype(np.int64)
    tick = np.clip(tick, 1, 99)
    keep = perm[qty[perm] > 0]
    orders = [Order(int(i), bool(is_bid[i]), int(tick[i]), int(qty[i])) for i in keep]
    return orders, is_bid[keep], tick[keep], qty[keep]


def run_market(h: np.ndarray, leg: Leg, mu: float, spread_scale, rng: np.random.Generator,
               charge_sell: float, charge_buy: float, capacity_usd: float) -> dict:
    """Build orders, append the house schedule (last in time priority), clear."""
    n = len(h)
    loads = rng.uniform(0.0, 0.25, size=n)
    perm = rng.permutation(n)
    orders, is_bid, tick, qty = business_orders(h, leg, mu, spread_scale, loads, perm)
    mu_s = (mu + leg.offset) / leg.width
    bt, at = inner_ticks(mu_s, charge_sell, charge_buy, leg.width)
    house = schedule(bt, at, capacity_usd)
    base = len(orders)
    for k, (ib, t, q) in enumerate(house):
        orders.append(Order(10_000_000 + k, ib, t, q))
    r = clear(orders)
    f = np.array(r.fills[:base], dtype=np.int64)
    hf = r.fills[base:]
    house_bid = sum(q for (ib, _, _), q in zip(house, hf) if ib)
    house_off = sum(q for (ib, _, _), q in zip(house, hf) if not ib)
    cap_bid = sum(q for ib, _, q in house if ib)
    cap_off = sum(q for ib, _, q in house if not ib)
    return dict(r=r, mu_s=mu_s, bid_tick=bt, ask_tick=at, is_bid=is_bid, tick=tick, qty=qty, fills=f,
                house_bid=house_bid, house_off=house_off, cap_bid=cap_bid, cap_off=cap_off)


def fees(m: dict, bps_list=(0, 10, 25, 50)) -> dict:
    """Protocol fee income ($) on hedger fills: bps of notional, and CoW-style 50 % of price
    improvement vs limit capped at 0.98 % of notional."""
    p = m["r"].p_star
    f, t, ib = m["fills"], m["tick"], m["is_bid"]
    notional = f.sum() * 1.0                                   # $1 per scalar unit
    impr = np.where(ib, t - p, p - t) / 100.0 * f               # $ improvement per order
    cow = np.minimum(0.5 * impr, 0.0098 * f).sum()
    out = {f"bps{b}": b / 1e4 * notional for b in bps_list}
    out["cow50"] = float(cow)
    out["hedger_notional"] = float(notional)
    out["hedger_improvement"] = float(impr.sum())
    return out


def settle_market(m: dict, x: float) -> dict:
    """House markout at settlement; x = long payout per scalar unit in [0, 1]."""
    p = m["r"].p_star / 100.0
    mo = (x - p) * m["house_bid"] + (p - x) * m["house_off"]
    return dict(mo_settle=float(mo))
