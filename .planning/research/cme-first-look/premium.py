"""Owner test: does CME weather price the outcome or a hedging premium?
Inputs (data/raw/cme-weather/): Databento GLBX.MDP3 statistics + trades (db_pull.py), ACIS daily max/min (fetch_acis.py).
Outputs: premium_rows.csv (one row per contract x trade date used), premium_summary.json, printed tables.
Error convention: e = price - final index. e > 0 means futures buyers paid more than the outcome (sellers earned it).
Run: uv run --no-project --with databento --with pandas python .planning/research/cme-first-look/premium.py"""
import json, re, calendar, datetime as dt
import numpy as np, pandas as pd, databento as db
from common import RAW, OUT, CITIES
START, END = "2022-10-01", "2026-10-24"
MCODE = dict(zip("FGHJKMNQUVXZ", range(1, 13)))
ROOT = {}
for city, h, k, wban, icao, ghcn in CITIES:
    ROOT[h] = (city, "hdd", icao); ROOT[k] = (city, "cdd", icao)
pat = re.compile(r"^(" + "|".join(sorted(ROOT, key=len, reverse=True)) + r")([FGHJKMNQUVXZ])(\d)$")

def year_of(digit, ref_year):
    y = 2020 + digit
    return y + 10 if y < ref_year - 2 else y

# ---------- CME statistics ----------
st = db.DBNStore.from_file(RAW / f"glbx-weather-stats-{START}-{END}.dbn.zst").to_df(map_symbols=True, price_type="float")
st = st[st.stat_type.isin([3, 6, 9])].copy()
m = st.symbol.str.extract(pat)
st = st[m[0].notna()].copy(); m = m[m[0].notna()]
st["root"], st["mon"], st["yd"] = m[0], m[1].map(MCODE), m[2].astype(int)
st["tdate"] = pd.to_datetime(st.ts_ref, unit="ns", utc=True, errors="coerce").dt.tz_localize(None).dt.normalize()
st = st[st.tdate.notna() & (st.tdate.dt.year > 2000) & (st.tdate.dt.year < 2100)]
st["cyear"] = [year_of(d, t.year) for d, t in zip(st.yd, st.tdate)]
st["contract"] = st.root + st.mon.astype(str).str.zfill(2) + "-" + st.cyear.astype(str)
st["recv"] = st.index
st = st.reset_index(drop=True)
settle = st[st.stat_type == 3].copy()
settle["final_flag"] = (settle.stat_flags & 1).astype(bool); settle["actual"] = (settle.stat_flags & 2).astype(bool)
settle = settle.sort_values(["contract", "tdate", "final_flag", "recv"]).groupby(["contract", "tdate"]).tail(1)
vol = st[st.stat_type == 6].sort_values("recv").groupby(["contract", "tdate"]).quantity.last().rename("cleared_vol")
oi = st[st.stat_type == 9].sort_values("recv").groupby(["contract", "tdate"]).quantity.last().rename("oi")
S = settle.set_index(["contract", "tdate"])[["root", "mon", "cyear", "price", "actual", "final_flag"]].join(vol).join(oi).reset_index()
S["cleared_vol"] = S.cleared_vol.fillna(0)
# Globex prints
tp = RAW / f"glbx-weather-trades-{START}-{END}.dbn.zst"
tr = db.DBNStore.from_file(tp).to_df(map_symbols=True, price_type="float")
mt = tr.symbol.str.extract(pat); tr = tr[mt[0].notna()].copy(); mt = mt[mt[0].notna()]
tr["tdate"] = (tr.index.tz_convert("America/Chicago") + pd.Timedelta(hours=7)).normalize().tz_localize(None)  # 17:00 CT session roll
tr["contract"] = mt[0] + mt[1].map(MCODE).astype(str).str.zfill(2) + "-" + [str(year_of(int(d), t.year)) for d, t in zip(mt[2], tr.tdate)]
tr = tr.reset_index(drop=True); tr["pv"] = tr.price * tr["size"]
gx = tr.groupby(["contract", "tdate"]).agg(gx_n=("price", "size"), gx_qty=("size", "sum"), pv=("pv", "sum"))
gx["gx_vwap"] = gx.pv / gx.gx_qty; gx = gx.drop(columns="pv")
S = S.set_index(["contract", "tdate"]).join(gx).reset_index(); S["gx_n"] = S.gx_n.fillna(0)
S["month_start"] = pd.to_datetime(dict(year=S.cyear, month=S.mon, day=1))
S["month_end"] = S.month_start + pd.offsets.MonthEnd(0)
S["lead"] = (S.month_end - S.tdate).dt.days
# final index = last settlement after month end (CME final settlement = Speedwell index)
fin = S[S.tdate > S.month_end].sort_values("tdate").groupby("contract").tail(1).set_index("contract").price.rename("final")
S = S.join(fin, on="contract")
S = S[S.final.notna()].copy()
S = S.sort_values(["contract", "tdate"])
S["prev"] = S.groupby("contract").price.shift(1)
S["changed"] = (S.price != S.prev) & S.prev.notna()
inwin = (S.tdate >= S.month_start - pd.Timedelta(days=15)) & (S.tdate <= S.month_end)
S["cls"] = np.where((S.cleared_vol > 0) | (S.gx_n > 0), "a_trade", np.where(inwin, "b_window_mark", "c_stale_mark"))
S = S[S.tdate <= S.month_end]  # pre-expiry prices only

