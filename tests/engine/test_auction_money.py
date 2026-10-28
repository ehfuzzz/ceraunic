"""Auction money failures the engine layer adds on top of wi.auction.clear (tested there):
the per-unit fee, the per-order `ahead` queue position and the O(1) claim formula.

How this could silently lose money: a fee that is escrowed but not charged (or charged twice), a
claim that refunds more than escrow - cost - fee, an O(1) fill that differs from the clearing fill
(units minted or burned at the marginal tick), or auction escrow that does not drain to exactly 0.
"""
import random

from wi.auction.clear import Order, clear
from wi.engine import auction
from wi.engine.markets import create_market, register_index
from wi.engine.reducer import Ledger
from wi.engine.scenario import ANVIL, default_world
from wi.engine.units import TICK, UNIT


def _book(rng):
    n = rng.randint(1, 60)
    c = rng.randint(5, 95)
    out = []
    for _ in range(n):
        t = min(99, max(1, c + rng.randint(-3, 3))) if rng.random() < 0.6 else rng.randint(1, 99)
        out.append({"isBid": rng.random() < 0.5, "tick": t, "qty": rng.choice([1, 2, 3, 5, 10, rng.randint(1, 10**6)])})
    return out


def test_engine_auction_conserves_money_with_fees_on_4000_random_books():
    rng = random.Random(7)
    traded = 0
    for _ in range(4000):
        orders = _book(rng)
        fee = rng.choice([0, 0, 1, 2_500, 10_000])
        r = auction.settle_book(orders, fee)
        ref = clear([Order(i + 1, o["isBid"], o["tick"], o["qty"]) for i, o in enumerate(orders)])
        assert (r["pStar"], r["qStar"]) == (ref.p_star, ref.q_star)
        assert [o["fill"] for o in r["orders"]] == list(ref.fills)
        bid = sum(o["fill"] for o in r["orders"] if o["isBid"])
        off = sum(o["fill"] for o in r["orders"] if not o["isBid"])
        assert bid == off == r["qStar"]
        assert sum(o["cost"] for o in r["orders"]) == r["qStar"] * UNIT
        assert sum(o["fee"] for o in r["orders"]) == 2 * r["qStar"] * fee
        for o in r["orders"]:
            assert o["refund"] >= 0 and o["escrow"] == o["cost"] + o["fee"] + o["refund"]
        traded += r["qStar"] > 0
    assert traded > 1000


def test_reducer_auction_path_drains_escrow_and_pays_fees_to_treasury():
    """Same books through Ledger.emit (I1/I2/I3 asserted per event): escrow ends at 0, treasury == fees."""
    rng = random.Random(11)
    w = default_world()
    traders = ANVIL[4:10]
    led = Ledger(w)
    for t in traders:
        led.emit(0, "AccountFunded", {"account": t, "amount": 10**18})
    iid = register_index(led, 0, "PAIR:LGA-NYC:TMAX:v1", kind="PAIR", scale=10, station="NYC", metro="NYC",
                         inputs=["a", "b"])
    for day in range(200):
        fee = rng.choice([0, 3_000])
        led.emit(led.last_line["ts"], "ParamsSet", {"key": "auctionFeePerUnit", "value": fee})
        ts0 = (day + 1) * 86_400 - 36_000
        mk = create_market(led, ts0, iid, day + 1, -50, 50, True)
        orders = _book(rng)[:40]
        for o in orders:
            side = o["tick"] if o["isBid"] else 100 - o["tick"]
            qty = max(o["qty"], -(-UNIT // (side * TICK)))  # public orders carry >= 1 USDC escrow
            auction.place_order(led, ts0, mk, rng.choice(traders), o["isBid"], o["tick"], qty)
        cut = led.state["markets"][mk]["cutoff"]
        before = led.state["bal"].get("@treasury", 0)
        c = auction.clear_market(led, cut, mk)
        auction.claim_all(led, cut, mk)
        m = led.state["markets"][mk]
        assert m["escrow"] == 0 and m["collateral"] == c["qStar"] * UNIT
        assert led.state["bal"].get("@treasury", 0) - before == 2 * c["qStar"] * fee
