"""Index registry, markets and the business-facing payout families (docs/SPEC.md sections 2, 3, 4).

Handlers: IndexRegistered, MarketCreated. Business views are pure conversions onto the one scalar
unit: CAPPED_CALL(K, C) = long [K, K+C]; CAPPED_PUT(K, C) = short [K-C, K]; DIGITAL_ABOVE(K) = long
[K, K+1]; DIGITAL_BELOW(K) = short [K, K+1]; BASIS_SWAP(R) = [-R, +R] on the basis index.
"""
from __future__ import annotations

from .eip712 import index_id, market_id
from .state import P, Revert
from .units import UNIT, check_int64, day_start_ts

KINDS = ("CLI", "PAIR", "METRO", "RA", "RAIN", "NCG", "PRISM")

# per-source oracle windows (SPEC 9.2): fetchLag, disputeWindow, voidGrace in seconds
WINDOWS = {
    "CLI": (12 * 3600, 24 * 3600, 72 * 3600),
    "GHCND": (12 * 3600, 24 * 3600, 72 * 3600),
    "NCG": (4 * 86400 + 12 * 3600, 24 * 3600, 72 * 3600),
    "PRISM": (6 * 86400 + 12 * 3600, 24 * 3600, 72 * 3600),
}


def market_times(st: dict, day: int) -> dict:
    """Times are derived from the global offsets, never supplied by the caller (SPEC section 4)."""
    d0 = day_start_ts(day)
    return {"saleCutoff": d0 + P(st, "saleCutoffOffset"), "houseCutoff": d0 + P(st, "houseCutoffOffset"),
            "cutoff": d0 + P(st, "cutoffOffset"), "bindBy": d0 + P(st, "bindByOffset")}


# ---------------------------------------------------------------- business payout families
def family_market(family: str, strike: int, cap: int = 0, basis_range: int = 0) -> tuple[int, int, bool]:
    """(lo, hi, business_is_long) for a payout family, all in the index's own scale."""
    if family == "CAPPED_CALL":
        return strike, strike + cap, True
    if family == "CAPPED_PUT":
        return strike - cap, strike, False
    if family == "DIGITAL_ABOVE":
        return strike, strike + 1, True
    if family == "DIGITAL_BELOW":
        return strike, strike + 1, False
    if family == "BASIS_SWAP":
        return -basis_range, basis_range, True
    raise ValueError(family)


def units_for(dollars_per_deg_e6: int, cap_tenths: int) -> int:
    """units = N_E6 x C_tenths / (10 x UNIT); must be a positive integer (SPEC section 2)."""
    num = dollars_per_deg_e6 * cap_tenths
    if num % (10 * UNIT) or num <= 0:
        raise ValueError("units must be a positive integer")
    return num // (10 * UNIT)


# ---------------------------------------------------------------- handlers
def h_index_registered(st: dict, ts: int, p: dict) -> None:
    if p["indexId"] != index_id(p["name"]):
        raise Revert("BadIndexId", p["name"])
    if p["indexId"] in st["indices"]:
        raise Revert("AlreadyRegistered", p["name"])
    if p["kind"] not in KINDS or p["scale"] not in (1, 10, 100):
        raise Revert("BadConfig", p["name"])
    if p["fetchLag"] <= 0 or p["disputeWindow"] <= 0 or p["voidGrace"] <= 0:
        raise Revert("BadConfig", "windows must be positive")
    st["indices"][p["indexId"]] = {k: p[k] for k in p if k != "indexId"} | {"listedAt": ts, "active": True}


def h_market_created(st: dict, ts: int, p: dict) -> None:
    idx = st["indices"].get(p["indexId"])
    if idx is None or not idx["active"]:
        raise Revert("NotRegistered", p["indexId"])
    for v in (p["lo"], p["hi"]):
        check_int64(v)
    if p["lo"] >= p["hi"]:
        raise Revert("BadRange")
    if p["marketId"] != market_id(p["indexId"], p["day"], p["lo"], p["hi"]):
        raise Revert("BadMarketId")
    if p["marketId"] in st["markets"]:
        raise Revert("MarketExists")
    times = market_times(st, p["day"])
    for k, v in times.items():
        if p[k] != v:
            raise Revert("BadTimes", k)
    st["markets"][p["marketId"]] = {
        "indexId": p["indexId"], "day": p["day"], "lo": p["lo"], "hi": p["hi"], **times,
        "auctioned": p["auctioned"], "createdAt": ts,
        # auction book
        "levels": {"b": {}, "o": {}}, "orderIds": [], "escrow": 0, "cleared": None, "unclaimed": 0,
        # PolicyManager collateral
        "collateral": 0, "collateralIn": 0, "paidOut": 0, "traders": [],
    }


# ---------------------------------------------------------------- commands
def register_index(led, ts: int, name: str, *, kind: str, scale: int, station: str, metro: str,
                   inputs: list[str], source: str = "CLI", quorum_bps: int = 10_000) -> str:
    fl, dw, vg = WINDOWS[source]
    iid = index_id(name)
    led.emit(ts, "IndexRegistered", {"indexId": iid, "name": name, "kind": kind, "scale": scale,
                                     "station": station, "metro": metro, "inputs": list(inputs),
                                     "quorumBps": quorum_bps, "fetchLag": fl, "disputeWindow": dw,
                                     "voidGrace": vg})
    return iid


def create_market(led, ts: int, index: str, day: int, lo: int, hi: int, auctioned: bool) -> str:
    mid = market_id(index, day, lo, hi)
    if mid in led.state["markets"]:
        return mid
    led.emit(ts, "MarketCreated", {"marketId": mid, "indexId": index, "day": day, "lo": lo, "hi": hi,
                                   **market_times(led.state, day), "auctioned": auctioned})
    return mid


def index_by_name(st: dict, name: str) -> str:
    iid = index_id(name)
    if iid not in st["indices"]:
        raise KeyError(name)
    return iid