# ---------- ACIS station data + trend-aware baseline ----------
daily = {}
for city, h, k, wban, icao, ghcn in CITIES:
    d = pd.DataFrame(json.load(open(RAW / f"acis-{icao}.json"))["data"], columns=["date", "tx", "tn"])
    d = d[(d.tx.str.match(r"^-?\d+$")) & (d.tn.str.match(r"^-?\d+$"))]
    d["date"] = pd.to_datetime(d.date); d = d.set_index("date")
    d["avg"] = (d.tx.astype(int) + d.tn.astype(int)) / 2
    daily[icao] = d.avg
def dd(a, kind): return np.maximum(0, 65 - a) if kind == "hdd" else np.maximum(0, a - 65)
cache = {}
def expected_dd(icao, kind, date, trend=True):
    """Detrended burn: same calendar day +-3 over prior 30 yrs, each year shifted by the station's
    linear warming slope (annual-mean OLS over those 30 yrs) to the target year. trend=False: 10-yr plain burn."""
    key = (icao, kind, date, trend)
    if key in cache: return cache[key]
    a = daily[icao]; Y = date.year
    if trend:
        yrs = range(Y - 30, Y)
        if (icao, Y) not in cache:
            ann = a[(a.index.year >= Y - 30) & (a.index.year < Y)].groupby(a.index.year[(a.index.year >= Y - 30) & (a.index.year < Y)]).mean()
            cache[(icao, Y)] = np.polyfit(ann.index.values, ann.values, 1)[0]
        b = cache[(icao, Y)]
    else:
        yrs = range(Y - 10, Y); b = 0.0
    vals = []
    for y in yrs:
        try: c = date.replace(year=y)
        except ValueError: c = date.replace(year=y, day=28)
        w = a.loc[c - pd.Timedelta(days=3): c + pd.Timedelta(days=3)].values + b * (Y - y)
        vals.append(dd(w, kind))
    v = float(np.mean(np.concatenate(vals))); cache[key] = v; return v
def baseline(icao, kind, tdate, ms, me, trend=True):
    a = daily[icao]
    known_end = tdate - pd.Timedelta(days=1)
    known = float(dd(a.loc[ms:known_end], kind).sum()) if known_end >= ms else 0.0
    rest = pd.date_range(max(ms, tdate), me)
    return known + sum(expected_dd(icao, kind, x, trend) for x in rest)
def acis_index(icao, kind, ms, me):
    s = daily[icao].loc[ms:me]
    return float(dd(s, kind).sum()) if len(s) == (me - ms).days + 1 else np.nan

# rows used: fixed leads (latest settle on or before month_end - L) + every trade day
LEADS = [90, 60, 30, 15, 7, 1]
rows = []
for cid, g in S.groupby("contract"):
    for L in LEADS:
        target = g.month_end.iloc[0] - pd.Timedelta(days=L)
        h = g[g.tdate <= target]
        if len(h) and (target - h.tdate.iloc[-1]).days <= 4:
            r = h.iloc[-1].to_dict(); r["lead_bucket"] = L; r["row_kind"] = "lead"; rows.append(r)
    for _, r in g[g.cls == "a_trade"].iterrows():
        r = r.to_dict(); r["lead_bucket"] = None; r["row_kind"] = "trade_day"; rows.append(r)
