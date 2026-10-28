#!/usr/bin/env bash
# Local end-to-end run on a throwaway anvil. Starts anvil in the background, runs
# deploy (30M block) -> block gas limit 3,000,000 -> configure -> smoke -> 5-phase E2E -> gas table,
# and always stops that anvil by PID. Uses only anvil's public dev keys.
set -euo pipefail
PORT="${1:-8547}"
cd "$(dirname "$0")/.."
export PATH="$HOME/.foundry/bin:$PATH"

if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "port $PORT is busy; pass another: make anvil-e2e ANVIL_PORT=8548" >&2
  exit 1
fi
rm -rf broadcast/*/31337 deployments/e2e-31337.json
LOG="$(mktemp -t wi-anvil.XXXXXX)"
anvil --chain-id 31337 --port "$PORT" >"$LOG" 2>&1 &
PID=$!
trap 'kill "$PID" 2>/dev/null || true; wait "$PID" 2>/dev/null || true; echo "anvil (pid $PID) stopped"' EXIT
for _ in $(seq 1 50); do
  cast chain-id --rpc-url "http://127.0.0.1:$PORT" >/dev/null 2>&1 && break
  sleep 0.2
done
echo "anvil pid $PID on port $PORT (log $LOG)"
make --no-print-directory deploy-anvil configure-anvil smoke-anvil e2e-anvil gas-anvil ANVIL_PORT="$PORT"
echo "max block gasLimit seen after the drop: $(cast block latest -f gasLimit --rpc-url "http://127.0.0.1:$PORT")"
