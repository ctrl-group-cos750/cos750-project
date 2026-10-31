# Deploying to Coolify

Two Coolify resources, both built from `docker-compose.yml` in this repo:

| Branch | Domain | Coolify environment |
|---|---|---|
| `master` | `https://ctrlacademy.co.za` (and `www.` redirecting to it) | production |
| `staging` | `https://staging.ctrlacademy.co.za` | staging |

Each has its own Postgres volume, so staging data never touches production.

## 1. DNS

At the registrar for `ctrlacademy.co.za`, replace the parking records with these, where
`<COOLIFY_IP>` is the Coolify server's public IPv4:

| Type | Name | Value |
|---|---|---|
| A | `@` | `<COOLIFY_IP>` |
| A | `www` | `<COOLIFY_IP>` |
| A | `staging` | `<COOLIFY_IP>` |

Check with `dig +short ctrlacademy.co.za` before step 3: Let's Encrypt can only issue the
certificate once the name resolves to the server.

## 2. Connect the repo

In Coolify, add the GitHub App as a source (Sources → GitHub App) with access to
`MatthewEls/cos750-project`. This gives private-repo access and push-to-deploy webhooks.

## 3. Create the production resource

1. Project → Environment `production` → New Resource → Private Repository (with GitHub App).
2. Repository `MatthewEls/cos750-project`, branch `master`, build pack **Docker Compose**,
   compose file `/docker-compose.yml`.
3. Under the `web` service, set Domains to `https://ctrlacademy.co.za,https://www.ctrlacademy.co.za`.
   Leave `api` and `db` without a domain: they are only reachable on the internal network.
4. Environment Variables: set `POSTGRES_PASSWORD` to a long random value (`openssl rand -hex 24`).
   `POSTGRES_USER` and `POSTGRES_DB` default to `ctrl`.
5. Optional: in the proxy settings, redirect `www` to the apex.
6. Deploy. Enable "Auto Deploy" so each push to `master` redeploys.

## 4. Create the staging resource

The same steps, in a `staging` environment: branch `staging`, domain
`https://staging.ctrlacademy.co.za`, and a **different** `POSTGRES_PASSWORD`.

## 5. Check it

```
curl https://ctrlacademy.co.za/api/health
# {"status":"ok","database":"ok"}
```

The home page also shows the API status line.

## Backups

Each resource has a Coolify scheduled task, `postgres-backup`, that runs in the `db` container:
staging at 01:00 UTC, production at 01:30 UTC. It writes a `pg_dump -Fc` file to
`/var/lib/postgresql/backups/` on the database volume and keeps 14 days.

These dumps survive redeploys and container rebuilds, but not the loss of the volume or the server.

Restore one (Coolify → resource → Terminal → `db`):

```
pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists /var/lib/postgresql/backups/<file>.dump
```

## Migrations

The API container runs `alembic upgrade head` before it starts serving. A migration that fails stops
the container, so the deploy fails and the previous one keeps serving. `/api/health` reports the
schema revision each environment is on.

## How the pieces fit

```
browser ──https──▶ Coolify proxy (Traefik) ──▶ web:80  (nginx: SPA + /api proxy)
                                                  │
                                                  └──/api/──▶ api:8000 (FastAPI) ──▶ db:5432 (Postgres)
```

One origin means no CORS, and no API URL baked into the frontend build. Every API route must
live under `/api`.
