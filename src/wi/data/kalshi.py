"""Kalshi keyless history pull: weather series, markets, hourly candlesticks.

Read-only against https://api.elections.kalshi.com/trade-api/v2. No key is ever sent.

Endpoint shapes (learned from prior/hl-mm-ins/reports/ins1/pull_candles.py, then extended):
  GET /series                                         all series (no pagination in practice)
  GET /markets?series_ticker=S&limit=1000&cursor=C    live markets (closed after the historical cutoff)
  GET /historical/markets?series_ticker=S&limit=1000  markets settled before the cutoff
  GET /historical/cutoff                              market_settled_ts: the live/historical boundary
  GET /series/S/markets/T/candlesticks?start_ts&end_ts&period_interval=60          live candles
  GET /historical/markets/T/candlesticks?start_ts&end_ts&period_interval=60        archived candles
Legacy pre-"KX" tickers (HIGHNY-21AUG06-T86) are served under the KX series_ticker in /historical/markets.

All timestamps written to parquet are UTC.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Iterable

import pandas as pd
import requests

BASE = "https://api.elections.kalshi.com/trade-api/v2"
ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "data" / "raw" / "kalshi" / "series"
CACHE = ROOT / "data" / "cache" / "kalshi"
MANIFESTS = ROOT / "data" / "manifests"

MAX_RPS = 5.0
CANDLES_PER_REQUEST = 4500  # API cap is 5000 candles per call
PERIOD = 60

CITIES = ("NY", "EWR", "TTN", "CHI", "MIA")
WEATHER_PREFIXES = ("KXHIGH", "KXLOW", "KXRAIN", "KXSNOW", "HIGH", "LOW", "RAIN", "SNOW")
WEATHER_WORDS = re.compile(r"climate|weather|temperature|\btemp\b|\brain|\bsnow|precip", re.I)
WEATHER_CATEGORIES = re.compile(r"climate|weather", re.I)
CITY_TITLE = [
    ("EWR", re.compile(r"newark|\bEWR\b", re.I)),
    ("TTN", re.compile(r"trenton|\bTTN\b", re.I)),
    ("CHI", re.compile(r"chicago", re.I)),
    ("MIA", re.compile(r"miami", re.I)),
    ("NY", re.compile(r"\bNYC\b|new york|central park", re.I)),
]
# tokens inside the ticker after the weather prefix (KXHIGHTEWR, KXRAINNYCM, KXSNOWCHIM, ...)
CITY_TICKER = [("EWR", "EWR"), ("TTN", "TTN"), ("CHI", "CHI"), ("MIA", "MIA"), ("NY", "NY")]
SETTLED_STATUSES = {"finalized", "settled"}
MONTHS = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}


class NotFound(Exception):
    pass


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def to_ts(s: str) -> int:
    return int(dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


class Client:
    """Keyless GET client: shared <=5 req/s limiter, backoff on 429/5xx/network errors."""

    def __init__(self, max_rps: float = MAX_RPS, log: Callable[[str], None] = print):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "weather-insurance-research/0.1 (read-only public data)"
        self.min_gap = 1.0 / max_rps
        self._lock = threading.Lock()
        self._next = 0.0
        self.log = log
        self.n_requests = 0

    def _wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            t = max(now, self._next)
            self._next = t + self.min_gap
            self.n_requests += 1
        if t > now:
            time.sleep(t - now)

    def get(self, path: str, params: dict | None = None, tries: int = 7) -> dict:
        err: Any = None
        for k in range(tries):
            self._wait()
            try:
                r = self.s.get(BASE + path, params=params, timeout=40)
            except requests.RequestException as e:
                err = e
                time.sleep(min(60, 2 ** (k + 1)))
                continue
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                raise NotFound(path)
            if r.status_code == 429 or r.status_code >= 500:
                err = f"HTTP {r.status_code}"
                ra = r.headers.get("Retry-After")
                time.sleep(float(ra) if ra and ra.replace(".", "").isdigit() else min(60, 2 ** (k + 1)))
                continue
            raise RuntimeError(f"HTTP {r.status_code} {path} {r.text[:200]}")
        raise RuntimeError(f"gave up after {tries} tries: {path} {err}")


# ---------------------------------------------------------------- (a) series discovery

def list_series(c: Client) -> list[dict]:
    out, cur = [], None
    while True:
        d = c.get("/series", {"cursor": cur} if cur else None)
        out += d.get("series", [])
        cur = d.get("cursor")
        if not cur:
            return out


def city_of(series: dict) -> str | None:
    """NY/EWR/TTN/CHI/MIA from the ticker first (Kalshi titles can be wrong: KXMIASNOWM is titled
    "Chicago Snowfall Monthly"), then the title; None if not one of the five."""
    tk = series["ticker"].upper()
    rest = tk
    for p in sorted(WEATHER_PREFIXES, key=len, reverse=True):
        if tk.startswith(p):
            rest = tk[len(p):]
            break
    for city, token in CITY_TICKER:
        if token in rest:
            return city
    title = series.get("title") or ""
    for city, rx in CITY_TITLE:
        if rx.search(title):
            return city
    return None


def is_weather(series: dict) -> bool:
    tk = series["ticker"].upper()
    cat = series.get("category") or ""
    hay = " ".join([cat, series.get("title") or "", *(series.get("tags") or []), *(series.get("categories") or [])])
    if WEATHER_CATEGORIES.search(cat) or WEATHER_WORDS.search(hay):
        return True
    # prefix match only counts when the category is not clearly something else
    return tk.startswith(WEATHER_PREFIXES) and cat in ("", "World", "Climate and Weather")


def weather_series(all_series: Iterable[dict]) -> list[dict]:
    out = []
    for s in all_series:
        if is_weather(s):
            s = dict(s)
            s["city"] = city_of(s)
            out.append(s)
    return out


# ---------------------------------------------------------------- (b) markets

def historical_cutoff(c: Client) -> dt.datetime:
    d = c.get("/historical/cutoff")
    return dt.datetime.fromisoformat(d["market_settled_ts"].replace("Z", "+00:00"))


def _paged(c: Client, path: str, params: dict) -> list[dict]:
    out, cur = [], None
    while True:
        p = dict(params, limit=1000)
        if cur:
            p["cursor"] = cur
        d = c.get(path, p)
        out += d.get("markets", [])
        cur = d.get("cursor")
        if not cur or not d.get("markets"):
            return out


def list_markets(c: Client, series: str) -> list[dict]:
    """All markets of a series, every status, live + archived, de-duplicated by ticker."""
    live = _paged(c, "/markets", {"series_ticker": series})
    hist = _paged(c, "/historical/markets", {"series_ticker": series})
    by: dict[str, dict] = {}
    for src, ms in (("historical", hist), ("live", live)):  # live overwrites: fresher
        for m in ms:
            m = dict(m)
            m["_source"] = src
            by[m["ticker"]] = m
    return sorted(by.values(), key=lambda m: (m.get("close_time") or "", m["ticker"]))


def is_settled(m: dict) -> bool:
    return m.get("status") in SETTLED_STATUSES or m.get("result") in ("yes", "no", "scalar")


# ---------------------------------------------------------------- (c) candles

def fetch_candles(c: Client, series: str, m: dict, cutoff: dt.datetime, now: dt.datetime | None = None) -> dict:
    """Hourly candles over the market's whole life. Returns the raw-file dict."""
    now = now or utcnow()
    t0 = to_ts(m["open_time"])
    t1 = min(to_ts(m["close_time"]), int(now.timestamp())) + 3600
    pre_cutoff = to_ts(m["close_time"]) < cutoff.timestamp()
    routes = ["hist", "live"] if pre_cutoff else ["live", "hist"]
    last_err = None
    for route in routes:
        candles: list[dict] = []
        try:
            a = t0
            while a < t1:
                b = min(a + CANDLES_PER_REQUEST * PERIOD * 60, t1)
                path = (
                    f"/historical/markets/{m['ticker']}/candlesticks"
                    if route == "hist"
                    else f"/series/{series}/markets/{m['ticker']}/candlesticks"
                )
                d = c.get(path, {"start_ts": a, "end_ts": b, "period_interval": PERIOD})
                candles += d.get("candlesticks", [])
                a = b
            return {
                "ticker": m["ticker"], "series_ticker": series, "route": route,
                "start_ts": t0, "end_ts": t1, "period_interval": PERIOD,
                "pulled_at": utcnow().isoformat(), "candlesticks": candles,
            }
        except NotFound as e:
            last_err = e
    return {
        "ticker": m["ticker"], "series_ticker": series, "route": None, "start_ts": t0, "end_ts": t1,
        "period_interval": PERIOD, "pulled_at": utcnow().isoformat(), "candlesticks": [],
        "error": f"404 on both live and historical candle routes ({last_err})",
    }


