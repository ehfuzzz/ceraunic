"""Pool vault: senior / junior ledgers, shares, waterfall, caps C1-C2, house deployment, epochs,
day close (docs/SPEC.md section 8).

Revert names and check order follow contracts/src/PoolVault.sol (Phase 8, read 2026-09-30) so the
waterfall parity fixture can carry an expected revert name. Every op validates before it mutates.
"""
from __future__ import annotations

from .state import P, Revert, add, dkey, is_house
from .units import BPS, DAY_S, mul_div

OFFSET = 10**6  # OZ ERC-4626 virtual share offset


# ---------------------------------------------------------------- views
def capital(pool: dict) -> int:
    return pool["senior"] + pool["junior"]


def cash_expected(pool: dict) -> int:
    return pool["senior"] + pool["junior"] - pool["deployed"]


def c1_ok(st: dict, reserved: int, deployed: int, cap: int) -> bool:
    return (reserved + deployed) * BPS <= P(st, "capBps") * cap


def c2_ok(st: dict, junior: int, cap: int) -> bool:
    return junior * BPS >= P(st, "jMinBps") * cap


def shares_for(assets: int, supply: int, tranche_assets: int) -> int:
    return mul_div(assets, supply + OFFSET, tranche_assets + 1)


def assets_for(shares: int, supply: int, tranche_assets: int) -> int:
    return mul_div(shares, tranche_assets + 1, supply + OFFSET)


# ---------------------------------------------------------------- internal waterfall steps
def _loss(pool: dict, day: int, l: int) -> tuple[int, int]:
    """Junior absorbs first; senior only once junior is 0. dayPnl carries the junior part."""
    j = min(l, pool["junior"])
    pool["junior"] -= j
    pool["senior"] -= l - j
    add(pool["dayPnl"], dkey(day), -j)
    return j, l - j


def check_reserve(st: dict, day: int, amount: int) -> None:
    pool = st["pool"]
    if pool["closed"].get(dkey(day)):
        raise Revert("DayAlreadyClosed")
    if pool["junior"] == 0:
        raise Revert("NoJunior")
    cap = capital(pool)
    if not c1_ok(st, pool["reserved"] + amount, pool["deployed"], cap):
        raise Revert("ExposureCap")
    if not c2_ok(st, pool["junior"], cap):
        raise Revert("JuniorMinimum")


def reserve(st: dict, day: int, amount: int) -> None:
    check_reserve(st, day, amount)
    pool = st["pool"]
    pool["reserved"] += amount
    add(pool["openPolicies"], dkey(day), 1)


def release(st: dict, day: int, amount: int) -> None:
    st["pool"]["reserved"] -= amount


def credit_premium(st: dict, day: int, amount: int) -> tuple[int, int]:
    """Cash already moved in by the caller (pool cash += amount done here)."""
    pool = st["pool"]
    s = mul_div(amount, P(st, "seniorPremiumBps"), BPS)
    j = amount - s
    pool["senior"] += s
    pool["junior"] += j
    pool["cash"] += amount
    add(pool["dayPnl"], dkey(day), j)
    return s, j


def check_absorb(st: dict, day: int, released: int, loss: int) -> None:
    if loss > released:
        raise Revert("LossExceedsRelease")
    pool = st["pool"]
    if pool["cash"] < loss:
        raise AssertionError("pool cash below a reserved payout (C1 should make this impossible)")
    if pool["openPolicies"].get(dkey(day), 0) < 1 or pool["reserved"] < released:
        raise AssertionError("absorbLoss without a matching reserve")


def absorb_loss(st: dict, day: int, released: int, loss: int, to: str) -> tuple[int, int]:
    check_absorb(st, day, released, loss)
    pool = st["pool"]
    pool["reserved"] -= released
    add(pool["openPolicies"], dkey(day), -1)
    j, s = _loss(pool, day, loss)
    pool["cash"] -= loss
    add(st["bal"], to, loss)
    if is_house(st, to):
        st["house"]["free"] += loss
    return j, s


# ---------------------------------------------------------------- handlers: LPs
def h_junior_deposited(st: dict, ts: int, p: dict) -> None:
    pool = st["pool"]
    if p["owner"] not in st["world"]["roles"]["juniorDepositors"]:
        raise Revert("OnlyJuniorDepositor")
    if p["amount"] == 0:
        raise Revert("ZeroAmount")
    shares = shares_for(p["amount"], pool["juniorSupply"], pool["junior"])
    if shares == 0:
        raise Revert("ZeroAmount")
    if shares != p["shares"]:
        raise Revert("BadShares")
    if st["bal"].get(p["owner"], 0) < p["amount"]:
        raise Revert("InsufficientBalance")
    st["bal"][p["owner"]] -= p["amount"]
    if is_house(st, p["owner"]):
        st["house"]["free"] -= p["amount"]
    pool["cash"] += p["amount"]
    pool["junior"] += p["amount"]
    pool["juniorSupply"] += shares
    add(pool["juniorShares"], p["owner"], shares)


