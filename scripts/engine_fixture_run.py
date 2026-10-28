"""Phase 7 engine fixture run: 30 climate days of the NYC metro through wi.engine, written as an artifact.

    uv run python scripts/engine_fixture_run.py                 # run on the committed inputs
    uv run python scripts/engine_fixture_run.py --build-inputs  # rebuild inputs from data/ first (pandas)

Writes reports/engine/fixture-run/{MANIFEST.json, events.jsonl, daily_pnl.csv, world.json} and the parity
vectors under contracts/test/fixtures/. The run is checked while it runs (invariants inside the reducer)
and after it: full replay, replay from the day-15 snapshot, a second independent run, log chain.
Nothing here reads a wall clock into the artifact; two runs give byte-identical files.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wi.engine import parity  # noqa: E402
from wi.engine.log import verify_chain, write_jsonl  # noqa: E402
from wi.engine.reducer import replay, replay_from_snapshot  # noqa: E402
from wi.engine.scenario import run_fixture  # noqa: E402
from wi.engine.state import DEFAULT_PARAMS  # noqa: E402
from wi.engine.units import canonical_json, day_to_iso, sha256_canonical, sha256_hex  # noqa: E402

INPUTS = ROOT / "tests/engine/fixtures/nyc_30d_inputs.json"
OUT = ROOT / "reports/engine/fixture-run"
FIX = ROOT / "contracts/test/fixtures"

WINDOW = ("2026-07-24", "2026-08-22")
PRE_DAYS = 70


# ------------------------------------------------------------------------------------------ inputs
def build_inputs() -> dict:
    """Small, committed input file from data/ (pandas lives only here, never in wi.engine)."""
    import math
    from datetime import date, timedelta
    from decimal import ROUND_HALF_UP, Decimal

    import pandas as pd

    from wi.engine.units import date_to_day, f_to_tenths

    d0, d1 = date.fromisoformat(WINDOW[0]), date.fromisoformat(WINDOW[1])
    days = [(d0 + timedelta(n)).isoformat() for n in range((d1 - d0).days + 1)]
    pre0 = (d0 - timedelta(PRE_DAYS)).isoformat()

    def cents(x):
        if x is None or (isinstance(x, float) and math.isnan(x)):
            return None
        return int((Decimal(repr(float(x))) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))

    def whole(x) -> int:
        if float(x) != int(x):
            raise ValueError(f"non-integer strike {x}")
        return int(x)

    def rows(path: Path, key: str, col: str, lo: str, hi: str):
        raw = path.read_bytes().decode().splitlines()
        hdr = raw[0].split(",")
        ki, ci = hdr.index(key), hdr.index(col)
        out = {}
        for line in raw[1:]:
            f = line.split(",")
            if lo <= f[ki] <= hi and f[ci] not in ("", "M", "None", "nan"):
                out[f[ki]] = (f[ci], "0x" + hashlib.sha256(line.encode()).hexdigest())
        return out

    src = {"NYC": (ROOT / "data/raw/iem/cli/NYC_KNYC_cli.csv", "valid", "high"),
           "LGA": (ROOT / "data/raw/iem/LGA.csv", "day", "max_temp_f"),
           "JFK": (ROOT / "data/raw/iem/JFK.csv", "day", "max_temp_f")}
    cli, vint, pre = {}, {}, {}
    raw = {s: rows(p, k, c, pre0, WINDOW[1]) for s, (p, k, c) in src.items()}
    for s, r in raw.items():
        cli[s] = {str(date_to_day(d)): f_to_tenths(v) for d, (v, _) in r.items() if d >= WINDOW[0]}
        vint[s] = {str(date_to_day(d)): h for d, (_, h) in r.items() if d >= WINDOW[0]}
    for s in ("LGA", "JFK"):
        pre[s] = {str(date_to_day(d)): f_to_tenths(raw[s][d][0]) - f_to_tenths(raw["NYC"][d][0])
                  for d in sorted(raw[s]) if d < WINDOW[0] and d in raw["NYC"]}

    m = pd.read_parquet(ROOT / "data/cache/kalshi/markets.parquet")
    m = m[(m.series_ticker == "KXHIGHNY") & (m.event_date >= WINDOW[0]) & (m.event_date <= WINDOW[1])]
    c = pd.read_parquet(ROOT / "data/cache/kalshi/candles.parquet",
                        columns=["market_ticker", "ts", "yes_ask_close", "yes_bid_close"])
    c = c[c.market_ticker.isin(set(m.market_ticker))]
    ladders = {}
    synth_days = {"2026-08-07", "2026-08-08"}
    for ev_date, g in m.groupby(m.event_date.dt.strftime("%Y-%m-%d")):
        D = date_to_day(ev_date)
        rungs = []
        for _, r in g.sort_values("market_ticker").iterrows():
            close_ts = int(r.close_time.timestamp())
            st_ts = r.settlement_ts
            settle_ts = math.ceil(st_ts.timestamp()) if pd.notna(st_ts) else close_ts + 14 * 3600
            cc = c[(c.market_ticker == r.market_ticker)].sort_values("ts")
            open_ts = int(r.open_time.timestamp())
            candles = [[int(t.timestamp()), cents(a), cents(b)] for t, a, b in
                       zip(cc.ts, cc.yes_ask_close, cc.yes_bid_close) if open_ts <= int(t.timestamp()) <= close_ts]
            rung = {"ticker": r.market_ticker, "strike_type": r.strike_type,
                    "floor_strike": None if pd.isna(r.floor_strike) else whole(r.floor_strike),
                    "cap_strike": None if pd.isna(r.cap_strike) else whole(r.cap_strike),
                    "close_ts": close_ts, "settle_ts": settle_ts, "result": r.result, "candles": candles, "books": []}
            if ev_date in synth_days:
                T = close_ts - 86_400
                last = [x for x in candles if x[0] <= T and x[1] is not None]
                if last and last[-1][1] < 99:
                    a = last[-1][1]
                    lv = [(100 - a - 5, 100), (100 - a - 2, 60), (100 - a - 1, 40), (100 - a, 25)]
                    lv = [(p, q) for p, q in lv if 1 <= p <= 99]
                    book = {"orderbook_fp": {"no_dollars": [[f"{p / 100:.2f}", f"{q:.2f}"] for p, q in lv]}}
                    rung["books"] = [[T - 300, book], [T - 30, book]]
            rungs.append(rung)
        ladders[str(D)] = rungs
    return {
        "meta": {
            "window": list(WINDOW),
            "sources": {
                "NYC": "NWS CLI Central Park via IEM (data/raw/iem/cli/NYC_KNYC_cli.csv, column high)",
                "LGA/JFK": "IEM ASOS daily.py max_temp_f (data/raw/iem/{LGA,JFK}.csv); equals the NWS CLI on 100 % "
                           "of station-days from 2025-10 (docs/CONVENTIONS.md section 8), used as the CLI stand-in",
                "ladders": "KXHIGHNY markets + hourly candles (data/cache/kalshi/{markets,candles}.parquet); "
                           "candle ts = end_period_ts; ask/bid dollars -> cents half away from zero",
                "vintages": "sha256 of the source CSV row (PAIR: sha256 of the two row hashes)",
            },
            "synthetic": "books on 2026-08-07 and 2026-08-08 are SYNTHETIC (built from the last candle ask at "
                         "T = close - 24 h, 4 NO-bid levels) only to exercise the book path; the hl-mm recorder "
                         "has no data yet. Every other input is real.",
            "prehistoryDays": PRE_DAYS,
        },
        "days": days,
        "cli": cli,
        "vintages": vint,
        "prehistory": pre,
        "ladders": ladders,
        "scenario": {
            "outages": [{"site": "LGA", "day": "2026-08-14"}],
            "revisions": [{"site": "LGA", "day": "2026-08-01", "error": 20}],
            "rfqDay": "2026-08-02",
            "params": {},
        },
    }


# ------------------------------------------------------------------------------------------ report
def daily_pnl(lines: list[dict], days: list[int]) -> list[dict]:
    rows = {d: {"day": day_to_iso(d), "premiumToPool": 0, "seniorPremium": 0, "juniorPremium": 0,
                "policyPayouts": 0, "voidRefunds": 0, "hedgeCostE6": 0, "hedgePayoutE6": 0, "hedgeShortfallCenti": 0,
                "houseDeployed": 0, "houseReturned": 0, "housePnl": 0, "juniorPnl": 0, "haircutBps": 0,
                "wiBurned": 0, "policies": 0} for d in days}
    pol_day, pol_market = {}, {}
    mk_day = {}
    for ln in lines:
        t, p = ln["type"], ln["payload"]
        if t == "MarketCreated":
            mk_day[p["marketId"]] = p["day"]
        elif t == "PolicyBought":
            pol_day[p["policyId"]] = mk_day[p["market"]]
            rows[mk_day[p["market"]]]["policies"] += 1
        d = p.get("day", pol_day.get(p.get("policyId")))
        if d not in rows:
            continue
        r = rows[d]
        if t == "PolicyBound":
            r["premiumToPool"] += p["toPool"]
            r["seniorPremium"] += p["seniorPremium"]
            r["juniorPremium"] += p["juniorPremium"]
        elif t == "PolicySettled":
            r["policyPayouts"] += p["payout"]
        elif t == "PolicyVoided":
            r["voidRefunds"] += p["refund"]
        elif t == "HedgeFilled":
            r["hedgeCostE6"] += p["costE6"]
            r["hedgeShortfallCenti"] += p["shortfallCenti"]
        elif t == "HedgeSettled":
            r["hedgePayoutE6"] += p["payoutE6"]
        elif t == "HouseFunded":
            r["houseDeployed"] += p["amount"]
        elif t == "HouseReturned":
            r["houseReturned"] += p["amount"]
            r["housePnl"] += p["pnl"]
        elif t == "DayClosed":
            r["juniorPnl"] = p["juniorPnl"]
            r["haircutBps"] = p["haircutBps"]
        elif t == "WIHaircut":
            r["wiBurned"] = p["burned"]
    return [rows[d] for d in days]


def csv_bytes(rows: list[dict]) -> bytes:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue().encode()


def git_head() -> str:
    """Read the checked-out commit from .git without running git."""
    g = ROOT / ".git"
    try:
        head = (g / "HEAD").read_text().strip()
        if head.startswith("ref: "):
            ref = head[5:]
            p = g / ref
            if p.exists():
                return p.read_text().strip()
            for line in (g / "packed-refs").read_text().splitlines():
                if line.endswith(" " + ref):
                    return line.split()[0]
        return head
    except OSError:
        return "unknown"


def file_entry(path: Path) -> dict:
    b = path.read_bytes()
    return {"path": str(path.relative_to(ROOT)), "bytes": len(b), "sha256": sha256_hex(b)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--build-inputs", action="store_true")
    args = ap.parse_args()
    if args.build_inputs or not INPUTS.exists():
        inp = build_inputs()
        INPUTS.parent.mkdir(parents=True, exist_ok=True)
        INPUTS.write_bytes(canonical_json(inp) + b"\n")
    inputs = json.loads(INPUTS.read_bytes())

    run = run_fixture(inputs, keep_snapshots=True)
    led = run["ledger"]
    final_hash = led.hash()
    lines = led.lines

    # checks after the run
    n_chain = verify_chain(lines)
    full = replay(run["world"], lines)
    snaps = led.snapshots
    k = next(i for i, s in enumerate(snaps) if s["boundaryDay"] >= run["days"][0] + 15)
    tail = replay_from_snapshot(snaps[k], lines)
    again = run_fixture(inputs)["ledger"]
    checks = {
        "logChainLines": n_chain,
        "fullReplayHashEqual": full.hash() == final_hash,
        "snapshotReplay": {"boundaryDay": day_to_iso(snaps[k]["boundaryDay"]), "fromSeq": snaps[k]["seq"],
                           "hashEqual": tail.hash() == final_hash},
        "secondRunHashEqual": again.hash() == final_hash and again.lines[-1] == lines[-1],
    }
    st = led.state
    held = sum(st["bal"].values()) + st["pm"]["escrow"] + sum(st["pm"]["margin"].values()) + st["pool"]["cash"] + \
        sum(m["escrow"] + m["collateral"] for m in st["markets"].values())

    OUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUT / "events.jsonl", lines)
    (OUT / "world.json").write_bytes(canonical_json(run["world"]) + b"\n")
    pnl = daily_pnl(lines, run["days"])
    (OUT / "daily_pnl.csv").write_bytes(csv_bytes(pnl))

    written = parity.write_all(FIX)

    policies = st["policies"].values()
    manifest = {
        "artifact": "wi.engine fixture run (engine demo; not evidence)",
        "spec": file_entry(ROOT / "docs/SPEC.md"),
        "gitHead": git_head(),
        "inputs": [file_entry(INPUTS)],
        "inputsNote": inputs["meta"]["synthetic"],
        "world": file_entry(OUT / "world.json") | {"canonicalSha256": sha256_canonical(run["world"])},
        "paramsSha256": sha256_canonical({k: st["params"].get(k, v) for k, v in sorted(DEFAULT_PARAMS.items())}),
        "params": st["params"],
        "window": inputs["meta"]["window"],
        "eventCount": len(lines),
        "eventCounts": dict(sorted(led.counts.items())),
        "finalStateSha256": final_hash,
        "lastEventHash": sha256_canonical(lines[-1]),
        "snapshots": [{"boundaryDay": day_to_iso(s["boundaryDay"]), "seq": s["seq"], "sha256": s["hash"]}
                      for s in snaps],
        "invariantChecks": dict(sorted(led.checks.items())),
        "invariantFailures": 0,
        "postRunChecks": checks,
        "conservation": {"funded": st["funded"], "held": held, "equal": held == st["funded"],
                         "kalshiNet": st["bal"].get("@kalshi", 0), "treasury": st["bal"].get("@treasury", 0)},
        "pool": {k: st["pool"][k] for k in ("senior", "junior", "reserved", "deployed", "cash", "seniorSupply",
                                             "juniorSupply")},
        "wi": {k: st["wi"][k] for k in ("supply", "burned", "totalStaked", "totalShares")},
        "policies": {"bought": len(st["policies"]),
                     "settled": sum(1 for p in policies if p["status"] == "Settled"),
                     "voided": sum(1 for p in policies if p["status"] == "Voided"),
                     "open": sum(1 for p in policies if p["status"] in ("Bought", "Bound"))},
        "daysClosed": sum(1 for v in st["pool"]["closed"].values() if v),
        "notes": run["notes"],
        "outputs": [file_entry(OUT / "events.jsonl"), file_entry(OUT / "daily_pnl.csv")],
        "parityFixtures": [file_entry(p) | {"cases": n} for p, n in written],
    }
    (OUT / "MANIFEST.json").write_bytes(json.dumps(manifest, indent=1, sort_keys=True).encode() + b"\n")
    ok = all([checks["fullReplayHashEqual"], checks["snapshotReplay"]["hashEqual"], checks["secondRunHashEqual"],
              held == st["funded"], manifest["policies"]["open"] == 0])
    print(json.dumps({"ok": ok, "events": len(lines), "finalStateSha256": final_hash,
                      "policies": manifest["policies"], "daysClosed": manifest["daysClosed"],
                      "checks": checks, "manifest": str((OUT / "MANIFEST.json").relative_to(ROOT))}, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
