"""Wire views over an engine-shaped state dict (SPEC section 13 state). Transport only: every number here
is read from the state, never computed as money. SimLedger passes the engine reducer state; EvmLedger
passes a state dict it rebuilds from chain reads, so the same views render both modes (that is what
makes the sim-vs-anvil golden a real parity test).

State keys used: bal, pool, policies, orders, markets, pos, obs, wi, hedges, params, house.
"""
from __future__ import annotations

from wi.engine.eip712 import index_id
from wi.engine.state import P
from wi.engine.units import DAY_S, TICK, UNIT, day_to_iso, tick_to_index, ts_to_iso

from . import catalog as cat
from .models import (
    Balances, Conservation, Cooldown, ExposureRow, Fill, Haircut, HedgeRow, HouseQuote, HouseQuoteRow, InventoryRow,
    Level, LpPosition, NavPoint, OracleRow, Order, Policy, PoolQueue, PoolState, Positions, QueueTicket,
    ResidualPosition, Rung, Settlement, StakingView,
)

NAMES = {index_id(n): n for n in cat.INDEX_NAMES}
PAIR_BY_INDEX = {index_id(cat.pair_index(s)): s for s in cat.PAIR_SITES}
SHARE = 10**12  # one whole pool share (SeniorShare has 12 decimals)


def out_addr(a: str) -> str:
    from eth_utils import to_checksum_address

    return to_checksum_address(a)


def nav_e6(supply: int, assets: int) -> int:
    """Value of one whole share (1e12) in base units; 1 USDC before any deposit."""
    if supply == 0:
        return UNIT
    return SHARE * (assets + 1) // (supply + 10**6)


def contract_of_market(st: dict, mk: str) -> str:
    m = st["markets"][mk]
    s = PAIR_BY_INDEX.get(m["indexId"])
    return cat.contract_id(s) if s else NAMES.get(m["indexId"], m["indexId"])


def auction_id(cid: str, day: int) -> str:
    return f"auc_{cid}_{day_to_iso(day)}"


def order_id_out(n: int) -> str:
    return f"ord_{n:06d}"


def basis(tick: int, R: int) -> int:
    return tick_to_index(tick, -R, R)


# ---------------------------------------------------------------- accounts
def locked_of(st: dict, addr: str) -> int:
    n = 0
    for o in st["orders"].values():
        if o["trader"] == addr and not o["claimed"]:
            n += o["escrow"]
    for k, ps in st["pos"].items():
        if k.endswith("|" + addr) and not ps["done"]:
            n += ps["paid"]
    return n


def balances(st: dict, addr: str) -> Balances:
    p = st["pool"]
    return Balances(usdc_e6=st["bal"].get(addr, 0), locked_e6=locked_of(st, addr),
                    senior_shares=p["seniorShares"].get(addr, 0), junior_shares=p["juniorShares"].get(addr, 0))


# ---------------------------------------------------------------- policies
def _vintage(st: dict, iid: str, day: int) -> str:
    ob = st["obs"].get(f"{iid}:{day}")
    return (ob or {}).get("vintage") or (ob or {}).get("vintage0") or ""


def unit_of(name: str) -> str:
    """Settlement unit of an index name: wetDay for the rain indices (CLI:<S>:WET), tenthsF otherwise."""
    return "wetDay" if ":WET:" in name else "tenthsF"


def policy_rows(st: dict, rec: dict) -> tuple[list[Settlement], int, bool]:
    """(settlement rows, refunded, all closed). A row exists only once the engine settled or voided that day."""
    rows, refunded, closed = [], 0, True
    for eid, day_iso in zip(rec["enginePolicyIds"], rec["days"]):
        pol = st["policies"].get(str(eid))
        if pol is None:
            closed = False
            continue
        m = st["markets"][pol["market"]]
        name = NAMES.get(m["indexId"], m["indexId"])
        if pol["status"] in ("Bound", "Settled") and "toPool" in pol:
            refunded += pol["premium"] - pol["toPool"] - pol["keptFee"]
        if pol["status"] == "Settled":
            if "x" in pol:
                rows.append(Settlement(ref_id=f"{rec['policyId']}:{day_iso}", kind="policy", day=day_iso, index=name,
                                       value=pol["x"], unit=unit_of(name), source=rec.get("source", "NWS CLI"),
                                       vintage_hash=_vintage(st, m["indexId"], m["day"]), status="final",
                                       payout_e6=pol["payout"]))
            else:  # bound at 0 units: the residual leg did not fill, premium refunded at bind
                rows.append(Settlement(ref_id=f"{rec['policyId']}:{day_iso}", kind="policy", day=day_iso, index=name,
                                       value=0, unit=unit_of(name), source="downsized to 0 units at bind (premium refunded)",
                                       vintage_hash="", status="final", payout_e6=0))
        elif pol["status"] == "Voided":
            refunded += pol.get("refundOnVoid", 0)
            rows.append(Settlement(ref_id=f"{rec['policyId']}:{day_iso}", kind="policy", day=day_iso, index=name,
                                   value=0, unit=unit_of(name), source="void: no index value (premium refunded)",
                                   vintage_hash="", status="void", payout_e6=0))
        else:
            closed = False
    return rows, refunded, closed


