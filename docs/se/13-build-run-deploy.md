# Build / Run / Deploy

## Local development
**Backend**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e .            # or: pip install -r requirements
alembic upgrade head        # apply migrations
python -m app.seed.load      # load placeholder fixtures (lessons, questions, graph scenarios) — real content added later
uvicorn app.main:app --reload
# API at http://localhost:8000 ; docs at /docs
```

**Frontend**
```bash
cd frontend
npm install
npm run dev                  # Vite dev server, e.g. http://localhost:5173
# Configure API base URL via env (e.g. VITE_API_BASE_URL)
```

## Testing & quality
```bash
# backend
cd backend && pytest -q && ruff check .
# frontend
cd frontend && npm test -- --silent && npm run lint
```

## CI (GitHub Actions) **[PROVISIONAL]**
- On push/PR: install deps, run Ruff + pytest (backend) and ESLint + Vitest (frontend), build the frontend. Keep `main` deployable.

## Deployment
Containerised deployment via Docker, orchestrated with Docker Compose, fronted by a reverse proxy that terminates HTTPS on the **team's domain**. Concrete but still draft-level:

- **Backend:** containerised FastAPI (Uvicorn behind a process manager) as a Docker service.
- **Database:** containerised **PostgreSQL** with a persistent volume; the backend connects via `DATABASE_URL`.
- **Frontend:** `vite build` produces static assets served by the reverse proxy (or a lightweight static container); `VITE_API_BASE_URL` points to the backend route.
- **Reverse proxy:** **Nginx, Caddy, or Traefik** terminates TLS on the team's domain, routes `/api/*` to the backend container and all other paths to the static frontend, and handles HTTPS certificates (e.g. automatic Let's Encrypt via Caddy/Traefik).
- **Media:** video files served as static assets (object storage or a static mount), not proxied through the API.
- **Secrets/config:** environment variables (DB URL, JWT secret, CORS origins, domain); never committed.
