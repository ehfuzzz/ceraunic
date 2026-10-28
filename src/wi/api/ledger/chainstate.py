"""Engine-shaped state read back from the contracts (anvil reads + the parity drift check).

`overlay(shadow)` deep-copies the engine state and overwrites every field the contracts hold with the value
read from chain (one batched JSON-RPC round trip per call to `run`): USDC and WI balances, both tranche
ledgers and share books, per-day books, withdrawal and unstake requests, the WI staking totals, every policy,
order, book result, tick level, market collateral, position and oracle observation, and the PolicyManager
escrow. The API views then run on that state, so an anvil read reports what the chain says.

Each overwrite also compares the chain value with the engine value; the differences are the drift. After every
anvil write the drift must be empty (checked in EvmLedger.write), which makes a view computed on the engine
state identical to the same view computed on chain.

Engine-only fields stay as they are: Kalshi hedges and the house's per-day attribution (off chain), quote
metadata, timestamps of engine actions, `@kalshi` (the off-chain venue).
"""
from __future__ import annotations

from wi.engine.state import copy_state

from .. import catalog as cat
from .chain import Contract, Reader, Rpc
from .mirror import TRANCHE_NAME, TREASURY

STATUS = ["None", "Bought", "Bound", "Settled", "Voided"]


def _day(k: str) -> int:
    return int(k)


