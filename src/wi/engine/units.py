"""Integer units, payout L(x), truncating division, canonical JSON and hashing.

The one place where scales and rounding live (docs/SPEC.md sections 1, 2 and 13). Pure Python,
standard library only: the engine API bundle imports this module and must stay slim.

Rules that everything else relies on:
- Money is int USDC base units (1 USDC = 1_000_000 = E6). Floats are refused for money.
- Temperature is int tenths of degF. Precipitation is int hundredths of an inch. Indicator
  indices are plain ints (-1, 0, 1).
- Signed division truncates toward zero (`tdiv`), which is Solidity's int division. Python's `//`
  floors, and the two differ on negative operands. Never use `//` on a value that can be negative.
- Days are UTC epoch days of the climate-day date (date - 1970-01-01). Timestamps are int Unix
  seconds, UTC.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

# --- scales ------------------------------------------------------------------------------------
UNIT = 1_000_000  # USDC base units per $1; one scalar unit pays at most UNIT
USDC = UNIT
TICK = 10_000  # one price tick = $0.01 per scalar unit, in base units
TICKS = 99  # valid ticks are 1..99
F10 = 10  # temperature scale: tenths of degF
IN100 = 100  # precipitation scale: hundredths of an inch
BPS = 10_000
PPM = 1_000_000
DAY_S = 86_400
MAX_INT64 = 2**63 - 1
MIN_INT64 = -(2**63)

_EPOCH = _dt.date(1970, 1, 1)


# --- integer arithmetic ------------------------------------------------------------------------
def _int(x: Any, name: str = "value") -> int:
    if isinstance(x, bool) or not isinstance(x, int):
        raise TypeError(f"{name} must be int, got {type(x).__name__}")
    return x


def tdiv(a: int, b: int) -> int:
    """Integer division truncating toward zero (Solidity int semantics)."""
    _int(a, "a"), _int(b, "b")
    if b == 0:
        raise ZeroDivisionError("tdiv by zero")
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def tmod(a: int, b: int) -> int:
    """Remainder matching tdiv: a == tdiv(a, b) * b + tmod(a, b) (Solidity %)."""
    return a - tdiv(a, b) * b


def ceil_div(a: int, b: int) -> int:
    """Ceiling division for a >= 0, b > 0."""
    _int(a, "a"), _int(b, "b")
    if a < 0 or b <= 0:
        raise ValueError("ceil_div needs a >= 0 and b > 0")
    return -(-a // b)


def mul_div(a: int, b: int, c: int) -> int:
    """floor(a * b / c) for non-negative operands (OZ Math.mulDiv, Rounding.Floor)."""
    _int(a, "a"), _int(b, "b"), _int(c, "c")
    if a < 0 or b < 0 or c <= 0:
        raise ValueError("mul_div needs a, b >= 0 and c > 0")
    return a * b // c


def round_half_away(a: int, b: int) -> int:
    """a / b rounded to the nearest int, halves away from zero (b > 0)."""
    _int(a, "a"), _int(b, "b")
    if b <= 0:
        raise ValueError("round_half_away needs b > 0")
    q = (2 * abs(a) + b) // (2 * b)
    return q if a >= 0 else -q


def clamp(x: int, lo: int, hi: int) -> int:
    return lo if x < lo else hi if x > hi else x


def bps(amount: int, rate_bps: int) -> int:
    """floor(amount * rate_bps / 10_000) for non-negative amounts."""
    return mul_div(amount, rate_bps, BPS)


# --- the scalar unit (SPEC section 2) ----------------------------------------------------------
def L(x: int, lo: int, hi: int) -> int:
    """Long payout per scalar unit in base units: clamp((x - lo) * 1e6 / (hi - lo), 0, 1e6).

    x, lo, hi are in the index's own integer scale. Requires lo < hi. The division truncates toward
    zero; on the clamped branch it only matters for lo < x < hi where the quotient is positive, so it
    equals floor there. Short receives UNIT - L(x).
    """
    _int(x, "x"), _int(lo, "lo"), _int(hi, "hi")
    if lo >= hi:
        raise ValueError("market needs lo < hi")
    if x <= lo:
        return 0
    if x >= hi:
        return UNIT
    return tdiv((x - lo) * UNIT, hi - lo)


def payout_long(qty: int, x: int, lo: int, hi: int) -> int:
    return _int(qty, "qty") * L(x, lo, hi)


def payout_short(qty: int, x: int, lo: int, hi: int) -> int:
    return _int(qty, "qty") * (UNIT - L(x, lo, hi))


# --- ticks and escrow (SPEC section 5) ---------------------------------------------------------
def check_tick(tick: int) -> int:
    _int(tick, "tick")
    if not 1 <= tick <= TICKS:
        raise ValueError(f"tick {tick} outside 1..{TICKS}")
    return tick


def tick_to_e6(tick: int) -> int:
    """Price of one scalar unit at `tick`, in base units."""
    return check_tick(tick) * TICK


def escrow_bid(tick: int, qty: int, fee_per_unit: int = 0) -> int:
    return _int(qty, "qty") * (tick_to_e6(tick) + fee_per_unit)


def escrow_offer(tick: int, qty: int, fee_per_unit: int = 0) -> int:
    return _int(qty, "qty") * ((100 - check_tick(tick)) * TICK + fee_per_unit)


def tick_to_index(tick: int, lo: int, hi: int) -> int:
    """Index value implied by a tick (the business-facing view), rounded half away from zero.

    For a basis market [-R, +R] this is the signed basis price: -R + tick * 2R / 100.
    """
    check_tick(tick)
    return round_half_away(lo * 100 + tick * (hi - lo), 100)


def index_to_tick(value: int, lo: int, hi: int) -> int:
    """Nearest tick for an implied index value, clamped to 1..99."""
    _int(value, "value")
    if lo >= hi:
        raise ValueError("market needs lo < hi")
    return clamp(round_half_away((value - lo) * 100, hi - lo), 1, TICKS)


# --- index encodings (SPEC section 1) ----------------------------------------------------------
def _dec(x: Any, name: str) -> Decimal:
    if isinstance(x, bool):
        raise TypeError(f"{name}: bool is not a number")
    if isinstance(x, Decimal):
        return x
    if isinstance(x, int):
        return Decimal(x)
    if isinstance(x, float):
        if x != x or x in (float("inf"), float("-inf")):
            raise ValueError(f"{name}: non-finite float")
        return Decimal(repr(x))  # shortest repr, so 91.3 stays 91.3
    if isinstance(x, str):
        return Decimal(x.strip())
    raise TypeError(f"{name}: unsupported type {type(x).__name__}")


def _q_half_away(d: Decimal) -> int:
    return int(d.quantize(Decimal(1), rounding=ROUND_HALF_UP))  # ROUND_HALF_UP = half away from zero


def f_to_tenths(deg_f: Any) -> int:
    """degF (int, decimal string, Decimal or float) -> int tenths of degF, halves away from zero."""
    return _q_half_away(_dec(deg_f, "deg_f") * F10)


def tenths_to_f(tenths: int) -> Decimal:
    return Decimal(_int(tenths, "tenths")) / F10


def c_to_tenths_f(deg_c: Any) -> int:
    """degC -> tenths of degF (F = C * 9/5 + 32), halves away from zero. Grid sources use this."""
    return _q_half_away(_dec(deg_c, "deg_c") * 18 + 320)


def inch_to_hundredths(inches: Any) -> int:
    """Inches -> hundredths, halves away from zero. The CLI trace flag 'T' (any case) is 0."""
    if isinstance(inches, str) and inches.strip().upper() == "T":
        return 0
    return _q_half_away(_dec(inches, "inches") * IN100)


def mm_to_hundredths(mm: Any) -> int:
    """Millimetres -> hundredths of an inch (in = mm / 25.4), halves away from zero."""
    return _q_half_away(_dec(mm, "mm") * 100 / Decimal("25.4"))


def hundredths_to_inch(h: int) -> Decimal:
    return Decimal(_int(h, "hundredths")) / IN100


def check_int64(v: int) -> int:
    _int(v, "value")
    if not MIN_INT64 <= v <= MAX_INT64:
        raise ValueError("value outside int64")
    return v


# --- money --------------------------------------------------------------------------------------
def usdc_to_e6(amount: Any) -> int:
    """Dollars (int, decimal string or Decimal) -> base units. Floats are refused; sub-unit
    precision is an error, never silently rounded."""
    if isinstance(amount, float):
        raise TypeError("money must not be a float; pass a decimal string")
    d = _dec(amount, "amount") * UNIT
    if d != d.to_integral_value():
        raise ValueError(f"{amount} has more than 6 decimals")
    return int(d)


def e6_to_usdc(e6: int) -> Decimal:
    return Decimal(_int(e6, "e6")) / UNIT


# --- days and timestamps (SPEC section 1) ------------------------------------------------------
def date_to_day(d: _dt.date | str) -> int:
    """Climate-day date (date or 'YYYY-MM-DD') -> epoch day (uint32 on chain)."""
    if isinstance(d, str):
        d = _dt.date.fromisoformat(d)
    if isinstance(d, _dt.datetime):
        raise TypeError("pass a date, not a datetime")
    return (d - _EPOCH).days


def day_to_date(day: int) -> _dt.date:
    return _EPOCH + _dt.timedelta(days=_int(day, "day"))


def day_to_iso(day: int) -> str:
    return day_to_date(day).isoformat()


def day_start_ts(day: int) -> int:
    """00:00Z of the epoch day, as Unix seconds."""
    return _int(day, "day") * DAY_S


def at_utc(day: int, hh: int, mm: int = 0) -> int:
    """Unix seconds of hh:mmZ on epoch day `day` (hh may exceed 23 to roll into later days)."""
    return day_start_ts(day) + hh * 3600 + mm * 60


def ts_to_day(ts: int) -> int:
    """UTC epoch day containing Unix second `ts`. Not a climate day: only for UTC bookkeeping."""
    return _int(ts, "ts") // DAY_S  # ts >= 0 in practice; floor is the UTC day for negatives too


def ts_to_iso(ts: int) -> str:
    return _dt.datetime.fromtimestamp(_int(ts, "ts"), tz=_dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_to_ts(s: str) -> int:
    """ISO-8601 with an explicit UTC designator ('Z' or +00:00) -> Unix seconds. Naive or
    non-UTC strings are refused (point-in-time rule)."""
    t = _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    if t.tzinfo is None or t.utcoffset() != _dt.timedelta(0):
        raise ValueError(f"timestamp must be UTC: {s!r}")
    if t.microsecond:
        raise ValueError(f"sub-second timestamp: {s!r}")
    return int(t.timestamp())


# --- canonical JSON and hashing (SPEC section 13) ----------------------------------------------
def _check_canon(o: Any, path: str = "$") -> None:
    if isinstance(o, float):
        raise TypeError(f"float at {path}; convert to a scaled int first")
    if isinstance(o, dict):
        for k, v in o.items():
            if not isinstance(k, str):
                raise TypeError(f"non-string key {k!r} at {path}")
            _check_canon(v, f"{path}.{k}")
    elif isinstance(o, (list, tuple)):
        for i, v in enumerate(o):
            _check_canon(v, f"{path}[{i}]")
    elif o is None or isinstance(o, (str, int, bool)):
        return
    else:
        raise TypeError(f"unsupported type {type(o).__name__} at {path}")


def canonical_json(obj: Any) -> bytes:
    """Byte-stable JSON: sorted keys, no whitespace, UTF-8, ints/strings/bools/null/lists/dicts only."""
    _check_canon(obj)
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_canonical(obj: Any) -> str:
    return sha256_hex(canonical_json(obj))


GENESIS_PREV = "0" * 64


def event_hash(event: dict) -> str:
    """Hash of one log line (the full event dict including its own `prev`). The next event's
    `prev` is this value."""
    return sha256_canonical(event)
