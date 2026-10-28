"""EvmLedger: the chain modes.

anvil   AnvilLedger. The Phase 8 contracts on a local anvil (deployed by Deploy.s.sol + Configure.s.sol) are the
        ledger of record; the engine runs alongside as the planner (house MM, pricing, clock steps) exactly as in
        sim. Every engine event of a write is replayed on chain at its own timestamp (mirror.py), the chain's
        event log is checked field by field against the engine payload, and after the write the whole chain
        state is read back and must equal the engine state (chainstate.py). Any refusal or difference undoes
        the write on both sides (evm_revert) and returns 500 CHAIN_DIVERGED. Reads run the API views on the
        state read from chain. Transactions are server-signed by anvil's unlocked PUBLIC dev accounts
        (eth_sendTransaction / eth_signTypedData_v4): no key material lives in this code or its env.
        One chain = one world ("demo"); POST /sim/worlds rewinds the chain to the post-genesis snapshot.
testnet TestnetLedger. Calldata only: every write returns a `needs_signature` envelope with the transactions
        the user's wallet must sign; the engine holds no keys (app.check_guards refuses any *PRIVATE_KEY* /
        *MNEMONIC* env). Reads use the Lens (one eth_call per user, cached 5 s). Selling policies needs the
        quoter key, so quotes/policies/oracle reports answer 409 OWNER_SCRIPT (the owner's scripts sell them).
"""
from __future__ import annotations

import json
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from wi.engine.units import ts_to_iso

from .. import catalog as cat
from .. import clock
from ..envelope import ApiError, TxRequest
from ..models import Balances, ChainInfo, Health, PoolState, StakingView, TxConfirm, WorldInfo
from ..store import DEMO, MemoryStore, decode, encode
from ..world import genesis
from .chain import CONTRACTS, MAX_UINT, Contract, Reader, Rpc, RpcError, decode_log
from .chainstate import fresh_chain_problems, overlay, param_problems
from .mirror import Diverged, Mirror
from .sim import SimLedger, _ReadWorld, base_config


def _deployment(path: str | None, chain_id: int) -> dict | None:
    cands = [Path(path)] if path else []
    here = Path(__file__).resolve()
    for p in here.parents:
        cands.append(p / "contracts" / "deployments" / f"{chain_id}.json")
    for p in cands:
        if p.exists():
            return json.loads(p.read_text())
    return None


def _contracts(dep: dict) -> dict[str, Contract]:
    return {n: Contract(n, dep[n]) for n in CONTRACTS}


class EvmLedger:
    """Factory: EvmLedger(mode, env) -> AnvilLedger | TestnetLedger."""

    def __new__(cls, mode: str, env):
        if mode == "anvil":
            return AnvilLedger(env)
        if mode == "testnet":
            return TestnetLedger(env)
        raise RuntimeError(f"EvmLedger has no mode {mode!r}")

    @staticmethod
    def offline_testnet_for_tests() -> "TestnetLedger":
        """A testnet adapter with the anvil address book and no RPC (calldata building only)."""
        dep = _deployment(None, 31337)
        if dep is None:
            raise RuntimeError("contracts/deployments/31337.json missing")
        return TestnetLedger({}, deployment={**dep, "chainId": 998}, rpc=None)


def diverged(e: Exception) -> ApiError:
    return ApiError(500, "CHAIN_DIVERGED", "Engine and contracts disagree", str(e)[:2000])


