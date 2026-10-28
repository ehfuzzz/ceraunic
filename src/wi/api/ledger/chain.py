"""Minimal EVM plumbing for EvmLedger: JSON-RPC over urllib, ABI encode/decode with eth_abi, log decoding and
custom-error names. No web3 (the deploy bundle stays small); imported only in anvil / testnet mode.

ABIs come from contracts/out/<C>.sol/<C>.json (forge build) or, in the deploy bundle, contracts/abi/<C>.json.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path

from eth_abi import decode as abi_decode
from eth_abi import encode as abi_encode
from eth_utils import keccak

from ..envelope import ApiError

CONTRACTS = ("PolicyManager", "BatchAuction", "PoolVault", "OracleAdapter", "MockUSDC", "Lens", "WIStaking",
             "WIToken", "SeniorShare")
MAX_UINT = 2**256 - 1


def _roots() -> list[Path]:
    here = Path(__file__).resolve()
    out = []
    for p in here.parents:
        if (p / "contracts").is_dir():
            out.append(p / "contracts")
    return out


@lru_cache(maxsize=None)
def abi_of(name: str) -> list[dict]:
    for root in _roots():
        for p in (root / "out" / f"{name}.sol" / f"{name}.json", root / "abi" / f"{name}.json"):
            if p.exists():
                raw = json.loads(p.read_text())
                return raw["abi"] if isinstance(raw, dict) else raw
    raise RuntimeError(f"no ABI for {name}: run `forge build` in contracts/ (or bundle contracts/abi/{name}.json)")


def _type(inp: dict) -> str:
    t = inp["type"]
    if t.startswith("tuple"):
        return "(" + ",".join(_type(c) for c in inp["components"]) + ")" + t[len("tuple"):]
    return t


def _shape(inp: dict, v):
    """Decoded eth_abi value -> python (tuples with component names become dicts; bytes -> 0x hex)."""
    t = inp["type"]
    if t.startswith("tuple"):
        if t.endswith("[]"):
            return [_shape({**inp, "type": t[:-2]}, x) for x in v]
        return {c["name"]: _shape(c, x) for c, x in zip(inp["components"], v)}
    if t.endswith("[]"):
        return [_shape({**inp, "type": t[:-2]}, x) for x in v]
    if t.startswith("bytes"):
        return "0x" + bytes(v).hex()
    if t == "address":
        return v.lower()
    return v


def _prep(inp: dict, v):
    """python -> eth_abi value (dicts become tuples in component order; 0x hex -> bytes)."""
    t = inp["type"]
    if t.startswith("tuple"):
        if t.endswith("[]"):
            return [_prep({**inp, "type": t[:-2]}, x) for x in v]
        if isinstance(v, dict):
            return tuple(_prep(c, v[c["name"]]) for c in inp["components"])
        return tuple(_prep(c, x) for c, x in zip(inp["components"], v))
    if t.startswith("bytes") and isinstance(v, str):
        return bytes.fromhex(v[2:] if v.startswith("0x") else v)
    return v


class Contract:
    def __init__(self, name: str, address: str):
        self.name, self.address = name, address.lower()
        self.abi = abi_of(name)
        self.fns: dict[str, list[dict]] = {}
        for e in self.abi:
            if e["type"] == "function":
                self.fns.setdefault(e["name"], []).append(e)

    def fn(self, name: str, nargs: int) -> dict:
        cands = [f for f in self.fns.get(name, []) if len(f["inputs"]) == nargs]
        if len(cands) != 1:
            raise RuntimeError(f"{self.name}.{name}/{nargs}: {len(cands)} candidates")
        return cands[0]

    def encode(self, name: str, *args) -> str:
        f = self.fn(name, len(args))
        sig = f"{name}(" + ",".join(_type(i) for i in f["inputs"]) + ")"
        types = [_type(i) for i in f["inputs"]]
        return "0x" + keccak(text=sig)[:4].hex() + abi_encode(types, [_prep(i, a) for i, a in zip(f["inputs"], args)]).hex()

    def decode(self, name: str, nargs: int, data: str):
        f = self.fn(name, nargs)
        raw = bytes.fromhex(data[2:])
        vals = abi_decode([_type(o) for o in f["outputs"]], raw)
        out = [_shape(o, v) for o, v in zip(f["outputs"], vals)]
        return out[0] if len(out) == 1 else out


@lru_cache(maxsize=None)
def _events() -> dict[str, tuple[str, dict]]:
    out = {}
    for c in CONTRACTS:
        try:
            abi = abi_of(c)
        except RuntimeError:
            continue
        for e in abi:
            if e["type"] == "event" and not e.get("anonymous"):
                sig = f"{e['name']}(" + ",".join(_type(i) for i in e["inputs"]) + ")"
                out["0x" + keccak(text=sig).hex()] = (c, e)
    return out


@lru_cache(maxsize=None)
def _errors() -> dict[str, tuple[str, list[dict]]]:
    out = {}
    for c in CONTRACTS:
        try:
            abi = abi_of(c)
        except RuntimeError:
            continue
        for e in abi:
            if e["type"] == "error":
                sig = f"{e['name']}(" + ",".join(_type(i) for i in e["inputs"]) + ")"
                out["0x" + keccak(text=sig)[:4].hex()] = (e["name"], e["inputs"])
    return out


def decode_log(log: dict) -> tuple[str, str, dict] | None:
    """(contract name, event name, fields) for a known event, else None."""
    topics = log.get("topics") or []
    if not topics:
        return None
    hit = _events().get(topics[0].lower())
    if hit is None:
        return None
    cname, ev = hit
    idx = [i for i in ev["inputs"] if i["indexed"]]
    rest = [i for i in ev["inputs"] if not i["indexed"]]
    fields = {}
    for i, t in zip(idx, topics[1:]):
        fields[i["name"]] = _shape(i, abi_decode([_type(i)], bytes.fromhex(t[2:]))[0])
    vals = abi_decode([_type(i) for i in rest], bytes.fromhex(log["data"][2:]))
    for i, v in zip(rest, vals):
        fields[i["name"]] = _shape(i, v)
    return cname, ev["name"], fields


def revert_name(data: str | None) -> str:
    if not data or len(data) < 10:
        return "revert (no data)"
    hit = _errors().get(data[:10].lower())
    if hit is None:
        if data[:10] == "0x08c379a0":
            try:
                return "Error(" + abi_decode(["string"], bytes.fromhex(data[10:]))[0] + ")"
            except Exception:  # noqa: BLE001
                pass
        return f"revert {data[:10]}"
    name, inputs = hit
    try:
        args = abi_decode([_type(i) for i in inputs], bytes.fromhex(data[10:]))
        return f"{name}({', '.join(str(a) for a in args)})" if args else name
    except Exception:  # noqa: BLE001
        return name


class RpcError(Exception):
    def __init__(self, message: str, data: str | None = None):
        super().__init__(message)
        self.data = data


class Rpc:
    def __init__(self, url: str, timeout: float = 30.0):
        self.url, self.timeout = url, timeout
        self._id = 0

    def _post(self, payload):
        req = urllib.request.Request(self.url, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return json.loads(r.read())
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise ApiError(503, "RPC_UNAVAILABLE", "Chain RPC unavailable", f"{self.url}: {e}") from None

    def call(self, method: str, *params):
        self._id += 1
        out = self._post({"jsonrpc": "2.0", "id": self._id, "method": method, "params": list(params)})
        if "error" in out:
            err = out["error"]
            data = err.get("data")
            if isinstance(data, dict):
                data = data.get("data")
            raise RpcError(err.get("message", "rpc error"), data if isinstance(data, str) else None)
        return out["result"]

    def batch(self, calls: list[tuple[str, list]]) -> list:
        """One HTTP round trip; results in call order. An individual error comes back as an RpcError value."""
        if not calls:
            return []
        payload = [{"jsonrpc": "2.0", "id": i, "method": m, "params": p} for i, (m, p) in enumerate(calls)]
        out = self._post(payload)
        by_id = {r["id"]: r for r in out}
        res = []
        for i in range(len(calls)):
            r = by_id[i]
            if "error" in r:
                d = r["error"].get("data")
                res.append(RpcError(r["error"].get("message", "rpc error"), d if isinstance(d, str) else None))
            else:
                res.append(r["result"])
        return res


class Reader:
    """Batched eth_call against named contracts: add(key, contract, fn, *args) then run() -> {key: value}."""

    def __init__(self, rpc: Rpc, contracts: dict[str, Contract]):
        self.rpc, self.c = rpc, contracts
        self.items: list[tuple[object, str, str, tuple]] = []

    def add(self, key, cname: str, fn: str, *args) -> None:
        self.items.append((key, cname, fn, args))

    def run(self, chunk: int = 400) -> dict:
        out = {}
        for i in range(0, len(self.items), chunk):
            part = self.items[i:i + chunk]
            calls = [("eth_call", [{"to": self.c[c].address, "data": self.c[c].encode(fn, *a)}, "latest"])
                     for _, c, fn, a in part]
            for (key, c, fn, a), res in zip(part, self.rpc.batch(calls)):
                if isinstance(res, RpcError):
                    raise ApiError(503, "RPC_UNAVAILABLE", "eth_call failed", f"{c}.{fn}{a}: {res} {revert_name(res.data)}")
                out[key] = self.c[c].decode(fn, len(a), res)
        self.items = []
        return out
