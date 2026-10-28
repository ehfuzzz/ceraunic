"""Keyless, read-only pull of the multi-city daily rain binary KXRAIN for the five cities (Phase 2 needs it;
the Phase 1 cache has KXRAINNYC only, which stops 2026-07-15). ≤ 4 req/s. Writes raw JSON under
data/raw/kalshi/series/KXRAIN and data/cache/kalshi/kxrain_{markets,candles}.parquet. Does not touch the
Phase 1 markets/candles parquet files."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wi.data import kalshi as K  # noqa: E402

CITY_SUFFIX = {"NY": "NY", "NYC": "NY", "CHI": "CHI", "MIA": "MIA", "EWR": "EWR", "TTN": "TTN"}


def main() -> None:
    c = K.Client(max_rps=4.0)
    cutoff = K.historical_cutoff(c)
    ms = K.list_markets(c, "KXRAIN")
    keep = []
    for m in ms:
        suf = m["ticker"].rsplit("-", 1)[-1]
        if suf in CITY_SUFFIX:
            m["_city"] = CITY_SUFFIX[suf]
            keep.append(m)
    print(f"KXRAIN: {len(ms)} markets listed, {len(keep)} in the five cities; suffixes seen:",
          sorted({m['ticker'].rsplit('-', 1)[-1] for m in ms}))
    d = K.series_dir("KXRAIN")
    K.write_json(d / "markets.json", {"series_ticker": "KXRAIN", "pulled_at": K.utcnow().isoformat(), "markets": keep})
    mrows, crows = [], []
    for i, m in enumerate(keep):
        f = d / f"{m['ticker']}.candles.json"
        if f.exists() and K.is_settled(m):
            raw = json.loads(f.read_text())
        else:
            raw = K.fetch_candles(c, "KXRAIN", m, cutoff)
            K.write_json(f, raw)
        mrows += K.market_rows("KXRAIN", m["_city"], [m])
        crows += K.candle_rows("KXRAIN", m["_city"], m.get("event_ticker"), raw)
        if (i + 1) % 100 == 0:
            print(f"{i+1}/{len(keep)} done, {c.n_requests} requests")
    mdf = pd.DataFrame(mrows)
    for col in ("open_time", "close_time", "expiration_time", "expected_expiration_time", "settlement_ts", "occurrence_datetime"):
        mdf[col] = pd.to_datetime(mdf[col], utc=True, format="ISO8601")
    cdf = pd.DataFrame(crows)
    cdf["ts"] = pd.to_datetime(cdf["end_period_ts"], unit="s", utc=True)
    cdf = cdf.drop(columns=["end_period_ts"])
    mdf.to_parquet(K.CACHE / "kxrain_markets.parquet", index=False)
    cdf.to_parquet(K.CACHE / "kxrain_candles.parquet", index=False)
    print(f"wrote {len(mdf)} markets, {len(cdf)} candle rows; {c.n_requests} requests total")


if __name__ == "__main__":
    main()
