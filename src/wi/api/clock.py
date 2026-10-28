"""Sim clock: the SPEC section 4 daily timeline replayed over the snapshot calendar (Pattern 5).

The clock is explicit world state (`meta.simTs`). `advance(world, t1)` runs every scheduled step with
simTs < ts <= t1 in (ts, priority) order, each through the engine, then sets simTs = t1. Steps are
idempotent against the state (house steps inspect what they already did), so the schedule is a pure
function of the calendar and a step never runs twice because the clock only moves forward.

Per climate day D (all UTC):
  D-1 14:00  markets     create D's residual (basis) markets, one per pair           -> markets_open
  D-1 14:05  book        house quote schedule on D's basis markets                   -> markets_open
  D   02:20  book        house residual legs for policies sold since (house cutoff 02:30) -> house_cutoff
  D   03:00  clear       clear + claim every basis market of D, bind D's policies    -> public_cutoff
  close-24h  hedge       house paper-hedges the bound station legs per series        -> hedge
  D+1 12:00  oracle      reporter posts CLI + pair values for D                      -> oracle_fetch
  settle_ts  hedge       Kalshi result -> HedgeSettled                               -> hedge
  D+2 12:00  finalize    finalize, settle policies and positions, house returns D    -> finalize
  D+5 12:00  void        void unreported index-days, refund (only if any)            -> finalize
  daily 12:30 epoch      PoolEpoch, matured withdrawals / unstakes, close days       -> epoch
"""
from __future__ import annotations

from wi.engine import house_mm, oracle, policy, pool, staking
from wi.engine.state import P, Revert
from wi.engine.units import DAY_S, sha256_hex, ts_to_iso

from . import catalog as cat
from . import snapshot_data as sd
from .world import SimWorld

KIND = {"markets": "markets_open", "book0": "markets_open", "book": "house_cutoff", "clear": "public_cutoff",
        "hedge": "hedge", "oracle": "oracle_fetch", "hsettle": "hedge", "finalize": "finalize", "void": "finalize",
        "epoch": "epoch"}


def _at(day: int, hh: int, mm: int = 0) -> int:
    return day * DAY_S + hh * 3600 + mm * 60


RAIN_SERIES = set(cat.RAIN_SERIES.values())


def series_rungs(series: str, D: int) -> list[dict] | None:
    """The day's Kalshi rungs for a temperature series or a daily rain series (one "> 0 in" rung)."""
    return sd.rain_ladder(series, D) if series in RAIN_SERIES else sd.ladder(series, D)


def steps_for_day(D: int) -> list[tuple]:
    out = [(_at(D - 1, 14), 10, "markets", D, ""), (_at(D - 1, 14, 5), 20, "book0", D, ""),
           (_at(D, 2, 20), 30, "book", D, ""), (_at(D, 3), 40, "clear", D, "")]
    for series in list(cat.HEDGE_SERIES.values()) + list(cat.RAIN_SERIES.values()):
        rungs = series_rungs(series, D)
        if rungs:
            close_ts = max(r["close_ts"] for r in rungs)
            out.append((close_ts - cat.params()["hedgeLeadS"], 50, "hedge", D, series))
            out.append((max(r["settle_ts"] for r in rungs), 65, "hsettle", D, series))
    out += [(_at(D + 1, 12), 60, "oracle", D, ""), (_at(D + 2, 12), 70, "finalize", D, ""),
            (_at(D + 5, 12), 71, "void", D, "")]
    return out