# ---------------------------------------------------------------- (d) raw on disk

def series_dir(series: str) -> Path:
    return RAW / series


def write_json(path: Path, obj: Any, enospc_wait_s: int = 900) -> None:
    """Atomic write; on a full disk wait and retry (the laptop disk runs near-full) instead of dying."""
    import errno
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    payload = json.dumps(obj, separators=(",", ":"))
    deadline = time.time() + enospc_wait_s
    while True:
        try:
            tmp.write_text(payload)
            tmp.replace(path)
            return
        except OSError as e:
            tmp.unlink(missing_ok=True)
            if e.errno != errno.ENOSPC or time.time() > deadline:
                raise
            time.sleep(15)


def pull_series(
    c: Client, series: str, cutoff: dt.datetime, workers: int = 4, limit: int | None = None,
    log: Callable[[str], None] = print,
) -> dict:
    """Markets + candles for one series, resume-safe. Returns a pull-log summary."""
    t_start = time.time()
    d = series_dir(series)
    ms = list_markets(c, series)
    if limit:
        ms = ms[:limit]
    write_json(d / "markets.json", {"series_ticker": series, "pulled_at": utcnow().isoformat(), "markets": ms})
    todo, skipped = [], 0
    for m in ms:
        f = d / f"{m['ticker']}.candles.json"
        if f.exists() and is_settled(m):
            skipped += 1
        else:
            todo.append(m)
    log(f"{series}: {len(ms)} markets, {skipped} skipped (settled + file exists), {len(todo)} to pull")
    errors: list[str] = []
    done = [0]

    def work(m: dict) -> None:
        try:
            out = fetch_candles(c, series, m, cutoff)
        except Exception as e:  # recorded, market retried next run (no file written)
            errors.append(f"{m['ticker']}: {e}")
            return
        if out.get("error"):
            errors.append(f"{m['ticker']}: {out['error']}")
        write_json(d / f"{m['ticker']}.candles.json", out)
        done[0] += 1
        if done[0] % 500 == 0:
            log(f"{series}: {done[0]}/{len(todo)} candles done, {c.n_requests} requests, {time.time()-t_start:.0f}s")

    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(work, todo))
    summary = {
        "series_ticker": series, "pulled_at": utcnow().isoformat(), "markets": len(ms),
        "skipped": skipped, "pulled": done[0], "errors": errors, "seconds": round(time.time() - t_start, 1),
    }
    prev = []
    lf = d / "pull-log.json"
    if lf.exists():
        prev = json.loads(lf.read_text()).get("runs", [])
    write_json(lf, {"runs": prev + [summary]})
    log(f"{series}: done in {summary['seconds']}s, {len(errors)} errors")
    return summary


