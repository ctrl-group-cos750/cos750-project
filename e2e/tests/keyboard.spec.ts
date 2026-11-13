import { activity, wrongOption, type ActivityOf } from './content'
import { result, segmentRegion } from './drive'
import { expect, shownPositions, test } from './fixtures'
import { chooseRadio, expectVisibleFocus, press, tabTo } from './helpers'

// NFR-A1 (issue #35: "one module completed with the keyboard only"; SE document §14.1): module 0
// from the map to "Finish module". Nothing here clicks: Tab, Shift+Tab, Enter, Space and the
// arrow keys. Only buttons and form controls are needed, so it runs in WebKit too, which (like
// Safari) skips links on Tab unless the user turns that on. The first diagnostic is answered
// wrong first, with a hint, as a student who doesn't know yet would; the rest right. Questions
// and answers come from the fixtures (module-0.json), so a content change can't break it.

test('module 0, from the map to "Finish module", with the keyboard only', async ({
  page,
  course,
}) => {
  const module = await course.module(0)
  await page.goto('/')
  await press(page, page.getByRole('button', { name: /^(Start|Continue) module 0/ }))
  await expect(
    page.getByRole('heading', { level: 1, name: new RegExp(module.title) }),
  ).toBeVisible()

  let firstActivity = true
  // The segments the student is shown (#172), as "Segment N of M" counts them.
  const segments = shownPositions(module).map((i) => module.segments[i])
  for (const [i, segment] of segments.entries()) {
    await expect(page.getByText(`Step ${i + 1} of ${segments.length}`)).toBeVisible()
    const region = segmentRegion(page, segment.title)
    await expect(region).toBeVisible()
    if (segment.kind === 'activity' && segment.activityId !== null) {
      const a = activity(segment.activityId)
      expect(a.kind, 'module 0 asks multiple-choice diagnostics').toBe('multiple_choice')
      const mc = a as ActivityOf<'multiple_choice'>
      const label = (id: string) => mc.config.options.find((o) => o.id === id)?.label ?? ''
      const radios = region.getByRole('radio')
      const checkAnswer = region.getByRole('button', { name: 'Check answer' })
      if (firstActivity) {
        firstActivity = false
        await chooseRadio(page, radios, label(wrongOption(mc)))
        await press(page, checkAnswer)
        await expect(result(region)).toContainText('Not quite')
        await press(page, region.getByRole('button', { name: 'Show next hint' }))
        await expect(region.getByText('Hint 1', { exact: true })).toBeVisible()
      }
      await chooseRadio(page, radios, label(mc.solution.correct))
      await press(page, checkAnswer)
      await expect(result(region)).toContainText('Correct')
    }
    const last = i === segments.length - 1
    const next = page.getByRole('button', { name: last ? 'Finish module' : /^Next/ })
    // Blocked until the module, fetched again after the answer, says the segment is done.
    await expect(next).not.toHaveAttribute('aria-disabled', 'true')
    await press(page, next)
  }

  // Back on the map: module 0 is complete and module 1 is open (FR-2.1, FR-2.6).
  await expect(page).toHaveURL(/\/$/)
  const modules = await course.modules()
  expect(modules.find((m) => m.number === 0)?.status).toBe('complete')
  expect(modules.find((m) => m.number === 1)?.status).toBe('open')
  await expect(page.getByRole('button', { name: /^(Start|Continue) module 1/ })).toBeVisible()
})

// WCAG 2.4.7: every control a keyboard user reaches in a module shows where focus is.
test('every control in a module activity shows a visible focus indicator', async ({
  page,
  course,
}) => {
  const module = await course.module(0)
  const index = module.segments.findIndex((s) => s.kind === 'activity' && s.shown !== false)
  await course.walk(0, index)
  await page.goto(`/modules/${module.id}`)
  const region = segmentRegion(page, module.segments[index].title)
  const mc = activity(module.segments[index].activityId ?? 0) as ActivityOf<'multiple_choice'>
  await chooseRadio(page, region.getByRole('radio'), mc.config.options[0].label)
  await expectVisibleFocus(region.getByRole('radio').first(), 'the first option')
  const controls = [
    region.getByRole('button', { name: 'Check answer' }),
    region.getByRole('button', { name: 'Show next hint' }),
    page.getByRole('button', { name: /Previous/ }),
    page.getByRole('button', { name: /^Next/ }),
  ]
  for (const control of controls) {
    await tabTo(page, control)
    await expectVisibleFocus(control, (await control.textContent()) ?? '')
  }
})

// WCAG 2.2 2.4.11 Focus Not Obscured: the sticky header covered the skip link on every signed-in
// page, and Shift+Tab from the bottom of a page left controls under the header (review of 13 Nov;
// #223 review, Should fix 7). The page's scrolling is padded by the header's height (base.css).
test('the sticky header never hides the focused control', async ({ page, course }) => {
  void course // a signed-in student, on the module map
  await page.setViewportSize({ width: 375, height: 667 })
  await page.goto('/')
  await expect(page.getByRole('button', { name: /^(Start|Continue) module 0/ })).toBeVisible()

  await page.keyboard.press('Tab')
  const skip = page.getByRole('link', { name: 'Skip to content' })
  await expect(skip).toBeFocused()
  const onTop = await skip.evaluate((el) => {
    const r = el.getBoundingClientRect()
    const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2)
    return !!hit && el.contains(hit)
  })
  expect(onTop, 'the skip link is drawn above the header').toBe(true)

  // From the bottom of the page, back up through it with Shift+Tab.
  await page.locator('body').evaluate((el) => (el as HTMLElement).focus())
  await page.keyboard.press('End')
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(0)
  const hidden: string[] = []
  for (let i = 0; i < 20; i++) {
    await page.keyboard.press('Shift+Tab')
    const covered = await page.evaluate(() => {
      const el = document.activeElement
      const header = document.querySelector('header')
      if (!el || el === document.body || !header || header.contains(el)) return null
      const r = el.getBoundingClientRect()
      const h = header.getBoundingClientRect()
      return r.top < h.bottom - 1 ? (el.textContent ?? el.tagName).trim().slice(0, 60) : null
    })
    if (covered !== null) hidden.push(covered)
  }
  expect(hidden, 'controls under the sticky header').toEqual([])
})
