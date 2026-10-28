"""Loaders (and the few Phase 3 top-up pulls) for EVAL-02 / EVAL-03.

Everything returned is on the CLI calendar day (docs/CONVENTIONS.md section 1); grids are moved onto it
only through align.py. Raw downloads never enter the repo: top-up pulls land in data/cache/eval03/ and
grid files are read from memory and discarded (CONVENTIONS section 12, 3 GiB floor).

Top-up pulls (run once, `uv run python scripts/eval03.py --pull`):
- IEM daily.py for the Q5 stations Phase 1 did not pull (JRB, WRI, VAY, DYL, PNE, LOM, CKZ, IGQ, LOT,
  06C, JOT, FXE), one request per network-year, 60 s apart.
- IEM json/cli.py for the non-settlement CLI stations (LGA, JFK, ORD, LOT, PWK, DPA, FLL, ISP, UGN).
- NCEI nClimGrid county averages (tmax, prcp) for every registry county (Phase 1 kept only 5 counties).
- NCEI nClimGrid monthly grids, streamed, to read the cell containing every registry station (Phase 1
  kept 40 km discs around S, which miss FRG, LOM, CKZ, DPA, JOT, FXE, ISP, BLM, UGN, DJT).
"""
from __future__ import annotations

import datetime as dt
import glob
import io
import shutil
import time
from pathlib import Path

import numpy as np
import pandas as pd

from wi.eval03 import align
from wi.eval03.points import STATIONS, needed_codes

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "data" / "cache"
E3 = CACHE / "eval03"
WEATHER = CACHE / "weather"
DISC = CACHE / "grid_disc"
UA = "weather-insurance-prototype/0.1 (research; keyless public reads)"
IEM_DAILY = "https://mesonet.agron.iastate.edu/cgi-bin/request/daily.py"
IEM_CLI = "https://mesonet.agron.iastate.edu/json/cli.py"
NCEI = "https://www.ncei.noaa.gov/data/nclimgrid-daily/access"
DISK_FLOOR = 3 * 2**30
YEARS = (2024, 2025, 2026)
LAST_DAY = "2026-09-29"

TOPUP_IEM = ["JRB", "WRI", "VAY", "DYL", "PNE", "LOM", "CKZ", "IGQ", "LOT", "06C", "JOT", "FXE"]
TOPUP_CLI = ["LGA", "JFK", "ORD", "LOT", "PWK", "DPA", "FLL", "ISP", "UGN"]


def _utc() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _disk_ok() -> None:
    free = shutil.disk_usage(ROOT).free
    if free < DISK_FLOOR:
        raise RuntimeError(f"OBJECTION: disk floor hit ({free / 2**30:.2f} GiB free)")


def _get(url: str, params: dict | None = None, tries: int = 8):
    import requests

    last = ""
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers={"User-Agent": UA}, timeout=300)
            if r.status_code == 200 and "over capacity" not in r.text[:200] and not r.text.startswith("ERROR"):
                return r
            if r.status_code == 404:
                return r
            last = f"HTTP {r.status_code} {r.text[:100]!r}"
        except Exception as e:  # noqa: BLE001
            last = repr(e)
        time.sleep(min(15 * (i + 1), 90))
    raise RuntimeError(f"{url} {params}: {last}")


def _log(row: dict) -> None:
    p = E3 / "pull_manifest.csv"
    df = pd.DataFrame([row])
    df.to_csv(p, mode="a", header=not p.exists(), index=False)


# ------------------------------------------------------------------------------------------ pulls
def pull_iem() -> None:
    out = E3 / "iem"
    out.mkdir(parents=True, exist_ok=True)
    by_net: dict[str, list[str]] = {}
    for c in TOPUP_IEM:
        by_net.setdefault(STATIONS[c].network, []).append(c)
    first = True
    for net, codes in sorted(by_net.items()):
        for y in YEARS:
            f = out / f"{net}_{y}.csv"
            if f.exists() and f.stat().st_size > 0:
                continue
            if not first:
                time.sleep(60)  # CONVENTIONS section 12: >= 60 s between IEM bulk requests
            first = False
            _disk_ok()
            ets = min(dt.date(y, 12, 31), dt.date.fromisoformat(LAST_DAY)).isoformat()
            params = [("network", net), *[("stations", c) for c in codes], ("sts", f"{y}-01-01"),
                      ("ets", ets), ("format", "csv")]
            r = _get(IEM_DAILY, params)
            if not r.text.startswith("station,day"):
                raise RuntimeError(f"bad IEM header {net} {y}: {r.text[:80]!r}")
            f.write_text(r.text)
            _log(dict(dataset="iem_daily", url=r.url, bytes=len(r.content), fetched_utc=_utc(), path=str(f.relative_to(ROOT))))
            print("iem", net, y, len(r.text.splitlines()) - 1, "rows", flush=True)


