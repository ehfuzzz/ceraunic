"""Engine state: one plain dict of JSON-able ints / strings / bools / lists / dicts with string keys.

The state hash is sha256 of its canonical JSON (units.canonical_json refuses floats). Nothing here
reads a clock, a file or the network. Standard library only.
"""
from __future__ import annotations

import json
from typing import Any

from .units import DAY_S, UNIT, canonical_json, sha256_hex

# SPEC section 17 placeholders (v0 values). reports/eval-04-05/handoff.json (13:48Z) carries no
# u_max / alpha / beta / gamma values, so these stay the SPEC placeholders.
DEFAULT_PARAMS: dict[str, int] = {
    "capBps": 8000,
    "alphaBps": 1000,
    "betaBps": 2000,
    "gammaBps": 3000,
    "jMinBps": 2000,
    "minJuniorForSenior": 1_000 * UNIT,
    "seniorPremiumBps": 30,  # ≈ 20 % of the simulated book's 1.5 % kept margin (SPEC §17, 07-CONTEXT 14:40Z)
    "haircutCapBps": 3000,
    "withdrawDelay": 12 * DAY_S,  # = houseReturnWindow + 2 d (seat ruling 2026-09-30; PoolVault guard)
    "withdrawClaimWindow": 3 * DAY_S,  # PoolVault.CLAIM_WINDOW: a matured request lapses after this (SPEC 8.2)
    "unstakeCooldown": 12 * DAY_S,
    "houseReturnWindow": 10 * DAY_S,
    "feeNotionalBps": 10,
    "feeMarginBps": 1000,
    "auctionFeePerUnit": 0,
    "rfqFeePerUnit": 0,
    "riskLoadBps": 200,
    "minPremiumE6": 10_000,
    "slipBufferCents": 1,
    # house quoting (SPEC 6.6): minHalfTicks, z (bps: 10000 = 1.0), buffer (ticks), k (ppm tick per
    # unit of inventory), level step (ticks), plus the per-level size cap (engine choice, 07-SUMMARY)
    "minHalfTicks": 1,
    "zBps": 10_000,
    "bufferTicks": 1,
    "kInvPpm": 0,
    "levelStepTicks": 1,
    "houseLevels": 3,
    "houseLevelMaxQty": 100,
    "historyDays": 60,
    "maxOrders": 200,  # non-house orders per book; house orders are exempt (08-HARDEN #2)
    "maxOrdersPerTrader": 20,  # per (book, non-house address)
    "minOrderEscrowE6": 1_000_000,  # 1 USDC escrow per non-house order
    "contractStepCenti": 100,
    "candleCapCenti": 3_000,
    "bookBandCents": 3,
    "bookMaxAgeS": 120,
    "maxReportAge": 24 * 3600,
    "saleCutoffOffset": 2 * 3600 + 15 * 60,
    "houseCutoffOffset": 2 * 3600 + 30 * 60,
    "cutoffOffset": 3 * 3600,
    "bindByOffset": 4 * 3600 + 30 * 60,
    "basisRangeTenths": 50,
    "hedgeLeadS": DAY_S,  # decision time T = close_time - 24 h
}


class Revert(Exception):
    """A rejected action (chain `revert`). `.name` matches the Solidity custom error where one exists."""

    def __init__(self, name: str, detail: str = ""):
        super().__init__(f"{name}: {detail}" if detail else name)
        self.name = name


class InvariantError(AssertionError):
    """A SPEC section 12 invariant failed after an event: the engine state is corrupt."""


def new_state(world: dict) -> dict:
    canonical_json(world)  # the world file must be canonical-JSON clean too
    return {
        "world": world,
        "params": {},
        "funded": 0,
        "bal": {},
        "indices": {},
        "obs": {},
        "markets": {},
        "orders": {},
        "nextOrderId": 1,
        "pos": {},
        "quotes": {},
        "nonces": {},
        "policies": {},
        "nextPolicyId": 1,
        "strips": {},
        "nextStripId": 1,
        "pm": {"escrow": 0, "margin": {}},
        "pool": {
            "senior": 0, "junior": 0, "reserved": 0, "deployed": 0, "cash": 0,
            "seniorSupply": 0, "juniorSupply": 0, "seniorShares": {}, "juniorShares": {},
            "deployedByDay": {}, "openPolicies": {}, "dayPnl": {}, "closed": {}, "houseDone": {},
            "withdrawals": {}, "nextWithdrawId": 1,
        },
        "wi": {
            "supply": int(world.get("wiSupply", 0)), "burned": 0,
            "bal": {a: int(v) for a, v in sorted(world.get("wiBalances", {}).items())},
            "totalStaked": 0, "totalShares": 0, "shares": {}, "unstakes": {}, "nextUnstakeId": 1,
            "haircutDays": {},
        },
        "house": {"free": 0, "ledger": {}},
        "hedges": {},
        "rfq": {"requests": {}, "quotes": {}, "filled": {}, "nonceFloor": {}, "count": 0},
        "stats": {"events": 0},
    }


def P(st: dict, key: str) -> int:
    """Current value of an integer parameter (ParamsSet overrides the SPEC default)."""
    v = st["params"].get(key)
    return DEFAULT_PARAMS[key] if v is None else v


def role(st: dict, name: str) -> str:
    return st["world"]["roles"][name]


def is_house(st: dict, addr: str) -> bool:
    return addr == st["world"]["roles"]["house"]


def dkey(day: int) -> str:
    return str(day)


def obs_key(index_id: str, day: int) -> str:
    return f"{index_id}:{day}"


def pos_key(market: str, trader: str) -> str:
    return f"{market}|{trader}"


def add(d: dict, k: str, v: int) -> None:
    d[k] = d.get(k, 0) + v


def state_json(st: dict) -> bytes:
    return canonical_json(st)


def state_hash(st: dict) -> str:
    return sha256_hex(canonical_json(st))


def copy_state(st: dict) -> dict:
    return json.loads(canonical_json(st))


def get(d: dict, k: str, default: Any = 0) -> Any:
    return d.get(k, default)
