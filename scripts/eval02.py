"""EVAL-01 (Phase 2): station hedge quality from real Kalshi hourly bid/ask, with fees.

Rules: reports/eval-01/PREREG.md (frozen before this script produced any number).
Run:   uv run python scripts/eval02.py --all
Out:   reports/eval-01/{results.json, tables.md, citydays.csv.gz, rain_daily.csv, figures/*.png}
"""
from __future__ import annotations

import datetime as dt
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import typer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from wi.data.kalshi import _event_date  # noqa: E402
from wi.eval import hedge as HG  # noqa: E402
from wi.eval.fees import kalshi_fee  # noqa: E402
from wi.eval.ladder import (Bracket, Ladder, QuoteSeries, book_yes_asks, bracket_from_market, call_payout,  # noqa: E402
                            depth_within, max_units, offer_status, price_leg, quantities)

OUT = ROOT / "reports" / "eval-01"
FIG = OUT / "figures"
KC = ROOT / "data" / "cache" / "kalshi"
WC = ROOT / "data" / "cache" / "weather"
BOOKS = ROOT / "prior" / "hl-mm-ins" / "reports" / "ins1" / "books.json"

TEMP_SERIES = {"KXHIGHNY": ("NY", "NYC"), "KXHIGHCHI": ("CHI", "MDW"), "KXHIGHMIA": ("MIA", "MIA"),
               "KXHIGHTEWR": ("EWR", "EWR"), "KXHIGHTTTN": ("TTN", "TTN")}
LIQUID = ["NY", "CHI", "MIA"]
THIN = ["EWR", "TTN"]
HORIZONS = [24, 12, 2]
CAP = 6.0
REF_UNITS = 10.0
SEED = 20260930
DRAWS = 2000
BLOCK = 7
RULES = ["A", "B"]
S3_STATUS = ("s3://hlmm-reduced-5325/kalshi-weather-books/ not listable at run time "
             "(anonymous: AccessDenied; default profile: session expired); depth uses books.json only")

app = typer.Typer(add_completion=False)


def log(*a):
    print(f"[{dt.datetime.now(dt.timezone.utc).strftime('%H:%M:%SZ')}]", *a, flush=True)


def fnum(x) -> float | None:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return None if (isinstance(x, float) and math.isnan(x)) else float(x)
    mt = re.search(r"-?\d+(?:\.\d+)?", str(x))
    return float(mt.group(0)) if mt else None


def settle_source(rules: str | None) -> str:
    r = rules or ""
    if "Weather Company" in r:
        return "TWC"
    if "National Weather Service" in r or "Climatological" in r or "NWS" in r:
        return "NWS"
    return "unstated"


def to_epoch(ts) -> int:
    return int(pd.Timestamp(ts).timestamp())


def day_num(d) -> int:
    return (pd.Timestamp(d).date() - dt.date(1970, 1, 1)).days


# ------------------------------------------------------------------ data

