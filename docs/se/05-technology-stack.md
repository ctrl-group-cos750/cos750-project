# Technology stack

| Layer | Choice | Rationale |
|---|---|---|
| Backend language | **Python 3.12** | Team decision. Good for algorithm code and fast API development. |
| Web framework | **FastAPI** | Pydantic validation, typed request/response models, OpenAPI docs generated at `/api/docs`, which serve as the frontend contract. |
| ASGI server | **Uvicorn** | Runs directly as the API container's process. Docker restarts it if it crashes, so it needs no separate process manager. |
| Validation | **Pydantic v2** | Comes with FastAPI. Validates every request at the API boundary. |
| ORM and migrations | **SQLAlchemy 2.1** + **Alembic** | Typed models. Migrations are applied automatically when the API container starts (`alembic upgrade head`), so a migration that fails stops the deploy instead of running against the wrong schema. Baseline revision `0001` is in place. |
| Database | **PostgreSQL 18** in every environment | Local development runs the same Postgres in Docker. Tests use in-memory SQLite, so they run without a database server. Using one database engine everywhere avoids JSON and enum behaviour differing between dev and production. |
| Auth | **JWT** (PyJWT) in an **httpOnly, Secure, SameSite=Lax cookie**; passwords hashed with **Argon2** (pwdlib) | JWT as in Draft 1. Because the SPA and API share one origin, a cookie is simpler than an `Authorization: Bearer` header, and JavaScript can't read it, so an XSS bug can't steal the token. pwdlib replaces passlib: passlib is no longer maintained and breaks with current bcrypt releases, and FastAPI's own documentation now uses pwdlib. Email is required. Password reset and refresh tokens are future work. |
| Frontend language | **TypeScript 7** | Team decision. Type safety across the UI and the API client. |
| Frontend framework | **React 19** | Team decision, and what the scaffold already uses. |
| Build tool | **Vite 8** | Fast dev server with hot reload; the dev server proxies `/api` to the local API, so dev also uses one origin. |
| Routing | **React Router** | Client-side routing for the multi-view SPA. nginx already serves `index.html` for unknown paths. |
| Server state | **TanStack Query** | Data fetching and caching against the REST API. |
| Graph rendering | **SVG via D3** | As Draft 1: for graphs of up to about 50 nodes, SVG is simpler than Canvas (one DOM element per node and edge, easy per-element transitions, highlighting and click handling). |
| Video | **HTML5 `<video>`**, self-hosted MP4 (H.264) with WebVTT captions | The player needs full control to pause at checkpoints and block seeking past them. An embedded YouTube player would add adverts, recommendations and a dependency outside our control during the demo. Captions also provide the `text` mode for each video. |
| Testing (backend) | **pytest** with FastAPI `TestClient`, warnings treated as errors | Unit tests for the BfsEngine and services, plus API tests against a fresh SQLite database that every migration has been applied to. |
| Testing (frontend) | **Vitest** + **React Testing Library** | Native fit with Vite; component and logic tests, with coverage reported in CI. |
| End-to-end testing | **Playwright** | Walks through the full student flow (log in, lesson, checkpoint, BFS, assessment, scaffold) in a real browser against a running stack. |
| Lint and format (Python) | **ruff** (format + lint, including the bandit security rules and the FastAPI rules) and **mypy --strict** | Enforced in CI. |
| Lint and format (TypeScript) | **oxlint** (correctness, suspicious and perf rules plus the React, import, jsx-a11y and Vitest plugins; warnings fail the build) and **Prettier** | oxlint replaces ESLint: it is already configured and runs in under a second. The `jsx-a11y` plugin enforces part of the accessibility requirements (NFR-A). |
| CI | **GitHub Actions** | On every PR and on every push to `staging` and `master`: format, lint, types, tests and builds for both apps, and a build of the Docker images. A `branch-flow` check rejects PRs into `master` that don't come from `staging`. Dependabot opens weekly update PRs into `staging`. |
| Hosting | **Coolify** on the team's server, **Docker Compose** build pack | Coolify builds and deploys on every push: `staging` → staging.ctrlacademy.co.za, `master` → ctrlacademy.co.za. Its Traefik proxy terminates HTTPS. Staging sits behind a team-password page so the public can't see unfinished work. |