# ---------------------------------------------------------------- (e) consolidation

def _num(x: Any) -> float | None:
    if x is None or x == "":
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _event_date(event_ticker: str) -> dt.date | None:
    mt = re.search(r"-(\d{2})([A-Z]{3})(\d{2})?(?:-|$)", event_ticker)
    if not mt:
        return None
    yy, mon, dd = mt.groups()
    if mon not in MONTHS:
        return None
    try:
        return dt.date(2000 + int(yy), MONTHS[mon], int(dd) if dd else 1)
    except ValueError:
        return None


def strikes_from_ticker(tk: str, subtitle: str | None) -> tuple[str | None, float | None, float | None]:
    """Legacy (pre-2022/pre-2025) temperature markets carry no floor/cap fields. Rebuild them with the
    modern convention: T<n> 'greater' -> floor=n (strictly above); T<n> 'less' -> cap=n (strictly below);
    B<x.5> -> floor=x, cap=x+1 (inclusive two-degree bracket)."""
    mt = re.search(r"-([TB])(-?\d+(?:\.\d+)?)$", tk)
    if not mt:
        return None, None, None
    kind, n = mt.group(1), float(mt.group(2))
    sub = (subtitle or "").lower()
    rng = re.match(r"^(\d+)\D+(\d+)", sub)
    if rng and float(rng.group(2)) < float(rng.group(1)):
        rng = None
    if kind == "B" or rng:  # the odd T83.5 tickers carry a "83-84" bracket subtitle
        if rng:
            return "between", float(rng.group(1)), float(rng.group(2))
        return "between", n - 0.5, n + 0.5
    if sub.startswith(">") or "higher" in sub or "above" in sub:
        return "greater", n, None
    if sub.startswith("<") or "lower" in sub or "below" in sub:
        return "less", None, n
    return None, None, None


