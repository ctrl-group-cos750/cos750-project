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

In Coolify, add the GitHub App as a source (Sources → GitHub App), installed on the `ctrl-group-cos750`
organisation with access to `ctrl-group-cos750/cos750-project`. This gives private-repo access and
push-to-deploy webhooks. (The repo moved from `MatthewEls` to the organisation on 1 November 2026; the
app has to be installed where the repo lives.)

## 3. Create the production resource

1. Project → Environment `production` → New Resource → Private Repository (with GitHub App).
2. Repository `ctrl-group-cos750/cos750-project`, branch `master`, build pack **Docker Compose**,
   compose file `/docker-compose.yml`.
3. Under the `web` service, set Domains to `https://ctrlacademy.co.za,https://www.ctrlacademy.co.za`.
   Leave `api` and `db` without a domain: they are only reachable on the internal network.
4. Environment Variables: set `POSTGRES_PASSWORD` to a long random value (`openssl rand -hex 24`)
   and `SECRET_KEY`, which signs the session cookies, to another (`openssl rand -hex 32`).
   `POSTGRES_USER` and `POSTGRES_DB` default to `ctrl`. Changing `SECRET_KEY` logs everyone out.
   Set `PILOT_PSEUDONYM_KEY` to a third (`openssl rand -hex 32`): it keys the pseudonyms in the
   pilot's CSV files (SE document FR-10.3), and changing it renames every student there, so set
   it once and keep it. Unset, the API uses `SECRET_KEY` and logs a warning, and then changing
   `SECRET_KEY` renames them too.
   Optional: `DEMO_PASSWORD` makes the four seeded demo accounts, one per stage of the course:
   `new@`, `mid@`, `not-yet@` and `ready@demo.example.com` (`api/app/seed/demo/accounts.json`
   says what each shows). Every deploy rebuilds them, undoing whatever a rehearsal did. Unset,
   there are none. It must pass the app's password rules (upper, lower, number, symbol, 8+
   characters, no account's name in it). If it doesn't, the deploy still succeeds but the demo
   accounts aren't rebuilt: the api container's log says `demo accounts NOT rebuilt` and why.
   A module with no content yet is passed over. If an account's module progress can't go on
   (a module it needs is still locked), the log says where (`demo progress …`). A passphrase is easiest to type on stage: `Purple kettle 42
   harbour`. Avoid `$`, which Coolify may try to expand.
5. Optional: in the proxy settings, redirect `www` to the apex.
6. Deploy. Enable "Auto Deploy" so each push to `master` redeploys.

## 4. Create the staging resource

The same steps, in a `staging` environment: branch `staging`, domain
`https://staging.ctrlacademy.co.za`, and a **different** `POSTGRES_PASSWORD`, `SECRET_KEY` and `PILOT_PSEUDONYM_KEY`.

## 5. Check it

```
curl https://ctrlacademy.co.za/api/health
# {"status":"ok","database":"ok"}
```

The home page also shows the API status line.

## Staging login

Staging shows a Ctrl Group login page (`web/gate/index.html`) until the visitor enters the team
password; the API is closed too. It is on when `STAGING_PASSWORD` is set, which it is in Coolify on
the staging resource only, so production and local runs have no login. To change the password, edit
it there and redeploy; everyone then logs in again. `/healthz` stays open for the container healthcheck.

The page stores `sha256("ctrl-academy-staging:" + password)` in a `ctrl_staging` cookie for 30 days,
and nginx compares it on every request (`web/staging-gate.sh`). It keeps the public out; it is not
per-user security, so never put real personal data on staging.

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
