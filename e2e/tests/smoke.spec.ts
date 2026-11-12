import { test } from '@playwright/test'
import { DEMO_PASSWORD, demo } from './accounts'
import { logIn } from './helpers'

// Logging in really works in each browser, cookie included.
test('a demo student can log in', async ({ page }) => {
  await logIn(page, demo.ready, DEMO_PASSWORD)
})
