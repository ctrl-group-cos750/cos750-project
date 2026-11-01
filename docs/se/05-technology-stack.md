# Technology Stack (engineering rationale)

| Layer | Choice | Brief engineering rationale |
|---|---|---|
| Backend language | **Python 3.12+** | Team decision; strong ecosystem for graph/algorithm code and rapid API development. |
| Web framework | **FastAPI** | ASGI performance, first-class Pydantic validation, automatic OpenAPI/Swagger docs (aids frontend contract + testing), typed request/response models. |
| ASGI server | **Uvicorn** (dev) / Uvicorn behind a process manager (prod) | Standard, lightweight ASGI server for FastAPI. |
| Data validation | **Pydantic v2** | Schema-driven validation at the API boundary; reduces hand-written input checks. |
| ORM | **SQLAlchemy 2.x** + **Alembic** | Mature ORM with typed models; Alembic for migrations as the schema evolves across drafts. |
| Database | **SQLite** (local dev only) → **PostgreSQL** (production) | Confirmed: PostgreSQL is the production database; SQLite remains a zero-setup option for local development. SQLAlchemy + Alembic abstract the switch and keep migrations portable. |
| Auth | **JWT access tokens** (OAuth2 password flow via FastAPI) + password hashing (**passlib/bcrypt**); email required for identity/recovery | Stateless, well-supported. Draft 1 scope: access tokens only. Password reset and refresh tokens are deferred to Draft 2. |
| Frontend language | **TypeScript** | Team decision; type safety across a non-trivial UI and API client. |
| Frontend framework | **React 18** | Team decision; large ecosystem for the interactive components required. |
| Build tool | **Vite** | Fast dev server + HMR, simple TS/React setup, efficient production bundles. |
| Routing | **React Router** | Standard client-side routing for the multi-view SPA. |
| Server state | **TanStack Query (React Query)** **[PROVISIONAL]** | Declarative data fetching/caching against the REST API; reduces bespoke fetch logic. |
| Graph rendering | **SVG via D3** (layout + transitions) | Chosen over Canvas. For Draft 1 graph sizes (≤ ~50 nodes), SVG is simpler: declarative DOM nodes/edges, easy per-element transitions/animation of BFS steps, straightforward highlighting and event handling, and less boilerplate than an imperative Canvas render loop. Canvas' large-graph performance advantage is unnecessary at this scale and can be revisited if graphs grow. |
| Testing (backend) | **pytest** + FastAPI `TestClient` | Fast unit/integration tests against the API and BfsEngine. |
| Testing (frontend) | **Vitest** + **React Testing Library** | Native fit with Vite; component and logic tests. |
| Lint/format | **Ruff** (Python), **ESLint + Prettier** (TS) | Consistent style; CI-enforceable. |
| Packaging/deploy | **Docker** containers (backend, PostgreSQL, static-served frontend) behind a reverse proxy (**Nginx/Caddy/Traefik**) | Confirmed deployment model: containerised services orchestrated with Docker Compose, fronted by a reverse proxy terminating HTTPS on the team's domain. Reproducible environments across dev and the demo deployment. |
