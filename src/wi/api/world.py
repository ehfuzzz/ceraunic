"""A sim world in memory: the engine Ledger (all money, SPEC state) plus the API metadata (businesses,
sales, API quote/policy groups, clock, idempotency). The Ledger is the only thing that moves money.

Blob layout (store.py saves it): {"state": engine state, "last": last log line, "meta": {...}}.
"""
from __future__ import annotations

from wi.engine import markets, pool, staking
from wi.engine.eip712 import index_id, market_id
from wi.engine.reducer import Ledger
from wi.engine.state import P
from wi.engine.units import DAY_S, UNIT, ts_to_day

from . import catalog as cat
from . import snapshot_data as sd


def new_meta(world_id: str) -> dict:
    return {"worldId": world_id, "simTs": cat.GENESIS_TS, "counters": {}, "nonce": 1, "businesses": {},
            "sales": {}, "quotes": {}, "policies": {}, "tickets": [], "idem": {}, "idemOrder": [], "ticks": {},
            "haircuts": [], "nav": [], "notes": []}


class SimWorld:
    def __init__(self, led: Ledger, meta: dict):
        self.led = led
        self.meta = meta

    # ------------------------------------------------------------ persistence
    @classmethod
    def from_blob(cls, blob: dict) -> "SimWorld":
        return cls(Ledger(state=blob["state"], last_line=blob["last"]), blob["meta"])

    def to_blob(self) -> dict:
        return {"state": self.led.state, "last": self.led.last_line, "meta": self.meta}

    @property
    def st(self) -> dict:
        return self.led.state

    @property
    def now(self) -> int:
        return self.meta["simTs"]

    @property
    def sim_day(self) -> int:
        return ts_to_day(self.now)

    def next_id(self, prefix: str) -> str:
        c = self.meta["counters"]
        c[prefix] = c.get(prefix, 0) + 1
        return f"{prefix}_{c[prefix]:06d}"

    # ------------------------------------------------------------ catalogue lookups
    def iid(self, name: str) -> str:
        return index_id(name)

    def R(self) -> int:
        return P(self.st, "basisRangeTenths")

    def basis_market_id(self, site: str, day: int) -> str:
        R = self.R()
        return market_id(index_id(cat.pair_index(site)), day, -R, R)

    def ensure_basis_market(self, ts: int, site: str, day: int) -> str:
        R = self.R()
        return markets.create_market(self.led, ts, index_id(cat.pair_index(site)), day, -R, R, True)

    def basis_markets(self, day: int) -> list[str]:
        out = []
        for s in cat.PAIR_SITES:
            mk = self.basis_market_id(s, day)
            if mk in self.st["markets"]:
                out.append(mk)
        return out

    def prehistory(self, day_limit: int | None = None) -> dict[str, list]:
        """Basis prehistory per pair index (finalised before the world's first day)."""
        return {index_id(cat.pair_index(s)): sd.pair_prehistory(s, cat.SITES[s][5], cat.FIRST_DAY)
                for s in cat.PAIR_SITES}

    def rain_prehistory(self, site: str) -> list:
        """Wet-day history of a rain station finalised before the world's first day (snapshot)."""
        return sd.rain_prehistory(site, cat.FIRST_DAY)

    def index_names(self) -> dict[str, str]:
        return {index_id(n): n for n in cat.INDEX_NAMES}


def genesis(world_id: str, world_file: dict | None = None) -> SimWorld:
    """Template demo-5-cities at GENESIS_TS: params, funding, index registry, tranche seed, WI stake."""
    wf = world_file or cat.world_file()
    led = Ledger(wf)
    ts = cat.GENESIS_TS
    for k, v in sorted(cat.params().items()):
        led.emit(ts, "ParamsSet", {"key": k, "value": v})
    led.emit(ts, "AccountFunded", {"account": cat.HOUSE, "amount": cat.HOUSE_FLOAT + cat.JUNIOR_SEED})
    led.emit(ts, "AccountFunded", {"account": cat.SEED_LP, "amount": cat.SENIOR_SEED})
    for s, (_, _, _, _, metro, settle, _) in cat.SITES.items():
        markets.register_index(led, ts, cat.cli_index(s), kind="CLI", scale=10, station=settle, metro=metro,
                               inputs=[f"CLI{s}"])
    for s in cat.PAIR_SITES:
        _, _, _, _, metro, settle, _ = cat.SITES[s]
        markets.register_index(led, ts, cat.pair_index(s), kind="PAIR", scale=10, station=settle, metro=metro,
                               inputs=[f"CLI{s}", f"CLI{settle}"])
    for s in cat.RAIN_SERIES:  # wet-day indices at the Kalshi rain stations (13-RAIN)
        markets.register_index(led, ts, cat.rain_index(s), kind="CLI", scale=1, station=s, metro=cat.SITES[s][4],
                               inputs=[f"CLI{s}"])
    pool.deposit_junior(led, ts, cat.HOUSE, cat.JUNIOR_SEED)
    pool.deposit_senior(led, ts, cat.SEED_LP, cat.SENIOR_SEED)
    staking.stake(led, ts, cat.OWNER, cat.WI_OWNER_STAKE)
    return SimWorld(led, new_meta(world_id))


def cash_of(st: dict, addr: str) -> int:
    return st["bal"].get(addr, 0)


def usd(e6: int) -> str:
    return f"${e6 / UNIT:,.2f}"


def day_of_ts(ts: int) -> int:
    return ts // DAY_S
