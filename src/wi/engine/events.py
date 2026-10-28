"""Event catalogue (docs/SPEC.md section 13) as frozen dataclasses with strict field types.

Every payload is validated here before the reducer sees it: exact key set, JSON integers only
(no floats, no bools where an int is expected), addresses as 0x + 40 lowercase hex or a reserved
account, bytes32 as 0x + 64 lowercase hex. Standard library only.

Extension to the SPEC catalogue (recorded in 07-SUMMARY): `HedgeDecision.rungs[]` also carries
`depthCenti` (book depth inside the 3-cent band, or the candle cap) and `askCents` (best ask used),
so the reducer can assert I13/I14 from the log alone.
"""
from __future__ import annotations

import re
from dataclasses import asdict, make_dataclass
from typing import Any

RESERVED = ("@pool", "@treasury", "@auction", "@pm", "@kalshi", "@staking")
_ADDR = re.compile(r"^0x[0-9a-f]{40}$")
_B32 = re.compile(r"^0x[0-9a-f]{64}$")

# sub-schemas for list-of-object fields
RUNG_DECISION = (("ticker", "str"), ("needCenti", "int"), ("depthCenti", "int"), ("askCents", "int"))
RUNG_FILL = (("ticker", "str"), ("filledCenti", "int"), ("costCents", "int"), ("feeCents", "int"))
RUNG_SETTLE = (("ticker", "str"), ("result", "str"), ("filledCenti", "int"))

SCHEMA: dict[str, tuple[tuple[str, Any], ...]] = {
    "ParamsSet": (("key", "str"), ("value", "int")),
    "AccountFunded": (("account", "addr"), ("amount", "int")),
    "IndexRegistered": (("indexId", "b32"), ("name", "str"), ("kind", "str"), ("scale", "int"),
                        ("station", "str"), ("metro", "str"), ("inputs", "[str]"), ("quorumBps", "int"),
                        ("fetchLag", "int"), ("disputeWindow", "int"), ("voidGrace", "int")),
    "MarketCreated": (("marketId", "b32"), ("indexId", "b32"), ("day", "int"), ("lo", "int"), ("hi", "int"),
                      ("saleCutoff", "int"), ("houseCutoff", "int"), ("cutoff", "int"), ("bindBy", "int"),
                      ("auctioned", "bool")),
    "SeniorDeposited": (("owner", "addr"), ("amount", "int"), ("shares", "int")),
    "JuniorDeposited": (("owner", "addr"), ("amount", "int"), ("shares", "int")),
    "WithdrawRequested": (("requestId", "int"), ("owner", "addr"), ("tranche", "str"), ("shares", "int"),
                          ("claimableAt", "int")),
    "WithdrawClaimed": (("requestId", "int"), ("owner", "addr"), ("amount", "int")),
    "WithdrawCancelled": (("requestId", "int"), ("owner", "addr"), ("shares", "int")),
    "WithdrawLapsed": (("requestId", "int"), ("owner", "addr"), ("shares", "int")),
    "HouseFunded": (("day", "int"), ("amount", "int")),
    "HouseReturned": (("day", "int"), ("amount", "int"), ("deployed", "int"), ("pnl", "int")),
    "HouseWrittenOff": (("day", "int"), ("deployed", "int")),
    "DayClosed": (("day", "int"), ("juniorPnl", "int"), ("haircutBps", "int")),
    "PoolEpoch": (),
    "WIStaked": (("owner", "addr"), ("amount", "int"), ("shares", "int")),
    "WIUnstakeRequested": (("requestId", "int"), ("owner", "addr"), ("shares", "int"), ("claimableAt", "int")),
    "WIUnstakeClaimed": (("requestId", "int"), ("owner", "addr"), ("amount", "int")),
    "WIHaircut": (("day", "int"), ("bps", "int"), ("burned", "int")),
    "QuoteIssued": (("digest", "b32"), ("market", "b32"), ("buyer", "addr"), ("isLong", "bool"), ("units", "int"),
                    ("premium", "int"), ("fee", "int"), ("expiry", "int"), ("nonce", "int"), ("stationLeg", "int"),
                    ("residualLeg", "int"), ("tail", "int"), ("riskMargin", "int"), ("notionalFee", "int"),
                    ("residualMarket", "b32"), ("residualQty", "int"), ("residualTick", "int"),
                    ("deltaPpm", "int"), ("dataAsOf", "int")),
    "PolicyBought": (("policyId", "int"), ("digest", "b32"), ("market", "b32"), ("buyer", "addr"),
                     ("isLong", "bool"), ("units", "int"), ("premium", "int"), ("fee", "int")),
    "PolicyBound": (("policyId", "int"), ("residualOrderId", "int"), ("boundUnits", "int"), ("refund", "int"),
                    ("keptFee", "int"), ("toPool", "int"), ("seniorPremium", "int"), ("juniorPremium", "int")),
    "PolicySettled": (("policyId", "int"), ("x", "int"), ("payout", "int")),
    "PolicyVoided": (("policyId", "int"), ("refund", "int")),
    "StripOpened": (("stripId", "int"), ("owner", "addr"), ("indexId", "b32"), ("lo", "int"), ("hi", "int"),
                    ("isLong", "bool"), ("units", "int"), ("maxDailyPremium", "int"), ("startDay", "int"),
                    ("endDay", "int")),
    "StripClosed": (("stripId", "int"),),
    "OrderPlaced": (("orderId", "int"), ("market", "b32"), ("trader", "addr"), ("isBid", "bool"), ("tick", "int"),
                    ("qty", "int"), ("ahead", "int"), ("escrow", "int"), ("policyId", "int")),
    "AuctionCleared": (("market", "b32"), ("pStar", "int"), ("qStar", "int"), ("tb", "int"), ("to", "int"),
                       ("mb", "int"), ("mo", "int")),
    "OrderClaimed": (("orderId", "int"), ("fill", "int"), ("cost", "int"), ("fee", "int"), ("refund", "int")),
    "MarginDeposited": (("maker", "addr"), ("amount", "int")),
    "MarginWithdrawn": (("maker", "addr"), ("amount", "int")),
    "RfqRequested": (("requestId", "b32"), ("requester", "addr"), ("market", "b32"), ("requesterLong", "bool"),
                     ("qty", "int"), ("windowEnd", "int")),
    "RfqQuoted": (("requestId", "b32"), ("digest", "b32"), ("maker", "addr"), ("tick", "int"), ("maxQty", "int"),
                  ("validUntil", "int"), ("nonce", "int")),
    "RfqAccepted": (("digest", "b32"), ("market", "b32"), ("taker", "addr"), ("maker", "addr"),
                    ("takerLong", "bool"), ("tick", "int"), ("qty", "int")),
    "PositionSettled": (("market", "b32"), ("trader", "addr"), ("longQty", "int"), ("shortQty", "int"),
                        ("x", "int"), ("payout", "int")),
    "PositionRefunded": (("market", "b32"), ("trader", "addr"), ("refund", "int")),
    "ReportPosted": (("indexId", "b32"), ("day", "int"), ("value", "int"), ("revision", "int"), ("asOf", "int"),
                     ("signer", "addr"), ("vintageHash", "b32")),
    "IndexFinalized": (("indexId", "b32"), ("day", "int"), ("value", "int")),
    "IndexVoided": (("indexId", "b32"), ("day", "int")),
    "HedgeDecision": (("series", "str"), ("day", "int"), ("decisionTs", "int"), ("closeTs", "int"),
                      ("source", "str"), ("snapshotTs", "int"), ("rungs", RUNG_DECISION)),
    "HedgeFilled": (("series", "str"), ("day", "int"), ("rungs", RUNG_FILL), ("costE6", "int"),
                    ("shortfallCenti", "int")),
    "HedgeSettled": (("series", "str"), ("day", "int"), ("rungs", RUNG_SETTLE), ("payoutE6", "int")),
}


