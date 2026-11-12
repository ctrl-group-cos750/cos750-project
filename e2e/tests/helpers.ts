import { expect, type Locator, type Page } from '@playwright/test'
import { PASSWORD } from './env'

/** Logs in through the real log-in page, then proves the browser keeps the session. */
export async function logIn(page: Page, email: string, password: string) {
  for (let attempt = 0; ; attempt++) {
    await page.goto('/login')
    await page.getByRole('textbox', { name: 'Email' }).fill(email)
    await page.getByRole('textbox', { name: 'Password' }).fill(password)
    const answer = page.waitForResponse((r) => r.url().endsWith('/api/auth/login'))
    await page.getByRole('button', { name: 'Log in' }).click()
    const res = await answer
    // The shared demo and staff accounts may log in 10 times a minute each (NFR-S6), and three
    // browsers share them: wait as the API asks.
    if (res.status() === 429 && attempt < 2) {
      await page.waitForTimeout((Number(res.headers()['retry-after'] ?? 10) + 1) * 1000)
      continue
    }
    expect(res.status(), `logging in as ${email}`).toBe(200)
    break
  }
  await expect(page).not.toHaveURL(/\/login/)

  // A full page load: the app asks the API who is logged in, and the browser must send
  // the session cookie itself. (page.request would use Playwright's cookies, not the browser's.)
  const me = page.waitForResponse((r) => r.url().endsWith('/api/auth/me'))
  await page.reload()
  expect((await me).status()).toBe(200)
}

/** Registers a new student through the register page and lands in the app. */
export async function register(page: Page, account: { email: string; displayName: string }) {
  await page.goto('/register')
  await page.getByRole('textbox', { name: 'Your name' }).fill(account.displayName)
  await page.getByRole('textbox', { name: 'Email' }).fill(account.email)
  await page.getByRole('textbox', { name: 'Password' }).fill(PASSWORD)
  await page.getByRole('button', { name: 'Create account' }).click()
  // The module map, where a new student starts on module 0 (FR-2.1, FR-2.6).
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByRole('button', { name: /^Continue module 0/ })).toBeVisible()
}

/** Presses Tab (or Shift+Tab) until `target` has focus, as a keyboard user would, never by
 * clicking or calling focus(). Shift+Tab when the target comes before the focused element on the
 * page, unless `back` says otherwise. Fails if it isn't reached in `max` presses, which means it
 * can't be reached with the keyboard (NFR-A1, WCAG 2.1.1). */
export async function tabTo(page: Page, target: Locator, options: { back?: boolean; max?: number } = {}) {
  await expect(target).toBeVisible()
  const back =
    options.back ??
    (await target.evaluate((el) => {
      const active = document.activeElement
      if (!active || active === document.body) return false
      return !!(el.compareDocumentPosition(active) & Node.DOCUMENT_POSITION_FOLLOWING)
    }))
  const max = options.max ?? 60
  for (let i = 0; i < max; i++) {
    if (await target.evaluate((el) => el === document.activeElement).catch(() => false)) return
    await page.keyboard.press(back ? 'Shift+Tab' : 'Tab')
  }
  await expect(target, `reachable with ${back ? 'Shift+Tab' : 'Tab'} in ${max} presses`).toBeFocused()
}

/** Activate a button or link with the keyboard: Tab to it, then Enter. */
export async function press(page: Page, target: Locator, options?: { back?: boolean }) {
  await tabTo(page, target, options)
  await page.keyboard.press('Enter')
}

/** Choose the radio button named `name` in the group `radios`, with the keyboard: Tab into the
 * group (onto its checked radio, or its first), then the arrow keys, which move and check. */
export async function chooseRadio(page: Page, radios: Locator, name: string) {
  await expect(radios.first()).toBeVisible()
  const all = await radios.all()
  const names = await Promise.all(
    all.map((r) => r.evaluate((el) => (el as HTMLInputElement).labels?.[0]?.textContent?.trim())),
  )
  const want = names.indexOf(name)
  expect(want, `a radio named "${name}" among ${JSON.stringify(names)}`).toBeGreaterThanOrEqual(0)
  const checked = await Promise.all(all.map((r) => r.isChecked()))
  const start = checked.indexOf(true)
  await tabTo(page, all[start === -1 ? 0 : start])
  if (start === -1) await page.keyboard.press('Space')
  const at = start === -1 ? 0 : start
  for (let i = at; i < want; i++) await page.keyboard.press('ArrowDown')
  for (let i = at; i > want; i--) await page.keyboard.press('ArrowUp')
  await expect(all[want]).toBeChecked()
}

/** The control's focus indicator is visible (WCAG 2.4.7): with focus it has an outline, or its
 * shadow differs from its shadow without focus. */
export async function expectVisibleFocus(target: Locator, label: string) {
  const style = () =>
    target.evaluate((el) => {
      const s = getComputedStyle(el)
      const outline = s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0
      return { outline, shadow: s.boxShadow }
    })
  // As Tab left it; then without focus. Each after the controls' 120 ms transitions end.
  await expect(target).toBeFocused()
  await target.page().waitForTimeout(250)
  const focused = await style()
  await target.evaluate((el) => (el as HTMLElement).blur())
  await target.page().waitForTimeout(250)
  const unfocused = await style()
  await target.focus()
  expect(
    focused.outline || focused.shadow !== unfocused.shadow,
    `${label}: no visible focus indicator (focused ${JSON.stringify(focused)}, not focused ${JSON.stringify(unfocused)})`,
  ).toBe(true)
}
