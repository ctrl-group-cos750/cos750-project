#!/usr/bin/env bash
# Runs every check CI runs, except the Docker build. Run it before you push.
#   scripts/check.sh          check only
#   scripts/check.sh --fix    format and auto-fix first, then check
set -euo pipefail
cd "$(dirname "$0")/.."

fix=false
[[ "${1:-}" == "--fix" ]] && fix=true

echo "== web"
(
  cd web
  [[ -d node_modules ]] || npm ci
  if $fix; then npm run format && npx oxlint --fix; fi
  npm run format:check
  npm run lint
  npm run test
  npm run build
)

echo "== api"
(
  cd api
  [[ -d .venv ]] || { python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt; }
  if $fix; then .venv/bin/ruff format . && .venv/bin/ruff check --fix .; fi
  .venv/bin/ruff format --check .
  .venv/bin/ruff check .
  .venv/bin/mypy
  .venv/bin/pytest
  # 90% gate on the code that decides a student's results (issue #67). Add each new result
  # module's --cov target and its test file here in the PR that adds it.
  .venv/bin/pytest -o addopts="" \
    --cov=app.services.bfs --cov=app.services.checking --cov=app.services.rewards \
    --cov-branch --cov-fail-under=90 --cov-report=term-missing \
    tests/test_bfs.py tests/test_checking.py tests/test_rewards.py tests/test_activity_kinds.py
)

echo "== all checks passed"