def pull_cli() -> None:
    out = E3 / "cli"
    out.mkdir(parents=True, exist_ok=True)
    for c in TOPUP_CLI:
        for y in YEARS:
            f = out / f"{c}_{y}.csv"
            if f.exists() and f.stat().st_size > 0:
                continue
            r = _get(IEM_CLI, dict(station="K" + c, year=y, fmt="csv"))
            if not r.text.startswith("station,valid"):
                print("cli", c, y, "no data:", r.text[:80].replace("\n", " "))
                f.write_text("")
            else:
                f.write_text(r.text)
            _log(dict(dataset="iem_cli", url=r.url, bytes=len(r.content), fetched_utc=_utc(), path=str(f.relative_to(ROOT))))
            print("cli", c, y, len(r.text.splitlines()) - 1, "rows", flush=True)
            time.sleep(10)


def _months(start="2024-01", end="2026-09") -> list[str]:
    y, m = map(int, start.split("-"))
    ye, me = map(int, end.split("-"))
    out = []
    while (y, m) <= (ye, me):
        out.append(f"{y}{m:02d}")
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


def pull_county() -> None:
    counties = sorted({s.county for s in STATIONS.values()})
    f = E3 / "county_daily.parquet"
    if f.exists():
        return
    rows = []
    for ym in _months():
        for var in ("tmax", "prcp"):
            got = None
            for status in ("scaled", "prelim"):
                url = f"{NCEI}/averages/{ym[:4]}/{var}-{ym}-cty-{status}.csv"
                _disk_ok()
                r = _get(url)
                time.sleep(0.5)
                if r.status_code == 200:
                    got = status
                    break
            if got is None:
                print("county", var, ym, "unavailable")
                continue
            _log(dict(dataset="nclimgrid_county", url=url, bytes=len(r.content), fetched_utc=_utc(), path="(parsed, not kept)"))
            for line in r.content.decode("latin-1").splitlines():
                p = [x.strip() for x in line.split(",")]
                if len(p) < 7 or p[2] not in counties:
                    continue
                y, m = int(p[3]), int(p[4])
                for k, v in enumerate(p[6:], start=1):
                    try:
                        day = dt.date(y, m, k)
                    except ValueError:
                        continue
                    x = float(v) if v not in ("", "NA") else np.nan
                    rows.append((p[2], day, var, np.nan if x <= -99 else x, got))
            print("county", var, ym, got, flush=True)
    df = pd.DataFrame(rows, columns=["county", "label_day", "var", "value", "status"])
    miss = sorted(set(counties) - set(df.county))
    if miss:
        print("county names not found in NCEI files:", miss)
    df.to_parquet(f, index=False)


