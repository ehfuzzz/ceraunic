"""SPEC section 12 invariants, asserted inside the reducer after every event.

`check(st, etype, payload, pre)` raises InvariantError on the first failure and returns the names it
checked (the run manifest counts them). `pre` is a light copy of the pool ledgers taken before the
event (for I7). I13 (point-in-time) and I16 (log hygiene) are enforced where the data enters: the
quote / hedge handlers and log.check_link.
"""
from __future__ import annotations

from . import margin
from .pool import c1_ok, c2_ok, capital
from .state import InvariantError, P, is_house, pos_key
from .units import UNIT

MARKET_EVENTS = ("AuctionCleared", "OrderClaimed", "RfqAccepted", "PositionSettled", "PositionRefunded")
I7_EVENTS = ("PolicySettled", "PolicyVoided", "HouseReturned", "HouseWrittenOff")


def _fail(name: str, msg: str) -> None:
    raise InvariantError(f"{name}: {msg}")


def conservation(st: dict) -> tuple[int, int]:
    held = sum(st["bal"].values())
    held += st["pm"]["escrow"] + sum(st["pm"]["margin"].values()) + st["pool"]["cash"]
    for m in st["markets"].values():
        held += m["escrow"] + m["collateral"]
    return held, st["funded"]


def _market_of(st: dict, etype: str, p: dict) -> str | None:
    if etype == "OrderClaimed":
        return st["orders"][str(p["orderId"])]["market"]
    return p.get("market")


def check_market(st: dict, mid: str) -> None:
    m = st["markets"][mid]
    if m["collateral"] != m["collateralIn"] - m["paidOut"] or m["collateral"] < 0:
        _fail("I5", f"collateral ledger broken on {mid}")
    c = m["cleared"]
    orders = [st["orders"][str(i)] for i in m["orderIds"]]
    if c is not None:
        claimed_cost = 0
        unclaimed_escrow = 0
        for o in orders:
            if o["claimed"]:
                claimed_cost += o["fill"] * (c["pStar"] if o["isBid"] else 100 - c["pStar"]) * 10_000
            else:
                unclaimed_escrow += o["escrow"]
        if m["escrow"] != unclaimed_escrow + claimed_cost - c["qStar"] * UNIT:
            _fail("I2", f"auction escrow does not reconcile on {mid}")
        if m["unclaimed"] == 0:
            bids = sum(o["fill"] for o in orders if o["isBid"])
            offs = sum(o["fill"] for o in orders if not o["isBid"])
            if not (bids == offs == c["qStar"]) or claimed_cost != c["qStar"] * UNIT or m["escrow"] != 0:
                _fail("I2", f"fills or cash do not balance on {mid}")
            for o in orders:  # I3: no fill through a limit
                if o["fill"] and ((o["isBid"] and o["tick"] < c["pStar"]) or (not o["isBid"] and o["tick"] > c["pStar"])):
                    _fail("I3", f"fill through limit on {mid}")
            ub = any(o["isBid"] and o["tick"] >= c["pStar"] and o["fill"] < o["qty"] for o in orders)
            uo = any(not o["isBid"] and o["tick"] <= c["pStar"] and o["fill"] < o["qty"] for o in orders)
            if c["qStar"] and ub and uo:
                _fail("I3", f"crossed leftovers on {mid}")
    if m["unclaimed"] == 0:
        paid = lng = sht = 0
        for t in m["traders"]:
            ps = st["pos"][pos_key(mid, t)]
            paid += ps["paid"]
            lng += ps["long"]
            sht += ps["short"]
        if not (paid == m["collateralIn"] == lng * UNIT == sht * UNIT):
            _fail("I5", f"collateral != paid != UNIT x long/short on {mid}")