def schedule(t0: int, t1: int) -> list[tuple]:
    """Every step with t0 < ts <= t1, ordered by (ts, priority, day, series)."""
    lo_day = max(cat.FIRST_DAY, t0 // DAY_S - 6)
    hi_day = min(cat.LAST_DAY, t1 // DAY_S + 2)
    items = []
    for D in range(lo_day, hi_day + 1):
        items += [s for s in steps_for_day(D) if t0 < s[0] <= t1]
    for d in range(t0 // DAY_S - 1, t1 // DAY_S + 1):
        ts = _at(d, 12, 30)
        if t0 < ts <= t1 and d >= cat.FIRST_DAY - 1:
            items.append((ts, 80, "epoch", d, ""))
    return sorted(items, key=lambda s: (s[0], s[1], s[3], s[4]))


def rest_after(t0: int, days: int) -> int:
    """The `days`-th 20:00Z rest point strictly after t0, capped at the end of the replay window."""
    base = (t0 // DAY_S) * DAY_S + cat.REST_S
    first = base if base > t0 else base + DAY_S
    return min(first + (days - 1) * DAY_S, cat.END_TS)


# ---------------------------------------------------------------- steps
def _markets(w: SimWorld, ts: int, D: int) -> str:
    for s in cat.PAIR_SITES:
        w.ensure_basis_market(ts, s, D)
    return f"residual auctions for {ts_to_iso(D * DAY_S)[:10]} open ({len(cat.PAIR_SITES)} pairs)"


def _book(w: SimWorld, ts: int, D: int) -> str:
    st = w.st
    before = st["nextOrderId"]
    house_mm.book(w.led, ts, D, w.basis_markets(D), w.prehistory())
    return f"house posted {st['nextOrderId'] - before} orders for {ts_to_iso(D * DAY_S)[:10]}"


def _clear(w: SimWorld, ts: int, D: int) -> str:
    st = w.st
    bms = w.basis_markets(D)
    house_mm.bind(w.led, ts, D, bms)
    q = sum((st["markets"][m]["cleared"] or {}).get("qStar", 0) for m in bms)
    return f"auctions for {ts_to_iso(D * DAY_S)[:10]} cleared ({q} units); policies bound"


def _hedge(w: SimWorld, ts: int, D: int, series: str) -> str | None:
    plan = house_mm.hedge_day(w.led, ts, D, series, series_rungs(series, D))
    if plan is None:  # rain series stay silent when no rain cover is sold that day (the event list is unchanged)
        return None if series in RAIN_SERIES else f"{series} {ts_to_iso(D * DAY_S)[:10]}: nothing to hedge"
    f = plan["fill"]
    return f"{series} {ts_to_iso(D * DAY_S)[:10]}: station leg hedged, cost ${f['costE6'] / 1e6:,.2f}, shortfall {f['shortfallCenti'] / 100:g} contracts"


def _hsettle(w: SimWorld, ts: int, D: int, series: str) -> str | None:
    pay = house_mm.settle_hedge(w.led, ts, D, series, series_rungs(series, D))
    if pay is None and series in RAIN_SERIES:
        return None
    msg = f"{series} {ts_to_iso(D * DAY_S)[:10]}: Kalshi result, hedge paid ${(pay or 0) / 1e6:,.2f}"
    if pay is not None and ts >= _at(D + 2, 12):
        # Kalshi settled after the day went final (KXRAIN often settles D+2 11:30-15:30Z): the house return that the
        # finalize step could not make (a hedge was still open) happens now. Before D+2 12:00Z nothing changes.
        pnl = house_mm.ret(w.led, ts, D)
        if pnl is not None:
            w.meta["housePnl"] = w.meta.get("housePnl", 0) + pnl
            msg += f"; house returned day {ts_to_iso(D * DAY_S)[:10]}"
    return msg


def pair_vintage(a: str, b: str) -> str:
    return "0x" + sha256_hex(bytes.fromhex(a[2:]) + bytes.fromhex(b[2:]))


def day_values(D: int, as_of: int) -> dict[str, tuple[int, str]]:
    """Index name -> (value, vintage hash) for climate day D, read at as_of (>= D+1 12:00Z)."""
    vals: dict[str, tuple[int, str]] = {}
    for s in cat.SITES:
        v = sd.cli_value(s, D, as_of)
        if v is not None:
            vals[cat.cli_index(s)] = v
    for s in cat.PAIR_SITES:
        a, b = vals.get(cat.cli_index(s)), vals.get(cat.cli_index(cat.SITES[s][5]))
        if a and b:
            vals[cat.pair_index(s)] = (a[0] - b[0], pair_vintage(a[1], b[1]))
    for s in cat.RAIN_SERIES:
        v = sd.wet_value(s, D, as_of)
        if v is not None:
            vals[cat.rain_index(s)] = v
    return vals


def _oracle(w: SimWorld, ts: int, D: int) -> str:
    n = 0
    for name, (v, vh) in sorted(day_values(D, ts).items()):
        iid = w.iid(name)
        if iid not in w.st["indices"] or f"{iid}:{D}" in w.st["obs"]:
            continue  # a world created before an index existed (e.g. the 13-RAIN wet-day indices) skips it
        oracle.post_report(w.led, ts, iid, D, v, vintage_hash=vh)
        n += 1
    return f"{n} index values posted for {ts_to_iso(D * DAY_S)[:10]}"


def settle_day(w: SimWorld, ts: int, D: int) -> int:
    st = w.st
    n = 0
    for pid, pol in house_mm.day_policies(st, D):
        m = st["markets"][pol["market"]]
        ob = st["obs"].get(f"{m['indexId']}:{D}")
        if ob is None:
            continue
        if ob["status"] == "final" and pol["status"] == "Bound":
            policy.settle_policy(w.led, ts, pid)
            n += 1
        elif ob["status"] == "void" and pol["status"] in ("Bought", "Bound"):
            policy.void_policy(w.led, ts, pid)
            n += 1
    for mk, m in list(st["markets"].items()):
        if m["day"] != D or not m["traders"]:
            continue
        ob = st["obs"].get(f"{m['indexId']}:{D}")
        if ob is not None and ob["status"] in ("final", "void") and m["unclaimed"] == 0:
            policy.settle_positions(w.led, ts, mk)
    pnl = house_mm.ret(w.led, ts, D)
    if pnl is not None:
        w.meta["housePnl"] = w.meta.get("housePnl", 0) + pnl
    return n


def _finalize(w: SimWorld, ts: int, D: int) -> str:
    st = w.st
    k = 0
    for iid in sorted(st["indices"]):
        ob = st["obs"].get(f"{iid}:{D}")
        if ob is not None and ob["status"] == "posted":
            oracle.finalize(w.led, ts, iid, D)
            k += 1
    n = settle_day(w, ts, D)
    return f"{k} values final for {ts_to_iso(D * DAY_S)[:10]}; {n} policy-days settled"


def _void(w: SimWorld, ts: int, D: int) -> str | None:
    st = w.st
    k = 0
    for iid in sorted(st["indices"]):
        if f"{iid}:{D}" not in st["obs"] and oracle.windows(st, iid, D)["voidAt"] <= ts:
            oracle.void_day(w.led, ts, iid, D)
            k += 1
    if k == 0:
        return None
    n = settle_day(w, ts, D)
    return f"{k} index-days void for {ts_to_iso(D * DAY_S)[:10]}; {n} policy-days refunded"


def _epoch(w: SimWorld, ts: int, d: int) -> str:
    st = w.st
    w.led.emit(ts, "PoolEpoch", {})
    done = []
    window = P(st, "withdrawClaimWindow")
    for rid, req in sorted(st["pool"]["withdrawals"].items(), key=lambda kv: int(kv[0])):
        if req["claimed"]:
            continue
        if ts >= req["claimableAt"] + window:  # claim window closed (SPEC 8.2): shares go back to the LP, no USDC moves
            pool.lapse_withdraw(w.led, ts, int(rid))
            done.append(f"withdrawal {rid} lapsed (shares back to the LP)")
        elif ts >= req["claimableAt"]:
            try:
                pool.claim_withdraw(w.led, ts, int(rid))
                done.append(f"withdrawal {rid} paid")
            except Revert as e:
                done.append(f"withdrawal {rid} deferred ({e.name})")
    for rid, r in sorted(st["wi"]["unstakes"].items(), key=lambda kv: int(kv[0])):
        if not r["claimed"] and ts >= r["claimableAt"]:
            staking.claim_unstake(w.led, ts, int(rid))
            done.append(f"unstake {rid} paid")
    active = sorted({int(x) for x in st["pool"]["openPolicies"]} | {int(x) for x in st["pool"]["deployedByDay"]})
    for day in active:
        if st["pool"]["closed"].get(str(day)):
            continue
        try:
            bps = pool.close_day(w.led, ts, day)
        except Revert:
            continue
        if bps:
            burned = next(ln["payload"]["burned"] for ln in reversed(w.led.lines) if ln["type"] == "WIHaircut")
            w.meta["haircuts"].append({"day": day, "bps": bps, "burned": str(burned), "ts": ts})
            done.append(f"day {ts_to_iso(day * DAY_S)[:10]} closed with a {bps} bps WI haircut")
    nav_point(w, ts)
    return "pool epoch" + (": " + "; ".join(done) if done else "")


def nav_point(w: SimWorld, ts: int) -> None:
    from .views import nav_e6

    p = w.st["pool"]
    w.meta["nav"].append([ts, nav_e6(p["seniorSupply"], p["senior"]), nav_e6(p["juniorSupply"], p["junior"])])
    w.meta["nav"] = w.meta["nav"][-90:]


def run_step(w: SimWorld, step: tuple) -> str | None:
    ts, _, kind, D, series = step
    if kind == "markets":
        return _markets(w, ts, D)
    if kind in ("book0", "book"):
        return _book(w, ts, D)
    if kind == "clear":
        return _clear(w, ts, D)
    if kind == "hedge":
        return _hedge(w, ts, D, series)
    if kind == "hsettle":
        return _hsettle(w, ts, D, series)
    if kind == "oracle":
        return _oracle(w, ts, D)
    if kind == "finalize":
        return _finalize(w, ts, D)
    if kind == "void":
        return _void(w, ts, D)
    if kind == "epoch":
        return _epoch(w, ts, D)
    raise ValueError(kind)


def advance(w: SimWorld, t1: int) -> list[dict]:
    """Run the schedule up to t1 and move the clock. A Revert inside a step is recorded, the step's
    earlier events stay (each event is atomic), and the clock keeps going; an InvariantError propagates
    (the state would be corrupt, so the store saves nothing)."""
    out = []
    t0 = w.now
    if t1 <= t0:
        return out
    for step in schedule(t0, t1):
        try:
            detail = run_step(w, step)
        except Revert as e:
            detail = f"{step[2]} {ts_to_iso(step[3] * DAY_S)[:10]} stopped: {e}"
            w.meta["notes"] = (w.meta["notes"] + [f"{ts_to_iso(step[0])} {detail}"])[-50:]
        w.meta["simTs"] = step[0]
        if detail:
            out.append({"ts": ts_to_iso(step[0]), "kind": KIND[step[2]], "detail": detail})
    w.meta["simTs"] = t1
    return out


def upcoming(w: SimWorld, horizon_s: int = DAY_S) -> list[dict]:
    return [{"ts": ts_to_iso(s[0]), "kind": KIND[s[2]], "detail": f"{s[2]} {ts_to_iso(s[3] * DAY_S)[:10]} {s[4]}".strip()}
            for s in schedule(w.now, w.now + horizon_s)]

