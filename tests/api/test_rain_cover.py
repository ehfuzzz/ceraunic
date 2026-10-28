"""Rain cover (13-RAIN): only the ways a wet-day cover could silently lose or mint money (AGENTS.md testing rules).

End to end through the HTTP API on the demo snapshot (a private sim world, Chicago bakery at Midway; its rain cover
settles on O'Hare, the KXRAIN Chicago station). Expected payouts are read from the raw NWS CLI file, not from the
snapshot code the engine uses, so a wrong station, a wrong day or a double pay shows up.

- a dry week (O'Hare 0.00 in on all 7 days) pays exactly 0
- a mixed week pays units x $1 on every day with 0.01 in or more and 0 on a trace day ("T" is no rain, as on Kalshi),
  once per day, and the business's balance moves by exactly payouts - premium
- no day is ever sold for more than it can pay (premium <= units x $1), over every day of the replay window
- the Kalshi station leg is costed and filled with the taker fee rounded up once per order, no phantom cent
"""
from __future__ import annotations

import csv
import math
import warnings
from fractions import Fraction
from pathlib import Path

import pytest

warnings.filterwarnings("ignore", category=DeprecationWarning)
from fastapi.testclient import TestClient  # noqa: E402

from wi.api import catalog as cat  # noqa: E402
from wi.api.app import create_app  # noqa: E402
from wi.api.ledger.sim import SimLedger  # noqa: E402
from wi.api.store import MemoryStore  # noqa: E402
from wi.engine.units import DAY_S, date_to_day, day_to_iso  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OWNER = "0x9965507D1a55bcC2695C58ba16FB37d819B0A4dc"
UNIT = 1_000_000
UNITS = 20  # $20 per wet day; <= the 30-contract candle cap, so the Kalshi leg fills in full


def ord_precip() -> dict[str, str]:
    with open(ROOT / "data/cache/eval03/cli/ORD_2026.csv") as f:
        return {r["valid"]: r["precip"] for r in csv.DictReader(f)}


@pytest.fixture()
def api():
    store = MemoryStore()
    ledger = SimLedger(store, {})
    c = TestClient(create_app("sim", {}, ledger=ledger))
    h = {"X-WI-World": c.post("/api/v1/sim/worlds").json()["worldId"]}
    biz = c.post("/api/v1/businesses", headers=h, json={"name": "bakery", "lat": 41.7868, "lon": -87.7522,
                                                        "naics": "311811", "owner": OWNER}).json()
    assert biz["rainStationId"] == "KORD"
    c.post("/api/v1/faucet", headers=h, json={"address": OWNER, "amountE6": 10_000 * UNIT})
    return c, h, biz, ledger


def advance_to_eve(c, h, day_iso: str) -> None:
    """Move the world clock to the 20:00Z rest point before climate day `day_iso` (sales for it are open)."""
    target = (date_to_day(day_iso) - 1) * DAY_S + cat.REST_S
    while True:
        now = c.get("/api/v1/sim/clock", headers=h).json()["simTime"]
        left = (target - _ts(now)) // DAY_S
        if left <= 0:
            return
        c.post("/api/v1/sim/advance", headers=h, json={"days": min(10, left)})


def _ts(iso: str) -> int:
    from datetime import datetime

    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())


def buy_week_and_settle(c, h, biz, first: str) -> tuple[dict, int, int]:
    advance_to_eve(c, h, first)
    last = day_to_iso(date_to_day(first) + 6)
    q = c.post("/api/v1/quotes", headers=h, json={"businessId": biz["businessId"], "peril": "rain", "strikeTenthsF": 0,
                                                  "capTenthsF": 1, "units": UNITS, "startDay": first, "endDay": last,
                                                  "path": "house-hedge"})
    assert q.status_code == 200, q.text
    q = q.json()
    before = c.get(f"/api/v1/accounts/{OWNER}/balances", headers=h).json()["usdcE6"]
    r = c.post("/api/v1/policies", headers=h, json={"quoteId": q["quoteId"], "holder": OWNER})
    assert r.status_code == 200, r.text
    pid = r.json()["result"]["policyId"]
    c.post("/api/v1/sim/advance", headers=h, json={"days": 9})
    pol = c.get(f"/api/v1/policies/{pid}", headers=h).json()
    after = c.get(f"/api/v1/accounts/{OWNER}/balances", headers=h).json()["usdcE6"]
    return pol, before, after