def overlay(rpc: Rpc, c: dict[str, Contract], shadow: dict) -> tuple[dict, list[str]]:
    st = copy_state(shadow)
    rd = Reader(rpc, c)
    drift: list[str] = []

    def put(obj: dict, key, value, path: str, *, keep_absent_zero: bool = False) -> None:
        old = obj.get(key)
        if old != value and not (keep_absent_zero and old is None and not value):
            drift.append(f"{path}: engine={old!r} chain={value!r}")
        if keep_absent_zero and old is None and not value:
            return
        obj[key] = value

    # ------------------------------------------------ reads
    for a in st["bal"]:
        if a.startswith("0x"):
            rd.add(("bal", a), "MockUSDC", "balanceOf", a)
    rd.add(("bal", "@treasury"), "MockUSDC", "balanceOf", TREASURY)
    rd.add("escrow", "PolicyManager", "policyEscrow")
    for f in ("seniorAssets", "juniorAssets", "reserved", "deployed", "cash", "totalJuniorShares"):
        rd.add(("pool", f), "PoolVault", f)
    rd.add(("pool", "seniorSupply"), "SeniorShare", "totalSupply")
    pool = st["pool"]
    for a in pool["seniorShares"]:
        rd.add(("sS", a), "SeniorShare", "balanceOf", a)
    for a in pool["juniorShares"]:
        rd.add(("jS", a), "PoolVault", "juniorSharesOf", a)
    days = set()
    for book in ("deployedByDay", "openPolicies", "dayPnl", "closed", "houseDone"):
        days |= set(pool[book])
    for d in days:
        for fn in ("deployedByDay", "openPolicies", "dayPnl", "dayClosed", "houseDone"):
            rd.add((fn, d), "PoolVault", fn, _day(d))
    for rid in pool["withdrawals"]:
        rd.add(("wd", rid), "PoolVault", "getWithdrawRequest", int(rid))
    wi = st["wi"]
    for a in wi["bal"]:
        if a.startswith("0x"):
            rd.add(("wibal", a), "WIToken", "balanceOf", a)
    for f in ("totalStaked", "totalShares", "totalBurned"):
        rd.add(("wi", f), "WIStaking", f)
    for a in wi["shares"]:
        rd.add(("wish", a), "WIStaking", "sharesOf", a)
    for rid in wi["unstakes"]:
        rd.add(("un", rid), "WIStaking", "getUnstakeRequest", int(rid))
    for pid in st["policies"]:
        rd.add(("pol", pid), "PolicyManager", "getPolicy", int(pid))
        rd.add(("rid", pid), "PolicyManager", "residualOrderOf", int(pid))
    for oid, o in st["orders"].items():
        rd.add(("ord", oid), "BatchAuction", "getOrder", int(oid))
        if o["claimed"]:
            rd.add(("fill", oid), "BatchAuction", "fillOf", int(oid))
    real = {mk: m for mk, m in st["markets"].items() if not m.get("__virtual__")}
    for mk, m in real.items():
        rd.add(("mkt", mk), "PolicyManager", "getMarket", mk)
        rd.add(("coll", mk), "PolicyManager", "marketCollateral", mk)
        if m["auctioned"]:
            rd.add(("book", mk), "BatchAuction", "getBook", mk)
            for t in set(m["levels"]["b"]) | set(m["levels"]["o"]):
                rd.add(("lvl", mk, t), "BatchAuction", "level", mk, int(t))
    for k in st["pos"]:
        mk, trader = k.split("|")
        rd.add(("pos", k), "PolicyManager", "positionOf", mk, trader)
    for k in st["obs"]:
        iid, d = k.split(":")
        rd.add(("obs", k), "OracleAdapter", "observation", iid, int(d))
    r = rd.run()

    # ------------------------------------------------ overwrite + compare
    for a in list(st["bal"]):
        if a.startswith("0x"):
            put(st["bal"], a, r[("bal", a)], f"bal.{a}")
    put(st["bal"], "@treasury", r[("bal", "@treasury")], "bal.@treasury", keep_absent_zero=True)
    put(st["pm"], "escrow", r["escrow"], "pm.escrow")
    for f, k in (("seniorAssets", "senior"), ("juniorAssets", "junior"), ("reserved", "reserved"),
                 ("deployed", "deployed"), ("cash", "cash"), ("totalJuniorShares", "juniorSupply"),
                 ("seniorSupply", "seniorSupply")):
        put(pool, k, r[("pool", f)], f"pool.{k}")
    for a in pool["seniorShares"]:
        put(pool["seniorShares"], a, r[("sS", a)], f"pool.seniorShares.{a}")
    for a in pool["juniorShares"]:
        put(pool["juniorShares"], a, r[("jS", a)], f"pool.juniorShares.{a}")
    for d in days:
        for fn, book in (("deployedByDay", "deployedByDay"), ("openPolicies", "openPolicies"), ("dayPnl", "dayPnl")):
            put(pool[book], d, r[(fn, d)], f"pool.{book}.{d}", keep_absent_zero=True)
        for fn, book in (("dayClosed", "closed"), ("houseDone", "houseDone")):
            v = r[(fn, d)]
            if bool(pool[book].get(d, False)) != v:
                drift.append(f"pool.{book}.{d}: engine={pool[book].get(d)!r} chain={v!r}")
            if v:
                pool[book][d] = True
            else:
                pool[book].pop(d, None)
    for rid, req in pool["withdrawals"].items():
        c_ = r[("wd", rid)]
        for k, v in (("owner", c_["owner"]), ("tranche", TRANCHE_NAME[c_["tranche"]]), ("claimed", c_["claimed"]),
                     ("claimableAt", c_["claimableAt"]), ("shares", c_["shares"])):
            put(req, k, v, f"pool.withdrawals.{rid}.{k}")
    for a in list(wi["bal"]):
        if a.startswith("0x"):
            put(wi["bal"], a, r[("wibal", a)], f"wi.bal.{a}")
    put(wi, "totalStaked", r[("wi", "totalStaked")], "wi.totalStaked")
    put(wi, "totalShares", r[("wi", "totalShares")], "wi.totalShares")
    put(wi, "burned", r[("wi", "totalBurned")], "wi.burned")
    for a in wi["shares"]:
        put(wi["shares"], a, r[("wish", a)], f"wi.shares.{a}")
    for rid, u in wi["unstakes"].items():
        c_ = r[("un", rid)]
        for k in ("owner", "claimed", "claimableAt", "shares"):
            put(u, k, c_[k], f"wi.unstakes.{rid}.{k}")
    for pid, pol in st["policies"].items():
        c_ = r[("pol", pid)]
        for k, v in (("buyer", c_["buyer"]), ("market", c_["market"]), ("isLong", c_["isLong"]),
                     ("status", STATUS[c_["status"]]), ("units", c_["units"]), ("boundUnits", c_["boundUnits"]),
                     ("premium", c_["premium"]), ("fee", c_["fee"])):
            put(pol, k, v, f"policies.{pid}.{k}")
        put(pol, "residualOrderId", r[("rid", pid)], f"policies.{pid}.residualOrderId", keep_absent_zero=True)
    for oid, o in st["orders"].items():
        c_ = r[("ord", oid)]
        for k in ("trader", "market", "isBid", "tick", "claimed", "qty", "ahead"):
            put(o, k, c_[k], f"orders.{oid}.{k}")
        if ("fill", oid) in r:
            put(o, "fill", r[("fill", oid)], f"orders.{oid}.fill")
    for mk, m in real.items():
        c_ = r[("mkt", mk)]
        if not c_["exists"]:
            drift.append(f"markets.{mk}: missing on chain")
            continue
        for k in ("indexId", "day", "lo", "hi", "saleCutoff", "houseCutoff", "cutoff", "bindBy", "auctioned"):
            put(m, k, c_[k], f"markets.{mk}.{k}")
        put(m, "collateral", r[("coll", mk)], f"markets.{mk}.collateral")
        if m["auctioned"]:
            b = r[("book", mk)]
            if b["cleared"]:
                res = {k: b[k] for k in ("pStar", "qStar", "tb", "to", "mb", "mo")}
                eng = m["cleared"] or {}
                for k, v in res.items():
                    if eng.get(k) != v:
                        drift.append(f"markets.{mk}.cleared.{k}: engine={eng.get(k)!r} chain={v!r}")
                m["cleared"] = res | {"at": eng.get("at", m["cutoff"])}
            elif m["cleared"] is not None:
                drift.append(f"markets.{mk}.cleared: engine cleared, chain not")
                m["cleared"] = None
            if b["orderCount"] != len(m["orderIds"]):
                drift.append(f"markets.{mk}.orderCount: engine={len(m['orderIds'])} chain={b['orderCount']}")
            for t in set(m["levels"]["b"]) | set(m["levels"]["o"]):
                bid, offer = r[("lvl", mk, t)]
                put(m["levels"]["b"], t, bid, f"markets.{mk}.levels.b.{t}", keep_absent_zero=True)
                put(m["levels"]["o"], t, offer, f"markets.{mk}.levels.o.{t}", keep_absent_zero=True)
    for k, ps in st["pos"].items():
        c_ = r[("pos", k)]
        for ek, ck in (("long", "longQty"), ("short", "shortQty"), ("paid", "paid"), ("done", "claimed")):
            put(ps, ek, c_[ck], f"pos.{k}.{ek}")
    for k, ob in st["obs"].items():
        c_ = r[("obs", k)]
        status = "void" if c_["voided"] else "final" if c_["finalized"] else "posted" if c_["posted"] else None
        put(ob, "status", status, f"obs.{k}.status")
        if status in ("posted", "final"):
            for ek, ck in (("value", "value"), ("revision", "revision"), ("asOf", "asOf"), ("vintage", "vintageHash")):
                put(ob, ek, c_[ck], f"obs.{k}.{ek}")
    return st, drift


