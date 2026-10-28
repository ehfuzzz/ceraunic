#!/usr/bin/env bash
# Phase 3 deviation 1: pull PRISM for the 9 business points that have no cell, rerun eval03, rebuild report + decks,
# print what changed and where hand-written pair counts still need fixing. Does NOT commit.
#
#   bash scripts/phase3_repull.sh             full run (refuses before 2026-10-01T15:40:00Z)
#   bash scripts/phase3_repull.sh --dry-run   gate status + the files it would fetch; fetches and writes nothing
#
# Idempotent: the first run snapshots results.json to var/phase3-repull/results.before.json and later runs keep that
# baseline; cached extra days are never fetched again; a partial pull (exit 5) just means "run me again".
set -euo pipefail
cd "$(dirname "$0")/.."

NOT_BEFORE="20261001T154000Z"     # 2026-10-01T15:40:00Z, 24 h 5 min after the last Phase 1 PRISM fetch (2026-09-30T15:36Z)
POINTS="reports/eval-03/repull_points.json"
WORK="var/phase3-repull"
BEFORE="$WORK/results.before.json"
RESULTS="reports/eval-03/results.json"
DRY=0
[ "${1:-}" = "--dry-run" ] && DRY=1
[ "$#" -gt 1 ] && { echo "usage: bash scripts/phase3_repull.sh [--dry-run]" >&2; exit 2; }
[ "$#" -eq 1 ] && [ "$DRY" -eq 0 ] && { echo "usage: bash scripts/phase3_repull.sh [--dry-run]" >&2; exit 2; }

now="$(date -u +%Y%m%dT%H%M%SZ)"
if [[ "$now" < "$NOT_BEFORE" ]]; then
  echo "too early: now is $now, the PRISM 24 h per-file rule lets the re-pull start at $NOT_BEFORE (2026-10-01T15:40:00Z)." >&2
  if [ "$DRY" -eq 0 ]; then
    echo "nothing was fetched or changed. Use --dry-run to see the plan." >&2
    exit 4
  fi
  echo "(--dry-run: continuing without fetching)" >&2
fi

[ -f "$POINTS" ] || { echo "missing $POINTS (uv run python scripts/pull_grids.py missing-points)" >&2; exit 2; }

if [ "$DRY" -eq 1 ]; then
  uv run python scripts/pull_grids.py prism --points "$POINTS" --dry-run --brief
  echo "dry run: nothing fetched, nothing written"
  exit 0
fi

mkdir -p "$WORK"
if [ ! -f "$BEFORE" ]; then
  cp "$RESULTS" "$BEFORE"
  echo "baseline saved: $BEFORE"
else
  echo "baseline kept: $BEFORE (first-run snapshot)"
fi

echo "== (b) pull PRISM for the missing points ($(date -u +%FT%TZ))"
set +e
uv run python scripts/pull_grids.py prism --points "$POINTS" 2>&1 | tee -a "$WORK/pull.log"
rc=${PIPESTATUS[0]}
set -e
if [ "$rc" -ne 0 ]; then
  echo "pull_grids exited $rc (5 = some days still missing or blocked; 3 = disk floor). Stopping before eval03." >&2
  echo "Re-run this script: cached days are skipped, and the baseline is kept." >&2
  exit "$rc"
fi

echo "== (c) eval03"
uv run python scripts/eval03.py --all
echo "== (d) make report"
make report
echo "== (e) build_decks"
python3 scripts/build_decks.py

echo "== (f) numbers that changed, old -> new (baseline $BEFORE)"
python3 scripts/phase3_repull_diff.py diff "$BEFORE" "$RESULTS" --tsv "$WORK/changes.tsv"

echo
echo "== (f) hand-written places to fix (file:line). Pairs now: " \
  "$(python3 -c "import json;d=json.load(open('$RESULTS'))['bakeoff'];print('rain G1-P',d['rain']['G1-P']['n_pairs'],'of',d['rain']['D0']['n_pairs'],'; temperature G1-P',d['temperature']['G1-P']['n_pairs'],'of',d['temperature']['D0']['n_pairs'])")"
python3 scripts/phase3_repull_diff.py handwritten "$BEFORE" "$RESULTS"
echo
echo "Literal strings to search for (old counts): '19 of 26', '27 of 37', '19/26', '27 pairs', '19 pairs'"
grep -nE '19 of 26|27 of 37|19/26|27/37|27 pairs|19 pairs|same 19' \
  reports/EVALUATION.md reports/pitch/DECK-crypto.md reports/pitch/DECK-fintech.md reports/pitch/14-TOKEN-POOL-MEMO.md \
  reports/pitch/DEMO-WALKTHROUGH.md reports/eval-03/RESULTS.md reports/eval-03/residual-spec.md \
  scripts/build_decks.py scripts/render_decks.py scripts/build_report.py || echo "(none left)"
echo
echo "Done. Nothing was committed. Review 'git diff --stat', fix the lines above, then commit by hand."
