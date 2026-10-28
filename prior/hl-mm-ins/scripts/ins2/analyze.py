"""ins2 V1 analysis. Choices fixed BEFORE the first run (see reports/ins2/README.md):
 - cell exposure = H(round(Tcell_F), K) with H(T,K)=min(max(T-K,0),6); K and the hedge (ladder_pay, the Kalshi ladder's
   binned payout) come from reports/ins1/rows.json; own-station exposure = H_nws (ASOS) as in ins1.
 - HE = 1 - pvar(exposure - hedge)/pvar(exposure); cells with zero exposure variance are dropped (counted).
 - test-2 residual r = H(cell) - H(station ASOS); sum over cells per day; ratio = pvar(sum_c r_c)/sum_c pvar(r_c).
   Sensitivity: residual vs ladder_pay; unrounded cell temps.
 - days = ins1 city-days for which nClimGrid-Daily exists. Alignment: the file says a day is "the 24-hour period ending in the early morning"
   of the labelled date, and the nearest-cell-vs-ASOS check (reports/ins2/README.md) confirms calendar day D = grid label D+1 (SHIFT=1).
   SHIFT=0 reproduces the mis-aligned run (kept only as a reference).
 - cell-share criterion: HE_cell >= HE_own_station - 0.1.
Run: PYTHONPATH=src ~/Desktop/hl-mm/.venv/bin/python scripts/ins2/analyze.py
"""
import json, sys, datetime as dt, numpy as np
SHIFT = int(sys.argv[1]) if len(sys.argv) > 1 else 1   # grid label day D holds the 24 h ending early morning of D -> calendar day D-1; use grid label D+SHIFT
OUTJ = "reports/ins2/results.json" if SHIFT == 1 else "reports/ins2/results_label_day_unshifted.json"
ROWS = json.load(open("reports/ins1/rows.json"))
Z = np.load("var/ins2/cells.npz")
SER = {"NYC": "KXHIGHNY", "EWR": "KXHIGHTEWR", "TTN": "KXHIGHTTTN", "MDW": "KXHIGHCHI", "MIA": "KXHIGHMIA"}
LAST = "2026-09-25"   # last calendar day with a grid value (Sep prelim runs to label 09-26)
lab = lambda d: (dt.date.fromisoformat(d) + dt.timedelta(days=SHIFT)).isoformat()
rng = np.random.default_rng(20260930)
NB = 2000

def H(T, K): return np.clip(T - K, 0.0, 6.0)
def he(x, y):
    v = np.var(x)
    return np.nan if v == 0 else 1 - np.var(x - y) / v

def load(st):
    days = list(Z[f"{st}_days"]); T = Z[f"{st}_tmaxC"]
    idx = {d: i for i, d in enumerate(days)}
    rs = [r for r in ROWS if r["ser"] == SER[st] and r["day"] <= LAST and r.get("H_nws") is not None and lab(r["day"]) in idx]
    rs.sort(key=lambda r: r["day"])
    ok = np.isfinite(T[[idx[lab(r["day"])] for r in rs]]).all(axis=0)
    Tc = T[[idx[lab(r["day"])] for r in rs]][:, ok] * 9 / 5 + 32
    return rs, Tc, dict(dist=Z[f"{st}_dist"][ok], n_cells_disc=T.shape[1])

