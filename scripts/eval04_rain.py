"""EVAL-04 extension: weekly rain two-leg book (rules: reports/eval-04-05/PREREG-rain.md, frozen 18:45:48Z).

uv run python scripts/eval04_rain.py

Book: wet-day cover per business per week. Station leg = daily KXRAIN / KXRAINNYC binaries priced
and hedged at T-24h; residual leg = G1-P on weekly wet-day counts (PRISM per-cell spread, same
source at b and S). Reuses Phase 4's population and participation draw, THE clearing function
(wi.pool.sim.run_market), the house quote rule, the Kalshi fee and the capital rule.
Writes only reports/eval-04-05/rain_book.{json,md} and data/cache/eval04_rain/*. Deterministic
(seed 20260930).
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wi.eval03 import points as P3  # noqa: E402
from wi.exposure.priors import load_priors, triangular_draws  # noqa: E402
from wi.pool import capital as cap  # noqa: E402
from wi.pool import kalshi_leg as kl  # noqa: E402
from wi.pool import sim  # noqa: E402
from wi.pool.markout import summarize  # noqa: E402

CACHE4 = ROOT / "data" / "cache" / "eval04"
CACHE = ROOT / "data" / "cache" / "eval04_rain"
REPORT = ROOT / "reports" / "eval-04-05"
GHCN = ROOT / "data" / "raw" / "ghcnd_eval04"
SEED = 20260930
PREREG_UTC = "2026-09-30T18:45:48Z"
STATIONS5 = ["NYC", "EWR", "TTN", "MDW", "MIA"]          # catchment keys (Phase 4)
RAIN_STATION = {"NYC": "NYC", "EWR": "EWR", "TTN": "TTN", "MDW": "ORD", "MIA": "MIA"}   # settles
GHCN_PRCP = {"NYC": "USW00094728", "EWR": "USW00014734", "TTN": "USW00014792", "ORD": "USW00094846",
             "MIA": "USW00012839", "MDW": "USW00014819", "LGA": "USW00014732", "TEB": "USW00094741",
             "JFK": "USW00094789", "CDW": "USW00054743", "HPN": "USW00094745", "FRG": "USW00054787",
             "SMQ": "USW00054785", "VAY": "USW00093780", "LOT": "USC00117457", "PWK": "USW00004838",
             "DPA": "USW00094892", "OPF": "USW00012882", "TMB": "USW00012888", "HWO": "USW00092809",
             "FLL": "USW00012849", "FXE": "USW00012885"}
CELL_S = {"NYC": "40.7917_-73.9583", "EWR": "40.6667_-74.1667", "TTN": "40.2917_-74.8333",
          "MDW": "41.9583_-87.9167", "MIA": "25.7917_-80.3333"}
RA_LIST = {"NYC": ["NYC", "LGA", "TEB", "EWR", "JFK", "CDW", "HPN", "FRG"],
           "EWR": ["EWR", "NYC", "TEB", "CDW", "LGA", "JFK", "SMQ"],
           "TTN": ["TTN", "VAY", "SMQ"],
           "MDW": ["MDW", "ORD", "LOT", "PWK", "DPA"],
           "MIA": ["MIA", "OPF", "TMB", "HWO", "FLL", "FXE"]}
MISSING_19 = {"HPN", "FRG", "SMQ", "PWK", "DPA", "FXE"}     # Phase 3 rain truth points without a PRISM cell
CITY = {"NY": "NYC", "CHI": "MDW", "MIA": "MIA", "EWR": "EWR", "TTN": "TTN"}
WET_LEG = sim.Leg("station", 1.0, 0.0)          # $1 binary: scalar = dollars
RES_LEG = sim.Leg("residual", 14.0, 7.0)        # r in [-7, 7] wet days
COC = 0.15
CAP_DAY = 250_000.0
CAP_WEEK = 250_000.0
DEPTH_SHARE = 0.10
JOINT = ("2024-01-01", "2026-08-31")
OBS_RES = ("2025-01-06", "2026-08-30")
LONG_YEARS = (1999, 2025)
REPS, BLOCK = 10_000, 7
DEVIATIONS: list[str] = [
    "D1 (2026-09-30T18:52:06Z, after the first full run at 18:50Z): under the frozen limits (mu_r +/- l*MAD_r, l <= 0.25, MAD ~0.5 wet days) "
    "a hedger's residual premium is under one tick of the 14-wide scalar ($0.14 per unit-week), so only 2-4 % of residual units fill and the "
    "primary two-leg book is almost the station leg alone. Added a residual 'absorb-all' sensitivity: the house takes every business's "
    "residual units (q_r = -sum h per cell, like Phase 4 D4(b)); capital, R3 ratio and junior reported for it alongside the primary. "
    "Also: clearing - fair is now averaged over markets that traded, and the no-trade share is reported (first run averaged over no-trade "
    "markets too). The primary rules and verdicts are unchanged.",
]

CACHE.mkdir(parents=True, exist_ok=True)


def utcnow() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# ----------------------------------------------------------------------------- businesses
def businesses() -> pd.DataFrame:
    """One row per participating business (Phase 4 p2 draw), wet-day units h (+ = buys wet cover)."""
    pop = pd.read_parquet(CACHE4 / "population.parquet")
    part = dict(np.load(CACHE4 / "participants.npz"))["p2"]
    idx = np.repeat(np.arange(len(pop)), part)
    b = pop.iloc[idx].reset_index(drop=True)
    b["h"] = -(b["daily_rev"] * b["e_R_central"] / 100.0)
    b["pop_row"] = idx
    return b


def netting(b_pop: pd.DataFrame) -> dict:
    pop = pd.read_parquet(CACHE4 / "population.parquet")
    part = dict(np.load(CACHE4 / "participants.npz"))
    pri = load_priors()
    prow = pri.set_index("row_id")
    rev = pop["daily_rev"].to_numpy()
    rows = pop["row_id"].to_numpy()
    st = pop["station"].to_numpy()

    def nr_for(e_by_row: dict, npart: np.ndarray) -> dict:
        e = np.array([e_by_row[r] for r in rows])
        u = -(rev * e / 100.0) * npart
        out, Lp, Sp = {}, 0.0, 0.0
        for s in STATIONS5:
            m = st == s
            L, S = u[m & (u > 0)].sum(), -u[m & (u < 0)].sum()
            out[s] = float(2 * min(L, S) / (L + S)) if L + S > 0 else None
            Lp += L; Sp += S
        out["pooled"] = float(2 * min(Lp, Sp) / (Lp + Sp))
        return out

    central = {int(r): float(prow.loc[r, "e_R_central"]) for r in prow.index}
    npart = part["p2"]
    e_c = np.array([central[r] for r in rows])
    c = float((rev * npart * e_c).sum() / (rev * npart).sum())
    null = {r: 0.75 * c + 0.25 * v for r, v in central.items()}
    res = dict(central=nr_for(central, npart), null=nr_for(null, npart), null_c=c)
    for k in ("p0.5", "p10", "p2_persist"):
        res[f"central_{k}"] = nr_for(central, part[k])
    # ensemble
    draws = triangular_draws(pri, "e_R", 1000, SEED)
    rid = pri["row_id"].to_numpy()
    rows_u = sorted(set(rows))
    col = [int(np.flatnonzero(rid == r)[0]) for r in rows_u]
    E = draws[:, col]
    ens, nump, denp = {}, 0.0, 0.0
    for s in STATIONS5:
        m = st == s
        R = pd.Series(rev[m] * npart[m]).groupby(rows[m]).sum().reindex(rows_u, fill_value=0.0).to_numpy()
        U = -(E * R[None, :]) / 100.0
        L = np.where(U > 0, U, 0).sum(axis=1); S = np.where(U < 0, -U, 0).sum(axis=1)
        ens[s] = 2 * np.minimum(L, S) / (L + S)
        nump = nump + 2 * np.minimum(L, S); denp = denp + L + S
    ens["pooled"] = nump / denp
    res["ensemble"] = {s: dict(p10=float(np.percentile(v, 10)), p50=float(np.percentile(v, 50)),
                               p90=float(np.percentile(v, 90)), share_ge_0p25=float(np.mean(v >= 0.25))) for s, v in ens.items()}
    # leftover units (book population)
    lo = {}
    for s in STATIONS5:
        h = b_pop.loc[b_pop.station == s, "h"].to_numpy()
        L, S = h[h > 0].sum(), -h[h < 0].sum()
        lo[s] = dict(businesses=int((b_pop.station == s).sum()), L_units=float(L), S_units=float(S),
                     leftover_units_per_day=float(abs(L - S)), max_payout_per_day_usd=float(abs(L - S)),
                     max_payout_per_week_station_leg_usd=float(7 * abs(L - S)))
    res["leftover"] = lo
    n_mat = sum(1 for s in STATIONS5 if (res["central"][s] or 0) >= 0.25)
    res["R1"] = dict(stations_ge_0p25=n_mat, verdict="MATERIAL" if n_mat >= 3 else "NOT MATERIAL")
    return res


# ----------------------------------------------------------------------------- weather
def ghcn_prcp(code: str) -> pd.Series:
    """Daily wet flag (1/0) from GHCN-D PRCP: value > 0 or M-flag T; quality-flagged values dropped."""
    p = GHCN / f"{GHCN_PRCP[code]}.csv.gz"
    if not p.exists():
        return pd.Series(dtype=float, name=code)
    df = pd.read_csv(p, header=None, names=["id", "date", "el", "v", "m", "q", "s", "t"], dtype=str, keep_default_na=False)
    df = df[(df["el"] == "PRCP") & (df["q"] == "")]
    wet = ((df["v"].astype(int) > 0) | (df["m"] == "T")).astype(float)
    s = pd.Series(wet.to_numpy(), index=pd.to_datetime(df["date"], format="%Y%m%d"), name=code)
    return s[~s.index.duplicated()].sort_index()


def station_wet(long: bool = False) -> pd.DataFrame:
    """Columns = catchment keys; value = wet flag at the rain settlement station. CLI (official_daily)
    where the station issues one there (NYC, EWR, TTN, MIA), GHCN-D for ORD and for the long history."""
    out = {}
    off = pd.read_parquet(ROOT / "data" / "cache" / "weather" / "official_daily.parquet")
    off["date"] = pd.to_datetime(off["date_local"])
    for s in STATIONS5:
        g = ghcn_prcp(RAIN_STATION[s])
        if not long and RAIN_STATION[s] in set(off["station"]):
            o = off[off.station == RAIN_STATION[s]].set_index("date")["precip_in"]
            o = (o > 0).astype(float).where(o.notna())
            g = o.combine_first(g)
        out[s] = g
    return pd.DataFrame(out)


def all_wet_for(codes: list[str]) -> pd.DataFrame:
    off = pd.read_parquet(ROOT / "data" / "cache" / "weather" / "official_daily.parquet")
    off["date"] = pd.to_datetime(off["date_local"])
    out = {}
    for c in codes:
        g = ghcn_prcp(c)
        if c in set(off["station"]):
            o = off[off.station == c].set_index("date")["precip_in"]
            g = (o > 0).astype(float).where(o.notna()).combine_first(g)
        out[c] = g
    return pd.DataFrame(out)


def markov_fair(W: pd.DataFrame, fit: tuple[int, int]) -> pd.DataFrame:
    """Scenario fair value mu_d = P(wet_d | station, month, wet_{d-1}) fitted on `fit` years."""
    mu = pd.DataFrame(index=W.index, columns=W.columns, dtype=float)
    for s in W.columns:
        w = W[s]
        prev = w.shift(1, freq="D").reindex(w.index)
        f = pd.DataFrame({"w": w, "p": prev, "m": w.index.month})
        ff = f[(f.index.year >= fit[0]) & (f.index.year <= fit[1])].dropna()
        tab = ff.groupby(["m", "p"])["w"].mean()
        clim = ff.groupby("m")["w"].mean()
        key = list(zip(f["m"], f["p"]))
        vals = [tab.get(k, np.nan) if not np.isnan(k[1]) else clim.get(k[0], np.nan) for k in key]
        mu[s] = vals
    return mu


def prism_cells() -> tuple[dict, dict]:
    """Per station disc: daily wet flag per cell on the CLI day (label - 1) and cell coordinates."""
    wet, coords = {}, {}
    for s in STATIONS5:
        fs = sorted(glob.glob(str(ROOT / f"data/cache/grid_disc/source=prism/station={s}/part-*.parquet")))
        g = pd.concat([pd.read_parquet(f, columns=["cell_id", "lat", "lon", "label_day", "cli_day", "prcp_hundredths_in"]) for f in fs])
        g["cli_day"] = pd.to_datetime(g["label_day"]) - pd.Timedelta(days=1)     # CONVENTIONS §3 / eval03.align
        pv = g.pivot_table(index="cli_day", columns="cell_id", values="prcp_hundredths_in", aggfunc="first")
        pv = pv.reindex(pd.date_range(pv.index.min(), pv.index.max()))
        wet[s] = (pv >= 1).astype(float).where(pv.notna())
        coords[s] = g.drop_duplicates("cell_id").set_index("cell_id")[["lat", "lon"]]
    return wet, coords


def weekly_count(daily: pd.DataFrame) -> pd.DataFrame:
    """Mon-Sun wet-day counts labelled by Sunday; NaN unless all 7 days present."""
    cnt = daily.resample("W-SUN").count()
    tot = daily.resample("W-SUN").sum(min_count=1)
    return tot.where(cnt == 7)


def assign_cells(b: pd.DataFrame, coords: dict) -> pd.Series:
    out = np.empty(len(b), dtype=object)
    for s in STATIONS5:
        m = (b.station == s).to_numpy()
        c = coords[s]
        la, lo = b.loc[m, "lat"].to_numpy(), b.loc[m, "lon"].to_numpy()
        d = (la[:, None] - c["lat"].to_numpy()[None, :]) ** 2 + ((lo[:, None] - c["lon"].to_numpy()[None, :]) * np.cos(np.radians(la[:, None]))) ** 2
        out[m] = c.index.to_numpy()[d.argmin(axis=1)]
    return pd.Series(out, index=b.index)


def footprint19(coords: dict) -> dict:
    """Cell -> True if the cell centre's nearest Phase 3 rain truth point (its market's list) has a PRISM cell."""
    out = {}
    for s in STATIONS5:
        pts = P3.TRUTH["rain"][s]
        for cid, r in coords[s].iterrows():
            d = [P3.haversine_km((r.lat, r.lon), p) for p in pts]
            out[(s, cid)] = pts[int(np.argmin(d))] not in MISSING_19
    return out


# ----------------------------------------------------------------------------- Kalshi rain
def kalshi_rain() -> tuple[pd.DataFrame, pd.DataFrame]:
    m1 = pd.read_parquet(ROOT / "data/cache/kalshi/markets.parquet")
    m1 = m1[(m1.series_ticker == "KXRAINNYC") & m1.settled].copy()
    m1["station"] = "NYC"
    m2 = pd.read_parquet(ROOT / "data/cache/kalshi/kxrain_markets.parquet")
    m2 = m2[(m2.series_ticker == "KXRAIN") & m2.settled].copy()
    m2["station"] = m2["city"].map(CITY)
    cols = ["series_ticker", "market_ticker", "station", "event_date", "close_time", "result", "volume", "rules_primary"]
    m1["event_date"] = pd.to_datetime(m1["event_date"]); m2["event_date"] = pd.to_datetime(m2["event_date"])
    m1 = m1[(m1.event_date >= "2025-01-01") & (m1.event_date <= "2026-07-14")]
    m2 = m2[m2.event_date <= "2026-09-28"]
    m = pd.concat([m1[cols], m2[cols]]).reset_index(drop=True)
    c1 = pd.read_parquet(ROOT / "data/cache/kalshi/candles.parquet", columns=["market_ticker", "ts", "yes_ask_close", "yes_bid_close", "volume"])
    c1 = c1[c1.market_ticker.isin(set(m1.market_ticker))]
    c2 = pd.read_parquet(ROOT / "data/cache/kalshi/kxrain_candles.parquet", columns=["market_ticker", "ts", "yes_ask_close", "yes_bid_close", "volume"])
    c2 = c2[c2.market_ticker.isin(set(m2.market_ticker))]
    c = pd.concat([c1, c2]).dropna(subset=["ts"]).reset_index(drop=True)
    c["ts"] = c["ts"].astype("datetime64[ms, UTC]")
    return m, c


def quotes(m: pd.DataFrame, c: pd.DataFrame, hours: float = 24.0) -> pd.DataFrame:
    """Ask/bid of the last candle with end ts <= close - hours (CONVENTIONS §5); volume before the cutoff."""
    t = m[["market_ticker", "close_time"]].copy()
    t["t"] = (t["close_time"] - pd.Timedelta(hours=hours)).astype("datetime64[ms, UTC]")
    j = pd.merge_asof(t.sort_values("t"), c.sort_values("ts")[["market_ticker", "ts", "yes_ask_close", "yes_bid_close"]],
                      left_on="t", right_on="ts", by="market_ticker", direction="backward").set_index("market_ticker")
    out = m.copy()
    out["ask"] = out.market_ticker.map(j["yes_ask_close"])
    out["bid"] = out.market_ticker.map(j["yes_bid_close"])
    out["quote_ts"] = out.market_ticker.map(j["ts"])
    out["cutoff"] = out.market_ticker.map(j["t"])
    a, b = out["ask"], out["bid"]
    out["valid"] = a.notna() & b.notna() & (a > 0) & ~((a >= 0.99) & (b < 0.90))
    out["mu"] = (a + b) / 2.0
    cc = c.merge(t[["market_ticker", "t"]], on="market_ticker")
    vol_pre = cc[cc["ts"] <= cc["t"]].groupby("market_ticker")["volume"].sum()
    out["vol_pre_cutoff"] = out.market_ticker.map(vol_pre).fillna(0.0)
    out["x"] = (out["result"] == "yes").astype(float)
    return out


# ----------------------------------------------------------------------------- auctions
def charges(Wl: pd.DataFrame, mul: pd.DataFrame, rweek: dict) -> dict:
    """(CoC/365) x standalone per-unit ES99 of a 30-day loss (historical overlapping windows)."""
    lam = COC / 365.0
    out = {}
    for s in STATIONS5:
        u = (Wl[s] - mul[s]).dropna()
        roll = u.rolling(30).sum().dropna().to_numpy()
        out[(s, "station")] = dict(sell=lam * cap.es(roll, 0.99), buy=lam * cap.es(-roll, 0.99))
        r = rweek[s]
        rr = (r - r.mean()).stack().dropna()
        tot = rr.groupby(level=0).mean()                        # per-unit average cell residual per week
        roll = tot.rolling(4).sum().dropna().to_numpy() if len(tot) > 8 else np.array([0.0])
        out[(s, "residual")] = dict(sell=lam * cap.es(roll, 0.99) if len(roll) else 0.0,
                                    buy=lam * cap.es(-roll, 0.99) if len(roll) else 0.0)
    return out


def station_auctions(q: pd.DataFrame, biz: pd.DataFrame, ch: dict) -> pd.DataFrame:
    rows = []
    hs = {s: biz.loc[biz.station == s, "h"].to_numpy() for s in STATIONS5}
    for date, day in q.groupby("event_date"):
        cap_each = CAP_DAY / len(day)
        for _, e in day.iterrows():
            s = e["station"]
            rng = np.random.default_rng([SEED, STATIONS5.index(s), date.toordinal(), 7])
            c_ = ch[(s, "station")]
            m = sim.run_market(hs[s], WET_LEG, float(e["mu"]), 0.0, rng, c_["sell"], c_["buy"], cap_each)
            r = m["r"]
            st_ = sim.settle_market(m, float(e["x"]))
            fz = sim.fees(m)
            gross = int(m["qty"].sum())
            rows.append(dict(date=date, station=s, market=e["market_ticker"], mu=float(e["mu"]), ask=float(e["ask"]),
                             bid=float(e["bid"]), x=float(e["x"]), p_star=r.p_star, cap_off=m["cap_off"], cap_bid=m["cap_bid"], q_star=r.q_star, ask_tick=m["ask_tick"],
                             bid_tick=m["bid_tick"], house_bid=m["house_bid"], house_off=m["house_off"],
                             bus_bid=int(m["fills"][m["is_bid"]].sum()), bus_off=int(m["fills"][~m["is_bid"]].sum()),
                             gross_qty=gross, bid_qty=int(m["qty"][m["is_bid"]].sum()), off_qty=int(m["qty"][~m["is_bid"]].sum()),
                             cap_usd=cap_each, mo_settle=st_["mo_settle"], vol_pre_cutoff=float(e["vol_pre_cutoff"]), **fz))
    return pd.DataFrame(rows)


def residual_auctions(rweek: dict, groups: dict, ch: dict, weeks: pd.DatetimeIndex, leg_key: str = "residual") -> pd.DataFrame:
    """groups[s] = {contract_id: h array}. rweek[s]: weekly r per contract (DataFrame, index Sunday)."""
    rows = []
    for w in weeks:
        mk = []
        for s in STATIONS5:
            R = rweek[s]
            if w not in R.index:
                continue
            hist = R[R.index < w - pd.Timedelta(days=6)]            # weeks ending before this week's Monday
            for cid, h in groups[s].items():
                if cid not in R.columns or np.isnan(R.loc[w, cid]):
                    continue
                hc = hist[cid].dropna()
                mu = float(hc.mean()) if len(hc) >= 8 else 0.0
                mad = float(np.abs(hc - mu).mean()) if len(hc) >= 8 else 0.3
                mk.append((s, cid, h, mu, mad, float(R.loc[w, cid])))
        if not mk:
            continue
        gross = np.array([np.rint(np.abs(h) * RES_LEG.width).sum() for _, _, h, _, _, _ in mk], float)
        for (s, cid, h, mu, mad, rv), g in zip(mk, gross):
            cap_m = CAP_WEEK * g / gross.sum() if gross.sum() > 0 else 0.0
            rng = np.random.default_rng([SEED, STATIONS5.index(s), w.toordinal(), _cid_int(cid), 9])
            c_ = ch[(s, leg_key)]
            m = sim.run_market(h, RES_LEG, mu, mad, rng, c_["sell"], c_["buy"], cap_m)
            x = (rv + 7.0) / 14.0
            st_ = sim.settle_market(m, x)
            fz = sim.fees(m)
            rows.append(dict(week=w, station=s, cell=cid, mu=mu, mad=mad, r=rv, x=x, mu_s=m["mu_s"], p_star=m["r"].p_star, cap_off=m["cap_off"],
                             q_star=m["r"].q_star, house_bid=m["house_bid"], house_off=m["house_off"],
                             gross_qty=int(m["qty"].sum()), bus_bid=int(m["fills"][m["is_bid"]].sum()),
                             bus_off=int(m["fills"][~m["is_bid"]].sum()), cap_usd=cap_m, mo_settle=st_["mo_settle"], **fz))
    return pd.DataFrame(rows)


def _cid_int(cid: str) -> int:
    """Deterministic integer from a cell id (Python's hash() is salted per process)."""
    return int(sum((i + 1) * ord(ch) for i, ch in enumerate(str(cid))) % (2**31))


def add_hedge(a: pd.DataFrame, depth: dict, mode: str = "proxy") -> pd.DataFrame:
    """Kalshi paper hedge of the house net station position at the T-24h quote."""
    a = a.copy()
    net = a["house_bid"] - a["house_off"]                         # + = house long wet
    units, pnl, fees_ = [], [], []
    for n, s, ask, bid, x in zip(net, a["station"], a["ask"], a["bid"], a["x"]):
        need = abs(int(n))
        capn = need if mode == "full" else (0 if mode == "none" else min(need, int(depth[s])))
        if capn <= 0:
            units.append(0); pnl.append(0.0); fees_.append(0.0); continue
        side = +1 if n < 0 else -1                                 # short wet -> buy YES
        px = ask if side > 0 else bid
        f = kl.fee(capn, px)
        units.append(side * capn); pnl.append(side * capn * (x - px) - f); fees_.append(f)
    a["hedge_units"] = units; a["hedge_pnl"] = pnl; a["hedge_fees"] = fees_
    a["net_short"] = np.maximum(-net, 0)
    return a


# ----------------------------------------------------------------------------- capital
def cap_series(pnl: pd.Series, H: int, fc_per_day: float, block: int = BLOCK, reps: int = REPS, seed: int = SEED) -> dict:
    """Phase 4 capital rule on a daily P&L series with gaps: historical h-day windows inside
    contiguous segments; bootstrap of h-day paths from 7-day blocks that do not cross a gap."""
    s = pnl.sort_index()
    full = s.reindex(pd.date_range(s.index.min(), s.index.max()))
    v = full.to_numpy(float)
    ok = ~np.isnan(v)
    x = np.nan_to_num(v)
    cs = np.concatenate([[0.0], np.cumsum(x)])
    okc = np.concatenate([[0], np.cumsum(ok)])
    n = len(v)
    starts = np.arange(0, n - H + 1)
    good = (okc[starts + H] - okc[starts]) == H
    hist = -(cs[starts + H] - cs[starts])[good]
    bstarts = np.arange(0, n - block + 1)
    bgood = bstarts[(okc[bstarts + block] - okc[bstarts]) == block]
    rng = np.random.default_rng(seed)
    nb = -(-H // block)
    pick = bgood[rng.integers(0, len(bgood), size=(reps, nb))]
    paths = x[pick[:, :, None] + np.arange(block)].reshape(reps, -1)[:, :H]
    boot = -paths.sum(axis=1)
    es99, es95 = cap.es(boot, 0.99), cap.es(boot, 0.95)
    worst = float(hist.max()) if len(hist) else float("nan")
    fc = H * fc_per_day
    c = min(fc, max(es99, worst if len(hist) else 0.0, 0.0))
    return dict(H=H, C=c, ES99=es99, ES95_junior=min(es95, c), worst_window=worst, FC=fc,
                binding=("FC" if c == fc else ("worst_window" if worst >= es99 else "ES99")),
                n_hist_windows=int(len(hist)), n_days=int(ok.sum()))


def book_from_run(st: pd.DataFrame, rs: pd.DataFrame, biz: pd.DataFrame, cellcol: str = "cell") -> dict:
    """Average house position per (station, month) station leg [after hedge] and per (station, contract, month) residual."""
    a = st.copy()
    a["month"] = pd.to_datetime(a["date"]).dt.month
    a["pos"] = a["house_bid"] - a["house_off"] + a["hedge_units"]
    a["fill_pos"] = a["house_bid"] - a["house_off"]
    dem = {s: float(-biz.loc[biz.station == s, "h"].sum()) for s in STATIONS5}
    tot_pos, tot_dem = a["pos"].sum(), sum(dem[s] * (a.station == s).sum() for s in STATIONS5)
    pooled_ratio = tot_pos / tot_dem if tot_dem else 0.0
    pooled_fill = a["fill_pos"].sum() / tot_dem if tot_dem else 0.0
    q_st, q_fill, src, price = {}, {}, {}, {}
    for s in STATIONS5:
        g = a[a.station == s]
        ratio = g["pos"].sum() / (dem[s] * len(g)) if len(g) and dem[s] else pooled_ratio
        rfill = g["fill_pos"].sum() / (dem[s] * len(g)) if len(g) and dem[s] else pooled_fill
        for mo in range(1, 13):
            gm = g[g.month == mo]
            if len(gm) >= 5:
                q_st[(s, mo)] = float(gm["pos"].mean()); q_fill[(s, mo)] = float(gm["fill_pos"].mean())
                price[(s, mo)] = float((gm["p_star"] / 100).mean()); src[(s, mo)] = f"observed ({len(gm)} days)"
            else:
                q_st[(s, mo)] = float(ratio * dem[s]); q_fill[(s, mo)] = float(rfill * dem[s])
                price[(s, mo)] = float((g["p_star"] / 100).mean()) if len(g) else float((a["p_star"] / 100).mean())
                src[(s, mo)] = "ratio x demand (Phase 4 D4 rule)" + ("" if len(g) else ", pooled ratio")
    r = rs.copy()
    r["month"] = pd.to_datetime(r["week"]).dt.month
    r["pos"] = (r["house_bid"] - r["house_off"]) / RES_LEG.width
    q_r = r.groupby(["station", cellcol, "month"])["pos"].mean().to_dict()
    mu_r = r.groupby(["station", cellcol])["mu"].mean().to_dict()
    return dict(q_st=q_st, q_fill=q_fill, src=src, price=price, q_r=q_r, mu_r_quote=mu_r)


def station_pnl(book: dict, W: pd.DataFrame, mu: pd.DataFrame, key: str = "q_st") -> pd.Series:
    mo = W.index.month
    tot = pd.Series(0.0, index=W.index)
    valid = pd.Series(False, index=W.index)
    for s in STATIONS5:
        q = np.array([book[key][(s, m)] for m in mo])
        u = (W[s] - mu[s]).to_numpy()
        tot += np.nan_to_num(q * u)
        valid |= ~np.isnan(u)
    return tot.where(valid)


def residual_pnl(book: dict, rweek: dict, index: pd.DatetimeIndex, keep: dict | None = None) -> pd.Series:
    """Weekly residual P&L (house long q_r) at in-sample cell mean mu_r, booked on Sunday; 0 on void weeks."""
    out = pd.Series(0.0, index=index)
    for s in STATIONS5:
        R = rweek[s]
        mu_r = R.mean()
        for (ss, cid, m), q in book["q_r"].items():
            if ss != s or cid not in R.columns or (keep is not None and not keep.get((s, cid), True)):
                continue
            col = R[cid]
            wk = col.index[(col.index.month == m) & col.notna()]
            wk = wk[wk.isin(index)]
            out.loc[wk] += q * (col.loc[wk] - mu_r[cid]).to_numpy()
    return out


def fc_notional(book: dict, months: list[int], keep: dict | None = None, residual: bool = True) -> tuple[float, float, float, float]:
    """Average daily full collateral and notional: (fc_station, fc_residual, not_station, not_residual)."""
    fs = fr = ns = nr_ = 0.0
    for m in months:
        for s in STATIONS5:
            q, p = book["q_st"][(s, m)], book["price"][(s, m)]
            fs += (-q) * (1 - p) if q < 0 else q * p
            ns += abs(q)
        if residual:
            for (s, cid, mm), q in book["q_r"].items():
                if mm != m or (keep is not None and not keep.get((s, cid), True)):
                    continue
                mu = book["mu_r_quote"].get((s, cid), 0.0)
                fr += ((-q) * (7 - mu) if q < 0 else q * (7 + mu)) / 7.0
                nr_ += abs(q) * 14.0 / 7.0
    n = len(months)
    return fs / n, fr / n, ns / n, nr_ / n


def capital_pack(pnl: pd.Series, fcd: float, nod: float, horizons=(30, 153)) -> dict:
    out = {"fc_per_day": fcd, "notional_per_day": nod}
    for Hh in horizons:
        c = cap_series(pnl, Hh, fcd)
        c["CPC_notional"] = c["C"] / (Hh * nod) if nod else None
        out[f"H{Hh}"] = c
    return out


# ----------------------------------------------------------------------------- junior
def split(prem, rm, t, rule):
    tre = t * rm
    sen = 0.20 * (prem - tre) if rule == "spec" else 0.20 * (1 - t) * rm
    return tre, sen, prem - tre - sen


def observed_junior(st: pd.DataFrame, rs: pd.DataFrame, J0: float, months=None) -> dict:
    a = st.copy(); a["date"] = pd.to_datetime(a["date"])
    p = a["p_star"] / 100.0
    a["prem"] = p * a["house_off"] + (1 - p) * a["house_bid"]
    a["rm"] = a["prem"] - (a["mu"] * a["house_off"] + (1 - a["mu"]) * a["house_bid"])
    a["pay"] = a["x"] * a["house_off"] + (1 - a["x"]) * a["house_bid"]
    assert np.allclose(a["prem"] - a["pay"], a["mo_settle"], atol=1e-6)
    r = rs.copy(); r["date"] = pd.to_datetime(r["week"])
    if months:
        a = a[a.date.dt.month.isin(months)]; r = r[r.date.dt.month.isin(months)]
    out = {}
    for rule in ("spec", "margin"):
        for t in (0.10, 0.20):
            per = {}
            for y in sorted(set(a.date.dt.year) | set(r.date.dt.year)):
                g, gr = a[a.date.dt.year == y], r[r.date.dt.year == y]
                tre, sen, jp = split(g["prem"].sum(), g["rm"].sum(), t, rule)
                j = jp - g["pay"].sum() + gr["mo_settle"].sum() + g["hedge_pnl"].sum()
                per[int(y)] = dict(station_days=int(len(g)), residual_markets=int(len(gr)), station_premium=float(g["prem"].sum()),
                                   station_rm=float(g["rm"].sum()), station_payouts=float(g["pay"].sum()),
                                   residual_pnl=float(gr["mo_settle"].sum()), hedge_pnl=float(g["hedge_pnl"].sum()),
                                   senior=float(sen), treasury=float(tre), junior_pnl=float(j), junior_return=float(j / J0))
            out[f"{rule}_t{int(t * 100)}"] = per
    return out


def model_junior(book: dict, Wl: pd.DataFrame, mul: pd.DataFrame, res_daily: pd.Series, J0: float,
                 kal: dict, season: str) -> dict:
    """Bootstrap seasons: station leg from the long history (quote rule on the scenario fair, Kalshi hedge
    at scenario fair + observed half-spread + fee), residual from a random joint-window year (2024/2025)."""
    if season == "MaySep":
        days = pd.date_range("2001-05-01", "2001-09-30")
    else:
        days = pd.date_range("2001-01-01", "2001-12-31")
    md = days.strftime("%m-%d")
    yrs = list(range(LONG_YEARS[0], LONG_YEARS[1] + 1))
    ND = len(days)
    comp = {k: np.zeros((len(yrs), ND)) for k in ("prem", "rm", "pay", "hedge")}
    for i, y in enumerate(yrs):
        idx = pd.to_datetime([f"{y}-{x}" for x in md])
        for s in STATIONS5:
            w = Wl[s].reindex(idx).to_numpy()
            mu = mul[s].reindex(idx).to_numpy()
            months = idx.month.to_numpy()
            qf = np.array([book["q_fill"][(s, m)] for m in months])            # house fill position (neg = sold)
            qh = np.array([book["q_st"][(s, m)] - book["q_fill"][(s, m)] for m in months])   # hedge units (+ long)
            ask_t = np.maximum(np.ceil(100 * mu - 1e-9), np.floor(100 * mu) + 1) / 100.0
            sold = np.maximum(-qf, 0)
            prem = sold * ask_t
            rm = sold * (ask_t - mu)
            pay = sold * w
            half = kal["half_spread"].get(s, kal["half_spread_pooled"])
            fee_c = kal["fee_per_contract"].get(s, kal["fee_per_contract_pooled"])
            hedge = qh * (w - (mu + half)) - np.abs(qh) * fee_c
            for k, v in (("prem", prem), ("rm", rm), ("pay", pay), ("hedge", hedge)):
                comp[k][i] += np.nan_to_num(v)
    # residual: joint-window years 2024, 2025 at the same calendar dates
    ry = [2024, 2025]
    resm = np.zeros((len(ry), ND))
    for i, y in enumerate(ry):
        idx = pd.to_datetime([f"{y}-{x}" for x in md])
        resm[i] = np.nan_to_num(res_daily.reindex(idx).to_numpy())
    rng = np.random.default_rng(SEED)
    nb = -(-ND // BLOCK)
    ys = rng.integers(0, len(yrs), size=(REPS, nb))
    yr = rng.integers(0, len(ry), size=(REPS, nb))
    sums = {k: np.zeros(REPS) for k in ("prem", "rm", "pay", "hedge", "res")}
    for b_ in range(nb):
        cols = slice(b_ * BLOCK, min((b_ + 1) * BLOCK, ND))
        for k in ("prem", "rm", "pay", "hedge"):
            sums[k] += comp[k][ys[:, b_], cols].sum(axis=1)
        sums["res"] += resm[yr[:, b_], cols].sum(axis=1)
    trip = rng.integers(0, REPS, size=(REPS, 3))
    out = dict(season=season, n_days=ND, station_years=[yrs[0], yrs[-1]], residual_years=ry, splits={},
               mean_components_per_season={k: float(v.mean()) for k, v in sums.items()})
    hist = {k: comp[k].sum(axis=1) for k in comp}
    for rule in ("spec", "margin"):
        for t in (0.10, 0.20):
            tre, sen, jp = split(sums["prem"], sums["rm"], t, rule)
            j = jp - sums["pay"] + sums["hedge"] + sums["res"]
            b = j / J0
            tr = j[trip].sum(axis=1) / J0
            tre_h, sen_h, jp_h = split(hist["prem"], hist["rm"], t, rule)
            jh = (jp_h - hist["pay"] + hist["hedge"] + resm.sum(axis=1).mean()) / J0
            out["splits"][f"{rule}_t{int(t * 100)}"] = dict(
                median=float(np.median(b)), p05_1in20=float(np.percentile(b, 5)), p01=float(np.percentile(b, 1)),
                worst=float(b.min()), share_negative=float((b < 0).mean()), three_season_sum_p05=float(np.percentile(tr, 5)),
                rule_1in20_positive_over_3y=bool(np.percentile(tr, 5) > 0),
                hist_station_years_median=float(np.median(jh)), hist_worst=float(jh.min()), hist_worst_year=int(yrs[int(jh.argmin())]),
                senior_mean=float(np.mean(sen)), treasury_mean=float(np.mean(tre)))
    return out


# ----------------------------------------------------------------------------- look-ahead check
def lookahead_check(qdf: pd.DataFrame, mk: pd.DataFrame, cand: pd.DataFrame, biz: pd.DataFrame, ch: dict) -> dict:
    rng0 = np.random.default_rng(SEED)
    pick = qdf.iloc[rng0.choice(len(qdf), size=min(20, len(qdf)), replace=False)]
    bad = 0
    for _, e in pick.iterrows():
        m1 = mk[mk.market_ticker == e["market_ticker"]]
        c = cand[cand.market_ticker == e["market_ticker"]].copy()
        post = c["ts"] > e["cutoff"]
        c2 = c.copy()
        c2.loc[post, "yes_ask_close"] = np.clip(c2.loc[post, "yes_ask_close"] + 0.3, 0.01, 0.99)
        c2.loc[post, "yes_bid_close"] = np.clip(c2.loc[post, "yes_bid_close"] + 0.3, 0.0, 0.98)
        m2 = m1.copy(); m2["result"] = "no" if e["result"] == "yes" else "yes"
        qa, qb = quotes(m1, c).iloc[0], quotes(m2, c2).iloc[0]
        s = e["station"]; h = biz.loc[biz.station == s, "h"].to_numpy()
        ra = sim.run_market(h, WET_LEG, float(qa["mu"]), 0.0, np.random.default_rng([SEED, 1]), ch[(s, "station")]["sell"], ch[(s, "station")]["buy"], 50_000)
        rb = sim.run_market(h, WET_LEG, float(qb["mu"]), 0.0, np.random.default_rng([SEED, 1]), ch[(s, "station")]["sell"], ch[(s, "station")]["buy"], 50_000)
        same = qa["mu"] == qb["mu"] and ra["r"].p_star == rb["r"].p_star and ra["r"].fills == rb["r"].fills and np.array_equal(ra["tick"], rb["tick"])
        bad += int(not same)
    assert bad == 0, f"look-ahead: {bad} markets moved when post-cutoff data changed"
    return dict(markets_checked=int(len(pick)), moved=bad)


# ----------------------------------------------------------------------------- main
def main() -> None:
    t0 = time.time()
    R: dict = dict(prereg="reports/eval-04-05/PREREG-rain.md", prereg_frozen_utc=PREREG_UTC, seed=SEED)
    biz = businesses()
    R["netting"] = netting(biz)
    print("netting", json.dumps(R["netting"]["central"]), flush=True)

    # --- weather
    Wj = station_wet(long=False)
    long_all = station_wet(long=True)
    Wl = long_all.copy()
    Wl = Wl[(Wl.index.year >= LONG_YEARS[0]) & (Wl.index.year <= LONG_YEARS[1])]
    Wl = Wl.reindex(pd.date_range(f"{LONG_YEARS[0]}-01-01", f"{LONG_YEARS[1]}-12-31"))
    R["history"] = dict(long_missing_station_days={s: int(Wl[s].isna().sum()) for s in STATIONS5},
                        long_days=int(len(Wl)))
    mul = markov_fair(Wl, LONG_YEARS)
    Wj = Wj.loc[JOINT[0]:JOINT[1]]
    muj = markov_fair(long_all.loc["1998-01-01":], LONG_YEARS).reindex(Wj.index)
    # Markov table with prev from the CLI series for the joint window
    muj2 = pd.DataFrame(index=Wj.index, columns=STATIONS5, dtype=float)
    for s in STATIONS5:
        f = pd.DataFrame({"w": long_all[s], "p": long_all[s].shift(1, freq="D").reindex(long_all[s].index)})
        f = f[(f.index.year >= LONG_YEARS[0]) & (f.index.year <= LONG_YEARS[1])].dropna()
        tab = f.groupby([f.index.month, "p"])["w"].mean()
        prev = Wj[s].shift(1, freq="D").reindex(Wj.index)
        muj2[s] = [tab.get((m, p), np.nan) for m, p in zip(Wj.index.month, prev)]
    muj = muj2.fillna(muj)

    wetc, coords = prism_cells()
    biz["cell"] = assign_cells(biz, coords)
    foot = footprint19(coords)
    rweek, rweek_raw = {}, {}
    for s in STATIONS5:
        wk = weekly_count(wetc[s].loc[JOINT[0]:])
        wk = wk[wk.index <= pd.Timestamp(JOINT[1]) + pd.Timedelta(days=6)]
        wk = wk[wk.index <= "2026-09-27"]
        cs = CELL_S[s]
        assert cs in wk.columns, (s, cs)
        cells = sorted(set(biz.loc[biz.station == s, "cell"]))
        rweek[s] = wk[cells].sub(wk[cs], axis=0)
        rweek_raw[s] = wk
    groups = {s: {cid: g["h"].to_numpy() for cid, g in biz[(biz.station == s) & (biz.cell != CELL_S[s])].groupby("cell")} for s in STATIONS5}
    R["cells"] = {s: dict(businesses=int((biz.station == s).sum()), cells_with_business=int(biz.loc[biz.station == s, "cell"].nunique()),
                          businesses_in_S_cell=int(((biz.station == s) & (biz.cell == CELL_S[s])).sum()),
                          cells_in_19_footprint=int(sum(foot[(s, c)] for c in set(biz.loc[biz.station == s, "cell"]))),
                          weekly_r_sd=float(np.nanstd(rweek[s].to_numpy())), weekly_r_mean=float(np.nanmean(rweek[s].to_numpy())))
                 for s in STATIONS5}
    # residual NR per cell (units h have the same sign per business on both legs)
    Lc = Sc = mm = 0.0
    for s in STATIONS5:
        for cid, h in groups[s].items():
            L_, S_ = h[h > 0].sum(), -h[h < 0].sum()
            Lc += L_ + 0; Sc += S_; mm += 2 * min(L_, S_)
    R["netting"]["residual_cell_level_pooled"] = float(mm / (Lc + Sc)) if Lc + Sc else None

    # --- Kalshi
    mk, cand = kalshi_rain()
    q_all = quotes(mk, cand)
    q = q_all[q_all.valid & q_all.mu.notna()].copy()
    R["kalshi_sample"] = dict(settled=int(len(q_all)), valid_at_T24=int(len(q)),
                              by_station={s: dict(days=int((q.station == s).sum()),
                                                  first=str(q.loc[q.station == s, "event_date"].min().date()) if (q.station == s).any() else None,
                                                  last=str(q.loc[q.station == s, "event_date"].max().date()) if (q.station == s).any() else None)
                                          for s in STATIONS5},
                              invalid_or_missing_quote=int((~q_all.valid).sum()))
    depth = {s: DEPTH_SHARE * float(q.loc[q.station == s, "vol_pre_cutoff"].median()) for s in STATIONS5}
    R["depth_proxy"] = dict(rule="10 % of the median volume traded before the T-24h cutoff per settled market",
                            contracts_per_city_day={s: int(depth[s]) for s in STATIONS5},
                            median_vol_pre_cutoff={s: float(q.loc[q.station == s, "vol_pre_cutoff"].median()) for s in STATIONS5},
                            median_total_volume={s: float(q.loc[q.station == s, "volume"].median()) for s in STATIONS5},
                            monthly_nyc_ladder_book_median_within_3c=550)

    # --- charges + look-ahead check
    ch = charges(Wl, mul, rweek)
    R["charges_per_unit"] = {f"{k[0]}/{k[1]}": v for k, v in ch.items()}
    R["lookahead_check"] = lookahead_check(q, mk, cand, biz, ch)
    print("lookahead ok", time.time() - t0, flush=True)

    # --- observed runs
    st = station_auctions(q, biz, ch)
    weeks = pd.date_range("2025-01-12", OBS_RES[1], freq="W-SUN")
    rs = residual_auctions(rweek, groups, ch, weeks)
    print("auctions", len(st), len(rs), round(time.time() - t0, 1), flush=True)
    runs = {mode: add_hedge(st, depth, mode) for mode in ("proxy", "none", "full")}
    runs["proxy"].to_parquet(CACHE / "station_primary.parquet", index=False)
    rs.to_parquet(CACHE / "residual_primary.parquet", index=False)
    a = runs["proxy"]

    # R-A sensitivity: one contract per station-week
    ra_wet = all_wet_for(sorted({c for v in RA_LIST.values() for c in v}))
    ra_week_j, ra_week_l = {}, {}
    for s in STATIONS5:
        lst = RA_LIST[s]
        for tag, rng_ in (("j", (JOINT[0], "2026-09-27")), ("l", (f"{LONG_YEARS[0]}-01-01", f"{LONG_YEARS[1]}-12-31"))):
            src = ra_wet if tag == "j" else pd.DataFrame({c: ghcn_prcp(c) for c in lst})
            X = src.reindex(columns=lst).sort_index()
            X = X[~X.index.duplicated()].reindex(pd.date_range(rng_[0], rng_[1]))
            wk = weekly_count(X)
            ok = wk.notna().sum(axis=1) >= 0.6 * len(lst)
            M = wk.mean(axis=1).where(ok)
            WS = weekly_count((Wj if tag == "j" else Wl)[[s]])[s]
            r = (M - WS.reindex(M.index)).round(2)
            (ra_week_j if tag == "j" else ra_week_l)[s] = pd.DataFrame({"RA": r})
    groups_ra = {s: {"RA": biz.loc[biz.station == s, "h"].to_numpy()} for s in STATIONS5}
    ch_ra = dict(ch)
    rs_ra = residual_auctions(ra_week_j, groups_ra, ch_ra, weeks)
    print("R-A auctions", len(rs_ra), flush=True)

    # --- netting / fills / markouts / depth
    R["auction"] = {}
    for s in STATIONS5:
        g = a[a.station == s]; gr = rs[rs.station == s]
        if len(g):
            R["auction"][f"{s}/station"] = dict(days=int(len(g)), hedger_fill_share=float((g.bus_bid + g.bus_off).sum() / g.gross_qty.sum()),
                                                clearing_minus_fair_cents=float((g.p_star - 100 * g.mu)[g.q_star > 0].mean()), no_trade_share=float((g.q_star == 0).mean()),
                                                house_net_short_mean=float(g.net_short.mean()), hedge_units_mean=float(g.hedge_units.mean()),
                                                capacity_binding_share=float(((g.house_off >= g.cap_off) & (g.cap_off > 0)).mean()),
                                                unfilled_hedger_share=float(1 - (g.bus_bid + g.bus_off).sum() / g.gross_qty.sum()))
        if len(gr):
            tr = gr[gr.q_star > 0]
            R["auction"][f"{s}/residual"] = dict(markets=int(len(gr)), hedger_fill_share=float((gr.bus_bid + gr.bus_off).sum() / gr.gross_qty.sum()),
                                                 capacity_binding_share=float(((gr.house_off >= gr.cap_off) & (gr.cap_off > 0)).mean()),
                                                 no_trade_share=float((gr.q_star == 0).mean()),
                                                 clearing_minus_fair_cents_traded=float((tr.p_star - 100 * tr.mu_s).mean()) if len(tr) else None)
    # depth R4
    dep = {}
    for s in STATIONS5:
        g = a[a.station == s]
        need = float(g["net_short"].mean()) if len(g) else float("nan")
        dem = float(-biz.loc[biz.station == s, "h"].sum())
        dep[s] = dict(observed_days=int(len(g)), mean_net_short_contracts=need, demand_units_per_day=dem,
                      depth_proxy=int(depth[s]), ratio=(depth[s] / need) if need and not np.isnan(need) else None,
                      participation_supported_pct=(2.0 * depth[s] / need) if need and not np.isnan(need) else None)
    n_ok = sum(1 for v in dep.values() if v["ratio"] is not None and v["ratio"] >= 0.5)
    R["depth"] = dict(by_city=dep, R4=dict(cities_ge_0p5=n_ok, verdict="HEDGEABLE" if n_ok >= 3 else "THE HOUSE CARRIES IT"))
    # hedge cost per contract (buying at ask vs mid) observed
    hc = a[a.hedge_units != 0]
    half = {s: float((g.ask - g.mu).mean()) for s, g in a.groupby("station")}
    fee_c = {s: float(g.hedge_fees.sum() / np.abs(g.hedge_units).sum()) for s, g in hc.groupby("station")} if len(hc) else {}
    kal = dict(half_spread=half, half_spread_pooled=float((a.ask - a.mu).mean()),
               fee_per_contract=fee_c, fee_per_contract_pooled=float(hc.hedge_fees.sum() / np.abs(hc.hedge_units).sum()) if len(hc) else 0.0)
    fh = runs["full"]
    R["full_hedge_cost"] = dict(mean_daily_usd=float((fh.hedge_pnl - fh.hedge_units * (fh.x - fh.mu)).groupby(fh.date).sum().mean()),
                                note="hedge P&L minus the same contracts at mid (spread + fee) per day, observed run, uncapped hedge")
    R["kalshi_cost"] = dict(**kal, ask_over_payout=float((a.ask.sum()) / a.x.sum()) if a.x.sum() else None)
    mo = {}
    for mode, df in runs.items():
        d = df.assign(mo_h=df.mo_settle + df.hedge_pnl).groupby("date")["mo_h"].sum()
        mo[mode] = summarize(d)
    mo["residual_weekly"] = summarize(rs.groupby("week")["mo_settle"].sum())
    mo["residual_weekly_RA"] = summarize(rs_ra.groupby("week")["mo_settle"].sum())
    R["markouts"] = mo

    # --- capital
    book = book_from_run(a, rs, biz)
    book_none = book_from_run(runs["none"], rs, biz)
    book_full = book_from_run(runs["full"], rs, biz)
    book_ra = book_from_run(a, rs_ra, biz)
    R["book"] = dict(station={f"{s}/{m}": dict(units=book["q_st"][(s, m)], fill_units=book["q_fill"][(s, m)], price=book["price"][(s, m)],
                                               source=book["src"][(s, m)]) for s in STATIONS5 for m in range(1, 13)},
                     residual_units_by_station_month={f"{s}/{m}": float(sum(v for (ss, c, mm), v in book["q_r"].items() if ss == s and mm == m))
                                                      for s in STATIONS5 for m in range(1, 13)})
    allm, ms = list(range(1, 13)), [5, 6, 7, 8, 9]
    res_j = residual_pnl(book, rweek, Wj.index)
    res_j19 = residual_pnl(book, rweek, Wj.index, keep=foot)
    res_ra = residual_pnl(book_ra, ra_week_j, Wj.index)
    stj = station_pnl(book, Wj, muj)
    stl = station_pnl(book, Wl, mul)
    stl_none, stl_full = station_pnl(book_none, Wl, mul), station_pnl(book_full, Wl, mul)
    stj_none, stj_full = station_pnl(book_none, Wj, muj), station_pnl(book_full, Wj, muj)
    R["corr_station_residual_weekly_joint"] = float(pd.concat([stj.resample("W-SUN").sum(), res_j.resample("W-SUN").sum()], axis=1).corr().iloc[0, 1])

    def pack(st_pnl, rs_pnl, bk, months, keep=None, residual=True):
        fs, fr, ns, nr_ = fc_notional(bk, months, keep, residual)
        if months != allm:
            st_pnl = st_pnl[st_pnl.index.month.isin(months)]
            rs_pnl = rs_pnl[rs_pnl.index.month.isin(months)] if rs_pnl is not None else None
            st_pnl = _segment(st_pnl)
            rs_pnl = _segment(rs_pnl) if rs_pnl is not None else None
        tot = st_pnl if rs_pnl is None else st_pnl.add(rs_pnl.reindex(st_pnl.index).fillna(0.0), fill_value=0.0).where(st_pnl.notna())
        return capital_pack(tot, fs + (fr if residual else 0.0), ns + (nr_ if residual else 0.0))

    C = {}
    C["station_long_1999_2025"] = pack(stl, None, book, allm, residual=False)
    C["station_joint"] = pack(stj, None, book, allm, residual=False)
    C["two_leg_joint"] = pack(stj, res_j, book, allm)
    ratio30 = C["two_leg_joint"]["H30"]["C"] / C["station_joint"]["H30"]["C"]
    ratio153 = C["two_leg_joint"]["H153"]["C"] / C["station_joint"]["H153"]["C"]
    C["two_leg_long_scaled"] = dict(H30=C["station_long_1999_2025"]["H30"]["C"] * ratio30,
                                    H153=C["station_long_1999_2025"]["H153"]["C"] * ratio153, ratio30=ratio30, ratio153=ratio153)
    # sensitivities
    C["sens_RA_two_leg_joint"] = pack(stj, res_ra, book_ra, allm)
    ra_long = residual_pnl(book_ra, ra_week_l, Wl.index)
    C["sens_RA_two_leg_long"] = pack(stl, ra_long, book_ra, allm)
    C["sens_19pair_two_leg_joint"] = pack(stj, res_j19, book, allm, keep=foot)
    C["sens_MaySep_station_long"] = pack(stl, None, book, ms, residual=False)
    C["sens_MaySep_station_joint"] = pack(stj, None, book, ms, residual=False)
    C["sens_MaySep_two_leg_joint"] = pack(stj, res_j, book, ms)
    C["sens_hedge_none_station_long"] = pack(stl_none, None, book_none, allm, residual=False)
    C["sens_hedge_full_station_long"] = pack(stl_full, None, book_full, allm, residual=False)
    C["sens_hedge_none_two_leg_joint"] = pack(stj_none, res_j, book_none, allm)
    C["sens_hedge_full_two_leg_joint"] = pack(stj_full, res_j, book_full, allm)
    # D1: residual absorb-all
    book_abs = dict(book)
    book_abs["q_r"] = {}
    for s_ in STATIONS5:
        for cid, h in groups[s_].items():
            for m_ in range(1, 13):
                book_abs["q_r"][(s_, cid, m_)] = -float(h.sum())
    book_abs["mu_r_quote"] = {(s_, cid): float(rweek[s_][cid].mean()) for s_ in STATIONS5 for cid in groups[s_]}
    res_abs = residual_pnl(book_abs, rweek, Wj.index)
    C["D1_absorb_all_two_leg_joint"] = pack(stj, res_abs, book_abs, allm)
    C["D1_absorb_all_19pair_two_leg_joint"] = pack(stj, residual_pnl(book_abs, rweek, Wj.index, keep=foot), book_abs, allm, keep=foot)
    C["D1_absorb_all_MaySep_two_leg_joint"] = pack(stj, res_abs, book_abs, ms)
    book_abs_ra = dict(book_ra); book_abs_ra["q_r"] = {(s_, "RA", m_): -float(groups_ra[s_]["RA"].sum()) for s_ in STATIONS5 for m_ in range(1, 13)}
    book_abs_ra["mu_r_quote"] = {(s_, "RA"): float(ra_week_j[s_]["RA"].mean()) for s_ in STATIONS5}
    C["D1_absorb_all_RA_two_leg_joint"] = pack(stj, residual_pnl(book_abs_ra, ra_week_j, Wj.index), book_abs_ra, allm)
    C["D1_absorb_all_RA_two_leg_long"] = pack(stl, residual_pnl(book_abs_ra, ra_week_l, Wl.index), book_abs_ra, allm)
    C["D1_absorb_all_residual_only_joint"] = capital_pack(res_abs.where(stj.notna()), fc_notional(book_abs, allm)[1], fc_notional(book_abs, allm)[3])
    R["D1_absorb_all"] = dict(ratio30=C["D1_absorb_all_two_leg_joint"]["H30"]["C"] / C["station_joint"]["H30"]["C"],
                              ratio153=C["D1_absorb_all_two_leg_joint"]["H153"]["C"] / C["station_joint"]["H153"]["C"],
                              corr_station_residual_weekly=float(pd.concat([stj.resample("W-SUN").sum(), res_abs.resample("W-SUN").sum()], axis=1).corr().iloc[0, 1]),
                              residual_units_per_week={s_: float(-sum(h.sum() for h in groups[s_].values())) for s_ in STATIONS5})
    R["capital"] = C
    head = C["two_leg_joint"]["H30"]
    R["R2"] = dict(CPC=head["CPC_notional"], C30=head["C"], verdict="LEVERAGE HOLDS" if head["CPC_notional"] <= 0.35 else "FULL-COLLATERAL")
    R["R3"] = dict(ratio=ratio30, verdict="RESIDUAL CHEAP TO CARRY" if ratio30 <= 1.25 else "RESIDUAL IS MATERIAL CAPITAL")
    print("capital", {k: round(v["H30"]["C"]) for k, v in C.items() if isinstance(v, dict) and "H30" in v and isinstance(v["H30"], dict)}, flush=True)

    # --- junior
    J0 = head["ES95_junior"]; S0 = head["C"] - J0
    R["junior"] = dict(J0=J0, S0=S0,
                       observed_all_year=observed_junior(a, rs, J0), observed_MaySep=observed_junior(a, rs, J0, months=ms),
                       model_MaySep=model_junior(book, Wl, mul, res_j, J0, kal, "MaySep"),
                       model_year=model_junior(book, Wl, mul, res_j, J0, kal, "year"))
    hA = C["D1_absorb_all_two_leg_joint"]["H30"]
    R["junior"]["D1_absorb_all_model_MaySep"] = model_junior(book_abs, Wl, mul, res_abs, hA["ES95_junior"], kal, "MaySep")
    R["junior"]["D1_absorb_all_model_MaySep"]["J0"] = hA["ES95_junior"]
    mb = R["junior"]["model_MaySep"]["splits"]
    R["R5"] = {k: dict(three_season_sum_p05=v["three_season_sum_p05"], verdict="PASS" if v["rule_1in20_positive_over_3y"] else "FAIL") for k, v in mb.items()}
    R["deviations"] = DEVIATIONS
    R["written_utc"] = utcnow()
    R["runtime_s"] = round(time.time() - t0, 1)
    R["lines"] = lines(R)
    (REPORT / "rain_book.json").write_text(json.dumps(R, indent=1, default=_js))
    (REPORT / "rain_book.md").write_text(write_md(R))
    print("done", R["runtime_s"], flush=True)


def pct(x):
    return f"{100 * x:+.0f} %"


def usd(x):
    return f"${x + 0.0:,.0f}"


def usd_m(x):
    return f"${x / 1e6:.2f}M" if abs(x) >= 1e6 else f"${x / 1e3:,.0f}k"


def lines(R: dict) -> dict:
    C = R["capital"]; j = R["junior"]["model_MaySep"]["splits"]["margin_t10"]
    ja = R["junior"]["D1_absorb_all_model_MaySep"]["splits"]["margin_t10"]
    dep = R["depth"]["by_city"]
    need = sum(v["mean_net_short_contracts"] for v in dep.values())
    have = sum(v["depth_proxy"] for v in dep.values())
    s7 = (f"Rain as a weekly two-leg book (wet-day cover; station leg = daily Kalshi rain binaries, residual = PRISM per-cell spread; "
          f"`reports/eval-04-05/rain_book.json`). Almost nothing nets: {R['netting']['central']['pooled']:.3f} of units cancel "
          f"(`netting.central.pooled`), because nearly every sector loses on wet days. At 2 % participation the pool is short "
          f"{usd_m(sum(v['leftover_units_per_day'] for v in R['netting']['leftover'].values()))} of payout per wet day across the five cities "
          f"(`netting.leftover.<ST>.leftover_units_per_day`), and Kalshi's daily rain markets can absorb about {round(have, -2):,.0f} contracts a day against "
          f"about {round(need, -3):,.0f} needed (`depth.by_city.<ST>.depth_proxy`, `.mean_net_short_contracts`; a volume proxy, no order-book history), so the house carries it. "
          f"The 30-day capital is {usd_m(C['two_leg_joint']['H30']['C'])} on the 2024-26 window (`capital.two_leg_joint.H30.C`; Phase 4's heat book: $412k, `handoff.C30_usd`), "
          f"{C['two_leg_joint']['H30']['CPC_notional']:.2f} of 30-day notional (`R2.CPC`), and {usd_m(C['station_long_1999_2025']['H30']['C'])} "
          f"for the station leg on 1999-2025 (`capital.station_long_1999_2025.H30.C`); the season (153-day) figure is "
          f"{usd_m(C['two_leg_joint']['H153']['C'])} (`capital.two_leg_joint.H153.C`). The residual leg adds little capital: "
          f"×{R['R3']['ratio']:.2f} as priced (`R3.ratio`), ×{R['D1_absorb_all']['ratio30']:.2f} if the house wrote every residual unit "
          f"(`D1_absorb_all.ratio30`). With senior paid out of margin, the junior's median May-Sep season is {pct(j['median'])} and the 1-in-20 season "
          f"{pct(j['p05_1in20'])} (`junior.model_MaySep.splits.margin_t10`), so the three-season test fails (`R5.margin_t10`).")
    memo = (f"Rain cover doesn't net and Kalshi's daily rain markets are about {round(need / have, -2):,.0f} times too thin to lay it off, so a rain book is "
            f"the pool's own risk: about {usd_m(C['two_leg_joint']['H30']['C'])} of 30-day capital at 2 % take-up, and the junior loses money in a bad year.")
    return {"evaluation_s7_paragraph": s7, "memo_line": memo}


def write_md(R: dict) -> str:
    C = R["capital"]; N = R["netting"]; D = R["depth"]
    L = ["# Weekly rain two-leg book (EVAL-04 extension)", "",
         f"Run {R['written_utc']} by `uv run python scripts/eval04_rain.py` ({R['runtime_s']} s, deterministic, seed {SEED}). "
         f"Rules frozen in `PREREG-rain.md` at {PREREG_UTC}, before any number. All numbers are in `rain_book.json`; keys in backticks.", "",
         "## Verdicts (pre-registered lines)", "",
         "| ID | Line | Result | Verdict |", "|---|---|---|---|",
         f"| R1 | NR >= 0.25 at >= 3 of 5 | NYC {N['central']['NYC'] + 0.0:.3f}, EWR {N['central']['EWR']:.3f}, TTN {N['central']['TTN'] + 0.0:.3f}, "
         f"MDW {N['central']['MDW'] + 0.0:.3f}, MIA {N['central']['MIA'] + 0.0:.3f}; pooled {N['central']['pooled']:.3f} | **{N['R1']['verdict']}** |",
         f"| R2 | two-leg C_30 / 30-day notional <= 0.35 | {R['R2']['CPC']:.3f} (C_30 {usd(R['R2']['C30'])}) | **{R['R2']['verdict']}** |",
         f"| R3 | two-leg C_30 / station C_30 <= 1.25 | {R['R3']['ratio']:.3f} (absorb-all, D1: {R['D1_absorb_all']['ratio30']:.3f}) | **{R['R3']['verdict']}** |",
         f"| R4 | depth proxy / net short contracts >= 0.5 in >= 3 of 5 | " + ", ".join(f"{k} {v['ratio']:.4f}" for k, v in D['by_city'].items()) +
         f" | **{D['R4']['verdict']}** |",
         "| R5 | 1-in-20 junior return positive over 3 seasons (May-Sep, model) | " + ", ".join(f"{k} {pct(v['three_season_sum_p05'])}" for k, v in R['R5'].items()) +
         " | **" + ", ".join(f"{k} {v['verdict']}" for k, v in R['R5'].items()) + "** |", "",
         "## Netting and leftover", "",
         f"- Central priors, 2 %: pooled NR {N['central']['pooled']:.3f}; shrink-to-common null {N['null']['pooled']:.3f}; prior ensemble pooled p10/p50/p90 "
         f"{N['ensemble']['pooled']['p10']:.3f} / {N['ensemble']['pooled']['p50']:.3f} / {N['ensemble']['pooled']['p90']:.3f}. Residual leg per cell: "
         f"{N['residual_cell_level_pooled']:.3f}. Only delivery and cinemas gain on wet days, and they are too few.", "",
         "| station | businesses | wet-cover units bought/day | sold/day | leftover $/wet day | station-leg max payout $/week |", "|---|---|---|---|---|---|"]
    for s_, v in N["leftover"].items():
        L.append(f"| {s_} | {v['businesses']} | {v['L_units'] + 0.0:,.0f} | {v['S_units'] + 0.0:,.0f} | {v['leftover_units_per_day']:,.0f} | {v['max_payout_per_week_station_leg_usd']:,.0f} |")
    L += ["", "## Kalshi depth", "",
          f"Depth proxy = 10 % of the median contracts traded before the T-24h cutoff (no daily-rain order book on file). "
          f"Buying the binary at the 24 h ask costs {R['kalshi_cost']['ask_over_payout']:.3f} per $1 of payout (EVAL-01: 1.20). "
          f"An uncapped hedge would cost {usd(-R['full_hedge_cost']['mean_daily_usd'])} a day in spread and fees on the observed run.", "",
          "| city | observed days | mean net short contracts/day | depth proxy | ratio | participation it supports |", "|---|---|---|---|---|---|"]
    for s_, v in D["by_city"].items():
        L.append(f"| {s_} | {v['observed_days']} | {v['mean_net_short_contracts']:,.0f} | {v['depth_proxy']} | {v['ratio']:.4f} | {v['participation_supported_pct']:.4f} % |")
    L += ["", "## Auctions (observed run)", "", "| market | days / markets | hedger fill share | no-trade share | clearing - fair (c) |", "|---|---|---|---|---|"]
    for k, v in R["auction"].items():
        L.append(f"| {k} | {v.get('days', v.get('markets'))} | {v['hedger_fill_share']:.3f} | {v['no_trade_share']:.3f} | "
                 f"{(v.get('clearing_minus_fair_cents') if 'clearing_minus_fair_cents' in v else v.get('clearing_minus_fair_cents_traded')) or float('nan'):.2f} |")
    mo = R["markouts"]
    L += ["", f"House P&L after the capped hedge, per day: mean {usd(mo['proxy']['mean'])} (95 % CI {usd(mo['proxy']['ci95'][0])} to {usd(mo['proxy']['ci95'][1])}), "
          f"worst day {usd(mo['proxy']['worst_day'])}, worst 30 days {usd(mo['proxy']['worst_30day'])}. Residual leg per week: mean {usd(mo['residual_weekly']['mean'])}.", "",
          "## Capital (Phase 4 rule; C = min(FC, max(ES99, worst window)))", "",
          "| book | history | C_30 | ES99_30 | worst 30 d | binding | CPC_30 | C_153 | junior ES95_30 |", "|---|---|---|---|---|---|---|---|---|"]
    rows = [("station leg", "1999-2025", "station_long_1999_2025"), ("station leg", "2024-26", "station_joint"),
            ("two legs (primary)", "2024-26", "two_leg_joint"), ("two legs, R-A", "2024-26", "sens_RA_two_leg_joint"),
            ("two legs, R-A", "1999-2025", "sens_RA_two_leg_long"), ("two legs, 19-pair", "2024-26", "sens_19pair_two_leg_joint"),
            ("station leg, May-Sep", "1999-2025", "sens_MaySep_station_long"), ("two legs, May-Sep", "2024-26", "sens_MaySep_two_leg_joint"),
            ("station, no hedge", "1999-2025", "sens_hedge_none_station_long"), ("two legs, uncapped hedge", "2024-26", "sens_hedge_full_two_leg_joint"),
            ("D1 absorb-all two legs", "2024-26", "D1_absorb_all_two_leg_joint"), ("D1 absorb-all, 19-pair", "2024-26", "D1_absorb_all_19pair_two_leg_joint"),
            ("D1 absorb-all, May-Sep", "2024-26", "D1_absorb_all_MaySep_two_leg_joint"), ("D1 absorb-all R-A", "1999-2025", "D1_absorb_all_RA_two_leg_long"),
            ("D1 residual alone", "2024-26", "D1_absorb_all_residual_only_joint")]
    for name, hist, k in rows:
        v = C[k]; a, b = v["H30"], v["H153"]
        L.append(f"| {name} | {hist} | {usd(a['C'])} | {usd(a['ES99'])} | {usd(a['worst_window']) if a['worst_window'] == a['worst_window'] else 'n/a'} | {a['binding']} | "
                 f"{(a['CPC_notional'] or 0):.3f} | {usd(b['C'])} | {usd(a['ES95_junior'])} |")
    L += ["", f"Two-leg long figure (station 1999-2025 × the 2024-26 two-leg/station ratio): C_30 {usd(C['two_leg_long_scaled']['H30'])}, C_153 {usd(C['two_leg_long_scaled']['H153'])}. "
          f"Weekly station/residual P&L correlation on 2024-26: {R['corr_station_residual_weekly_joint']:.2f} (absorb-all {R['D1_absorb_all']['corr_station_residual_weekly']:.2f}).", "",
          "## Junior return (junior_returns method)", "",
          f"J0 = two-leg ES95_30 = {usd(R['junior']['J0'])}; S0 = {usd(R['junior']['S0'])}.", "",
          "| rule | observed 2025 | observed 2026 | model May-Sep median | 1-in-20 | p1 | 3-season p5 | model year median | year 1-in-20 | absorb-all May-Sep median / 1-in-20 / 3-season p5 |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for k in ("spec_t10", "spec_t20", "margin_t10", "margin_t20"):
        o = R["junior"]["observed_all_year"][k]; m = R["junior"]["model_MaySep"]["splits"][k]; y = R["junior"]["model_year"]["splits"][k]
        aa = R["junior"]["D1_absorb_all_model_MaySep"]["splits"][k]
        o = {str(kk): vv for kk, vv in o.items()}
        L.append(f"| {k} | {pct(o['2025']['junior_return'])} | {pct(o['2026']['junior_return'])} | {pct(m['median'])} | {pct(m['p05_1in20'])} | {pct(m['p01'])} | "
                 f"{pct(m['three_season_sum_p05'])} | {pct(y['median'])} | {pct(y['p05_1in20'])} | {pct(aa['median'])} / {pct(aa['p05_1in20'])} / {pct(aa['three_season_sum_p05'])} |")
    comp = R["junior"]["model_MaySep"]["mean_components_per_season"]
    L += ["", f"Mean modelled May-Sep season: station premium {usd(comp['prem'])}, margin inside it {usd(comp['rm'])} ({100 * comp['rm'] / comp['prem']:.1f} %), "
          f"payouts {usd(comp['pay'])}, hedge {usd(comp['hedge'])}, residual {usd(comp['res'])}. Observed 2025 is NYC only (KXRAINNYC); 2026 adds CHI/MIA from mid-July and EWR/TTN from late August.", "",
          "## Two lines for the report and memo", "", "§7 paragraph:", "", "> " + R["lines"]["evaluation_s7_paragraph"], "", "Memo line:", "", "> " + R["lines"]["memo_line"], "",
          "## Assumptions", ""]
    L += [f"- {a}" for a in ASSUMPTIONS]
    L += ["", "## Caveats", ""] + [f"- {c}" for c in CAVEATS]
    L += ["", "## Deviations (UTC)", ""] + [f"- {d}" for d in R["deviations"]]
    L += ["", f"Look-ahead runtime check: {R['lookahead_check']['markets_checked']} station markets re-run with every post-cutoff candle and the result flipped; {R['lookahead_check']['moved']} moved."]
    return "\n".join(L) + "\n"


ASSUMPTIONS = [
    "Population, participation (2 %, Phase 4 `p2` draw) and e_R priors as Phase 4; wet-day units h = -daily_rev x e_R/100; Chicago businesses in the Midway catchment, rain station leg at O'Hare (KXRAIN CHI settles at CLIORD).",
    "Wet day = precipitation > 0 including trace (Kalshi rule). Joint-window station data: CLI (`official_daily`) for NYC/EWR/TTN/MIA, GHCN-D for ORD; long history GHCN-D PRCP 1999-2025 (TTN's record starts 1998).",
    "Residual = G1-P design on weekly wet-day counts (PRISM ppt >= 0.01 in on labels Tue..Mon), not the inch spec; cell nearest each business ZIP point; Chicago c(S) = O'Hare's cell. PRISM values as cached (mostly final grids), not the count-2 snapshot.",
    "Station fair value = Kalshi mid at T-24h; scenario fair value = Markov P(wet | month, wet yesterday) fitted in-sample on 1999-2025; residual scenario fair = in-sample cell mean over 2024-26.",
    "House quote = fair + max(charge, 1 tick); charges (CoC 15 %) are a fraction of a cent, so the quote is tick-bound, as in Phase 4.",
    "Kalshi hedge capped by the depth proxy (10 % of pre-cutoff volume, 44-186 contracts per city-day); hedge P&L includes the taker fee.",
    "Book for capital = average observed house position per station-month (after the hedge), ratio x demand where a month has < 5 observed days; residual book per cell-month from the observed weekly auctions.",
    "Junior: station fills are policies; residual fills and the hedge are house deployment (all to junior). Model seasons join the long station history with the residual from a random 2024/2025 block at the same calendar dates (independent across years).",
]
CAVEATS = [
    "The observed Kalshi era is mostly NYC (519 of 726 station-days); other cities have 33-71 days, so their books lean on the ratio rule.",
    "The two-leg history is 32 months (2024-01..2026-08): the season-horizon (153-day) capital has few independent windows; May-Sep has 2.",
    "Depth is a volume proxy; no KXRAIN order book exists on file. The need is about 110 (TTN) to 2,200 (NYC) times the proxy, so the verdict survives any plausible error in it.",
    "The residual on wet-day counts was not scored in Phase 3 (which used inches); its hedge value is untested here.",
    "Under the frozen limits almost no residual trades (hedgers will not pay one 14-wide tick), so the primary two-leg book is the station leg plus a sliver; D1 gives the absorb-all read.",
    "The modelled residual component has a non-zero mean (+ about $250k a season absorb-all) because its fair value is the 2024-26 mean and the bootstrap draws 2024-25 only; the junior median under absorb-all is flattered by it.",
    "Sector priors are LOW confidence; e_R for outdoor recreation (-30 %), car washes (-40 %) and landscaping (-20 %) drive most of the demand.",
]


def _segment(s: pd.Series) -> pd.Series:
    """Keep a month-filtered daily series as-is (gaps become NaN on reindex in cap_series)."""
    return s


def _js(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, (pd.Timestamp, dt.date)):
        return str(o)
    return str(o)


if __name__ == "__main__":
    main()
