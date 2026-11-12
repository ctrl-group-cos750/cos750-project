import { readFileSync } from 'node:fs'
import { demoAccounts, firstOfKind, type Kind } from './content'
import { answerActivity, walkModule } from './drive'
import { DEMO_PASSWORD, PASSWORD, STAFF_FILE } from './env'
import {
  CHECKPOINT,
  clientAddress,
  createVideo,
  expect,
  expectNoViolations,
  newAccount,
  seekPastCheckpoint,
  test,
  type Page,
} from './fixtures'
import { logIn } from './helpers'

// axe-core finds no WCAG 2.1 A or AA violation (NFR-A2, NFR-A3; SE document §14.1) on any page,
// in each state that changes what is on screen (an answer's feedback, hints, the warning before
// hint 3), in the light and the dark theme (the app follows the system's). A new page belongs
// here. Every test registers its own student or only looks at a demo account, so nothing here
// changes what another test sees.

const graphs = JSON.parse(
  readFileSync(new URL('../../api/app/seed/graphs.json', import.meta.url), 'utf8'),
) as { graphs: { id: number }[] }

/** Open a page and wait until it has its data: nothing is still being fetched, and a heading is
 * there (the main one, unless the page has none). */
async function open(page: Page, path: string, heading = page.getByRole('heading', { level: 1 })) {
  await page.goto(path)
  await page.waitForLoadState('networkidle')
  await expect(heading.first()).toBeVisible()
}

async function check(page: Page, path: string) {
  await open(page, path)
  await expectNoViolations(page, path)
}

const KINDS: Kind[] = [
  'multiple_choice',
  'matching',
  'fill_in',
  'parsons',
  'trace',
  'fix_the_bug',
  'choose_tests',
]

const STAFF_PAGES = [
  '/staff',
  '/staff/videos',
  '/staff/videos/import',
  '/staff/content',
  '/staff/content/modules/1',
  '/staff/content/review-paths/1',
  `/staff/content/activities/${firstOfKind('parsons').id}`,
  '/staff/content/objectives/1',
  `/staff/content/graphs/${graphs.graphs[0].id}`,
  '/staff/accounts',
  '/staff/pilot',
  '/staff/members',
]