def h_senior_deposited(st: dict, ts: int, p: dict) -> None:
    pool = st["pool"]
    if p["amount"] == 0:
        raise Revert("ZeroAmount")
    if pool["junior"] == 0 or pool["junior"] < P(st, "minJuniorForSenior"):
        raise Revert("SeniorClosed")
    shares = shares_for(p["amount"], pool["seniorSupply"], pool["senior"])
    if shares == 0:
        raise Revert("ZeroAmount")
    if shares != p["shares"]:
        raise Revert("BadShares")
    if not c2_ok(st, pool["junior"], capital(pool) + p["amount"]):
        raise Revert("JuniorMinimum")
    if st["bal"].get(p["owner"], 0) < p["amount"]:
        raise Revert("InsufficientBalance")
    st["bal"][p["owner"]] -= p["amount"]
    pool["cash"] += p["amount"]
    pool["senior"] += p["amount"]
    pool["seniorSupply"] += shares
    add(pool["seniorShares"], p["owner"], shares)


def h_withdraw_requested(st: dict, ts: int, p: dict) -> None:
    pool = st["pool"]
    if p["tranche"] not in ("senior", "junior"):
        raise Revert("BadTranche")
    if p["shares"] == 0:
        raise Revert("ZeroAmount")
    if p["requestId"] != pool["nextWithdrawId"]:
        raise Revert("BadRequestId")
    if p["claimableAt"] != ts + P(st, "withdrawDelay"):
        raise Revert("BadClaimableAt")
    book = pool["seniorShares" if p["tranche"] == "senior" else "juniorShares"]
    if book.get(p["owner"], 0) < p["shares"]:
        raise Revert("InsufficientShares")
    book[p["owner"]] -= p["shares"]  # escrowed; still inside the tranche supply until claim
    pool["nextWithdrawId"] += 1
    pool["withdrawals"][str(p["requestId"])] = {"owner": p["owner"], "tranche": p["tranche"], "shares": p["shares"],
                                               "requestedAt": ts, "claimableAt": p["claimableAt"], "claimed": False}


def withdraw_amount(st: dict, req: dict) -> int:
    pool = st["pool"]
    if req["tranche"] == "senior":
        return assets_for(req["shares"], pool["seniorSupply"], pool["senior"])
    return assets_for(req["shares"], pool["juniorSupply"], pool["junior"])


def check_withdraw(st: dict, ts: int, rid: int) -> int:
    pool = st["pool"]
    req = pool["withdrawals"].get(str(rid))
    if req is None or ts < req["claimableAt"]:
        raise Revert("NotClaimable")
    if req["claimed"]:
        raise Revert("AlreadyClaimed")
    if ts >= req["claimableAt"] + P(st, "withdrawClaimWindow"):
        raise Revert("ClaimWindowClosed")  # the request lapses instead (h_withdraw_lapsed)
    amt = withdraw_amount(st, req)
    if amt > pool["cash"]:
        raise Revert("InsufficientCash")
    senior, junior = pool["senior"], pool["junior"]
    if req["tranche"] == "senior":
        senior -= amt
    else:
        junior -= amt
        if not c2_ok(st, junior, senior + junior):
            raise Revert("JuniorMinimum")
    if not c1_ok(st, pool["reserved"], pool["deployed"], senior + junior):
        raise Revert("ExposureCap")
    return amt


def h_withdraw_claimed(st: dict, ts: int, p: dict) -> None:
    amt = check_withdraw(st, ts, p["requestId"])
    pool = st["pool"]
    req = pool["withdrawals"][str(p["requestId"])]
    if amt != p["amount"] or req["owner"] != p["owner"]:
        raise Revert("BadWithdraw")
    req["claimed"] = True
    req["status"] = "claimed"
    req["amount"] = amt
    if req["tranche"] == "senior":
        pool["senior"] -= amt
        pool["seniorSupply"] -= req["shares"]
    else:
        pool["junior"] -= amt
        pool["juniorSupply"] -= req["shares"]
    pool["cash"] -= amt
    add(st["bal"], req["owner"], amt)
    if is_house(st, req["owner"]):
        st["house"]["free"] += amt  # the house's own junior money, not attributed to any day


def _return_shares(st: dict, req: dict) -> None:
    """Escrowed shares never left the tranche supply, so handing them back moves no assets."""
    book = st["pool"]["seniorShares" if req["tranche"] == "senior" else "juniorShares"]
    add(book, req["owner"], req["shares"])