def pull_nclimgrid_points() -> None:
    """Stream each monthly nClimGrid-Daily grid and keep the cell containing every registry station."""
    import netCDF4 as nc

    out = E3 / "nclimgrid_points"
    out.mkdir(parents=True, exist_ok=True)
    codes = needed_codes()
    raw = ROOT / "data" / "raw" / "nclimgrid"
    for ym in _months():
        f = out / f"{ym}.parquet"
        if f.exists():
            continue
        local = [raw / f"ncdd-{ym}-grd-scaled.nc", raw / f"ncdd-{ym}-grd-prelim.nc"]
        local = [p for p in local if p.exists()]
        if local:
            b, status, url = local[0].read_bytes(), local[0].name.split("-")[-1][:-3], str(local[0].relative_to(ROOT))
        else:
            _disk_ok()
            url = f"{NCEI}/grids/{ym[:4]}/ncdd-{ym}-grd-scaled.nc"
            r = _get(url)
            status = "scaled"
            if r.status_code == 404:
                url = url.replace("scaled", "prelim")
                r = _get(url)
                status = "prelim"
            b = r.content
            time.sleep(1.0)
        ds = nc.Dataset("mem.nc", mode="r", memory=b)
        lat = np.asarray(ds["lat"][:], float)
        lon = np.asarray(ds["lon"][:], float)
        days = [dt.date(1800, 1, 1) + dt.timedelta(days=int(v)) for v in ds["time"][:]]
        recs = []
        idx = {}
        for c in codes:
            s = STATIONS[c]
            i, j = int(np.argmin(np.abs(lat - s.lat))), int(np.argmin(np.abs(lon - s.lon)))
            idx[c] = (i, j)
        tm = np.ma.filled(ds["tmax"][:, :, :].astype("float64"), np.nan)
        pr = np.ma.filled(ds["prcp"][:, :, :].astype("float64"), np.nan)
        for c, (i, j) in idx.items():
            for k, d in enumerate(days):
                recs.append((c, f"{lat[i]:.4f}_{lon[j]:.4f}", lat[i], lon[j], d, tm[k, i, j], pr[k, i, j], status))
        ds.close()
        pd.DataFrame(recs, columns=["code", "cell_id", "lat", "lon", "label_day", "tmax_c", "prcp_mm", "status"]).to_parquet(f, index=False)
        _log(dict(dataset="nclimgrid_grid_points", url=url, bytes=len(b), fetched_utc=_utc(), path=str(f.relative_to(ROOT))))
        print("nclimgrid points", ym, status, len(b), flush=True)
        del b, tm, pr


# ------------------------------------------------------------------------------------------ loaders
def iem_daily() -> pd.DataFrame:
    """IEM daily summary, all stations: columns code, day (date), tmax_f, precip_in."""
    a = pd.read_parquet(WEATHER / "stations_daily.parquet")
    a = a.assign(code=a.station.replace({"PBI": "DJT"}), day=pd.to_datetime(a.date_local))[["code", "day", "tmax_f", "precip_in"]]
    frames = [a]
    for f in sorted(glob.glob(str(E3 / "iem" / "*.csv"))):
        d = pd.read_csv(f, na_values=["None", "M", ""])
        frames.append(pd.DataFrame({"code": d.station.astype(str), "day": pd.to_datetime(d.day),
                                    "tmax_f": d.max_temp_f, "precip_in": d.precip_in}))
    out = pd.concat(frames, ignore_index=True).drop_duplicates(["code", "day"], keep="first")
    # trace (0.0001) is a dry day for 0.01 in rounding
    return out


def cli_daily() -> pd.DataFrame:
    """NWS CLI (IEM json/cli.py): code, day, tmax_f, precip_in (trace -> 0.0001)."""
    a = pd.read_parquet(WEATHER / "official_daily.parquet")
    a = a.assign(code=a.station, day=pd.to_datetime(a.date_local), tmax_f=a.high_f)[["code", "day", "tmax_f", "precip_in"]]
    frames = [a]
    for f in sorted(glob.glob(str(E3 / "cli" / "*.csv"))):
        if Path(f).stat().st_size == 0:
            continue
        d = pd.read_csv(f, dtype=str, index_col=False)
        num = lambda c: pd.to_numeric(d[c].replace({"M": None, "T": "0.0001"}), errors="coerce")  # noqa: E731
        frames.append(pd.DataFrame({"code": d.station.str[1:], "day": pd.to_datetime(d.valid),
                                    "tmax_f": num("high"), "precip_in": num("precip")}))
    return pd.concat(frames, ignore_index=True).drop_duplicates(["code", "day"], keep="first")


def ghcn_daily() -> pd.DataFrame:
    """GHCN-D for registry stations with a USW id: code, day, tmax_f, precip_in. QC-flagged values dropped."""
    frames = []
    for c, s in STATIONS.items():
        if not s.ghcn:
            continue
        p = CACHE / "ghcnd" / f"{s.ghcn}.parquet"
        if not p.exists():
            continue
        d = pd.read_parquet(p)
        tm = d.tmax_f_tenths.astype("float64") / 10.0
        pr = d.prcp_hundredths_in.astype("float64") / 100.0
        tm[d.tmax_q.fillna("").str.strip() != ""] = np.nan
        pr[d.prcp_q.fillna("").str.strip() != ""] = np.nan
        pr[(d.prcp_m.fillna("") == "T") & (pr == 0)] = 0.0001
        frames.append(pd.DataFrame({"code": c, "day": pd.to_datetime(d.date), "tmax_f": tm, "precip_in": pr}))
    return pd.concat(frames, ignore_index=True)


