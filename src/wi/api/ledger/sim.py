"""SimLedger: one engine reducer per world (Pattern 4), stored in Upstash (or memory locally).

Each write: lock the world -> restore the snapshot -> run engine commands (Ledger.emit applies each event
and asserts the SPEC 12 invariants) -> save snapshot + append the new log lines -> unlock. A Revert or any
other error saves nothing, so a multi-event write (a 7-day policy is 7 PolicyBought events) is atomic.
Reads load the snapshot without the lock. The pinned `demo` world is created on first touch; visitor
worlds (`w_<hex>`) come from POST /sim/worlds and expire after 7 days.
"""
from __future__ import annotations

import hashlib
import secrets
from contextlib import contextmanager
from typing import Iterator

from wi.engine import auction, house_mm, markets, oracle, pool, staking
from wi.engine.eip712 import index_id
from wi.engine.state import P, Revert
from wi.engine.units import DAY_S, TICK, date_to_day, day_to_iso, ts_to_iso

from .. import catalog as cat
from .. import clock, quoting, views
from .. import elasticity as el
from .. import snapshot_data as sd
from ..envelope import ApiError
from ..models import (
    AdvanceResult, Auction, AuctionContract, AuctionSummary, Business, ChainInfo, Clock, ClearingResult, Coef,
    Config, Elasticity, EventSummary, Health, HouseMm, Limits, OracleRow, Prior, Quote,
    Recommendation, ResidualLeg, Rung, Schedule, Settlement, Site, Station, StationLeg, TickResult, TxConfirm,
    WorldInfo,
)
from ..store import DEMO, BaseStore, decode, encode
from ..world import SimWorld, genesis
from .base import revert_error

MAX_SALES_ROWS = 5000
MAX_BODY_BYTES = 4_500_000
IDEM_KEEP = 300

_TEMPLATE: dict = {}


def template_blob() -> tuple[str, str]:
    """(encoded blob, encoded lines) of a fresh demo-5-cities world at START_TS, computed once per process."""
    if "blob" not in _TEMPLATE:
        w = genesis("template")
        clock.advance(w, cat.START_TS)
        _TEMPLATE["blob"] = encode(w.to_blob())
        _TEMPLATE["lines"] = encode(w.led.lines)
    return _TEMPLATE["blob"], _TEMPLATE["lines"]


def bad(detail: str) -> ApiError:
    return ApiError(422, "VALIDATION", "Validation failed", detail)


