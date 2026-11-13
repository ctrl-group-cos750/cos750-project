import { activities, activity, demoAccounts, wrongOption } from './content'
import { answerActivity, segmentRegion, walkModule } from './drive'
import { DEMO_PASSWORD } from './env'
import { expect, newAccount, PASSWORD, test } from './fixtures'
import { logIn, register } from './helpers'

// The student's path (FR-1, FR-2, FR-5; SE document §14.1). Questions and answers come from the
// fixtures (content.ts), so content changes don't break these tests.

test('a new student registers, logs out and back in', async ({ page }, testInfo) => {
  const account = newAccount(testInfo.project.name)
  // A visitor at / sees the landing page, with the way in (#landing).
  await page.goto('/')
  await expect(
    page.getByRole('heading', {
      level: 1,
      name: /Learn graphs and breadth-first search/,
    }),
  ).toBeVisible()
  await page.getByRole('link', { name: 'Sign up' }).click()
  await expect(page).toHaveURL(/\/register$/)
  await register(page, account)

  // The module map: module 0 is where a new student starts (FR-2.1, FR-2.6).
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByRole('button', { name: /^(Start|Continue) module 0/ })).toBeVisible()

  await page.getByRole('button', { name: account.displayName }).click()
  await page.getByRole('button', { name: 'Log out' }).click()
  await expect(page).toHaveURL(/\/login$/)
  await page.goto('/report')
  await expect(page).toHaveURL(/\/login/)

  // Logging in on the page it sent them to takes them back to the page they asked for.
  await page.getByRole('textbox', { name: 'Email' }).fill(account.email)
  await page.getByRole('textbox', { name: 'Password' }).fill(PASSWORD)
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page).toHaveURL(/\/report$/)
  await expect(page.getByRole('heading', { name: 'Your mastery report' })).toBeVisible()
})

test('registering is refused, with the reason beside the field, for a password that breaks the rules', async ({
  page,
}, testInfo) => {
  const { email, displayName } = newAccount(testInfo.project.name)
  await page.goto('/register')
  await page.getByRole('textbox', { name: 'Your name' }).fill(displayName)
  await page.getByRole('textbox', { name: 'Email' }).fill(email)
  const password = page.getByRole('textbox', { name: 'Password' })
  await password.fill('short')
  await expect(password).not.toHaveAttribute('aria-invalid', 'true')
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(password).toHaveAttribute('aria-invalid', 'true')
  await expect(page).toHaveURL(/\/register$/)
})

test('a wrong password is refused with a message', async ({ page }) => {
  await page.goto('/login')
  await page.getByRole('textbox', { name: 'Email' }).fill(`${demoAccounts[0].key}@demo.example.com`)
  await page.getByRole('textbox', { name: 'Password' }).fill('Not-the-password-1')
  const refused = page.getByRole('group', {
    name: 'Email or password is incorrect.',
  })
  await expect(refused).toHaveCount(0)
  await page.getByRole('button', { name: 'Log in' }).click()
  // The message takes focus, so it is read and keyboard focus isn't lost (A7).
  await expect(refused).toBeFocused()
  await expect(page).toHaveURL(/\/login$/)
})

// Each demo account through the login form, where its stage shows (FR-1.4). Only looked at.
test('every demo account logs in and its report shows its stage', async ({ page }) => {
  expect(demoAccounts.length, 'the fixtures have demo accounts').toBeGreaterThan(0)
  for (const demo of demoAccounts) {
    await test.step(demo.key, async () => {
      await page.context().clearCookies()
      await logIn(page, `${demo.key}@demo.example.com`, DEMO_PASSWORD)
      await expect(page.getByRole('button', { name: demo.display_name })).toBeVisible()
      await page.getByRole('button', { name: /your account/ }).click()
      await page.getByRole('link', { name: 'Mastery report' }).click()
      await expect(page.getByRole('heading', { name: 'Your mastery report' })).toBeVisible()
      if (demo.expect.ready)
        await expect(page.getByText('Ready for the lecture', { exact: true })).toBeVisible()
      else await expect(page.getByText(/^Not ready yet/)).toBeVisible()
      for (const objective of demo.expect.not_yet ?? [])
        await expect(
          page.getByRole('link', {
            name: new RegExp(`^Start review path\\W+objective ${objective}$`),
          }),
        ).toBeVisible()
    })
  }
})