def test_dry_week_pays_zero_trace_days_pay_zero_and_measurable_days_pay_units(api):
    c, h, biz, _ = api
    raw = ord_precip()

    # a mixed week: 2026-08-11..17 at O'Hare = 0.47, T, 0.23, T, 0.05, 0.12, T -> 4 measurable days, 3 trace days
    week = [day_to_iso(date_to_day("2026-08-11") + i) for i in range(7)]
    trace = [d for d in week if raw[d] == "T"]
    measurable = [d for d in week if raw[d] not in ("T", "M") and float(raw[d]) >= 0.01]
    assert len(trace) == 3 and len(measurable) == 4, [raw[d] for d in week]
    pol, before, after = buy_week_and_settle(c, h, biz, week[0])
    assert pol["status"] == "settled" and [s["day"] for s in pol["settlements"]] == week
    by_day = {s["day"]: s for s in pol["settlements"]}
    assert all(by_day[d]["payoutE6"] == UNITS * UNIT and by_day[d]["value"] == 1 for d in measurable)
    assert all(by_day[d]["payoutE6"] == 0 and by_day[d]["value"] == 0 for d in trace)
    paid = sum(s["payoutE6"] for s in pol["settlements"])
    assert paid == UNITS * UNIT * len(measurable)
    assert after - before == paid - pol["premiumE6"] + pol["refundedE6"]

    # a dry week: 2026-09-22..28 at O'Hare = 0.00 in every day
    dry = [day_to_iso(date_to_day("2026-09-22") + i) for i in range(7)]
    assert all(raw[d] not in ("T", "M") and float(raw[d]) == 0.0 for d in dry), [raw[d] for d in dry]
    pol, before, after = buy_week_and_settle(c, h, biz, dry[0])
    assert pol["status"] == "settled" and [s["day"] for s in pol["settlements"]] == dry
    assert all(s["payoutE6"] == 0 and s["value"] == 0 for s in pol["settlements"])
    assert after - before == -pol["premiumE6"] + pol["refundedE6"]


def test_no_day_is_sold_for_more_than_it_can_pay(api):
    """Every climate day of the window, quoted on its eve (next day's Kalshi market open, or not listed), is either
    refused or priced at most units x $1, with the SPEC 6.6 identity intact."""
    from wi.api import quoting

    c, h, biz, ledger = api
    rec = ledger._biz(ledger.read(h["X-WI-World"]), biz["businessId"])
    refused = priced = 0
    for d in range(cat.FIRST_DAY, cat.LAST_DAY + 1):
        advance_to_eve(c, h, day_to_iso(d))
        w = ledger.read(h["X-WI-World"])
        try:
            q = quoting.build(w, biz=rec, peril="rain", strike=0, cap=1, units=UNITS, days=[d], path="house-hedge",
                              nonce0=1, emit=False)
        except Exception as e:  # ApiError NO_PRICE: refused, never sold at a loss-making cap breach
            assert getattr(e, "code", None) == "NO_PRICE", e
            refused += 1
            continue
        priced += 1
        assert 0 < q["premium"] <= UNITS * UNIT, (day_to_iso(d), q["premium"])
        assert q["premium"] == q["station"] + q["tail"] + q["risk"] + q["nfee"], day_to_iso(d)
        assert q["tail"] >= 0 and q["residual"] == 0
    assert priced >= 60, (priced, refused)


def test_kalshi_leg_fee_rounds_up_once_per_order_without_phantom_cents(api):
    """A day whose KXRAIN market is open at quote time: the quoted station leg and the house's paper fill at
    T - 24 h both carry ceil(0.07 x C x P x (1 - P)) cents per order, computed here with exact fractions."""
    c, h, biz, ledger = api
    day = "2026-08-26"  # KXRAIN-26AUG26-CHI: open at 08-25 20:00Z, ask 56c at T - 24 h
    advance_to_eve(c, h, day)
    q = c.post("/api/v1/quotes", headers=h, json={"businessId": biz["businessId"], "peril": "rain", "strikeTenthsF": 0,
                                                  "capTenthsF": 1, "units": UNITS, "startDay": day, "endDay": day,
                                                  "path": "house-hedge"}).json()
    (rung,) = q["stationLeg"]["rungs"]
    assert rung["source"] == "kalshi-ask" and rung["qty"] == UNITS
    ask = rung["askCents"]

    def fee_cents(contracts: int, px: int) -> int:
        return math.ceil(Fraction(7, 100) * contracts * Fraction(px, 100) * Fraction(100 - px, 100) * 100)

    slip = 1  # slipBufferCents
    assert q["stationLegE6"] == (UNITS * ask + fee_cents(UNITS, ask) + UNITS * slip) * 10_000
    c.post("/api/v1/policies", headers=h, json={"quoteId": q["quoteId"], "holder": OWNER})
    c.post("/api/v1/sim/advance", headers=h, json={"days": 2})
    st = ledger.read(h["X-WI-World"]).st
    fill = st["hedges"][f"KXRAIN-CHI:{date_to_day(day)}"]["fill"]
    (r,) = fill["rungs"]
    px = st["hedges"][f"KXRAIN-CHI:{date_to_day(day)}"]["decision"]["rungs"][0]["askCents"]
    assert r["filledCenti"] == UNITS * 100
    assert r["costCents"] == UNITS * px and r["feeCents"] == fee_cents(UNITS, px)
    assert fill["costE6"] == (UNITS * px + fee_cents(UNITS, px)) * 10_000
