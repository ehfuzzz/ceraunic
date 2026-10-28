"""Kalshi history CLI (keyless, read-only).

  uv run python scripts/pull_kalshi.py discover
  uv run python scripts/pull_kalshi.py pull --series KXHIGHNY,KXHIGHCHI
  uv run python scripts/pull_kalshi.py pull --all-weather
  uv run python scripts/pull_kalshi.py consolidate
  uv run python scripts/pull_kalshi.py datamd
"""
from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

import pandas as pd
import typer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wi.data import kalshi as K  # noqa: E402

app = typer.Typer(add_completion=False, no_args_is_help=True)
MANIFEST = K.MANIFESTS / "kalshi-series.csv"
FIELDS = ["series_ticker", "title", "category", "city", "in_scope", "first_market_date", "last_market_date",
          "market_count", "settled_count"]


def _manifest_rows() -> list[dict]:
    if not MANIFEST.exists():
        raise typer.BadParameter(f"{MANIFEST} missing: run `discover` first")
    return list(csv.DictReader(MANIFEST.open()))


@app.command()
def discover() -> None:
    """List weather series; for the five cities also count markets (live + archived)."""
    t0 = time.time()
    c = K.Client()
    allser = K.list_series(c)
    ws = K.weather_series(allser)
    typer.echo(f"{len(allser)} series, {len(ws)} weather-like, {sum(1 for s in ws if s['city'])} in the five cities")
    rows = []
    for s in sorted(ws, key=lambda s: (s["city"] is None, s["ticker"])):
        row = {"series_ticker": s["ticker"], "title": s.get("title"), "category": s.get("category"),
               "city": s["city"] or "", "in_scope": bool(s["city"]), "first_market_date": "",
               "last_market_date": "", "market_count": "", "settled_count": ""}
        if s["city"]:
            ms = K.list_markets(c, s["ticker"])
            closes = sorted(m["close_time"][:10] for m in ms if m.get("close_time"))
            row.update(first_market_date=closes[0] if closes else "", last_market_date=closes[-1] if closes else "",
                       market_count=len(ms), settled_count=sum(K.is_settled(m) for m in ms))
            typer.echo(f"  {s['ticker']:<16} {s['city']:<4} markets={len(ms):>6} settled={row['settled_count']:>6} "
                       f"{row['first_market_date']}..{row['last_market_date']}  {s.get('title')}")
        rows.append(row)
    K.MANIFESTS.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("w", newline="") as f:
        w = csv.DictWriter(f, FIELDS)
        w.writeheader()
        w.writerows(rows)
    typer.echo(f"wrote {MANIFEST} ({len(rows)} rows, {c.n_requests} requests, {time.time()-t0:.0f}s)")


@app.command()
def pull(
    series: str = typer.Option("", help="comma-separated series tickers"),
    all_weather: bool = typer.Option(False, "--all-weather", help="every discovered in-scope series with markets"),
    include_hourly: bool = typer.Option(False, "--include-hourly", help="also pull KXTEMP* hourly-directional series (~100k short markets)"),
    workers: int = typer.Option(4),
    limit: int = typer.Option(0, help="debug: only the first N markets per series"),
) -> None:
    """Markets + hourly candles per series; skips settled markets whose candle file exists."""
    if all_weather:
        names = [r["series_ticker"] for r in _manifest_rows() if r["in_scope"] == "True" and int(r["market_count"] or 0) > 0
                 and (include_hourly or not r["series_ticker"].startswith("KXTEMP"))]
    else:
        names = [s.strip() for s in series.split(",") if s.strip()]
    if not names:
        raise typer.BadParameter("give --series or --all-weather")
    c = K.Client()
    cutoff = K.historical_cutoff(c)
    typer.echo(f"historical cutoff {cutoff.isoformat()}; pulling {len(names)} series")
    t0 = time.time()
    for n in names:
        K.pull_series(c, n, cutoff, workers=workers, limit=limit or None, log=typer.echo)
    typer.echo(f"all done: {c.n_requests} requests, {time.time()-t0:.0f}s")


def _scoped() -> dict[str, str | None]:
    return {r["series_ticker"]: (r["city"] or None) for r in _manifest_rows()
            if (K.RAW / r["series_ticker"] / "markets.json").exists()}


@app.command()
def consolidate() -> None:
    """Rebuild data/cache/kalshi/{markets,candles}.parquet from raw JSON."""
    K.consolidate(_scoped(), log=typer.echo)


def _du(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())


@app.command()
def datamd() -> None:
    """Append the Kalshi section to data/manifests/DATA.md from the parquet + pull logs."""
    mk = pd.read_parquet(K.CACHE / "markets.parquet")
    cd = pd.read_parquet(K.CACHE / "candles.parquet", columns=["series_ticker", "market_ticker"])
    rows_by = cd.groupby("series_ticker").size().to_dict()
    cand_mk = cd.groupby("series_ticker")["market_ticker"].nunique().to_dict()
    lines = [
        "",
        f"## Kalshi history (plan 01-02), written {K.utcnow().strftime('%Y-%m-%dT%H:%MZ')}",
        "",
        "Source: keyless Kalshi trade-api v2 (live `/markets` + archived `/historical/markets`, hourly candles). "
        "Raw JSON under `data/raw/kalshi/series/<SERIES>/` (gitignored); consolidated to "
        "`data/cache/kalshi/markets.parquet` and `candles.parquet` (UTC). Series list: `data/manifests/kalshi-series.csv`.",
        "",
        "| series | city | markets | settled | first close | last close | candle rows | markets with candles | bytes on disk | last pull (UTC) | gaps / errors |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for s, g in mk.groupby("series_ticker"):
        log = K.series_dir(s) / "pull-log.json"
        runs = json.loads(log.read_text())["runs"] if log.exists() else []
        last = runs[-1]["pulled_at"][:19] if runs else ""
        errs = sorted({e for r in runs[-1:] for e in r["errors"]}) if runs else []
        empty = len(g) - cand_mk.get(s, 0)
        gap = []
        if errs:
            gap.append(f"{len(errs)} errors (e.g. {errs[0][:80]})")
        if empty:
            gap.append(f"{empty} markets with no candle rows")
        lines.append(
            f"| {s} | {g['city'].iloc[0] or ''} | {len(g)} | {int(g['settled'].sum())} | "
            f"{g['close_time'].min().date()} | {g['close_time'].max().date()} | {rows_by.get(s, 0)} | "
            f"{cand_mk.get(s, 0)} | {_du(K.series_dir(s))} | {last} | {'; '.join(gap) or 'none'} |"
        )
    K.MANIFESTS.mkdir(parents=True, exist_ok=True)
    p = K.MANIFESTS / "DATA.md"
    head = "" if p.exists() else "# DATA manifest\n"
    with p.open("a") as f:
        f.write(head + "\n".join(lines) + "\n")
    typer.echo(f"appended to {p}")


if __name__ == "__main__":
    app()
