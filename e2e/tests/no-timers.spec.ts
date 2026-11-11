import { expect, test } from '@playwright/test'
import { DEMO_PASSWORD, demo } from './accounts'
import { answerCorrectly, logIn, nextSegment, register } from './helpers'

// ID document §6.2, WCAG 2.2.1: no timers on activities, checkpoints or the mastery check.
// The browser's clock jumps two hours ahead: nothing may expire, count down or lock.
const TIMER_TEXT = /time (left|remaining|is up)|time's up|seconds? left|expired/i

test('an activity can still be answered after two hours', async ({ page, browserName }) => {
  await page.clock.install()
  await register(page, browserName)
  await page.goto('/modules/0')
  await nextSegment(page) // to the first question

  await page.clock.fastForward('02:00:00')
  await expect(page.getByText(TIMER_TEXT)).toHaveCount(0)
  await answerCorrectly(page, 'Ama')
})

test('a mastery-check item has no timer', async ({ page }) => {
  await page.clock.install()
  await logIn(page, demo.ready, DEMO_PASSWORD)
  await page.goto('/activities/602') // a module 6 mastery item; only looked at, never answered

  await page.clock.fastForward('02:00:00')
  await expect(page.getByText(TIMER_TEXT)).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Check answer' })).toBeEnabled()
})