def fresh_chain_problems(rpc: Rpc, c: dict[str, Contract]) -> list[str]:
    """Why this chain cannot host a new world (empty list = fresh Phase 8 deployment, configured, no state)."""
    rd = Reader(rpc, c)
    rd.add("pid", "PolicyManager", "lastPolicyId")
    rd.add("oid", "BatchAuction", "lastOrderId")
    rd.add("j", "PoolVault", "juniorAssets")
    rd.add("st", "WIStaking", "totalStaked")
    rd.add("pm", "PoolVault", "policyManager")
    r = rd.run()
    out = []
    if r["pm"] == "0x" + "00" * 20:
        out.append("contracts are not configured (run make configure-anvil)")
    if r["pid"] or r["oid"] or r["j"] or r["st"]:
        out.append("the chain already holds policies, orders, pool money or stake (start a fresh anvil)")
    return out


def param_problems(rpc: Rpc, c: dict[str, Contract], params: dict[str, int], roles: dict) -> list[str]:
    """Chain settings that differ from the engine parameters / roles the world runs with."""
    rd = Reader(rpc, c)
    want = {
        ("PoolVault", "capBps"): params["capBps"], ("PoolVault", "jMinBps"): params["jMinBps"],
        ("PoolVault", "seniorPremiumBps"): params["seniorPremiumBps"],
        ("PoolVault", "minJuniorForSenior"): params["minJuniorForSenior"],
        ("PoolVault", "withdrawDelay"): params["withdrawDelay"],
        ("PoolVault", "houseReturnWindow"): params["houseReturnWindow"],
        ("WIStaking", "unstakeCooldown"): params["unstakeCooldown"],
        ("WIStaking", "haircutCapBps"): params["haircutCapBps"],
        ("PolicyManager", "saleCutoffOffset"): params["saleCutoffOffset"],
        ("PolicyManager", "houseCutoffOffset"): params["houseCutoffOffset"],
        ("PolicyManager", "cutoffOffset"): params["cutoffOffset"],
        ("PolicyManager", "bindByOffset"): params["bindByOffset"],
        ("PolicyManager", "rfqFeePerUnit"): params["rfqFeePerUnit"],
        ("BatchAuction", "auctionFeePerUnit"): params["auctionFeePerUnit"],
        ("BatchAuction", "MAX_ORDERS"): params["maxOrders"],
        ("OracleAdapter", "maxReportAge"): params["maxReportAge"],
        ("PolicyManager", "quoter"): roles["quoter"], ("PolicyManager", "house"): roles["house"],
        ("PolicyManager", "treasury"): TREASURY, ("BatchAuction", "house"): roles["house"],
        ("PoolVault", "house"): roles["house"],
    }
    for (cn, fn) in want:
        rd.add((cn, fn), cn, fn)
    for rep in roles["reporters"]:
        rd.add(("rep", rep), "OracleAdapter", "isReporter", rep)
    for dep in roles["juniorDepositors"]:
        rd.add(("jd", dep), "PoolVault", "juniorDepositor", dep)
    r = rd.run()
    out = [f"{cn}.{fn} = {r[(cn, fn)]!r}, engine {v!r}" for (cn, fn), v in want.items() if r[(cn, fn)] != v]
    out += [f"reporter {a} not allow-listed" for a in roles["reporters"] if not r[("rep", a)]]
    out += [f"junior depositor {a} not allow-listed" for a in roles["juniorDepositors"] if not r[("jd", a)]]
    return out


def world_roles() -> dict:
    return cat.world_file()["roles"]
