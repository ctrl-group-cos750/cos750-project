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

For video uploads without Docker, start the API with `MEDIA_DIR=./media SERVE_MEDIA=1` so it
stores uploads in `api/media/` and serves them at `/media/` (Vite proxies that to it too).

## Videos and checkpoints

Videos live on the `media` volume (in `docker-compose.yml`), not in git: the API writes uploads
there and nginx serves them at `/media/`. On Coolify the volume persists across deploys.

1. Register an account in the app, then make it staff:
   `docker compose exec api python -m app.staff grant you@example.com`
   (on Coolify, in the api container's terminal). Log out and in again if the page was open.
2. Open **Videos** in the header (`/staff/videos`) → **New video**.
3. Upload the MP4 (up to 95 MB, H.264) and its WebVTT captions, fill in the title and transcript.
4. Play the preview, pause where it should stop and press **Add checkpoint at the current time**.
   Write the question, mark the correct option, say why each wrong one is wrong, add up to four
   hints. Save.
5. **Open as a student** (`/videos/<id>`) to try it.

Editing a checkpoint keeps its attempts; removing one keeps its activity if students answered it.

## Checks

CI runs these on every PR, for the parts it touches (not again on the merge). Run them before you push:

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

Dependabot opens monthly update PRs into `staging`; security updates come at once.

## Database

Postgres, through SQLAlchemy 2 models and Alembic migrations. Each environment (local, staging,
production) has its own database. **Migrations run automatically when the API starts**, so a merged
migration reaches staging on its deploy. `/api/health` reports the schema revision it is on.

Add a table:

1. Write the model in `api/app/models/<thing>.py`, subclassing `Base` from `app.db`, and import it in
   `api/app/models/__init__.py`.
2. With the local database running (`docker compose -f docker-compose.yml -f docker-compose.local.yml up -d db`):
   ```
   cd api
   .venv/bin/alembic upgrade head
   .venv/bin/alembic revision --autogenerate -m "add <thing>"
   ```
   Read the generated file in `api/migrations/versions/` and fix anything autogenerate got wrong.
3. Commit the model and the migration together. CI fails if a model changes without a migration,
   or if two branches both added one (`alembic merge heads` fixes that).

Use the database in a route:

```python
from app.db import DbSession

@app.post("/api/things")
def create_thing(body: ThingIn, session: DbSession) -> ThingOut:
    thing = Thing(name=body.name)
    session.add(thing)
    session.commit()
    return ThingOut.model_validate(thing, from_attributes=True)
```

Tests never need Postgres: the `working_db` fixture in `api/tests/conftest.py` swaps in SQLite.

## Writing content

Modules, activities, hints and review paths are JSON fixtures in `api/app/seed/`. The authoring
guide, [`api/app/seed/README.md`](api/app/seed/README.md), explains every segment and activity
kind, with a template per activity kind in `api/app/seed/templates/`. Check content with
`cd api && .venv/bin/python -m app.seed --check`.

## Branches and deploys

`feature/*` → PR into `staging` → PR from `staging` into `master`. A PR into `master` from any
other branch fails the `branch-flow` check.

- **Rules** (`.github/rulesets/`, applied by `scripts/apply-branch-rules.sh`): `staging` and
  `master` change only through a PR with one approving review from someone other than the last
  person to push, and a green `checks` job (CI's one job); `master` also needs
  `source-is-staging`. No force-pushes, no deleting either branch. They need the organisation on
  GitHub Team (free for student organisations through GitHub Education).
- **Until then**, the `push-guard` workflow checks every push to `staging` and `master`: anything
  that isn't the merge of a PR, or is a force-push, fails and opens an issue for the Scrum Master;
  and `delete-guard` does the same if `master` is deleted, with the commit to restore it from.
  (GitHub never allows deleting the default branch, `staging`.)

Coolify deploys `staging` to staging.ctrlacademy.co.za on every push. Production (`master` →
ctrlacademy.co.za) is deployed deliberately after a release PR, not automatically on push.
Setup: [docs/deploy/coolify.md](docs/deploy/coolify.md).
