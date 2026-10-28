"""The pure event reducer: state = fold(apply, events), invariants after every event, hash-chained log,
UTC day-boundary snapshots, and replay (docs/SPEC.md sections 12-13).

No wall clock, network or unseeded randomness here. Commands (the modules' `led`-taking functions)
compute an event from the current state and call `Ledger.emit`; replay feeds the same lines back
through `Ledger.apply_line`, which recomputes every derived field and rejects a line that disagrees.
"""
from __future__ import annotations

from . import auction, hedge, invariants, markets, oracle, policy, pool, rfq, staking
from .log import check_link, make_line
from .state import Revert, add, copy_state, is_house, new_state, state_hash
from .units import ts_to_day


def _params_set(st: dict, ts: int, p: dict) -> None:
    st["params"][p["key"]] = p["value"]


def _account_funded(st: dict, ts: int, p: dict) -> None:
    if p["amount"] <= 0:
        raise Revert("ZeroAmount")
    add(st["bal"], p["account"], p["amount"])
    st["funded"] += p["amount"]
    if is_house(st, p["account"]):
        st["house"]["free"] += p["amount"]


HANDLERS = {
    "ParamsSet": _params_set,
    "AccountFunded": _account_funded,
    "IndexRegistered": markets.h_index_registered,
    "MarketCreated": markets.h_market_created,
    "SeniorDeposited": pool.h_senior_deposited,
    "JuniorDeposited": pool.h_junior_deposited,
    "WithdrawRequested": pool.h_withdraw_requested,
    "WithdrawClaimed": pool.h_withdraw_claimed,
    "WithdrawCancelled": pool.h_withdraw_cancelled,
    "WithdrawLapsed": pool.h_withdraw_lapsed,
    "HouseFunded": pool.h_house_funded,
    "HouseReturned": pool.h_house_returned,
    "HouseWrittenOff": pool.h_house_written_off,
    "DayClosed": pool.h_day_closed,
    "PoolEpoch": pool.h_pool_epoch,
    "WIStaked": staking.h_wi_staked,
    "WIUnstakeRequested": staking.h_wi_unstake_requested,
    "WIUnstakeClaimed": staking.h_wi_unstake_claimed,
    "WIHaircut": staking.h_wi_haircut,
    "QuoteIssued": policy.h_quote_issued,
    "PolicyBought": policy.h_policy_bought,
    "PolicyBound": policy.h_policy_bound,
    "PolicySettled": policy.h_policy_settled,
    "PolicyVoided": policy.h_policy_voided,
    "StripOpened": policy.h_strip_opened,
    "StripClosed": policy.h_strip_closed,
    "OrderPlaced": auction.h_order_placed,
    "AuctionCleared": auction.h_auction_cleared,
    "OrderClaimed": auction.h_order_claimed,
    "MarginDeposited": rfq.h_margin_deposited,
    "MarginWithdrawn": rfq.h_margin_withdrawn,
    "RfqRequested": rfq.h_rfq_requested,
    "RfqQuoted": rfq.h_rfq_quoted,
    "RfqAccepted": rfq.h_rfq_accepted,
    "PositionSettled": policy.h_position_settled,
    "PositionRefunded": policy.h_position_refunded,
    "ReportPosted": oracle.h_report_posted,
    "IndexFinalized": oracle.h_index_finalized,
    "IndexVoided": oracle.h_index_voided,
    "HedgeDecision": hedge.h_hedge_decision,
    "HedgeFilled": hedge.h_hedge_filled,
    "HedgeSettled": hedge.h_hedge_settled,
}


class Ledger:
    """Engine state + its log. `emit` for live commands, `apply_line` for replay."""

    def __init__(self, world: dict | None = None, *, state: dict | None = None, last_line: dict | None = None,
                 keep_snapshots: bool = False):
        if state is None and world is None:
            raise ValueError("need a world or a snapshot state")
        self.state = copy_state(state) if state is not None else new_state(world)
        self.lines: list[dict] = []
        self.last_line = last_line
        self.keep_snapshots = keep_snapshots
        self.snapshots: list[dict] = []
        self.checks: dict[str, int] = {}
        self.counts: dict[str, int] = {}

    # -- core -----------------------------------------------------------------------------------
    def _maybe_snapshot(self, ts: int, seq: int) -> None:
        if self.last_line is None:
            return
        if ts_to_day(ts) > ts_to_day(self.last_line["ts"]):
            snap = {"boundaryDay": ts_to_day(ts), "seq": seq, "hash": state_hash(self.state),
                    "lastLine": self.last_line}
            if self.keep_snapshots:
                snap["state"] = copy_state(self.state)
            self.snapshots.append(snap)

    def _apply(self, line: dict) -> None:
        st = self.state
        etype, p, ts = line["type"], line["payload"], line["ts"]
        pre = {k: st["pool"][k] for k in ("senior", "junior", "cash", "seniorSupply", "juniorSupply")}
        HANDLERS[etype](st, ts, p)
        for name in invariants.check(st, etype, p, pre):
            self.checks[name] = self.checks.get(name, 0) + 1
        st["stats"]["events"] += 1
        st["stats"]["lastTs"] = ts
        self.counts[etype] = self.counts.get(etype, 0) + 1

    def emit(self, ts: int, etype: str, payload: dict) -> dict:
        line = make_line(self.last_line, ts, etype, payload)
        self._maybe_snapshot(ts, line["seq"])
        self._apply(line)  # a Revert leaves state untouched (handlers validate before they mutate)
        self.lines.append(line)
        self.last_line = line
        return line

    def apply_line(self, line: dict) -> None:
        check_link(self.last_line, line)
        self._maybe_snapshot(line["ts"], line["seq"])
        self._apply(line)
        self.lines.append(line)
        self.last_line = line

    # -- views ----------------------------------------------------------------------------------
    def hash(self) -> str:
        return state_hash(self.state)

    @property
    def world(self) -> dict:
        return self.state["world"]


def replay(world: dict, lines: list[dict], *, keep_snapshots: bool = False) -> Ledger:
    led = Ledger(world, keep_snapshots=keep_snapshots)
    for line in lines:
        led.apply_line(line)
    return led


def replay_from_snapshot(snapshot: dict, lines: list[dict]) -> Ledger:
    """Start from a stored snapshot (state + the line before it) and apply the tail from snapshot['seq']."""
    led = Ledger(state=snapshot["state"], last_line=snapshot["lastLine"])
    for line in lines:
        if line["seq"] >= snapshot["seq"]:
            led.apply_line(line)
    return led