res = {}; allres = []
for st in SER:
    rs, Tf, info = load(st)
    K = np.array([r["K"] for r in rs]); pay = np.array([r["ladder_pay"] for r in rs]); Hn = np.array([r["H_nws"] for r in rs])
    Tn = np.array([r["T_nws"] for r in rs])
    def cellH(rounded=True):
        T = np.round(Tf) if rounded else Tf
        return H(T, K[:, None])
    Hc = cellH(True); Hu = cellH(False)
    own = he(Hn, pay)
    hec = np.array([he(Hc[:, j], pay) for j in range(Hc.shape[1])]); heu = np.array([he(Hu[:, j], pay) for j in range(Hc.shape[1])])
    keep = np.isfinite(hec)
    share = float(np.mean(hec[keep] >= own - 0.1)); shareu = float(np.mean(heu[np.isfinite(heu)] >= own - 0.1))
    # test 2
    R = Hc - Hn[:, None]                       # residual cell - station, per day x cell
    R2 = Hc - pay[:, None]                     # sensitivity: vs ladder payoff
    def ratio(R, rows=None):
        if rows is not None: R = R[rows]
        return float(np.var(R.sum(axis=1)) / np.var(R, axis=0).sum())
    ratio1 = ratio(R); ratio2 = ratio(R2)
    n = len(rs); bs = []; bsh = []
    for _ in range(NB):
        rows = rng.integers(0, n, n)
        bs.append(ratio(R, rows))
        h = np.array([he(Hc[rows, j], pay[rows]) for j in range(0, Hc.shape[1], 3)]); o = he(Hn[rows], pay[rows])
        h = h[np.isfinite(h)]; bsh.append(np.mean(h >= o - 0.1) if np.isfinite(o) and len(h) else np.nan)
    bsh = np.array(bsh); bsh = bsh[np.isfinite(bsh)]
    j0 = int(np.argmin(info["dist"]))
    # exploratory (not pre-registered): best cell, share within 0.3, and HE after an in-sample offset/ratio fit (as ins1 T2d)
    def he_ols(x, y):
        b = np.cov(y, x, bias=True)[0, 1] / np.var(y) if np.var(y) > 0 else 0.0; a = x.mean() - b * y.mean()
        return 1 - np.var(x - (a + b * y)) / np.var(x) if np.var(x) > 0 else np.nan
    heo = np.array([he_ols(Hc[:, j], pay) for j in range(Hc.shape[1])])
    # mean pairwise correlation of residuals
    cs = np.corrcoef(R[:, np.var(R, axis=0) > 0].T); m = cs.shape[0]; mpc = float((cs.sum() - m) / (m * (m - 1)))
    # nearest-cell sanity vs ASOS
    near_bias = float(np.mean(Tf[:, j0] - Tn)); near_rmse = float(np.sqrt(np.mean((Tf[:, j0] - Tn) ** 2)))
    mean_bias_all = float(np.mean(Tf.mean(axis=1) - Tn))
    res[st] = dict(n_days=n, cells=int(Hc.shape[1]), cells_disc=info["n_cells_disc"], cells_zero_var=int((~keep).sum()),
                   he_station=float(own), he_cell_median=float(np.nanmedian(hec)), he_cell_p10=float(np.nanpercentile(hec, 10)),
                   he_cell_p90=float(np.nanpercentile(hec, 90)), share_within=share, he_nearest_cell=float(hec[j0]), he_cell_max=float(np.nanmax(hec)), share_within_0p3=float(np.mean(hec[keep] >= own - 0.3)), he_cell_median_offset_ratio_fit=float(np.nanmedian(heo)), ratio_over_ncells=ratio1 / Hc.shape[1], share_within_unrounded=shareu,
                   share_ci=[float(np.percentile(bsh, 2.5)), float(np.percentile(bsh, 97.5))],
                   ratio=ratio1, ratio_ci=[float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))],
                   ratio_vs_ladder=ratio2, mean_pair_corr=mpc, resid_rmse=float(np.sqrt(np.mean(R ** 2))),
                   resid_sd_sum=float(np.std(R.sum(axis=1))), sum_of_sd=float(np.sqrt(np.var(R, axis=0)).sum()),
                   nearest_cell_km=float(info["dist"][j0]), nearest_cell_bias_F=near_bias, nearest_cell_rmse_F=near_rmse, disc_mean_bias_F=mean_bias_all,
                   dist_hec_corr=float(np.corrcoef(info["dist"][keep], hec[keep])[0, 1]))
    allres.append((st, Hc, Hn, pay, hec, own, keep, R))

# pooled over all five stations (cells weighted equally; each cell vs its own station's HE)
share_all = float(np.mean(np.concatenate([h[k] >= o - 0.1 for _, _, _, _, h, o, k, _ in allres])))
ncell = sum(int(k.sum()) for *_, k, _ in allres)
# book across stations: days differ per station; align on calendar day for the >1-station book
byday = {}
for st, Hc, Hn, pay, hec, own, keep, R in allres:
    days = [r["day"] for r in sorted([r for r in ROWS if r["ser"] == SER[st] and r["day"] <= LAST and r.get("H_nws") is not None], key=lambda r: r["day"])]
    for i, d in enumerate(days): byday.setdefault(d, []).append(R[i])
tot = [np.concatenate(v) for v in byday.values()]
s_all = np.array([x.sum() for x in tot])
indiv = sum(np.var(np.array([np.concatenate(byday[d])[j] for d in byday if len(byday[d]) == 5]), axis=0).sum() for _ in [0]) if False else None
# cleaner: variance of the all-cell sum only on days where all five ladders exist, vs sum of per-cell variances on those days
full = [d for d in byday if len(byday[d]) == 5]
M = np.array([np.concatenate(byday[d]) for d in full])
ratio_all = float(np.var(M.sum(axis=1)) / np.var(M, axis=0).sum())
res["ALL"] = dict(cells=ncell, share_within=share_all, ratio_all_five_ladders=ratio_all, days_all_five=len(full))
json.dump(res, open(OUTJ, "w"), indent=1)
print(json.dumps(res, indent=1))