def nclimgrid_points() -> pd.DataFrame:
    """Cell containing each registry station, nClimGrid, on the CLI day: code, cell_id, day, tmax_f, prcp_in, status."""
    d = pd.concat([pd.read_parquet(f) for f in sorted(glob.glob(str(E3 / "nclimgrid_points" / "*.parquet")))], ignore_index=True)
    d["day"] = align.cli_day_from_label(d.label_day)
    d["tmax_f"] = np.round(d.tmax_c * 9 / 5 + 32, 1)
    d["prcp_in"] = np.round(d.prcp_mm / 25.4, 2)
    return d[["code", "cell_id", "lat", "lon", "day", "tmax_f", "prcp_in", "status"]]


def grid_disc(source: str) -> pd.DataFrame:
    """Phase 1 40 km discs around each S: station(S), cell_id, lat, lon, dist_km, day (CLI), tmax_f, prcp_in, release."""
    cols = ["station", "cell_id", "lat", "lon", "dist_km", "label_day", "tmax_f_tenths", "prcp_hundredths_in",
            "status", "prism_release_tmax", "prism_release_ppt"]
    d = pd.read_parquet(DISC / f"source={source}", columns=cols)
    d["station"] = d.station.astype(str)
    d["day"] = align.cli_day_from_label(d.label_day)
    d["tmax_f"] = d.tmax_f_tenths.astype("float64") / 10.0
    d["prcp_in"] = d.prcp_hundredths_in.astype("float64") / 100.0
    return d.drop(columns=["label_day", "tmax_f_tenths", "prcp_hundredths_in"])


def prism_extra() -> pd.DataFrame | None:
    """PRISM cells outside the Phase 1 discs (Phase 3 re-pull, scripts/pull_grids.py prism --points ...), same
    units and day alignment as grid_disc. None when no re-pull has been assembled."""
    f = CACHE / "grid_extra" / "prism_extra_cells.parquet"
    if not f.exists():
        return None
    d = pd.read_parquet(f)
    d["day"] = align.cli_day_from_label(d.label_day)
    d["tmax_f"] = d.tmax_f_tenths.astype("float64") / 10.0
    d["prcp_in"] = d.prcp_hundredths_in.astype("float64") / 100.0
    return d.drop(columns=["label_day", "tmax_f_tenths", "prcp_hundredths_in"])


def county_daily() -> pd.DataFrame:
    """NCEI county averages on the CLI day: county, day, tmax_f, prcp_in, status."""
    d = pd.read_parquet(E3 / "county_daily.parquet")
    w = d.pivot_table(index=["county", "label_day"], columns="var", values="value").reset_index()
    st = d.groupby(["county", "label_day"]).status.first().reset_index()
    w = w.merge(st, on=["county", "label_day"])
    w["day"] = align.cli_day_from_label(w.label_day)
    w["tmax_f"] = np.round(w.tmax * 9 / 5 + 32, 1)
    w["prcp_in"] = np.round(w.prcp / 25.4, 2)
    return w[["county", "day", "tmax_f", "prcp_in", "status"]]


def prism_stn_codes() -> dict[str, set[str]]:
    """Station ids in the kept PRISM .stn.csv files (only 2026-07-15 survives Phase 1): var -> set of ids."""
    out = {}
    for var in ("tmax", "ppt"):
        f = CACHE / "prism_stn" / f"prism_{var}_20260715.stn.csv"
        if not f.exists():
            continue
        d = pd.read_csv(f, skiprows=1, dtype=str)
        out[var] = d
    return out


# ------------------------------------------------------------------------------------------ data-quality check
DQ_WINDOW = ("2024-01-01", "2026-08-31")
DQ_THRESHOLD = 0.02


def _r0(x):
    return np.floor(np.asarray(x, float) + 0.5)


def _r2(x):
    return np.floor(np.asarray(x, float) * 100 + 0.5) / 100


def _mismatch(a: pd.Series, b: pd.Series, var: str) -> tuple[float, int, float]:
    j = pd.concat([a.rename("a"), b.rename("b")], axis=1).dropna()
    if j.empty:
        return float("nan"), 0, float("nan")
    if var == "tmax":
        diff = _r0(j.a) - _r0(j.b)
        return float((diff != 0).mean()), int(len(j)), float(diff.mean())
    diff = _r2(j.a) - _r2(j.b)
    return float((np.abs(diff) >= 0.005).mean()), int(len(j)), float(diff.mean())


