"""The 30-day one-metro fixture run (plan 07-06, SPEC section 4 timeline). Pure: inputs dict in,
Ledger out. The script scripts/engine_fixture_run.py builds the inputs from data/ and writes the
manifest; the tests call `run_fixture` directly.

World: NYC metro, settlement station Central Park (CLI:NYC, Kalshi KXHIGHNY), residual indices
PAIR:LGA-NYC and PAIR:JFK-NYC on CLI values. Four businesses with opposite exposure (heat-hurt and
cool-hurt at LGA and at JFK), one house-seeded junior deposit, one senior LP, two WI stakers, one
any-wallet trader with seeded random auction orders and one RFQ. One reporter outage (LGA, one day)
voids the LGA indices for that day; one transcription error is corrected by a revision.
The P&L is labelled "engine demo" and is never evidence.
"""
from __future__ import annotations

import random

from . import auction, house_mm, markets, oracle, policy, pool, pricing, rfq, staking
from .margin import breaches
from .reducer import Ledger
from .state import DEFAULT_PARAMS, P, Revert
from .units import DAY_S, TICK, UNIT, at_utc, date_to_day

ANVIL = [
    "0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266", "0x70997970c51812dc3a010c7d01b50e0d17dc79c8",
    "0x3c44cdddb6a900fa2b585dd299e03d12fa4293bc", "0x90f79bf6eb2c4f870365e785982e1f101e93b906",
    "0x15d34aaf54267db7d7c367839aaf71a00a2c6a65", "0x9965507d1a55bcc2695c58ba16fb37d819b0a4dc",
    "0x976ea74026e726554db657fa54763abd0c3a0aa9", "0x14dc79964da2c08b23698b3d3cc7ca32193d9955",
    "0x23618e81e3f5cdf7f54c3d65f7fbc0abf5b21e8f", "0xa0ee7a142d267c1f36714e4a8f75612f20a79720",
]
OWNER, HOUSE, REPORTER, KEEPER, LP, B1, B2, B3, B4, TRADER = ANVIL
WI_UNIT = 10**18

SITES = {"NYC": "CLI:NYC:TMAX:v1", "LGA": "CLI:LGA:TMAX:v1", "JFK": "CLI:JFK:TMAX:v1"}
PAIRS = {"LGA": "PAIR:LGA-NYC:TMAX:v1", "JFK": "PAIR:JFK-NYC:TMAX:v1"}

# (address, site, family, strike tenths, cap tenths, dollars per degF E6, strip?)
BUSINESSES = [
    (B1, "LGA", "CAPPED_CALL", 880, 60, 10 * UNIT, True),   # heat-hurt at LGA (ice-cream-shop mirror: pays on heat)
    (B2, "LGA", "CAPPED_PUT", 800, 50, 5 * UNIT, False),    # cool-hurt at LGA
    (B3, "JFK", "CAPPED_CALL", 860, 60, 5 * UNIT, False),   # heat-hurt at JFK
    (B4, "JFK", "CAPPED_PUT", 780, 40, 5 * UNIT, False),    # cool-hurt at JFK
]


def default_world() -> dict:
    return {
        "name": "engine-fixture-nyc-30d",
        "roles": {"owner": OWNER, "house": HOUSE, "quoter": HOUSE, "reporters": [REPORTER], "keeper": KEEPER,
                  "juniorDepositors": [HOUSE], "rfqMakers": [HOUSE]},
        "hedgeableSeries": {"NYC": "KXHIGHNY"},
        "residualIndexFor": {SITES["LGA"]: PAIRS["LGA"], SITES["JFK"]: PAIRS["JFK"]},
        "wiSupply": 1_000_000 * WI_UNIT,
        "wiBalances": {OWNER: 700_000 * WI_UNIT, LP: 300_000 * WI_UNIT},
        "policyDomain": {"chainId": 31337, "verifyingContract": "0x00000000000000000000000000000000000000a2"},
        "oracleDomain": {"chainId": 31337, "verifyingContract": "0x00000000000000000000000000000000000000a1"},
    }