def market_rows(series: str, city: str | None, markets: list[dict]) -> list[dict]:
    rows = []
    for m in markets:
        tk = m["ticker"]
        st, fl, cp = m.get("strike_type"), _num(m.get("floor_strike")), _num(m.get("cap_strike"))
        strike_source = "api" if (fl is not None or cp is not None) else None
        if strike_source is None and re.match(r"(KX)?(HIGH|LOW)", series):  # temperature ladders only
            st2, fl, cp = strikes_from_ticker(tk, m.get("subtitle") or m.get("yes_sub_title"))
            if st2:
                st, strike_source = st2, "ticker"
        rows.append({
            "series_ticker": series,
            "event_ticker": m.get("event_ticker"),
            "market_ticker": tk,
            "legacy_prefix": not tk.startswith("KX"),
            "city": city,
            "event_date": _event_date(m.get("event_ticker") or ""),
            "title": m.get("title"),
            "subtitle": m.get("subtitle") or m.get("yes_sub_title"),
            "strike_type": st,
            "floor_strike": fl,
            "cap_strike": cp,
            "strike_source": strike_source,
            "status": m.get("status"),
            "result": m.get("result"),
            "settled": is_settled(m),
            "open_time": m.get("open_time"),
            "close_time": m.get("close_time"),
            "expiration_time": m.get("expiration_time"),
            "expected_expiration_time": m.get("expected_expiration_time"),
            "settlement_ts": m.get("settlement_ts"),
            "occurrence_datetime": m.get("occurrence_datetime"),
            "expiration_value": m.get("expiration_value"),
            "settlement_value": _num(m.get("settlement_value_dollars", m.get("settlement_value"))),
            "volume": _num(m.get("volume_fp", m.get("volume"))),
            "open_interest": _num(m.get("open_interest_fp", m.get("open_interest"))),
            "last_price": _num(m.get("last_price_dollars", m.get("last_price"))),
            "source": m.get("_source"),
            "rules_primary": m.get("rules_primary"),
        })
    return rows


def _pick(d: dict | None, k: str) -> float | None:
    """Candle price dicts use 'close_dollars' (live) or 'close' (historical)."""
    if not d:
        return None
    v = d.get(k + "_dollars", d.get(k))
    return _num(v)


def candle_rows(series: str, city: str | None, event: str | None, raw: dict) -> list[dict]:
    rows = []
    for k in raw.get("candlesticks", []):
        p, a, b = k.get("price") or {}, k.get("yes_ask") or {}, k.get("yes_bid") or {}
        row = {
            "series_ticker": series, "event_ticker": event, "market_ticker": raw["ticker"], "city": city,
            "end_period_ts": k["end_period_ts"],
            "volume": _num(k.get("volume_fp", k.get("volume"))),
            "open_interest": _num(k.get("open_interest_fp", k.get("open_interest"))),
        }
        for nm, dd in (("price", p), ("yes_ask", a), ("yes_bid", b)):
            for f in ("open", "high", "low", "close"):
                row[f"{nm}_{f}"] = _pick(dd, f)
        row["price_mean"] = _pick(p, "mean")
        row["price_previous"] = _pick(p, "previous")
        rows.append(row)
    return rows


def consolidate(series_city: dict[str, str | None], log: Callable[[str], None] = print) -> dict:
    """Rebuild data/cache/kalshi/{markets,candles}.parquet from raw JSON for the given series."""
    CACHE.mkdir(parents=True, exist_ok=True)
    mrows: list[dict] = []
    crows: list[dict] = []
    stats: dict[str, dict] = {}
    for series, city in series_city.items():
        d = series_dir(series)
        mf = d / "markets.json"
        if not mf.exists():
            continue
        markets = json.loads(mf.read_text())["markets"]
        mrows += market_rows(series, city, markets)
        ev = {m["ticker"]: m.get("event_ticker") for m in markets}
        n = 0
        for m in markets:
            f = d / f"{m['ticker']}.candles.json"
            if not f.exists():
                continue
            rr = candle_rows(series, city, ev.get(m["ticker"]), json.loads(f.read_text()))
            n += len(rr)
            crows += rr
        stats[series] = {"candle_rows": n}
        log(f"consolidate {series}: {len(markets)} markets, {n} candle rows")
    mdf = pd.DataFrame(mrows)
    for col in ("open_time", "close_time", "expiration_time", "expected_expiration_time", "settlement_ts", "occurrence_datetime"):
        mdf[col] = pd.to_datetime(mdf[col], utc=True, format="ISO8601")
    mdf["event_date"] = pd.to_datetime(mdf["event_date"])
    cdf = pd.DataFrame(crows)
    cdf["ts"] = pd.to_datetime(cdf["end_period_ts"], unit="s", utc=True)
    cdf = cdf.drop(columns=["end_period_ts"])
    cols = ["series_ticker", "event_ticker", "market_ticker", "city", "ts"]
    cdf = cdf[cols + [x for x in cdf.columns if x not in cols]]
    mdf.to_parquet(CACHE / "markets.parquet", index=False)
    cdf.to_parquet(CACHE / "candles.parquet", index=False)
    log(f"wrote {CACHE/'markets.parquet'} ({len(mdf)} rows) and {CACHE/'candles.parquet'} ({len(cdf)} rows)")
    return {"markets": len(mdf), "candles": len(cdf), "per_series": stats}
