"""Conservative re-cut of premium_rows.csv: trade-day errors clustered by calendar month (cities share weather),
10-yr baseline on trade days, Globex-vs-block split, and minimum detectable effect (MDE = 2.8 x SE, 80% power, 5% two-sided)."""
import pandas as pd, numpy as np, json
from common import OUT
R = pd.read_csv(OUT / "premium_rows.csv", parse_dates=["tdate"])
def cl(x, g):
    d = pd.DataFrame({"x": x.values, "g": g.values}).dropna(); gm = d.groupby("g").x.mean()
    se = gm.std(ddof=1) / np.sqrt(len(gm)); return dict(mean=round(d.x.mean(), 1), se=round(se, 1), mde=round(2.8 * se, 1), n=len(d), months=len(gm))
res = {}
T = R[R.row_kind == "trade_day"]
print("trade days with Globex prints:", int((T.gx_n > 0).sum()), "of", len(T), "| cleared vol on those:", int(T[T.gx_n > 0].cleared_vol.sum()), "of", int(T.cleared_vol.sum()))
for k in ("hdd", "cdd"):
    g = T[T.kind == k]
    res[k] = {c: cl(g[c], g.ym) for c in ("e_price", "e_base", "e_base10", "price_minus_base")}
    res[k]["share_price_above_final"] = round((g.e_price > 0).mean(), 3)
    print(k, json.dumps(res[k]))
L = R[(R.row_kind == "lead") & (R.cls == "b_window_mark")]
for k in ("hdd", "cdd"):
    for lb in (30, 15, 7, 1):
        g = L[(L.kind == k) & (L.lead_bucket == lb)]
        print("window", k, lb, "price", cl(g.e_price, g.ym), "corr(mark, final)", round(np.corrcoef(g.price, g.final)[0, 1], 3),
              "corr(trend base, final)", round(np.corrcoef(g.base_trend, g.final)[0, 1], 3))
json.dump(res, open(OUT / "premium_extra.json", "w"), indent=1)