# ================================================================ anvil
class AnvilLedger(SimLedger):
    mode = "anvil"

    def __init__(self, env):
        super().__init__(MemoryStore(), env)
        self.rpc = Rpc(env.get("ANVIL_RPC_URL") or "http://127.0.0.1:8545")
        self.dep_path = env.get("WI_DEPLOYMENT") or None
        self.dep: dict | None = None
        self.c: dict[str, Contract] = {}
        self.chain_id = 31337
        self.mirror: Mirror | None = None
        self.signers = {a: "anvil-unlocked" for a in cat.ANVIL}  # anvil's public dev accounts sign; no keys here
        self._boot_lock = threading.Lock()
        self._genesis: tuple[str, str] | None = None
        self._snap: str | None = None
        self.last_drift: list[str] = []

    # ------------------------------------------------------------ boot
    def _connect(self) -> None:
        if self.dep is not None:
            return
        try:
            cid = int(self.rpc.call("eth_chainId"), 16)
        except RpcError as e:
            raise ApiError(503, "RPC_UNAVAILABLE", "anvil unavailable", str(e)) from None
        dep = _deployment(self.dep_path, cid)
        if dep is None:
            raise ApiError(503, "RPC_UNAVAILABLE", "No deployment", f"no address book for chain {cid}; "
                           "run scripts/anvil-scenario.sh (deploy + configure) or set WI_DEPLOYMENT")
        if dep.get("chainId") != cid:
            raise ApiError(503, "RPC_UNAVAILABLE", "Wrong chain", f"address book is for chain {dep.get('chainId')}, RPC is {cid}")
        c = _contracts(dep)
        if self.rpc.call("eth_getCode", c["PolicyManager"].address, "latest") in ("0x", "0x0"):
            raise ApiError(503, "RPC_UNAVAILABLE", "No contracts", "the address book's PolicyManager has no code on this anvil")
        self.dep, self.c, self.chain_id = dep, c, cid
        self.mirror = Mirror(self.rpc, c, cid)

    def _world_file(self) -> dict:
        return cat.world_file((self.chain_id, self.c["PolicyManager"].address),
                              (self.chain_id, self.c["OracleAdapter"].address))

    def _ensure(self) -> None:
        if self._genesis is not None:
            return
        with self._boot_lock:
            if self._genesis is not None:
                return
            self._connect()
            wf = self._world_file()
            probs = fresh_chain_problems(self.rpc, self.c) + param_problems(self.rpc, self.c, cat.params(), wf["roles"])
            if probs:
                raise ApiError(503, "RPC_UNAVAILABLE", "anvil deployment does not match the engine world",
                               "; ".join(probs))
            head = int(self.rpc.call("eth_getBlockByNumber", "latest", False)["timestamp"], 16)
            if head > cat.GENESIS_TS:
                raise ApiError(503, "RPC_UNAVAILABLE", "anvil clock is past genesis",
                               f"chain time {ts_to_iso(head)} > {ts_to_iso(cat.GENESIS_TS)}; start anvil with "
                               "--timestamp before it (scripts/anvil-scenario.sh does)")
            w = genesis(DEMO, wf)
            clock.advance(w, cat.START_TS)
            snap0 = self.rpc.call("evm_snapshot")
            try:
                self.mirror.materialise(cat.GENESIS_TS)
                self.mirror.apply(w.st, w.led.lines)
                _, drift = overlay(self.rpc, self.c, w.st)
                if drift:
                    raise Diverged("after genesis: " + "; ".join(drift[:20]))
            except Diverged as e:
                self.rpc.call("evm_revert", snap0)
                raise diverged(e) from None
            blob = w.to_blob()
            self._genesis = (encode(blob), encode(w.led.lines))
            self._install_genesis()

    def _install_genesis(self) -> None:
        blob, lines = self._genesis
        self.store.delete(DEMO)
        with self.store.write(DEMO) as box:
            box["blob"], box["lines"] = decode(blob), decode(lines)
        self._snap = self.rpc.call("evm_snapshot")

    def _rewind(self) -> WorldInfo:
        self._ensure()
        with self.store.write(DEMO) as box:  # hold the world lock while the chain rewinds
            box["save"] = False
            if not self.rpc.call("evm_revert", self._snap):
                raise ApiError(503, "RPC_UNAVAILABLE", "evm_revert failed", "restart anvil (scripts/anvil-scenario.sh)")
        self._install_genesis()
        return WorldInfo(world_id=DEMO, sim_time=ts_to_iso(cat.START_TS))

    # ------------------------------------------------------------ world plumbing
    @staticmethod
    def _one_world(wid: str) -> None:
        if wid != DEMO:
            raise ApiError(404, "NOT_FOUND", "Unknown world", "anvil mode has one world: 'demo' (the chain)")

    @contextmanager
    def write(self, wid: str) -> Iterator:
        self._one_world(wid)
        self._ensure()
        with super().write(wid) as w:
            snap = self.rpc.call("evm_snapshot")
            try:
                yield w
                self.mirror.apply(w.st, w.led.lines)
                _, drift = overlay(self.rpc, self.c, w.st)
                self.last_drift = drift
                if drift:
                    raise Diverged("state after the write: " + "; ".join(drift[:20]))
            except Diverged as e:
                self.rpc.call("evm_revert", snap)
                raise diverged(e) from None
            except BaseException:
                self.rpc.call("evm_revert", snap)
                raise

    def read(self, wid: str):
        self._one_world(wid)
        self._ensure()
        blob = self.store.load(wid)
        st, drift = overlay(self.rpc, self.c, blob["state"])
        self.last_drift = drift
        if drift:
            raise diverged(Diverged("read: " + "; ".join(drift[:20])))
        return _ReadWorld({"state": st, "meta": blob["meta"], "last": blob["last"]})

    def execution(self, cls, result):
        return cls(mode="anvil", status="done", result=result, txs=[])

    # ------------------------------------------------------------ meta
    def health(self) -> Health:
        self._ensure()
        blob = self.store.load(DEMO)
        return Health(ok=True, mode="anvil", chain_id=self.chain_id, engine_version=cat.ENGINE_VERSION,
                      spec_hash=cat.spec_hash(), sim_time=ts_to_iso(blob["meta"]["simTs"]))

    def config(self):
        self._connect()
        return base_config("anvil", ChainInfo(id=self.chain_id, name="anvil", rpc_url=self.rpc.url),
                           {n: self.c[n].address for n in CONTRACTS})

    def new_world(self) -> WorldInfo:
        return self._rewind()

    def reset_world(self, wid: str) -> WorldInfo:
        self._one_world(wid)
        return self._rewind()

    def tx_confirm(self, tx_hash: str) -> TxConfirm:
        self._connect()
        return _confirm(self.rpc, tx_hash)