def check_cancel(st: dict, ts: int, rid: int, owner: str) -> dict:
    req = st["pool"]["withdrawals"].get(str(rid))
    if req is None or req["owner"] != owner:
        raise Revert("NotRequestOwner")
    if req["claimed"]:
        raise Revert("AlreadyClaimed")
    if ts >= req["claimableAt"]:
        raise Revert("NotCancellable")
    return req


def h_withdraw_cancelled(st: dict, ts: int, p: dict) -> None:
    """Owner, before maturity: the request closes and its shares go back (PoolVault.cancelWithdraw)."""
    req = check_cancel(st, ts, p["requestId"], p["owner"])
    if p["shares"] != req["shares"]:
        raise Revert("BadCancel")
    req["claimed"] = True
    req["status"] = "cancelled"
    _return_shares(st, req)


def check_lapse(st: dict, ts: int, rid: int) -> dict:
    req = st["pool"]["withdrawals"].get(str(rid))
    if req is None:
        raise Revert("NotClaimable")
    if req["claimed"]:
        raise Revert("AlreadyClaimed")
    if ts < req["claimableAt"] + P(st, "withdrawClaimWindow"):
        raise Revert("NotLapsed")
    return req


def h_withdraw_lapsed(st: dict, ts: int, p: dict) -> None:
    """Anyone, once the claim window is over: the shares go back to the owner; the money never leaves the
    tranche or the pool (PoolVault.lapseWithdraw)."""
    req = check_lapse(st, ts, p["requestId"])
    if p["owner"] != req["owner"] or p["shares"] != req["shares"]:
        raise Revert("BadLapse")
    req["claimed"] = True
    req["status"] = "lapsed"
    _return_shares(st, req)


# ---------------------------------------------------------------- handlers: house deployment
def h_house_funded(st: dict, ts: int, p: dict) -> None:
    pool = st["pool"]
    d = dkey(p["day"])
    if pool["houseDone"].get(d) or pool["closed"].get(d):
        raise Revert("HouseDayDone")
    today = ts // DAY_S
    if p["day"] + 1 < today or p["day"] > today + 2:
        raise Revert("BadDay")  # PoolVault 08-HARDEN #5: only days in [today - 1, today + 2]
    if p["amount"] == 0:
        raise Revert("ZeroAmount")
    cap = capital(pool)
    if not c1_ok(st, pool["reserved"], pool["deployed"] + p["amount"], cap):
        raise Revert("ExposureCap")
    if not c2_ok(st, pool["junior"], cap):
        raise Revert("JuniorMinimum")
    if pool["cash"] < p["amount"]:
        raise AssertionError("fundHouse beyond cash (C1 should make this impossible)")
    house = st["world"]["roles"]["house"]
    add(pool["deployedByDay"], d, p["amount"])
    pool["deployed"] += p["amount"]
    pool["cash"] -= p["amount"]
    add(st["bal"], house, p["amount"])
    add(st["house"]["ledger"], d, p["amount"])


def h_house_returned(st: dict, ts: int, p: dict) -> None:
    pool = st["pool"]
    d = dkey(p["day"])
    if pool["houseDone"].get(d):
        raise Revert("HouseDayDone")
    dep = pool["deployedByDay"].get(d, 0)
    if p["deployed"] != dep or p["pnl"] != p["amount"] - dep:
        raise Revert("BadReturn")
    house = st["world"]["roles"]["house"]
    # engine rule (trust T3 made explicit): the house returns everything the day left it with, so the
    # house's own P&L is zero by construction
    if p["amount"] != st["house"]["ledger"].get(d, 0):
        raise Revert("HouseMustReturnAll", f"day {d}")
    if st["bal"].get(house, 0) < p["amount"]:
        raise Revert("InsufficientBalance")
    pool["houseDone"][d] = True
    st["bal"][house] -= p["amount"]
    st["house"]["ledger"][d] = 0
    pool["cash"] += p["amount"]
    pool["deployedByDay"][d] = 0
    pool["deployed"] -= dep
    if p["pnl"] >= 0:
        pool["junior"] += p["pnl"]
        add(pool["dayPnl"], d, p["pnl"])
    else:
        _loss(pool, p["day"], -p["pnl"])