def quote_index(candles: pd.DataFrame) -> dict[str, QuoteSeries]:
    c = candles.sort_values(["market_ticker", "ts"])
    tk = c["market_ticker"].to_numpy()
    ts = (c["ts"].astype("int64") // 10**3).to_numpy()  # ms → s
    ask = c["yes_ask_close"].to_numpy(float)
    bid = c["yes_bid_close"].to_numpy(float)
    uniq, start = np.unique(tk, return_index=True)
    ends = list(start[1:]) + [len(tk)]
    out = {}
    for u, s, e in zip(uniq, start, ends):
        q = QuoteSeries.__new__(QuoteSeries)
        q.ts, q.ask, q.bid = ts[s:e], ask[s:e], bid[s:e]
        out[u] = q
    return out


def load():
    log("loading caches")
    m = pd.read_parquet(KC / "markets.parquet")
    c = pd.read_parquet(KC / "candles.parquet", columns=["series_ticker", "market_ticker", "ts", "yes_ask_close", "yes_bid_close"])
    if c["ts"].dtype.unit != "ms":
        c["ts"] = c["ts"].dt.as_unit("ms")
    km = pd.read_parquet(KC / "kxrain_markets.parquet") if (KC / "kxrain_markets.parquet").exists() else pd.DataFrame()
    kc = pd.read_parquet(KC / "kxrain_candles.parquet", columns=["series_ticker", "market_ticker", "ts", "yes_ask_close", "yes_bid_close"]) \
        if (KC / "kxrain_candles.parquet").exists() else pd.DataFrame()
    if len(kc):
        kc["ts"] = kc["ts"].dt.as_unit("ms")
    cli = pd.read_parquet(WC / "official_daily.parquet")
    sd = pd.read_parquet(WC / "stations_daily.parquet")
    keep = set(TEMP_SERIES) | {"KXRAINNYC", "KXRAINNYCM", "KXRAINCHIM", "KXRAINMIAM"}
    c = c[c.series_ticker.isin(keep)]
    allc = pd.concat([c, kc], ignore_index=True) if len(kc) else c
    q = quote_index(allc)
    log(f"markets {len(m)}, kxrain markets {len(km)}, candle rows used {len(allc)}, quoted markets {len(q)}")
    return m, km, q, cli, sd


# ------------------------------------------------------------------ temperature city-days

def build_citydays(m: pd.DataFrame, Q: dict[str, QuoteSeries], cli: pd.DataFrame):
    cli_hi = {(r.station, str(r.date_local)): r.high_f for r in cli.itertuples() if pd.notna(r.high_f)}
    t = m[m.series_ticker.isin(TEMP_SERIES)].copy()
    excl = Counter()
    excl_list = defaultdict(list)
    events = []
    for (ser, ev), g in t.groupby(["series_ticker", "event_ticker"], sort=False):
        city, st = TEMP_SERIES[ser]
        if not g["settled"].all():
            excl["unsettled"] += 1
            continue
        brs = [bracket_from_market(r) for r in g.to_dict("records")]
        brs = [b for b in brs if b]
        if len(brs) < 4:
            excl["fewer than 4 usable brackets"] += 1
            excl_list["fewer than 4 usable brackets"].append(ev)
            continue
        yes = g[g.result == "yes"]
        if len(yes) != 1:
            k = f"{len(yes)} brackets settled yes"
            excl[k] += 1
            excl_list[k].append(ev)
            continue
        lad = Ladder(brs)
        bad = lad.validate()
        if bad:
            excl["malformed ladder (overlap/gap)"] += 1
            excl_list["malformed ladder (overlap/gap)"].append(f"{ev}: {bad}")
            continue
        TS = None
        for v in [yes.iloc[0].expiration_value] + list(g.expiration_value):
            TS = fnum(v)
            if TS is not None:
                break
        win = yes.iloc[0].market_ticker
        d = g.event_date.iloc[0]
        d = pd.Timestamp(d).date() if pd.notna(d) else _event_date(ev)
        ts_source = "expiration_value"
        if TS is None:
            # Deviation 1 (logged in PREREG): the API returns no expiration_value for ~200 events in
            # 2025-10..2026-01. Fill with the NWS CLI high (the settlement source in that era) only when it
            # lies inside the bracket that settled YES; otherwise exclude as pre-registered.
            tc = cli_hi.get((st, d.isoformat()))
            if tc is not None and lad.by_ticker()[win].contains(round(tc)):
                TS, ts_source = float(tc), "cli_fill"
            else:
                excl["no numeric expiration_value"] += 1
                excl_list["no numeric expiration_value"].append(ev)
                continue
        close = g.close_time.mode().iloc[0]
        cts = to_epoch(close)
        quotes = {}
        for h in HORIZONS:
            tt = cts - h * 3600
            for b in lad.brackets:
                qs = Q.get(b.ticker)
                quotes[(b.ticker, h)] = qs.at(tt) if qs is not None else None
        events.append(dict(
            series=ser, city=city, station=st, event=ev, date=d, year=d.year, day=day_num(d),
            close_ts=cts, close_time=pd.Timestamp(close).isoformat(), ladder=lad, winner=win, T_S=TS, ts_source=ts_source,
            T_CLI=cli_hi.get((st, d.isoformat())), n_brackets=len(lad),
            settle_source=settle_source(g.rules_primary.mode().iloc[0] if g.rules_primary.notna().any() else None),
            candle_source=g.source.mode().iloc[0], quotes=quotes,
            winner_open=lad.by_ticker()[win].open_ended,
            ts_in_winner=lad.by_ticker()[win].contains(round(TS)),
        ))
    log(f"temperature: {len(events)} city-days kept; exclusions {dict(excl)}")
    # rule B strike: floor(mean T_S over t-7..t-1), CLI fill, >= 5 of 7
    ts_by = defaultdict(dict)
    for e in events:
        ts_by[e["series"]][e["day"]] = e["T_S"]
    cli_by = defaultdict(dict)
    for (stn, ds), v in cli_hi.items():
        cli_by[stn][day_num(ds)] = v
    for e in events:
        vals = []
        for k in range(1, 8):
            v = ts_by[e["series"]].get(e["day"] - k)
            if v is None:
                v = cli_by[e["station"]].get(e["day"] - k)
            if v is not None:
                vals.append(v)
        e["K_B"] = float(math.floor(np.mean(vals))) if len(vals) >= 5 else None
        e["K_A"] = e["ladder"].second_floor()
    return events, excl, excl_list


def price_citydays(events: list[dict]) -> pd.DataFrame:
    rows = []
    for e in events:
        lad = e["ladder"]
        base = {k: e[k] for k in ("series", "city", "station", "event", "date", "year", "day", "close_time",
                                  "T_S", "ts_source", "T_CLI", "n_brackets", "settle_source", "candle_source", "winner",
                                  "winner_open", "ts_in_winner", "K_A", "K_B")}
        for rule in RULES:
            K = e[f"K_{rule}"]
            if K is None:
                continue
            pay = lambda T, K=K: call_payout(T, K, CAP)  # noqa: E731
            qty = quantities(lad, pay)
            X = pay(lad.by_ticker()[e["winner"]].rep)
            E = pay(round(e["T_S"]))
            Ecli = pay(e["T_CLI"]) if e["T_CLI"] is not None else np.nan
            r = dict(base, rule=rule, K=K, X=X, E=E, E_cli=Ecli, n_rungs=len(qty),
                     contracts=sum(qty.values()), unspanned=len(qty) == 0)
            for h in HORIZONS:
                tt = e["close_ts"] - h * 3600
                qts = {tk: e["quotes"][(tk, h)] for tk in qty}
                lp = price_leg(qty, qts, tt, ref_units=REF_UNITS, contract_step=1.0)
                allq = [e["quotes"][(b.ticker, h)] for b in lad.brackets]
                book = sum(q[0] for q in allq if offer_status(q) == "ok") - 1 if all(offer_status(q) == "ok" for q in allq) else np.nan
                r.update({
                    f"prem{h}": lp.premium if lp.n_missing == 0 else np.nan,
                    f"spread{h}": lp.spread if lp.n_missing == 0 else np.nan,
                    f"fee{h}": lp.fee if lp.n_missing == 0 else np.nan,
                    f"feeraw{h}": lp.fee_raw if lp.n_missing == 0 else np.nan,
                    f"exec{h}": lp.n_missing == 0,
                    f"nooffer{h}": lp.n_missing > 0,
                    f"nmiss{h}": lp.n_missing,
                    f"why{h}": ";".join(f"{k}:{v}" for k, v in sorted(lp.reasons.items())),
                    f"stale{h}": lp.max_stale_s if lp.n_missing == 0 else np.nan,
                    f"booksum{h}": book,
                })
            rows.append(r)
    df = pd.DataFrame(rows)
    return df


# ------------------------------------------------------------------ metrics

def group_metrics(df: pd.DataFrame, h: int, boot: bool = True) -> dict:
    """All PREREG metrics for one subset (one strike rule) at horizon h."""
    out: dict = {"n_citydays": int(len(df))}
    if len(df) == 0:
        return out
    ex = df[df[f"exec{h}"]]
    out["n_exec"] = int(len(ex))
    out["no_offer_share"] = float(df[f"nooffer{h}"].mean())
    need = df["n_rungs"].sum()
    out["rung_no_offer_share"] = float(df[f"nmiss{h}"].sum() / need) if need else float("nan")
    reasons = Counter()
    for w in df[f"why{h}"]:
        for kv in filter(None, str(w).split(";")):
            k, v = kv.split(":")
            reasons[k] += int(v)
    out["no_offer_reasons_rungs"] = dict(reasons)
    out["unhedgeable_share"] = float((df[f"nooffer{h}"] | df["unspanned"]).mean())
    out["unspanned_share"] = float(df["unspanned"].mean())
    b = df["E"] - df["X"]
    out["binning_rmse"] = float(np.sqrt(np.mean(b ** 2)))
    out["binning_mean"] = float(b.mean())
    tail = df["winner_open"] & (df["E"] != df["X"])
    out["tail_outside_share"] = float(tail.mean())
    out["tail_outside_payout_share"] = float((df.loc[tail, "E"] - df.loc[tail, "X"]).abs().sum() / df["E"].sum()) if df["E"].sum() > 0 else float("nan")
    out["mean_E"] = float(df["E"].mean())
    out["share_E_pos"] = float((df["E"] > 0).mean())
    out["he_cover_all_days"] = he_pooled(df["E"], df["X"], df["city"])
    if len(ex):
        out["stale_median_h"] = float(ex[f"stale{h}"].median() / 3600)
        out["stale_p90_h"] = float(ex[f"stale{h}"].quantile(0.9) / 3600)
        out["fee_raw"] = float(ex[f"feeraw{h}"].mean())
        out["booksum_mean"] = float(ex[f"booksum{h}"].mean()) if ex[f"booksum{h}"].notna().any() else float("nan")
        exc = ex[ex["E_cli"].notna()]
        if len(exc) >= 5:
            out["n_cli"] = int(len(exc))
            out["he_cover_cli"] = pooled_point(exc, "E_cli", "X")
            out["he_cover_same_days_as_cli"] = pooled_point(exc, "E", "X")
    if len(ex) >= 5:
        S, _, _ = HG.day_sums(ex["day"].to_numpy(), ex["city"].to_numpy(), ex["E"], ex["X"],
                              ex[f"prem{h}"], ex[f"fee{h}"], ex[f"spread{h}"])
        if boot:
            out.update(HG.bootstrap(S, DRAWS, BLOCK, SEED))
        else:
            out.update({k: {"est": float(v)} for k, v in HG.stats_from_sums(S.sum(axis=1)).items()})
    return out


def pooled_point(df, ecol, xcol) -> float:
    S, _, _ = HG.day_sums(df["day"].to_numpy(), df["city"].to_numpy(), df[ecol], df[xcol])
    return float(HG.stats_from_sums(S.sum(axis=1))["he_cover"])


def he_pooled(E, X, g) -> float:
    d = pd.DataFrame({"E": np.asarray(E, float), "X": np.asarray(X, float), "g": np.asarray(g)})
    num = den = 0.0
    for _, x in d.groupby("g"):
        num += len(x) * np.var(x.E - x.X)
        den += len(x) * np.var(x.E)
    return float(1 - num / den) if den > 0 else float("nan")



def temperature_metrics(df: pd.DataFrame) -> dict:
    res: dict = {"city_year": [], "city": [], "pooled": [], "settle_source": [], "candle_source": []}
    t0 = time.time()
    for rule in RULES:
        d = df[df.rule == rule]
        for h in HORIZONS:
            for (city, yr), g in d.groupby(["city", "year"]):
                res["city_year"].append(dict(rule=rule, h=h, city=city, year=int(yr), **group_metrics(g, h)))
            for city, g in d.groupby("city"):
                res["city"].append(dict(rule=rule, h=h, city=city, **group_metrics(g, h)))
            for name, cities in (("liquid NY+CHI+MIA", LIQUID), ("thin EWR+TTN", THIN)):
                g = d[d.city.isin(cities)]
                res["pooled"].append(dict(rule=rule, h=h, pool=name, **group_metrics(g, h)))
            # post-hoc, descriptive only (not in PREREG): the current market era
            g = d[d.city.isin(LIQUID) & (d.year >= 2025)]
            res["pooled"].append(dict(rule=rule, h=h, pool="liquid 2025+ (post-hoc)", **group_metrics(g, h)))
            for (city, ss), g in d.groupby(["city", "settle_source"]):
                res["settle_source"].append(dict(rule=rule, h=h, city=city, settle_source=ss, **group_metrics(g, h)))
            g = d[d.city.isin(LIQUID)]
            for ss, gg in g.groupby("settle_source"):
                res["settle_source"].append(dict(rule=rule, h=h, city="liquid", settle_source=ss, **group_metrics(gg, h)))
            for cs, gg in g.groupby("candle_source"):
                res["candle_source"].append(dict(rule=rule, h=h, pool="liquid NY+CHI+MIA", candle_source=cs, **group_metrics(gg, h)))
        log(f"metrics rule {rule} done ({time.time()-t0:.0f}s)")
    return res


def mismatch(df: pd.DataFrame) -> list[dict]:
    """CLI vs expiration_value (2023+), per city × settle_source, rule A rows (one per city-day)."""
    d = df[(df.rule == "A") & df.T_CLI.notna() & (df.ts_source == "expiration_value")].copy()  # CLI-filled days would match by construction
    out = []
    for keys, g in list(d.groupby(["city", "settle_source"])) + [(("all", "all"), d)]:
        ne = (g.T_CLI.round() != g.T_S.round())
        # CLI outside the settled bracket
        outside = []
        for r in g.itertuples():
            outside.append(not r.ts_in_winner_cli)
        out.append(dict(city=keys[0], settle_source=keys[1], n=int(len(g)),
                        value_mismatch_share=float(ne.mean()),
                        bracket_mismatch_share=float(np.mean(outside)) if len(outside) else float("nan"),
                        mean_cli_minus_ts=float((g.T_CLI - g.T_S).mean())))
    return out


# ------------------------------------------------------------------ rain

RAIN_STN = [(r"CLIORD|O'Hare|OHare", "ORD"), (r"CLIMDW|Midway", "MDW"), (r"CLIMIA|Miami", "MIA"),
            (r"CLIEWR|Newark", "EWR"), (r"CLITTN|Trenton", "TTN"), (r"CLINYC|Central Park|New York", "NYC")]


def rain_station(rules: str | None, default: str) -> str:
    for pat, st in RAIN_STN:
        if rules and re.search(pat, rules):
            return st
    return default


def station_precip(cli: pd.DataFrame, sd: pd.DataFrame) -> dict:
    p = {}
    for r in cli.itertuples():
        if pd.notna(r.precip_in):
            p[(r.station, str(r.date_local))] = float(r.precip_in)
    for r in sd[sd.station == "ORD"].itertuples():
        if pd.notna(r.precip_in) and not r.precip_missing:
            p[("ORD", str(r.date_local))] = float(r.precip_in)
    return p


def rain_daily(m: pd.DataFrame, km: pd.DataFrame, Q, cli, sd, wet_rule_arg: str = "prereg", write_csv: bool = True) -> dict:
    """wet_rule_arg: 'prereg' = the frozen conditional (default, unchanged); 'dry' = forced precip >= 0.01 in (trace = dry),
    the rule the product pays on (sensitivity only; never the primary)."""
    P = station_precip(cli, sd)
    r1 = m[(m.series_ticker == "KXRAINNYC") & m.market_ticker.str.endswith("-T0")].copy()
    r1["city"] = "NY"
    r2 = km.copy()
    rr = pd.concat([r1, r2], ignore_index=True)
    rr = rr[rr.settled & rr.result.isin(["yes", "no"])]
    rows = []
    for r in rr.itertuples():
        d = r.event_date
        d = pd.Timestamp(d).date() if pd.notna(d) else _event_date(r.event_ticker)
        stn = rain_station(r.rules_primary, {"NY": "NYC", "CHI": "ORD", "MIA": "MIA", "EWR": "EWR", "TTN": "TTN"}[r.city])
        pr = P.get((stn, d.isoformat()))
        row = dict(series=r.series_ticker, market=r.market_ticker, city=r.city, station=stn, date=d, year=d.year,
                   month=d.month, day=day_num(d), y=1.0 if r.result == "yes" else 0.0, precip=pr)
        cts = to_epoch(r.close_time)
        for h in HORIZONS:
            q = Q[r.market_ticker].at(cts - h * 3600) if r.market_ticker in Q else None
            stt = offer_status(q)
            quoted = q is not None and not math.isnan(q[0]) and q[0] > 0
            ask = q[0] if quoted else np.nan
            bid = (0.0 if math.isnan(q[1]) else q[1]) if quoted else np.nan
            row[f"mid{h}"] = (ask + bid) / 2 if quoted else np.nan
            row[f"ask{h}"] = ask
            row[f"ok{h}"] = stt == "ok"
            row[f"fee{h}"] = kalshi_fee(REF_UNITS, ask) / REF_UNITS if stt == "ok" else np.nan
        rows.append(row)
    df = pd.DataFrame(rows)
    # trace check (pre-registered conditional wet definition)
    tr = df[df.precip.notna() & (df.precip > 0) & (df.precip < 0.01)]
    trace_yes = float(tr.y.mean()) if len(tr) else float("nan")
    wet_rule = "precip > 0 incl. trace" if (len(tr) and trace_yes > 0.5) else "precip >= 0.01 in (trace = dry)"
    if wet_rule_arg == "dry":
        wet_rule = "precip >= 0.01 in (trace = dry)"  # forced by --wet-rule dry, not by the conditional
    thr = 0.0 if wet_rule.startswith("precip > 0") else 0.01
    wet = lambda p: (p > thr) if thr == 0.0 else (p >= 0.01)  # noqa: E731
    df["wet"] = np.where(df.precip.notna(), wet(df.precip.fillna(-1)).astype(float), np.nan)
    agree = df[df.precip.notna()]
    # leave-year-out monthly climatology from the station daily table
    clim_rows = []
    for (stn, ds), p in P.items():
        dd = dt.date.fromisoformat(ds)
        clim_rows.append((stn, dd.year, dd.month, float(wet(p))))
    cl = pd.DataFrame(clim_rows, columns=["station", "year", "month", "wet"])
    agg = cl.groupby(["station", "month", "year"]).wet.agg(["sum", "count"]).reset_index()

    def pclim(stn, yr, mo):
        a = agg[(agg.station == stn) & (agg.month == mo) & (agg.year != yr)]
        return float(a["sum"].sum() / a["count"].sum()) if a["count"].sum() else np.nan

    cache = {}
    df["p_clim"] = [cache.setdefault((s, y, mo), pclim(s, y, mo)) for s, y, mo in zip(df.station, df.year, df.month)]
    out = {"n_markets": int(len(df)), "by_series": df.series.value_counts().to_dict(),
           "by_city": df.city.value_counts().to_dict(),
           "trace_days": int(len(tr)), "trace_yes_share": trace_yes, "wet_rule": wet_rule,
           "result_vs_station_agreement": float((agree.y == agree.wet).mean()) if len(agree) else float("nan"),
           "n_with_station_precip": int(len(agree)),
           "horizons": {}}
    for h in HORIZONS:
        hq = df[df[f"mid{h}"].notna() & df.p_clim.notna()]
        res = {"n_quoted": int(len(hq)), "no_quote_share": float(1 - df[f"mid{h}"].notna().mean()),
               "no_offer_share": float(1 - df[f"ok{h}"].mean())}
        if len(hq):
            bm = (hq[f"mid{h}"] - hq.y) ** 2
            bc = (hq.p_clim - hq.y) ** 2
            res.update(brier_market=float(bm.mean()), brier_clim=float(bc.mean()),
                       brier_gain=float(bc.mean() - bm.mean()), base_rate=float(hq.y.mean()))
            res["brier_gain_ci"] = boot_mean_diff(hq.day.to_numpy(), (bc - bm).to_numpy())
            res["by_city"] = {c: dict(n=int(len(g)), brier_market=float(((g[f"mid{h}"] - g.y) ** 2).mean()),
                                      brier_clim=float(((g.p_clim - g.y) ** 2).mean()))
                              for c, g in hq.groupby("city")}
            res["by_series"] = {s: dict(n=int(len(g)), brier_market=float(((g[f"mid{h}"] - g.y) ** 2).mean()),
                                        brier_clim=float(((g.p_clim - g.y) ** 2).mean()))
                                for s, g in hq.groupby("series")}
        ok = df[df[f"ok{h}"]]
        if len(ok) and ok.y.sum() > 0:
            res["cost_per_dollar_payout"] = float((ok[f"ask{h}"] + ok[f"fee{h}"]).sum() / ok.y.sum())
            res["cost_per_dollar_payout_ex_fee"] = float(ok[f"ask{h}"].sum() / ok.y.sum())
        okw = ok[ok.wet.notna()]
        if len(okw) >= 10:
            S, _, _ = HG.day_sums(okw.day.to_numpy(), okw.station.to_numpy(), okw.wet, okw.y, okw[f"ask{h}"], okw[f"fee{h}"])
            b = HG.bootstrap(S, DRAWS, BLOCK, SEED)
            res["he_wet"] = {"n": int(len(okw)), "he_cover": b["he_cover"], "he_ladder": b["he_ladder"]}
        out["horizons"][h] = res
    if wet_rule_arg == "dry":
        out["wet_rule_forced"] = "dry (--wet-rule dry); the frozen conditional would have chosen the primary rule"
    if write_csv:
        df.to_csv(OUT / "rain_daily.csv", index=False)
    return out


def boot_mean_diff(day: np.ndarray, v: np.ndarray) -> dict:
    d0 = int(day.min())
    n_days = int(day.max()) - d0 + 1
    s = np.zeros(n_days)
    n = np.zeros(n_days)
    np.add.at(s, day - d0, v)
    np.add.at(n, day - d0, 1)
    W = HG.block_weights(n_days, DRAWS, BLOCK, SEED).astype(float)
    b = (W @ s) / (W @ n)
    lo, hi = np.percentile(b[np.isfinite(b)], [2.5, 97.5])
    return {"est": float(v.mean()), "lo": float(lo), "hi": float(hi)}


def rain_monthly(m: pd.DataFrame, Q) -> dict:
    r = m[m.series_ticker.isin(["KXRAINNYCM", "KXRAINCHIM", "KXRAINMIAM"]) & m.settled & m.result.isin(["yes", "no"])]
    rows = []
    for x in r.itertuples():
        mt = re.search(r"-(\d{2})([A-Z]{3})", x.event_ticker)
        mon = dt.datetime.strptime(mt.group(1) + mt.group(2), "%y%b").replace(tzinfo=dt.timezone.utc)
        times = {"month_start": int((mon + dt.timedelta(hours=12)).timestamp()), "close_24h": to_epoch(x.close_time) - 86400}
        for lab, tt in times.items():
            q = Q[x.market_ticker].at(tt) if x.market_ticker in Q else None
            quoted = q is not None and not math.isnan(q[0]) and q[0] > 0
            bid = (0.0 if (q is None or math.isnan(q[1])) else q[1])
            rows.append(dict(series=x.series_ticker, market=x.market_ticker, when=lab, y=1.0 if x.result == "yes" else 0.0,
                             quoted=quoted, ok=offer_status(q) == "ok",
                             spread=(q[0] - bid) if quoted else np.nan, mid=(q[0] + bid) / 2 if quoted else np.nan))
    df = pd.DataFrame(rows)
    out = {}
    for (s, w), g in df.groupby(["series", "when"]):
        qq = g[g.quoted]
        out[f"{s}|{w}"] = dict(n=int(len(g)), n_quoted=int(len(qq)), no_offer_share=float(1 - g.ok.mean()),
                               spread_median=float(qq.spread.median()) if len(qq) else None,
                               spread_p90=float(qq.spread.quantile(0.9)) if len(qq) else None,
                               brier_mid=float(((qq.mid - qq.y) ** 2).mean()) if len(qq) else None,
                               base_rate=float(g.y.mean()))
    return out


# ------------------------------------------------------------------ depth

def depth(m: pd.DataFrame) -> dict:
    books = json.loads(BOOKS.read_text())
    mk = m.set_index("market_ticker")
    rungs = []
    ladders = defaultdict(dict)
    for tk, ob in books.items():
        asks = book_yes_asks(ob)
        best, dep = depth_within(asks, 0.03)
        ev = tk.rsplit("-", 1)[0]
        product = re.match(r"KX[A-Z]+", tk).group(0)
        rungs.append(dict(ticker=tk, event=ev, product=product, best_ask=best, depth_3c=dep,
                          levels=len(asks), total_offered=sum(q for _, q in asks)))
        if product.startswith("KXHIGH"):
            ladders[ev][tk] = dep
    lad_out = {}
    for ev, deps in ladders.items():
        if all(tk in mk.index for tk in deps):
            brs = [bracket_from_market(dict(mk.loc[tk], market_ticker=tk)) for tk in deps]
        else:  # not in the Phase 1 cache (e.g. LAX): rebuild from tickers (lowest T = less, other T = greater)
            nums = {tk: float(tk.rsplit("-", 1)[1][1:]) for tk in deps}
            tlow = min(v for tk, v in nums.items() if "-T" in tk)
            brs = []
            for tk, n in nums.items():
                if "-B" in tk:
                    brs.append(Bracket(tk, "between", n - 0.5, n + 0.5))
                elif n == tlow:
                    brs.append(Bracket(tk, "less", None, n))
                else:
                    brs.append(Bracket(tk, "greater", n, None))
        lad = Ladder([b for b in brs if b])
        K = lad.second_floor()
        qty = quantities(lad, lambda T: call_payout(T, K, CAP))
        lad_out[ev] = dict(K=K, contracts_per_unit=sum(qty.values()),
                           depth_3c={tk: deps[tk] for tk in qty}, max_units_3c=max_units(qty, deps),
                           valid=lad.validate() is None)
    return {"source": str(BOOKS.relative_to(ROOT)), "s3": S3_STATUS,
            "snapshot": "2026-09-29 (ins1 pull; exact UTC time not stored in the file) for the 2026-09-30 ladders",
            "rungs": rungs, "ladders": lad_out}


# ------------------------------------------------------------------ report

def fmt(x, p=2, pct=False):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "–"
    return f"{100*x:.{max(p-2,0)}f}%" if pct else f"{x:.{p}f}"


def ci(d, k, p=2, pct=False):
    v = d.get(k)
    if not isinstance(v, dict):
        return "–"
    s = fmt(v["est"], p, pct)
    if "lo" in v and np.isfinite(v["lo"]):
        s += f" [{fmt(v['lo'], p, pct)}, {fmt(v['hi'], p, pct)}]"
    return s


def row_line(r, label):
    return (f"| {label} | {r['n_citydays']} | {r.get('n_exec','–')} | {ci(r,'premium')} | {ci(r,'payout')} | "
            f"{ci(r,'overround',3,True)} | {ci(r,'fee',3)} | {ci(r,'spread',3)} | {fmt(r.get('binning_rmse'))} | "
            f"{ci(r,'he_cover')} | {ci(r,'he_ladder')} | {fmt(r.get('no_offer_share'),3,True)} | "
            f"{fmt(r.get('tail_outside_share'),3,True)} |")


HDR = ("| group | city-days | exec | premium | payout | overround | fee | spread | bin RMSE | HE_cover | HE_ladder | "
       "no-offer | tail-out |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|")


def write_tables(R: dict) -> str:
    T = R["temperature"]
    L = [f"# EVAL-01 tables\n\nGenerated {R['meta']['run_utc']} by scripts/eval02.py. Rules: PREREG.md "
         f"(frozen {R['meta']['prereg_frozen']}). Per $1/°F unit, cap 6 °F. Premium at YES asks, fees excluded "
         "(fee column = cent-rounded per rung order at a 10-unit policy, per unit). Brackets: 95 % 7-day block "
         "bootstrap, 2,000 draws, seed 20260930. exec = city-days with every needed rung offered at the horizon.\n"]
    for rule, title in (("A", "Strike rule A (K = second-bracket floor, ins1)"), ("B", "Strike rule B (K = floor of trailing 7-day mean T_S)")):
        L.append(f"\n## {title}\n")
        for h in HORIZONS:
            L.append(f"\n### Pooled and per city, {h} h before close\n\n{HDR}")
            for r in T["pooled"]:
                if r["rule"] == rule and r["h"] == h:
                    L.append(row_line(r, r["pool"]))
            for r in T["city"]:
                if r["rule"] == rule and r["h"] == h:
                    L.append(row_line(r, r["city"]))
        L.append(f"\n### Per city-year, 24 h\n\n{HDR}")
        for r in T["city_year"]:
            if r["rule"] == rule and r["h"] == 24:
                L.append(row_line(r, f"{r['city']} {r['year']}"))
        if rule == "A":
            for h in (12, 2):
                L.append(f"\n### Per city-year, {h} h\n\n{HDR}")
                for r in T["city_year"]:
                    if r["rule"] == rule and r["h"] == h:
                        L.append(row_line(r, f"{r['city']} {r['year']}"))
        L.append(f"\n### By settle_source, 24 h\n\n{HDR}")
        for r in T["settle_source"]:
            if r["rule"] == rule and r["h"] == 24:
                L.append(row_line(r, f"{r['city']} / {r['settle_source']}"))
        L.append(f"\n### By candle source (liquid pooled), 24 h\n\n{HDR}")
        for r in T["candle_source"]:
            if r["rule"] == rule and r["h"] == 24:
                L.append(row_line(r, f"liquid / {r['candle_source']}"))
    L.append("\n## HE against the NWS CLI high (2023+, rule A, same executable days)\n\n| group | h | n | HE_cover vs T_S | HE_cover vs T_CLI |\n|---|---|---|---|---|")
    for r in T["city"] + T["pooled"]:
        if r["rule"] == "A" and "he_cover_cli" in r:
            L.append(f"| {r.get('city', r.get('pool'))} | {r['h']} | {r['n_cli']} | {fmt(r['he_cover_same_days_as_cli'])} | {fmt(r['he_cover_cli'])} |")
    L.append("\n## Settlement: NWS CLI vs expiration_value (2023+)\n\n| city | settle_source | n | value ≠ | CLI outside settled bracket | mean CLI − T_S |\n|---|---|---|---|---|---|")
    for r in R["mismatch"]:
        L.append(f"| {r['city']} | {r['settle_source']} | {r['n']} | {fmt(r['value_mismatch_share'],3,True)} | {fmt(r['bracket_mismatch_share'],3,True)} | {fmt(r['mean_cli_minus_ts'])} |")
    L.append("\n## Unhedgeable days (24 h)\n\n| rule | group | no-offer share | unspanned share | unhedgeable share | rung no-offer | reasons (rungs) |\n|---|---|---|---|---|---|---|")
    for r in T["city"]:
        if r["h"] == 24:
            L.append(f"| {r['rule']} | {r['city']} | {fmt(r['no_offer_share'],3,True)} | {fmt(r['unspanned_share'],3,True)} | {fmt(r['unhedgeable_share'],3,True)} | {fmt(r['rung_no_offer_share'],3,True)} | {r['no_offer_reasons_rungs']} |")
    rd = R["rain_daily"]
    L.append(f"\n## Daily rain binary\n\n{rd['n_markets']} settled markets {rd['by_series']}; wet rule: {rd['wet_rule']} "
             f"(trace days {rd['trace_days']}, share settled YES {fmt(rd['trace_yes_share'],3,True)}); result vs station wet agreement "
             f"{fmt(rd['result_vs_station_agreement'],3,True)} on {rd['n_with_station_precip']} markets.\n\n"
             "| h | quoted | Brier market (mid) | Brier climatology | gain [95 % CI] | cost per $ payout (incl. fee) | HE_cover wet | HE_ladder wet |\n|---|---|---|---|---|---|---|---|")
    for h, x in rd["horizons"].items():
        g = x.get("brier_gain_ci", {})
        hw = x.get("he_wet", {})
        L.append(f"| {h} | {x['n_quoted']} | {fmt(x.get('brier_market'),3)} | {fmt(x.get('brier_clim'),3)} | "
                 f"{fmt(g.get('est'),3)} [{fmt(g.get('lo'),3)}, {fmt(g.get('hi'),3)}] | {fmt(x.get('cost_per_dollar_payout'),3)} | "
                 f"{ci(hw,'he_cover') if hw else '–'} | {ci(hw,'he_ladder') if hw else '–'} |")
    L.append("\n### Daily rain by city, 24 h\n\n| city | n | Brier market | Brier climatology |\n|---|---|---|---|")
    for c, x in rd["horizons"]["24"].get("by_city", {}).items():
        L.append(f"| {c} | {x['n']} | {fmt(x['brier_market'],3)} | {fmt(x['brier_clim'],3)} |")
    L.append("\n## Monthly rain ladders\n\n| series | when | markets | quoted | no-offer | median spread | p90 spread | Brier (mid) | base rate |\n|---|---|---|---|---|---|---|---|---|")
    for k, x in R["rain_monthly"].items():
        s, w = k.split("|")
        L.append(f"| {s} | {w} | {x['n']} | {x['n_quoted']} | {fmt(x['no_offer_share'],3,True)} | {fmt(x['spread_median'])} | {fmt(x['spread_p90'])} | {fmt(x['brier_mid'],3)} | {fmt(x['base_rate'],3,True)} |")
    D = R["depth"]
    L.append(f"\n## Depth (books.json, {D['snapshot']})\n\n{D['s3']}.\n\n| ladder | K | contracts/unit | depth within 3c per needed rung | max units at ≤ 3c |\n|---|---|---|---|---|")
    for ev, x in D["ladders"].items():
        L.append(f"| {ev} | {x['K']:.0f} | {x['contracts_per_unit']:.1f} | {', '.join(f'{k.rsplit(chr(45),1)[1]}:{v:.0f}' for k, v in x['depth_3c'].items())} | {x['max_units_3c']:.1f} |")
    L.append("\n| product | books | median depth within 3c | min | max |\n|---|---|---|---|---|")
    dr = pd.DataFrame(D["rungs"])
    for p, g in dr.groupby("product"):
        L.append(f"| {p} | {len(g)} | {g.depth_3c.median():.0f} | {g.depth_3c.min():.0f} | {g.depth_3c.max():.0f} |")
    c = R["ins1_check"]
    L.append(f"\n## ins1 reproduction (NYC 2026-07-24..2026-09-29, rule A, 24 h, fees excluded)\n\n"
             f"n = {c['n']} (exec {c['n_exec']}); premium {fmt(c['premium'],3)} vs ins1 1.73 ({fmt(c['premium_dev'],3,True)}); "
             f"payout {fmt(c['payout'],3)} vs ins1 1.43 ({fmt(c['payout_dev'],3,True)}); within 5 %: {c['pass']}.\n")
    L.append("\n## Exclusions (temperature events)\n")
    for k, v in R["exclusions"].items():
        L.append(f"- {k}: {v}")
    return "\n".join(L) + "\n"


def figures(R: dict, df: pd.DataFrame):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    FIG.mkdir(parents=True, exist_ok=True)
    cy = pd.DataFrame([dict(city=r["city"], year=r["year"], h=r["h"],
                            he_cover=r.get("he_cover", {}).get("est", np.nan), he_ladder=r.get("he_ladder", {}).get("est", np.nan),
                            he_lo=r.get("he_cover", {}).get("lo", np.nan), he_hi=r.get("he_cover", {}).get("hi", np.nan),
                            over=r.get("overround", {}).get("est", np.nan), nooffer=r.get("no_offer_share", np.nan))
                       for r in R["temperature"]["city_year"] if r["rule"] == "A"])
    cy = cy[cy.city.isin(LIQUID)]
    thin_note = "EWR/TTN (34 days each, 2026 only) are in tables.md; off this scale"
    years = sorted(cy.year.unique())
    fig, ax = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
    for i, key in enumerate(["he_cover", "he_ladder"]):
        for city, g in cy[cy.h == 24].groupby("city"):
            ax[i].plot(g.year, g[key], marker="o", label=city)
        ax[i].axhline(0.85 if key == "he_cover" else 0.5, ls="--", c="grey", lw=0.8)
        ax[i].axhline(0, c="black", lw=0.5)
        ax[i].set_title(f"{key}, rule A, 24 h (dashed: {'T1 bar 0.85' if key == 'he_cover' else 'expectation 0.5'})", fontsize=9)
        ax[i].set_xticks(years)
    ax[0].set_ylabel("hedge effectiveness")
    ax[0].legend()
    fig.text(0.5, 0.005, thin_note, ha="center", fontsize=7)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(FIG / "he_by_year.png", dpi=130)
    plt.close(fig)
    fig, ax = plt.subplots(1, 3, figsize=(13, 4), sharey=True)
    for i, h in enumerate(HORIZONS):
        for city, g in cy[cy.h == h].groupby("city"):
            ax[i].plot(g.year, 100 * g.over, marker="o", label=city)
        ax[i].axhline(20, ls="--", c="grey", lw=0.8)
        ax[i].axhline(0, c="black", lw=0.5)
        ax[i].set_title(f"overround %, rule A, {h} h (dashed: T1 bar 20 %)", fontsize=9)
        ax[i].set_xticks(years)
    ax[0].legend()
    fig.text(0.5, 0.005, thin_note, ha="center", fontsize=7)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(FIG / "overround_by_year.png", dpi=130)
    plt.close(fig)
    fig, ax = plt.subplots(1, 3, figsize=(13, 4), sharey=True)
    for i, h in enumerate(HORIZONS):
        for city, g in cy[cy.h == h].groupby("city"):
            ax[i].plot(g.year, 100 * g.nooffer, marker="o", label=city)
        ax[i].axhline(10, ls="--", c="grey", lw=0.8)
        ax[i].set_title(f"no-offer share of city-days %, {h} h (dashed: T4 bar 10 %)", fontsize=9)
        ax[i].set_xticks(years)
    ax[0].legend()
    fig.tight_layout()
    fig.savefig(FIG / "no_offer_share.png", dpi=130)
    plt.close(fig)
    dr = pd.DataFrame(R["depth"]["rungs"])
    fig, ax = plt.subplots(figsize=(8, 4))
    prods = sorted(dr["product"].unique())
    for i, pr in enumerate(prods):
        v = dr.loc[dr["product"] == pr, "depth_3c"].to_numpy(float)
        jitter = np.linspace(-0.15, 0.15, len(v)) if len(v) > 1 else np.zeros(1)
        ax.scatter(np.maximum(v, 0.8), i + jitter, s=18, alpha=0.8)
        ax.text(max(v.max(), 0.8) * 1.3, i, f"median {np.median(v):.0f}", va="center", fontsize=7)
    ax.set_xscale("log")
    ax.set_yticks(range(len(prods)))
    ax.set_yticklabels(prods, fontsize=8)
    ax.set_xlabel("contracts offered within 3c of the best YES ask, per rung (log; empty books drawn at 0.8)")
    ax.set_title("Order-book depth, books.json (2026-09-29 snapshot)", fontsize=10)
    fig.tight_layout()
    fig.savefig(FIG / "depth_hist.png", dpi=130)
    plt.close(fig)


def verdicts(R: dict) -> dict:
    T = R["temperature"]
    liq = next(r for r in T["pooled"] if r["rule"] == "A" and r["h"] == 24 and r["pool"] == "liquid NY+CHI+MIA")
    hc, ov = liq["he_cover"]["est"], liq["overround"]["est"]
    v = {"T1": {"he_cover": hc, "overround": ov, "pass": bool(hc >= 0.85 and ov <= 0.20)}}
    v["T1b"] = {"he_ladder": liq["he_ladder"]["est"], "expectation": 0.5}
    t2 = {}
    for r in T["city"]:
        if r["rule"] == "A" and r["h"] == 24 and r["city"] in THIN:
            o = r.get("overround", {}).get("est", np.nan)
            t2[r["city"]] = {"overround": o, "fail": bool(o > 1.0)}
    v["T2"] = t2
    g = R["rain_daily"]["horizons"][24]
    v["T3"] = {"brier_gain": g.get("brier_gain"), "pass": bool(g.get("brier_gain", -1) >= 0.02)}
    cy = [r for r in T["city_year"] if r["rule"] == "A" and r["h"] == 24 and r["city"] in LIQUID and r["year"] >= 2024]
    worst = max(cy, key=lambda r: r["no_offer_share"])
    v["T4"] = {"per_city_year": {f"{r['city']} {r['year']}": r["no_offer_share"] for r in cy},
               "worst": f"{worst['city']} {worst['year']}", "worst_share": worst["no_offer_share"],
               "pass": bool(all(r["no_offer_share"] <= 0.10 for r in cy))}
    return v


def ins1_check(df: pd.DataFrame) -> dict:
    d = df[(df.rule == "A") & (df.city == "NY") & (df.date >= dt.date(2026, 7, 24)) & (df.date <= dt.date(2026, 9, 29))]
    ex = d[d.exec24]
    p, x = float(ex.prem24.mean()), float(ex.X.mean())
    return dict(n=int(len(d)), n_exec=int(len(ex)), premium=p, payout=x, premium_dev=p / 1.73 - 1, payout_dev=x / 1.43 - 1,
                **{"pass": bool(abs(p / 1.73 - 1) <= 0.05 and abs(x / 1.43 - 1) <= 0.05)})


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (dt.date, pd.Timestamp)):
        return o.isoformat()
    return o


