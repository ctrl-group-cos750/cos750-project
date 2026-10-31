# Ctrl Academy

COS750 group project (Control Group): a pre-lecture tutor app for COS212 that teaches graphs and
breadth-first search. Live at <https://ctrlacademy.co.za>, staging at <https://staging.ctrlacademy.co.za>.

| Folder | What |
|---|---|
| `web/` | React + Vite + TypeScript frontend, served by nginx in production |
| `api/` | FastAPI backend (Python 3.12), Postgres via SQLAlchemy |
| `docs/` | Spec, references, deploy notes |
| `assets/` | Logo pack |

## Run it

All of it in Docker, the way Coolify runs it:

```
cp .env.example .env
docker compose -f docker-compose.yml -f docker-compose.local.yml up --build
# http://localhost:8080
```

Or with hot reload, Postgres in Docker and the rest on your machine:

```
docker compose -f docker-compose.yml -f docker-compose.local.yml up -d db

cd api && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload            # http://localhost:8000/api/docs

cd web && npm install && npm run dev               # http://localhost:5173, proxies /api to :8000
```

## Checks

CI runs these on every PR and on every push to `staging` and `master`. Run them before you push:

```
scripts/check.sh          # everything below
scripts/check.sh --fix    # format and auto-fix first
```

| Where | Check | Command |
|---|---|---|
| `web/` | Format (Prettier) | `npm run format:check`, fix with `npm run format` |
| `web/` | Lint (oxlint, warnings fail) | `npm run lint` |
| `web/` | Tests (Vitest + Testing Library) | `npm test`, or `npm run test:watch` while you work |
| `web/` | Types and build | `npm run build` |
| `api/` | Format and lint (ruff) | `.venv/bin/ruff format --check .` and `.venv/bin/ruff check .` |
| `api/` | Types (mypy, strict) | `.venv/bin/mypy` |
| `api/` | Tests (pytest, warnings fail) | `.venv/bin/pytest` |
| repo | Docker images build | `POSTGRES_PASSWORD=x docker compose build` (in CI, not in `check.sh`) |

Tests sit next to the code: `web/src/**/*.test.tsx` and `api/tests/test_*.py`. API tests swap the
database for in-memory SQLite (`api/tests/conftest.py`), so they don't need Postgres running.
Coverage: `cd web && npm run coverage`.

Dependabot opens weekly update PRs into `staging`.

## Branches and deploys

`feature/*` → PR into `staging` → PR from `staging` into `master`. A PR into `master` from any
other branch fails the `branch-flow` check.

Coolify deploys on push: `staging` → staging.ctrlacademy.co.za, `master` → ctrlacademy.co.za.
Setup: [docs/deploy/coolify.md](docs/deploy/coolify.md).
