"""The Ledger protocol the routes call (Pattern 2). Behaviour differs by adapter, never by `if mode` in a
handler. Every write returns an Execution envelope: `done` (sim, anvil server-signed) or
`needs_signature` (testnet, or anvil with ANVIL_SERVER_SIGNS_USERS=0).
"""
from __future__ import annotations

from typing import Protocol

from wi.engine.state import Revert

from ..envelope import ApiError

REVERTS = {
    "InsufficientBalance": (409, "INSUFFICIENT_BALANCE"), "InsufficientShares": (409, "INSUFFICIENT_BALANCE"),
    "InsufficientWI": (409, "INSUFFICIENT_BALANCE"), "InsufficientCash": (409, "POOL_UTILIZATION"),
    "ExposureCap": (409, "POOL_UTILIZATION"), "JuniorMinimum": (409, "POOL_UTILIZATION"),
    "NoJunior": (409, "POOL_UTILIZATION"), "SeniorClosed": (409, "POOL_UTILIZATION"),
    "ExposureCapEngine": (409, "CAP_EXCEEDED"), "OnlyJuniorDepositor": (403, "FORBIDDEN"),
    "AuctionClosed": (409, "AUCTION_CLOSED"), "HouseCutoff": (409, "AUCTION_CLOSED"), "BookFull": (409, "ORDER_LIMIT"),
    "SalesClosed": (409, "QUOTE_EXPIRED"), "QuoteExpired": (409, "QUOTE_EXPIRED"), "NonceUsed": (409, "QUOTE_EXPIRED"),
    "TooEarly": (409, "AUCTION_OPEN"), "NotClaimable": (409, "VALIDATION"), "AlreadyClaimed": (409, "VALIDATION"),
    "NotRequestOwner": (403, "FORBIDDEN"), "NotCancellable": (409, "NOT_CANCELLABLE"),
    "NotLapsed": (409, "VALIDATION"), "ClaimWindowClosed": (409, "VALIDATION"),
    "ZeroAmount": (422, "VALIDATION"), "ZeroQty": (422, "VALIDATION"), "BadTick": (422, "VALIDATION"),
}


def revert_error(e: Revert) -> ApiError:
    status, code = REVERTS.get(e.name, (409, "VALIDATION"))
    return ApiError(status, code, f"Rejected: {e.name}", str(e))


class Ledger(Protocol):
    mode: str

    def health(self) -> dict: ...
    def config(self) -> dict: ...
