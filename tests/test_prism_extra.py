"""Phase 3 PRISM re-pull (scripts/pull_grids.py prism --points ...): end-to-end on a synthetic CONUS file, no network.

Silent-corruption failure modes covered, each asserted on the written artifacts:
1. wrong cell: the extra value must be the one at the PRISM cell containing the point (lat/lon -> index), for both variables;
2. day shift: the assembled parquet keeps PRISM's label day, and the eval loader turns it into label - 1 (CLI day);
3. re-request inside PRISM's 24 h rule (per file) or of a day already in the extra cache: zero GET calls;
4. a partial pull reported as complete: exit code 5 while a day that Phase 1 has is missing from the extra cache.
"""
from __future__ import annotations

import datetime as dt
import io
import zipfile

import netCDF4 as nc
import numpy as np
import pandas as pd
import pytest

from wi.data import grids
from wi.eval03 import sources

LAT0, LON0 = 24.08333333333333, -125.0
STATIONS = {"NYC": (40.779, -73.96925), "EWR": (40.68272, -74.16932), "TTN": (40.27682, -74.81588),
            "MDW": (41.78597, -87.75242), "MIA": (25.78805, -80.31693)}


def _synthetic_zip(tmp_path, shift: float) -> bytes:
    """A PRISM-shaped zip: 621 x 1405 grid, Band1[i, j] = i + j / 10000 + shift, plus the info file."""
    f = tmp_path / "syn.nc"
    ds = nc.Dataset(f, "w")
    ds.createDimension("lat", 621)
    ds.createDimension("lon", 1405)
    ds.createVariable("lat", "f8", ("lat",))[:] = LAT0 + np.arange(621) / 24.0
    ds.createVariable("lon", "f8", ("lon",))[:] = LON0 + np.arange(1405) / 24.0
    band = ds.createVariable("Band1", "f4", ("lat", "lon"), fill_value=-9999.0)
    ii, jj = np.meshgrid(np.arange(621), np.arange(1405), indexing="ij")
    band[:, :] = (ii + jj / 10000.0 + shift).astype("float32")
    ds.close()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("PRISM_syn.nc", f.read_bytes())
        z.writestr("PRISM_syn.info.txt", "PRISM_DATASET_RELEASE_NUMBER: 8\nPRISM_DATASET_CREATE_DATE: 2026-01-01\n"
                                          "PRISM_DATASET_VERSION: M4\nPRISM_DATASET_TYPE: an91d\n")
    return buf.getvalue()


class _Resp:
    status_code = 200

    def __init__(self, body: bytes):
        self.body = body

    def iter_content(self, n):
        yield self.body


@pytest.fixture
def world(tmp_path, monkeypatch):
    cache, raw, man = tmp_path / "cache", tmp_path / "raw", tmp_path / "manifests"
    monkeypatch.setattr(grids, "CACHE", cache)
    monkeypatch.setattr(grids, "RAW", raw)
    monkeypatch.setattr(grids, "MANIFESTS", man)
    monkeypatch.setattr(grids, "PRISM_DAYS", cache / "prism_days")
    monkeypatch.setattr(grids, "PRISM_EXTRA_DAYS", cache / "prism_days_extra")
    monkeypatch.setattr(grids, "PRISM_EXTRA_OUT", cache / "grid_extra" / "prism_extra_cells.parquet")
    monkeypatch.setattr(grids, "PRISM_SLEEP", 0.0)
    monkeypatch.setattr(grids, "settlement_points", lambda: STATIONS)
    calls: list[str] = []
    zips = {"a": _synthetic_zip(tmp_path, 0.0)}

    def fake_get(url, **kw):
        calls.append(url)
        return _Resp(zips["a"])

    monkeypatch.setattr(grids, "get", fake_get)
    return dict(calls=calls, cache=cache, man=man)


def _cells():
    # two points with no disc cell: Mount Holly NJ-ish and a Long Island point, plus their PRISM cells
    out = []
    for lat, lon in ((41.06694, -73.7075), (40.72878, -73.41341)):
        c = grids.prism_cell_for(lat, lon)
        out.append({k: c[k] for k in ("cell_id", "i", "j", "lat", "lon")})
    return out


