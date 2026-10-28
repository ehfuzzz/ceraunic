"""Hash-chained JSONL event log (docs/SPEC.md section 13, invariant I16).

Line = {"seq", "ts", "type", "payload", "prev"}; prev of seq 0 = 64 zeros; prev of line n = sha256 of
line n-1's canonical JSON (units.event_hash). Standard library only.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .events import validate
from .units import GENESIS_PREV, canonical_json, event_hash


class LogError(ValueError):
    pass


def make_line(prev_line: dict | None, ts: int, etype: str, payload: dict) -> dict:
    validate(etype, payload)
    if isinstance(ts, bool) or not isinstance(ts, int):
        raise LogError("ts must be int")
    if prev_line is None:
        seq, prev = 0, GENESIS_PREV
    else:
        if ts < prev_line["ts"]:
            raise LogError(f"ts went backwards: {ts} < {prev_line['ts']} ({etype})")
        seq, prev = prev_line["seq"] + 1, event_hash(prev_line)
    return {"seq": seq, "ts": ts, "type": etype, "payload": payload, "prev": prev}


def check_link(prev_line: dict | None, line: dict) -> None:
    """I16 for one line against its predecessor (None for the first line)."""
    if set(line) != {"seq", "ts", "type", "payload", "prev"}:
        raise LogError(f"bad line keys at seq {line.get('seq')}")
    validate(line["type"], line["payload"])
    canonical_json(line)  # refuses floats anywhere in the line
    if prev_line is None:
        if line["seq"] != 0 or line["prev"] != GENESIS_PREV:
            raise LogError("first line must be seq 0 with the genesis prev")
        return
    if line["seq"] != prev_line["seq"] + 1:
        raise LogError(f"seq gap at {line['seq']}")
    if line["ts"] < prev_line["ts"]:
        raise LogError(f"ts went backwards at seq {line['seq']}")
    if line["prev"] != event_hash(prev_line):
        raise LogError(f"prev hash mismatch at seq {line['seq']}")


def verify_chain(lines: Iterable[dict], prev_line: dict | None = None) -> int:
    n = 0
    for line in lines:
        check_link(prev_line, line)
        prev_line = line
        n += 1
    return n


def write_jsonl(path: str | Path, lines: Iterable[dict]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("wb") as f:
        for line in lines:
            f.write(canonical_json(line) + b"\n")
    tmp.replace(p)


def read_jsonl(path: str | Path) -> list[dict]:
    out = []
    with Path(path).open("rb") as f:
        for raw in f:
            raw = raw.strip()
            if raw:
                out.append(json.loads(raw))
    return out
