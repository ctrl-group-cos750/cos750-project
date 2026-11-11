import { expect, test, type Page } from '@playwright/test'
import { DEMO_PASSWORD, demo } from './accounts'
import { logIn } from './helpers'

// NFR-U1: every module except 2, 4 and 5 (which need a keyboard for code) works at 360 px.
test.use({ viewport: { width: 360, height: 740 } })

async function expectNoSidewaysScroll(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow, 'the page scrolls sideways').toBeLessThanOrEqual(0)
}

/** Moves to the next or previous segment and waits until the page shows it. */
async function step(page: Page, name: 'Next →' | '← Previous') {
  const counter = page.getByText(/^Segment \d+ of \d+$/)
  const before = (await counter.textContent()) ?? ''
  // dispatchEvent: Playwright's WebKit on Windows never reports this button as "stable" at
  // 360 px (a different segment each run), so a normal click times out. This test checks
  // layout, not clicking. Still to check on a real iPhone that nothing on these pages jitters.
  await page.getByRole('button', { name }).dispatchEvent('click')
  await expect(counter).not.toHaveText(before)
}

test('modules 0, 1, 3 and 6 fit a 360 px screen', async ({ page }) => {
  // The ready account has finished every module, so every segment can be visited.
  await logIn(page, demo.ready, DEMO_PASSWORD)
  await expectNoSidewaysScroll(page) // the module map

  for (const id of [0, 1, 3, 6]) {
    await test.step(`module ${id}`, async () => {
      await page.goto(`/modules/${id}`)
      const counter = page.getByText(/^Segment \d+ of \d+$/)
      await expect(counter).toBeVisible()

      // A finished module opens at its end: go back to the first segment.
      for (let i = 0; i < 20 && !/^Segment 1 of/.test((await counter.textContent()) ?? ''); i++) {
        await step(page, '← Previous')
      }
      // Then check every segment on the way to the end.
      for (let i = 0; i < 20; i++) {
        await expectNoSidewaysScroll(page)
        const [, at, total] = ((await counter.textContent()) ?? '').match(/(\d+) of (\d+)/) ?? []
        if (at === total) break
        await step(page, 'Next →')
      }
    })
  }
})