# ------------------------------------------------------------------ trace = dry sensitivity

def _leaves(o, pre=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from _leaves(v, f"{pre}.{k}" if pre else str(k))
    elif isinstance(o, (int, float)) and not isinstance(o, bool):
        yield pre, float(o)


def wet_rule_sensitivity(m, km, Q, cli, sd) -> None:
    """Labelled sensitivity: daily-rain numbers with trace = dry. Writes only sensitivity_trace_dry.{json,md}.
    The wet rule enters only rain_daily (exposure label, leave-year-out climatology, HE_wet, station agreement);
    temperature ladders, depth, monthly rain and the rain market Brier / cost / no-offer numbers do not use it."""
    t0 = time.time()
    primary = json.loads((OUT / "results.json").read_text())["rain_daily"]
    repro = jsonable(rain_daily(m, km, Q, cli, sd, "prereg", write_csv=False))
    dry = jsonable(rain_daily(m, km, Q, cli, sd, "dry", write_csv=False))
    pl, rl, dl = dict(_leaves(primary)), dict(_leaves(repro)), dict(_leaves(dry))
    repro_diff = max((abs(pl[k] - rl[k]) for k in pl if k in rl), default=0.0)
    moved = {k: {"primary": pl[k], "dry": dl[k]} for k in pl if k in dl and abs(pl[k] - dl[k]) > 1e-12}
    only = sorted(set(pl) ^ set(dl))
    g24p, g24d = primary["horizons"]["24"], dry["horizons"]["24"]
    out = {"note": "SENSITIVITY, not the pre-registered result. rain_daily recomputed with --wet-rule dry "
                   "(wet = station precip >= 0.01 in, trace = dry); primary = reports/eval-01/results.json rain_daily.",
           "rule_primary": primary["wet_rule"], "rule_dry": dry["wet_rule"],
           "primary_reproduced_max_abs_diff": repro_diff,
           "seconds": round(time.time() - t0, 1),
           "moved": moved, "n_leaves_compared": len(pl), "n_leaves_moved": len(moved),
           "keys_in_one_side_only": only,
           "unchanged_keys_note": "brier_market, cost_per_dollar_payout*, no_offer_share, no_quote_share, n_quoted, base_rate do not use the wet rule",
           "T3_brier_gain_24": {"primary": g24p["brier_gain"], "dry": g24d["brier_gain"],
                                "pass_primary": bool(g24p["brier_gain"] >= 0.02), "pass_dry": bool(g24d["brier_gain"] >= 0.02)},
           "rain_daily_dry": dry}
    (OUT / "sensitivity_trace_dry.json").write_text(json.dumps(jsonable(out), indent=1))

    def pv(k, d=3):
        x = moved.get(k)
        return "unchanged" if x is None else f"{x['primary']:.{d}f} -> {x['dry']:.{d}f}"

    L = ["# EVAL-01 sensitivity: trace = dry (labelled; primary numbers in results.json are unchanged)",
         f"Rule: primary `{primary['wet_rule']}` (frozen conditional, all-series trace YES share {primary['trace_yes_share']:.3f}); "
         f"this run `{dry['wet_rule']}`, the rule the product pays on. By scripts/eval02.py --wet-rule dry, rain_daily only ({out['seconds']:.0f} s).",
         f"Moved: {len(moved)} of {len(pl)} rain_daily numbers (exposure label, climatology, HE_wet, station agreement). Market Brier, cost per $ payout and no-offer shares do not use the rule. T3 at 24 h (gain >= 0.02) passes under the dry rule: {out['T3_brier_gain_24']['pass_dry']}.",
         "", "| number (key under `rain_daily`) | primary -> dry |", "|---|---|",
         f"| result_vs_station_agreement | {pv('result_vs_station_agreement')} |"]
    for h in HORIZONS:
        b = f"horizons.{h}"
        L.append(f"| {b}.brier_clim ; brier_gain | {pv(b + '.brier_clim')} ; {pv(b + '.brier_gain')} |")
    for h in HORIZONS:
        b = f"horizons.{h}.he_wet"
        L.append(f"| {b}.he_cover.est / he_ladder.est | {pv(b + '.he_cover.est', 2)} / {pv(b + '.he_ladder.est', 2)} |")
    (OUT / "sensitivity_trace_dry.md").write_text("\n".join(L) + "\n")
    log(f"sensitivity written: {len(moved)}/{len(pl)} numbers moved; primary reproduced within {repro_diff:.2e} ({time.time()-t0:.0f}s)")


@app.command()
def main(all: bool = typer.Option(False, "--all", help="run every part of EVAL-01"),
         report_only: bool = typer.Option(False, "--report-only", help="rebuild tables.md + figures from results.json"),
         wet_rule: str = typer.Option("prereg", "--wet-rule",
                                      help="prereg (default, the frozen conditional) | dry (sensitivity: trace = dry; rain rows only, "
                                           "writes only sensitivity_trace_dry.{json,md})")):
    if wet_rule not in ("prereg", "dry"):
        typer.echo("--wet-rule must be prereg or dry")
        raise typer.Exit(1)
    if wet_rule == "dry":
        m, km, Q, cli, sd = load()
        wet_rule_sensitivity(m, km, Q, cli, sd)
        return
    if report_only:
        R = json.loads((OUT / "results.json").read_text())
        (OUT / "tables.md").write_text(write_tables(R))
        figures(R, None)
        return
    if not all:
        typer.echo("use --all")
        raise typer.Exit(1)
    t0 = time.time()
    prereg = (OUT / "PREREG.md").read_text()
    frozen = re.search(r"Frozen: (\S+)", prereg).group(1)
    m, km, Q, cli, sd = load()
    events, excl, excl_list = build_citydays(m, Q, cli)
    # CLI-in-winner flag for the bracket mismatch
    for e in events:
        e["ts_in_winner_cli"] = e["ladder"].by_ticker()[e["winner"]].contains(e["T_CLI"]) if e["T_CLI"] is not None else None
    df = price_citydays(events)
    flag = {e["event"]: e["ts_in_winner_cli"] for e in events}
    df["ts_in_winner_cli"] = df.event.map(flag)
    log(f"priced {len(df)} rows")
    R = {"meta": {"run_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "prereg_frozen": frozen,
                  "s3": S3_STATUS, "seed": SEED, "draws": DRAWS, "block_days": BLOCK, "ref_units_for_fees": REF_UNITS,
                  "cap": CAP, "n_citydays": {k: int(v) for k, v in df[df.rule == "A"].city.value_counts().items()},
                  "n_citydays_rule_B": {k: int(v) for k, v in df[df.rule == "B"].city.value_counts().items()},
                  "date_range": {c: [str(g.date.min()), str(g.date.max())] for c, g in df[df.rule == "A"].groupby("city")},
                  "ts_not_in_winner_bracket": int((~df[df.rule == "A"].ts_in_winner).sum()),
                  "inputs": {"markets": "data/cache/kalshi/markets.parquet", "candles": "data/cache/kalshi/candles.parquet",
                             "kxrain": "data/cache/kalshi/kxrain_{markets,candles}.parquet (pulled 2026-09-30 by scripts/pull_kxrain.py)",
                             "cli": "data/cache/weather/official_daily.parquet", "iem": "data/cache/weather/stations_daily.parquet (ORD precip)",
                             "books": "prior/hl-mm-ins/reports/ins1/books.json"}},
         "exclusions": dict(excl), "exclusion_examples": {k: v[:15] for k, v in excl_list.items()}}
    R["temperature"] = temperature_metrics(df)
    R["mismatch"] = mismatch(df)
    R["ins1_check"] = ins1_check(df)
    log("rain daily")
    R["rain_daily"] = rain_daily(m, km, Q, cli, sd)
    log("rain monthly")
    R["rain_monthly"] = rain_monthly(m, Q)
    log("depth")
    R["depth"] = depth(m)
    R["verdicts"] = verdicts(R)
    st = df[(df.rule == "A") & (df.ts_source == "expiration_value")]
    liq = group_metrics(st[st.city.isin(LIQUID)], 24)
    R["sensitivity_prereg_strict_sample"] = {
        "note": "rule A, 24 h, city-days with a numeric expiration_value only (the sample as frozen, before deviation 1)",
        "n_cli_filled": int(((df.rule == "A") & (df.ts_source == "cli_fill")).sum()),
        "liquid_pooled": {k: liq[k] for k in ("n_citydays", "n_exec", "he_cover", "he_ladder", "overround", "no_offer_share")},
        "T1_pass": bool(liq["he_cover"]["est"] >= 0.85 and liq["overround"]["est"] <= 0.20),
        "T4_per_city_year": {f"{c} {y}": float(g.nooffer24.mean()) for (c, y), g in st[st.city.isin(LIQUID) & (st.year >= 2024)].groupby(["city", "year"])},
    }
    R["sensitivity_prereg_strict_sample"]["T4_pass"] = bool(max(R["sensitivity_prereg_strict_sample"]["T4_per_city_year"].values()) <= 0.10)
    R["meta"]["seconds"] = round(time.time() - t0, 1)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(jsonable(R), indent=1))
    (OUT / "tables.md").write_text(write_tables(jsonable(R)))
    df.to_csv(OUT / "citydays.csv.gz", index=False)
    figures(jsonable(R), df)
    log(f"done in {time.time()-t0:.0f}s; verdicts: {json.dumps(jsonable(R['verdicts']))}")


if __name__ == "__main__":
    app()