def data_quality(codes: list[str] | None = None) -> tuple[pd.DataFrame, dict]:
    """PREREG "Station values": IEM daily summary unless it differs from the CLI on > 2 % of days (per
    variable) at a CLI station; 03-PLAN: a non-CLI station failing the same check against GHCN-D uses GHCN-D.
    Returns (table, {(code, var): chosen source}). Produces data-quality numbers only, no HE."""
    codes = codes or needed_codes()
    lo, hi = map(pd.Timestamp, DQ_WINDOW)
    iem, cli, gh = iem_daily(), cli_daily(), ghcn_daily()
    series = {}
    for name, df in (("iem", iem), ("cli", cli), ("ghcn", gh)):
        df = df[(df.day >= lo) & (df.day <= hi)]
        for c, g in df.groupby("code"):
            series[(name, c)] = g.set_index("day")[["tmax_f", "precip_in"]]
    rows, choice = [], {}
    for c in codes:
        s = STATIONS[c]
        ref = "cli" if s.cli else ("ghcn" if s.ghcn else None)
        I = series.get(("iem", c))
        R = series.get((ref, c)) if ref else None
        for var, col in (("tmax", "tmax_f"), ("precip", "precip_in")):
            if R is not None and I is not None:
                share, n, mdiff = _mismatch(I[col], R[col], var)
                # mismatch by regime (CONVENTIONS section 8: IEM changed around 2025-10)
                pre, _, mpre = _mismatch(I[col][I.index < "2025-10-01"], R[col][R.index < "2025-10-01"], var)
                post, _, _ = _mismatch(I[col][I.index >= "2025-10-01"], R[col][R.index >= "2025-10-01"], var)
                src = ref if (np.isfinite(share) and share > DQ_THRESHOLD) else "iem"
            else:
                share = n = mdiff = pre = post = mpre = float("nan")
                src = "iem" if I is not None else (ref or "none")
            if src == "iem" and I is None and R is not None:
                src = ref
            chosen = series.get((src, c))
            cov = {}
            for w, (a, b_) in (("train", ("2024-01-01", "2024-12-31")), ("test", ("2025-01-01", "2026-08-31"))):
                days = pd.date_range(a, b_)
                cov[w] = float(chosen[col].reindex(days).notna().mean()) if chosen is not None else 0.0
            rows.append(dict(code=c, var=var, cli=s.cli, ghcn=s.ghcn or "", ref=ref or "none",
                             n_compared=n, mismatch_share=share, mismatch_pre_2025_10=pre, mismatch_post_2025_10=post,
                             mean_iem_minus_ref=mdiff, mean_iem_minus_ref_pre=mpre, source=src,
                             cov_train=cov["train"], cov_test=cov["test"]))
            choice[(c, var)] = src
    return pd.DataFrame(rows), choice


# ------------------------------------------------------------------------------------------ bundle
def _pivot(df: pd.DataFrame, col: str, days: pd.DatetimeIndex) -> pd.DataFrame:
    return df.pivot_table(index="day", columns="code", values=col, aggfunc="first").reindex(days)


