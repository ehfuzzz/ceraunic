#!/usr/bin/env bash
# Deploy the engine API (sim mode) to the Vercel project `wi-engine` from a git-less slim bundle.
#
#   bash scripts/deploy-engine.sh            # assemble, check, deploy --prod, print the production alias
#   bash scripts/deploy-engine.sh --check    # assemble + import/size checks only (no deploy)
#
# Bundle = wi.engine + wi.api + the pieces the engine imports (wi.auction.clear, wi.eval.{ladder,fees}) + the
# Phase 5 portal estimator (wi.elasticity.{portal,design,fit,shrink}) + data/demo as demo-data/. Checks: a clean
# venv from services/engine-api/pyproject.toml imports the app, builds a world and prices a quote; none of
# pandas/xarray/netCDF4/pyarrow/matplotlib/scipy/statsmodels is importable; bundle + venv < 500 MB.
# Env for the project comes from the local gitignored .env via `vercel env add` (values never printed).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${TMPDIR:-/tmp}/wi-engine-bundle"
PROJECT="wi-engine"
rm -rf "$OUT"
trap 'rm -rf "$OUT"' EXIT  # the bundle and its check venv never outlive the run (disk is tight on this Mac)
mkdir -p "$OUT/wi/engine" "$OUT/wi/api/ledger" "$OUT/wi/auction" "$OUT/wi/eval" "$OUT/wi/elasticity" "$OUT/demo-data"

cp "$ROOT/src/wi/__init__.py" "$OUT/wi/"
for f in "$ROOT"/src/wi/engine/*.py; do
  case "$(basename "$f")" in parity.py|scenario.py) ;; *) cp "$f" "$OUT/wi/engine/" ;; esac
done
cp "$ROOT"/src/wi/api/*.py "$OUT/wi/api/"
cp "$ROOT"/src/wi/api/ledger/*.py "$OUT/wi/api/ledger/"
cp "$ROOT"/src/wi/auction/{__init__,clear}.py "$OUT/wi/auction/"
cp "$ROOT"/src/wi/eval/{__init__,ladder,fees}.py "$OUT/wi/eval/"
cp "$ROOT"/src/wi/elasticity/{__init__,portal,design,fit,shrink}.py "$OUT/wi/elasticity/"
cp "$ROOT"/data/demo/* "$OUT/demo-data/"
shasum -a 256 "$ROOT/docs/SPEC.md" | cut -d' ' -f1 > "$OUT/wi/api/SPEC.sha256"
cp "$ROOT"/services/engine-api/{app.py,pyproject.toml,vercel.json,.python-version} "$OUT/"
if [ -d "$ROOT/contracts/deployments" ]; then  # EvmLedger reads these in chain modes; tiny
  mkdir -p "$OUT/contracts/deployments" "$OUT/contracts/abi"
  cp "$ROOT"/contracts/deployments/*.json "$OUT/contracts/deployments/" 2>/dev/null || true
  for n in PolicyManager BatchAuction PoolVault OracleAdapter MockUSDC Lens WIStaking WIToken SeniorShare; do
    j="$ROOT/contracts/out/$n.sol/$n.json"
    [ -f "$j" ] && python3 -c "import json,sys; print(json.dumps(json.load(open(sys.argv[1]))['abi']))" "$j" > "$OUT/contracts/abi/$n.json"
  done
fi
python3 - "$OUT" <<'EOF'
import sys, tomllib, pathlib
out = pathlib.Path(sys.argv[1])
deps = tomllib.loads((out / "pyproject.toml").read_text())["project"]["dependencies"]
(out / "requirements.txt").write_text("\n".join(deps) + "\n")
EOF

# ---------------------------------------------------------------- checks in a clean venv
(
  cd "$OUT"
  uv venv -q --python 3.14 .chk
  uv pip install -q --python .chk/bin/python -r requirements.txt
  CHAIN_MODE=sim .chk/bin/python - <<'EOF'
import importlib.util, sys, time
bad = [m for m in ("pandas", "xarray", "netCDF4", "pyarrow", "matplotlib", "scipy", "statsmodels")
       if importlib.util.find_spec(m)]
assert not bad, f"heavy modules importable in the bundle venv: {bad}"
t = time.time()
import app  # noqa: F401  (the Vercel entrypoint)
print(f"import app: {time.time() - t:.2f}s")
from wi.api.ledger.sim import SimLedger
from wi.api.store import MemoryStore
from wi.api.models import QuoteRequest, BusinessCreate
from wi.engine.units import date_to_day
led = SimLedger(MemoryStore(), {})
w = led.new_world()
biz = led.create_business(w.world_id, BusinessCreate(name="x", lat=40.7769, lon=-73.874, owner="0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65"))
q = led.quote(w.world_id, QuoteRequest(business_id=biz.business_id, peril="heat", strike_tenths_f=900, cap_tenths_f=60,
              units=6, start_day="2026-07-16", end_day="2026-07-16", path="house-hedge"), [date_to_day("2026-07-16")])
assert q.premium_e6 > 0
led.advance(w.world_id, 3)
print(f"bundle check ok: world + quote + 3-day advance in {time.time() - t:.2f}s")
EOF
  SIZE=$(du -sm . | cut -f1)
  echo "bundle + installed deps (what the function ships): ${SIZE} MB (limit 500)"
  [ "$SIZE" -lt 500 ] || { echo "bundle too large"; exit 1; }
  rm -rf .chk
)
echo "upload bundle (Vercel installs the deps itself): $(du -sh "$OUT" | cut -f1)"
[ "${1:-}" = "--check" ] && exit 0

# ---------------------------------------------------------------- deploy
cd "$OUT"
vercel project add "$PROJECT" >/dev/null 2>&1 || true
vercel link --yes --project "$PROJECT" >/dev/null
set -a; . "$ROOT/.env"; set +a
CHAIN_MODE=sim
have=$(vercel env ls production 2>/dev/null || true)
for name in CHAIN_MODE UPSTASH_REDIS_REST_URL UPSTASH_REDIS_REST_TOKEN ADMIN_TOKEN; do
  if ! grep -q "^ *$name " <<<"$have"; then
    printf '%s' "${!name}" | vercel env add "$name" production >/dev/null 2>&1
    echo "env $name: added"
  else
    echo "env $name: present"
  fi
done
vercel deploy --prod --yes > "$OUT/.deploy.log" 2>&1 || { tail -30 "$OUT/.deploy.log"; exit 1; }
# the public production alias is the project-name domain; team-scoped and per-deployment URLs are SSO-gated
ALIAS=$(grep -Eo "https://$PROJECT\.vercel\.app" "$OUT/.deploy.log" | head -1)
echo "production alias: ${ALIAS:-unknown (see vercel project ls)}"
[ -n "$ALIAS" ] && curl -s -m 60 "$ALIAS/api/v1/health" && echo
