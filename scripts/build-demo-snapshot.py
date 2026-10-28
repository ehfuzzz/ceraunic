"""Build the demo snapshot the engine API ships with (data/demo/*.json.gz). pandas lives here only.

    uv run python scripts/build-demo-snapshot.py

Window: climate days 2026-07-15..2026-09-28 (the sim world's replay calendar), plus 90 days of
index prehistory before it (residual fair value needs 60 finalised basis days before the first
quoted day) and the settlement-station weather since 2023-01-01 (the elasticity estimator's
regressors; the API filters them to days before the simulated day).

Files (all ints for money/temperature, UTC epoch seconds for timestamps):
  ladders.json.gz   {series: {YYYY-MM-DD: [rung, ...]}}  engine rung format (wi.engine.hedge docstring):
                    ticker, strike_type, floor_strike, cap_strike, close_ts, settle_ts, result,
                    candles [[end_ts, ask_cents|null, bid_cents|null]] from open to close, books []
  cli.json.gz       {site: {YYYY-MM-DD: [tenths_F, vintageHash]}}   daily max per location site
  weather.json.gz   {station: [[YYYY-MM-DD, tmax_f, prcp_in, snow_in|null], ...]}  NWS CLI rows
  books_ins1.json.gz  hl-mm ins1 recorded books for weather tickers (reference only: they were
                    recorded 2026-09-29, outside the replay window, and are NOT used for fills)
  priors.json       copy of reports/eval-06/priors.json (the Phase 5 estimator's priors)
  he.json           EVAL-06 group medians HE_cover / HE_ladder (arm A3, daily, heat+rain)
  rain.json.gz      rain cover (13-RAIN): {"ladders": {KXRAIN-<CITY>: {YYYY-MM-DD: [one "> 0 in" rung]}},
                    "precip": {site: {YYYY-MM-DD: [hundredths_in, trace 0|1, vintageHash]}} for the three Kalshi
                    rain stations (CLINYC, CLIORD, CLIMIA), "he": EVAL-01 wet-day HE}. Added as a separate file so the
                    temperature files above stay byte-identical.
  MANIFEST.json     window, sources, row counts, sha256 of every file
Two runs give byte-identical files (gzip mtime 0, sorted keys).
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/demo"
WINDOW = ("2026-07-15", "2026-09-28")
PRE_DAYS = 90
WEATHER_FROM = "2023-01-01"
SERIES = {"KXHIGHNY": "NYC", "KXHIGHCHI": "MDW", "KXHIGHMIA": "MIA"}

# location site -> (source file, date column, value column, source label)
CLI_SITES = {"NYC": "NYC_KNYC", "EWR": "EWR_KEWR", "TTN": "TTN_KTTN", "MDW": "MDW_KMDW", "MIA": "MIA_KMIA"}
IEM_SITES = ("LGA", "JFK", "ORD", "FLL", "OPF")
# rain (13-RAIN): Kalshi KXRAIN city suffix -> (engine series key, CLI precip site, NWS CLI csv). KXRAIN settles on
# CLINYC / CLIORD / CLIMIA ("total precipitation ... strictly greater than 0 inches", rules_primary in the cache).
# ORD's CLI comes from the Phase 3 top-up pull (data/cache/eval03/cli), the other two from the Phase 1 CLI files.
RAIN = {"NY": ("KXRAIN-NYC", "NYC", "data/raw/iem/cli/NYC_KNYC_cli.csv"),
        "CHI": ("KXRAIN-CHI", "ORD", "data/cache/eval03/cli/ORD_2026.csv"),
        "MIA": ("KXRAIN-MIA", "MIA", "data/raw/iem/cli/MIA_KMIA_cli.csv")}


def cents(x) -> int | None:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    return int((Decimal(repr(float(x))) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def tenths(v: str) -> int:
    return int((Decimal(v) * 10).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def whole(x) -> int | None:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    if float(x) != int(x):
        raise ValueError(f"non-integer strike {x}")
    return int(x)


def csv_rows(path: Path, key: str, col: str, lo: str, hi: str) -> dict[str, tuple[str, str]]:
    raw = path.read_text().splitlines()
    hdr = raw[0].split(",")
    ki, ci = hdr.index(key), hdr.index(col)
    out = {}
    for line in raw[1:]:
        f = line.split(",")
        if lo <= f[ki] <= hi and f[ci] not in ("", "M", "None", "nan"):
            out[f[ki]] = (f[ci], "0x" + hashlib.sha256(line.encode()).hexdigest())
    return out


def build_cli() -> dict:
    lo = (date.fromisoformat(WINDOW[0]) - timedelta(PRE_DAYS)).isoformat()
    out = {}
    for site, stem in CLI_SITES.items():
        r = csv_rows(ROOT / f"data/raw/iem/cli/{stem}_cli.csv", "valid", "high", lo, WINDOW[1])
        out[site] = {d: [tenths(v), h] for d, (v, h) in sorted(r.items())}
    for site in IEM_SITES:
        r = csv_rows(ROOT / f"data/raw/iem/{site}.csv", "day", "max_temp_f", lo, WINDOW[1])
        out[site] = {d: [tenths(v), h] for d, (v, h) in sorted(r.items())}
    return out


def build_weather() -> dict:
    def num(v: str) -> float | None:
        if v in ("", "M", "None"):
            return None
        return 0.0 if v == "T" else float(v)

    out = {}
    for site, stem in CLI_SITES.items():
        raw = (ROOT / f"data/raw/iem/cli/{stem}_cli.csv").read_text().splitlines()
        hdr = raw[0].split(",")
        iv, ih, ip, isn = hdr.index("valid"), hdr.index("high"), hdr.index("precip"), hdr.index("snow")
        rows = []
        for line in raw[1:]:
            f = line.split(",")
            if not (WEATHER_FROM <= f[iv] <= WINDOW[1]):
                continue
            t, p = num(f[ih]), num(f[ip])
            if t is None or p is None:
                continue
            rows.append([f[iv], t, p, num(f[isn])])
        out[site] = sorted(rows)
    return out


def build_ladders() -> dict:
    m = pd.read_parquet(ROOT / "data/cache/kalshi/markets.parquet")
    m = m[m.series_ticker.isin(list(SERIES)) & (m.event_date >= WINDOW[0]) & (m.event_date <= WINDOW[1])]
    c = pd.read_parquet(ROOT / "data/cache/kalshi/candles.parquet",
                        columns=["market_ticker", "ts", "yes_ask_close", "yes_bid_close"])
    c = c[c.market_ticker.isin(set(m.market_ticker))].sort_values(["market_ticker", "ts"])
    by_ticker = {t: g for t, g in c.groupby("market_ticker")}
    out: dict[str, dict] = {s: {} for s in SERIES}
    for (series, ev), g in m.groupby([m.series_ticker, m.event_date.dt.strftime("%Y-%m-%d")]):
        rungs = []
        for _, r in g.sort_values("market_ticker").iterrows():
            close_ts = int(r.close_time.timestamp())
            open_ts = int(r.open_time.timestamp())
            st_ts = r.settlement_ts
            settle_ts = math.ceil(st_ts.timestamp()) if pd.notna(st_ts) else close_ts + 14 * 3600
            cc = by_ticker.get(r.market_ticker)
            candles = [] if cc is None else [
                [int(t.timestamp()), cents(a), cents(b)]
                for t, a, b in zip(cc.ts, cc.yes_ask_close, cc.yes_bid_close)
                if open_ts <= int(t.timestamp()) <= close_ts]
            rungs.append({"ticker": r.market_ticker, "strike_type": r.strike_type,
                          "floor_strike": whole(r.floor_strike), "cap_strike": whole(r.cap_strike),
                          "close_ts": close_ts, "settle_ts": settle_ts, "result": r.result,
                          "candles": candles, "books": []})
        out[series][ev] = rungs
    return out


def hundredths(v: str) -> int:
    return int((Decimal(v) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def build_rain() -> dict:
    """KXRAIN daily "> 0 in" binaries for NYC/CHI/MIA (one rung per day, engine rung format) plus the CLI daily
    precipitation at each settlement station, trace kept as a flag (the engine decides what a trace pays)."""
    m = pd.read_parquet(ROOT / "data/cache/kalshi/kxrain_markets.parquet")
    m = m.assign(day=pd.to_datetime(m.event_date).dt.strftime("%Y-%m-%d"))
    m = m[m.city.isin(list(RAIN)) & (m.day >= WINDOW[0]) & (m.day <= WINDOW[1])]
    c = pd.read_parquet(ROOT / "data/cache/kalshi/kxrain_candles.parquet",
                        columns=["market_ticker", "ts", "yes_ask_close", "yes_bid_close"])
    c = c[c.market_ticker.isin(set(m.market_ticker))].sort_values(["market_ticker", "ts"])
    by_ticker = {t: g for t, g in c.groupby("market_ticker")}
    ladders: dict[str, dict] = {v[0]: {} for v in RAIN.values()}
    for _, r in m.sort_values("market_ticker").iterrows():
        if r.strike_type != "greater" or float(r.floor_strike) != 0.0:
            raise ValueError(f"unexpected rain strike {r.market_ticker}")
        close_ts, open_ts = int(r.close_time.timestamp()), int(r.open_time.timestamp())
        st_ts = r.settlement_ts
        settle_ts = math.ceil(st_ts.timestamp()) if pd.notna(st_ts) else close_ts + 14 * 3600
        cc = by_ticker.get(r.market_ticker)
        candles = [] if cc is None else [
            [int(t.timestamp()), cents(a), cents(b)]
            for t, a, b in zip(cc.ts, cc.yes_ask_close, cc.yes_bid_close) if open_ts <= int(t.timestamp()) <= close_ts]
        ladders[RAIN[r.city][0]][r.day] = [{
            "ticker": r.market_ticker, "strike_type": "greater", "floor_strike": 0, "cap_strike": None,
            "close_ts": close_ts, "settle_ts": settle_ts, "result": r.result, "candles": candles, "books": []}]
    lo = (date.fromisoformat(WINDOW[0]) - timedelta(PRE_DAYS)).isoformat()
    precip = {}
    for _, site, path in RAIN.values():
        raw = (ROOT / path).read_text().splitlines()
        hdr = raw[0].split(",")
        iv, ip = hdr.index("valid"), hdr.index("precip")
        rows = {}
        for line in raw[1:]:
            f = line.split(",")
            if not (lo <= f[iv] <= WINDOW[1]) or f[ip] in ("", "M", "None"):
                continue  # a missing day stays missing: the index-day voids (SPEC 9.4)
            h = "0x" + hashlib.sha256(line.encode()).hexdigest()
            rows[f[iv]] = [0, 1, h] if f[ip] == "T" else [hundredths(f[ip]), 0, h]
        precip[site] = dict(sorted(rows.items()))
    r = json.loads((ROOT / "reports/eval-01/results.json").read_text())["rain_daily"]["horizons"]["24"]
    he = {"heCover": round(r["he_wet"]["he_cover"]["est"], 4), "heLadder": round(r["he_wet"]["he_ladder"]["est"], 4),
          "costPerDollarPayout24h": round(r["cost_per_dollar_payout"], 4),
          "source": "reports/eval-01/results.json rain_daily.horizons.24 (wet-day HE, 2023+, trace counted wet there)"}
    return {"ladders": ladders, "precip": precip, "he": he}


def build_books() -> dict:
    books = json.loads((ROOT / "prior/hl-mm-ins/reports/ins1/books.json").read_text())
    return {k: v for k, v in sorted(books.items()) if k.startswith("KXHIGH")}


def build_he() -> dict:
    r = json.loads((ROOT / "reports/eval-06/results.json").read_text())
    out = {}
    for gid, g in sorted(r["groups"].items()):
        a3 = g["primary"]["arms"]["A3"]
        out[gid] = {"heCover": round(a3["cover_heat_rain_daily"]["median"], 4),
                    "heLadder": round(a3["ladder_heat_rain_daily"]["median"], 4),
                    "heCoverHeatOnly": round(a3["cover_heat_daily"]["median"], 4),
                    "heLadderHeatOnly": round(a3["ladder_heat_daily"]["median"], 4)}
    return {"source": "reports/eval-06/results.json, primary split, arm A3 (credibility-shrunk), daily medians; "
                      "heat+rain unless named HeatOnly. Chicago groups: HE_ladder is heat leg only.",
            "groups": out}


def dump_gz(name: str, obj) -> bytes:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    data = gzip.compress(raw, compresslevel=9, mtime=0)
    (OUT / name).write_bytes(data)
    return data


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    files = {}
    cli = build_cli()
    files["cli.json.gz"] = dump_gz("cli.json.gz", cli)
    weather = build_weather()
    files["weather.json.gz"] = dump_gz("weather.json.gz", weather)
    ladders = build_ladders()
    files["ladders.json.gz"] = dump_gz("ladders.json.gz", ladders)
    books = build_books()
    files["books_ins1.json.gz"] = dump_gz("books_ins1.json.gz", books)
    pri = (ROOT / "reports/eval-06/priors.json").read_bytes()
    (OUT / "priors.json").write_bytes(pri)
    files["priors.json"] = pri
    rain = build_rain()
    files["rain.json.gz"] = dump_gz("rain.json.gz", rain)
    he = json.dumps(build_he(), sort_keys=True, indent=1).encode() + b"\n"
    (OUT / "he.json").write_bytes(he)
    files["he.json"] = he
    manifest = {
        "window": list(WINDOW), "prehistoryDays": PRE_DAYS, "weatherFrom": WEATHER_FROM,
        "sources": {
            "cli": "NWS CLI via IEM (data/raw/iem/cli/*_cli.csv, column high) for NYC/EWR/TTN/MDW/MIA; IEM ASOS "
                   "daily.py max_temp_f (data/raw/iem/{LGA,JFK,ORD,FLL,OPF}.csv) as the CLI stand-in for the other "
                   "location sites (docs/CONVENTIONS.md section 8). vintageHash = sha256 of the source CSV row.",
            "weather": "NWS CLI via IEM: high (F), precip (in, T = 0), snow (in, T = 0, M = null)",
            "ladders": "Kalshi KXHIGHNY/KXHIGHCHI/KXHIGHMIA markets + hourly candles (data/cache/kalshi/"
                       "{markets,candles}.parquet); candle ts = end_period_ts; ask/bid dollars -> cents half up. "
                       "No recorded books in the window: hedge fills use the candle rule (SPEC 7.2).",
            "books_ins1": "prior/hl-mm-ins/reports/ins1/books.json (2026-09-29 snapshot), reference only",
            "priors": "reports/eval-06/priors.json", "he": "reports/eval-06/results.json",
            "rain": "Kalshi KXRAIN daily '> 0 in' binaries for NYC/CHI/MIA (data/cache/kalshi/kxrain_{markets,candles}"
                    ".parquet, scripts/pull_kxrain.py) + NWS CLI daily precip at CLINYC/CLIORD/CLIMIA (data/raw/iem/cli, "
                    "data/cache/eval03/cli/ORD_2026.csv); trace kept as a flag; vintageHash = sha256 of the CSV row.",
        },
        "counts": {"cliSites": {s: len(v) for s, v in cli.items()},
                   "weatherRows": {s: len(v) for s, v in weather.items()},
                   "ladderDays": {s: len(v) for s, v in ladders.items()},
                   "rungs": sum(len(r) for v in ladders.values() for r in v.values()),
                   "candles": sum(len(x["candles"]) for v in ladders.values() for r in v.values() for x in r),
                   "books": len(books),
                   "rainLadderDays": {k: len(v) for k, v in rain["ladders"].items()},
                   "rainPrecipDays": {k: len(v) for k, v in rain["precip"].items()}},
        "sha256": {k: hashlib.sha256(v).hexdigest() for k, v in sorted(files.items())},
        "bytes": {k: len(v) for k, v in sorted(files.items())},
    }
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, sort_keys=True, indent=1) + "\n")
    print(json.dumps({"counts": manifest["counts"], "bytes": manifest["bytes"]}, indent=1))


if __name__ == "__main__":
    main()
