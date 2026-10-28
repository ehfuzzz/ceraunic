"""Engine event -> contract call(s) on anvil, with an event-level parity check.

Every engine log line a write produced is replayed on the Phase 8 contracts at the line's own timestamp
(evm_setNextBlockTimestamp; anvil accepts equal timestamps, so chain time == engine time). The chain's own
event log from each receipt is then compared field by field with the engine payload (ids, shares, fills,
premiums, payouts, haircuts). A chain revert or any field difference raises Diverged: the engine and the
contracts disagree, which Phase 8 parity says must not happen, so it is a ledger bug and the write is undone
(evm_revert) together with the engine write.

Engine-only events: ParamsSet (checked once at boot), QuoteIssued (the quote is signed off chain; its digest is
checked by the PolicyBought log), PoolEpoch, HedgeDecision. Kalshi is off chain: HedgeFilled moves the cost
from the house wallet to a sink address, HedgeSettled mints the payout to the house (MockUSDC stands in for the
Kalshi withdrawal). WIHaircut is emitted by the chain inside closeDay and checked against the DayClosed receipt.
"""
from __future__ import annotations

import time

from eth_utils import keccak

from wi.engine.eip712 import QUOTE_FIELDS, REPORT_FIELDS

from .. import catalog as cat
from .chain import MAX_UINT, Contract, Rpc, RpcError, decode_log, revert_name

KALSHI_SINK = "0x00000000000000000000000000000000004b414c"  # "KAL": where hedge premiums go (off-chain venue)
TRANCHE = {"senior": 0, "junior": 1}
TRANCHE_NAME = {0: "senior", 1: "junior"}
TREASURY = cat.KEEPER  # contracts/Makefile ANVIL_ENV sets TREASURY = anvil #3 (the engine's "@treasury")


class Diverged(Exception):
    """The chain refused or disagreed with an engine event."""


def _typed(fields: tuple, name: str, domain: dict, msg: dict) -> dict:
    def val(t, v):
        if t.startswith("uint") or t.startswith("int"):
            return str(v)
        return v

    return {
        "types": {"EIP712Domain": [{"name": "name", "type": "string"}, {"name": "version", "type": "string"},
                                   {"name": "chainId", "type": "uint256"},
                                   {"name": "verifyingContract", "type": "address"}],
                  name: [{"name": n, "type": t} for n, t in fields]},
        "primaryType": name, "domain": domain,
        "message": {n: val(t, msg[n]) for n, t in fields},
    }