def policy(st: dict, rec: dict) -> Policy:
    rows, refunded, closed = policy_rows(st, rec)
    return Policy(policy_id=rec["policyId"], business_id=rec["businessId"], holder=out_addr(rec["holder"]),
                  path=rec["path"], peril=rec["peril"], strike_tenths_f=rec["strike"], cap_tenths_f=rec["cap"],
                  days=rec["days"], units=rec["units"], premium_e6=rec["premium"], max_payout_e6=rec["maxPayout"],
                  status="settled" if closed else "active", settlements=rows, refunded_e6=refunded)


# ---------------------------------------------------------------- auctions
def orders_of_market(st: dict, mk: str) -> list[tuple[int, dict]]:
    return [(i, st["orders"][str(i)]) for i in st["markets"][mk]["orderIds"]]


def order(st: dict, oid: int, o: dict) -> Order:
    m = st["markets"][o["market"]]
    if not o["claimed"]:
        status, locked, filled = "open", o["escrow"], 0
        if m["cleared"] is not None:
            from wi.engine.auction import fill_o1

            filled = fill_o1(o["isBid"], o["tick"], o["qty"], o["ahead"], m["cleared"])
            status = "unfilled" if filled == 0 else ("filled" if filled == o["qty"] else "partial")
    else:
        filled = o.get("fill", 0)
        status = "unfilled" if filled == 0 else ("filled" if filled == o["qty"] else "partial")
        c = m["cleared"]
        locked = filled * (c["pStar"] if o["isBid"] else 100 - c["pStar"]) * TICK if filled else 0
        ps = st["pos"].get(f"{o['market']}|{o['trader']}")
        if ps is not None and ps["done"]:
            locked = 0
    return Order(order_id=order_id_out(oid), auction_id=auction_id(contract_of_market(st, o["market"]), m["day"]),
                 trader=out_addr(o["trader"]), side="buy" if o["isBid"] else "sell", qty=o["qty"],
                 limit_price_e6=o["tick"] * TICK, locked_e6=locked, status=status, filled_qty=filled)


def auction_status(st: dict, mk: str, now: int) -> str:
    m = st["markets"][mk]
    if m["cleared"] is not None:
        return "cleared"
    return "open" if now < m["cutoff"] else "closed"


def house_quote(st: dict, mk: str) -> HouseQuote | None:
    house = st["world"]["roles"]["house"] if "world" in st else cat.HOUSE
    bids = [o for _, o in orders_of_market(st, mk) if o["trader"] == house and o["policyId"] == 0 and o["isBid"]]
    asks = [o for _, o in orders_of_market(st, mk) if o["trader"] == house and o["policyId"] == 0 and not o["isBid"]]
    if not bids or not asks:
        return None
    R = st["markets"][mk]["hi"]
    b, a = max(o["tick"] for o in bids), min(o["tick"] for o in asks)
    return HouseQuote(bid_e6=b * TICK, ask_e6=a * TICK, max_qty=sum(o["qty"] for o in bids + asks),
                      bid_basis_tenths_f=basis(b, R), ask_basis_tenths_f=basis(a, R))


def levels(st: dict, mk: str) -> tuple[list[Level], list[Level]]:
    m = st["markets"][mk]
    R = m["hi"]
    bids = [Level(price_e6=int(t) * TICK, qty=q, basis_tenths_f=basis(int(t), R))
            for t, q in sorted(m["levels"]["b"].items(), key=lambda kv: -int(kv[0])) if q]
    asks = [Level(price_e6=int(t) * TICK, qty=q, basis_tenths_f=basis(int(t), R))
            for t, q in sorted(m["levels"]["o"].items(), key=lambda kv: int(kv[0])) if q]
    return bids, asks


