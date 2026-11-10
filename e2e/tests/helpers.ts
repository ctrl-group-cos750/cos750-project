import { expect, type Page } from '@playwright/test'

/** Logs in through the real log-in page, then proves the browser keeps the session. */
export async function logIn(page: Page, email: string, password: string) {
  await page.goto('/login')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page).not.toHaveURL(/\/login/)

  // A full page load: the app asks the API who is logged in, and the browser must send
  // the session cookie itself. (page.request would use Playwright's cookies, not the browser's.)
  const me = page.waitForResponse((r) => r.url().endsWith('/api/auth/me'))
  await page.reload()
  expect((await me).status()).toBe(200)
}