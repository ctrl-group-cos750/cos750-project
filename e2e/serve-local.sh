#!/usr/bin/env bash
# Serves the app for the end-to-end tests without Docker: the API on SQLite (migrated, seeded,
# demo accounts) and the production build of the app behind `vite preview`, which forwards /api
# and /media to it. Plain HTTP, so only Chromium keeps the Secure session cookie: use this for a
# quick run in Chromium; CI and docker-compose.e2e.yml cover Firefox and WebKit over HTTPS.
#
#   e2e/serve-local.sh [api-port] [web-port]        # then, in another terminal, the line it prints
#
# Needs api/.venv (or E2E_PYTHON) and web/node_modules.
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
api_port="${1:-8100}"
web_port="${2:-4173}"
python="${E2E_PYTHON:-$root/api/.venv/bin/python}"
run="$(mktemp -d "${TMPDIR:-/tmp}/ctrl-e2e-XXXX")"
export DATABASE_URL="sqlite:///$run/e2e.db" MEDIA_DIR="$run/media" SERVE_MEDIA=1
export DEMO_PASSWORD="${DEMO_PASSWORD:-Demo-pass-2026!}"
mkdir -p "$MEDIA_DIR"

cd "$root/api"
"$python" -m alembic upgrade head >/dev/null
"$python" -m app.seed >/dev/null
# uvicorn believes X-Forwarded-For from 127.0.0.1 only: vite preview, here, as it believes only
# our own proxies when deployed. Each test sends its own address (tests/fixtures.ts).
"$python" -m uvicorn app.main:app --host 127.0.0.1 --port "$api_port" \
  --proxy-headers --forwarded-allow-ips 127.0.0.1 --log-level warning &
api=$!
trap 'kill $api 2>/dev/null' EXIT

cd "$root/web"
npx vite build --logLevel warn
cat >"$run/preview.config.mjs" <<CONFIG
export default {
  root: '$root/web',
  preview: { proxy: { '/api': 'http://127.0.0.1:$api_port', '/media': 'http://127.0.0.1:$api_port' } },
}
CONFIG
echo
echo "Run the tests with:"
echo "  BASE_URL=http://localhost:$web_port DEMO_PASSWORD='$DEMO_PASSWORD' \\"
echo "  E2E_STAFF_GRANT='cd api && DATABASE_URL=$DATABASE_URL $python -m app.staff grant' \\"
echo "  npx playwright test --project=chromium"
echo
npx vite preview --config "$run/preview.config.mjs" --port "$web_port" --strictPort
