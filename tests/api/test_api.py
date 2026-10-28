"""API tests: only failures that silently corrupt state or lose money (AGENTS.md testing rules), plus the
plan's parity/golden checks.

- heavy imports would break the Vercel bundle (500 MB) and cold start
- boot guards are the owner's "testnet engine holds no keys" rule
- a retried buy must not charge twice; two concurrent buys must both land (lost update)
- one visitor's world must not move another's money
- the stored event log must replay to the stored snapshot (a dropped or reordered event is silent corruption)
- point in time: no settlement before D+2 12:00Z, quotes use data with ts <= quote time, and the estimator
  ignores sales dated on or after the simulated day
- the scenario's money projection equals the committed golden (sim now; anvil must match the same file)
- testnet mode only ever returns calldata to sign
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import warnings
from pathlib import Path

import pytest

warnings.filterwarnings("ignore", category=DeprecationWarning)
from fastapi.testclient import TestClient  # noqa: E402

from wi.api import catalog as cat  # noqa: E402
from wi.api.app import create_app  # noqa: E402
from wi.api.ledger.sim import SimLedger  # noqa: E402
from wi.api.store import MemoryStore  # noqa: E402

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import run_scenario  # noqa: E402

A = "0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"
B = "0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc"
UNIT = 1_000_000


@pytest.fixture()
def app_store():
    store = MemoryStore()
    app = create_app("sim", {}, ledger=SimLedger(store, {}))
    return TestClient(app), store


@pytest.fixture()
def client(app_store):
    return app_store[0]


def new_world(c: TestClient) -> dict:
    return {"X-WI-World": c.post("/api/v1/sim/worlds").json()["worldId"]}


def business(c, h, owner=A, lat=40.7794, lon=-73.9632):
    return c.post("/api/v1/businesses", headers=h, json={"name": "s", "lat": lat, "lon": lon, "naics": "722515",
                                                          "owner": owner}).json()


def quote(c, h, biz, days=("2026-07-16", "2026-07-16"), units=6, peril="heat", strike=900):
    r = c.post("/api/v1/quotes", headers=h, json={"businessId": biz["businessId"], "peril": peril,
                                                   "strikeTenthsF": strike, "capTenthsF": 60, "units": units,
                                                   "startDay": days[0], "endDay": days[1], "path": "house-hedge"})
    assert r.status_code == 200, r.text
    return r.json()


def usdc(c, h, addr):
    return c.get(f"/api/v1/accounts/{addr}/balances", headers=h).json()["usdcE6"]


def test_api_module_imports_no_heavy_libs():
    code = ("import sys, wi.api.app;"
            "bad=[m for m in ('pandas','xarray','netCDF4','pyarrow','matplotlib','scipy','statsmodels','web3') if m in sys.modules];"
            "print(bad)")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip()
    assert out == "[]"


@pytest.mark.parametrize("mode,env", [
    ("testnet", {"HOUSE_MM_PRIVATE_KEY": "x"}),
    ("testnet", {"DEPLOYER_MNEMONIC": "x"}),
    ("testnet", {"house_private_key": "x"}),
    ("anvil", {"VERCEL": "1"}),
    ("sim", {"VERCEL": "1"}),
])
def test_boot_guards_refuse_unsafe_config(mode, env):
    with pytest.raises(RuntimeError):
        create_app(mode, env)


def test_idempotent_buy_charges_once_and_rejects_key_reuse(client):
    h = new_world(client)
    client.post("/api/v1/faucet", json={"address": A, "amountE6": 500 * UNIT}, headers=h)
    q = quote(client, h, business(client, h), days=("2026-07-16", "2026-07-18"))
    buy = {"quoteId": q["quoteId"], "holder": A}
    r1 = client.post("/api/v1/policies", json=buy, headers={**h, "Idempotency-Key": "k1"})
    r2 = client.post("/api/v1/policies", json=buy, headers={**h, "Idempotency-Key": "k1"})
    assert r1.status_code == r2.status_code == 200 and r1.json() == r2.json()
    assert usdc(client, h, A) == 500 * UNIT - q["premiumE6"]
    assert len(client.get("/api/v1/policies", params={"holder": A}, headers=h).json()) == 1
    r3 = client.post("/api/v1/policies", json=buy, headers={**h, "Idempotency-Key": "k2"})
    assert r3.status_code == 409  # a used quote never charges again
    other = client.post("/api/v1/policies", json={"quoteId": "q_000999", "holder": A}, headers={**h, "Idempotency-Key": "k1"})
    assert other.status_code == 422 and other.json()["code"] == "VALIDATION"
    assert usdc(client, h, A) == 500 * UNIT - q["premiumE6"]


def test_concurrent_buys_both_land_and_money_is_conserved(client):
    h = new_world(client)
    client.post("/api/v1/faucet", json={"address": A, "amountE6": 900 * UNIT}, headers=h)
    biz = business(client, h)
    qs = [quote(client, h, biz, units=u) for u in (3, 5, 7, 9)]
    out = []

    def buy(q):
        out.append(client.post("/api/v1/policies", json={"quoteId": q["quoteId"], "holder": A}, headers=h).status_code)

    ts = [threading.Thread(target=buy, args=(q,)) for q in qs]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert out == [200] * 4
    assert len(client.get("/api/v1/policies", params={"holder": A}, headers=h).json()) == 4
    assert usdc(client, h, A) == 900 * UNIT - sum(q["premiumE6"] for q in qs)


def test_worlds_are_isolated(client):
    h1, h2 = new_world(client), new_world(client)
    client.post("/api/v1/faucet", json={"address": A, "amountE6": 100 * UNIT}, headers=h1)
    client.post("/api/v1/sim/advance", json={"days": 2}, headers=h1)
    assert usdc(client, h2, A) == 0
    c1, c2 = (client.get("/api/v1/sim/clock", headers=h).json()["simTime"] for h in (h1, h2))
    assert c1 != c2 and c2 == "2026-07-15T20:00:00Z"
    assert client.get("/api/v1/pool", headers=h2).json()["capitalE6"] == cat.JUNIOR_SEED + cat.SENIOR_SEED


def test_stored_event_log_replays_to_the_stored_snapshot(app_store):
    from wi.engine.reducer import replay
    from wi.engine.state import state_hash

    c, store = app_store
    h = new_world(c)
    c.post("/api/v1/faucet", json={"address": A, "amountE6": 500 * UNIT}, headers=h)
    q = quote(c, h, business(c, h, lat=40.7769, lon=-73.874), days=("2026-07-16", "2026-07-17"))
    c.post("/api/v1/policies", json={"quoteId": q["quoteId"], "holder": A}, headers=h)
    c.post("/api/v1/sim/advance", json={"days": 4}, headers=h)
    blob = store.load(h["X-WI-World"])
    led = replay(blob["state"]["world"], store.events(h["X-WI-World"]))
    assert led.hash() == state_hash(blob["state"])
    assert led.last_line == blob["last"]


def test_no_settlement_before_d_plus_two_noon_and_quotes_are_point_in_time(client):
    h = new_world(client)
    client.post("/api/v1/faucet", json={"address": A, "amountE6": 500 * UNIT}, headers=h)
    q = quote(client, h, business(client, h))
    assert q["stationLeg"]["asOf"] <= "2026-07-15T20:00:00Z"  # quote read nothing after the quote time
    client.post("/api/v1/policies", json={"quoteId": q["quoteId"], "holder": A}, headers=h)
    seen = []
    for _ in range(3):  # clock rests at 07-15, 07-16, 07-17 20:00Z; D = 07-16 is final at 07-18 12:00Z
        seen.append(len(client.get("/api/v1/settlements", params={"owner": A}, headers=h).json()))
        client.post("/api/v1/sim/advance", json={"days": 1}, headers=h)
    seen.append(len(client.get("/api/v1/settlements", params={"owner": A}, headers=h).json()))
    assert seen == [0, 0, 0, 1]


def test_estimator_ignores_sales_dated_on_or_after_the_sim_day(client):
    import datetime as dt

    def rows(poison: bool):
        out, d = [], dt.date(2026, 4, 1)
        while d <= dt.date(2026, 7, 25):
            v = 100_000 + (d.toordinal() * 7919) % 30_000
            if poison and d >= dt.date(2026, 7, 15):
                v *= 1000
            out.append({"date": d.isoformat(), "grossSalesCents": v})
            d += dt.timedelta(days=1)
        return out

    res = []
    for poison in (False, True):
        h = new_world(client)
        biz = business(client, h)
        client.post(f"/api/v1/businesses/{biz['businessId']}/sales", headers=h, json={"source": "csv", "rows": rows(poison)})
        e = client.post(f"/api/v1/businesses/{biz['businessId']}/elasticity", headers=h).json()
        res.append((e["heat"], e["wet"], e["rowsUsed"], e["recentMeanDailySalesCents"]))
    assert res[0] == res[1]


def test_scenario_money_matches_the_golden(client):
    scenario = json.loads((HERE / "scenario_nyc_3d.json").read_text())
    dump, ok = run_scenario.run("http://testserver", scenario, http=client)
    assert ok
    got = run_scenario.money(dump)
    golden = HERE / "golden" / "scenario_nyc_3d.json"
    if os.environ.get("WI_WRITE_GOLDEN"):
        golden.parent.mkdir(exist_ok=True)
        golden.write_text(json.dumps(got, indent=0) + "\n")
    assert got == json.loads(golden.read_text())


def _house_junior_shares(c, h):
    return sum(p["shares"] for p in c.get("/api/v1/positions", params={"owner": cat.HOUSE}, headers=h).json()["lp"]
               if p["tranche"] == "junior")


def _house_junior_request(c, h):
    """A request the epoch can never pay (it would empty the junior tranche: JuniorMinimum), so it stays open."""
    shares = _house_junior_shares(c, h)
    r = c.post("/api/v1/pool/withdrawals", headers=h, json={"owner": cat.HOUSE, "tranche": "junior", "shares": shares})
    assert r.status_code == 200, r.text
    return shares, r.json()["result"]


def _advance_to(c, h, iso):
    while c.get("/api/v1/sim/clock", headers=h).json()["simTime"] < iso:
        assert c.post("/api/v1/sim/advance", json={"days": 1}, headers=h).status_code == 200


def test_request_past_its_claim_window_lapses_at_the_epoch_and_the_shares_come_back(app_store):
    """An unclaimable matured request must not stay escrowed (and log "deferred" forever): once the 3-day window is
    over the epoch lapses it, the LP holds the shares again and no USDC moved (the lapse event is the only
    withdrawal event after the request; the tranche share supply is unchanged)."""
    client, store = app_store
    h = new_world(client)
    before = _house_junior_shares(client, h)
    shares, t = _house_junior_request(client, h)
    assert shares == before and _house_junior_shares(client, h) == 0  # escrowed
    assert t["status"] == "queued" and t["requestId"] == "1" and t["claimBy"] > t["epochTs"]
    supply0 = client.get("/api/v1/pool", headers=h).json()["juniorShares"]
    _advance_to(client, h, t["epochTs"])
    client.post("/api/v1/sim/advance", json={"days": 1}, headers=h)  # matured: the epoch tries to pay, JuniorMinimum defers it
    assert client.get("/api/v1/pool", headers=h).json()["queue"]["withdrawals"][0]["status"] == "queued"
    assert _house_junior_shares(client, h) == 0
    _advance_to(client, h, t["claimBy"])
    client.post("/api/v1/sim/advance", json={"days": 1}, headers=h)  # the next 12:30Z epoch is past claimBy
    pool1 = client.get("/api/v1/pool", headers=h).json()
    assert pool1["queue"]["withdrawals"][0]["status"] == "lapsed"
    assert _house_junior_shares(client, h) == before
    assert pool1["juniorShares"] == supply0
    wd = [(e["type"], e["payload"]["requestId"]) for e in store.events(h["X-WI-World"])
          if e["type"].startswith("Withdraw")]
    assert wd == [("WithdrawRequested", 1), ("WithdrawLapsed", 1)]  # never paid


def test_cancel_withdrawal_before_maturity_only_and_only_by_the_owner(client):
    h = new_world(client)
    before = _house_junior_shares(client, h)
    _, t = _house_junior_request(client, h)
    url = f"/api/v1/pool/withdraw/{t['requestId']}/cancel"
    other = client.post(url, headers=h, json={"owner": A})
    assert other.status_code == 403 and other.json()["code"] == "FORBIDDEN"
    assert _house_junior_shares(client, h) == 0
    ok = client.post(url, headers=h, json={"owner": cat.HOUSE})
    assert ok.status_code == 200 and ok.json()["result"]["status"] == "cancelled"
    assert _house_junior_shares(client, h) == before
    assert client.post(url, headers=h, json={"owner": cat.HOUSE}).status_code == 409  # shares cannot return twice
    assert _house_junior_shares(client, h) == before
    assert client.post("/api/v1/pool/withdraw/99/cancel", headers=h, json={"owner": cat.HOUSE}).status_code == 404
    _, t2 = _house_junior_request(client, h)  # a second request, cancelled after it matured
    _advance_to(client, h, t2["epochTs"])
    late = client.post(f"/api/v1/pool/withdraw/{t2['requestId']}/cancel", headers=h, json={"owner": cat.HOUSE})
    assert late.status_code == 409 and late.json()["code"] == "NOT_CANCELLABLE"
    assert _house_junior_shares(client, h) == 0  # still escrowed


def test_testnet_mode_returns_calldata_only():
    from wi.api.ledger.evm import EvmLedger

    led = EvmLedger.offline_testnet_for_tests()
    ex = led.faucet("demo", A.lower(), 5 * UNIT, None)
    assert ex["status"] == "needs_signature" and ex["txs"] and all(t["data"].startswith("0x") for t in ex["txs"])
    assert led.signers == {}


ANVIL = pytest.mark.skipif(not os.environ.get("WI_ANVIL_RPC"),
                           reason="set WI_ANVIL_RPC (scripts/anvil-scenario.sh starts a fresh anvil with the 08 deployment)")


@pytest.fixture(scope="module")
def anvil_client():
    from wi.api.ledger.evm import EvmLedger

    env = {"ANVIL_RPC_URL": os.environ["WI_ANVIL_RPC"], "WI_DEPLOYMENT": os.environ.get("WI_DEPLOYMENT", "")}
    led = EvmLedger("anvil", env)
    return TestClient(create_app("anvil", env, ledger=led), raise_server_exceptions=False), led


@ANVIL
def test_anvil_scenario_matches_the_same_golden(anvil_client):
    """Same scenario, contracts as the ledger of record: the money projection must equal the sim golden."""
    c, led = anvil_client
    scenario = json.loads((HERE / "scenario_nyc_3d.json").read_text())
    dump, ok = run_scenario.run("http://testserver", scenario, http=c)
    assert ok
    assert run_scenario.money(dump) == json.loads((HERE / "golden" / "scenario_nyc_3d.json").read_text())
    assert led.mirror.txs > 500 and led.last_drift == []


@ANVIL
def test_anvil_chain_money_moved_behind_the_engine_is_refused(anvil_client):
    """USDC minted on chain outside the engine must surface as CHAIN_DIVERGED, never as a silent balance."""
    c, led = anvil_client
    h = {"X-WI-World": c.post("/api/v1/sim/worlds").json()["worldId"]}
    assert c.post("/api/v1/faucet", json={"address": A, "amountE6": 5 * UNIT}, headers=h).status_code == 200
    assert usdc(c, h, A) == 5 * UNIT
    usdc_c = led.c["MockUSDC"]
    head = led.rpc.call("eth_getBlockByNumber", "latest", False)["timestamp"]
    led.rpc.call("evm_setNextBlockTimestamp", head)
    tx = {"from": cat.OWNER, "to": usdc_c.address, "data": usdc_c.encode("mint", A.lower(), 1)}
    assert int(led.mirror.receipt(led.rpc.call("eth_sendTransaction", tx))["status"], 16) == 1
    r = c.get(f"/api/v1/accounts/{A}/balances", headers=h)
    assert r.status_code == 500 and r.json()["code"] == "CHAIN_DIVERGED"
    w = c.post("/api/v1/faucet", json={"address": A, "amountE6": UNIT}, headers=h)
    assert w.status_code == 500 and w.json()["code"] == "CHAIN_DIVERGED"
    c.post("/api/v1/sim/worlds")  # rewind for whoever runs next


@ANVIL
def test_anvil_withdraw_cancel_and_lapse_are_mirrored_on_chain(anvil_client):
    """Cancel (owner, before maturity) and the epoch's lapse must replay on PoolVault and leave chain == engine."""
    c, led = anvil_client
    h = {"X-WI-World": c.post("/api/v1/sim/worlds").json()["worldId"]}
    before = _house_junior_shares(c, h)
    _, t1 = _house_junior_request(c, h)
    ok = c.post(f"/api/v1/pool/withdraw/{t1['requestId']}/cancel", headers=h, json={"owner": cat.HOUSE})
    assert ok.status_code == 200 and ok.json()["result"]["status"] == "cancelled"
    assert _house_junior_shares(c, h) == before
    _, t2 = _house_junior_request(c, h)
    _advance_to(c, h, t2["claimBy"])
    r = c.post("/api/v1/sim/advance", json={"days": 1}, headers=h)
    assert r.status_code == 200, r.text
    row = c.get("/api/v1/pool", headers=h).json()["queue"]["withdrawals"][-1]
    assert row["status"] == "lapsed" and _house_junior_shares(c, h) == before
    assert led.last_drift == []
    c.post("/api/v1/sim/worlds")  # rewind for whoever runs next
