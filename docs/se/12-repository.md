# Repository Structure

Single GitHub repository, monorepo-style with `backend/` and `frontend/`. **[PROVISIONAL]**

```
cos212-bfs-app/
├─ README.md
├─ .gitignore
├─ .github/
│  └─ workflows/
│     └─ ci.yml                 # lint + test (backend & frontend)
├─ docker-compose.yml           # reverse proxy + backend + PostgreSQL + static frontend
├─ backend/
│  ├─ pyproject.toml            # deps, ruff, pytest config
│  ├─ alembic.ini
│  ├─ app/
│  │  ├─ main.py                # FastAPI app factory, router registration
│  │  ├─ config.py              # env-based settings
│  │  ├─ db.py                  # engine/session
│  │  ├─ models/                # SQLAlchemy models
│  │  ├─ schemas/               # Pydantic request/response models
│  │  ├─ routers/               # auth, content, questions, bfs, scoring, leaderboard, assessment
│  │  ├─ services/              # AuthService, ContentService, ScoringService, AssessmentService
│  │  ├─ bfs/
│  │  │  └─ engine.py           # BfsEngine (pure, tested in isolation)
│  │  └─ seed/                  # fixtures: lessons, questions, graph scenarios
│  ├─ migrations/               # alembic versions
│  └─ tests/                    # pytest (engine, api, services)
├─ frontend/
│  ├─ package.json
│  ├─ vite.config.ts
│  ├─ tsconfig.json
│  ├─ index.html
│  ├─ src/
│  │  ├─ main.tsx
│  │  ├─ api/                   # ApiClient + typed endpoints
│  │  ├─ auth/
│  │  ├─ components/            # shared components
│  │  ├─ features/
│  │  │  ├─ lessons/
│  │  │  ├─ video/
│  │  │  ├─ bfs/
│  │  │  ├─ assessment/
│  │  │  └─ gamification/
│  │  ├─ routes/
│  │  └─ types/                 # shared TS types (ideally generated from OpenAPI)
│  └─ tests/                    # Vitest + RTL
└─ docs/
   ├─ SE-design.md              # this document
   └─ api/                      # exported OpenAPI, if checked in
```