def h_house_written_off(st: dict, ts: int, p: dict) -> None:
    pool = st["pool"]
    d = dkey(p["day"])
    if ts < p["day"] * DAY_S + P(st, "houseReturnWindow"):
        raise Revert("TooEarly")
    dep = pool["deployedByDay"].get(d, 0)
    if dep == 0:
        raise Revert("NothingDeployed")
    if p["deployed"] != dep:
        raise Revert("BadWriteOff")
    pool["houseDone"][d] = True
    pool["deployedByDay"][d] = 0
    pool["deployed"] -= dep
    _loss(pool, p["day"], dep)
    # the money stays with the house wallet; it is no longer attributed to the day
    st["house"]["free"] += st["house"]["ledger"].get(d, 0)
    st["house"]["ledger"][d] = 0


# ---------------------------------------------------------------- day close + haircut (SPEC 8.7)
def haircut_bps(st: dict, day: int) -> int:
    pool = st["pool"]
    pnl = pool["dayPnl"].get(dkey(day), 0)
    if pnl >= 0:
        return 0
    l = -pnl
    return min(mul_div(l, BPS, pool["junior"] + l), P(st, "haircutCapBps"))


def check_close(st: dict, ts: int, day: int) -> None:
    pool = st["pool"]
    d = dkey(day)
    if pool["closed"].get(d):
        raise Revert("DayAlreadyClosed")
    if ts < (day + 1) * DAY_S:
        raise Revert("TooEarly")
    if pool["openPolicies"].get(d, 0) != 0 or pool["deployedByDay"].get(d, 0) != 0:
        raise Revert("DayOpen")


def h_day_closed(st: dict, ts: int, p: dict) -> None:
    check_close(st, ts, p["day"])
    pool = st["pool"]
    d = dkey(p["day"])
    if p["juniorPnl"] != pool["dayPnl"].get(d, 0) or p["haircutBps"] != haircut_bps(st, p["day"]):
        raise Revert("BadClose")
    pool["closed"][d] = True
    if p["haircutBps"]:
        st["wi"]["haircutDays"][d] = {"bps": p["haircutBps"], "applied": False}


def h_pool_epoch(st: dict, ts: int, p: dict) -> None:
    st["pool"]["lastEpoch"] = ts


# ---------------------------------------------------------------- commands
def deposit_junior(led, ts: int, owner: str, amount: int) -> int:
    pool = led.state["pool"]
    sh = shares_for(amount, pool["juniorSupply"], pool["junior"])
    led.emit(ts, "JuniorDeposited", {"owner": owner, "amount": amount, "shares": sh})
    return sh


def deposit_senior(led, ts: int, owner: str, amount: int) -> int:
    pool = led.state["pool"]
    sh = shares_for(amount, pool["seniorSupply"], pool["senior"])
    led.emit(ts, "SeniorDeposited", {"owner": owner, "amount": amount, "shares": sh})
    return sh


def request_withdraw(led, ts: int, owner: str, tranche: str, shares: int) -> int:
    st = led.state
    rid = st["pool"]["nextWithdrawId"]
    led.emit(ts, "WithdrawRequested", {"requestId": rid, "owner": owner, "tranche": tranche, "shares": shares,
                                       "claimableAt": ts + P(st, "withdrawDelay")})
    return rid


def claim_withdraw(led, ts: int, rid: int) -> int:
    st = led.state
    amt = check_withdraw(st, ts, rid)
    led.emit(ts, "WithdrawClaimed", {"requestId": rid, "owner": st["pool"]["withdrawals"][str(rid)]["owner"],
                                     "amount": amt})
    return amt


def cancel_withdraw(led, ts: int, owner: str, rid: int) -> None:
    req = check_cancel(led.state, ts, rid, owner)
    led.emit(ts, "WithdrawCancelled", {"requestId": rid, "owner": owner, "shares": req["shares"]})


def lapse_withdraw(led, ts: int, rid: int) -> None:
    req = check_lapse(led.state, ts, rid)
    led.emit(ts, "WithdrawLapsed", {"requestId": rid, "owner": req["owner"], "shares": req["shares"]})


def fund_house(led, ts: int, day: int, amount: int) -> None:
    if amount > 0:
        led.emit(ts, "HouseFunded", {"day": day, "amount": amount})


def return_from_house(led, ts: int, day: int) -> int:
    st = led.state
    d = dkey(day)
    amt = st["house"]["ledger"].get(d, 0)
    dep = st["pool"]["deployedByDay"].get(d, 0)
    led.emit(ts, "HouseReturned", {"day": day, "amount": amt, "deployed": dep, "pnl": amt - dep})
    return amt - dep


def close_day(led, ts: int, day: int) -> int:
    st = led.state
    check_close(st, ts, day)
    bps = haircut_bps(st, day)
    led.emit(ts, "DayClosed", {"day": day, "juniorPnl": st["pool"]["dayPnl"].get(dkey(day), 0), "haircutBps": bps})
    if bps:
        from .staking import apply_haircut

        apply_haircut(led, ts, day, bps)
    return bps
