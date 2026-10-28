"""Money-failure properties of the one clearing function (AGENTS.md: test only what can lose money).

How clear() could silently lose money: fills that do not balance (units minted or burned), cash
that does not add up to Q* x $1 (collateral minted or burned), a fill above its quantity, a fill
outside its limit, or a clearing price that leaves marketable volume on both sides unfilled.
"""
import random

from wi.auction.clear import TICK, UNIT, Order, clear


def _book(rng: random.Random) -> list[Order]:
    n = rng.randint(1, 60)
    centre = rng.randint(5, 95)
    out = []
    for i in range(n):
        if rng.random() < 0.5:
            tick = min(99, max(1, centre + rng.randint(-3, 3)))   # clustering -> ties
        else:
            tick = rng.randint(1, 99)
        qty = rng.choice([1, 1, 2, 3, 5, 10, rng.randint(1, 1_000_000)])
        out.append(Order(i, rng.random() < 0.5, tick, qty))
    return out


def test_clear_conserves_units_and_cash_on_4000_random_books():
    rng = random.Random(20260930)
    traded = 0
    for _ in range(4000):
        orders = _book(rng)
        r = clear(orders)
        bids = [(o, f) for o, f in zip(orders, r.fills) if o.is_bid]
        offs = [(o, f) for o, f in zip(orders, r.fills) if not o.is_bid]
        assert sum(f for _, f in bids) == r.q_star
        assert sum(f for _, f in offs) == r.q_star
        assert sum(r.cost) == r.q_star * UNIT                     # nothing minted or burned
        assert sum(r.escrow) - sum(r.refund) == r.q_star * UNIT
        for o, f in zip(orders, r.fills):
            assert 0 <= f <= o.qty
            if f:
                assert (o.tick >= r.p_star) if o.is_bid else (o.tick <= r.p_star)
        for rf in r.refund:
            assert rf >= 0
        if r.q_star:
            traded += 1
            unfilled_bid = any(o.tick >= r.p_star and f < o.qty for o, f in bids)
            unfilled_off = any(o.tick <= r.p_star and f < o.qty for o, f in offs)
            assert not (unfilled_bid and unfilled_off)
        else:
            assert all(f == 0 for f in r.fills) and sum(r.refund) == sum(r.escrow)
    assert traded > 1000   # the property was exercised on books that trade


def test_hand_case_from_08_research():
    # bids 10 @ 60 vs offers 5 @ 40 -> p* = 50, tb = 60, to = 40, fill 5 (FIFO at the bid tick)
    orders = [Order(1, True, 60, 4), Order(2, True, 60, 6), Order(3, False, 40, 5)]
    r = clear(orders)
    assert (r.p_star, r.q_star, r.tb, r.to) == (50, 5, 60, 40)
    assert r.fills == (4, 1, 5)
    assert r.cost == (4 * 50 * TICK, 1 * 50 * TICK, 5 * 50 * TICK)
