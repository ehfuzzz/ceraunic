"""Seed the pinned `demo` world of the engine API for the hosted demo (Phase 13). Stdlib only.

    python3 scripts/seed-demo.py                                   # hosted engine, ADMIN_TOKEN from the repo .env
    python3 scripts/seed-demo.py --origin http://127.0.0.1:8787    # local engine (admin token dev-admin)
    python3 scripts/seed-demo.py --check                           # read-only: the world still matches the manifest

What it does, in order (every write goes through the public API; the admin routes are reset, advance,
house-MM tick and the house-MM view):
  1. reset `demo` to genesis (2026-07-15 20:00Z; junior seed $200,000 from the house, senior $300,000)
  2. three businesses = the Phase 12 Square fixture merchants (apps/portal/fixtures/square), with opposite
     weather exposures: an NYC ice-cream shop (sells more on hot days -> cool-day cover), a Chicago bakery
     (sells less on hot days -> hot-day cover) and a Miami juice bar; each uploads its csv-export.csv rows,
     gets an elasticity and a recommendation, is funded from the sim faucet and buys a 7-day cover
     13-RAIN: the Chicago bakery also buys a 7-day rain cover ($20 per wet day at O'Hare, 07-16..07-22, house-hedge
     path). Its own history shows sales slightly UP on wet days (+4.7 %), so the recommendation is the smallest size
     ($1); the seed overrides the size to show the product, the same way the heat lines are overridden above
  3. advance 1 day (the clock opens the 07-17 residual auctions and books the house MM quote schedule);
     run a house-MM tick (idempotent: nothing new if the schedule is already booked)
  4. two demo traders post crossing orders on one 07-17 residual auction (LaGuardia minus Central Park)
  5. advance 2 days: that auction clears at 07-17 03:00Z, day 07-16 goes final and settles at 07-18 12:00Z
  6. read everything back and write reports/demo/seed-state.json (the numbers DEMO-SCRIPT.md quotes)

The admin token is read from the environment or the gitignored .env and is never printed.
Addresses are anvil's public dev accounts (catalog.DEMO_USERS); nobody should hold real value on them.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "apps/portal/fixtures/square"
OUT = ROOT / "reports/demo/seed-state.json"
HOSTED = "https://wi-engine.vercel.app"
E6 = 1_000_000

# anvil public accounts 4..9 (wi.api.catalog.DEMO_USERS)
NYC_OWNER = "0x15d34aaf54267db7d7c367839aaf71a00a2c6a65"
CHI_OWNER = "0x9965507d1a55bcc2695c58ba16fb37d819b0a4dc"
MIA_OWNER = "0x976ea74026e726554db657fa54763abd0c3a0aa9"
TRADER_BUY = "0x14dc79964da2c08b23698b3d3cc7ca32193d9955"
TRADER_SELL = "0x23618e81e3f5cdf7f54c3d65f7fbc0abf5b21e8f"

# (key, Square location id, name, lat, lon, zip, NAICS, owner, cover override or None = the recommendation)
MERCHANTS = [
    ("nyc", "LFIXNYC000001", "Fixture Scoops Midtown", 40.7648, -73.9808, "10019", "722515", NYC_OWNER, None),
    # The recommendation for the bakery is hot-day cover above 75 F. In mid-July Chicago nearly every day is above
    # 75 F, so the engine refuses it (it would cost more than it can pay). The bakery takes the same size above 90 F.
    ("chi", "LFIXCHI000002", "Fixture Bakehouse Midway", 41.7868, -87.7522, "60629", "311811", CHI_OWNER,
     {"peril": "heat", "strikeTenthsF": 900}),
    # Same story in Miami: hot-day cover above 75 F would pay every July day, so the engine refuses it; 93 F is the
    # first whole degree where the premium is under a fifth of the most the cover can pay.
    ("mia", "LFIXMIA000003", "Fixture Juice Bar Miami", 25.7959, -80.2870, "33126", "722515", MIA_OWNER,
     {"peril": "heat", "strikeTenthsF": 930}),
]
FAUCET_E6 = 1_000 * E6
# 13-RAIN: the bakery's rain cover (dollars per wet day at O'Hare; <= 30 so the Kalshi candle cap fills it in full)
RAIN_KEY = "chi"
RAIN_UNITS = 20
AUCTION_CONTRACT = "RES-LGA-NYC"
AUCTION_DAY = "2026-07-17"
TRADE_QTY = 20


def admin_token(origin: str) -> str:
    tok = os.environ.get("ADMIN_TOKEN")
    local = "127.0.0.1" in origin or "localhost" in origin
    if not tok and local:
        return "dev-admin"  # a local engine without ADMIN_TOKEN accepts the dev token; the .env token is the hosted one
    if not tok and (ROOT / ".env").exists():
        for line in (ROOT / ".env").read_text().splitlines():
            if line.startswith("ADMIN_TOKEN="):
                tok = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not tok:
        sys.exit("no ADMIN_TOKEN in the environment or .env")
    return tok


class Api:
    def __init__(self, origin: str, token: str | None):
        self.origin = origin.rstrip("/")
        self.token = token
        self.calls = 0

    def __call__(self, method: str, path: str, body=None, admin: bool = False, idem: str | None = None):
        h = {"Content-Type": "application/json", "X-WI-World": "demo"}
        if admin:
            h["X-Admin-Token"] = self.token or ""
        if idem:
            h["Idempotency-Key"] = idem
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(f"{self.origin}/api/v1{path}", data=data, headers=h, method=method)
        self.calls += 1
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=120) as f:
                    return json.load(f)
            except urllib.error.HTTPError as e:
                detail = e.read().decode(errors="replace")[:400]
                if e.code in (502, 503, 504) and attempt < 2:
                    time.sleep(2)
                    continue
                sys.exit(f"{method} {path} -> {e.code}: {detail}")
            except urllib.error.URLError as e:
                if attempt < 2:
                    time.sleep(2)
                    continue
                sys.exit(f"{method} {path} -> {e}")


def sales_rows(location_id: str) -> list[dict]:
    with open(FIX / "csv-export.csv") as f:
        return [{"date": r["date"], "grossSalesCents": int(r["gross_sales_cents"]), "orderCount": int(r["order_count"])}
                for r in csv.DictReader(f) if r["location_id"] == location_id]


def usd(e6: int | None) -> str:
    return "n/a" if e6 is None else f"${e6 / E6:,.2f}"


def snapshot(api: Api, merchants: dict) -> dict:
    """Everything DEMO-SCRIPT.md quotes, read from the world."""
    clock = api("GET", "/sim/clock")
    pool = api("GET", "/pool")
    out = {"simTime": clock["simTime"],
           "pool": {k: pool[k] for k in ("seniorAssetsE6", "juniorAssetsE6", "seniorShares", "juniorShares",
                                         "utilizationBp", "lockedE6", "freeE6", "seniorRateBp")},
           "merchants": {}}
    for key, m in merchants.items():
        pols = api("GET", f"/policies?holder={m['owner']}")
        bal = api("GET", f"/accounts/{m['owner']}/balances")
        pol = next(p for p in pols if p["peril"] != "rain")
        rain = next((p for p in pols if p["peril"] == "rain"), None)
        rows = [{"day": s["day"], "status": s["status"], "value": s["value"], "payoutE6": s["payoutE6"]}
                for s in pol["settlements"]]
        out["merchants"][key] = {**m, "policyId": pol["policyId"], "policyStatus": pol["status"],
                                 "premiumE6": pol["premiumE6"], "maxPayoutE6": pol["maxPayoutE6"],
                                 "refundedE6": pol.get("refundedE6", 0), "settlements": rows,
                                 "paidOutE6": sum(r["payoutE6"] for r in rows), "usdcE6": bal["usdcE6"]}
        if rain is not None:
            rr = [{"day": s["day"], "status": s["status"], "value": s["value"], "payoutE6": s["payoutE6"]}
                  for s in rain["settlements"]]
            out["merchants"][key]["rain"] = {**(m.get("rain") or {}), "policyId": rain["policyId"],
                                             "policyStatus": rain["status"], "premiumE6": rain["premiumE6"],
                                             "maxPayoutE6": rain["maxPayoutE6"], "units": rain["units"],
                                             "days": rain["days"], "settlements": rr,
                                             "paidOutE6": sum(r["payoutE6"] for r in rr)}
    auc = api("GET", f"/auctions/auc_{AUCTION_CONTRACT}_{AUCTION_DAY}")
    res = auc["result"] or {}
    out["auction"] = {"auctionId": auc["auctionId"], "status": auc["status"], "day": auc["day"],
                      "orderCount": auc["orderCount"], "priceE6": res.get("priceE6"),
                      "basisTenthsF": res.get("basisTenthsF"), "filledQty": res.get("filledQty"),
                      "poolFilledQty": res.get("poolFilledQty"), "conservation": res.get("conservation"),
                      "fills": res.get("fills")}
    out["auctionsByStatus"] = {}
    for a in api("GET", "/auctions"):
        out["auctionsByStatus"].setdefault(a["status"], []).append(a["auctionId"])
    out["traders"] = {name: api("GET", f"/accounts/{addr}/balances")["usdcE6"]
                      for name, addr in (("buyer", TRADER_BUY), ("seller", TRADER_SELL))}
    return out


def seed(api: Api) -> dict:
    t0 = time.time()
    w = api("POST", "/sim/worlds/demo/reset", {}, admin=True)
    assert w["simTime"] == "2026-07-15T20:00:00Z", w
    pool0 = api("GET", "/pool")
    genesis = {"simTime": w["simTime"], "juniorAssetsE6": pool0["juniorAssetsE6"], "seniorAssetsE6": pool0["seniorAssetsE6"]}
    assert pool0["juniorAssetsE6"] == 200_000 * E6 and pool0["seniorAssetsE6"] == 300_000 * E6, genesis
    print(f"reset demo: {w['simTime']}, junior {usd(pool0['juniorAssetsE6'])}, senior {usd(pool0['seniorAssetsE6'])}")

    merchants: dict[str, dict] = {}
    for key, lid, name, lat, lon, zp, naics, owner, override in MERCHANTS:
        b = api("POST", "/businesses", {"name": name, "lat": lat, "lon": lon, "zip": zp, "naics": naics, "owner": owner})
        bid = b["businessId"]
        rows = sales_rows(lid)
        s = api("POST", f"/businesses/{bid}/sales", {"source": "fixture", "rows": rows})
        e = api("POST", f"/businesses/{bid}/elasticity")
        rec = api("GET", f"/businesses/{bid}/recommendation")
        cover = {"peril": rec["peril"], "strikeTenthsF": rec["strikeTenthsF"], "capTenthsF": rec["capTenthsF"],
                 "units": rec["unitsPerDay"], "startDay": rec["startDay"], "endDay": rec["endDay"], "path": "house-hedge"}
        if override:
            cover.update(override)
        api("POST", "/faucet", {"address": owner, "amountE6": FAUCET_E6})
        q = api("POST", "/quotes", {"businessId": bid, **cover})
        buy = api("POST", "/policies", {"quoteId": q["quoteId"], "holder": owner}, idem=f"seed-demo-{key}")
        pol = buy["result"]
        merchants[key] = {
            "businessId": bid, "name": name, "squareLocationId": lid, "owner": owner, "site": b["locationSite"],
            "settlementStation": b["settlementStation"], "residualContractId": b["residualContractId"],
            "salesRowsSent": len(rows), "salesRowsStored": s["rows"], "salesFirst": s["firstDate"], "salesLast": s["lastDate"],
            "rowsUsed": e["rowsUsed"], "rowsIgnoredAfterSimDay": e["rowsIgnoredAfterSimDay"],
            "heatBeta": e["heat"]["beta"], "heatSe": e["heat"]["se"], "heatUsdPerDegF": e["heatUsdPerDegF"],
            "recentMeanDailySalesCents": e["recentMeanDailySalesCents"], "origin": e["origin"],
            "recommendation": {k: rec[k] for k in ("peril", "strikeTenthsF", "capTenthsF", "unitsPerDay", "startDay",
                                                   "endDay", "maxDailyPremiumE6")},
            "cover": cover, "overridden": bool(override),
            "quote": {"premiumE6": q["premiumE6"], "stationLegE6": q["stationLegE6"], "residualLegE6": q["residualLegE6"],
                      "feesE6": q["feesE6"], "maxPayoutE6": q["maxPayoutE6"], "perDayPremiumE6": q["perDayPremiumE6"],
                      "heEstimate": q["heEstimate"]},
            "policyIdAtBuy": pol["policyId"],
        }
        print(f"{name}: {b['locationSite']} -> {b['settlementStation']}, {s['rows']} sales days, heat beta "
              f"{e['heat']['beta'] * 100:+.2f}%/F, {cover['peril']} {cover['strikeTenthsF'] / 10:g}F x {cover['units']} units "
              f"{cover['startDay']}..{cover['endDay']}, premium {usd(q['premiumE6'])} for up to {usd(q['maxPayoutE6'])}")

    # 13-RAIN: bought after all three temperature covers, so their policy ids stay pol_000001..3
    m = merchants[RAIN_KEY]
    bid, owner, cover = m["businessId"], m["owner"], m["cover"]
    b = api("GET", f"/businesses/{bid}")
    rrec = api("GET", f"/businesses/{bid}/recommendation?peril=rain")
    rcover = {"peril": "rain", "strikeTenthsF": 0, "capTenthsF": 1, "units": RAIN_UNITS,
              "startDay": cover["startDay"], "endDay": cover["endDay"], "path": "house-hedge"}
    rq = api("POST", "/quotes", {"businessId": bid, **rcover})
    rbuy = api("POST", "/policies", {"quoteId": rq["quoteId"], "holder": owner}, idem=f"seed-demo-{RAIN_KEY}-rain")
    m["rain"] = {
        "recommendation": {k: rrec[k] for k in ("peril", "unitsPerDay", "maxDailyPremiumE6", "rationale")},
        "rainStation": b.get("rainStationId"), "cover": rcover, "overridden": True,
        "quote": {"premiumE6": rq["premiumE6"], "stationLegE6": rq["stationLegE6"], "tailE6": rq["tailE6"],
                  "feesE6": rq["feesE6"], "maxPayoutE6": rq["maxPayoutE6"], "perDayPremiumE6": rq["perDayPremiumE6"],
                  "heEstimate": rq["heEstimate"],
                  "contracts": [{k: r.get(k) for k in ("forDay", "ticker", "qty", "askCents", "source")}
                                for r in rq["stationLeg"]["rungs"]]},
        "policyIdAtBuy": rbuy["result"]["policyId"],
    }
    print(f"{m['name']}: rain cover at {b.get('rainStationName')} ${RAIN_UNITS}/wet day {rcover['startDay']}..{rcover['endDay']} "
          f"(recommended ${rrec['unitsPerDay']}), premium {usd(rq['premiumE6'])} for up to {usd(rq['maxPayoutE6'])}")

    adv1 = api("POST", "/sim/advance", {"days": 1}, admin=True)
    tick = api("POST", "/admin/house-mm/tick", {}, admin=True)
    hm = api("GET", "/admin/house-mm", admin=True)
    aid = f"auc_{AUCTION_CONTRACT}_{AUCTION_DAY}"
    auc = api("GET", f"/auctions/{aid}")
    hq = auc["houseQuote"]
    assert hq, f"no house quote on {aid}"
    print(f"advance 1 day -> {adv1['simTime']} ({len(adv1['events'])} events); house tick posted {tick['quotesPosted']}; "
          f"{len(hm['quotes'])} open house quotes; {aid} house bid {hq['bidE6'] / 1e4:.0f}c ask {hq['askE6'] / 1e4:.0f}c")

    # Two traders cross the house quote from both sides: one lifts the house ask, one hits the house bid.
    buy_px, sell_px = hq["askE6"], hq["bidE6"]
    for addr in (TRADER_BUY, TRADER_SELL):
        api("POST", "/faucet", {"address": addr, "amountE6": 500 * E6})
    api("POST", f"/auctions/{aid}/orders", {"trader": TRADER_BUY, "side": "buy", "qty": TRADE_QTY, "limitPriceE6": buy_px},
        idem="seed-demo-order-buy")
    api("POST", f"/auctions/{aid}/orders", {"trader": TRADER_SELL, "side": "sell", "qty": TRADE_QTY, "limitPriceE6": sell_px},
        idem="seed-demo-order-sell")
    adv2 = api("POST", "/sim/advance", {"days": 2}, admin=True)
    print(f"advance 2 days -> {adv2['simTime']} ({len(adv2['events'])} events)")

    snap = snapshot(api, merchants)
    for key, m in merchants.items():
        snap["merchants"][key]["policyId"] == m["policyIdAtBuy"] or sys.exit(f"{key}: policy id changed")
        if "rain" in m and snap["merchants"][key]["rain"]["policyId"] != m["rain"]["policyIdAtBuy"]:
            sys.exit(f"{key}: rain policy id changed")
    snap["genesis"] = genesis
    snap["houseMmAfterDay1"] = {"quotesOpen": len(hm["quotes"]), "tickQuotesPosted": tick["quotesPosted"],
                                "houseQuoteOnAuction": hq, "traderBuyLimitE6": buy_px, "traderSellLimitE6": sell_px,
                                "tradeQty": TRADE_QTY}
    hm2 = api("GET", "/admin/house-mm", admin=True)
    snap["houseMm"] = {"pnlE6": hm2["pnlE6"], "capsUsed": hm2["capsUsed"], "quotesOpen": len(hm2["quotes"]),
                       "hedges": [{"series": h["series"], "day": h["day"], "costE6": h["costE6"], "payoutE6": h["payoutE6"]}
                                  for h in hm2["hedges"]],
                       "inventory": hm2["inventory"]}
    snap["events"] = {"advance1": adv1["events"], "advance2": adv2["events"]}
    snap["seededAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    snap["origin"] = api.origin
    snap["seedSeconds"] = round(time.time() - t0, 1)
    snap["apiCalls"] = api.calls
    return snap


COMPARE = [("simTime",), ("pool", "juniorAssetsE6"), ("pool", "seniorAssetsE6"), ("auction", "priceE6"),
           ("auction", "filledQty"), ("auction", "status")]


def check(api: Api) -> int:
    want = json.loads(OUT.read_text())
    have = snapshot(api, {k: {kk: v[kk] for kk in ("businessId", "name", "owner")} for k, v in want["merchants"].items()})
    bad = []
    for path in COMPARE:
        a, b = want, have
        for p in path:
            a, b = a[p], b[p]
        if a != b:
            bad.append(f"{'.'.join(path)}: manifest {a!r} world {b!r}")
    for k, m in want["merchants"].items():
        h = have["merchants"][k]
        for f in ("policyId", "premiumE6", "maxPayoutE6", "paidOutE6", "usdcE6", "settlements"):
            if m[f] != h[f]:
                bad.append(f"merchants.{k}.{f}: manifest {m[f]!r} world {h[f]!r}")
        for f in ("policyId", "premiumE6", "maxPayoutE6", "paidOutE6", "settlements"):
            if "rain" in m and m["rain"][f] != (h.get("rain") or {}).get(f):
                bad.append(f"merchants.{k}.rain.{f}: manifest {m['rain'][f]!r} world {(h.get('rain') or {}).get(f)!r}")
    for line in bad:
        print("MISMATCH", line)
    print("check:", "OK, the demo world matches reports/demo/seed-state.json" if not bad else f"{len(bad)} mismatches")
    return 1 if bad else 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--origin", default=os.environ.get("ENGINE_ORIGIN", HOSTED))
    ap.add_argument("--check", action="store_true", help="read-only comparison against the manifest")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    if a.check:
        return check(Api(a.origin, None))
    api = Api(a.origin, admin_token(a.origin))
    snap = seed(api)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n")
    au = snap["auction"]
    print(f"{au['auctionId']}: {au['status']}, price {usd(au['priceE6'])}, filled {au['filledQty']} "
          f"(pool {au['poolFilledQty']}), conservation {au['conservation']}")
    for k, m in snap["merchants"].items():
        print(f"{m['name']}: policy {m['policyId']} {m['policyStatus']}, settled days "
              f"{sum(1 for s in m['settlements'] if s['status'] == 'final')}, paid out {usd(m['paidOutE6'])}, "
              f"wallet {usd(m['usdcE6'])}")
        if "rain" in m:
            r = m["rain"]
            print(f"  rain cover: policy {r['policyId']} {r['policyStatus']}, premium {usd(r['premiumE6'])}, settled days "
                  f"{sum(1 for s in r['settlements'] if s['status'] == 'final')}, paid out {usd(r['paidOutE6'])}")
    print(f"wrote {Path(a.out).relative_to(ROOT) if Path(a.out).is_relative_to(ROOT) else a.out} "
          f"({snap['apiCalls']} API calls, {snap['seedSeconds']} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
