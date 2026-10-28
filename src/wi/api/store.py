"""World storage: one blob per sim world (engine state + last log line + API metadata) and its event log.

Pattern 4 (09-RESEARCH): keys `wi:w:{world}:snap` (zlib+base64 of the canonical blob), `wi:w:{world}:events`
(one RPUSH element per write: zlib+base64 of that write's hash-chained JSONL lines), `wi:w:{world}:lock`
(SET NX PX mutex, compare-and-delete unlock). Every write holds the lock from read to save, so two
concurrent POSTs cannot both act on the same snapshot; a write that raises saves nothing.
Idempotency results live inside the blob, so a replayed key and the state it produced are saved atomically.

MemoryStore keeps the same serialised bytes (no shared dicts between requests), so tests exercise the
exact encode/decode path the Upstash store uses.
"""
from __future__ import annotations

import base64
import json
import secrets
import threading
import time
import zlib
from contextlib import contextmanager
from typing import Iterator

from .envelope import ApiError

DEMO = "demo"
WORLD_TTL_S = 7 * 86_400
LOCK_TTL_MS = 120_000
LOCK_WAIT_S = 20.0


def encode(obj) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    return base64.b64encode(zlib.compress(raw, 6)).decode()


def decode(s: str | bytes):
    if isinstance(s, str):
        s = s.encode()
    return json.loads(zlib.decompress(base64.b64decode(s)))


class WorldBusy(ApiError):
    def __init__(self, world: str):
        super().__init__(409, "WORLD_BUSY", "World is busy", f"another write holds world {world!r}; retry")


class BaseStore:
    """Subclasses implement _get, _set, _append, _lock, _unlock, _exists."""

    def load(self, world: str) -> dict | None:
        raw = self._get(world)
        return None if raw is None else decode(raw)

    def exists(self, world: str) -> bool:
        return self._exists(world)

    @contextmanager
    def write(self, world: str) -> Iterator[dict | None]:
        """Yield the current blob (or None) under the world lock; the caller mutates `box['blob']`."""
        token = self._lock(world)
        box: dict = {"blob": self.load(world), "lines": [], "save": True}
        try:
            yield box
            if box["save"] and box["blob"] is not None:
                self._set(world, encode(box["blob"]), pinned=(world == DEMO))
                if box["lines"]:
                    self._append(world, encode(box["lines"]), pinned=(world == DEMO))
        finally:
            self._unlock(world, token)

    def events(self, world: str) -> list[dict]:
        out = []
        for chunk in self._events(world):
            out.extend(decode(chunk))
        return out


class MemoryStore(BaseStore):
    def __init__(self) -> None:
        self._snap: dict[str, str] = {}
        self._ev: dict[str, list[str]] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def _get(self, world):
        return self._snap.get(world)

    def _set(self, world, value, pinned):
        self._snap[world] = value

    def _append(self, world, value, pinned):
        self._ev.setdefault(world, []).append(value)

    def _events(self, world):
        return list(self._ev.get(world, []))

    def _exists(self, world):
        return world in self._snap

    def _lock(self, world):
        with self._guard:
            lk = self._locks.setdefault(world, threading.Lock())
        if not lk.acquire(timeout=LOCK_WAIT_S):
            raise WorldBusy(world)
        return lk

    def _unlock(self, world, token):
        token.release()

    def delete(self, world):
        self._snap.pop(world, None)
        self._ev.pop(world, None)


_UNLOCK = "if redis.call('get',KEYS[1])==ARGV[1] then return redis.call('del',KEYS[1]) else return 0 end"


class UpstashStore(BaseStore):
    """Upstash Redis over REST (serverless-safe). Reads UPSTASH_REDIS_REST_URL / _TOKEN."""

    def __init__(self, url: str, token: str, prefix: str = "wi") -> None:
        from upstash_redis import Redis  # lazy: only when the env is set

        self.r = Redis(url=url, token=token)
        self.p = prefix

    def _k(self, world: str, part: str) -> str:
        return f"{self.p}:w:{world}:{part}"

    def _get(self, world):
        return self.r.get(self._k(world, "snap"))

    def _set(self, world, value, pinned):
        if pinned:
            self.r.set(self._k(world, "snap"), value)
        else:
            self.r.set(self._k(world, "snap"), value, ex=WORLD_TTL_S)

    def _append(self, world, value, pinned):
        k = self._k(world, "events")
        self.r.rpush(k, value)
        if not pinned:
            self.r.expire(k, WORLD_TTL_S)

    def _events(self, world):
        return self.r.lrange(self._k(world, "events"), 0, -1) or []

    def _exists(self, world):
        return bool(self.r.exists(self._k(world, "snap")))

    def _lock(self, world):
        key, token = self._k(world, "lock"), secrets.token_hex(8)
        deadline = time.monotonic() + LOCK_WAIT_S
        while True:
            if self.r.set(key, token, nx=True, px=LOCK_TTL_MS):
                return token
            if time.monotonic() > deadline:
                raise WorldBusy(world)
            time.sleep(0.1)

    def _unlock(self, world, token):
        self.r.eval(_UNLOCK, keys=[self._k(world, "lock")], args=[token])

    def delete(self, world):
        self.r.delete(self._k(world, "snap"), self._k(world, "events"))


def store_from_env(env) -> BaseStore:
    url, tok = env.get("UPSTASH_REDIS_REST_URL"), env.get("UPSTASH_REDIS_REST_TOKEN")
    if url and tok:
        return UpstashStore(url, tok, prefix=env.get("WI_STORE_PREFIX", "wi"))
    return MemoryStore()
