import { expect, test } from '@playwright/test'
import { DEMO_PASSWORD, demo } from './accounts'
import { answerCorrectly, finishModule, logIn, nextSegment, register } from './helpers'

// Module 0's content: api/app/seed/module-0.json. Segments 2, 4 and 6 are the three
// diagnostic questions, shown inline; 3, 5 and 7 are refreshers; 8 is "You're ready".
test('a new student registers and completes module 0', async ({ page, browserName }) => {
  await register(page, browserName)

  await page.getByRole('link', { name: /Warm-up and queue refresher/ }).click()
  await expect(page).toHaveURL(/\/modules\/0/)

  await nextSegment(page) // 1 "Before we start" → 2
  await answerCorrectly(page, 'Ama')
  await nextSegment(page) // → 3 refresher
  await nextSegment(page) // → 4
  await answerCorrectly(page, '"C"')
  await nextSegment(page) // → 5 refresher
  await nextSegment(page) // → 6
  await answerCorrectly(page, 'B then C then D, one per line')
  await finishModule(page) // → 7, 8, then Finish module

  // Module 1 opens once module 0 is complete.
  await expect(page.getByRole('link', { name: /What is a graph\?.*open/ })).toBeVisible()
})

// A code activity (api/app/seed/module-2.json, activity 205): fill in the blanks of
// add_vertex and submit. The server checks it by comparison (FR-5).
test('a student submits a fill-in code activity', async ({ page, browserName }) => {
  await logIn(page, demo.mid, DEMO_PASSWORD)
  await page.goto('/activities/205')

  await page.getByLabel('Blank 1').selectOption('not in')
  await page.getByLabel('Blank 2').selectOption('[]')

  const checked = page.waitForResponse(
    (r) => r.url().includes('/api/activities/205/') && r.request().method() === 'POST',
  )
  await page.getByRole('button', { name: 'Check answer' }).click()
  expect((await checked).status()).toBe(201)// the attempt is recorded (FR-4.5
  await expect(page.getByText('Correct', { exact: true }).first()).toBeVisible()
})