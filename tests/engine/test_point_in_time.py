"""Point-in-time and settlement-source failures.

How this could silently corrupt data or lose money: a quote priced with ladder candles or basis finals
that did not exist yet at the quote time; a hedge filled with a book or candle stamped after
T = close - 24 h; a policy settled on a value other than the last accepted report of the fixed vintage,
on a later source revision, or before the index finalized.
"""
import json
from functools import lru_cache
from pathlib import Path

import pytest

from wi.engine import oracle, policy, pool, pricing
from wi.engine.markets import create_market, register_index
from wi.engine.reducer import Ledger
from wi.engine.scenario import ANVIL, default_world, run_fixture
from wi.engine.state import Revert
from wi.engine.units import UNIT, at_utc, date_to_day

INPUTS = Path(__file__).parent / "fixtures" / "nyc_30d_inputs.json"


@lru_cache(maxsize=None)
def _inputs() -> dict:
    return json.loads(INPUTS.read_bytes())


@lru_cache(maxsize=None)
def _run(poison: bool = False):
    return run_fixture(_inputs(), poison_after_decision=poison)


def test_hedge_ignores_books_and_candles_after_decision_time():
    clean, poisoned = _run(False)["ledger"], _run(True)["ledger"]
    pick = lambda led: [ln["payload"] for ln in led.lines if ln["type"] in ("HedgeDecision", "HedgeFilled")]  # noqa: E731
    assert pick(clean) == pick(poisoned) and len(pick(clean)) == 60
    for ln in clean.lines:
        if ln["type"] == "HedgeDecision":
            p = ln["payload"]
            assert p["snapshotTs"] <= p["decisionTs"] == p["closeTs"] - 86_400 <= ln["ts"]


def test_every_quote_reprices_identically_from_the_final_state():
    """Re-price each logged quote at its original ts from the END state (which holds every later final and
    candle). Any look-ahead in the ladder or basis-history read would change a component."""
    run = _run(False)
    led, st = run["ledger"], run["ledger"].state
    ladders = {int(k): v for k, v in _inputs()["ladders"].items()}
    n = 0
    for ln in led.lines:
        if ln["type"] != "QuoteIssued":
            continue
        q = ln["payload"]
        m = st["markets"][q["market"]]
        basis = q["residualMarket"] if q["residualQty"] else None
        if basis is None:  # h = 0: find the basis market of the same day/site to reprice the same way
            site_basis = st["world"]["residualIndexFor"][st["indices"][m["indexId"]]["name"]]
            from wi.engine.eip712 import index_id, market_id
            basis = market_id(index_id(site_basis), m["day"], -50, 50)
        comps = pricing.price_policy(st, ln["ts"], market=q["market"], buyer=q["buyer"], is_long=q["isLong"],
                                     units=q["units"], rungs=ladders[m["day"]], basis_market=basis,
                                     prehistory=run["prehistory"][st["markets"][basis]["indexId"]], nonce=q["nonce"],
                                     expiry=q["expiry"])
        for k in ("stationLeg", "residualLeg", "tail", "residualQty", "residualTick", "deltaPpm", "dataAsOf"):
            assert comps[k] == q[k], (k, ln["seq"])
        assert q["dataAsOf"] <= ln["ts"]
        n += 1
    assert n > 100


def test_settled_values_match_source_data_and_the_revision():
    """Every policy settles on the source value of its site-day (the revised value on the transcription-error
    day, never the wrong revision 0), and the outage day settles nothing (void refunds instead)."""
    run = _run(False)
    led, st = run["ledger"], run["ledger"].state
    cli = {s: {int(d): v for d, v in vals.items()} for s, vals in _inputs()["cli"].items()}
    names = {v: k for k, v in run["ids"].items()}
    rev_day = date_to_day(_inputs()["scenario"]["revisions"][0]["day"])
    seen_rev = False
    for ln in led.lines:
        if ln["type"] != "PolicySettled":
            continue
        pol = st["policies"][str(ln["payload"]["policyId"])]
        m = st["markets"][pol["market"]]
        site = names[m["indexId"]].split(":")[1]
        assert ln["payload"]["x"] == cli[site][m["day"]]
        seen_rev |= site == "LGA" and m["day"] == rev_day
    assert seen_rev
    wrong = [ln for ln in led.lines if ln["type"] == "ReportPosted" and ln["payload"]["revision"] == 0
             and ln["payload"]["day"] == rev_day and ln["payload"]["indexId"] == run["ids"]["CLI:LGA:TMAX:v1"]]
    assert wrong and wrong[0]["payload"]["value"] != cli["LGA"][rev_day]
    voided = [st["policies"][str(ln["payload"]["policyId"])] for ln in led.lines if ln["type"] == "PolicyVoided"]
    out_day = date_to_day(_inputs()["scenario"]["outages"][0]["day"])
    assert voided and all(p["day"] == out_day for p in voided)


def _mini():
    led = Ledger(default_world())
    t = at_utc(200, 12)
    led.emit(t, "AccountFunded", {"account": ANVIL[1], "amount": 10**12})
    led.emit(t, "AccountFunded", {"account": ANVIL[5], "amount": 10**12})
    iid = register_index(led, t, "CLI:LGA:TMAX:v1", kind="CLI", scale=10, station="NYC", metro="NYC", inputs=["x"])
    pool.deposit_junior(led, t, ANVIL[1], 10_000 * UNIT)
    mk = create_market(led, t, iid, 201, 880, 940, False)
    dg = policy.issue_quote(led, t, {"market": mk, "buyer": ANVIL[5], "isLong": True, "units": 6, "expiry": t + 3600,
                                     "nonce": 1, "stationLeg": 2 * UNIT, "residualLeg": 0, "tail": 0,
                                     "residualMarket": "0x" + "00" * 32, "residualQty": 0, "residualTick": 0,
                                     "deltaPpm": 0, "dataAsOf": t})
    pid = policy.buy_policy(led, t, dg)
    policy.bind(led, at_utc(201, 3, 5), pid, 0)
    return led, iid, pid


def test_no_settlement_before_finalize_and_no_change_of_vintage():
    led, iid, pid = _mini()
    v0 = "0x" + "ab" * 32
    oracle.post_report(led, at_utc(202, 12), iid, 201, 930, vintage_hash=v0)
    with pytest.raises(Revert) as e:
        policy.settle_policy(led, at_utc(202, 13), pid)  # posted, not final
    assert e.value.name == "NotFinal"
    with pytest.raises(Revert) as e:  # a later source revision (new vintage) cannot replace the fixed vintage
        oracle.post_report(led, at_utc(202, 18), iid, 201, 950, revision=1, as_of=at_utc(202, 12),
                           vintage_hash="0x" + "cd" * 32)
    assert e.value.name == "VintageChanged"
    oracle.post_report(led, at_utc(202, 18), iid, 201, 910, revision=1, as_of=at_utc(202, 12), vintage_hash=v0)
    with pytest.raises(Revert) as e:  # after the dispute window nothing can be posted
        oracle.post_report(led, at_utc(203, 12), iid, 201, 940, revision=2, as_of=at_utc(203, 11), vintage_hash=v0)
    assert e.value.name == "WindowClosed"
    oracle.finalize(led, at_utc(203, 12), iid, 201)
    pay = policy.settle_policy(led, at_utc(203, 12), pid)
    assert pay == 6 * 500_000  # the corrected revision (91.0 F), not 93.0 or 95.0
