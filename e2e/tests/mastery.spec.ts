import { activity, demoAccounts, objectives, reviewPaths } from './content'
import { answerActivity, walkModule } from './drive'
import { DEMO_PASSWORD, demo } from './accounts'
import { expect, test, type Page } from './fixtures'
import { logIn } from './helpers'

// The mastery report, review paths and the mastery check (FR-7; ID document §7.5, §7.6).

test('the mastery report says a finished student is ready for the lecture', async ({ page }) => {
  await logIn(page, demo.ready, DEMO_PASSWORD)
  await page.goto('/report')
  await expect(page.getByRole('heading', { name: 'Your mastery report' })).toBeVisible()
  await expect(page.getByText('Ready for the lecture', { exact: true })).toBeVisible()
  await expect(page.getByText(/^Not ready yet/)).toHaveCount(0)
})

// Only opens the review path, so the account stays "not yet" for the next run.
test('a "not yet" objective opens its review path', async ({ page }) => {
  const notYet = demoAccounts.find((d) => `${d.key}@demo.example.com` === demo.notYet)
  const objective = notYet?.expect.not_yet?.[0]
  expect(objective, 'the not-yet demo account has an objective not yet met').toBeDefined()
  await logIn(page, demo.notYet, DEMO_PASSWORD)
  await page.goto('/report')
  await expect(page.getByText(/^Not ready yet/)).toBeVisible()
  await page
    .getByRole('link', { name: new RegExp(`^Start review path\\W+objective ${objective}$`) })
    .click()
  await expect(page).toHaveURL(new RegExp(`/review/${objective}$`))
  await expect(page.getByRole('heading', { name: `Review: objective ${objective}` })).toBeVisible()
})

// A student who has done modules 0 to 5 (through the API) answers every mastery item in module 6
// on screen, every kind of activity, right except for one objective's. The report then shows that
// objective "not yet" with its review path; the student works through the path's fresh questions
// and the report turns "Ready for the lecture".
//
// No timers (ID document §6.2, WCAG 2.2.1): each mastery item is left open for 30 minutes of the
// page's clock before it is answered, and must still take the answer.

/** The objective with the fewest fresh questions on its review path, so the test stays short.
 * Chosen from the content, not named, so a content change can't break it. */
function objectiveToMiss(): number {
  const fresh = (objective: number) =>
    (reviewPaths.get(objective)?.segments ?? []).filter(
      (s) => s.activity_id !== undefined && activity(s.activity_id).purpose === 'mastery',
    ).length
  return [...reviewPaths.keys()]
    .filter((o) => fresh(o) > 0)
    .sort((a, b) => fresh(a) - fresh(b) || a - b)[0]
}

/** The report's row for an objective, found by the objective's text. */
function row(page: Page, objective: number) {
  const text = objectives.find((o) => o.id === objective)?.text ?? ''
  return page.getByRole('main').getByRole('listitem').filter({ hasText: text })
}

const ALL_KINDS = [
  'multiple_choice',
  'matching',
  'fill_in',
  'parsons',
  'trace',
  'fix_the_bug',
  'choose_tests',
]

test('the mastery check on screen, the report, then a review path that makes the student ready', async ({
  page,
  course,
}) => {
  test.slow() // one student through all of module 6 and a review path
  const missed = objectiveToMiss()
  expect(missed, 'an objective whose review path has fresh questions').toBeDefined()
  await course.completeBefore(6)
  const module = await course.module(6)
  // The mastery check asks every kind of activity (ID document §7.5).
  const kinds = new Set(module.segments.flatMap((s) => (s.activityId ? [activity(s.activityId).kind] : [])))
  expect([...kinds].sort()).toEqual([...ALL_KINDS].sort())
  await course.roomFor(module.segments.length + module.retrieval.length)

  await page.clock.install()
  await walkModule(page, module, {
    answerFor: (a) => (a.purpose === 'mastery' && a.objective_id === missed ? 'wrong' : 'right'),
    beforeAnswer: async () => {
      // The item is on screen before the clock moves (not while it still loads).
      await expect(page.getByRole('button', { name: 'Check answer' }).first()).toBeVisible()
      await page.clock.fastForward('30:00')
      await expect(page.getByRole('timer')).toHaveCount(0)
      await expect(page.getByText(/time('s| is) up|timed out|time left|time remaining/i)).toHaveCount(0)
    },
  })

  // The report (FR-7.3, FR-7.4): the missed objective is "not yet", with its review path.
  await page.goto('/report')
  await expect(page.getByRole('heading', { name: 'Your mastery report' })).toBeVisible()
  await expect(page.getByText('Not ready yet: 1 objective to review', { exact: true })).toBeVisible()
  for (const { id } of objectives)
    await expect(row(page, id)).toContainText(id === missed ? 'Not yet' : 'Met independently')

  // The review path (FR-7.5): answer each fresh question on its own page, then back.
  await row(page, missed)
    .getByRole('link', { name: /^Start review path/ })
    .click()
  await expect(page.getByRole('heading', { name: `Review: objective ${missed}` })).toBeVisible()
  const freshLinks = page.getByRole('link', { name: /^Answer\W/ })
  const fresh = await freshLinks.count()
  expect(fresh).toBeGreaterThan(0)
  await expect(page.getByText(/^You have answered every fresh question/)).toHaveCount(0)
  for (let i = 0; i < fresh; i++) {
    await freshLinks.first().click()
    const id = Number(new URL(page.url()).pathname.split('/').pop())
    await answerActivity(page, page.getByRole('main'), activity(id), 'right')
    await page.goBack()
    await expect(page.getByRole('heading', { name: `Review: objective ${missed}` })).toBeVisible()
  }
  await expect(page.getByText(/^You have answered every fresh question/)).toBeVisible()

  await page.getByRole('link', { name: 'Back to your report' }).click()
  await expect(page.getByText('Ready for the lecture', { exact: true })).toBeVisible()
  await expect(row(page, missed)).toContainText('Met independently')
  await expect(row(page, missed)).toContainText('after the review path')
})
