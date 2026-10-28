"""Engine-side exposure caps C3-C5 (docs/SPEC.md section 8.4). Full collateral, no hedge credit.

Exposure of a group = policy reserves (units x UNIT while Bought, boundUnits x UNIT while Bound) +
house auction escrow on unclaimed orders + house position `paid` on unsettled positions (auction
fills and RFQ collateral), grouped by the index registry: (indexId, day), (station, day), (metro, day).
Caps are fractions of current capital. C6 (house station units per series-day within recorded depth)
is enforced where the hedge fills (hedge.h_hedge_filled).
"""
from __future__ import annotations

from .pool import capital
from .state import P, Revert, is_house
from .units import BPS, UNIT


def _groups(st: dict, index_id: str, day: int) -> list[tuple]:
    idx = st["indices"][index_id]
    return [("idx", index_id, day), ("sta", idx["station"], day), ("met", idx["metro"], day)]


def exposures(st: dict) -> dict[tuple, int]:
    out: dict[tuple, int] = {}

    def put(index_id: str, day: int, amt: int) -> None:
        if amt:
            for g in _groups(st, index_id, day):
                out[g] = out.get(g, 0) + amt

    for pol in st["policies"].values():
        m = st["markets"][pol["market"]]
        if pol["status"] == "Bought":
            put(m["indexId"], m["day"], pol["units"] * UNIT)
        elif pol["status"] == "Bound":
            put(m["indexId"], m["day"], pol["boundUnits"] * UNIT)
    for o in st["orders"].values():
        if not o["claimed"] and is_house(st, o["trader"]):
            m = st["markets"][o["market"]]
            put(m["indexId"], m["day"], o["escrow"])
    house = st["world"]["roles"]["house"]
    for mid, m in st["markets"].items():
        ps = st["pos"].get(f"{mid}|{house}")
        if ps and not ps["done"]:
            put(m["indexId"], m["day"], ps["paid"])
    return out


def limits(st: dict) -> dict[str, int]:
    cap = capital(st["pool"])
    return {"idx": P(st, "alphaBps") * cap, "sta": P(st, "betaBps") * cap, "met": P(st, "gammaBps") * cap}


def breaches(st: dict, index_id: str, day: int, extra: int = 0, exp: dict | None = None) -> list[str]:
    """Names of C3/C4/C5 that would fail for (index_id, day) with `extra` more exposure (bps-scaled compare)."""
    exp = exposures(st) if exp is None else exp
    lim = limits(st)
    names = {"idx": "C3", "sta": "C4", "met": "C5"}
    out = []
    for g in _groups(st, index_id, day):
        if (exp.get(g, 0) + extra) * BPS > lim[g[0]]:
            out.append(names[g[0]])
    return out


def check_caps(st: dict, index_id: str, day: int, extra: int = 0) -> None:
    b = breaches(st, index_id, day, extra)
    if b:
        raise Revert("ExposureCapEngine", ",".join(b))


def headroom(st: dict, index_id: str, day: int, exp: dict | None = None) -> int:
    """Largest extra exposure (base units) that keeps C3-C5 for (index_id, day)."""
    exp = exposures(st) if exp is None else exp
    lim = limits(st)
    room = None
    for g in _groups(st, index_id, day):
        r = lim[g[0]] // BPS - exp.get(g, 0)
        room = r if room is None else min(room, r)
    return max(0, room or 0)
