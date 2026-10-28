"""EVAL-04 / EVAL-05 driver (plan 04, single worker run). Rules: reports/eval-04-05/PREREG.md.

uv run python scripts/eval04.py --all
uv run python scripts/eval04.py --stage population --stage units ...
Stages: population, units, netting, auction, capital, revision, report.
Intermediate artifacts: data/cache/eval04/ (gitignored). Outputs: reports/eval-04-05/.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from wi.exposure import hedge as hedge_mod  # noqa: E402
from wi.exposure.priors import PERSIST_W, load_priors, naics_map, triangular_draws  # noqa: E402
from wi.population import revenue, stations, zbp  # noqa: E402

CACHE = ROOT / "data" / "cache" / "eval04"
RAW = ROOT / "data" / "raw"
REPORT = ROOT / "reports" / "eval-04-05"
MANIFEST = ROOT / "data" / "manifests" / "eval04-sources.csv"
SEED = 20260930
PARTICIPATION = {"p0.5": 0.005, "p2": 0.02, "p10": 0.10}

CACHE.mkdir(parents=True, exist_ok=True)
(REPORT / "figures").mkdir(parents=True, exist_ok=True)


def utcnow() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def md5(p: Path) -> str:
    h = hashlib.md5()
    with open(p, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def load_results() -> dict:
    p = CACHE / "results_partial.json"
    return json.loads(p.read_text()) if p.exists() else {}


def save_results(key: str, val) -> None:
    r = load_results()
    r[key] = val
    (CACHE / "results_partial.json").write_text(json.dumps(r, indent=1, default=float))


def write_source_manifest() -> None:
    urls = {
        "census/zbp23detail.zip": "https://www2.census.gov/programs-surveys/cbp/datasets/2023/zbp23detail.zip",
        "census/zbp23totals.zip": "https://www2.census.gov/programs-surveys/cbp/datasets/2023/zbp23totals.zip",
        "census/cbp23co.zip": "https://www2.census.gov/programs-surveys/cbp/datasets/2023/cbp23co.zip",
        "census/us_state_6digitnaics_2022.txt": "https://www2.census.gov/programs-surveys/susb/tables/2022/us_state_6digitnaics_2022.txt",
        "census/2024_Gaz_zcta_national.zip": "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_zcta_national.zip",
    }
    rows = []
    for rel, url in urls.items():
        p = RAW / rel
        rows.append(dict(dataset=rel.split("/")[0], local_path=f"data/raw/{rel}", url=url, bytes=p.stat().st_size,
                         md5=md5(p), fetched_utc=dt.datetime.fromtimestamp(p.stat().st_mtime, dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")))
    for p in sorted((RAW / "ghcnd_eval04").glob("*.csv.gz")):
        rows.append(dict(dataset="ghcnd", local_path=f"data/raw/ghcnd_eval04/{p.name}",
                         url=f"https://www.ncei.noaa.gov/pub/data/ghcn/daily/by_station/{p.name}", bytes=p.stat().st_size,
                         md5=md5(p), fetched_utc=dt.datetime.fromtimestamp(p.stat().st_mtime, dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")))
    for p in sorted((RAW / "iem_afos_cli").glob("*.txt.gz")) if (RAW / "iem_afos_cli").exists() else []:
        rows.append(dict(dataset="iem_afos_cli", local_path=f"data/raw/iem_afos_cli/{p.name}",
                         url="https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py?pil=" + p.name.split("_")[0],
                         bytes=p.stat().st_size, md5=md5(p),
                         fetched_utc=dt.datetime.fromtimestamp(p.stat().st_mtime, dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")))
    pd.DataFrame(rows).to_csv(MANIFEST, index=False)


# ----------------------------------------------------------------------------- population
def stage_population() -> None:
    pri = load_priors()
    nm = naics_map(pri)
    codes = set(nm["naics"])
    det = zbp.read_detail(RAW / "census" / "zbp23detail.zip", codes | {"------"})
    allind = det[det["naics"] == "------"]
    det = det[det["naics"] != "------"].reset_index(drop=True)

    # every prior row must match >= 1 ZBP row (Pitfall 3: NAICS 2017 vs 2022)
    present = set(det["naics"])
    match = {int(r): sorted(set(g["naics"]) & present) for r, g in nm.groupby("row_id")}
    missing_codes = sorted(codes - present)
    assert all(len(v) > 0 for v in match.values()), f"prior rows without ZBP rows: {match}"

    vals, imp_log = zbp.impute_sizes(det)
    small, small_log = zbp.small_business_long(det, vals)

    # midpoint calibration (descriptive): ZBP totals employment vs detail all-industry est x midpoint
    import zipfile
    with zipfile.ZipFile(RAW / "census" / "zbp23totals.zip") as z:
        tot = pd.read_csv(z.open("zbp23totals.txt"), dtype={"zip": str}, encoding="latin-1")
    av, _ = zbp.impute_sizes(allind.reset_index(drop=True))
    implied = pd.Series((av * zbp.MID[None, :]).sum(axis=1), index=allind["zip"].to_numpy())
    cal = tot.set_index("zip")["emp"].reindex(implied.index)
    calib_all = float(cal.sum() / implied[cal.notna()].sum())
    # CBP county, summed to national per NAICS, vs ZBP detail est x midpoint per NAICS
    with zipfile.ZipFile(RAW / "census" / "cbp23co.zip") as z:
        co = pd.read_csv(z.open("cbp23co.txt"), dtype=str, encoding="latin-1", usecols=["naics", "emp"])
    co = co[co["naics"].isin(codes)]
    co_emp = co.assign(emp=pd.to_numeric(co["emp"], errors="coerce")).groupby("naics")["emp"].sum()
    det_emp = pd.Series((vals * zbp.MID[None, :]).sum(axis=1), index=det["naics"].to_numpy()).groupby(level=0).sum()
    calib_naics = (co_emp / det_emp).dropna().round(3).to_dict()
    # deviation D2 evidence: the research imputation rule on the same rows
    vals_r, _ = zbp.impute_sizes(det, method="research")
    det_emp_r = pd.Series((vals_r * zbp.MID[None, :]).sum(axis=1), index=det["naics"].to_numpy()).groupby(level=0).sum()
    d2 = dict(research_rule=dict(est_small=float(vals_r[:, :zbp.SMALL].sum()),
                                 cbp_over_implied_emp_median=float((co_emp / det_emp_r).dropna().median())),
              proportional_rule=dict(est_small=float(vals[:, :zbp.SMALL].sum()),
                                     cbp_over_implied_emp_median=float((co_emp / det_emp).dropna().median())))

    # revenue
    st_rpe, nat_rpe = revenue.receipts_per_employee(RAW / "census" / "us_state_6digitnaics_2022.txt", codes)
    small = revenue.attach_revenue(small, st_rpe, nat_rpe)
    assert small["daily_rev"].notna().all()

    # stations
    zc = stations.load_zcta(RAW / "census" / "2024_Gaz_zcta_national.zip")
    zs = stations.assign_station(zc)
    in_zcta = small["zip"].isin(set(zc["zip"]))
    dropped_no_zcta = dict(rows=int((~in_zcta).sum()), est=float(small.loc[~in_zcta, "est"].sum()),
                           est_share_states=float(small.loc[~in_zcta & small.stabbr.isin(["NY", "NJ", "PA", "CT", "IL", "IN", "FL"]), "est"].sum()
                                                   / small.loc[small.stabbr.isin(["NY", "NJ", "PA", "CT", "IL", "IN", "FL"]), "est"].sum()))
    pop = small.merge(zs, on="zip", how="inner")
    pop = pop.merge(nm, on="naics", how="left")
    pop = pop.merge(pri[["row_id", "group", "e_T_central", "T0", "e_R_central", "pclass"]], on="row_id", how="left")
    pop = pop.sort_values(["station", "zip", "naics", "size"]).reset_index(drop=True)

    out = CACHE / "population.parquet"
    pop.to_parquet(out, index=False)
    by_station = pop.groupby("station").agg(rows=("est", "size"), est=("est", "sum"),
                                             daily_rev_total=("daily_rev", lambda s: float((s * pop.loc[s.index, "est"]).sum())))
    by_row = pop.groupby(["station", "row_id"])["est"].sum().unstack(fill_value=0).round(1)
    prior_rows_in_catchments = {int(c): int((by_row[c] > 0).sum()) for c in by_row.columns}
    log = dict(file=str(out.relative_to(ROOT)), rows=int(len(pop)), md5=md5(out), written_utc=utcnow(),
               zbp_filtered=imp_log, small_business=small_log, missing_codes_in_zbp=missing_codes,
               prior_row_matches=match, prior_rows_present_in_n_stations=prior_rows_in_catchments,
               dropped_no_zcta=dropped_no_zcta, rpe_source_share=pop.groupby("rpe_source")["est"].sum().div(pop["est"].sum()).round(4).to_dict(),
               midpoint_calibration_all_industries_emp_over_implied=round(calib_all, 4), deviation_D2_imputation=d2,
               midpoint_calibration_cbp_emp_over_zbp_implied_by_naics=calib_naics,
               by_station={k: {kk: float(vv) for kk, vv in v.items()} for k, v in by_station.to_dict("index").items()},
               est_by_station_row=by_row.to_dict("index"))
    save_results("population", log)
    write_source_manifest()
    print(json.dumps({k: log[k] for k in ["rows", "md5", "small_business", "dropped_no_zcta", "by_station"]}, indent=1))


# ----------------------------------------------------------------------------- weather + units
def load_weather() -> dict:
    """GHCN TMAX for every station (cached), settlement series with the MDW splice, metro means."""
    from wi.pool import scenarios as sc
    p = CACHE / "ghcnd_tmax.parquet"
    if p.exists():
        df = pd.read_parquet(p)
        tmax = {c: df[c].dropna() for c in df.columns}
    else:
        tmax = {c: sc.load_tmax(c) for c in sc.GHCN_ID}
        tmax = {c: v for c, v in tmax.items() if len(v)}
        pd.DataFrame(tmax).to_parquet(p)
    settle, splice = sc.settlement_series(tmax)
    metro = {s: sc.metro_mean(tmax, s, settle[s]) for s in sc.SETTLE}
    return dict(tmax=tmax, settle=settle, splice=splice, metro=metro)


def proxy_bundle(W: dict, years: tuple[int, int], detrend: bool = True) -> dict:
    from wi.pool import scenarios as sc
    models, days = {}, {}
    for s in sc.SETTLE:
        mdl = sc.fit_proxy(W["settle"][s], s, years, detrend)
        d = sc.proxy_days(W["settle"][s], mdl, (1951, 2025))   # model fit on `years`; days through 2025
        M = W["metro"][s].reindex(d.index)
        d["M"] = np.round(M + d["shift"], 1)   # the station's trend shift applied to the metro mean
        d["r"] = sc.H(d["M"], d["K"]) - d["H"]
        models[s], days[s] = mdl, d
    return dict(models=models, days=days)


def stage_units() -> None:
    from wi.exposure.hedge import unit_weights
    W = load_weather()
    B = proxy_bundle(W, (1951, 2020), detrend=True)
    pri = load_priors()
    t0s = sorted(set(pri["T0"].dropna().tolist())) + [float("nan")]
    days = {s: d[(d.index.year >= 1951) & (d.index.year <= 2020)] for s, d in B["days"].items()}
    w = unit_weights(days, t0s)
    w.to_parquet(CACHE / "unit_weights.parquet", index=False)
    info = {s: dict(phi=round(m.phi, 3), trend_F_per_year=round(m.trend_per_year, 4), n_days=int(len(days[s])),
                    resid_sd_by_month={int(k): round(float(v.std()), 3) for k, v in m.resid_by_month.items()},
                    first_year=int(days[s].index.year.min()))
            for s, m in B["models"].items()}
    cover = {s: dict(years_with_residual_quorum=int(W["metro"][s].dropna().index.year.nunique()),
                     first_quorum_year=int(W["metro"][s].dropna().index.year.min())) for s in W["metro"]}
    save_results("weather", dict(proxy_1951_2020=info, mdw_splice=W["splice"], metro_quorum=cover))
    print(json.dumps(info, indent=1)[:1500])
    print(cover)


# ----------------------------------------------------------------------------- Kalshi ladders
def stage_ladders() -> None:
    from wi.pool import kalshi_leg as kl
    rungs = kl.load_rungs()
    cand = pd.read_parquet(ROOT / "data" / "cache" / "kalshi" / "candles.parquet",
                           columns=["market_ticker", "ts", "yes_ask_close", "yes_bid_close"])
    cand = cand[cand["market_ticker"].isin(set(rungs["market_ticker"]))]
    rungs = kl.quotes_at(rungs, cand, 24, "c24")
    rungs = kl.quotes_at(rungs, cand, 2, "c2")
    ev = rungs.groupby("event_ticker").agg(station=("station", "first"), date=("event_date", "first"),
                                            close_time=("close_time", "first"), K=("K", "first"),
                                            n_rungs=("n_rungs", "first"), n_yes=("n_yes", "first"))
    win = rungs[rungs["result"] == "yes"].groupby("event_ticker")["Hv"].first()
    ev["ladder_pay"] = win
    for tag in ("c24", "c2"):
        ev = ev.join(kl.fair_value(rungs, tag))
    off = pd.read_parquet(ROOT / "data" / "cache" / "weather" / "official_daily.parquet")
    off["date"] = pd.to_datetime(off["date_local"])
    ev = ev.reset_index().merge(off[["station", "date", "high_f"]], on=["station", "date"], how="left")
    ev["T_cli"] = ev["high_f"]
    ev["H_cli"] = kl.H(ev["T_cli"], ev["K"])
    crit = dict(n_events=len(ev), six_rungs=int((ev.n_rungs >= 6).sum()),
                one_yes=int(((ev.n_rungs >= 6) & (ev.n_yes == 1)).sum()),
                cli=int(((ev.n_rungs >= 6) & (ev.n_yes == 1) & ev.T_cli.notna()).sum()))
    ev["sample"] = (ev.n_rungs >= 6) & (ev.n_yes == 1) & ev.T_cli.notna() & ev.allvalid_c24
    ev["sample_c2"] = ev["sample"] & ev.allvalid_c2
    crit["valid_c24"] = int(ev["sample"].sum())
    ev.to_parquet(CACHE / "ladders.parquet", index=False)
    rungs[rungs["event_ticker"].isin(set(ev.loc[ev["sample"], "event_ticker"]))].to_parquet(CACHE / "rungs.parquet", index=False)
    s = ev[ev["sample"]]
    counts = s.groupby("station").agg(days=("date", "size"), first=("date", "min"), last=("date", "max"))
    counts["first"] = counts["first"].astype(str); counts["last"] = counts["last"].astype(str)
    save_results("sample", dict(filter_counts=crit, by_station=counts.to_dict("index"),
                                c2_days=s.groupby("station")["sample_c2"].sum().astype(int).to_dict()))
    print(crit); print(counts)


# ----------------------------------------------------------------------------- netting
def participants(pop: pd.DataFrame, p: float, level: int, persist: bool = False) -> np.ndarray:
    """Binomial participation per population row on round(est), seeded, fixed for the season."""
    rng = np.random.default_rng([SEED, level, int(persist)])
    n = np.round(pop["est"].to_numpy()).astype(int)
    prob = np.full(len(pop), p)
    if persist:
        w = pop["pclass"].map(PERSIST_W).fillna(1.0).to_numpy()
        prob = p * w * (n.sum() / (n * w).sum())
        prob = np.clip(prob, 0, 1)
    return rng.binomial(n, prob)


def weights_for(pop: pd.DataFrame, uw: pd.DataFrame) -> pd.DataFrame:
    """(rows x months) w for each population row (its station, its T0)."""
    t0 = pop["T0"].fillna(-999.0)
    u = uw.assign(T0k=uw["T0"].fillna(-999.0)).pivot_table(index=["station", "T0k"], columns="month", values="w")
    key = pd.MultiIndex.from_arrays([pop["station"], t0])
    return pd.DataFrame(u.reindex(key).to_numpy(), columns=u.columns)


def nr(L: np.ndarray, S: np.ndarray, days: np.ndarray) -> float:
    den = (days * (L + S)).sum()
    return float((days * 2 * np.minimum(L, S)).sum() / den) if den > 0 else float("nan")


def stage_netting() -> None:
    pop = pd.read_parquet(CACHE / "population.parquet")
    uw = pd.read_parquet(CACHE / "unit_weights.parquet")
    pri = load_priors()
    ev = pd.read_parquet(CACHE / "ladders.parquet")
    ev = ev[ev["sample"]]
    ev["month"] = pd.to_datetime(ev["date"]).dt.month
    ndays = ev.groupby(["station", "month"]).size()
    W = weights_for(pop, uw)                      # rows x months 5..9
    months = list(W.columns)
    stations_ = ["NYC", "EWR", "TTN", "MDW", "MIA"]
    part = {k: participants(pop, p, i) for i, (k, p) in enumerate(PARTICIPATION.items())}
    part["p2_persist"] = participants(pop, 0.02, 1, persist=True)
    np.savez(CACHE / "participants.npz", **part)
    rev = pop["daily_rev"].to_numpy()
    rowidx = pop["row_id"].to_numpy()
    prow = pri.set_index("row_id")

    def station_LS(e_by_row: dict, npart: np.ndarray) -> dict:
        e = np.array([e_by_row[r] for r in rowidx])
        out = {}
        for s in stations_:
            m_s = (pop["station"] == s).to_numpy()
            Ls, Ss, ds = [], [], []
            for mo in months:
                h = hedge_mod.signed_units(rev[m_s], e[m_s], W.loc[m_s, mo].to_numpy()) * npart[m_s]
                Ls.append(h[h > 0].sum()); Ss.append(-h[h < 0].sum()); ds.append(int(ndays.get((s, mo), 0)))
            out[s] = (np.array(Ls), np.array(Ss), np.array(ds))
        return out

    def summarize(LS: dict) -> dict:
        res = {s: nr(*LS[s]) for s in stations_}
        Lp = np.concatenate([LS[s][0] for s in stations_]); Sp = np.concatenate([LS[s][1] for s in stations_])
        dp = np.concatenate([LS[s][2] for s in stations_])
        res["pooled"] = nr(Lp, Sp, dp)
        return res

    central = {int(r): float(prow.loc[r, "e_T_central"]) for r in prow.index}
    npart = part["p2"]
    LS_c = station_LS(central, npart)
    # null: c = revenue-weighted mean of central e_T over the pooled participating population
    e_c = np.array([central[r] for r in rowidx])
    c = float((rev * npart * e_c).sum() / (rev * npart).sum())
    null = {r: 0.75 * c + 0.25 * v for r, v in central.items()}
    LS_n = station_LS(null, npart)
    out = dict(participation="p2", central=summarize(LS_c), null=summarize(LS_n), null_c=c)
    out["central_by_month"] = {s: {int(m): (float(2 * min(l, sh) / (l + sh)) if l + sh > 0 else None)
                                   for m, l, sh in zip(months, LS_c[s][0], LS_c[s][1])} for s in stations_}
    # leftover units per station-day (constant within station-month)
    out["leftover_units_per_day"] = {}
    for s in stations_:
        L, S, d = LS_c[s]
        lo = np.abs(L - S)
        out["leftover_units_per_day"][s] = dict(
            mean_units=float((lo * d).sum() / d.sum()) if d.sum() else None,
            mean_gross_units=float(((L + S) * d).sum() / d.sum()) if d.sum() else None,
            mean_max_payout_usd=float(6 * (lo * d).sum() / d.sum()) if d.sum() else None,
            by_month={int(m): dict(L=float(l), S=float(sh)) for m, l, sh in zip(months, L, S)})
    # other participation levels + persistence weighting
    for k in ["p0.5", "p10", "p2_persist"]:
        out[f"central_{k}"] = summarize(station_LS(central, part[k]))
    # ensemble: 1,000 triangular draws per prior row (fixed across days)
    draws = triangular_draws(pri, "e_T", 1000, SEED)
    rid = pri["row_id"].to_numpy()
    # precompute per station-month-row revenue x w x participants, then units = -R*e/100
    rows_u = sorted(set(rowidx))
    R = {}
    for s in stations_:
        m_s = (pop["station"] == s).to_numpy()
        for mo in months:
            vec = rev[m_s] * W.loc[m_s, mo].to_numpy() * npart[m_s]
            R[(s, mo)] = pd.Series(vec).groupby(rowidx[m_s]).sum().reindex(rows_u, fill_value=0.0).to_numpy()
    col = [int(np.flatnonzero(rid == r)[0]) for r in rows_u]
    E = draws[:, col]                                      # draws x rows_u
    ens = {s: [] for s in stations_ + ["pooled"]}
    num_p = np.zeros(len(E)); den_p = np.zeros(len(E))
    for s in stations_:
        num = np.zeros(len(E)); den = np.zeros(len(E))
        for mo in months:
            d = int(ndays.get((s, mo), 0))
            if d == 0:
                continue
            U = -(E * R[(s, mo)][None, :]) / 100.0
            L = np.where(U > 0, U, 0).sum(axis=1); S = np.where(U < 0, -U, 0).sum(axis=1)
            num += d * 2 * np.minimum(L, S); den += d * (L + S)
        ens[s] = num / den
        num_p += num; den_p += den
    ens["pooled"] = num_p / den_p
    out["ensemble"] = {s: dict(p10=float(np.nanpercentile(v, 10)), p50=float(np.nanpercentile(v, 50)),
                               p90=float(np.nanpercentile(v, 90)), share_ge_0p25=float(np.mean(v >= 0.25)))
                       for s, v in ens.items()}
    out["ensemble_M1_material_share"] = float(np.mean(sum((ens[s] >= 0.25).astype(int) for s in stations_) >= 3))
    # ZIP-level netting (matched inside each ZIP), central
    e = np.array([central[r] for r in rowidx])
    zipnr = {}
    for s in stations_:
        m_s = (pop["station"] == s).to_numpy()
        num = den = 0.0
        for mo in months:
            d = int(ndays.get((s, mo), 0))
            if d == 0:
                continue
            h = hedge_mod.signed_units(rev[m_s], e[m_s], W.loc[m_s, mo].to_numpy()) * npart[m_s]
            z = pd.DataFrame({"zip": pop.loc[m_s, "zip"].to_numpy(), "L": np.where(h > 0, h, 0), "S": np.where(h < 0, -h, 0)}).groupby("zip").sum()
            num += d * 2 * np.minimum(z["L"], z["S"]).sum(); den += d * (z["L"] + z["S"]).sum()
        zipnr[s] = float(num / den) if den else None
    out["zip_level"] = zipnr
    # metro level: NYC+EWR+TTN as one metro (units summed per month, weighted by NYC days)
    Lm = LS_c["NYC"][0] + LS_c["EWR"][0] + LS_c["TTN"][0]; Sm = LS_c["NYC"][1] + LS_c["EWR"][1] + LS_c["TTN"][1]
    out["metro_level"] = {"NYC-metro": nr(Lm, Sm, LS_c["NYC"][2]), "MDW": out["central"]["MDW"], "MIA": out["central"]["MIA"]}
    # rain (descriptive): wet-day units daily_rev*e_R/100; e_R<0 -> buys wet cover
    eR = np.array([float(prow.loc[r, "e_R_central"]) for r in rowidx])
    rain = {}
    for s in stations_:
        m_s = (pop["station"] == s).to_numpy()
        u = -(rev[m_s] * eR[m_s] / 100.0) * npart[m_s]
        L, S = u[u > 0].sum(), -u[u < 0].sum()
        rain[s] = float(2 * min(L, S) / (L + S))
    out["rain_central"] = rain
    # verdicts
    n_mat = sum(1 for s in stations_ if out["central"][s] >= 0.25)
    out["M1"] = dict(stations_ge_0p25=n_mat, verdict="MATERIAL" if n_mat >= 3 else "NOT MATERIAL")
    out["M2"] = dict(null_pooled=out["null"]["pooled"],
                     verdict="the pitch must not lead with netting" if out["null"]["pooled"] < 0.10 else "netting survives the null")
    # participant counts
    out["participants"] = {k: pd.Series(v).groupby(pop["station"].to_numpy()).sum().astype(int).to_dict() for k, v in part.items()}
    save_results("netting", out)
    print(json.dumps({k: out[k] for k in ["central", "null", "null_c", "M1", "M2", "ensemble", "zip_level", "metro_level", "rain_central", "participants"]}, indent=1))


# ----------------------------------------------------------------------------- auction on history
STATIONS5 = ["NYC", "EWR", "TTN", "MDW", "MIA"]
CAPACITY_USD = 250_000.0


def business_table(pop: pd.DataFrame, npart: np.ndarray, uw: pd.DataFrame, e_col: str = "e_T_central") -> dict:
    """Per station: one row per participating business, signed units h by month (central priors)."""
    W = weights_for(pop, uw)
    out = {}
    for s in STATIONS5:
        m_s = np.flatnonzero((pop["station"] == s).to_numpy() & (npart > 0))
        rep = np.repeat(m_s, npart[m_s])
        H_by_m = {int(mo): hedge_mod.signed_units(pop["daily_rev"].to_numpy()[rep], pop[e_col].to_numpy()[rep],
                                                  W[mo].to_numpy()[rep]) for mo in W.columns}
        out[s] = dict(rows=rep, h=H_by_m)
    return out


def residual_climatology(B: dict, window: int | None = None) -> dict:
    """mu_r and MAD_r per (station, month, year) from proxy days with year < Y (1951 -> Y-1);
    window=k (sensitivity): only years Y-k .. Y-1."""
    out = {}
    for s, d in B["days"].items():
        d = d.dropna(subset=["r"])
        for Y in range(2021, 2027):
            h = d[(d.index.year < Y) & (d.index.year >= (Y - window if window else 0))]
            for mo, g in h.groupby(h.index.month):
                mu = float(g["r"].mean())
                out[(s, int(mo), Y)] = (mu, float(np.abs(g["r"] - mu).mean()), int(len(g)))
    return out


def kalshi_era_residual(W: dict) -> dict:
    from wi.pool import scenarios as sc
    return {s: pd.DataFrame({"M": W["metro"][s], "T": W["settle"][s]}) for s in sc.SETTLE}


def charges_from_book(B: dict, book: dict, coc: float, years=(1999, 2020)) -> dict:
    """(CoC/365) x Euler co-ES99 per (station, leg) in the 30-day rolled book (block bootstrap)."""
    from wi.pool import capital as cap
    yrs = list(range(years[0], years[1] + 1))
    mats, bookm = {}, np.zeros((len(yrs), len(cap.SEASON)))
    month_of = np.array([int(x[:2]) for x in cap.SEASON])
    for s in STATIONS5:
        d = B["days"][s]
        for leg, col, mucol in (("station", "u", None), ("residual", "r", "mu_r")):
            if leg == "station":
                ser = d["u"]
            else:
                mu_r = d.dropna(subset=["r"])
                mu_r = mu_r[(mu_r.index.year >= years[0]) & (mu_r.index.year <= years[1])].groupby(mu_r.index.month[(mu_r.index.year >= years[0]) & (mu_r.index.year <= years[1])])["r"].mean()
                ser = d["r"] - mu_r.reindex(d.index.month).to_numpy()
            M = np.nan_to_num(cap.season_matrix(ser, yrs))
            mats[(s, leg)] = M
            q = np.array([book.get((s, leg, int(mo)), 0.0) for mo in month_of])
            bookm += M * q[None, :]
    rng = np.random.default_rng(SEED)
    reps, Hh, blk = 10_000, 30, 7
    nb = -(-Hh // blk)
    y = rng.integers(0, len(yrs), size=(reps, nb)); st = rng.integers(0, len(cap.SEASON) - blk + 1, size=(reps, nb))
    def paths(M):
        return np.concatenate([M[y[:, b, None], st[:, b, None] + np.arange(blk)] for b in range(nb)], axis=1)[:, :Hh].sum(axis=1)
    keys = list(mats)
    unit = np.column_stack([paths(mats[k]) for k in keys])
    bp = paths(bookm)
    ce = cap.co_es(unit, bp)
    lam = coc / 365.0
    return {k: dict(co_es=float(c), charge_buy=float(lam * c), charge_sell=float(-lam * c)) for k, c in zip(keys, ce)}


def imbalance_book(biz: dict) -> dict:
    """House position if it absorbed the whole net hedger demand: q = -(L - S) $1/degF units."""
    book = {}
    for s in STATIONS5:
        for mo, h in biz[s]["h"].items():
            book[(s, "station", mo)] = -float(h.sum())
            book[(s, "residual", mo)] = -float(h.sum())
    return book


def delta_samples(resid: dict) -> dict:
    """(station, month, Y) -> array of metro-minus-station deltas M - T from years < Y (raw GHCN)."""
    out = {}
    for s, df in resid.items():
        d = (df["M"] - df["T"]).dropna()
        for Y in range(2021, 2027):
            h = d[d.index.year < Y]
            for mo, g in h.groupby(h.index.month):
                out[(s, int(mo), Y)] = g.to_numpy()
    return out


def ladder_residual_mu(er: pd.DataFrame, K: float, deltas: np.ndarray, tag: str) -> float:
    """Sensitivity: E[H(T+delta;K) - H(T;K)] with T from the ladder mids at the cutoff and delta
    from the metro-minus-station climatology through year D-1."""
    from wi.pool import kalshi_leg as kl
    mid = ((er[f"ask_{tag}"] + er[f"bid_{tag}"]) / 2.0).to_numpy()
    v = er["v"].to_numpy()
    val = np.array([np.mean(kl.H(vb + deltas, K) - kl.H(vb, K)) for vb in v])
    return float((mid * val).sum() / mid.sum())


def run_auctions(ev: pd.DataFrame, rungs: pd.DataFrame, biz: dict, rclim: dict, resid: dict, charges: dict,
                 tag: str = "c24", keep_rows: bool = True, deltas: dict | None = None) -> pd.DataFrame:
    from wi.pool import kalshi_leg as kl
    from wi.pool import sim
    ev = ev.copy()
    ev["date"] = pd.to_datetime(ev["date"])
    rg = {k: g for k, g in rungs.groupby("event_ticker")}
    rows = []
    for date, day in ev.groupby("date"):
        mkts = []
        for _, e in day.iterrows():
            s = e["station"]
            mkts.append(("station", s, e))
            rr = resid[s]
            if date in rr.index and not np.isnan(rr.loc[date, "M"]) and not np.isnan(rr.loc[date, "T"]) \
                    and (s, date.month, date.year) in rclim:
                mkts.append(("residual", s, e))
        cap_each = CAPACITY_USD / len(mkts)
        for leg_name, s, e in mkts:
            leg = sim.STATION if leg_name == "station" else sim.RESIDUAL
            h = biz[s]["h"][date.month]
            rng = np.random.default_rng([SEED, STATIONS5.index(s), date.toordinal(), 0 if leg_name == "station" else 1])
            if leg_name == "station":
                mu = float(e[f"mu_{tag}"]); spread = 0.0
            else:
                mu, spread, _ = rclim[(s, date.month, date.year)]
                if deltas is not None:
                    mu = ladder_residual_mu(rg[e["event_ticker"]], float(e["K"]), deltas[(s, date.month, date.year)], tag)
            ch = charges[(s, leg_name)]
            m = sim.run_market(h, leg, mu, spread, rng, ch["charge_sell"], ch["charge_buy"], cap_each)
            r = m["r"]
            if leg_name == "station":
                x = float(kl.H(e["T_cli"], e["K"])) / 6.0
                mu2 = float(e["mu_c2"]) / 6.0 if not np.isnan(e["mu_c2"]) else np.nan
            else:
                rr = resid[s].loc[date]
                rv = float(kl.H(rr["M"], e["K"]) - kl.H(rr["T"], e["K"]))
                x = (rv + 6.0) / 12.0
                mu2 = m["mu_s"]
            st_ = sim.settle_market(m, x)
            fz = sim.fees(m)
            bus_bid = int(m["fills"][m["is_bid"]].sum()); bus_off = int(m["fills"][~m["is_bid"]].sum())
            p = r.p_star / 100.0
            mo2h = (mu2 - p) * m["house_bid"] + (p - mu2) * m["house_off"] if r.q_star else 0.0
            net_h_units = (m["house_bid"] - m["house_off"]) / leg.width   # + = house long
            hp, hfee, hc, hunits = 0.0, 0.0, 0, 0.0
            if leg_name == "station" and s in ("NYC", "MDW", "MIA") and net_h_units != 0:
                hunits = min(5.0, abs(net_h_units))
                side = +1 if net_h_units < 0 else -1
                hp, hfee, hc = kl.hedge_pnl(rg[e["event_ticker"]], hunits, side, tag)
                hunits = side * hunits   # + = hedge long H
            matched_units = min(bus_bid, bus_off) / leg.width
            avoided = np.nan
            if leg_name == "station":
                er = rg[e["event_ticker"]]
                fee_unit = sum(kl.fee(int(round(100 * hv)), a) for hv, a in zip(er["Hv"], er[f"ask_{tag}"]) if hv > 0) / 100.0
                avoided = matched_units * (float(e[f"premask_{tag}"]) - float(e[f"mu_{tag}"]) + fee_unit)
            rows.append(dict(date=date, station=s, leg=leg_name, event=e["event_ticker"], K=float(e["K"]), mu=mu, mu_s=m["mu_s"],
                             p_star=r.p_star, q_star=r.q_star, bid_tick=m["bid_tick"], ask_tick=m["ask_tick"],
                             n_orders=int(len(m["qty"])), hedger_bid_qty=int(m["qty"][m["is_bid"]].sum()),
                             hedger_off_qty=int(m["qty"][~m["is_bid"]].sum()), bus_bid_fill=bus_bid, bus_off_fill=bus_off,
                             house_bid=m["house_bid"], house_off=m["house_off"], cap_bid=m["cap_bid"], cap_off=m["cap_off"],
                             cap_usd=cap_each, x=x, mo_settle=st_["mo_settle"], mo_2h=mo2h, hedge_pnl=hp, hedge_fees=hfee,
                             hedge_contracts=hc, hedge_units=hunits, house_net_units=net_h_units,
                             matched_units=matched_units, kalshi_cost_avoided=avoided, **fz))
    return pd.DataFrame(rows)


def stage_auction() -> None:
    from wi.pool import capital as cap
    pop = pd.read_parquet(CACHE / "population.parquet")
    uw = pd.read_parquet(CACHE / "unit_weights.parquet")
    part = dict(np.load(CACHE / "participants.npz"))
    ev = pd.read_parquet(CACHE / "ladders.parquet")
    rungs = pd.read_parquet(CACHE / "rungs.parquet")
    W = load_weather()
    B = proxy_bundle(W, (1951, 2020), detrend=True)
    rclim = residual_climatology(B)
    resid = kalshi_era_residual(W)
    biz = business_table(pop, part["p2"], uw)
    book0 = imbalance_book(biz)
    out = {}
    deltas = delta_samples(resid)
    runs = {"primary": ("c24", 0.15, None), "coc6": ("c24", 0.06, None), "coc30": ("c24", 0.30, None),
            "cutoff2h": ("c2", 0.15, None), "resid_ladder_mu": ("c24", 0.15, deltas), "resid_trailing5": ("c24", 0.15, None)}
    rclim5 = residual_climatology(B, window=5)
    for name, (tag, coc, dl) in runs.items():
        ch = charges_from_book(B, book0, coc)
        e = ev[ev["sample"] if tag == "c24" else ev["sample_c2"]]
        t0 = time.time()
        df = run_auctions(e, rungs, biz, rclim5 if name == "resid_trailing5" else rclim, resid, ch, tag, deltas=dl)
        df.to_parquet(CACHE / f"auction_{name}.parquet", index=False)
        out[name] = dict(charges={f"{k[0]}/{k[1]}": v for k, v in ch.items()}, n_market_days=int(len(df)),
                         seconds=round(time.time() - t0, 1))
        print(name, len(df), round(time.time() - t0, 1), "s", flush=True)
    save_results("auction_runs", out)


# ----------------------------------------------------------------------------- capital + backtest
LEGS = ("station", "residual")
WIDTH = {"station": 6.0, "residual": 12.0}


def average_book(auc: pd.DataFrame, biz: dict) -> tuple[dict, dict, dict]:
    """Pool's average signed position ($1/degF units, + = long) per (station, leg, month) after
    the Kalshi hedge; station-months without sample days use the station's ratio of pool
    position to net hedger demand (deviation D4). Also average fair price per unit ($)."""
    a = auc.copy()
    a["month"] = pd.to_datetime(a["date"]).dt.month
    a["pos"] = a["house_net_units"] + a["hedge_units"]
    a["mu_usd"] = np.where(a["leg"] == "station", a["mu"], a["mu"])
    a["demand"] = [float(-biz[s]["h"][m].sum()) for s, m in zip(a["station"], a["month"])]
    book, price, src = {}, {}, {}
    for s in STATIONS5:
        for leg in LEGS:
            g = a[(a.station == s) & (a.leg == leg)]
            ratio = g["pos"].sum() / g["demand"].sum() if len(g) and g["demand"].sum() != 0 else 0.0
            mu_all = float(g["mu_usd"].mean()) if len(g) else (3.0 if leg == "station" else 0.0)
            for mo in (5, 6, 7, 8, 9):
                gm = g[g.month == mo]
                if len(gm):
                    book[(s, leg, mo)] = float(gm["pos"].mean()); price[(s, leg, mo)] = float(gm["mu_usd"].mean())
                    src[(s, leg, mo)] = f"auction ({len(gm)} days)"
                else:
                    book[(s, leg, mo)] = float(ratio * -biz[s]["h"][mo].sum()); price[(s, leg, mo)] = mu_all
                    src[(s, leg, mo)] = "ratio x demand (D4)"
    return book, price, src


def unit_matrices(B: dict, years: list[int], calib: tuple[int, int], pricing: str = "proxy") -> dict:
    """(n_years, 153) per-unit P&L matrices of a house LONG unit, per (station, leg).

    pricing="proxy" (PREREG): station leg priced daily at the persistence-forecast fair value.
    pricing="clim" (sensitivity asked by the seat after Phase 2): the cover is priced before the
    forecast is known, at climatology: K fixed per station-month = round(mean T - 3.5), price =
    calibration-window mean of H(T;K). The house then carries forecast-level risk too."""
    from wi.pool import capital as cap
    from wi.pool import scenarios as sc
    mats = {}
    for s in STATIONS5:
        d = B["days"][s]
        if pricing == "clim":
            c = d[(d.index.year >= calib[0]) & (d.index.year <= calib[1])]
            Km = np.floor(c.groupby(c.index.month)["T"].mean() - 3.5 + 0.5)
            Kd = Km.reindex(d.index.month).to_numpy()
            Hd = sc.H(d["T"], Kd)
            cm = pd.Series(sc.H(c["T"], Km.reindex(c.index.month).to_numpy()), index=c.index)
            mu = cm.groupby(cm.index.month).mean().reindex(d.index.month).to_numpy()
            mats[(s, "station")] = cap.season_matrix(pd.Series(Hd - mu, index=d.index), years)
        else:
            mats[(s, "station")] = cap.season_matrix(d["u"], years)
        dr = d.dropna(subset=["r"])
        c = dr[(dr.index.year >= calib[0]) & (dr.index.year <= calib[1])]
        mu_r = c.groupby(c.index.month)["r"].mean()
        mats[(s, "residual")] = cap.season_matrix(d["r"] - mu_r.reindex(d.index.month).to_numpy(), years)
    return mats


def book_pnl(mats: dict, book: dict, legs=LEGS) -> tuple[np.ndarray, np.ndarray]:
    from wi.pool import capital as cap
    month_of = np.array([int(x[:2]) for x in cap.SEASON])
    tot = None
    miss = None
    for (s, leg), M in mats.items():
        if leg not in legs:
            continue
        q = np.array([book[(s, leg, int(mo))] for mo in month_of])
        part = M * q[None, :]
        tot = np.nan_to_num(part) if tot is None else tot + np.nan_to_num(part)
        mm = np.isnan(M) & (q[None, :] != 0)
        miss = mm if miss is None else (miss | mm)
    return tot, miss


def fc_per_day(book: dict, price: dict, legs=LEGS, stations=STATIONS5) -> tuple[float, float]:
    """Average daily full collateral and notional ($) of the book over May-Sep days."""
    from wi.pool import capital as cap
    month_of = [int(x[:2]) for x in cap.SEASON]
    fc = no = 0.0
    for mo in month_of:
        for s in stations:
            for leg in legs:
                q, p = book[(s, leg, mo)], price[(s, leg, mo)]
                w = WIDTH[leg]
                lo = p + (6.0 if leg == "residual" else 0.0)     # long escrow per unit ($)
                fc += q * lo if q > 0 else -q * (w - lo)
                no += abs(q) * w
    n = len(month_of)
    return fc / n, no / n


def capital_block(B: dict, book: dict, price: dict, years: list[int], calib, legs=LEGS, stations=STATIONS5,
                  pricing: str = "proxy") -> dict:
    from wi.pool import capital as cap
    mats = unit_matrices(B, years, calib, pricing)
    mats = {k: v for k, v in mats.items() if k[0] in stations}
    pnl, miss = book_pnl(mats, book, legs)
    keep = miss.sum(axis=1) <= 5 if miss is not None else np.ones(len(years), bool)
    pnl = pnl[keep]
    fcd, nod = fc_per_day(book, price, legs, stations)
    out = {"years": [int(y) for y, k in zip(years, keep) if k], "fc_per_day": fcd, "notional_per_day": nod}
    for Hh in (1, 5, 30):
        c = cap.capital(pnl, Hh, fcd)
        c["CPC_notional"] = c["C"] / (Hh * nod) if nod else None
        c["C_over_FC"] = c["C"] / c["FC"] if c["FC"] else None
        out[f"H{Hh}"] = c
    return out


def stage_capital() -> None:
    from wi.pool import capital as cap
    from wi.pool import markout as mk
    pop = pd.read_parquet(CACHE / "population.parquet")
    uw = pd.read_parquet(CACHE / "unit_weights.parquet")
    part = dict(np.load(CACHE / "participants.npz"))
    biz = business_table(pop, part["p2"], uw)
    auc = pd.read_parquet(CACHE / "auction_primary.parquet")
    book, price, src = average_book(auc, biz)
    W = load_weather()
    res = {"book": {f"{k[0]}/{k[1]}/{k[2]}": dict(units=v, price=price[k], source=src[k]) for k, v in book.items()}}
    variants = {}
    for label, fit, detrend in (("deploy_detrended", (1951, 2025), True), ("deploy_raw", (1951, 2025), False),
                                ("backtest_detrended", (1951, 2020), True)):
        B = proxy_bundle(W, fit, detrend)
        yr_end = fit[1]
        v = {}
        v["pooled_both_legs"] = capital_block(B, book, price, list(range(1999, yr_end + 1)), fit)
        v["pooled_station_leg_only"] = capital_block(B, book, price, list(range(1959, yr_end + 1)), fit, legs=("station",))
        v["per_station_both_legs"] = {s: capital_block(B, book, price, list(range(1999, yr_end + 1)), fit, stations=[s]) for s in STATIONS5}
        if label == "deploy_detrended":
            v["sensitivity_clim_priced_both_legs"] = capital_block(B, book, price, list(range(1999, yr_end + 1)), fit, pricing="clim")
            v["sensitivity_clim_priced_station_only"] = capital_block(B, book, price, list(range(1959, yr_end + 1)), fit,
                                                                     legs=("station",), pricing="clim")
        variants[label] = v
        print(label, {k: round(v["pooled_both_legs"][f"H{k}"]["C"], 0) for k in (1, 5, 30)},
              round(v["pooled_both_legs"]["H30"]["CPC_notional"], 3), flush=True)
    res["capital"] = variants
    head = variants["deploy_detrended"]["pooled_both_legs"]
    cpc = head["H30"]["CPC_notional"]
    res["M3"] = dict(CPC=cpc, C30=head["H30"]["C"], N30=30 * head["notional_per_day"],
                     verdict="LEVERAGE STORY HOLDS" if cpc <= 0.35 else "FULL-COLLATERAL STORY")

    # ---- backtest (M5): each Kalshi-era day's actual book vs the 1951-2020 model
    Bb = proxy_bundle(W, (1951, 2020), True)
    yrs = list(range(1999, 2021))
    mats = unit_matrices(Bb, yrs, (1951, 2020))
    month_of = np.array([int(x[:2]) for x in cap.SEASON])
    a = auc.copy()
    a["date"] = pd.to_datetime(a["date"])
    a["pos"] = a["house_net_units"] + a["hedge_units"]
    a["pnl"] = a["mo_settle"] + a["hedge_pnl"]
    daily = a.groupby("date")["pnl"].sum()
    bt_rows = []
    for date, g in a.groupby("date"):
        cols = month_of == date.month
        scen = np.zeros((len(yrs), int(cols.sum())))
        for _, r in g.iterrows():
            M = mats[(r["station"], r["leg"])][:, cols]
            scen += np.nan_to_num(M) * r["pos"]
        loss = -scen.ravel()
        bt_rows.append(dict(date=date, realized_loss=-float(daily.loc[date]), VaR99=cap.var(loss, 0.99), ES99=cap.es(loss, 0.99)))
    bt = pd.DataFrame(bt_rows).sort_values("date")
    bt["exceed_var"] = bt["realized_loss"] > bt["VaR99"]
    bt["exceed_es"] = bt["realized_loss"] > bt["ES99"]
    bt.to_parquet(CACHE / "backtest_days.parquet", index=False)
    kp = cap.kupiec(len(bt), int(bt["exceed_var"].sum()), 0.01)
    c30_bt = variants["backtest_detrended"]["pooled_both_legs"]["H30"]["C"]
    roll30 = bt.set_index("date")["realized_loss"].rolling(30).sum()
    res["M5"] = dict(kupiec=kp, exceed_es99=int(bt["exceed_es"].sum()), C30_backtest_model=c30_bt,
                     worst_realized_30day_loss=float(roll30.max()), c30_breaches=int((roll30 > c30_bt).sum()),
                     verdict=("PASS" if not kp["rejected"] else f"REJECTED ({kp['direction']})"))
    # ---- markouts, fees, pool return
    a["mo_hedged"] = a["mo_settle"] + a["hedge_pnl"]
    mo = {}
    for (s, leg), g in a.groupby(["station", "leg"]):
        mo[f"{s}/{leg}"] = dict(settle=mk.summarize(g.groupby("date")["mo_settle"].sum()),
                                mo_2h=mk.summarize(g.groupby("date")["mo_2h"].sum()),
                                hedged=mk.summarize(g.groupby("date")["mo_hedged"].sum()),
                                per_unit_day_usd=float(g["mo_settle"].sum() / (np.abs(g["house_net_units"]).sum() or np.nan)),
                                cents_per_contract=float(100 * g["mo_settle"].sum() / ((g["house_bid"] + g["house_off"]).sum() or np.nan)))
    pooled_daily = a.groupby("date")["mo_hedged"].sum()
    mo["pooled"] = dict(hedged=mk.summarize(pooled_daily))
    st_daily = a[a.leg == "station"].pivot_table(index="date", columns="station", values="mo_hedged", aggfunc="sum")
    mo["cross_station_corr_station_leg"] = st_daily.corr().round(3).to_dict()
    res["markouts"] = mo
    fee_cols = ["bps0", "bps10", "bps25", "bps50", "cow50"]
    notional = a["hedger_notional"].sum()
    res["fees"] = {c: dict(total_usd=float(a[c].sum()), per_usd_notional=float(a[c].sum() / notional),
                           per_season_usd=float(a.groupby(a.date.dt.year)[c].sum().mean())) for c in fee_cols}
    res["fees"]["hedger_notional_total"] = float(notional)
    res["fees"]["hedger_improvement_total"] = float(a["hedger_improvement"].sum())
    seasons = a.groupby(a.date.dt.year).agg(fees10=("bps10", "sum"), mo_hedged=("mo_hedged", "sum"), days=("date", "nunique"))
    c30 = res["M3"]["C30"]
    res["pool_return"] = dict(by_season={int(y): dict(fees10=float(r.fees10), mo_hedged=float(r.mo_hedged), days=int(r.days),
                                                      return_on_C30=float((r.fees10 + r.mo_hedged) / c30)) for y, r in seasons.iterrows()},
                              mean_season_return_on_C30=float(((seasons.fees10 + seasons.mo_hedged) / c30).mean()))
    # ---- auction descriptives (M3/M4 of the research draft)
    a["house_fill"] = a["house_bid"] + a["house_off"]
    desc = {}
    for (s, leg), g in a.groupby(["station", "leg"]):
        gross = (g["hedger_bid_qty"] + g["hedger_off_qty"]).sum()
        desc[f"{s}/{leg}"] = dict(days=int(len(g)), no_trade_share=float((g["q_star"] == 0).mean()),
                                  clearing_minus_fair_cents=float((g["p_star"] - 100 * g["mu_s"]).mean()),
                                  house_fill_share=float(g["house_fill"].sum() / g["q_star"].sum()),
                                  internalisation=float(2 * np.minimum(g["bus_bid_fill"], g["bus_off_fill"]).sum() / gross),
                                  hedger_fill_share=float((g["bus_bid_fill"] + g["bus_off_fill"]).sum() / gross),
                                  capacity_binding_share=float(((g["house_bid"] >= g["cap_bid"]) & (g["cap_bid"] > 0) |
                                                                (g["house_off"] >= g["cap_off"]) & (g["cap_off"] > 0)).mean()),
                                  unfilled_hedger_share=float(1 - (g["bus_bid_fill"] + g["bus_off_fill"]).sum() / gross),
                                  kalshi_cost_avoided_per_day=float(g["kalshi_cost_avoided"].mean()) if leg == "station" else None,
                                  hedge_units_mean=float(np.abs(g["hedge_units"]).mean()),
                                  house_net_units_mean=float(g["house_net_units"].mean()))
    res["auction"] = desc
    # variants (CoC, cutoff): summary only
    var_ = {}
    for name in ("coc6", "coc30", "cutoff2h", "resid_ladder_mu", "resid_trailing5"):
        v = pd.read_parquet(CACHE / f"auction_{name}.parquet")
        v["mo_hedged"] = v["mo_settle"] + v["hedge_pnl"]
        var_[name] = dict(days=int(v["date"].nunique()), clearing_minus_fair_cents=float((v["p_star"] - 100 * v["mu_s"]).mean()),
                          mo_hedged_mean_daily=float(v.groupby("date")["mo_hedged"].sum().mean()),
                          fees10_per_usd=float(v["bps10"].sum() / v["hedger_notional"].sum()),
                          mo_hedged_mean_daily_by_market={f"{a}/{b}": float(g.groupby("date")["mo_hedged"].sum().mean())
                                                          for (a, b), g in v.groupby(["station", "leg"])})
    var_["primary"] = dict(days=int(a["date"].nunique()), clearing_minus_fair_cents=float((a["p_star"] - 100 * a["mu_s"]).mean()),
                           mo_hedged_mean_daily=float(pooled_daily.mean()), fees10_per_usd=res["fees"]["bps10"]["per_usd_notional"])
    res["auction_variants"] = var_
    # in-sample sensitivity: capital from the realized Kalshi-era daily P&L (labelled in-sample)
    rz = cap.season_matrix(daily, sorted(daily.index.year.unique()))
    res["capital_kalshi_era_in_sample"] = {f"H{h}": cap.capital(np.nan_to_num(rz), h, head["fc_per_day"]) for h in (1, 5, 30)}
    save_results("capital", res)
    print(json.dumps({k: res[k] for k in ["M3", "M5"]}, indent=1, default=float))


# ----------------------------------------------------------------------------- revision (M4)
def nclimgrid_revision(n_days: int = 5) -> dict:
    """Descriptive: nClimGrid-Daily prelim vintage at label day + N (latest vintage created <= D+N)
    vs the scaled (final) file for Apr-Aug 2026 cells in the 40 km discs (01-04 outputs)."""
    import glob
    vp = ROOT / "data" / "cache" / "vintages" / "nclimgrid_prelim.parquet"
    if not vp.exists():
        return dict(status="not measured: no vintages")
    v = pd.read_parquet(vp)
    v["vintage_created"] = pd.to_datetime(v["vintage_created"]); v["label_day"] = pd.to_datetime(v["label_day"])
    v = v[v["vintage_created"] <= v["label_day"] + pd.Timedelta(days=n_days)]
    v = v.sort_values("vintage_created").groupby(["station", "cell_id", "label_day"]).last().reset_index()
    fs = [f for f in glob.glob(str(ROOT / "data/cache/grid_disc/source=nclimgrid/station=*/part-2026*.parquet"))]
    g = pd.concat([pd.read_parquet(f, columns=["station", "cell_id", "label_day", "tmax_f_tenths", "prcp_hundredths_in", "status"]) for f in fs])
    g = g[g["status"] == "scaled"].copy()
    g["label_day"] = pd.to_datetime(g["label_day"]); g["station"] = g["station"].astype(str)
    j = v.merge(g, on=["station", "cell_id", "label_day"], suffixes=("_pre", "_fin"))
    j = j.dropna(subset=["tmax_f_tenths_pre", "tmax_f_tenths_fin"])
    dT = (j["tmax_f_tenths_pre"].astype(float) - j["tmax_f_tenths_fin"].astype(float)).abs() / 10.0
    wet_pre = j["prcp_hundredths_in_pre"].astype(float) >= 10; wet_fin = j["prcp_hundredths_in_fin"].astype(float) >= 10
    by = j.assign(moved=dT >= 0.5, flip=wet_pre != wet_fin).groupby("station")[["moved", "flip"]].mean().round(4)
    return dict(N_days=n_days, n_vintages=int(pd.read_parquet(vp, columns=["vintage_created"])["vintage_created"].nunique()),
                cell_days_compared=int(len(j)), label_days=[str(j["label_day"].min().date()), str(j["label_day"].max().date())],
                tmax_moves_ge_0p5F_share=float((dT >= 0.5).mean()), tmax_abs_change_mean_F=float(dT.mean()),
                tmax_abs_change_p99_F=float(dT.quantile(0.99)), wet_flag_flip_share=float((wet_pre != wet_fin).mean()),
                by_station=by.to_dict("index"))


def stage_revision() -> None:
    from wi.oracle import revision as rv
    from wi.pool import kalshi_leg as kl
    prods = rv.load_all()
    v = rv.settlement_vintage(prods)
    v = v[v["day"].dt.month.isin([5, 6, 7, 8, 9])].copy()
    auc = pd.read_parquet(CACHE / "auction_primary.parquet")
    st = auc[auc["leg"] == "station"].copy()
    st["day"] = pd.to_datetime(st["date"])
    st["units"] = (st["hedger_bid_qty"] + st["hedger_off_qty"]) / 6.0
    j = st.merge(v, left_on=["station", "day"], right_on=["station", "day"], how="left")
    j["moved"] = (np.abs(kl.H(j["tmax_latest"], j["K"]) - kl.H(j["tmax_settle"], j["K"])) >= 0.5) & j["tmax_settle"].notna()
    weighted = float((j["units"] * j["moved"]).sum() / j["units"].sum())
    v["changed_any"] = (v["tmax_latest"] != v["tmax_settle"]) & v["tmax_settle"].notna()
    unweighted = float(v["changed_any"].mean())
    # missing at T+N (no final product by D+1 12:00Z)
    missing = v.groupby("station")["tmax_settle"].apply(lambda s: int(s.isna().sum())).to_dict()
    # preliminary (same-day ~4 PM) vs final: why N >= 1 day
    pre = prods[prods["prelim"] & prods["tmax"].notna()].sort_values("issued_utc").groupby(["station", "day"]).last()["tmax"]
    cmp_ = v.set_index(["station", "day"]).join(pre.rename("tmax_prelim"), how="inner")
    prelim_diff = float((cmp_["tmax_prelim"] != cmp_["tmax_settle"]).mean())
    # CLI settlement vintage vs GHCN-D TMAX (secondary)
    W = load_weather()
    g = []
    for s in STATIONS5:
        gs = W["tmax"][s] if s != "MDW" else W["tmax"]["MDW"]
        t = v[v["station"] == s].set_index("day")
        t = t.join(gs.rename("ghcn"), how="left")
        g.append(t.assign(station=s))
    g = pd.concat(g)
    ghcn_diff = float(((g["ghcn"] != g["tmax_settle"]) & g["ghcn"].notna() & g["tmax_settle"].notna()).mean())
    ncg = nclimgrid_revision()
    out = dict(n_products=int(len(prods)), n_station_days=int(len(v)), nclimgrid_prelim_vs_scaled=ncg,
               days_with_multiple_final_products=int((v["n_final_products"] > 1).sum()),
               corrections_flagged=int(((prods["correction"] != "") | prods["corrected_text"]).sum()),
               revision_share_units_weighted=weighted, revision_share_unweighted_any_change=unweighted,
               missing_final_by_D1_12Z=missing, prelim_vs_final_differs_share=prelim_diff,
               cli_settle_vs_ghcn_tmax_differs_share=ghcn_diff,
               M4=dict(share=weighted, verdict="ACCEPTABLE" if weighted <= 0.02 else "NOT ACCEPTABLE"))
    save_results("revision", out)
    write_source_manifest()
    print(json.dumps(out, indent=1))


# ----------------------------------------------------------------------------- report
def _fmt(x, nd=3):
    if x is None:
        return "—"
    if isinstance(x, (int, np.integer)):
        return f"{x:,}"
    if isinstance(x, float):
        if abs(x) >= 1000:
            return f"{x:,.0f}"
        return f"{x:.{nd}f}"
    return str(x)


def stage_report() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    R = load_results()
    prereg = (REPORT / "PREREG.md").read_bytes()
    pri_sha = hashlib.sha256((REPORT / "priors_2026-09-30.csv").read_bytes()).hexdigest()
    auc = pd.read_parquet(CACHE / "auction_primary.parquet")
    auc["date"] = pd.to_datetime(auc["date"])
    days = auc["date"].nunique()
    hedger_notional_day = float(auc["hedger_notional"].sum() / days)
    hedger_order_notional_day = float((auc["hedger_bid_qty"] + auc["hedger_off_qty"]).sum() / days)
    cap_ = R["capital"]
    head = cap_["capital"]["deploy_detrended"]["pooled_both_legs"]
    st_only = cap_["capital"]["deploy_detrended"]["pooled_station_leg_only"]
    clim_b = cap_["capital"]["deploy_detrended"]["sensitivity_clim_priced_both_legs"]
    clim_s = cap_["capital"]["deploy_detrended"]["sensitivity_clim_priced_station_only"]
    # pool return under the trailing-5 residual pricing sensitivity
    t5 = pd.read_parquet(CACHE / "auction_resid_trailing5.parquet"); t5["date"] = pd.to_datetime(t5["date"])
    t5["mo_hedged"] = t5["mo_settle"] + t5["hedge_pnl"]
    s5 = t5.groupby(t5.date.dt.year).agg(f=("bps10", "sum"), m=("mo_hedged", "sum"))
    ret_t5 = float(((s5.f + s5.m) / head["H30"]["C"]).mean())
    results = dict(
        meta=dict(written_utc=utcnow(), prereg_frozen_utc="2026-09-30T13:26:00Z",
                  prereg_sha256=hashlib.sha256(prereg).hexdigest(), priors_sha256=pri_sha,
                  seed=SEED, code="scripts/eval04.py + src/wi/{population,exposure,auction,pool,oracle}"),
        verdicts=dict(M1=R["netting"]["M1"], M2=R["netting"]["M2"], M3=cap_["M3"], M4=R["revision"]["M4"], M5=cap_["M5"]),
        population=R["population"], weather=R["weather"], sample=R["sample"], netting=R["netting"],
        auction=cap_["auction"], auction_variants=cap_["auction_variants"], auction_runs=R["auction_runs"],
        capital=cap_["capital"], capital_book=cap_["book"], capital_kalshi_era_in_sample=cap_["capital_kalshi_era_in_sample"],
        markouts=cap_["markouts"], fees=cap_["fees"], pool_return=dict(cap_["pool_return"], mean_season_return_on_C30_resid_trailing5=ret_t5),
        revision=R["revision"],
        derived=dict(days=int(days), hedger_fill_notional_per_day=hedger_notional_day,
                     hedger_order_notional_per_day=hedger_order_notional_day,
                     capital_per_usd_gross_hedger_cover_H30=head["H30"]["C"] / (30 * hedger_order_notional_day)))
    (REPORT / "results.json").write_text(json.dumps(results, indent=1, default=float))

    handoff = dict(
        written_utc=utcnow(), source="reports/eval-04-05/results.json", for_phases=[7, 14, 16],
        caveats=["sector priors LOW confidence; netting collapses under the shrink-to-common null",
                 "capital tail = worst historical 30-day window on 26 joint seasons (1999-2025, both legs) / 64 (station leg only)",
                 "persistence-forecast pricing in scenarios is conservative vs Kalshi (backtest: 1 exceedance in 599 days)",
                 "Kalshi hedge capped at 5 units per city-day; the pool carries the rest"],
        capital_per_usd_cover_H30=dict(
            per_usd_pool_notional_both_legs=head["H30"]["CPC_notional"],
            per_usd_pool_notional_station_leg_only=st_only["H30"]["CPC_notional"],
            per_usd_pool_notional_clim_priced_both_legs=clim_b["H30"]["CPC_notional"],
            per_usd_pool_notional_clim_priced_station_only=clim_s["H30"]["CPC_notional"],
            per_usd_gross_hedger_cover=head["H30"]["C"] / (30 * hedger_order_notional_day),
            C_over_full_collateral=head["H30"]["C_over_FC"]),
        C30_usd=head["H30"]["C"], ES99_30d_usd=head["H30"]["ES99"], worst_window_30d_usd=head["H30"]["worst_window"],
        junior_ES95_30d_usd=head["H30"]["ES95_junior"], junior_share=head["H30"]["ES95_junior"] / head["H30"]["C"],
        capital_H={f"H{h}": dict(C=head[f"H{h}"]["C"], ES99=head[f"H{h}"]["ES99"], worst_window=head[f"H{h}"]["worst_window"],
                                 FC=head[f"H{h}"]["FC"], junior=head[f"H{h}"]["ES95_junior"]) for h in (1, 5, 30)},
        pool_book_per_day=dict(notional_usd=head["notional_per_day"], full_collateral_usd=head["fc_per_day"]),
        fee_income_per_usd_notional={k: v["per_usd_notional"] for k, v in cap_["fees"].items() if isinstance(v, dict)},
        fee_income_per_season_usd={k: v["per_season_usd"] for k, v in cap_["fees"].items() if isinstance(v, dict)},
        netting_ratio=dict(central=R["netting"]["central"], null=R["netting"]["null"],
                           ensemble_p10_p50_p90={k: [v["p10"], v["p50"], v["p90"]] for k, v in R["netting"]["ensemble"].items()}),
        house_markout_mean_daily_usd=dict(primary=cap_["markouts"]["pooled"]["hedged"]["mean"],
                                          resid_trailing5=cap_["auction_variants"]["resid_trailing5"]["mo_hedged_mean_daily"]),
        revision=dict(cli_share=R["revision"]["M4"]["share"],
                      nclimgrid_prelim_D5_vs_scaled_tmax_moves=R["revision"]["nclimgrid_prelim_vs_scaled"].get("tmax_moves_ge_0p5F_share"),
                      nclimgrid_wet_flag_flips=R["revision"]["nclimgrid_prelim_vs_scaled"].get("wet_flag_flip_share")),
        margin_placeholders_for_phase7=dict(
            house_capacity_full_collateral_per_day_usd=CAPACITY_USD,
            kalshi_hedge_cap_units_per_city_day=5, protocol_fee_bps_primary=10),
        excluded="forecast-level risk of pricing before the forecast is known is NOT in the headline; it is the clim-priced sensitivity row")
    (REPORT / "handoff.json").write_text(json.dumps(handoff, indent=1, default=float))

    # ---- figures
    fig, ax = plt.subplots(figsize=(7, 3.5))
    sts = STATIONS5 + ["pooled"]
    x = np.arange(len(sts))
    ens = R["netting"]["ensemble"]
    ax.bar(x - 0.2, [R["netting"]["central"][s] for s in sts], 0.4, label="central priors")
    ax.bar(x + 0.2, [R["netting"]["null"][s] for s in sts], 0.4, label="shrink-to-common null")
    ax.errorbar(x - 0.2, [ens[s]["p50"] for s in sts], yerr=[[ens[s]["p50"] - ens[s]["p10"] for s in sts], [ens[s]["p90"] - ens[s]["p50"] for s in sts]],
                fmt="none", ecolor="k", capsize=3, label="ensemble p10-p90")
    ax.axhline(0.25, ls="--", c="grey", lw=0.8); ax.axhline(0.10, ls=":", c="grey", lw=0.8)
    ax.set_xticks(x, sts); ax.set_ylabel("netting ratio"); ax.legend(fontsize=7); ax.set_title("M1/M2 netting ratio (2 % participation)")
    fig.tight_layout(); fig.savefig(REPORT / "figures" / "netting_ratio.png", dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 3.5))
    Hs = [1, 5, 30]
    for key, lab in (("C", "capital C_h"), ("ES99", "ES99"), ("worst_window", "worst window"), ("FC", "full collateral")):
        ax.plot(Hs, [head[f"H{h}"][key] for h in Hs], marker="o", label=lab)
    ax.plot(Hs, [clim_b[f"H{h}"]["C"] for h in Hs], marker="x", ls="--", label="C_h, clim-priced sensitivity")
    ax.set_xlabel("horizon h (days)"); ax.set_ylabel("$"); ax.set_yscale("log"); ax.legend(fontsize=7)
    ax.set_title("Pool capital, pooled book (both legs, 1999-2025)")
    fig.tight_layout(); fig.savefig(REPORT / "figures" / "capital_by_horizon.png", dpi=130); plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 3.5))
    auc["mo_hedged"] = auc["mo_settle"] + auc["hedge_pnl"]
    for lab, df in (("primary", auc), ("residual priced on trailing 5 y", t5)):
        s = df.groupby("date")["mo_hedged"].sum().sort_index().cumsum()
        ax.plot(s.index, s.to_numpy(), label=lab)
    ax.set_ylabel("cumulative house P&L after Kalshi hedge ($)"); ax.legend(fontsize=7); ax.set_title("House markouts, Kalshi-era warm seasons")
    fig.tight_layout(); fig.savefig(REPORT / "figures" / "house_markout_cumulative.png", dpi=130); plt.close(fig)

    bt = pd.read_parquet(CACHE / "backtest_days.parquet")
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.plot(bt["date"], bt["realized_loss"], lw=0.6, label="realised 1-day loss")
    ax.plot(bt["date"], bt["VaR99"], lw=0.8, label="model 1-day VaR99 (1951-2020 fit)")
    ax.legend(fontsize=7); ax.set_ylabel("$"); ax.set_title("M5 backtest")
    fig.tight_layout(); fig.savefig(REPORT / "figures" / "backtest_var.png", dpi=130); plt.close(fig)

    # ---- tables.md
    L = ["# EVAL-04/05 tables (generated by scripts/eval04.py --stage report)", "",
         f"Written {utcnow()}; PREREG frozen 2026-09-30T13:26:00Z (sha256 {hashlib.sha256(prereg).hexdigest()[:16]}...).", ""]
    L += ["## Verdicts", "", "| ID | metric | value | verdict |", "|---|---|---|---|",
          f"| M1 | stations with central NR ≥ 0.25 | {R['netting']['M1']['stations_ge_0p25']} of 5 | {R['netting']['M1']['verdict']} |",
          f"| M2 | pooled NR under the null | {_fmt(R['netting']['null']['pooled'])} | {R['netting']['M2']['verdict']} |",
          f"| M3 | CPC = C_30 / N_30 (both legs) | {_fmt(cap_['M3']['CPC'])} | {cap_['M3']['verdict']} |",
          f"| M4 | CLI revision share (units) | {_fmt(R['revision']['M4']['share'])} | {R['revision']['M4']['verdict']} |",
          f"| M5 | Kupiec: {cap_['M5']['kupiec']['x']} exceedances in {cap_['M5']['kupiec']['n']} days (expected {_fmt(cap_['M5']['kupiec']['expected'], 1)}), LR {_fmt(cap_['M5']['kupiec']['LR'], 2)} | p = {_fmt(cap_['M5']['kupiec']['p_value'])} | {cap_['M5']['verdict']} |", ""]
    L += ["## Sample (hedge days, May-Sep, all rungs quoted at T-24h)", "", "| station | days | first | last |", "|---|---|---|---|"]
    for s, v in R["sample"]["by_station"].items():
        L.append(f"| {s} | {v['days']} | {v['first'][:10]} | {v['last'][:10]} |")
    L += ["", f"Filter counts: {R['sample']['filter_counts']}", ""]
    L += ["## Population (ZBP 2023, < 50 employees, prior NAICS, nearest station ≤ 40 km)", "",
          "| station | rows | establishments | daily revenue ($) | participants at 2 % |", "|---|---|---|---|---|"]
    for s, v in R["population"]["by_station"].items():
        L.append(f"| {s} | {_fmt(int(v['rows']))} | {_fmt(v['est'])} | {_fmt(v['daily_rev_total'])} | {R['netting']['participants']['p2'][s]} |")
    L += ["", f"Population parquet: {R['population']['rows']} rows, md5 {R['population']['md5']}.", ""]
    L += ["## Netting ratio", "", "| station | central | null | ensemble p10 / p50 / p90 | 0.5 % | 10 % | persistence-weighted | ZIP-level | rain (central) |",
          "|---|---|---|---|---|---|---|---|---|"]
    N = R["netting"]
    for s in sts:
        e = N["ensemble"][s]
        L.append(f"| {s} | {_fmt(N['central'][s])} | {_fmt(N['null'][s])} | {_fmt(e['p10'])} / {_fmt(e['p50'])} / {_fmt(e['p90'])} | "
                 f"{_fmt(N['central_p0.5'][s])} | {_fmt(N['central_p10'][s])} | {_fmt(N['central_p2_persist'][s])} | "
                 f"{_fmt(N['zip_level'].get(s))} | {_fmt(N['rain_central'].get(s))} |")
    L += ["", f"Metro level (NYC+EWR+TTN as one contract): {_fmt(N['metro_level']['NYC-metro'])}. Null c = {_fmt(N['null_c'])} %/°F. "
          f"Ensemble share of draws with M1 MATERIAL: {_fmt(N['ensemble_M1_material_share'])}.", ""]
    L += ["Leftover units per station-day (central, 2 %): " + "; ".join(
        f"{s} {_fmt(v['mean_units'], 0)} of {_fmt(v['mean_gross_units'], 0)} gross ($1/°F units)" for s, v in N["leftover_units_per_day"].items()), ""]
    L += ["## Auction on history (primary: T-24h, CoC 15 %, 10 bps)", "",
          "| market | days | p* − fair (c) | house fill share | internalisation | hedger fill share | capacity binding | Kalshi cost avoided $/day | house net units/day |",
          "|---|---|---|---|---|---|---|---|---|"]
    for k, v in cap_["auction"].items():
        L.append(f"| {k} | {v['days']} | {_fmt(v['clearing_minus_fair_cents'], 2)} | {_fmt(v['house_fill_share'])} | {_fmt(v['internalisation'])} | "
                 f"{_fmt(v['hedger_fill_share'])} | {_fmt(v['capacity_binding_share'])} | {_fmt(v['kalshi_cost_avoided_per_day'], 0)} | {_fmt(v['house_net_units_mean'], 0)} |")
    L += ["", "No-trade share is 0 on every market-day (the house always quotes).", ""]
    L += ["## Capital (deployable, detrended; $)", "", "| book | years | h | C_h | ES99 | worst window | FC | binding | junior ES95 | C / notional |", "|---|---|---|---|---|---|---|---|---|---|"]
    for lab, b in (("both legs", head), ("station leg only", st_only), ("both legs, clim-priced", clim_b), ("station only, clim-priced", clim_s)):
        for h in Hs:
            c = b[f"H{h}"]
            L.append(f"| {lab} | {b['years'][0]}-{b['years'][-1]} ({len(b['years'])}) | {h} | {_fmt(c['C'])} | {_fmt(c['ES99'])} | {_fmt(c['worst_window'])} | "
                     f"{_fmt(c['FC'])} | {c['binding']} | {_fmt(c['ES95_junior'])} | {_fmt(c['CPC_notional'])} |")
    for lab in ("deploy_raw", "backtest_detrended"):
        b = cap_["capital"][lab]["pooled_both_legs"]["H30"]
        L.append(f"| both legs, {lab} | | 30 | {_fmt(b['C'])} | {_fmt(b['ES99'])} | {_fmt(b['worst_window'])} | {_fmt(b['FC'])} | {b['binding']} | {_fmt(b['ES95_junior'])} | {_fmt(b['CPC_notional'])} |")
    L += ["", "Per station alone (both legs, h = 30): " + "; ".join(
        f"{s} C {_fmt(v['H30']['C'])} (C/notional {_fmt(v['H30']['CPC_notional'])})" for s, v in cap_["capital"]["deploy_detrended"]["per_station_both_legs"].items()),
          f"Book per day: notional ${_fmt(head['notional_per_day'])}, full collateral ${_fmt(head['fc_per_day'])}. "
          f"Gross hedger order notional per day ${_fmt(hedger_order_notional_day)} → C_30 per $ of gross hedger cover {_fmt(results['derived']['capital_per_usd_gross_hedger_cover_H30'])}.",
          f"Kalshi-era in-sample (realised daily P&L, 4 seasons): C_30 {_fmt(cap_['capital_kalshi_era_in_sample']['H30']['C'])}.", ""]
    L += ["## House markouts ($ per day; after hedge where noted)", "", "| market | mean settle | 95 % CI | mean 2h | worst day | worst 30-day | win rate | c/contract |", "|---|---|---|---|---|---|---|---|"]
    for k, v in cap_["markouts"].items():
        if k in ("pooled", "cross_station_corr_station_leg"):
            continue
        s_ = v["settle"]
        L.append(f"| {k} | {_fmt(s_['mean'], 0)} | [{_fmt(s_['ci95'][0], 0)}, {_fmt(s_['ci95'][1], 0)}] | {_fmt(v['mo_2h']['mean'], 0)} | {_fmt(s_['worst_day'], 0)} | "
                 f"{_fmt(s_['worst_30day'], 0)} | {_fmt(s_['win_rate'], 2)} | {_fmt(v['cents_per_contract'], 2)} |")
    p_ = cap_["markouts"]["pooled"]["hedged"]
    L += [f"| pooled, hedged | {_fmt(p_['mean'], 0)} | [{_fmt(p_['ci95'][0], 0)}, {_fmt(p_['ci95'][1], 0)}] | | {_fmt(p_['worst_day'], 0)} | {_fmt(p_['worst_30day'], 0)} | {_fmt(p_['win_rate'], 2)} | |", ""]
    L += ["Variants (pooled mean daily house P&L after hedge): " + "; ".join(f"{k} {_fmt(v['mo_hedged_mean_daily'], 0)}" for k, v in cap_["auction_variants"].items()), ""]
    L += ["## Fees", "", "| rule | $ per $ hedger notional | $ per season |", "|---|---|---|"]
    for k, v in cap_["fees"].items():
        if isinstance(v, dict):
            L.append(f"| {k} | {v['per_usd_notional']:.4f} | {_fmt(v['per_season_usd'])} |")
    L += ["", f"Pool return on C_30 per season (10 bps + house P&L): primary {_fmt(cap_['pool_return']['mean_season_return_on_C30'])}; residual on trailing-5-y pricing {_fmt(ret_t5)}.", ""]
    rv_ = R["revision"]; ng = rv_["nclimgrid_prelim_vs_scaled"]
    L += ["## Revision", "",
          f"- CLI: {rv_['n_products']} products, {rv_['n_station_days']} station-days (May-Sep 2021-2026); {rv_['days_with_multiple_final_products']} days with more than one final report; "
          f"payout-moving revisions after D+1 12:00Z: {rv_['revision_share_units_weighted']:.3%} of units, {rv_['revision_share_unweighted_any_change']:.3%} of days. "
          f"No final report by D+1 12:00Z: {rv_['missing_final_by_D1_12Z']}. Same-day preliminary differs from final on {rv_['prelim_vs_final_differs_share']:.1%} of days. "
          f"CLI settlement value vs GHCN-D TMAX differ on {rv_['cli_settle_vs_ghcn_tmax_differs_share']:.2%} of days.",
          f"- nClimGrid-Daily prelim at label day + 5 vs scaled (Apr-Aug 2026, {ng.get('cell_days_compared')} cell-days, {ng.get('n_vintages')} vintages): "
          f"Tmax moves ≥ 0.5 °F on {ng.get('tmax_moves_ge_0p5F_share', 0):.1%} (mean |Δ| {ng.get('tmax_abs_change_mean_F', 0):.2f} °F, p99 {ng.get('tmax_abs_change_p99_F', 0):.1f} °F); wet-day flag flips {ng.get('wet_flag_flip_share', 0):.1%}.", ""]
    (REPORT / "tables.md").write_text("\n".join(L) + "\n")
    print("wrote results.json, handoff.json, tables.md, figures/")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--stage", action="append", default=[])
    a = ap.parse_args()
    order = ["population", "units", "ladders", "netting", "auction", "capital", "revision", "report"]
    for s in (order if a.all else a.stage):
        t = time.time()
        print(f"[eval04] {utcnow()} stage {s} ...", flush=True)
        globals()[f"stage_{s}"]()
        print(f"[eval04] stage {s} done in {time.time() - t:.1f}s", flush=True)