def test_extra_pull_end_to_end(world, tmp_path, monkeypatch):
    cells = _cells()
    assert not {c["cell_id"] for c in cells} & grids.disc_cell_ids()
    d1, d2, d3 = dt.date(2026, 7, 14), dt.date(2026, 7, 15), dt.date(2026, 7, 16)
    # Phase 1 has all three days for both variables (its npz files hold the disc cells only)
    discs = grids.prism_discs_from_local()
    for d in (d1, d2, d3):
        for var in grids.PRISM_VARS:
            p = world["cache"] / "prism_days" / var / f"{d:%Y%m%d}.npz"
            p.parent.mkdir(parents=True, exist_ok=True)
            shift = 5.0 if d == d2 else 0.0  # Phase 1 saw a different PRISM vintage on d2
            arrs = {s: (dc["ii"] + dc["jj"] / 10000.0 + shift).astype("float32") for s, dc in discs.items()}
            np.savez_compressed(p, release=7, created="", version="", **arrs)
    # the ppt file of d3 was downloaded 1 h ago: PRISM would refuse it again
    now = dt.datetime.now(dt.timezone.utc)
    grids.manifest_append("grids", dict(dataset="prism_4km_ppt_daily",
                                        url=grids.PRISM_URL.format(var="ppt", ymd="20260716"),
                                        fetched_utc=(now - dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                        http_status="200"))
    plan = {(r["var"], r["day"]): r["status"] for r in grids.plan_prism_extra(cells, d1, d3)}
    assert plan[("ppt", d3)] == "blocked_24h" and plan[("tmax", d3)] == "fetch"
    assert sum(1 for s in plan.values() if s == "fetch") == 5

    rc = grids.pull_prism_extra(cells, d1, d3)
    assert rc == 5  # ppt d3 still missing while Phase 1 has it: not complete
    assert len(world["calls"]) == 5 and not any("ppt/20260716" in u for u in world["calls"])
    # 1. the value at each requested cell is the synthetic value at that cell's own (i, j)
    z = np.load(world["cache"] / "prism_days_extra" / "tmax" / "20260714.npz")
    for c in cells:
        k = z["cell_ids"].tolist().index(c["cell_id"])
        assert z["vals"][k] == pytest.approx(c["i"] + c["j"] / 10000.0, abs=1e-4)
        assert z["lat"][k] == pytest.approx(LAT0 + c["i"] / 24.0)
    # vintage check recorded: d1 identical to Phase 1, d2 differs
    assert int(np.load(world["cache"] / "prism_days_extra" / "tmax" / "20260714.npz")["disc_cells_changed"]) == 0
    assert int(np.load(world["cache"] / "prism_days_extra" / "tmax" / "20260715.npz")["disc_cells_changed"]) > 0
    # 3. second run: cached days are not requested again, only the blocked file is still waiting
    world["calls"].clear()
    assert grids.pull_prism_extra(cells, d1, d3) == 5 and world["calls"] == []
    # once the 24 h have passed the last file is fetched and the pull is complete
    man = world["man"] / "grids.csv"
    man.write_text(man.read_text().replace(((now - dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")),
                                           (now - dt.timedelta(hours=26)).strftime("%Y-%m-%dT%H:%M:%SZ")))
    assert grids.pull_prism_extra(cells, d1, d3) == 0 and len(world["calls"]) == 1
    # 2. assembled parquet: label day kept, tmax in F tenths, ppt in hundredths of an inch, 2 cells x 3 days
    df = pd.read_parquet(world["cache"] / "grid_extra" / "prism_extra_cells.parquet")
    assert len(df) == 6 and set(df.label_day) == {d1, d2, d3}
    row = df[(df.cell_id == cells[0]["cell_id"]) & (df.label_day == d1)].iloc[0]
    v = cells[0]["i"] + cells[0]["j"] / 10000.0
    assert row.tmax_f_tenths == round((np.float32(v) * 9 / 5 + 32) * 10)
    assert row.prcp_hundredths_in == round(np.float32(v) / 25.4 * 100)
    # the eval loader moves label D to CLI day D - 1
    monkeypatch.setattr(sources, "CACHE", world["cache"])
    ex = sources.prism_extra()
    assert sorted(ex.day.dt.date.unique()) == [dt.date(2026, 7, 13), dt.date(2026, 7, 14), dt.date(2026, 7, 15)]


def test_extra_cache_must_cover_every_requested_cell(world):
    """A day cached for cell A only is not 'cached' for {A, B}: the plan must re-request it (never silently reuse)."""
    cells = _cells()
    d = dt.date(2026, 7, 14)
    grids.pull_prism_extra(cells[:1], d, d)
    plan = {(r["var"]): r["status"] for r in grids.plan_prism_extra(cells[:1], d, d)}
    assert set(plan.values()) == {"cached"}
    plan = {(r["var"]): r["status"] for r in grids.plan_prism_extra(cells, d, d)}
    assert set(plan.values()) == {"blocked_24h"}  # just fetched, so PRISM would refuse it for 24 h
