import { expect, test } from '@playwright/test'
import { DEMO_PASSWORD, demo } from './accounts'
import { logIn } from './helpers'

test('the mastery report says a finished student is ready for the lecture', async ({ page }) => {
  await logIn(page, demo.ready, DEMO_PASSWORD)
  await page.goto('/report')
  await expect(page.getByText(/ready for the lecture/i).first()).toBeVisible()
})

// Only opens the review path, so the account stays "not yet" for the next run.
test('a "not yet" objective opens its review path', async ({ page }) => {
  await logIn(page, demo.notYet, DEMO_PASSWORD)
  await page.goto('/report')
  await expect(page.getByText(/not yet/i).first()).toBeVisible()
  await page.getByRole('link', { name: /review/i }).first().click()
  await expect(page).toHaveURL(/\/review\/6/)
})