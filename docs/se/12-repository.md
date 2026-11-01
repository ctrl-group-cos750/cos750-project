# Repository structure

Repository: `MatthewEls/cos750-project`. Folders marked *(planned)* don't exist yet.

```
cos750-project/
├─ README.md                    run it, checks, database, branches and deploys
├─ docker-compose.yml           web + api + db, deployed by Coolify as it is
├─ docker-compose.local.yml     publishes ports for local use
├─ .env.example
├─ .github/
│  ├─ workflows/ci.yml          web, api and compose jobs
│  ├─ workflows/branch-flow.yml
│  ├─ dependabot.yml
│  └─ pull_request_template.md
├─ scripts/check.sh             every CI check locally; --fix formats first
├─ api/
│  ├─ Dockerfile                runs migrations, then Uvicorn
│  ├─ requirements.txt          runtime dependencies (pinned)
│  ├─ requirements-dev.txt      + pytest, ruff, mypy
│  ├─ pyproject.toml            ruff, mypy and pytest settings
│  ├─ alembic.ini
│  ├─ migrations/versions/      one file per schema change
│  ├─ app/
│  │  ├─ main.py                FastAPI app, router registration
│  │  ├─ db.py                  engine, Base, DbSession dependency
│  │  ├─ models/                SQLAlchemy models
│  │  ├─ schemas/               Pydantic request/response models (planned)
│  │  ├─ routers/               auth, content, questions, bfs, scoring, leaderboard, assessment (planned)
│  │  ├─ services/              AuthService, ContentService, ScoringService, AssessmentService (planned)
│  │  ├─ bfs/engine.py          BfsEngine: pure, tested in isolation (planned)
│  │  └─ seed/                  lessons, questions, graph scenarios, demo accounts (planned)
│  └─ tests/
├─ web/
│  ├─ Dockerfile                Vite build, then nginx
│  ├─ nginx.conf                SPA, /api proxy, /media, /healthz
│  ├─ staging-gate.sh, gate/    staging team-password page
│  ├─ package.json, vite.config.ts, .oxlintrc.json, .prettierrc.json, .nvmrc
│  └─ src/
│     ├─ main.tsx, App.tsx
│     ├─ api/                   typed API client (planned)
│     ├─ auth/                  (planned)
│     ├─ components/            shared components (planned)
│     ├─ features/              lessons, video, bfs, assessment, gamification (planned)
│     └─ test/setup.ts
├─ e2e/                         Playwright tests (planned)
├─ assets/                      Ctrl Group logo pack
└─ docs/
   ├─ se/                       this document, one Markdown file per section
   ├─ id/                       the ID document
   ├─ build/                    builds both into PDFs (npm run pdf)
   ├─ spec/, references/, course-material/
   └─ deploy/coolify.md
```
