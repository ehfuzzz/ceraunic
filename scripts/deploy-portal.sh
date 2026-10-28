#!/usr/bin/env bash
# Deploy the portal (apps/portal) to the Vercel project `wi-portal` from a git-less bundle, in sim mode, with
# /api/v1/* rewritten to the engine's production alias.
#
#   bash scripts/deploy-portal.sh            # assemble, check, deploy --prod, print the production alias, curl it
#   bash scripts/deploy-portal.sh --check    # assemble + frozen install + local production build checks only
#
# Bundle = apps/portal without node_modules/.next/test output + a standalone pnpm lockfile cut from the workspace
# lockfile (importer apps/portal -> .) + vercel.json pinning the nextjs framework preset (load-bearing: a null
# framework serves the build as static files and the route handlers 500).
# Checks, in the bundle: `pnpm install --frozen-lockfile` (the cut lockfile is exact), then `next build` with the
# production env, then the Square route's trace must list the fixture files (outputFileTracingIncludes).
# Env: ENGINE_ORIGIN (baked into the rewrite at build time) and CHAIN_MODE=sim, set with `vercel env add`; values are
# never printed. The portal gets no secrets: the admin token stays in the engine project and the owner's browser tab.
# The bundle, its node_modules and its .next are deleted on exit; nothing is written inside the repo.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${TMPDIR:-/tmp}/wi-portal-bundle"
PROJECT="wi-portal"
ENGINE_ORIGIN="${ENGINE_ORIGIN:-https://wi-engine.vercel.app}"
CHAIN_MODE="sim"
case "$ENGINE_ORIGIN" in
  https://*.vercel.app) ;;
  *) echo "ENGINE_ORIGIN must be a production alias (https://<project>.vercel.app)"; exit 1 ;;
esac
rm -rf "$OUT"
trap 'rm -rf "$OUT"' EXIT
mkdir -p "$OUT"

rsync -a \
  --exclude node_modules --exclude .next --exclude .vercel --exclude test-results --exclude playwright-report \
  --exclude '*.tsbuildinfo' --exclude next-env.d.ts --exclude AGENTS.md --exclude CLAUDE.md --exclude .DS_Store \
  "$ROOT/apps/portal/" "$OUT/"

python3 - "$ROOT/pnpm-lock.yaml" "$OUT/pnpm-lock.yaml" <<'EOF'
import re, sys
src, dst = sys.argv[1], sys.argv[2]
text = open(src).read()
head, rest = text.split("\nimporters:\n", 1)
imps, pkgs = rest.split("\npackages:\n", 1)
blocks = re.split(r"\n(?=  \S)", imps.strip("\n"))
keep = [b for b in blocks if b.startswith("  apps/portal:")]
assert len(keep) == 1, "apps/portal importer not found in the workspace lockfile"
others = [b.split(":", 1)[0].strip() for b in blocks if not b.startswith("  apps/portal:") and not b.startswith("  .:")]
assert not others, f"lockfile has other importers {others}; the cut would drop their deps"
open(dst, "w").write(head + "\nimporters:\n\n" + keep[0].replace("  apps/portal:", "  .:", 1) + "\n\npackages:\n" + pkgs)
EOF

cat > "$OUT/vercel.json" <<'EOF'
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "framework": "nextjs",
  "installCommand": "pnpm install --frozen-lockfile",
  "buildCommand": "pnpm run build"
}
EOF
printf 'node_modules\n.next\n.vercel/output\ntest-results\nplaywright-report\n' > "$OUT/.vercelignore"

# ---------------------------------------------------------------- checks
(
  cd "$OUT"
  pnpm install --frozen-lockfile --prefer-offline --ignore-scripts --reporter=silent
  t=$(date +%s)
  ENGINE_ORIGIN="$ENGINE_ORIGIN" CHAIN_MODE="$CHAIN_MODE" NEXT_TELEMETRY_DISABLED=1 pnpm exec next build > .build.log 2>&1 \
    || { tail -40 .build.log; exit 1; }
  echo "local production build: ok in $(( $(date +%s) - t ))s"
  grep -E "^(├|└|┌)" .build.log | sed 's/^/  /' || true
  NFT=".next/server/app/api/pos/square/route.js.nft.json"
  [ -f "$NFT" ] || { echo "missing $NFT"; exit 1; }
  n=$(python3 -c "import json,sys; print(sum(1 for f in json.load(open(sys.argv[1]))['files'] if 'fixtures/square/' in f))" "$NFT")
  echo "square route trace: $n fixture files"
  [ "$n" -ge 6 ] || { echo "fixtures/square missing from the route trace (outputFileTracingIncludes)"; exit 1; }
  grep -q "wi-engine.vercel.app\|$ENGINE_ORIGIN" .next/routes-manifest.json || { echo "rewrite to $ENGINE_ORIGIN not in routes-manifest"; exit 1; }
  echo "rewrite /api/v1/* -> $ENGINE_ORIGIN: in routes-manifest"
  rm -rf node_modules .next .build.log
)
echo "upload bundle: $(du -sh "$OUT" | cut -f1)"
[ "${1:-}" = "--check" ] && exit 0

# ---------------------------------------------------------------- deploy
cd "$OUT"
vercel project add "$PROJECT" >/dev/null 2>&1 || true
vercel link --yes --project "$PROJECT" >/dev/null
have=$(vercel env ls production 2>/dev/null || true)
for name in ENGINE_ORIGIN CHAIN_MODE; do  # config, not secrets; replaced on every run so a stale value can't linger
  if grep -q "^ *$name " <<<"$have"; then
    vercel env rm "$name" production --yes >/dev/null 2>&1 || true
  fi
  printf '%s' "${!name}" | vercel env add "$name" production >/dev/null 2>&1
  echo "env $name: set"
done
vercel deploy --prod --yes > "$OUT/.deploy.log" 2>&1 || { tail -40 "$OUT/.deploy.log"; exit 1; }
# the public production alias is the project-name domain; team-scoped and per-deployment URLs are SSO-gated
ALIAS=$(grep -Eo "https://$PROJECT\.vercel\.app" "$OUT/.deploy.log" | head -1)
echo "production alias: ${ALIAS:-unknown (see vercel project ls)}"
[ -n "$ALIAS" ] || exit 1
code=$(curl -s -o /dev/null -w '%{http_code}' -m 60 "$ALIAS/")
echo "GET $ALIAS/ -> $code"
echo "GET $ALIAS/api/v1/health -> $(curl -s -m 60 "$ALIAS/api/v1/health")"
echo "GET $ALIAS/api/pos/square -> $(curl -s -m 60 "$ALIAS/api/pos/square" | head -c 200)"
