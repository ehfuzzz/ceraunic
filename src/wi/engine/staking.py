"""WI staking: stake, cooldown unstake, pro-rata burn haircut on a closed day's junior loss
(docs/SPEC.md section 8.7). WI is fixed supply; nothing mints it after genesis (world file).
"""
from __future__ import annotations

from .pool import OFFSET
from .state import P, Revert, add, dkey
from .units import BPS, mul_div


def stake_shares(wi: dict, amount: int) -> int:
    return mul_div(amount, wi["totalShares"] + OFFSET, wi["totalStaked"] + 1)


def unstake_amount(wi: dict, shares: int) -> int:
    return mul_div(shares, wi["totalStaked"] + 1, wi["totalShares"] + OFFSET)


def h_wi_staked(st: dict, ts: int, p: dict) -> None:
    wi = st["wi"]
    if p["amount"] == 0:
        raise Revert("ZeroAmount")
    sh = stake_shares(wi, p["amount"])
    if sh == 0:
        raise Revert("ZeroAmount")
    if sh != p["shares"]:
        raise Revert("BadShares")
    if wi["bal"].get(p["owner"], 0) < p["amount"]:
        raise Revert("InsufficientWI")
    wi["bal"][p["owner"]] -= p["amount"]
    wi["totalStaked"] += p["amount"]
    wi["totalShares"] += sh
    add(wi["shares"], p["owner"], sh)


def h_wi_unstake_requested(st: dict, ts: int, p: dict) -> None:
    wi = st["wi"]
    if p["shares"] == 0:
        raise Revert("ZeroAmount")
    if p["requestId"] != wi["nextUnstakeId"]:
        raise Revert("BadRequestId")
    if p["claimableAt"] != ts + P(st, "unstakeCooldown"):
        raise Revert("BadClaimableAt")
    if wi["shares"].get(p["owner"], 0) < p["shares"]:
        raise Revert("InsufficientShares")
    wi["shares"][p["owner"]] -= p["shares"]  # in cooldown: still inside totalShares, still cuttable
    wi["nextUnstakeId"] += 1
    wi["unstakes"][str(p["requestId"])] = {"owner": p["owner"], "shares": p["shares"], "requestedAt": ts,
                                          "claimableAt": p["claimableAt"], "claimed": False}


def check_unstake(st: dict, ts: int, rid: int) -> int:
    wi = st["wi"]
    r = wi["unstakes"].get(str(rid))
    if r is None or ts < r["claimableAt"]:
        raise Revert("NotClaimable")
    if r["claimed"]:
        raise Revert("AlreadyClaimed")
    return unstake_amount(wi, r["shares"])


def h_wi_unstake_claimed(st: dict, ts: int, p: dict) -> None:
    amt = check_unstake(st, ts, p["requestId"])
    wi = st["wi"]
    r = wi["unstakes"][str(p["requestId"])]
    if amt != p["amount"] or r["owner"] != p["owner"]:
        raise Revert("BadUnstake")
    r["claimed"] = True
    r["amount"] = amt
    wi["totalShares"] -= r["shares"]
    wi["totalStaked"] -= amt
    add(wi["bal"], r["owner"], amt)


def burn_for(wi: dict, bps: int) -> int:
    return mul_div(wi["totalStaked"], bps, BPS)


def h_wi_haircut(st: dict, ts: int, p: dict) -> None:
    wi = st["wi"]
    hd = wi["haircutDays"].get(dkey(p["day"]))
    if hd is None or hd["bps"] != p["bps"]:
        raise Revert("NoHaircutDue")
    if hd["applied"]:
        raise Revert("HaircutDone")
    if p["bps"] > P(st, "haircutCapBps"):
        raise Revert("AboveCap")
    burned = burn_for(wi, p["bps"])
    if burned != p["burned"]:
        raise Revert("BadBurn")
    hd["applied"] = True
    wi["totalStaked"] -= burned
    wi["burned"] += burned


# ---------------------------------------------------------------- commands
def stake(led, ts: int, owner: str, amount: int) -> int:
    sh = stake_shares(led.state["wi"], amount)
    led.emit(ts, "WIStaked", {"owner": owner, "amount": amount, "shares": sh})
    return sh


def request_unstake(led, ts: int, owner: str, shares: int) -> int:
    st = led.state
    rid = st["wi"]["nextUnstakeId"]
    led.emit(ts, "WIUnstakeRequested", {"requestId": rid, "owner": owner, "shares": shares,
                                        "claimableAt": ts + P(st, "unstakeCooldown")})
    return rid


def claim_unstake(led, ts: int, rid: int) -> int:
    st = led.state
    amt = check_unstake(st, ts, rid)
    led.emit(ts, "WIUnstakeClaimed", {"requestId": rid, "owner": st["wi"]["unstakes"][str(rid)]["owner"],
                                      "amount": amt})
    return amt


def apply_haircut(led, ts: int, day: int, bps: int) -> int:
    burned = burn_for(led.state["wi"], bps)
    led.emit(ts, "WIHaircut", {"day": day, "bps": bps, "burned": burned})
    return burned