class Mirror:
    def __init__(self, rpc: Rpc, c: dict[str, Contract], chain_id: int):
        self.rpc, self.c, self.chain_id = rpc, c, chain_id
        self.haircut_logs: dict[int, dict] = {}
        self.txs = 0

    # ------------------------------------------------------------ transport
    def send(self, ts: int, sender: str, cname: str, fn: str, *args) -> list[tuple[str, str, dict]]:
        data = self.c[cname].encode(fn, *args)
        try:
            self.rpc.call("evm_setNextBlockTimestamp", hex(ts))
        except RpcError as e:
            raise Diverged(f"chain clock is ahead of the engine event time {ts}: {e}") from None
        try:
            h = self.rpc.call("eth_sendTransaction", {"from": sender, "to": self.c[cname].address, "data": data})
        except RpcError as e:
            raise Diverged(f"{cname}.{fn} from {sender} at {ts} reverted: {revert_name(e.data) if e.data else e}") from None
        rc = self.receipt(h)
        if rc is None or int(rc["status"], 16) != 1:
            raise Diverged(f"{cname}.{fn} at {ts}: tx {h} failed")
        self.txs += 1
        return [d for d in (decode_log(lg) for lg in rc["logs"]) if d is not None]

    def receipt(self, h: str, wait_s: float = 10.0) -> dict | None:
        """Automine answers eth_sendTransaction before the block is sealed; poll until the receipt exists."""
        deadline = time.monotonic() + wait_s
        delay = 0.0005
        while True:
            rc = self.rpc.call("eth_getTransactionReceipt", h)
            if rc is not None or time.monotonic() > deadline:
                return rc
            time.sleep(delay)
            delay = min(delay * 2, 0.05)

    def sign_typed(self, signer: str, typed: dict, digest: str) -> str:
        from eth_account import Account

        sig = self.rpc.call("eth_signTypedData_v4", signer, typed)
        got = Account._recover_hash(bytes.fromhex(digest[2:]), signature=bytes.fromhex(sig[2:]))
        if got.lower() != signer.lower():
            raise Diverged(f"EIP-712 digest mismatch: anvil signed a different digest than the engine's {digest}")
        return sig

    @staticmethod
    def expect(logs, event: str, want: dict, what: str) -> dict:
        rows = [f for _, name, f in logs if name == event]
        for f in rows:
            if all(f.get(k) == v for k, v in want.items()):
                return f
        got = rows[0] if rows else None
        diff = {k: (v, got.get(k)) for k, v in want.items() if got is not None and got.get(k) != v}
        raise Diverged(f"{what}: chain {event} " + (f"differs (engine, chain): {diff}" if got else "missing"))

    # ------------------------------------------------------------ world materialisation (no engine event)
    def materialise(self, ts: int) -> None:
        """The world file's WI balances and standing allowances (the engine has no allowance concept)."""
        for u in cat.DEMO_USERS:
            self.send(ts, cat.OWNER, "WIToken", "transfer", u, cat.WI_DEMO_USER)
        for a in cat.ANVIL:
            for spender in ("PoolVault", "PolicyManager", "BatchAuction"):
                self.send(ts, a, "MockUSDC", "approve", self.c[spender].address, MAX_UINT)
            self.send(ts, a, "WIToken", "approve", self.c["WIStaking"].address, MAX_UINT)

    # ------------------------------------------------------------ lines
    def apply(self, st: dict, lines: list[dict]) -> None:
        for line in lines:
            h = getattr(self, "_" + line["type"], None)
            if h is None:
                raise Diverged(f"engine event {line['type']} has no chain mirror (not used by the API)")
            try:
                h(st, line["ts"], line["payload"])
            except Diverged as e:
                raise Diverged(f"seq {line['seq']} {line['type']}: {e}") from None

    # engine-only
    def _ParamsSet(self, st, ts, p): pass
    def _QuoteIssued(self, st, ts, p): pass
    def _PoolEpoch(self, st, ts, p): pass
    def _HedgeDecision(self, st, ts, p): pass

    def _AccountFunded(self, st, ts, p):
        self.expect(self.send(ts, cat.OWNER, "MockUSDC", "mint", p["account"], p["amount"]), "Transfer",
                    {"to": p["account"], "value": p["amount"]}, "faucet")

    def _IndexRegistered(self, st, ts, p):
        oa = self.c["OracleAdapter"]
        cfg = {"fetchLag": p["fetchLag"], "disputeWindow": p["disputeWindow"], "voidGrace": p["voidGrace"], "active": True}
        reg = oa.decode("registered", 1, self.rpc.call("eth_call", {"to": oa.address, "data": oa.encode("registered", p["indexId"])}, "latest"))
        if reg:  # Configure.s.sol registered it with the same CLI windows; prove it
            have = oa.decode("indexConfig", 1, self.rpc.call("eth_call", {"to": oa.address, "data": oa.encode("indexConfig", p["indexId"])}, "latest"))
            if have != cfg:
                raise Diverged(f"{p['name']} registered on chain with {have}, engine has {cfg}")
            return
        self.expect(self.send(ts, cat.OWNER, "OracleAdapter", "registerIndex", p["indexId"], cfg), "IndexRegistered",
                    {"indexId": p["indexId"], "fetchLag": p["fetchLag"]}, p["name"])

    def _MarketCreated(self, st, ts, p):
        self.expect(self.send(ts, cat.HOUSE, "PolicyManager", "createMarket", p["indexId"], p["day"], p["lo"], p["hi"],
                              p["auctioned"]), "MarketCreated", {"marketId": p["marketId"], "day": p["day"]}, "market")

    # pool
    def _JuniorDeposited(self, st, ts, p):
        self.expect(self.send(ts, p["owner"], "PoolVault", "depositJunior", p["amount"]), "Deposited",
                    {"owner": p["owner"], "tranche": 1, "assets": p["amount"], "shares": p["shares"]}, "junior deposit")

    def _SeniorDeposited(self, st, ts, p):
        self.expect(self.send(ts, p["owner"], "PoolVault", "depositSenior", p["amount"]), "Deposited",
                    {"owner": p["owner"], "tranche": 0, "assets": p["amount"], "shares": p["shares"]}, "senior deposit")

    def _WithdrawRequested(self, st, ts, p):
        self.expect(self.send(ts, p["owner"], "PoolVault", "requestWithdraw", TRANCHE[p["tranche"]], p["shares"]),
                    "WithdrawRequested", {"requestId": p["requestId"], "owner": p["owner"], "shares": p["shares"],
                                          "claimableAt": p["claimableAt"]}, "withdraw request")

    def _WithdrawClaimed(self, st, ts, p):
        self.expect(self.send(ts, cat.KEEPER, "PoolVault", "claimWithdraw", p["requestId"]), "Withdrawn",
                    {"requestId": p["requestId"], "owner": p["owner"], "assets": p["amount"]}, "withdraw claim")

    def _WithdrawCancelled(self, st, ts, p):
        self.expect(self.send(ts, p["owner"], "PoolVault", "cancelWithdraw", p["requestId"]), "WithdrawCancelled",
                    {"requestId": p["requestId"], "owner": p["owner"], "shares": p["shares"]}, "withdraw cancel")

    def _WithdrawLapsed(self, st, ts, p):  # anyone may lapse; the keeper does (no USDC moves)
        self.expect(self.send(ts, cat.KEEPER, "PoolVault", "lapseWithdraw", p["requestId"]), "WithdrawLapsed",
                    {"requestId": p["requestId"], "owner": p["owner"], "shares": p["shares"]}, "withdraw lapse")

    def _HouseFunded(self, st, ts, p):
        self.expect(self.send(ts, cat.HOUSE, "PoolVault", "fundHouse", p["day"], p["amount"]), "HouseFunded",
                    {"day": p["day"], "amount": p["amount"]}, "fund house")

    def _HouseReturned(self, st, ts, p):
        self.expect(self.send(ts, cat.HOUSE, "PoolVault", "returnFromHouse", p["day"], p["amount"]), "HouseReturned",
                    {"day": p["day"], "amount": p["amount"], "deployed": p["deployed"], "pnl": p["pnl"]}, "house return")

    def _HouseWrittenOff(self, st, ts, p):
        self.expect(self.send(ts, cat.KEEPER, "PoolVault", "writeOffHouse", p["day"]), "HouseWrittenOff",
                    {"day": p["day"], "deployed": p["deployed"]}, "write-off")

    def _DayClosed(self, st, ts, p):
        logs = self.send(ts, cat.KEEPER, "PoolVault", "closeDay", p["day"])
        self.expect(logs, "DayClosed", {"day": p["day"], "juniorPnl": p["juniorPnl"], "haircutBps": p["haircutBps"]},
                    "close day")
        for _, name, f in logs:
            if name == "Haircut":
                self.haircut_logs[f["day"]] = f

    # staking
    def _WIStaked(self, st, ts, p):
        self.expect(self.send(ts, p["owner"], "WIStaking", "stake", p["amount"]), "Staked",
                    {"owner": p["owner"], "amount": p["amount"], "shares": p["shares"]}, "stake")

    def _WIUnstakeRequested(self, st, ts, p):
        self.expect(self.send(ts, p["owner"], "WIStaking", "requestUnstake", p["shares"]), "UnstakeRequested",
                    {"requestId": p["requestId"], "owner": p["owner"], "shares": p["shares"],
                     "claimableAt": p["claimableAt"]}, "unstake request")

    def _WIUnstakeClaimed(self, st, ts, p):
        self.expect(self.send(ts, p["owner"], "WIStaking", "claimUnstake", p["requestId"]), "UnstakeClaimed",
                    {"requestId": p["requestId"], "owner": p["owner"], "amount": p["amount"]}, "unstake claim")

    def _WIHaircut(self, st, ts, p):
        f = self.haircut_logs.pop(p["day"], None)
        if f is None or (f["bps"], f["burned"]) != (p["bps"], p["burned"]):
            raise Diverged(f"haircut day {p['day']}: engine bps={p['bps']} burned={p['burned']}, chain {f}")

    # policies
    def quote_sig(self, st: dict, q: dict, digest: str) -> str:
        dom = {"name": "wi-policy", "version": "1", "chainId": self.chain_id,
               "verifyingContract": self.c["PolicyManager"].address}
        return self.sign_typed(st["world"]["roles"]["quoter"], _typed(QUOTE_FIELDS, "Quote", dom, q), digest)

    def _PolicyBought(self, st, ts, p):
        q = st["quotes"][p["digest"]]
        qs = {k: q[k] for k, _ in QUOTE_FIELDS}
        sig = self.quote_sig(st, qs, p["digest"])
        self.expect(self.send(ts, p["buyer"], "PolicyManager", "buyPolicy", qs, sig), "PolicyBought",
                    {"policyId": p["policyId"], "market": p["market"], "buyer": p["buyer"], "isLong": p["isLong"],
                     "units": p["units"], "premium": p["premium"], "fee": p["fee"], "quoteDigest": p["digest"]}, "buy")

    def _PolicyBound(self, st, ts, p):
        logs = self.send(ts, cat.HOUSE, "PolicyManager", "bind", p["policyId"], p["residualOrderId"])
        self.expect(logs, "PolicyBound", {"policyId": p["policyId"], "residualOrderId": p["residualOrderId"],
                                          "boundUnits": p["boundUnits"], "refund": p["refund"], "keptFee": p["keptFee"],
                                          "toPool": p["toPool"]}, "bind")
        if p["toPool"]:
            self.expect(logs, "PremiumCredited", {"amount": p["toPool"], "senior": p["seniorPremium"],
                                                  "junior": p["juniorPremium"]}, "premium split")

    def _PolicySettled(self, st, ts, p):
        self.expect(self.send(ts, cat.KEEPER, "PolicyManager", "settlePolicy", p["policyId"]), "PolicySettled",
                    {"policyId": p["policyId"], "x": p["x"], "payout": p["payout"]}, "settle")

    def _PolicyVoided(self, st, ts, p):
        self.expect(self.send(ts, cat.KEEPER, "PolicyManager", "settlePolicy", p["policyId"]), "PolicyVoided",
                    {"policyId": p["policyId"], "refund": p["refund"]}, "void")

    # auctions
    def _OrderPlaced(self, st, ts, p):
        self.expect(self.send(ts, p["trader"], "BatchAuction", "placeOrder", p["market"], p["isBid"], p["tick"], p["qty"]),
                    "OrderPlaced", {"orderId": p["orderId"], "market": p["market"], "trader": p["trader"],
                                    "isBid": p["isBid"], "tick": p["tick"], "qty": p["qty"], "ahead": p["ahead"],
                                    "escrow": p["escrow"]}, "order")

    def _AuctionCleared(self, st, ts, p):
        self.expect(self.send(ts, cat.KEEPER, "BatchAuction", "clear", p["market"]), "AuctionCleared",
                    {k: p[k] for k in ("market", "pStar", "qStar", "tb", "to", "mb", "mo")}, "clear")

    def _OrderClaimed(self, st, ts, p):
        self.expect(self.send(ts, cat.KEEPER, "BatchAuction", "claim", p["orderId"]), "OrderClaimed",
                    {k: p[k] for k in ("orderId", "fill", "cost", "fee", "refund")}, "claim")

    def _PositionSettled(self, st, ts, p):
        self.expect(self.send(ts, p["trader"], "PolicyManager", "claimPosition", p["market"]), "PositionSettled",
                    {k: p[k] for k in ("market", "trader", "longQty", "shortQty", "x", "payout")}, "position")

    def _PositionRefunded(self, st, ts, p):
        self.expect(self.send(ts, p["trader"], "PolicyManager", "claimPosition", p["market"]), "PositionRefunded",
                    {k: p[k] for k in ("market", "trader", "refund")}, "position refund")

    # oracle
    def _ReportPosted(self, st, ts, p):
        from wi.engine.eip712 import report_digest

        r = {k: p[k] for k, _ in REPORT_FIELDS}
        oa = self.c["OracleAdapter"].address
        dom = {"name": "wi-oracle", "version": "1", "chainId": self.chain_id, "verifyingContract": oa}
        sig = self.sign_typed(p["signer"], _typed(REPORT_FIELDS, "Report", dom, r),
                              report_digest(r, self.chain_id, oa))
        self.expect(self.send(ts, cat.KEEPER, "OracleAdapter", "post", p["indexId"], p["day"], p["value"], p["revision"],
                              p["asOf"], p["vintageHash"], sig), "Posted",
                    {k: p[k] for k in ("indexId", "day", "value", "revision", "asOf", "signer", "vintageHash")}, "post")

    def _IndexFinalized(self, st, ts, p):
        self.expect(self.send(ts, cat.KEEPER, "OracleAdapter", "finalize", p["indexId"], p["day"]), "Finalized",
                    {"indexId": p["indexId"], "day": p["day"], "value": p["value"]}, "finalize")

    def _IndexVoided(self, st, ts, p):
        self.expect(self.send(ts, cat.KEEPER, "OracleAdapter", "voidDay", p["indexId"], p["day"]), "Voided",
                    {"indexId": p["indexId"], "day": p["day"]}, "void day")

    # Kalshi (off chain)
    def _HedgeFilled(self, st, ts, p):
        if p["costE6"]:
            self.send(ts, cat.HOUSE, "MockUSDC", "transfer", KALSHI_SINK, p["costE6"])

    def _HedgeSettled(self, st, ts, p):
        if p["payoutE6"]:
            self.send(ts, cat.OWNER, "MockUSDC", "mint", cat.HOUSE, p["payoutE6"])


def selector(sig: str) -> str:
    return "0x" + keccak(text=sig)[:4].hex()