class EventError(ValueError):
    """A payload that does not match the catalogue (wrong keys or types)."""


def _check_value(kind: Any, v: Any, where: str) -> None:
    if isinstance(kind, tuple):  # list of objects with a sub-schema
        if not isinstance(v, list):
            raise EventError(f"{where}: expected list")
        for i, item in enumerate(v):
            _check_fields(kind, item, f"{where}[{i}]")
        return
    if kind == "int":
        if isinstance(v, bool) or not isinstance(v, int):
            raise EventError(f"{where}: expected int, got {type(v).__name__}")
    elif kind == "bool":
        if not isinstance(v, bool):
            raise EventError(f"{where}: expected bool")
    elif kind == "str":
        if not isinstance(v, str):
            raise EventError(f"{where}: expected str")
    elif kind == "addr":
        if not isinstance(v, str) or not (v in RESERVED or _ADDR.match(v)):
            raise EventError(f"{where}: bad address {v!r}")
    elif kind == "b32":
        if not isinstance(v, str) or not _B32.match(v):
            raise EventError(f"{where}: bad bytes32 {v!r}")
    elif kind == "[str]":
        if not isinstance(v, list) or not all(isinstance(s, str) for s in v):
            raise EventError(f"{where}: expected list of str")
    else:  # pragma: no cover
        raise EventError(f"unknown kind {kind}")


def _check_fields(schema: tuple, payload: Any, where: str) -> None:
    if not isinstance(payload, dict):
        raise EventError(f"{where}: payload must be an object")
    names = [n for n, _ in schema]
    if set(payload) != set(names):
        missing = set(names) - set(payload)
        extra = set(payload) - set(names)
        raise EventError(f"{where}: missing {sorted(missing)} extra {sorted(extra)}")
    for n, kind in schema:
        _check_value(kind, payload[n], f"{where}.{n}")


def validate(etype: str, payload: dict) -> None:
    if etype not in SCHEMA:
        raise EventError(f"unknown event type {etype!r}")
    _check_fields(SCHEMA[etype], payload, etype)


# Frozen dataclasses, one per event type (e.g. events.OrderPlaced(orderId=1, ...)). They validate on
# construction and turn into the payload dict with .payload().
def _mk(etype: str, schema: tuple):
    def __post_init__(self):
        validate(etype, asdict(self))

    def payload(self) -> dict:
        return asdict(self)

    fields = [(n, object) for n, _ in schema]
    return make_dataclass(etype, fields, frozen=True, namespace={"__post_init__": __post_init__,
                                                                  "payload": payload, "TYPE": etype})


EVENT_CLASSES = {t: _mk(t, s) for t, s in SCHEMA.items()}
globals().update(EVENT_CLASSES)


def make(etype: str, **fields) -> dict:
    """Validated payload dict for `etype`."""
    return EVENT_CLASSES[etype](**fields).payload()