R = pd.DataFrame(rows)
R["city"], R["kind"], R["icao"] = zip(*R.root.map(ROOT))
R["base_trend"] = [baseline(i, k, t, a, b, True) for i, k, t, a, b in zip(R.icao, R.kind, R.tdate, R.month_start, R.month_end)]
R["base_10y"] = [baseline(i, k, t, a, b, False) for i, k, t, a, b in zip(R.icao, R.kind, R.tdate, R.month_start, R.month_end)]
R["acis_final"] = [acis_index(i, k, a, b) for i, k, a, b in zip(R.icao, R.kind, R.month_start, R.month_end)]
R["e_price"] = R.price - R.final
R["e_base"] = R.base_trend - R.final
R["e_base10"] = R.base_10y - R.final
R["price_minus_base"] = R.price - R.base_trend
R["ym"] = R.month_start.dt.strftime("%Y-%m")
R.to_csv(OUT / "premium_rows.csv", index=False)

def clus(x, by):
    """mean and SE clustered by calendar month (cities in the same month share weather regimes)."""
    df = pd.DataFrame({"x": x.values, "g": by.values}).dropna()
    if len(df) < 2: return (round(df.x.mean(), 1) if len(df) else None, None, len(df), df.g.nunique())
    gm = df.groupby("g").x.mean(); k = len(gm)
    se = gm.std(ddof=1) / np.sqrt(k) if k > 1 else np.nan
    return (round(df.x.mean(), 1), round(float(se), 1) if k > 1 else None, len(df), k)
summary = {}
print("=== final index check: CME final vs ACIS (max+min)/2 sum, per contract ===")
F = R.drop_duplicates("contract")
dif = (F.final - F.acis_final).dropna()
summary["final_check"] = dict(n=int(len(dif)), mean=round(dif.mean(), 2), mae=round(dif.abs().mean(), 2), share_within_1=round((dif.abs() <= 1).mean(), 3))
print(summary["final_check"])
print("\n=== class counts (all pre-expiry contract-days) ===")
cc = S.groupby("cls").agg(n=("price", "size"), changed_share=("changed", "mean"), actual_flag_share=("actual", "mean"))
print(cc.round(3)); summary["class_counts"] = cc.round(3).reset_index().to_dict("records")
print("\n=== fixed leads: e = price - final (mean, clustered SE, n rows, n months) | trend baseline | 10y baseline | price - trend baseline | sd(e) ===")
L = R[R.row_kind == "lead"]; out = []
for (cls, kind, lb), g in L.groupby(["cls", "kind", "lead_bucket"]):
    o = dict(cls=cls, kind=kind, lead=int(lb), price=clus(g.e_price, g.ym), base_trend=clus(g.e_base, g.ym), base_10y=clus(g.e_base10, g.ym),
             price_minus_base=clus(g.price_minus_base, g.ym), sd_price=round(g.e_price.std(), 1), sd_base=round(g.e_base.std(), 1),
             rmse_price=round(np.sqrt((g.e_price ** 2).mean()), 1), rmse_base=round(np.sqrt((g.e_base ** 2).mean()), 1))
    out.append(o); print(o)
summary["leads"] = out
print("\n=== trade days (class a): by lead bucket ===")
T = R[R.row_kind == "trade_day"].copy()
T["bucket"] = pd.cut(T.lead, [-1, 7, 15, 31, 60, 120, 2000], labels=["0-7", "8-15", "16-31", "32-60", "61-120", "121+"])
out = []
for (kind, bk), g in T.groupby(["kind", "bucket"], observed=True):
    o = dict(kind=kind, bucket=str(bk), n_days=len(g), n_contracts=g.contract.nunique(), vol=int(g.cleared_vol.sum()),
             price=clus(g.e_price, g.contract), base_trend=clus(g.e_base, g.contract), price_minus_base=clus(g.price_minus_base, g.contract))
    out.append(o); print(o)
summary["trade_days"] = out
for kind in ("hdd", "cdd"):
    g = T[T.kind == kind]
    w = g.cleared_vol
    summary[f"trade_all_{kind}"] = dict(n_days=len(g), n_contracts=int(g.contract.nunique()), vol=int(w.sum()),
        e_price=clus(g.e_price, g.contract), e_base=clus(g.e_base, g.contract), price_minus_base=clus(g.price_minus_base, g.contract),
        vol_weighted_e_price=round(float(np.average(g.e_price, weights=w)), 1) if w.sum() > 0 else None,
        vol_weighted_price_minus_base=round(float(np.average(g.price_minus_base, weights=w)), 1) if w.sum() > 0 else None)
    print(kind, summary[f"trade_all_{kind}"])
by_city = T.groupby(["city", "kind"]).agg(n=("e_price", "size"), vol=("cleared_vol", "sum"), e_price=("e_price", "mean"), pmb=("price_minus_base", "mean")).round(1)
print(by_city); summary["trade_by_city"] = by_city.reset_index().to_dict("records")
json.dump(summary, open(OUT / "premium_summary.json", "w"), indent=1, default=str)