def build_data(days: pd.DatetimeIndex, choice: dict, include_ladder: bool = True):
    """Assemble wi.eval03.designs.Data from the caches. nClimGrid prelim values are dropped (PREREG:
    scaled files only)."""
    from wi.eval03.designs import Data

    codes = needed_codes()
    src = {"iem": iem_daily(), "cli": cli_daily(), "ghcn": ghcn_daily()}
    T = pd.DataFrame(index=days, columns=codes, dtype=float)
    P = pd.DataFrame(index=days, columns=codes, dtype=float)
    for c in codes:
        for var, col, tgt in (("tmax", "tmax_f", T), ("precip", "precip_in", P)):
            s = choice.get((c, var), "iem")
            if s == "none":
                continue
            d = src[s]
            g = d[d.code == c].set_index("day")[col]
            tgt[c] = g[~g.index.duplicated()].reindex(days).to_numpy()
    # nClimGrid cell containing each station
    pts = nclimgrid_points()
    pts.loc[pts.status != "scaled", ["tmax_f", "prcp_in"]] = np.nan
    NT, NP = _pivot(pts, "tmax_f", days).reindex(columns=codes), _pivot(pts, "prcp_in", days).reindex(columns=codes)
    ncell = pts.drop_duplicates("code").set_index("code")["cell_id"].to_dict()
    # PRISM: cell containing each station, searched in every Phase 1 disc
    disc = {}
    PT = pd.DataFrame(index=days, columns=codes, dtype=float)
    PP = pd.DataFrame(index=days, columns=codes, dtype=float)
    pcell, rel = {}, None
    for source in ("nclimgrid", "prism"):
        g = grid_disc(source)
        if source == "nclimgrid":
            g.loc[g.status != "scaled", ["tmax_f", "prcp_in"]] = np.nan
        else:
            r_ = g.groupby("day").prism_release_tmax.max()
            rel = r_.astype("float64").reindex(days)
        for S, gs in g.groupby("station", observed=True):
            cells = gs.drop_duplicates("cell_id").sort_values("cell_id")
            tp = gs.pivot_table(index="day", columns="cell_id", values="tmax_f", aggfunc="first").reindex(days)[cells.cell_id]
            pp = gs.pivot_table(index="day", columns="cell_id", values="prcp_in", aggfunc="first").reindex(days)[cells.cell_id]
            disc[(source, S)] = {"T": tp, "P": pp, "lat": cells.lat.to_numpy(), "dist": cells.dist_km.to_numpy(float)}
            if source == "prism":
                for c in codes:
                    if c in pcell:
                        continue
                    st = STATIONS[c]
                    hit = cells[(np.abs(cells.lat - st.lat) <= 1 / 48 + 1e-6) & (np.abs(cells.lon - st.lon) <= 1 / 48 + 1e-6)]
                    if len(hit):
                        cid = hit.cell_id.iloc[0]
                        pcell[c] = cid
                        PT[c] = tp[cid].to_numpy()
                        PP[c] = pp[cid].to_numpy()
    # PRISM cells outside the Phase 1 discs (re-pull): only for stations no disc contains
    ex = prism_extra()
    if ex is not None and len(ex):
        cells = ex.drop_duplicates("cell_id")
        tp = ex.pivot_table(index="day", columns="cell_id", values="tmax_f", aggfunc="first").reindex(days)
        pp = ex.pivot_table(index="day", columns="cell_id", values="prcp_in", aggfunc="first").reindex(days)
        for c in codes:
            if c in pcell:
                continue
            st = STATIONS[c]
            hit = cells[(np.abs(cells.lat - st.lat) <= 1 / 48 + 1e-6) & (np.abs(cells.lon - st.lon) <= 1 / 48 + 1e-6)]
            if len(hit):
                cid = hit.cell_id.iloc[0]
                pcell[c] = cid
                PT[c] = tp[cid].to_numpy()
                PP[c] = pp[cid].to_numpy()
    # county averages
    cty = county_daily()
    cty.loc[cty.status != "scaled", ["tmax_f", "prcp_in"]] = np.nan
    CT = cty.pivot_table(index="day", columns="county", values="tmax_f").reindex(days)
    CP = cty.pivot_table(index="day", columns="county", values="prcp_in").reindex(days)
    ladder = kalshi_ladder() if include_ladder else None
    data = Data(T=T, P=P, NT=NT, NP=NP, PT=PT, PP=PP, disc=disc, CT=CT, CP=CP, prism_rel=rel, ladder=ladder)
    return data, {"nclimgrid_cell": ncell, "prism_cell": pcell}


def kalshi_ladder() -> dict:
    """Phase 2 settled rule-A city-days: market -> DataFrame(index=CLI day, K, X = binned ladder payout)."""
    f = ROOT / "reports" / "eval-01" / "citydays.csv.gz"
    if not f.exists():
        return {}
    d = pd.read_csv(f, usecols=["city", "date", "rule", "K", "X"])
    d = d[d.rule == "A"].dropna(subset=["K", "X"])
    m = {"NY": "NYC", "CHI": "MDW", "MIA": "MIA", "EWR": "EWR", "TTN": "TTN"}
    out = {}
    for city, g in d.groupby("city"):
        if city in m:
            g = g.assign(day=pd.to_datetime(g.date)).drop_duplicates("day").set_index("day")[["K", "X"]]
            out[m[city]] = g
    return out