def clearing(st: dict, mk: str) -> dict | None:
    from wi.engine.auction import fill_o1

    m = st["markets"][mk]
    c = m["cleared"]
    if c is None:
        return None
    house = st["world"]["roles"]["house"] if "world" in st else cat.HOUSE
    fills, pool_q, long_l, short_l = [], 0, 0, 0
    for oid, o in orders_of_market(st, mk):
        f = fill_o1(o["isBid"], o["tick"], o["qty"], o["ahead"], c)
        if not f:
            continue
        fills.append(Fill(order_id=order_id_out(oid), trader=out_addr(o["trader"]),
                          side="buy" if o["isBid"] else "sell", qty=f))
        if o["trader"] == house:
            pool_q += f
        if o["isBid"]:
            long_l += f * c["pStar"] * TICK
        else:
            short_l += f * (100 - c["pStar"]) * TICK
    q = c["qStar"]
    return {"price_e6": c["pStar"] * TICK if q else None, "filled_qty": q, "fills": fills, "pool_filled_qty": pool_q,
            "conservation": Conservation(long_locked_e6=long_l, short_locked_e6=short_l,
                                         ok=(long_l + short_l == q * UNIT)),
            "basis_tenths_f": basis(c["pStar"], m["hi"]) if q else None}


# ---------------------------------------------------------------- pool
def pool_state(st: dict, meta: dict) -> PoolState:
    p = st["pool"]
    cap = p["senior"] + p["junior"]
    locked = p["reserved"] + p["deployed"]
    exp: dict[str, list[int]] = {}
    house = cat.HOUSE
    for k, ps in st["pos"].items():
        mk, trader = k.split("|")
        if trader == house and not ps["done"]:
            row = exp.setdefault(contract_of_market(st, mk), [0, 0])
            row[0] += ps["long"] - ps["short"]
            row[1] += ps["paid"]
    for o in st["orders"].values():
        if o["trader"] == house and not o["claimed"]:
            exp.setdefault(contract_of_market(st, o["market"]), [0, 0])[1] += o["escrow"]
    for pol in st["policies"].values():
        if pol["status"] in ("Bought", "Bound"):
            u = pol["units"] if pol["status"] == "Bought" else pol["boundUnits"]
            row = exp.setdefault(NAMES.get(st["markets"][pol["market"]]["indexId"], "?"), [0, 0])
            row[0] += -u if pol["isLong"] else u
            row[1] += u * UNIT
    tickets = [ticket(st, t) for t in meta.get("tickets", [])]
    return PoolState(
        senior_assets_e6=p["senior"], junior_assets_e6=p["junior"], senior_shares=p["seniorSupply"],
        junior_shares=p["juniorSupply"], senior_rate_bp=P(st, "seniorPremiumBps"),
        utilization_bp=locked * 10_000 // cap if cap else 0, locked_e6=locked, free_e6=cap - locked,
        exposure_by_contract=[ExposureRow(contract_id=c, net_qty=v[0], locked_e6=v[1]) for c, v in sorted(exp.items())],
        queue=PoolQueue(deposits=[t for t in tickets if t.kind == "deposit"],
                        withdrawals=[t for t in tickets if t.kind == "withdrawal"]),
        nav_history=[NavPoint(ts=ts_to_iso(ts), senior_nav_e6=s, junior_nav_e6=j) for ts, s, j in meta.get("nav", [])],
        capital_e6=cap, reserved_e6=p["reserved"], deployed_e6=p["deployed"],
        senior_premium_share_bp=P(st, "seniorPremiumBps"))


def ticket(st: dict, t: dict) -> QueueTicket:
    status, request_id, claim_by = "processed", None, None
    if t["kind"] == "withdrawal":
        req = st["pool"]["withdrawals"].get(str(t["requestId"]), {})
        status = {"cancelled": "cancelled", "lapsed": "lapsed"}.get(req.get("status"), "processed") \
            if req.get("claimed") else "queued"
        request_id = str(t["requestId"])
        if req:
            claim_by = ts_to_iso(req["claimableAt"] + P(st, "withdrawClaimWindow"))
    return QueueTicket(ticket_id=t["ticketId"], kind=t["kind"], owner=out_addr(t["owner"]), tranche=t["tranche"],
                       amount_e6=t.get("amount") if t["kind"] == "deposit" else
                       st["pool"]["withdrawals"].get(str(t.get("requestId")), {}).get("amount"),
                       shares=t.get("shares"), epoch_ts=ts_to_iso(t["epochTs"]), status=status,
                       request_id=request_id, claim_by=claim_by)


