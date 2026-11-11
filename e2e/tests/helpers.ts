import { expect, type Locator, type Page } from '@playwright/test'

/** Logs in through the real log-in page, then proves the browser keeps the session. */
export async function logIn(page: Page, email: string, password: string) {
  await page.goto('/login')
  await page.getByRole('textbox', { name: 'Email' }).fill(email)
  await page.getByRole('textbox', { name: 'Password' }).fill(password)
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page).not.toHaveURL(/\/login/)

  // A full page load: the app asks the API who is logged in, and the browser must send
  // the session cookie itself. (page.request would use Playwright's cookies, not the browser's.)
  const me = page.waitForResponse((r) => r.url().endsWith('/api/auth/me'))
  await page.reload()
  expect((await me).status()).toBe(200)
}

/** Registers a fresh student (unique per browser and run) and lands in the app. */
export async function register(page: Page, browserName: string) {
  const email = `e2e-${browserName}-${Date.now()}@example.com`
  await page.goto('/register')
  await page.getByRole('textbox', { name: 'Your name' }).fill('E2E Tester')
  await page.getByRole('textbox', { name: 'Email' }).fill(email)
  await page.getByRole('textbox', { name: 'Password' }).fill('Queue-Walk-2026!')
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page).not.toHaveURL(/\/register/)
  return email
}

/** Answers a multiple-choice activity and expects it marked correct. */
export async function answerCorrectly(page: Page, option: string) {
  await page.getByRole('radio', { name: option, exact: true }).check()
  await page.getByRole('button', { name: 'Check answer' }).click()
  await expect(page.getByText('Correct', { exact: true }).first()).toBeVisible()
}

/** Clicks Next and waits until the page shows the next segment ("Segment N of M"). */
export async function nextSegment(page: Page) {
  const counter = page.getByText(/^Segment \d+ of \d+$/)
  const before = (await counter.textContent()) ?? ''
  const next = page.getByRole('button', { name: 'Next →' })
  await expect(next).not.toHaveAttribute('aria-disabled', 'true') // the module knows it's done
  await next.click()
  await expect(counter).not.toHaveText(before)
}

/** Moves to the last segment, finishes the module and waits for the module map. */
export async function finishModule(page: Page) {
  const counter = page.getByText(/^Segment \d+ of \d+$/)
  for (let i = 0; i < 20; i++) {
    const [, at, total] = (await counter.textContent())?.match(/(\d+) of (\d+)/) ?? []
    if (at === total) break
    await nextSegment(page)
  }
  await page.getByRole('button', { name: 'Finish module' }).click()
  await expect(page).toHaveURL(/\/$/) // back on the module map
}

/** Presses Tab until `target` has focus, as a keyboard user would. */
export async function tabTo(page: Page, target: Locator) {
  await expect(target).toBeVisible()
  for (let i = 0; i < 60; i++) {
    if (await target.evaluate((el) => el === document.activeElement)) return
    await page.keyboard.press('Tab')
  }
  throw new Error('Could not reach the element with the keyboard')
}