test('module 0 on screen, from the map to "Finish module"; then module 1 opens', async ({
  page,
  course,
}) => {
  const module = await course.module(0)
  await page.getByRole('button', { name: /^(Start|Continue) module 0/ }).click()
  await expect(
    page.getByRole('heading', { level: 1, name: new RegExp(module.title) }),
  ).toBeVisible()
  await walkModule(page, module)

  // Back on the map: module 0 is complete and module 1 is open (FR-2.1, FR-2.6).
  const modules = await course.modules()
  expect(modules.find((m) => m.number === 0)?.status).toBe('complete')
  expect(modules.find((m) => m.number === 1)?.status).toBe('open')
  await expect(page.getByRole('button', { name: /^(Start|Continue) module 1/ })).toBeVisible()
})

// Code submissions (FR-5: ordering and completing code). Module 4 builds BFS with a Parsons
// problem and fill-in code; the student gets there through modules 0 to 3 (through the API),
// then works through module 4 on screen. The first code activity is answered wrong first: the
// feedback says so and Next stays blocked (FR-2.7), then right.
// A second wrong answer lets the student move on without it (#214): the next test.
const CODE_KINDS = new Set(['parsons', 'fill_in'])

test('module 4: a code activity answered wrong, then right, then the rest of the module', async ({
  page,
  course,
}) => {
  test.slow() // modules 0 to 3 first
  await course.completeBefore(4)
  const module = await course.module(4)
  const index = module.segments.findIndex(
    (s) =>
      s.shown !== false && s.activityId !== null && CODE_KINDS.has(activity(s.activityId).kind),
  )
  expect(index, 'module 4 has a Parsons or fill-in activity').toBeGreaterThanOrEqual(0)
  await course.walk(4, index)
  await course.roomFor(module.segments.length)

  // The module opens at the code activity, the furthest segment reached (FR-2.5).
  await page.goto(`/modules/${module.id}`)
  const segment = module.segments[index]
  const region = segmentRegion(page, segment.title)
  const a = activity(segment.activityId ?? 0)
  const next = page.getByRole('navigation', { name: 'Step navigation' }).getByRole('button', {
    name: /^Next/,
  })
  const blocked = page.locator('#segment-blocked')
  await expect(blocked).toHaveText(/^Answer the activity to continue/)
  await answerActivity(page, region, a, 'wrong')
  // A practice activity is done once it is right, answered after its last hint (FR-2.7, #165), or
  // answered twice (#214). After one wrong answer the module, fetched again, says try again.
  await expect(blocked).toHaveText(/^Not yet right\. Try again/)
  await expect(next).toHaveAttribute('aria-disabled', 'true')

  // Then right: for Parsons, with the arrow keys (NFR-A1).
  await page.reload()
  await answerActivity(page, segmentRegion(page, segment.title), a, 'right')
  await expect(blocked).toBeEmpty()
  await expect(next).not.toHaveAttribute('aria-disabled', 'true')

  // The rest of module 4, on screen, to "Finish module".
  await walkModule(page, await course.module(4))
  expect((await course.modules()).find((m) => m.number === 4)?.status).toBe('complete')
})

// Moving on after two tries (FR-2.7, #214): a student isn't held on one question until it is
// right or every hint is open. The activity is marked to look at again and earns nothing.
test('module 1: two wrong answers and the student may move on, marked to look at again', async ({
  page,
  course,
}) => {
  await course.completeBefore(1)
  const module = await course.module(1)
  const index = module.segments.findIndex(
    (s) =>
      s.shown !== false &&
      s.activityId !== null &&
      activity(s.activityId).kind === 'multiple_choice' &&
      activity(s.activityId).purpose === 'practice',
  )
  await course.walk(1, index)
  await page.goto(`/modules/${module.id}`)
  const segment = module.segments[index]
  const a = activity(segment.activityId ?? 0)
  const next = page.getByRole('navigation', { name: 'Step navigation' }).getByRole('button', {
    name: /^Next/,
  })
  const status = page.locator('#segment-blocked')
  const points = async () =>
    page.evaluate(async () => (await (await fetch('/api/rewards')).json()).points as number)
  const before = await points()
  await answerActivity(page, segmentRegion(page, segment.title), a, 'wrong')
  await expect(status).toHaveText(/^Not yet right/)
  await expect(next).toHaveAttribute('aria-disabled', 'true')
  await page.reload()
  await answerActivity(page, segmentRegion(page, segment.title), a, 'wrong')
  await expect(status).toHaveText(
    'You can move on: this one is marked to look at again. It earns no points now that the first answer was wrong, but answer it right later and it counts towards your medal.',
  )
  await expect(next).not.toHaveAttribute('aria-disabled', 'true')
  await next.click()
  // Steps count only the segments shown: support the student isn't shown comes before this one
  // now that module 1's opening puzzle is a diagnostic item, not practice.
  const shown = module.segments.filter((s) => s.shown !== false).map((s) => s.id)
  await expect(page.getByText(`Step ${shown.indexOf(segment.id) + 2} of`)).toBeVisible()
  // Moving on earns nothing: the activity is still not right.
  expect(await points()).toBe(before)
  // It is listed to look at again, and the link opens it (#215 review).
  const progress = page.locator('details', { hasText: '1 to look at again' })
  const beside = page.getByRole('complementary', { name: 'Your progress' })
  const panel = (await beside.isVisible()) ? beside : progress
  if (panel === progress) await progress.locator('summary').click()
  await panel.getByRole('link', { name: segment.title }).click()
  await expect(page).toHaveURL(new RegExp(`/modules/${module.id}\\?segment=${index}$`))
  await expect(page.getByRole('heading', { level: 2, name: segment.title })).toBeFocused()
  await page.goto('/')
  await expect(page.getByText('1 marked to look at again')).toBeVisible()
})

