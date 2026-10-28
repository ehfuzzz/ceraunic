"""The 30-day fixture run as an artifact: repeatable, fully settled, nothing stranded.

How this could silently lose money or corrupt data: a run that is not byte-repeatable (hashes in the
manifest would mean nothing), money left stranded in auction escrow, market collateral, policy escrow,
pool reserves or house deployment after every day settled, a day that never closes (its WI haircut
never happens), or a heavy import that breaks the API bundle.
"""
import json
import subprocess
import sys
from pathlib import Path

from wi.engine.scenario import run_fixture

INPUTS = Path(__file__).parent / "fixtures" / "nyc_30d_inputs.json"


def test_fixture_run_repeats_and_leaves_nothing_stranded():
    inputs = json.loads(INPUTS.read_bytes())
    a = run_fixture(inputs)["ledger"]
    b = run_fixture(inputs)["ledger"]
    assert a.hash() == b.hash() and a.lines == b.lines
    st = a.state
    assert sum(st["bal"].values()) + st["pool"]["cash"] == st["funded"]  # everything is back in wallets / pool
    assert st["pm"]["escrow"] == 0 and not any(st["pm"]["margin"].values())
    assert all(m["escrow"] == 0 and m["collateral"] == 0 for m in st["markets"].values())
    assert st["pool"]["reserved"] == 0 and st["pool"]["deployed"] == 0
    assert all(v == 0 for v in st["house"]["ledger"].values())
    assert all(p["status"] in ("Settled", "Voided") for p in st["policies"].values())
    assert len([d for d, v in st["pool"]["closed"].items() if v]) == len(inputs["days"])
    assert all(h["settled"] is not None for h in st["hedges"].values())
    # every invariant family was exercised during the run
    assert {"I1", "I2", "I3", "I5", "I6", "I7", "I8", "I9", "I10", "I11", "I12", "I15"} <= set(a.checks)


def test_engine_imports_stay_slim():
    code = ("import sys, wi.engine.reducer, wi.engine.scenario, wi.engine.pricing, wi.engine.house_mm;"
            "print([m for m in ('pandas','xarray','netCDF4','pyarrow','matplotlib') if m in sys.modules])")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout.strip()
    assert out == "[]"


def test_duplicated_house_ticks_change_nothing(monkeypatch):
    """Every house step run twice (a retried scheduler tick) must give the same ledger: no second residual
    leg, schedule, funding, hedge or return (each would deploy pool capital twice)."""
    from wi.engine import house_mm

    inputs = json.loads(INPUTS.read_bytes())
    once = run_fixture(inputs)["ledger"].hash()
    for name in ("book", "bind", "hedge_day", "settle_hedge", "ret"):
        f = getattr(house_mm, name)

        def twice(*a, _f=f, **k):
            r = _f(*a, **k)
            _f(*a, **k)
            return r

        monkeypatch.setattr(house_mm, name, twice)
    assert run_fixture(inputs)["ledger"].hash() == once
