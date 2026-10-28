"""Plan 01-04 driver. Usage: uv run python scripts/pull_grids.py {nclimgrid|county|prism|assemble-prism|vintages|ghcnd|chain}

`chain` = nclimgrid months, county averages, vintages, then GHCN-Daily (one process, so at most
one raw grid file is on disk besides the separate `prism` process).
Stops with a message if free disk drops under 3 GiB (DiskFloor).

PRISM, Phase 3 re-pull (extra cells outside the 40 km discs; the Phase 1 cache is never touched):
  prism --points reports/eval-03/repull_points.json [--dry-run] [--brief] [--start D] [--end D]
  prism --radius-km N                               [--dry-run] [--brief]   (every cell within N km of a settlement
                                                                             station that is not already in a disc)
  prism --dry-run                                   plan of the default pull (files with no Phase 1 npz), fetches nothing
  assemble-prism-extra                              rebuild data/cache/grid_extra/prism_extra_cells.parquet from the cache
  missing-points [--write PATH]                     write reports/eval-03/repull_points.json from what is on disk
--dry-run never touches the network. A file fetched inside the last 24 h is never requested again (per file, from
data/manifests/grids.csv)."""
import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wi.data import grids  # noqa: E402


def main(cmd: str, args: argparse.Namespace | None = None) -> int:
    args = args or argparse.Namespace(points=None, radius_km=None, dry_run=False, brief=False, start=None, end=None, write=None)
    extra = args.points or args.radius_km is not None or args.dry_run or args.write
    if extra and cmd not in ("prism", "assemble-prism-extra", "missing-points"):
        raise SystemExit(f"--points/--radius-km/--dry-run/--write do not apply to `{cmd}`\n\n{__doc__}")
    if args.points and args.radius_km is not None:
        raise SystemExit("use --points or --radius-km, not both")
    try:
        if cmd == "nclimgrid":
            grids.pull_nclimgrid_months()
        elif cmd == "county":
            grids.pull_county_averages()
        elif cmd == "prism":
            start = dt.date.fromisoformat(args.start) if args.start else grids.WINDOW_START
            end = dt.date.fromisoformat(args.end) if args.end else grids.WINDOW_END
            if args.points or args.radius_km is not None:
                cells = (grids.cells_from_points_file(Path(args.points)) if args.points
                         else grids.cells_from_radius(args.radius_km))
                label = (f"extra cells from {args.points}" if args.points else f"extra cells within {args.radius_km:g} km")
                return grids.pull_prism_extra(cells, start, end, dry_run=args.dry_run, brief=args.brief,
                                              label=f"{label}: {len(cells)} cells, {start}..{end}")
            if args.dry_run:
                grids.print_prism_plan(grids.plan_prism_default(start, end), f"default discs, {start}..{end}", args.brief)
            elif args.start or args.end:
                grids.pull_prism(start, end)
            else:
                grids.pull_prism()
        elif cmd == "assemble-prism":
            grids.assemble_prism_all()
        elif cmd == "assemble-prism-extra":
            n = grids.assemble_prism_extra(grids.cells_from_points_file(Path(args.points)) if args.points else None)
            print("assembled rows", n, grids.PRISM_EXTRA_OUT)
        elif cmd == "missing-points":
            import json
            doc = grids.missing_points_doc()
            out = Path(args.write) if args.write else grids.REPULL_POINTS
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(doc, indent=1) + "\n")
            print("wrote", out, f"({doc['n_points']} points, {len(doc['cells'])} cells, covering radius {doc['covering_radius_km']:g} km)")
        elif cmd == "vintages":
            grids.pull_vintages()
        elif cmd == "ghcnd":
            from wi.data import ghcnd
            ghcnd.pull_all()
        elif cmd == "chain":
            grids.pull_nclimgrid_months()
            grids.pull_county_averages()
            grids.pull_vintages()
            from wi.data import ghcnd
            ghcnd.pull_all()
        else:
            raise SystemExit(__doc__)
    except grids.DiskFloor as e:
        print("OBJECTION: disk floor hit:", e, flush=True)
        raise SystemExit(3)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(usage=__doc__, add_help=False)
    ap.add_argument("cmd", nargs="?", default="")
    ap.add_argument("--points")
    ap.add_argument("--radius-km", type=float)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--brief", action="store_true")
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--write")
    a = ap.parse_args()
    raise SystemExit(main(a.cmd, a))