for (const colorScheme of ['light', 'dark'] as const) {
  test.describe(`${colorScheme} theme`, () => {
    test.use({ colorScheme })

    test('pages before logging in, and the register errors', async ({ page }) => {
      for (const path of ['/login', '/register']) {
        await test.step(path, () => check(page, path))
      }
      const password = page.getByRole('textbox', { name: 'Password' })
      await expect(password).not.toHaveAttribute('aria-invalid', 'true')
      await page.getByRole('button', { name: 'Create account' }).click()
      await expect(password).toHaveAttribute('aria-invalid', 'true')
      await expectNoViolations(page, '/register with its errors showing')
    })

    test('a new student: the map, a locked module, the report, module 0, badges, profile, a missing page', async ({
      page,
      course,
    }) => {
      const modules = await course.modules()
      const locked = modules.find((m) => m.status === 'locked')
      expect(locked, 'a new student has a locked module').toBeDefined()
      for (const path of [
        '/',
        `/modules/${locked?.id}`,
        '/report',
        `/modules/${modules[0].id}`,
        '/badges',
        '/profile',
        `/graphs/${graphs.graphs[0].id}`, // the BFS visualiser
      ]) {
        await test.step(path, () => check(page, path))
      }
      await page.goto('/no-such-page')
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
      await expectNoViolations(page, 'a page that does not exist')
    })

    test('modules 1 and 2: every segment, answered', async ({ page, course }) => {
      test.slow()
      await course.completeBefore(1)
      for (const number of [1, 2]) {
        const module = await course.module(number)
        await course.roomFor(module.segments.length + module.retrieval.length)
        await walkModule(page, module, { onSegment: (label) => expectNoViolations(page, label) })
      }
    })

    for (const kind of KINDS) {
      test(`a ${kind} activity: unanswered, with hints, answered wrong, then right`, async ({
        page,
        course,
      }) => {
        const a = firstOfKind(kind)
        await course.openModuleOf(a)
        const main = page.getByRole('main')
        const nextHint = main.getByRole('button', { name: 'Show next hint' })
        await check(page, `/activities/${a.id}`)
        // Each hint is on screen before the next is asked for.
        await expect(main.getByText('Hint 1', { exact: true })).toHaveCount(0)
        if (a.purpose === 'mastery') {
          // Some kinds are only in the mastery check: two hints at most, and one answer, which
          // only says it was recorded (#144).
          await nextHint.click()
          await expect(main.getByText('Hint 1', { exact: true })).toBeVisible()
          await nextHint.click()
          await expect(main.getByText('Hint 2', { exact: true })).toBeVisible()
          await expectNoViolations(page, `${kind} (mastery), two hints`)
          await answerActivity(page, main, a, 'wrong')
          await expectNoViolations(page, `${kind} (mastery), answered`)
          return
        }
        await answerActivity(page, main, a, 'wrong')
        await nextHint.click()
        await expect(main.getByText('Hint 1', { exact: true })).toBeVisible()
        await nextHint.click()
        await expect(main.getByText('Hint 2', { exact: true })).toBeVisible()
        await nextHint.click()
        await expect(main.getByText('The next hint gives a lot away')).toBeVisible()
        await expectNoViolations(page, `${kind}, wrong, two hints and the warning`)
        await page.reload()
        await answerActivity(page, main, a, 'right')
        await expectNoViolations(page, `${kind}, right`)
      })
    }

    test('a video, then its checkpoint with feedback and every hint', async ({
      page,
      student,
      staff,
    }, testInfo) => {
      void student
      const videoId = await createVideo(staff, `E2E: ${testInfo.title}`)
      // The video page has no h1 of its own; its Transcript heading shows it has loaded.
      await open(page, `/videos/${videoId}`, page.getByRole('heading', { name: 'Transcript' }))
      await expectNoViolations(page, 'the video page')
      await seekPastCheckpoint(page)
      await expectNoViolations(page, 'its checkpoint')
      const checkpoint = page.getByRole('region', { name: 'Checkpoint' })
      await checkpoint.getByRole('radio').last().check()
      await checkpoint.getByRole('button', { name: 'Check answer' }).click()
      await expect(checkpoint.getByText('Not quite')).toBeVisible()
      // Hint 1, 2, the warning, then 3 and 4: each on screen before the next is asked for.
      const nextHint = checkpoint.getByRole('button', { name: 'Show next hint' })
      const [h1, h2, h3, h4] = CHECKPOINT.hints.map((h) => h.body)
      for (const shows of [h1, h2, 'The next hint gives a lot away', h3, h4]) {
        await expect(checkpoint.getByText(shows)).toHaveCount(0)
        await nextHint.click()
        await expect(checkpoint.getByText(shows)).toBeVisible()
      }
      await expect(nextHint).toHaveCount(0)
      await expectNoViolations(page, 'the checkpoint with feedback and every hint')
    })

    test('the demo accounts: the report, the review paths and badges', async ({ page }) => {
      const shown = demoAccounts.filter((d) => d.expect.ready || d.expect.not_yet?.length)
      expect(shown.length, 'a ready and a not-yet demo account').toBeGreaterThanOrEqual(2)
      for (const demo of shown) {
        await test.step(demo.key, async () => {
          await page.context().clearCookies()
          await logIn(page, `${demo.key}@demo.example.com`, DEMO_PASSWORD)
          await check(page, '/report')
          for (const objective of demo.expect.not_yet ?? [])
            await check(page, `/review/${objective}`)
          await check(page, '/badges')
        })
      }
    })

    test('the staff portal, a video in the editor, and an account', async ({
      page,
      staff,
      playwright,
      baseURL,
    }, testInfo) => {
      test.slow() // a dozen pages
      // A second team member, so the members page shows a "Remove access" button.
      const other = await playwright.request.newContext({
        baseURL,
        ignoreHTTPSErrors: true,
        extraHTTPHeaders: { 'X-Forwarded-For': clientAddress() },
      })
      const member = newAccount('member')
      const res = await other.post('/api/auth/register', {
        data: { ...member, password: PASSWORD },
      })
      expect(res.status(), await res.text()).toBe(201)
      await other.dispose()
      const added = await staff.post('/api/staff/members', { data: { email: member.email } })
      expect(added.ok(), await added.text()).toBe(true)
      const videoId = await createVideo(staff, `E2E: ${testInfo.title}`)

      const account = JSON.parse(readFileSync(STAFF_FILE, 'utf8')) as { email: string }
      await logIn(page, account.email, PASSWORD)
      for (const path of [...STAFF_PAGES, `/staff/videos/${videoId}`]) {
        await test.step(path, async () => {
          if (path === '/staff/members') {
            await open(page, path)
            await expect(
              page
                .getByRole('main')
                .getByRole('button', { name: /Remove/ })
                .first(),
            ).toBeVisible()
            await expectNoViolations(page, path)
          } else await check(page, path)
        })
      }
      await open(page, '/staff/accounts')
      await page.locator('main a[href^="/staff/accounts/"]').first().click()
      await expect(page).toHaveURL(/\/staff\/accounts\/\d+$/)
      await page.waitForLoadState('networkidle')
      await expectNoViolations(page, '/staff/accounts/:id')
    })
  })
}
