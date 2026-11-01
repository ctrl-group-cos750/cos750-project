# System Architecture

## High-level architecture

```
Browser
  │  HTTPS, one origin: ctrlacademy.co.za (production), staging.ctrlacademy.co.za (staging)
  ▼
Coolify's Traefik proxy (on our server; Let's Encrypt certificates, Cloudflare DNS)
  ▼
web container: nginx
  ├─ /            React + TypeScript SPA (Vite build)
  ├─ /media/      lesson videos (static files, served with range requests)
  └─ /api/*  ──►  api container: FastAPI on Uvicorn
                    routers → services → SQLAlchemy models
                    BfsEngine (pure Python module)
                      ▼
                  db container: PostgreSQL 18 (persistent volume, nightly pg_dump)
```

The three containers are defined in `docker-compose.yml`, and Coolify deploys that file as it is.
nginx serves the SPA and forwards `/api` to the API, so the browser only ever talks to one origin.
That removes the need for CORS and for an API base URL in the frontend.

## Tier responsibilities
- **Frontend (client tier):** presentation, interaction, animation, client-side validation. Holds no business authority over scores — it reports events; the backend decides and persists.
- **Backend (application tier):** authoritative logic — authentication, BFS computation, scoring rules, assessment branching, content retrieval, persistence orchestration.
- **Data tier:** durable storage of structured data; media served from a static/object store rather than the database.

## Key architectural decisions
- **Thin client for authority-bearing logic.** Score/assessment decisions are server-side to prevent client tampering and keep rules in one place.
- **BFS computed server-side.** Guarantees a single correct implementation (the canonical algorithm being taught) and keeps the frontend a pure renderer of returned steps.
- **Stateless API with token auth.** Enables horizontal scaling and simple deployment. The token travels in an httpOnly cookie (§5).
- **Content as data.** Lessons, questions, and graph scenarios are stored/configured as data so new content does not require frontend code changes.
