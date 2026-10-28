#!/usr/bin/env bash
# Anvil parity run for the engine API (Phase 9 Task 2):
#   fresh anvil (port 8548, chain 31338, clock before the world's genesis)
#   -> Phase 8 `make deploy-anvil configure-anvil` with the engine's parameters (no seed, no stake, no demo markets:
#      the engine world's genesis does those through the API ledger, on chain)
#   -> tests/api/scenario_nyc_3d.json through EvmLedger(anvil) in-process
#   -> money projection must equal tests/api/golden/scenario_nyc_3d.json (recorded from sim).
# Stops anvil by PID and removes its temp files on exit. Chain 31338 keeps the committed deployments/31337.json.
#
#   bash scripts/anvil-scenario.sh            # parity test (pytest -k anvil)
#   KEEP=1 bash scripts/anvil-scenario.sh     # keep $WORK (anvil + forge logs, address book) for inspection
set -euo pipefail
export PATH="$HOME/.foundry/bin:$PATH"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${ANVIL_PORT:-8548}"
CHAIN=31338
RPC="http://127.0.0.1:$PORT"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/wi-anvil.XXXXXX")"
if lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then echo "port $PORT is busy"; exit 1; fi

read -r TS DEPLOY_ENV CONF_ENV < <(cd "$ROOT" && uv run --quiet python - <<'EOF'
from wi.api import catalog as c
p, r = c.params(), c.world_file()["roles"]
deploy = (f"WITHDRAW_DELAY_S={p['withdrawDelay']} HOUSE_RETURN_WINDOW_S={p['houseReturnWindow']} "
          f"UNSTAKE_COOLDOWN_S={p['unstakeCooldown']} MAX_REPORT_AGE_S={p['maxReportAge']}")
conf = (f"HOUSE={r['house']} QUOTER={r['quoter']} REPORTER={r['reporters'][0]} TREASURY={c.KEEPER} "
        f"CAP_BPS={p['capBps']} JMIN_BPS={p['jMinBps']} SENIOR_PREMIUM_BPS={p['seniorPremiumBps']} "
        f"MIN_JUNIOR_FOR_SENIOR={p['minJuniorForSenior']} JUNIOR_SEED=0 SENIOR_SEED=0 HOUSE_USDC=0 WI_STAKE=0 DEMO_DAYS=0")
print(c.GENESIS_TS - 6 * 3600, deploy.replace(" ", ","), conf.replace(" ", ","))
EOF
)
DEPLOY_ENV="${DEPLOY_ENV//,/ }"
CONF_ENV="${CONF_ENV//,/ }"

anvil --port "$PORT" --chain-id "$CHAIN" --timestamp "$TS" --silent > "$WORK/anvil.log" 2>&1 &
APID=$!
cleanup() {
  kill "$APID" 2>/dev/null || true
  rm -f "$ROOT/contracts/deployments/$CHAIN.json"
  if [ -z "${KEEP:-}" ]; then rm -rf "$WORK"; else echo "kept $WORK"; fi
}
trap cleanup EXIT
for _ in $(seq 100); do cast chain-id --rpc-url "$RPC" >/dev/null 2>&1 && break; sleep 0.1; done
echo "anvil pid $APID on $RPC (chain $CHAIN, clock $(date -u -r "$TS" +%FT%TZ))"

(cd "$ROOT/contracts" && make deploy-anvil configure-anvil ANVIL_PORT="$PORT" ANVIL_DEPLOY_ENV="$DEPLOY_ENV" \
   ANVIL_ENV="$CONF_ENV" > "$WORK/forge.log" 2>&1) || { tail -40 "$WORK/forge.log"; exit 1; }
cp "$ROOT/contracts/deployments/$CHAIN.json" "$WORK/deployment.json"
echo "deployed + configured: $(grep -c '"0x' "$WORK/deployment.json") addresses; $(grep -Eo "gas limit is now [0-9]+ \(next blocks: [0-9]+\)" "$WORK/forge.log" || true)"

cd "$ROOT"
WI_ANVIL_RPC="$RPC" WI_DEPLOYMENT="$WORK/deployment.json" \
  uv run pytest tests/api -q -p no:cacheprovider -k "test_anvil_" -rs "$@"