# ---------------------------------------------------------------- positions
def residuals(st: dict, addr: str) -> list[ResidualPosition]:
    out = []
    for k, ps in sorted(st["pos"].items()):
        mk, trader = k.split("|")
        if trader != addr or ps["done"]:
            continue
        m = st["markets"][mk]
        cost = {True: [0, 0], False: [0, 0]}
        for _, o in orders_of_market(st, mk):
            if o["trader"] == addr and o["claimed"] and o.get("fill"):
                c = m["cleared"]
                cost[o["isBid"]][0] += o["fill"]
                cost[o["isBid"]][1] += o["fill"] * (c["pStar"] if o["isBid"] else 100 - c["pStar"]) * TICK
        for is_long, qty in ((True, ps["long"]), (False, ps["short"])):
            if qty:
                q, paid = cost[is_long]
                entry = paid // q if q else 0
                out.append(ResidualPosition(contract_id=contract_of_market(st, mk), day=day_to_iso(m["day"]),
                                            side="buy" if is_long else "sell", qty=qty,
                                            entry_price_e6=entry if is_long else UNIT - entry,
                                            locked_e6=paid))
    return out


def lp(st: dict, addr: str) -> list[LpPosition]:
    p = st["pool"]
    out = []
    for tr, sup, assets in (("senior", p["seniorSupply"], p["senior"]), ("junior", p["juniorSupply"], p["junior"])):
        sh = p[f"{tr}Shares"].get(addr, 0)
        if sh:
            out.append(LpPosition(tranche=tr, shares=sh, value_e6=sh * (assets + 1) // (sup + 10**6)))
    return out


def positions(st: dict, meta: dict, addr: str) -> Positions:
    open_orders = [order(st, int(i), o) for i, o in sorted(st["orders"].items(), key=lambda kv: int(kv[0]))
                   if o["trader"] == addr and not o["claimed"]]
    return Positions(balances=balances(st, addr),
                     policies=[policy(st, r) for r in meta["policies"].values() if r["holder"] == addr],
                     residuals=residuals(st, addr), lp=lp(st, addr), open_orders=open_orders)


def residual_settlements(st: dict, addr: str) -> list[Settlement]:
    out = []
    for k, ps in sorted(st["pos"].items()):
        mk, trader = k.split("|")
        if trader != addr or not ps["done"]:
            continue
        m = st["markets"][mk]
        ob = st["obs"].get(f"{m['indexId']}:{m['day']}") or {}
        void = ob.get("status") == "void"
        out.append(Settlement(ref_id=f"{contract_of_market(st, mk)}:{day_to_iso(m['day'])}", kind="residual",
                              day=day_to_iso(m["day"]), index=NAMES.get(m["indexId"], m["indexId"]),
                              value=0 if void else ob.get("value", 0), unit="tenthsF", source="NWS CLI pair (IEM)",
                              vintage_hash=ob.get("vintage", ""), status="void" if void else "final",
                              payout_e6=ps.get("payout", 0)))
    return out


# ---------------------------------------------------------------- admin
def oracle_rows(st: dict, now: int, days_back: int = 4) -> list[OracleRow]:
    out = []
    d_now = now // DAY_S
    for k, ob in sorted(st["obs"].items()):
        iid, day = k.rsplit(":", 1)
        day = int(day)
        if day < d_now - days_back:
            continue
        status = {"posted": "reported", "final": "final", "void": "void"}[ob["status"]]
        out.append(OracleRow(index=NAMES.get(iid, iid), day=day_to_iso(day), value=ob.get("value", 0),
                             source="NWS CLI (IEM)", vintage_hash=ob.get("vintage", ""),
                             fetched_at=ts_to_iso(ob.get("asOf", ob.get("voidAt", 0))), status=status))
    return out


def hedges(st: dict) -> list[HedgeRow]:
    out = []
    for k, h in sorted(st["hedges"].items(), key=lambda kv: (kv[1]["decision"]["day"], kv[0])):
        fill = h["fill"] or {"rungs": [], "costE6": 0}
        asks = {r["ticker"]: r.get("askCents", 0) for r in h["decision"]["rungs"]}
        rungs = [Rung(ticker=r["ticker"], qty=r["filledCenti"] // 100, ask_cents=asks.get(r["ticker"], 0),
                      qty_centi=r["filledCenti"]) for r in fill["rungs"] if r["filledCenti"]]
        out.append(HedgeRow(series=h["decision"]["series"], day=day_to_iso(h["decision"]["day"]), rungs=rungs,
                            cost_e6=fill["costE6"], payout_e6=(h["settled"] or {}).get("payoutE6")))
    return out


def house_quotes(st: dict, now: int) -> list[HouseQuoteRow]:
    out = []
    for mk, m in sorted(st["markets"].items(), key=lambda kv: (kv[1]["day"], kv[0])):
        if not m["auctioned"] or auction_status(st, mk, now) != "open":
            continue
        hq = house_quote(st, mk)
        if hq:
            out.append(HouseQuoteRow(auction_id=auction_id(contract_of_market(st, mk), m["day"]), bid_e6=hq.bid_e6,
                                     ask_e6=hq.ask_e6, max_qty=hq.max_qty))
    return out


def inventory(st: dict) -> list[InventoryRow]:
    net: dict[str, int] = {}
    for k, ps in st["pos"].items():
        mk, trader = k.split("|")
        if trader == cat.HOUSE and not ps["done"]:
            c = contract_of_market(st, mk)
            net[c] = net.get(c, 0) + ps["long"] - ps["short"]
    return [InventoryRow(contract_id=c, net_qty=v) for c, v in sorted(net.items())]


def caps_used(st: dict) -> dict[str, float]:
    from wi.engine import margin

    p = st["pool"]
    cap = p["senior"] + p["junior"]
    if cap == 0:
        return {"C1": 0.0, "C3": 0.0, "C4": 0.0, "C5": 0.0}
    out = {"C1": round((p["reserved"] + p["deployed"]) * 10_000 / (P(st, "capBps") * cap), 4)}
    exp = margin.exposures(st)
    lim = margin.limits(st)
    for key, name in (("idx", "C3"), ("sta", "C4"), ("met", "C5")):
        worst = max((v * 10_000 / lim[key] for g, v in exp.items() if g[0] == key), default=0.0)
        out[name] = round(worst, 4)
    return out


# ---------------------------------------------------------------- staking
def staking(st: dict, meta: dict, addr: str | None, now: int | None = None) -> StakingView:
    from wi.engine.staking import unstake_amount

    wi = st["wi"]
    sh = wi["shares"].get(addr, 0) if addr else 0
    cds = []
    for rid, r in sorted(wi["unstakes"].items(), key=lambda kv: int(kv[0])):
        if addr and r["owner"] == addr:
            val = r.get("amount") if r["claimed"] else unstake_amount(wi, r["shares"])
            cds.append(Cooldown(request_id=int(rid), shares=str(r["shares"]), value_wei=str(val),
                                claimable_at=ts_to_iso(r["claimableAt"]), claimed=r["claimed"],
                                claimable=bool(now is not None and not r["claimed"] and now >= r["claimableAt"])))
    val = unstake_amount(wi, sh) if sh else 0
    return StakingView(
        owner=out_addr(addr) if addr else None, wi_balance_wei=str(wi["bal"].get(addr, 0) if addr else 0),
        staked_shares=str(sh), staked_value_wei=str(val), voting_power_wei=str(val),
        total_staked_wei=str(wi["totalStaked"]), total_shares=str(wi["totalShares"]),
        cooldown_days=P(st, "unstakeCooldown") // DAY_S, haircut_cap_bps=P(st, "haircutCapBps"),
        cooldowns=cds,
        haircuts=[Haircut(day=day_to_iso(h["day"]), bps=h["bps"], burned_wei=str(h["burned"]))
                  for h in meta.get("haircuts", [])],
        note="Staked WI votes on pool settings and is cut pro rata (burned) when the junior tranche loses money on a "
             "closed day, at most haircutCapBps per event; shares in cooldown stay cuttable. Stakers earn nothing in v0.")
