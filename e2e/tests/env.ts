import { fileURLToPath } from 'node:url'

/**
 * Where the tests find the app, and the test-only passwords. Every value can be set from the
 * environment.
 *
 * - BASE_URL: the app (default: the docker-compose.e2e.yml stack at https://localhost:8443).
 * - DEMO_PASSWORD: the seeded demo accounts' password in that stack (docker-compose.e2e.yml).
 * - E2E_STAFF_GRANT: the command that makes an account staff, given its email as the last
 *   argument, as on a real deploy (api/app/staff.py). Default: through the compose stack's api
 *   container; set COMPOSE_PROJECT_NAME if the stack was started with `-p`.
 */
export const BASE_URL = process.env.BASE_URL ?? 'https://localhost:8443'

/** A test-only password for local and CI stacks, never the deployed one. */
export const DEMO_PASSWORD = process.env.DEMO_PASSWORD ?? 'Demo-pass-2026!'

/** The password of every account a test registers. It passes the app's rules (passwordRules.ts). */
export const PASSWORD = 'Queue-Walk-2026!'

export const STAFF_GRANT =
  process.env.E2E_STAFF_GRANT ??
  'docker compose -f docker-compose.yml -f docker-compose.e2e.yml exec -T api python -m app.staff grant'

/** The repository root, where E2E_STAFF_GRANT runs. */
export const REPO_ROOT = fileURLToPath(new URL('../../', import.meta.url))

/** Gitignored: what the setup project leaves for the tests, one folder per stack, so two runs
 * against different stacks don't share a staff account. */
const stack = new URL(BASE_URL).host.replace(/[^a-z0-9]+/gi, '-')
export const STATE_DIR = fileURLToPath(new URL(`../.state/${stack}/`, import.meta.url))
export const STAFF_FILE = `${STATE_DIR}staff.json`
export const STAFF_STATE = `${STATE_DIR}staff-session.json`
