"""Demo snapshot data (data/demo/*.json.gz, built by scripts/build-demo-snapshot.py). Read-only, cached.

Point-in-time is enforced here as well as in the engine (09-RESEARCH Pitfall 13): an index value for
climate day D is handed out only at or after its fetch time (D+1 12:00Z for CLI indices), and
prehistory rows carry their finalisation time so `pricing.basis_history` can filter them by the quote
time. Ladder candles are filtered by the engine (`hedge.candle_at` never reads a candle after t).
No pandas here; json + gzip only.
"""
from __future__ import annotations

import gzip
import json
import os
from functools import lru_cache
from pathlib import Path

from wi.engine.units import DAY_S, date_to_day, day_to_iso


class LookAheadError(AssertionError):
    """A snapshot read asked for data that did not exist yet at the given time."""


def _data_dir() -> Path:
    env = os.environ.get("WI_DEMO_DATA")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for cand in (here.parents[3] / "data" / "demo", here.parents[2] / "demo-data", here.parents[1] / "demo-data"):
        if (cand / "ladders.json.gz").exists():
            return cand
    raise FileNotFoundError("demo snapshot not found (data/demo or demo-data next to the bundle)")


def _load(name: str):
    p = _data_dir() / name
    raw = p.read_bytes()
    if name.endswith(".gz"):
        raw = gzip.decompress(raw)
    return json.loads(raw)


@lru_cache(maxsize=1)
def ladders() -> dict:
    return _load("ladders.json.gz")


@lru_cache(maxsize=1)
def cli() -> dict:
    return _load("cli.json.gz")


@lru_cache(maxsize=1)
def weather() -> dict:
    return _load("weather.json.gz")


@lru_cache(maxsize=1)
def priors() -> dict:
    return _load("priors.json")


@lru_cache(maxsize=1)
def he() -> dict:
    return _load("he.json")


@lru_cache(maxsize=1)
def manifest() -> dict:
    return _load("MANIFEST.json")


@lru_cache(maxsize=1)
def rain() -> dict:
    """KXRAIN binaries + CLI precip at the Kalshi rain stations (13-RAIN; scripts/build-demo-snapshot.py)."""
    try:
        return _load("rain.json.gz")
    except FileNotFoundError:
        return {"ladders": {}, "precip": {}, "he": {}}


# Trace rule for rain cover (13-RAIN trace flip, seat ruling 2026-09-30): the cover pays on measurable rain only, CLI
# daily precipitation >= 0.01 in; a trace ("T") is a dry day (SPEC 1: T = 0). That is Kalshi's KXRAIN rule: on the
# settled KXRAIN days in the cache (2026-07-15..09-29) all 26 trace days at CLINYC/CLIORD/CLIMIA settled NO, all 94 measurable
# days YES, all 96 dry days NO (reports/eval-01/trace_kxrain_2026.json). So the cover and the Kalshi leg settle the
# same way. The trace flag stays in data/demo/rain.json.gz so the evidence stays checkable.
TRACE_IS_WET = False


def window() -> tuple[str, str]:
    w = manifest()["window"]
    return w[0], w[1]


def ladder(series: str, day: int) -> list[dict] | None:
    return ladders().get(series, {}).get(day_to_iso(day))


CLI_FETCH_LAG = 12 * 3600


def cli_value(site: str, day: int, as_of: int) -> tuple[int, str] | None:
    """(tenths F, vintage hash) of the site's daily max for climate day `day`, read at `as_of`.

    Refuses a read before the fetch time D+1 12:00Z (no look-ahead)."""
    if as_of < (day + 1) * DAY_S + CLI_FETCH_LAG:
        raise LookAheadError(f"CLI {site} {day_to_iso(day)} read at {as_of}, before its fetch time")
    v = cli().get(site, {}).get(day_to_iso(day))
    return None if v is None else (int(v[0]), str(v[1]))


def rain_ladder(series: str, day: int) -> list[dict] | None:
    return rain()["ladders"].get(series, {}).get(day_to_iso(day))


def _wet(v: list) -> int:
    """[hundredths, trace, vintage] -> wet-day indicator (1 wet, 0 dry)."""
    return 1 if int(v[0]) >= 1 or (v[1] and TRACE_IS_WET) else 0


def wet_value(site: str, day: int, as_of: int) -> tuple[int, str] | None:
    """(wet indicator 0|1, vintage hash) of the site's CLI daily precipitation for climate day `day`, read at `as_of`.
    Refuses a read before the fetch time D+1 12:00Z (no look-ahead)."""
    if as_of < (day + 1) * DAY_S + CLI_FETCH_LAG:
        raise LookAheadError(f"CLI precip {site} {day_to_iso(day)} read at {as_of}, before its fetch time")
    v = rain()["precip"].get(site, {}).get(day_to_iso(day))
    return None if v is None else (_wet(v), str(v[2]))


def rain_prehistory(site: str, before_day: int) -> list[list[int]]:
    """[day, wet 0|1, finalizedTs] for days < before_day (CLI final D+2 12:00Z): the wet-day history the house prices
    days without an open Kalshi market from (pricing.price_rain_policy)."""
    out = []
    for d_iso, v in rain()["precip"].get(site, {}).items():
        d = date_to_day(d_iso)
        if d < before_day:
            out.append([d, _wet(v), (d + 2) * DAY_S + 12 * 3600])
    return sorted(out)


def pair_prehistory(site: str, station: str, before_day: int) -> list[list[int]]:
    """[day, basis tenths, finalizedTs] for days < before_day where both sites report (CLI final D+2 12:00Z)."""
    a, s = cli().get(site, {}), cli().get(station, {})
    out = []
    for d_iso, (va, _) in a.items():
        d = date_to_day(d_iso)
        if d < before_day and d_iso in s:
            out.append([d, int(va) - int(s[d_iso][0]), (d + 2) * DAY_S + 12 * 3600])
    return sorted(out)


def weather_rows(station: str, before_day: int) -> list[dict]:
    """Settlement-station weather rows for the elasticity estimator, dated strictly before `before_day`."""
    cut = day_to_iso(before_day)
    return [{"date": d, "tmax_f": t, "prcp_in": p, "snow_in": s}
            for d, t, p, s in weather().get(station, []) if d < cut]