def check(st: dict, etype: str, p: dict, pre: dict) -> tuple[str, ...]:
    done = ["I1", "I6", "house"]
    held, funded = conservation(st)
    if held != funded:
        _fail("I1", f"held {held} != funded {funded} after {etype}")
    pool = st["pool"]
    if pool["cash"] != pool["senior"] + pool["junior"] - pool["deployed"]:
        _fail("I6", f"pool cash {pool['cash']} != senior + junior - deployed after {etype}")
    if pool["senior"] < 0 or pool["junior"] < 0 or pool["reserved"] < 0 or pool["deployed"] < 0:
        _fail("I6", "negative ledger")
    if sum(pool["deployedByDay"].values()) != pool["deployed"]:
        _fail("I6", "deployedByDay does not sum to deployed")
    house = st["world"]["roles"]["house"]
    led = st["house"]["ledger"]
    if st["bal"].get(house, 0) != st["house"]["free"] + sum(led.values()) or any(v < 0 for v in led.values()):
        _fail("house", "house wallet != free + day ledgers, or a day ledger went negative")

    if etype in I7_EVENTS:
        done.append("I7")
        if pool["senior"] < pre["senior"] and pool["junior"] != 0:
            _fail("I7", f"senior fell while junior > 0 after {etype}")

    if etype in ("PolicyBought", "HouseFunded"):
        done.append("I8")
        cap = capital(pool)
        if not c1_ok(st, pool["reserved"], pool["deployed"], cap) or not c2_ok(st, pool["junior"], cap):
            _fail("I8", f"C1/C2 broken after {etype}")
    elif etype == "SeniorDeposited":
        done.append("I8")
        if not c2_ok(st, pool["junior"], capital(pool)):
            _fail("I8", "C2 broken after senior deposit")
    elif etype in ("WithdrawCancelled", "WithdrawLapsed"):
        done.append("I15")
        if any(pool[k] != pre[k] for k in ("senior", "junior", "cash", "seniorSupply", "juniorSupply")):
            _fail("I15", f"{etype} moved pool money or share supply")  # shares go back; nothing leaves the pool
    elif etype == "WithdrawClaimed":
        done += ["I8", "I15"]
        req = pool["withdrawals"][str(p["requestId"])]
        cap = capital(pool)
        if not c1_ok(st, pool["reserved"], pool["deployed"], cap):
            _fail("I8", "C1 broken after withdrawal")
        if req["tranche"] == "junior" and not c2_ok(st, pool["junior"], cap):
            _fail("I8", "C2 broken after junior withdrawal")

    if etype == "PolicyBought" or (etype == "OrderPlaced" and is_house(st, p["trader"])) or \
            (etype == "RfqAccepted" and is_house(st, p["maker"])):
        done.append("I9")
        m = st["markets"][p["market"]]
        b = margin.breaches(st, m["indexId"], m["day"])
        if b:
            _fail("I9", f"{b} breached after {etype}")

    if etype in MARKET_EVENTS:
        done += ["I2", "I3", "I5"]
        check_market(st, _market_of(st, etype, p))

    if etype in ("PolicyBound", "PolicySettled", "PolicyVoided"):
        done.append("I10")
        pol = st["policies"][str(p["policyId"])]
        if pol["boundUnits"] > pol["units"]:
            _fail("I10", "boundUnits > units")
        if etype == "PolicyBound":
            kept = pol["premium"] - p["refund"]
            if p["keptFee"] + p["toPool"] != kept or p["seniorPremium"] + p["juniorPremium"] != p["toPool"]:
                _fail("I10", "bind split does not add up")
        if etype == "PolicySettled" and p["payout"] > pol["boundUnits"] * UNIT:
            _fail("I10", "payout above boundUnits x UNIT")

    if etype in ("PolicySettled", "PositionSettled"):
        done.append("I11")
        mk = st["markets"][st["policies"][str(p["policyId"])]["market"]] if etype == "PolicySettled" \
            else st["markets"][p["market"]]
        ob = st["obs"].get(f"{mk['indexId']}:{mk['day']}")
        if ob is None or ob["status"] != "final" or ob["value"] != p["x"]:
            _fail("I11", "settled on something other than the finalized value")

    if etype in ("WIStaked", "WIUnstakeClaimed", "WIHaircut", "DayClosed"):
        done.append("I12")
        wi = st["wi"]
        if sum(wi["bal"].values()) + wi["totalStaked"] != wi["supply"] - wi["burned"]:
            _fail("I12", "WI supply identity broken")
        if etype == "WIHaircut" and p["bps"] > P(st, "haircutCapBps"):
            _fail("I12", "haircut above cap")
    return tuple(done)
