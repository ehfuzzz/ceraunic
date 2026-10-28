"""Pull CME weather statistics + trades from Databento GLBX.MDP3 for the 26 US monthly roots.
Re-checks get_cost first and aborts if the total is over $1. Writes DBN (zstd) to data/raw/cme-weather/.
Run: uv run --no-project --with databento --with pandas python .planning/research/cme-first-look/db_pull.py"""
import json, sys
import databento as db
from common import RAW, CITIES, databento_key
START, END = "2022-10-01", "2026-10-24"
ROOTS = [c[1] for c in CITIES] + [c[2] for c in CITIES]
SYMS = [r + ".FUT" for r in ROOTS]
c = db.Historical(databento_key())
jobs = [("statistics", "stats"), ("trades", "trades")]
total = 0.0; est = {}
for schema, tag in jobs:
    kw = dict(dataset="GLBX.MDP3", symbols=SYMS, stype_in="parent", schema=schema, start=START, end=END)
    est[schema] = dict(cost=c.metadata.get_cost(**kw), records=c.metadata.get_record_count(**kw),
                       billable_bytes=c.metadata.get_billable_size(**kw))
    total += est[schema]["cost"]
print("estimate", json.dumps(est), "total $%.4f" % total)
if total > 1.0:
    sys.exit("ABORT: estimated cost over $1")
for schema, tag in jobs:
    p = RAW / f"glbx-weather-{tag}-{START}-{END}.dbn.zst"
    if p.exists(): print("exists", p.name); continue
    c.timeseries.get_range(dataset="GLBX.MDP3", symbols=SYMS, stype_in="parent", schema=schema,
                           start=START, end=END, path=str(p))
    print("wrote", p.name, p.stat().st_size, "bytes")
json.dump(est, open(RAW / "db_pull_estimate.json", "w"), indent=1)
