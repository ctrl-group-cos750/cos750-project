import { execSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { expect, test } from '@playwright/test'
import { PASSWORD, REPO_ROOT, STAFF_FILE, STAFF_GRANT, STAFF_STATE, STATE_DIR } from './env'
import { clientAddress, newAccount } from './fixtures'

// Runs once, before the browser projects (playwright.config.ts): a staff account, registered
// like any student and then made staff with the CLI, as on a real deploy (api/app/staff.py).
// The video tests use it to upload a video with a checkpoint through the staff API, so a fresh
// stack needs no videos of its own.

test('a staff account', async ({ playwright, baseURL }) => {
  mkdirSync(STATE_DIR, { recursive: true })
  const context = await playwright.request.newContext({
    baseURL,
    ignoreHTTPSErrors: true,
    extraHTTPHeaders: { 'X-Forwarded-For': clientAddress() },
  })
  const account = newAccount('staff')
  const res = await context.post('/api/auth/register', { data: { ...account, password: PASSWORD } })
  expect(res.status(), await res.text()).toBe(201)
  execSync(`${STAFF_GRANT} ${account.email}`, { cwd: REPO_ROOT, stdio: 'pipe' })
  const me = await context.get('/api/auth/me')
  expect(((await me.json()) as { isStaff: boolean }).isStaff, 'made staff').toBe(true)
  writeFileSync(STAFF_FILE, JSON.stringify(account))
  // The API session, for the tests' staff API calls (never loaded into a browser).
  await context.storageState({ path: STAFF_STATE })
  await context.dispose()
})