class Scheduler:
    def __init__(self):
        self.items: list[tuple[int, int, int, str, object]] = []

    def at(self, ts: int, prio: int, name: str, fn) -> None:
        self.items.append((ts, prio, len(self.items), name, fn))

    def run(self) -> None:
        for ts, _, _, name, fn in sorted(self.items, key=lambda x: x[:3]):
            fn(ts)


def run_fixture(inputs: dict, *, world: dict | None = None, keep_snapshots: bool = False, seed: int = 20260930,
                poison_after_decision: bool = False) -> dict:
    """Run the fixture timeline. Returns {"ledger", "notes", "days", "world"}."""
    world = world or default_world()
    led = Ledger(world, keep_snapshots=keep_snapshots)
    st = led.state
    days = [date_to_day(d) for d in inputs["days"]]
    first, last = days[0], days[-1]
    cli = {site: {int(k): v for k, v in vals.items()} for site, vals in inputs["cli"].items()}
    vint = {site: {int(k): v for k, v in vals.items()} for site, vals in inputs["vintages"].items()}
    ladders = {int(k): v for k, v in inputs["ladders"].items()}
    outages = {(o["site"], date_to_day(o["day"])) for o in inputs["scenario"]["outages"]}
    revisions = {(r["site"], date_to_day(r["day"])): r["error"] for r in inputs["scenario"]["revisions"]}
    rfq_day = date_to_day(inputs["scenario"]["rfqDay"])
    rng = random.Random(seed)
    notes: list[str] = []
    sch = Scheduler()
    ids: dict[str, str] = {}
    prehistory: dict[str, list] = {}
    counters = {"nonce": 1}
    basis_mk: dict[int, dict[str, str]] = {}
    policy_mk: dict[int, dict[str, str]] = {}
    strip_id = {"B1": 0}

    # ------------------------------------------------------------ genesis
    def genesis(ts: int) -> None:
        for k in sorted(DEFAULT_PARAMS):
            led.emit(ts, "ParamsSet", {"key": k, "value": DEFAULT_PARAMS[k]})
        for k, v in sorted(inputs["scenario"].get("params", {}).items()):
            led.emit(ts, "ParamsSet", {"key": k, "value": v})
        for acct, usd in ((HOUSE, 9_000), (LP, 30_000), (B1, 5_000), (B2, 5_000), (B3, 5_000), (B4, 5_000),
                          (TRADER, 20_000)):
            led.emit(ts, "AccountFunded", {"account": acct, "amount": usd * UNIT})
        for site, name in SITES.items():
            ids[name] = markets.register_index(led, ts, name, kind="CLI", scale=10, station="NYC", metro="NYC",
                                               inputs=[f"CLI{site}"])
        for site, name in PAIRS.items():
            ids[name] = markets.register_index(led, ts, name, kind="PAIR", scale=10, station="NYC", metro="NYC",
                                               inputs=[f"CLI{site}", "CLINYC"])
            prehistory[ids[name]] = [[int(d), v, (int(d) + 2) * DAY_S + 12 * 3600]
                                     for d, v in sorted(inputs["prehistory"][site].items(), key=lambda kv: int(kv[0]))]
        pool.deposit_junior(led, ts, HOUSE, 8_000 * UNIT)
        pool.deposit_senior(led, ts, LP, 20_000 * UNIT)
        staking.stake(led, ts, OWNER, 600_000 * WI_UNIT)
        staking.stake(led, ts, LP, 300_000 * WI_UNIT)
        a, site, fam, k, c, n, strip = BUSINESSES[0]
        lo, hi, is_long = markets.family_market(fam, k, c)
        strip_id["B1"] = policy.open_strip(led, ts, a, ids[SITES[site]], lo, hi, is_long, markets.units_for(n, c),
                                           40 * UNIT, first, last)

    sch.at(at_utc(first - 2, 12), 0, "genesis", genesis)

    # ------------------------------------------------------------ per-day steps
    def create_markets(D: int):
        def f(ts: int) -> None:
            R = P(st, "basisRangeTenths")
            basis_mk[D] = {site: markets.create_market(led, ts, ids[name], D, -R, R, True) for site, name in PAIRS.items()}
            policy_mk[D] = {}
            for a, site, fam, k, c, n, _ in BUSINESSES:
                lo, hi, _ = markets.family_market(fam, k, c)
                policy_mk[D][a] = markets.create_market(led, ts, ids[SITES[site]], D, lo, hi, False)
        return f

    def sell(D: int):
        def f(ts: int) -> None:
            rungs = ladders[D]
            for a, site, fam, k, c, n, strip in BUSINESSES:
                lo, hi, is_long = markets.family_market(fam, k, c)
                units = markets.units_for(n, c)
                mk = policy_mk[D][a]
                comps = pricing.price_policy(st, ts, market=mk, buyer=a, is_long=is_long, units=units, rungs=rungs,
                                             basis_market=basis_mk[D][site], prehistory=prehistory[ids[PAIRS[site]]],
                                             nonce=counters["nonce"], expiry=st["markets"][mk]["saleCutoff"])
                if comps is None:
                    notes.append(f"{D}: no quote for {a[:8]} (ladder not priceable at {ts})")
                    continue
                resid_escrow = auction.escrow_for(is_long, comps["residualTick"], comps["residualQty"], 0) \
                    if comps["residualQty"] else 0
                b = breaches(st, st["markets"][mk]["indexId"], D, units * UNIT + resid_escrow)
                if b:
                    notes.append(f"{D}: quote for {a[:8]} refused, caps {b}")
                    continue
                ident = policy.quote_identity(st, units, comps["stationLeg"], comps["residualLeg"], comps["tail"])
                if ident["premium"] > units * UNIT:
                    notes.append(f"{D}: no quote for {a[:8]}, premium {ident['premium']} above max payout")
                    continue
                counters["nonce"] += 1
                dg = policy.issue_quote(led, ts, comps)
                if strip:
                    pid = policy.buy_strip_day(led, ts, strip_id["B1"], dg)
                    if pid is None:
                        notes.append(f"{D}: strip day skipped, premium {st['quotes'][dg]['premium']} above max")
                else:
                    policy.buy_policy(led, ts, dg)
        return f

    def house_book(D: int):
        return lambda ts: house_mm.book(led, ts, D, list(basis_mk[D].values()), prehistory)

    def trader_orders(D: int, when: list[int]):
        def f(ts: int) -> None:
            for site, mk in basis_mk[D].items():
                m = st["markets"][mk]
                hist = pricing.basis_history(st, m["indexId"], ts, prehistory[m["indexId"]])
                fair = pricing.fair_stats([v for _, v in hist], m["hi"])["s1"] // len(hist) // TICK
                for _ in range(rng.randint(1, 3)):
                    is_bid = rng.random() < 0.5
                    tick = min(99, max(1, fair + rng.randint(-8, 8)))
                    qty = rng.randint(1, 40)
                    side = tick if is_bid else 100 - tick
                    qty = max(qty, -(-P(st, "minOrderEscrowE6") // (side * TICK)))  # public minimum escrow
                    auction.place_order(led, ts, mk, TRADER, is_bid, tick, qty)
        return f

    def rfq_flow(D: int):
        def f(ts: int) -> None:
            mk = basis_mk[D]["JFK"]
            m = st["markets"][mk]
            qty = 25
            rid = rfq.request(led, ts, TRADER, mk, True, qty, ts + 300)
            hist = pricing.basis_history(st, m["indexId"], ts, prehistory[m["indexId"]])
            rt = pricing.residual_ticks(st, pricing.fair_stats([v for _, v in hist], m["hi"]))
            tick = min(99, max(1, rt["schedAsk"]))  # house sells long units to a long taker at its ask
            complement = qty * UNIT - qty * tick * TICK
            pool.fund_house(led, ts + 60, D, complement)
            rfq.deposit_margin(led, ts + 60, HOUSE, complement)
            dg = rfq.respond(led, ts + 60, rid, HOUSE, tick, qty, ts + 900, counters["nonce"])
            counters["nonce"] += 1
            rfq.accept(led, ts + 360, dg, qty)
            rfq.withdraw_margin(led, ts + 360, HOUSE, st["pm"]["margin"].get(HOUSE, 0))
        return f

    def clear_and_bind(D: int):
        def f(ts: int) -> None:
            for mk in basis_mk[D].values():
                auction.clear_market(led, ts, mk)
                auction.claim_all(led, ts, mk)
        return f

    def bind(D: int):
        return lambda ts: house_mm.bind(led, ts, D, list(basis_mk[D].values()))

    def do_hedge(D: int):
        def f(ts: int) -> None:
            rungs = ladders[D]
            if poison_after_decision:
                rungs = _poison(rungs, ts)
            house_mm.hedge_day(led, ts, D, "KXHIGHNY", rungs)
        return f

    def report(D: int):
        def f(ts: int) -> None:
            vals = {}
            for site, name in SITES.items():
                if (site, D) in outages or D not in cli[site]:
                    continue
                vals[name] = (cli[site][D], vint[site][D])
            for site, name in PAIRS.items():
                if SITES[site] in vals and SITES["NYC"] in vals:
                    vals[name] = (cli[site][D] - cli["NYC"][D], _pair_vintage(vint[site][D], vint["NYC"][D]))
            for name, (v, vh) in vals.items():
                site = name.split(":")[1].split("-")[0]
                err = revisions.get((site, D), 0)
                oracle.post_report(led, ts, ids[name], D, v + err, vintage_hash=vh)
        return f

    def correct(D: int):
        def f(ts: int) -> None:
            for (site, d), err in revisions.items():
                if d != D:
                    continue
                for name in (SITES[site], PAIRS.get(site)):
                    if name is None:
                        continue
                    ob = st["obs"].get(f"{ids[name]}:{D}")
                    if ob is None:
                        continue
                    oracle.post_report(led, ts, ids[name], D, ob["value"] - err, revision=ob["revision"] + 1,
                                       as_of=ob["asOf"], vintage_hash=ob["vintage0"])
        return f

    def settle_hedge(D: int):
        return lambda ts: house_mm.settle_hedge(led, ts, D, "KXHIGHNY", ladders[D])

    def finalize_and_settle(D: int):
        def f(ts: int) -> None:
            for name, iid in ids.items():
                ob = st["obs"].get(f"{iid}:{D}")
                if ob is not None and ob["status"] == "posted":
                    oracle.finalize(led, ts, iid, D)
            _settle_day(D, ts)
        return f

    def void_and_refund(D: int):
        def f(ts: int) -> None:
            for name, iid in ids.items():
                if f"{iid}:{D}" not in st["obs"] and oracle.windows(st, iid, D)["voidAt"] <= ts:
                    oracle.void_day(led, ts, iid, D)
            _settle_day(D, ts)
        return f

    def _settle_day(D: int, ts: int) -> None:
        for pid, pol in house_mm.day_policies(st, D):
            m = st["markets"][pol["market"]]
            ob = st["obs"].get(f"{m['indexId']}:{D}")
            if ob is None:
                continue
            if ob["status"] == "final" and pol["status"] == "Bound":
                policy.settle_policy(led, ts, pid)
            elif ob["status"] == "void" and pol["status"] in ("Bought", "Bound"):
                policy.void_policy(led, ts, pid)
        for mk in basis_mk.get(D, {}).values():
            m = st["markets"][mk]
            ob = st["obs"].get(f"{m['indexId']}:{D}")
            if ob is not None and ob["status"] in ("final", "void"):
                policy.settle_positions(led, ts, mk)
        house_mm.ret(led, ts, D)

    def epoch(ts: int) -> None:
        led.emit(ts, "PoolEpoch", {})
        for rid, req in sorted(st["pool"]["withdrawals"].items(), key=lambda kv: int(kv[0])):
            if req["claimed"] or ts < req["claimableAt"]:
                continue
            if ts >= req["claimableAt"] + P(st, "withdrawClaimWindow"):
                pool.lapse_withdraw(led, ts, int(rid))  # shares back to the LP; nothing leaves the pool
                notes.append(f"withdraw {rid} lapsed")
                continue
            try:
                pool.claim_withdraw(led, ts, int(rid))
            except Revert as e:
                notes.append(f"withdraw {rid} deferred: {e.name}")
        for rid, r in sorted(st["wi"]["unstakes"].items(), key=lambda kv: int(kv[0])):
            if not r["claimed"] and ts >= r["claimableAt"]:
                staking.claim_unstake(led, ts, int(rid))
        active = sorted({int(d) for d in st["pool"]["openPolicies"]} | {int(d) for d in st["pool"]["deployedByDay"]})
        for d in active:
            try:
                pool.close_day(led, ts, d)
            except Revert:
                pass

    for D in days:
        sch.at(at_utc(D - 1, 14), 10, "markets", create_markets(D))
        sch.at(at_utc(D - 1, 20), 20, "sell", sell(D))
        sch.at(at_utc(D - 1, 20, 30), 30, "book", house_book(D))
        for hh, mm in ((21, 0), (23, 30), (26, 10), (26, 40)):  # 26:40 = D 02:40Z (public only; house cut 02:30Z)
            sch.at(at_utc(D - 1, hh, mm), 35, "trader", trader_orders(D, []))
        if D == rfq_day:
            sch.at(at_utc(D - 1, 21, 30), 36, "rfq", rfq_flow(D))
        sch.at(at_utc(D, 3), 40, "clear", clear_and_bind(D))
        sch.at(at_utc(D, 3, 5), 41, "bind", bind(D))
        close_ts = max(r["close_ts"] for r in ladders[D])
        sch.at(close_ts - DEFAULT_PARAMS["hedgeLeadS"], 50, "hedge", do_hedge(D))
        sch.at(at_utc(D + 1, 12), 60, "report", report(D))
        sch.at(at_utc(D + 1, 15), 61, "correct", correct(D))
        settle_ts = max(r["settle_ts"] for r in ladders[D])
        sch.at(settle_ts, 65, "hedge-settle", settle_hedge(D))
        sch.at(at_utc(D + 2, 12), 70, "finalize", finalize_and_settle(D))
        if any(d == D for _, d in outages):
            sch.at(at_utc(D + 5, 12), 70, "void", void_and_refund(D))
    for d in range(first - 1, last + 7):
        sch.at(at_utc(d, 12, 30), 80, "epoch", epoch)
    sch.at(at_utc(first + 4, 13), 85, "lp-withdraw",
           lambda ts: pool.request_withdraw(led, ts, LP, "senior", st["pool"]["seniorShares"][LP] // 10))
    sch.at(at_utc(first + 6, 13), 85, "unstake",
           lambda ts: staking.request_unstake(led, ts, LP, st["wi"]["shares"][LP] // 2))
    sch.run()
    return {"ledger": led, "notes": notes, "days": days, "world": world, "ids": ids, "prehistory": prehistory}


def _pair_vintage(a: str, b: str) -> str:
    from .units import sha256_hex

    return "0x" + sha256_hex(bytes.fromhex(a[2:]) + bytes.fromhex(b[2:]))


def _poison(rungs: list[dict], decision_ts: int) -> list[dict]:
    """Copy of the ladder with absurd candles/books stamped after the decision time (look-ahead probe)."""
    out = []
    for r in rungs:
        r2 = dict(r)
        r2["candles"] = list(r["candles"]) + [[decision_ts + 1, 1, 0], [decision_ts + 60, 99, 98]]
        r2["books"] = list(r.get("books", [])) + [[decision_ts + 1, {"orderbook_fp": {"no_dollars": [["0.99", "99999.00"]]}}]]
        out.append(r2)
    return out
