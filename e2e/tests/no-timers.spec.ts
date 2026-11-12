import { activity, firstOfKind, type Kind } from './content'
import { answerActivity, segmentRegion } from './drive'
import { CHECKPOINT, createVideo, expect, seekPastCheckpoint, test, type Page } from './fixtures'
import type { Locator } from '@playwright/test'

// No timers on any activity, checkpoint or the mastery check (ID document §6.2; WCAG 2.2.1).
// The page's clock jumps two hours while a question is open: nothing counts down, nothing
// closes, and the answer is still taken. The mastery check is covered item by item in
// mastery.spec.ts, which does the same before every mastery item.

const TIMER_TEXT = /time('s| is) up|timed out|time (left|remaining)|seconds? left|expired/i
/** Anything that reads like a clock or a countdown: 1:30, 00:59. */
const CLOCK_TEXT = /\b\d{1,2}:\d{2}\b/g

/** Runs `wait` (the clock jump) with the question open, and fails if anything that looks like a
 * timer is there, or if any clock-like text in `scope` changed while the clock moved. */
async function expectNoTimerAcross(page: Page, scope: Locator, wait: () => Promise<void>) {
  const clocks = async () => ((await scope.innerText()).match(CLOCK_TEXT) ?? []).join(' ')
  const before = await clocks()
  await wait()
  await expect(page.getByRole('timer')).toHaveCount(0)
  await expect(page.getByText(TIMER_TEXT)).toHaveCount(0)
  expect(await clocks(), 'no clock or countdown changed while the question was open').toBe(before)
}

test('a video checkpoint left open for two hours still takes an answer', async ({
  page,
  student,
  staff,
}, testInfo) => {
  void student
  const videoId = await createVideo(staff, `E2E: ${testInfo.title}`)
  await page.clock.install()
  await page.goto(`/videos/${videoId}`)
  await seekPastCheckpoint(page)
  const checkpoint = page.getByRole('region', { name: 'Checkpoint' })
  await expect(checkpoint.getByRole('button', { name: 'Check answer' })).toBeVisible()
  await expectNoTimerAcross(page, checkpoint, () => page.clock.fastForward('02:00:00'))
  const right = CHECKPOINT.question.options.find((o) => o.id === CHECKPOINT.question.correct)
  await checkpoint.getByRole('radio', { name: right?.label }).check()
  await checkpoint.getByRole('button', { name: 'Check answer' }).click()
  await expect(checkpoint.getByText('Correct', { exact: true })).toBeVisible()
})

test('a module activity left open for two hours still takes an answer', async ({
  page,
  course,
}) => {
  const module = await course.module(0)
  const index = module.segments.findIndex((s) => s.kind === 'activity' && s.shown !== false)
  await course.walk(0, index)
  await page.clock.install()
  await page.goto(`/modules/${module.id}`)
  const segment = module.segments[index]
  const region = segmentRegion(page, segment.title)
  // The activity is on screen before the clock moves, not still loading.
  await expect(region.getByRole('button', { name: 'Check answer' })).toBeVisible()
  await expectNoTimerAcross(page, page.getByRole('main'), () => page.clock.fastForward('02:00:00'))
  await answerActivity(page, region, activity(segment.activityId ?? 0), 'right')
})

// Every kind of activity, on its own page, the first of its kind a student meets: left open,
// then answered.
const kinds: Kind[] = [
  'multiple_choice',
  'matching',
  'fill_in',
  'parsons',
  'trace',
  'fix_the_bug',
  'choose_tests',
]
for (const kind of kinds) {
  test(`a ${kind} activity left open for two hours still takes an answer`, async ({
    page,
    course,
  }) => {
    const a = firstOfKind(kind)
    await course.openModuleOf(a)
    await page.clock.install()
    await page.goto(`/activities/${a.id}`)
    await expect(page.getByRole('heading', { level: 1, name: a.title })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Check answer' })).toBeVisible()
    await expectNoTimerAcross(page, page.getByRole('main'), () =>
      page.clock.fastForward('02:00:00'),
    )
    await answerActivity(page, page.getByRole('main'), a, 'right')
  })
}
