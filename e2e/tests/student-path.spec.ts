import { activity, demoAccounts } from './content'
import { answerActivity, segmentRegion, walkModule } from './drive'
import { DEMO_PASSWORD } from './env'
import { expect, newAccount, PASSWORD, test } from './fixtures'
import { logIn, register } from './helpers'

// The student's path (FR-1, FR-2, FR-5; SE document §14.1). Questions and answers come from the
// fixtures (content.ts), so content changes don't break these tests.

test('a new student registers, logs out and back in', async ({ page }, testInfo) => {
  const account = newAccount(testInfo.project.name)
  await page.goto('/')
  await expect(page).toHaveURL(/\/login$/)
  await page.getByRole('link', { name: 'Create an account' }).click()
  await register(page, account)

  // The module map: module 0 is where a new student starts (FR-2.1, FR-2.6).
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByRole('button', { name: /^Continue module 0/ })).toBeVisible()

  await page.getByRole('button', { name: account.displayName }).click()
  await page.getByRole('button', { name: 'Log out' }).click()
  await expect(page).toHaveURL(/\/login$/)
  await page.goto('/report')
  await expect(page).toHaveURL(/\/login/)

  await logIn(page, account.email, PASSWORD)
  await expect(page.getByRole('button', { name: /^Continue module 0/ })).toBeVisible()
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
  await expect(page.getByRole('alert')).toHaveCount(0)
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page.getByRole('alert')).toBeVisible()
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
      await page.getByRole('link', { name: 'Report', exact: true }).click()
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
  await page.getByRole('button', { name: /^Continue module 0/ }).click()
  await expect(page.getByRole('heading', { level: 1, name: new RegExp(module.title) })).toBeVisible()
  await walkModule(page, module)

  // Back on the map: module 0 is complete and module 1 is open (FR-2.1, FR-2.6).
  const modules = await course.modules()
  expect(modules.find((m) => m.number === 0)?.status).toBe('complete')
  expect(modules.find((m) => m.number === 1)?.status).toBe('open')
  await expect(page.getByRole('button', { name: /^Continue module 1/ })).toBeVisible()
})

// Code submissions (FR-5: ordering and completing code). Module 4 builds BFS with a Parsons
// problem and fill-in code; the student gets there through modules 0 to 3 (through the API),
// then works through module 4 on screen. The first code activity is answered wrong first: the
// feedback says so and Next stays blocked (FR-2.7), then right.
const CODE_KINDS = new Set(['parsons', 'fill_in'])

test('module 4: a code activity answered wrong, then right, then the rest of the module', async ({
  page,
  course,
}) => {
  test.slow() // modules 0 to 3 first
  await course.completeBefore(4)
  const module = await course.module(4)
  const index = module.segments.findIndex(
    (s) => s.activityId !== null && CODE_KINDS.has(activity(s.activityId).kind),
  )
  expect(index, 'module 4 has a Parsons or fill-in activity').toBeGreaterThanOrEqual(0)
  await course.walk(4, index)
  await course.roomFor(module.segments.length)

  // The module opens at the code activity, the furthest segment reached (FR-2.5).
  await page.goto(`/modules/${module.id}`)
  const segment = module.segments[index]
  const region = segmentRegion(page, segment.title)
  const a = activity(segment.activityId ?? 0)
  const next = page.getByRole('navigation', { name: 'Segment navigation' }).getByRole('button', {
    name: /^Next/,
  })
  const blocked = page.locator('#segment-blocked')
  await expect(blocked).toHaveText(/^Answer the activity to continue/)
  await answerActivity(page, region, a, 'wrong')
  // A practice activity is done only once it is right, or answered after its last hint (FR-2.7,
  // #165). Not true before the answer: the module, fetched again, now knows it was attempted.
  await expect(blocked).toHaveText(/^Get it right to continue/)
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
