import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'
import { DEMO_PASSWORD, demo } from './accounts'
import { logIn } from './helpers'

// WCAG 2.1 levels A and AA (NFR-A2, NFR-A3; SE document §14.1).
const WCAG_21_AA = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']

/** Scans the current page and fails with a readable list of any violations. */
async function expectNoViolations(page: Page) {
  const { violations } = await new AxeBuilder({ page }).withTags(WCAG_21_AA).analyze()
  const found = violations.map(
    (v) =>
      `${v.id} (${v.impact}): ${v.help}, on ${v.nodes
        .slice(0, 3)
        .map((n) => n.target.join(' '))
        .join(', ')}`,
  )
  expect(found).toEqual([])
}

test('pages before logging in', async ({ page }) => {
  for (const path of ['/login', '/register']) {
    await test.step(path, async () => {
      await page.goto(path)
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
      await expectNoViolations(page)
    })
  }
})

test('pages for a signed-in student', async ({ page }) => {
  // Only visits pages, so the account's progress stays the same.
  await logIn(page, demo.notYet, DEMO_PASSWORD)
  const pages = [
    '/', // module map
    '/modules/0',
    '/modules/3',
    '/activities/205', // a code activity
    '/graphs/1', // the BFS visualiser
    '/report',
    '/review/6',
    '/badges',
    '/profile',
  ]
  for (const path of pages) {
    await test.step(path, async () => {
      await page.goto(path)
      await page.waitForLoadState('networkidle') // wait until the page has its data
      await expectNoViolations(page)
    })
  }
})