class SimLedger:
    mode = "sim"

    def __init__(self, store: BaseStore, env):
        self.store = store
        self.env = env

    # ------------------------------------------------------------ world plumbing
    def _fresh(self, wid: str) -> tuple[dict, list]:
        enc_blob, enc_lines = template_blob()
        blob = decode(enc_blob)
        blob["meta"]["worldId"] = wid
        return blob, decode(enc_lines)

    @contextmanager
    def write(self, wid: str) -> Iterator[SimWorld]:
        with self.store.write(wid) as box:
            lines0: list = []
            if box["blob"] is None:
                if wid != DEMO:
                    box["save"] = False
                    raise ApiError(404, "NOT_FOUND", "Unknown world", f"world {wid!r} does not exist; POST /sim/worlds")
                box["blob"], lines0 = self._fresh(wid)
            w = SimWorld.from_blob(box["blob"])
            try:
                yield w
            except BaseException:
                box["save"] = False
                raise
            box["blob"] = w.to_blob()
            box["lines"] = lines0 + w.led.lines

    def read(self, wid: str) -> SimWorld:
        blob = self.store.load(wid)
        if blob is None:
            if wid != DEMO:
                raise ApiError(404, "NOT_FOUND", "Unknown world", f"world {wid!r} does not exist; POST /sim/worlds")
            with self.write(DEMO):
                pass
            blob = self.store.load(wid)
        return _ReadWorld(blob)

    def idempotent(self, w: SimWorld, key: str | None, scope: str, body_json: str, compute):
        if not key:
            return compute()
        fp = hashlib.sha256((scope + body_json).encode()).hexdigest()
        hit = w.meta["idem"].get(key)
        if hit:
            if hit[0] != fp:
                raise bad("Idempotency-Key was already used with a different request")
            return hit[1]
        out = compute()
        dumped = out.model_dump(by_alias=True, mode="json") if hasattr(out, "model_dump") else out
        w.meta["idem"][key] = [fp, dumped]
        w.meta["idemOrder"].append(key)
        while len(w.meta["idemOrder"]) > IDEM_KEEP:
            w.meta["idem"].pop(w.meta["idemOrder"].pop(0), None)
        return dumped

    @staticmethod
    def engine(fn, *a, **k):
        try:
            return fn(*a, **k)
        except Revert as e:
            raise revert_error(e) from None

    def execution(self, cls, result):
        return cls(mode="sim", status="done", result=result, txs=[])

    # ------------------------------------------------------------ meta
    def health(self) -> Health:
        w = self.read(DEMO)
        return Health(ok=True, mode="sim", chain_id=None, engine_version=cat.ENGINE_VERSION, spec_hash=cat.spec_hash(),
                      sim_time=ts_to_iso(w.now))

    def config(self) -> Config:
        return base_config("sim", ChainInfo(id=0, name="simulated", rpc_url=""), {})

    # ------------------------------------------------------------ sim worlds
    def new_world(self) -> WorldInfo:
        wid = "w_" + secrets.token_hex(6)
        blob, lines = self._fresh(wid)
        with self.store.write(wid) as box:
            box["blob"], box["lines"] = blob, lines
        return WorldInfo(world_id=wid, sim_time=ts_to_iso(blob["meta"]["simTs"]))

    def reset_world(self, wid: str) -> WorldInfo:
        if wid != DEMO and not self.store.exists(wid):
            raise ApiError(404, "NOT_FOUND", "Unknown world", wid)
        blob, lines = self._fresh(wid)
        self.store.delete(wid)
        with self.store.write(wid) as box:
            box["blob"], box["lines"] = blob, lines
        return WorldInfo(world_id=wid, sim_time=ts_to_iso(blob["meta"]["simTs"]))

    def advance(self, wid: str, days: int) -> AdvanceResult:
        with self.write(wid) as w:
            t1 = clock.rest_after(w.now, days)
            ev = clock.advance(w, t1)
            return AdvanceResult(sim_time=ts_to_iso(w.now), events=[EventSummary(**e) for e in ev])

    def clock(self, wid: str) -> Clock:
        w = self.read(wid)
        return Clock(sim_time=ts_to_iso(w.now), next_events=[EventSummary(**e) for e in clock.upcoming(w)][:12])

    # ------------------------------------------------------------ accounts
    def balances(self, wid: str, addr: str):
        w = self.read(wid)
        return views.balances(w.st, addr)

    def faucet(self, wid: str, addr: str, amount: int, cls):
        with self.write(wid) as w:
            self.engine(w.led.emit, w.now, "AccountFunded", {"account": addr, "amount": amount})
            return self.execution(cls, views.balances(w.st, addr))

    # ------------------------------------------------------------ businesses
    def create_business(self, wid: str, body) -> Business:
        site, km = cat.nearest_site(body.lat, body.lon)
        if km > cat.MAX_SITE_KM:
            raise bad(f"location is {km:.0f} km from the nearest station with data (max {cat.MAX_SITE_KM:.0f} km)")
        with self.write(wid) as w:
            bid = w.next_id("biz")
            rec = {"businessId": bid, "name": body.name, "owner": body.owner.lower(), "lat": body.lat, "lon": body.lon,
                   "zip": body.zip, "naics": body.naics, "locationSite": site, "distanceKm": round(km, 2)}
            w.meta["businesses"][bid] = rec
            return business_view(rec)

    def business(self, wid: str, bid: str) -> Business:
        return business_view(self._biz(self.read(wid), bid))

    @staticmethod
    def _biz(w, bid: str) -> dict:
        rec = w.meta["businesses"].get(bid)
        if rec is None:
            raise ApiError(404, "NOT_FOUND", "Unknown business", bid)
        return rec

    def upload_sales(self, wid: str, bid: str, body) -> dict:
        with self.write(wid) as w:
            self._biz(w, bid)
            book = w.meta["sales"].setdefault(bid, {})
            for row in body.rows:
                book[row.date] = row.gross_sales_cents
            days = sorted(book)
            warnings = []
            if len(days) < 30:
                warnings.append("fewer than 30 days of history: the estimate leans on the sector prior")
            if any(v < 0 for v in book.values()):
                warnings.append("negative sales rows present (refunds?)")
            later = sum(1 for d in days if d >= day_to_iso(w.sim_day))
            if later:
                warnings.append(f"{later} days are dated on or after the simulated day {day_to_iso(w.sim_day)}; "
                                "the estimator uses only days before it")
            span = (date_to_day(days[-1]) - date_to_day(days[0]) + 1) if days else 0
            return {"rows": len(days), "first_date": days[0] if days else None, "last_date": days[-1] if days else None,
                    "gaps": span - len(days), "warnings": warnings}

    def elasticity(self, wid: str, bid: str) -> Elasticity:
        w = self.read(wid)
        rec = self._biz(w, bid)
        e = el.estimate(rec, w.meta["sales"].get(bid, {}), w.sim_day)
        return elasticity_view(e)

    def recommendation(self, wid: str, bid: str, peril: str | None = None) -> Recommendation:
        w = self.read(wid)
        rec = self._biz(w, bid)
        e = el.estimate(rec, w.meta["sales"].get(bid, {}), w.sim_day)
        r = el.recommend_rain(rec, e, w.sim_day) if peril == "rain" else el.recommend(rec, e, w.sim_day)
        try:
            q = quoting.build(w, biz=rec, peril=r["peril"], strike=r["strike_tenths_f"], cap=r["cap_tenths_f"],
                              units=r["units_per_day"], days=[date_to_day(r["start_day"])], path="house-hedge",
                              nonce0=w.meta["nonce"], emit=False)
            per_day = q["premium"]
        except ApiError:
            per_day = 0
        return Recommendation(**r, max_daily_premium_e6=per_day * 5 // 4)

    # ------------------------------------------------------------ quotes + policies
    def quote(self, wid: str, body, days: list[int]) -> Quote:
        with self.write(wid) as w:
            biz = self._biz(w, body.business_id)
            rec = self.engine(quoting.build, w, biz=biz, peril=body.peril, strike=body.strike_tenths_f,
                              cap=body.cap_tenths_f, units=body.units, days=days, path=body.path,
                              nonce0=w.meta["nonce"], emit=True)
            w.meta["nonce"] = rec.get("nonceNext", w.meta["nonce"])
            qid = w.next_id("q")
            rec["quoteId"] = qid
            rec["used"] = False
            w.meta["quotes"][qid] = {k: v for k, v in rec.items() if k not in ("replication",)}
            return quote_view(rec)

    def buy(self, wid: str, body, key: str | None, cls):
        with self.write(wid) as w:
            def go():
                q = w.meta["quotes"].get(body.quote_id)
                if q is None:
                    raise ApiError(404, "NOT_FOUND", "Unknown quote", body.quote_id)
                holder = body.holder.lower()
                if not q["digests"]:
                    raise ApiError(409, "VALIDATION", "Nothing to buy", q.get("note") or "this quote sells nothing")
                if q["used"] or w.now > q["expiry"]:
                    raise ApiError(409, "QUOTE_EXPIRED", "Quote expired or already used", body.quote_id)
                if holder != q["buyer"]:
                    raise bad("holder must be the business owner the quote was issued to")
                have = w.st["bal"].get(holder, 0)
                if have < q["premium"]:
                    raise ApiError(409, "INSUFFICIENT_BALANCE", "Not enough USDC", f"need {q['premium']}, have {have}")
                from wi.engine import policy as pol

                eids = [self.engine(pol.buy_policy, w.led, w.now, dg) for dg in q["digests"]]
                q["used"] = True
                pid = w.next_id("pol")
                rec = {"policyId": pid, "businessId": q["businessId"], "holder": holder, "path": q["path"],
                       "peril": q["peril"], "strike": q["strike"], "cap": q["cap"], "days": q["days"],
                       "units": q["units"], "enginePolicyIds": eids, "premium": q["premium"],
                       "maxPayout": q["maxPayout"], "indexName": q["indexName"], "quoteId": body.quote_id}
                w.meta["policies"][pid] = rec
                return self.execution(cls, views.policy(w.st, rec))
            return self.idempotent(w, key, "policies", body.model_dump_json(), go)

    def policies(self, wid: str, holder: str):
        w = self.read(wid)
        return [views.policy(w.st, r) for r in w.meta["policies"].values() if r["holder"] == holder]

    def policy(self, wid: str, pid: str):
        w = self.read(wid)
        rec = w.meta["policies"].get(pid)
        if rec is None:
            raise ApiError(404, "NOT_FOUND", "Unknown policy", pid)
        return views.policy(w.st, rec)

    # ------------------------------------------------------------ auctions
    def _auction_markets(self, w, day: str | None) -> list[str]:
        days = [date_to_day(day)] if day else [w.sim_day - 1, w.sim_day, w.sim_day + 1]
        out = []
        for d in days:
            for s in cat.PAIR_SITES:
                mk = w.basis_market_id(s, d)
                if mk in w.st["markets"]:
                    out.append(mk)
        return out

    def _market_of(self, w, aid: str) -> str:
        try:
            _, cid, day = aid.split("_", 2)
            site = cat.CONTRACTS[cid]
            mk = w.basis_market_id(site, date_to_day(day))
        except (ValueError, KeyError):
            raise ApiError(404, "NOT_FOUND", "Unknown auction", aid) from None
        if mk not in w.st["markets"]:
            raise ApiError(404, "NOT_FOUND", "Unknown auction", aid)
        return mk

    def _summary(self, w, mk: str) -> AuctionSummary:
        st = w.st
        m = st["markets"][mk]
        cid = views.contract_of_market(st, mk)
        return AuctionSummary(auction_id=views.auction_id(cid, m["day"]), contract_id=cid,
                              station_id=cat.SITES[cat.SITES[cat.CONTRACTS[cid]][5]][0], day=day_to_iso(m["day"]),
                              status=views.auction_status(st, mk, w.now), public_cutoff=ts_to_iso(m["cutoff"]),
                              order_count=len(m["orderIds"]), range_tenths_f=m["hi"])

    def auctions(self, wid: str, day: str | None, status: str | None):
        w = self.read(wid)
        out = [self._summary(w, mk) for mk in self._auction_markets(w, day)]
        return [a for a in out if status is None or a.status == status]

    def auction(self, wid: str, aid: str) -> Auction:
        w = self.read(wid)
        mk = self._market_of(w, aid)
        bids, asks = views.levels(w.st, mk)
        res = views.clearing(w.st, mk)
        return Auction(**self._summary(w, mk).model_dump(), bids=bids, asks=asks,
                       house_quote=views.house_quote(w.st, mk), result=ClearingResult(**res) if res else None)

    def post_order(self, wid: str, aid: str, body, key: str | None, cls):
        with self.write(wid) as w:
            def go():
                mk = self._market_of(w, aid)
                trader = body.trader.lower()
                if trader == cat.HOUSE:
                    raise ApiError(403, "FORBIDDEN", "House address", "the house account places orders only via the house MM")
                oid = self.engine(auction.place_order, w.led, w.now, mk, trader, body.side == "buy",
                                  body.limit_price_e6 // TICK, body.qty)
                return self.execution(cls, views.order(w.st, oid, w.st["orders"][str(oid)]))
            return self.idempotent(w, key, f"orders:{aid}", body.model_dump_json(), go)

    def cancel_order(self, wid: str, aid: str, oid: str, trader: str, cls):
        raise ApiError(409, "NOT_CANCELLABLE", "Orders cannot be cancelled",
                       "v0 auctions have no cancels (SPEC 5: a cancel would corrupt the price-time queue)")

    def clear(self, wid: str, aid: str, admin: bool, cls):
        with self.write(wid) as w:
            mk = self._market_of(w, aid)
            m = w.st["markets"][mk]
            if m["cleared"] is None and w.now < m["cutoff"]:
                if not admin:
                    raise ApiError(409, "AUCTION_OPEN", "Auction still open", f"public cutoff {ts_to_iso(m['cutoff'])}")
                clock.advance(w, m["cutoff"])  # admin: run the world clock to the cutoff (the clock clears)
            if m["cleared"] is None:  # clock did not reach it (e.g. a market outside the calendar)
                self.engine(auction.clear_market, w.led, max(w.now, m["cutoff"]), mk)
                self.engine(auction.claim_all, w.led, max(w.now, m["cutoff"]), mk)
            return self.execution(cls, ClearingResult(**views.clearing(w.st, mk)))

    # ------------------------------------------------------------ pool
    def pool(self, wid: str):
        w = self.read(wid)
        return views.pool_state(w.st, w.meta)

    def deposit(self, wid: str, body, key: str | None, cls):
        with self.write(wid) as w:
            def go():
                owner = body.owner.lower()
                if body.tranche == "junior":
                    sh = self.engine(pool.deposit_junior, w.led, w.now, owner, body.amount_e6)
                else:
                    sh = self.engine(pool.deposit_senior, w.led, w.now, owner, body.amount_e6)
                t = {"ticketId": w.next_id("tkt"), "kind": "deposit", "owner": owner, "tranche": body.tranche,
                     "amount": body.amount_e6, "shares": sh, "epochTs": w.now}
                w.meta["tickets"].append(t)
                return self.execution(cls, views.ticket(w.st, t))
            return self.idempotent(w, key, "pool-dep", body.model_dump_json(), go)

    def withdraw(self, wid: str, body, key: str | None, cls):
        with self.write(wid) as w:
            def go():
                owner = body.owner.lower()
                rid = self.engine(pool.request_withdraw, w.led, w.now, owner, body.tranche, body.shares)
                req = w.st["pool"]["withdrawals"][str(rid)]
                t = {"ticketId": w.next_id("tkt"), "kind": "withdrawal", "owner": owner, "tranche": body.tranche,
                     "shares": body.shares, "requestId": rid, "epochTs": req["claimableAt"]}
                w.meta["tickets"].append(t)
                return self.execution(cls, views.ticket(w.st, t))
            return self.idempotent(w, key, "pool-wd", body.model_dump_json(), go)

    def cancel_withdraw(self, wid: str, rid: int, body, key: str | None, cls):
        """Owner only, before maturity (engine check_cancel): the escrowed shares go back, no USDC moves."""
        with self.write(wid) as w:
            def go():
                owner = body.owner.lower()
                if str(rid) not in w.st["pool"]["withdrawals"]:
                    raise ApiError(404, "NOT_FOUND", "Unknown withdrawal", f"no withdrawal request {rid}")
                self.engine(pool.cancel_withdraw, w.led, w.now, owner, rid)
                t = next((t for t in w.meta["tickets"] if t["kind"] == "withdrawal" and t["requestId"] == rid), None)
                if t is None:  # a request the ticket list does not know (should not happen): show it anyway
                    req = w.st["pool"]["withdrawals"][str(rid)]
                    t = {"ticketId": w.next_id("tkt"), "kind": "withdrawal", "owner": owner, "tranche": req["tranche"],
                         "shares": req["shares"], "requestId": rid, "epochTs": req["claimableAt"]}
                    w.meta["tickets"].append(t)
                return self.execution(cls, views.ticket(w.st, t))
            return self.idempotent(w, key, f"pool-wd-cancel:{rid}", body.model_dump_json(), go)

    # ------------------------------------------------------------ positions
    def positions(self, wid: str, owner: str):
        w = self.read(wid)
        return views.positions(w.st, w.meta, owner)

    def settlements(self, wid: str, owner: str, from_day: str | None, to_day: str | None) -> list[Settlement]:
        w = self.read(wid)
        rows = [s for r in w.meta["policies"].values() if r["holder"] == owner for s in views.policy_rows(w.st, r)[0]]
        rows += views.residual_settlements(w.st, owner)
        rows = [s for s in rows if (not from_day or s.day >= from_day) and (not to_day or s.day <= to_day)]
        return sorted(rows, key=lambda s: (s.day, s.ref_id))

    # ------------------------------------------------------------ admin
    def house_mm(self, wid: str) -> HouseMm:
        w = self.read(wid)
        st = w.st
        return HouseMm(quotes=views.house_quotes(st, w.now), inventory=views.inventory(st), hedges=views.hedges(st),
                       pnl_e6=w.meta.get("housePnl", 0), caps_used=views.caps_used(st))

    def house_tick(self, wid: str) -> TickResult:
        with self.write(wid) as w:
            key = f"{wid}:{ts_to_iso(w.now)}"
            if key in w.meta["ticks"]:
                return TickResult(tick_key=key, quotes_posted=0, hedges_placed=0, events=[])
            before = w.st["nextOrderId"]
            events = []
            for D in (w.sim_day, w.sim_day + 1):
                bms = w.basis_markets(D)
                if bms and w.now < markets.market_times(w.st, D)["houseCutoff"]:
                    self.engine(house_mm.book, w.led, w.now, D, bms, w.prehistory())
                    events.append(EventSummary(ts=ts_to_iso(w.now), kind="house_cutoff",
                                               detail=f"house book for {day_to_iso(D)}"))
            w.meta["ticks"][key] = True
            return TickResult(tick_key=key, quotes_posted=w.st["nextOrderId"] - before, hedges_placed=0, events=events)

    def oracle(self, wid: str) -> list[OracleRow]:
        w = self.read(wid)
        return views.oracle_rows(w.st, w.now)

    def oracle_report(self, wid: str, index: str, day: str, cls):
        name = normalize_index(index)
        with self.write(wid) as w:
            D = date_to_day(day)
            iid = index_id(name)
            if f"{iid}:{D}" in w.st["obs"]:
                raise ApiError(409, "VALIDATION", "Already reported", f"{name} {day} already has a report")
            win = oracle.windows(w.st, iid, D)
            if w.now < win["fetchAt"]:
                raise bad(f"{name} {day} is not observable before {ts_to_iso(win['fetchAt'])}")
            vals = clock.day_values(D, w.now)
            if name not in vals:
                raise ApiError(409, "VALIDATION", "No value", f"the snapshot has no value for {name} {day}")
            v, vh = vals[name]
            self.engine(oracle.post_report, w.led, w.now, iid, D, v, vintage_hash=vh)
            row = next(r for r in views.oracle_rows(w.st, w.now, days_back=10_000) if r.index == name and r.day == day)
            return self.execution(cls, row)

    def tx_confirm(self, tx_hash: str) -> TxConfirm:
        return TxConfirm(status="confirmed", block_number=0, objects=[])

    # ------------------------------------------------------------ staking
    def staking(self, wid: str, owner: str | None):
        w = self.read(wid)
        return views.staking(w.st, w.meta, owner, w.now)

    def stake(self, wid: str, owner: str, amount: int, cls):
        with self.write(wid) as w:
            if amount <= 0:
                raise bad("amountWei must be positive")
            self.engine(staking.stake, w.led, w.now, owner, amount)
            return self.execution(cls, views.staking(w.st, w.meta, owner, w.now))

    def unstake_request(self, wid: str, owner: str, shares: int, cls):
        with self.write(wid) as w:
            if shares <= 0:
                raise bad("shares must be positive")
            self.engine(staking.request_unstake, w.led, w.now, owner, shares)
            return self.execution(cls, views.staking(w.st, w.meta, owner, w.now))

    def unstake_claim(self, wid: str, owner: str, rid: int, cls):
        with self.write(wid) as w:
            r = w.st["wi"]["unstakes"].get(str(rid))
            if r is None or r["owner"] != owner:
                raise ApiError(404, "NOT_FOUND", "Unknown unstake request", str(rid))
            self.engine(staking.claim_unstake, w.led, w.now, rid)
            return self.execution(cls, views.staking(w.st, w.meta, owner, w.now))


class _ReadWorld:
    """A loaded blob for read-only views (no Ledger copy)."""

    def __init__(self, blob: dict):
        self.st = blob["state"]
        self.meta = blob["meta"]

    @property
    def now(self) -> int:
        return self.meta["simTs"]

    @property
    def sim_day(self) -> int:
        return self.now // DAY_S

    def basis_market_id(self, site: str, day: int) -> str:
        from wi.engine.eip712 import market_id

        R = P(self.st, "basisRangeTenths")
        return market_id(index_id(cat.pair_index(site)), day, -R, R)

    def prehistory(self):
        return {index_id(cat.pair_index(s)): sd.pair_prehistory(s, cat.SITES[s][5], cat.FIRST_DAY)
                for s in cat.PAIR_SITES}

    # quoting.build(emit=False) needs these
    @property
    def led(self):
        return None


def normalize_index(index: str) -> str:
    if index in cat.INDEX_NAMES:
        return index
    if index.startswith("tmax:"):
        site = cat.SITE_BY_STATION.get(index.split(":", 1)[1])
        if site:
            return cat.cli_index(site)
    raise bad(f"unknown index {index!r}; use an engine index name (e.g. CLI:LGA:TMAX:v1) or tmax:<station id>")


# ---------------------------------------------------------------- view helpers shared with EvmLedger
def business_view(rec: dict) -> Business:
    site = rec["locationSite"]
    sid, name, lat, lon, metro, settle, _ = cat.SITES[site]
    rs = cat.RAIN_SITE.get(metro)
    return Business(business_id=rec["businessId"], name=rec["name"], owner=views.out_addr(rec["owner"]),
                    lat=rec["lat"], lon=rec["lon"], zip=rec.get("zip"), naics=rec.get("naics"), city=metro,
                    settlement_station=cat.SITES[settle][0], location_index=cat.cli_index(site),
                    residual_contract_id=cat.contract_id(site) if site != settle else "",
                    location_site=site, distance_km=rec.get("distanceKm"),
                    rain_station_id=cat.SITES[rs][0] if rs else None, rain_station_name=cat.SITES[rs][1] if rs else None)


def elasticity_view(e: dict) -> Elasticity:
    return Elasticity(heat=Coef(**e["heat"]), wet=Coef(**e["wet"]), shrink_weight=e["shrink_weight"],
                      prior=Prior(**e["prior"]), origin=e["origin"], method=e["method"], he_cover=e["he_cover"],
                      he_ladder=e["he_ladder"], he_by_path=e["he_by_path"], advisory_only=e["advisory_only"],
                      prior_group=e["prior_group"], model=e["model"], heat_usd_per_deg_f=e["heat_usd_per_deg_f"],
                      rain_contracts=e["rain_contracts"],
                      recent_mean_daily_sales_cents=e["recent_mean_daily_sales_cents"], rows_used=e["rows_used"],
                      rows_ignored_after_sim_day=e["rows_ignored_after_sim_day"], warnings=e["warnings"])


def quote_view(rec: dict) -> Quote:
    he = sd.he()["groups"]
    rungs = [Rung(ticker=r["ticker"], qty=r["qty"], ask_cents=r["askCents"], qty_centi=r["qtyCenti"],
                  for_day=r.get("day"), source=r.get("source")) for r in rec.get("rungs") or []]
    ladder = [Rung(ticker=r["ticker"], qty=r["qty"], ask_cents=r["askCents"], qty_centi=r["qtyCenti"],
                   for_day=r.get("day"), source=r.get("source")) for r in rec.get("ladder") or []] or None
    g = el.group_for(cat.SITES[cat.CONTRACTS.get(rec.get("contractId"), "NYC")][4] if rec.get("contractId") else "NYC",
                     None)[0]
    he_v = he.get(g, {}).get("heCover" if rec["path"] == "house-hedge" else "heLadder") or 0.0
    if rec.get("peril") == "rain":  # EVAL-01 wet-day HE (cover vs the Kalshi binary bought by the business)
        he_v = sd.rain().get("he", {}).get("heCover" if rec["path"] == "house-hedge" else "heLadder") or 0.0
    return Quote(
        quote_id=rec["quoteId"], expires_at=ts_to_iso(rec["expiry"]), premium_e6=rec["premium"],
        station_leg_e6=rec["station"], residual_leg_e6=rec["residual"],
        fees_e6=rec["premium"] - rec["station"] - rec["residual"], max_payout_e6=rec["maxPayout"], he_estimate=he_v,
        station_leg=StationLeg(series=rec.get("series", ""), as_of=ts_to_iso(rec.get("asOf", 0)), rungs=rungs,
                               overround_bp=rec.get("overround", 0)),
        residual_leg=ResidualLeg(contract_id=rec.get("contractId", ""), qty=rec.get("residualQty", 0),
                                 fair_price_e6=rec.get("fair", 0), half_spread_e6=rec.get("half", 0),
                                 tick=rec.get("residualTick"), basis_tenths_f=rec.get("basis")),
        ladder_for_business=ladder, tail_e6=rec["tail"], risk_margin_e6=rec["risk"], notional_fee_e6=rec["nfee"],
        treasury_fee_e6=rec["fee"], days=rec["days"], per_day_premium_e6=rec["perDay"],
        priced_with_ladder_day=rec.get("pricedWith"), note=rec.get("note"))


def base_config(mode: str, chain: ChainInfo, contracts: dict) -> Config:
    return Config(
        mode=mode, chain=chain, contracts=contracts,
        stations=[Station(station_id=s[0], city=s[1], name=s[2], lat=s[3], lon=s[4], kalshi_series=s[5],
                          settlement_source=s[6]) for s in cat.STATIONS],
        auction_contracts=[AuctionContract(contract_id=cat.contract_id(s), station_id=cat.SITES[cat.SITES[s][5]][0],
                                           index_id=cat.pair_index(s), range_tenths_f=50,
                                           description=f"{cat.SITES[s][1]} minus {cat.SITES[cat.SITES[s][5]][1]} "
                                                       f"daily high, +-5.0 F")
                           for s in cat.PAIR_SITES],
        schedule=Schedule(house_cutoff_utc="02:30", public_cutoff_utc="03:00"),
        limits=Limits(max_orders_per_auction=200, max_sales_rows=MAX_SALES_ROWS, max_body_bytes=MAX_BODY_BYTES),
        sites=[Site(site=k, station_id=v[0], name=v[1], lat=v[2], lon=v[3], metro=v[4],
                    settlement_station=cat.SITES[v[5]][0], index_id=cat.cli_index(k),
                    residual_contract_id=cat.contract_id(k) if k != v[5] else None, source=v[6])
               for k, v in cat.SITES.items()],
        replay_window=[day_to_iso(cat.FIRST_DAY), day_to_iso(cat.LAST_DAY)])

