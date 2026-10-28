"""Wire base, Execution envelope, addresses, RFC 9457 problems."""
from __future__ import annotations

import re
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, BeforeValidator, ConfigDict
from pydantic.alias_generators import to_camel

ProblemCode = Literal[
    "VALIDATION", "NOT_FOUND", "QUOTE_EXPIRED", "AUCTION_OPEN", "AUCTION_CLOSED",
    "MODE_NOT_SIM", "MODE_READ_ONLY", "OWNER_SCRIPT", "WORLD_BUSY", "MARGIN_EXCEEDED",
    "CAP_EXCEEDED", "INSUFFICIENT_BALANCE", "POOL_UTILIZATION", "ORDER_LIMIT",
    "RPC_UNAVAILABLE", "FORBIDDEN", "NOT_CANCELLABLE", "OUT_OF_WINDOW", "NO_PRICE", "CHAIN_DIVERGED",
]


class Wire(BaseModel):
    """camelCase on the wire, snake_case in Python."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


_ADDR = re.compile(r"^0x[0-9a-fA-F]{40}$")


def normalize_address(v: object) -> str:
    """Accept any case, emit EIP-55. eth_utils is imported lazily (small, but not needed at boot)."""
    if not isinstance(v, str) or not _ADDR.match(v):
        raise ValueError("address must be 0x + 40 hex chars")
    from eth_utils import to_checksum_address
    return to_checksum_address(v.lower())


Address = Annotated[str, BeforeValidator(normalize_address)]

T = TypeVar("T")
Mode = Literal["sim", "anvil", "testnet"]


class TxRequest(Wire):
    chain_id: int
    to: Address
    data: str
    value: str = "0"  # wei, decimal string
    description: str


class Execution(Wire, Generic[T]):
    mode: Mode
    status: Literal["done", "needs_signature"]
    result: T | None = None
    txs: list[TxRequest] = []


class Problem(Wire):
    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    code: ProblemCode


class ApiError(Exception):
    def __init__(self, status: int, code: str, title: str, detail: str | None = None):
        self.status, self.code, self.title, self.detail = status, code, title, detail
        super().__init__(f"{code}: {title}")
