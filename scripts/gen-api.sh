#!/usr/bin/env bash
# Regenerate the frontend's API types from the backend (NFR-M2).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

PY=python3
for p in "$ROOT/api/.venv/bin/python" "$ROOT/api/.venv/Scripts/python.exe"; do
  [ -x "$p" ] && PY="$p" && break
done

(cd "$ROOT/api" && "$PY" -m app.export_openapi)
(cd "$ROOT/web" && npm run gen:api)
