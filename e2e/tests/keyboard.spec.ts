import { expect, test } from '@playwright/test'
import { register, tabTo } from './helpers'

// NFR-A1: one module completed with the keyboard only (module 0; answers from module-0.json).
test('a student completes module 0 with the keyboard only', async ({ page, browserName }) => {
  // WebKit, like Safari, skips links on Tab unless the user turns on "Press Tab to highlight
  // each item" (or holds Option), which a test can't do. Chromium and Firefox cover NFR-A1.
  test.skip(browserName === 'webkit', 'WebKit skips links on Tab by default')

  await register(page, browserName)
  const counter = page.getByText(/^Segment \d+ of \d+$/)

  // Tab to a link or button and press Enter.
  async function activate(name: string | RegExp, role: 'link' | 'button' = 'button') {
    await tabTo(page, page.getByRole(role, { name }))
    await page.keyboard.press('Enter')
  }

  async function next() {
    const before = (await counter.textContent()) ?? ''
    // After an answer the module reloads to learn the segment is done; until then Next is
    // aria-disabled and ignores key presses.
    await expect(page.getByRole('button', { name: 'Next →' })).not.toHaveAttribute(
      'aria-disabled',
      'true',
    )
    await activate('Next →')
    await expect(counter).not.toHaveText(before)
  }

  // Tab into the options, Space to pick one, arrow keys to move to the right answer.
  async function answer(option: string) {
    await tabTo(page, page.getByRole('radio').first())
    await page.keyboard.press('Space')
    const target = page.getByRole('radio', { name: option, exact: true })
    for (let i = 0; i < 5 && !(await target.isChecked()); i++) {
      await page.keyboard.press('ArrowDown')
    }
    await expect(target).toBeChecked()
    await activate('Check answer')
    await expect(page.getByText('Correct', { exact: true }).first()).toBeVisible()
  }

  await activate(/Warm-up and queue refresher/, 'link')
  await expect(page).toHaveURL(/\/modules\/0/)
  await next()
  await answer('Ama')
  await next()
  await next()
  await answer('"C"')
  await next()
  await next()
  await answer('B then C then D, one per line')
  await next()
  await next()
  await activate('Finish module')
  await expect(page).toHaveURL(/\/$/)
  // Finishing really completed the module: module 1 is now open.
  await expect(page.getByRole('link', { name: /What is a graph\?.*open/ })).toBeVisible()
})