// Learner choice (#214): a new student starts where they choose. Module 3 is open from the
// start, and its quick check lets a student who knows it test out of it.
test('a new student tests out of module 3 with its quick check, from the map', async ({
  page,
  student,
}) => {
  void student
  await page.goto('/')
  await expect(page.getByText('recommended next')).toBeVisible()
  await page.getByRole('link', { name: 'Already know module 3? Take the quick check' }).click()
  await expect(page).toHaveURL(/\/modules\/3\/check$/)
  const questions = [...activities.values()]
    .filter((a) => a.purpose === 'test_out' && a.module_id === 3)
    .sort((x, y) => x.id - y.id)
  expect(questions).toHaveLength(4)
  for (const [index, q] of questions.entries()) {
    if (q.kind !== 'multiple_choice')
      throw new Error(`quick check item ${q.id} isn't multiple choice`)
    const fieldset = page.getByRole('group', {
      name: new RegExp(`^Question ${index + 1} of 4`),
    })
    // The last one wrong: all but one right still passes.
    const id = index === 3 ? wrongOption(q) : q.solution.correct
    const label = q.config.options.find((o) => o.id === id)?.label ?? ''
    await fieldset.getByRole('radio', { name: label, exact: true }).check()
  }
  await page.getByRole('button', { name: 'Check my answers' }).click()
  await expect(page.getByRole('heading', { name: /quick check, 3 of 4 right$/ })).toBeVisible()
  await expect(page.getByText('You know this already')).toBeVisible()
  await page.getByRole('link', { name: /^Go to module 4/ }).click()
  await expect(page).toHaveURL(/\/modules\/4$/)
  await page.goto('/')
  const card = page.getByRole('link', { name: /Meet BFS/ })
  await expect(card).toContainText('passed the quick check')
  await expect(page.getByText('Already know module 3?')).toHaveCount(0)
  // The result stays one link away (#215 review).
  await expect(
    page.getByRole('link', {
      name: /Quick check: 3 of 4, see the results for module 3/,
    }),
  ).toHaveAttribute('href', '/modules/3/check')
})

// The progress panel beside a lesson fits a 1366 × 900 laptop screen: "See your badges" isn't cut
// off at its foot (#215 review).
test.describe('the progress panel on a laptop', () => {
  test.use({ viewport: { width: 1366, height: 900 } })

  test('fits a 1366 × 900 screen with its badges link in view', async ({ page }) => {
    await logIn(page, 'mid@demo.example.com', DEMO_PASSWORD)
    await page.goto('/modules/3')
    const panel = page.getByRole('complementary', { name: 'Your progress' })
    const link = panel.getByRole('link', { name: 'See your badges' })
    await expect(link).toBeVisible()
    const fit = await panel.evaluate((el) => ({ overflow: el.scrollHeight - el.clientHeight }))
    expect(fit.overflow, 'the panel scrolls inside itself').toBeLessThanOrEqual(1)
    const box = await link.boundingBox()
    const area = await panel.boundingBox()
    expect((box?.y ?? 0) + (box?.height ?? 0)).toBeLessThanOrEqual(
      (area?.y ?? 0) + (area?.height ?? 0),
    )
  })
})