def _confirm(rpc: Rpc, tx_hash: str) -> TxConfirm:
    rc = rpc.call("eth_getTransactionReceipt", tx_hash)
    if rc is None:
        return TxConfirm(status="pending", block_number=0, objects=[])
    objs = []
    for lg in rc["logs"]:
        d = decode_log(lg)
        if d is None:
            continue
        _, name, f = d
        if name == "PolicyBought":
            objs.append({"kind": "policy", "id": str(f["policyId"]), "policyId": str(f["policyId"])})
        elif name == "OrderPlaced":
            objs.append({"kind": "order", "id": str(f["orderId"])})
        elif name in ("WithdrawRequested", "WithdrawCancelled", "WithdrawLapsed"):
            objs.append({"kind": "withdrawal", "id": str(f["requestId"])})
        elif name == "UnstakeRequested":
            objs.append({"kind": "unstake", "id": str(f["requestId"])})
        elif name == "Staked":
            objs.append({"kind": "stake", "id": f["owner"]})
    ok = int(rc["status"], 16) == 1
    return TxConfirm(status="confirmed" if ok else "reverted", block_number=int(rc["blockNumber"], 16), objects=objs)


# ================================================================ testnet (calldata only)
class TestnetLedger:
    mode = "testnet"
    CACHE_S = 5.0

    def __init__(self, env, *, deployment: dict | None = None, rpc: Rpc | None | bool = False):
        self.env = env
        self.chain_id = int(env.get("TESTNET_CHAIN_ID", "998"))
        self.dep = deployment if deployment is not None else _deployment(env.get("WI_DEPLOYMENT"), self.chain_id)
        url = env.get("HYPEREVM_TESTNET_RPC") or "https://rpc.hyperliquid-testnet.xyz/evm"
        self.rpc = Rpc(url, timeout=10.0) if rpc is False else rpc
        self.c = _contracts(self.dep) if self.dep else {}
        self.signers: dict = {}  # the testnet engine never signs
        self._cache: dict = {}

    # ------------------------------------------------------------ helpers
    def _need_dep(self) -> None:
        if not self.dep:
            raise ApiError(503, "RPC_UNAVAILABLE", "No testnet deployment",
                           f"contracts/deployments/{self.chain_id}.json is missing (the owner runs make deploy-testnet)")

    def _tx(self, cname: str, desc: str, fn: str, *args) -> TxRequest:
        return TxRequest(chain_id=self.chain_id, to=self.c[cname].address, data=self.c[cname].encode(fn, *args),
                         description=desc)

    def _env(self, cls, txs: list[TxRequest]):
        if cls is None:
            return {"mode": "testnet", "status": "needs_signature", "result": None,
                    "txs": [t.model_dump(by_alias=True) for t in txs]}
        return cls(mode="testnet", status="needs_signature", result=None, txs=txs)

    def _cached(self, key, fn):
        hit = self._cache.get(key)
        now = time.monotonic()
        if hit and now - hit[0] < self.CACHE_S:
            return hit[1]
        v = fn()
        self._cache[key] = (now, v)
        return v

    def _read(self, items: list[tuple]) -> dict:
        self._need_dep()
        if self.rpc is None:
            raise ApiError(503, "RPC_UNAVAILABLE", "Offline", "this testnet adapter has no RPC")
        rd = Reader(self.rpc, self.c)
        for it in items:
            rd.add(*it)
        return rd.run()

    def _user(self, addr: str) -> dict:
        return self._cached(("user", addr), lambda: self._read([("u", "Lens", "userView", addr)])["u"])

    @staticmethod
    def _unsupported(what: str) -> ApiError:
        return ApiError(503, "RPC_UNAVAILABLE", "Not wired in testnet mode",
                        f"{what} needs indexed chain history (Phase 13); use the portal's chain reads or sim mode")

    @staticmethod
    def _owner_script(what: str) -> ApiError:
        return ApiError(409, "OWNER_SCRIPT", "Owner script only",
                        f"{what} needs the quoter/reporter key, which the testnet engine never holds")

    # ------------------------------------------------------------ meta
    def health(self) -> Health:
        return Health(ok=bool(self.dep), mode="testnet", chain_id=self.chain_id, engine_version=cat.ENGINE_VERSION,
                      spec_hash=cat.spec_hash(), sim_time=None)

    def config(self):
        return base_config("testnet", ChainInfo(id=self.chain_id, name="HyperEVM testnet",
                                                rpc_url=self.rpc.url if self.rpc else ""),
                           {n: c.address for n, c in self.c.items()})

    def tx_confirm(self, tx_hash: str) -> TxConfirm:
        self._need_dep()
        return _confirm(self.rpc, tx_hash)

    # ------------------------------------------------------------ reads (Lens, 5 s cache)
    def balances(self, wid: str, addr: str) -> Balances:
        u = self._user(addr)
        locked = sum(o["order"]["qty"] * (o["order"]["tick"] if o["order"]["isBid"] else 100 - o["order"]["tick"]) * 10_000
                     for o in u["orders"] if not o["order"]["claimed"])  # escrow still in the auction (fee 0 in v0)
        return Balances(usdc_e6=u["usdcBalance"], locked_e6=locked, senior_shares=u["seniorShares"],
                        junior_shares=u["juniorShares"])

    def pool(self, wid: str) -> PoolState:
        raise self._unsupported("the pool NAV history")

    def staking(self, wid: str, owner: str | None) -> StakingView:
        r = self._cached(("staking", owner), lambda: self._read(
            [("ts", "WIStaking", "totalStaked"), ("tsh", "WIStaking", "totalShares"),
             ("cd", "WIStaking", "unstakeCooldown"), ("cap", "WIStaking", "haircutCapBps")]
            + ([("u", "Lens", "userView", owner)] if owner else [])))
        u = r.get("u")
        return StakingView(owner=owner, wi_balance_wei=str(u["wiBalance"] if u else 0),
                           staked_shares=str(u["stakedShares"] if u else 0),
                           staked_value_wei=str(u["votingPower"] if u else 0),
                           voting_power_wei=str(u["votingPower"] if u else 0), total_staked_wei=str(r["ts"]),
                           total_shares=str(r["tsh"]), cooldown_days=r["cd"] // 86400, haircut_cap_bps=r["cap"],
                           cooldowns=[], haircuts=[],
                           note="testnet: cooldown and haircut history need indexed events (Phase 13)")

    # ------------------------------------------------------------ writes (calldata only)
    def faucet(self, wid: str, addr: str, amount: int, cls):
        self._need_dep()
        return self._env(cls, [self._tx("MockUSDC", f"mint {amount} MockUSDC base units to {addr}", "mint", addr, amount)])

    def deposit(self, wid: str, body, key, cls):
        self._need_dep()
        fn = "depositSenior" if body.tranche == "senior" else "depositJunior"
        return self._env(cls, [self._tx("MockUSDC", "allow the pool to take the deposit", "approve",
                                        self.c["PoolVault"].address, body.amount_e6),
                               self._tx("PoolVault", f"{body.tranche} deposit", fn, body.amount_e6)])

    def withdraw(self, wid: str, body, key, cls):
        self._need_dep()
        return self._env(cls, [self._tx("PoolVault", f"request a {body.tranche} withdrawal", "requestWithdraw",
                                        0 if body.tranche == "senior" else 1, body.shares)])

    def cancel_withdraw(self, wid: str, rid: int, body, key, cls):
        self._need_dep()  # owner-only is enforced by the contract (msg.sender == request owner), not here
        return self._env(cls, [self._tx("PoolVault", f"cancel withdrawal request {rid} (before maturity)",
                                        "cancelWithdraw", rid)])

    def post_order(self, wid: str, aid: str, body, key, cls):
        self._need_dep()
        from wi.engine.eip712 import index_id, market_id
        from wi.engine.state import DEFAULT_PARAMS
        from wi.engine.units import TICK, date_to_day

        try:
            _, cid, day = aid.split("_", 2)
            site = cat.CONTRACTS[cid]
        except (ValueError, KeyError):
            raise ApiError(404, "NOT_FOUND", "Unknown auction", aid) from None
        R = DEFAULT_PARAMS["basisRangeTenths"]
        mk = market_id(index_id(cat.pair_index(site)), date_to_day(day), -R, R)
        tick = body.limit_price_e6 // TICK
        bid = body.side == "buy"
        fee = self._read([("f", "BatchAuction", "auctionFeePerUnit")])["f"] if self.rpc else 0
        escrow = body.qty * ((tick if bid else 100 - tick) * TICK + fee)
        return self._env(cls, [self._tx("MockUSDC", "allow the auction to take the escrow", "approve",
                                        self.c["BatchAuction"].address, escrow),
                               self._tx("BatchAuction", f"{body.side} {body.qty} at {tick}c", "placeOrder", mk, bid,
                                        tick, body.qty)])

    def clear(self, wid: str, aid: str, admin: bool, cls):
        self._need_dep()
        from wi.engine.eip712 import index_id, market_id
        from wi.engine.state import DEFAULT_PARAMS
        from wi.engine.units import date_to_day

        try:
            _, cid, day = aid.split("_", 2)
            site = cat.CONTRACTS[cid]
        except (ValueError, KeyError):
            raise ApiError(404, "NOT_FOUND", "Unknown auction", aid) from None
        R = DEFAULT_PARAMS["basisRangeTenths"]
        return self._env(cls, [self._tx("BatchAuction", "clear the auction (anyone, after the cutoff)", "clear",
                                        market_id(index_id(cat.pair_index(site)), date_to_day(day), -R, R))])

    def cancel_order(self, wid, aid, oid, trader, cls):
        raise ApiError(409, "NOT_CANCELLABLE", "Orders cannot be cancelled", "v0 auctions have no cancels (SPEC 5)")

    def stake(self, wid: str, owner: str, amount: int, cls):
        self._need_dep()
        return self._env(cls, [self._tx("WIToken", "allow staking to take the WI", "approve",
                                        self.c["WIStaking"].address, amount),
                               self._tx("WIStaking", "stake WI", "stake", amount)])

    def unstake_request(self, wid: str, owner: str, shares: int, cls):
        self._need_dep()
        return self._env(cls, [self._tx("WIStaking", "start the unstake cooldown", "requestUnstake", shares)])

    def unstake_claim(self, wid: str, owner: str, rid: int, cls):
        self._need_dep()
        return self._env(cls, [self._tx("WIStaking", "claim unstaked WI", "claimUnstake", rid)])

    def quote(self, *a, **k):
        raise self._owner_script("quoting a policy")

    def buy(self, *a, **k):
        raise self._owner_script("selling a policy (the buyer's tx carries a quoter signature)")

    def oracle_report(self, *a, **k):
        raise self._owner_script("posting an oracle report")

    def house_tick(self, *a, **k):
        raise self._owner_script("the house market maker")

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)

        def _na(*a, **k):
            raise self._unsupported(name)
        return _na


__all__ = ["EvmLedger", "AnvilLedger", "TestnetLedger", "MAX_UINT"]
