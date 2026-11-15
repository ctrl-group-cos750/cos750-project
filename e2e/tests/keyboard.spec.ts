import { activity, wrongOption, type ActivityOf } from './content'
import { result, segmentRegion } from './drive'
import { expect, moduleNow, shownPositions, test } from './fixtures'
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
  // The segments the student is shown (#172), as "Step N of M" counts them. A right first answer
  // to a warm-up question skips the refresher after it (#224), so the module is read again after
  // each answer, and the walk goes on to the next segment shown now.
  let current = await moduleNow(page, module.id)
  let from = current.currentSegmentPosition
  for (;;) {
    const shown = shownPositions(current)
    const i = shown.findIndex((p) => p >= from)
    if (i === -1) break
    const segment = current.segments[shown[i]]
    await expect(page.getByText(`Step ${i + 1} of ${shown.length}`)).toBeVisible()
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
    current = await moduleNow(page, module.id)
    const after = shownPositions(current)
    const last = after[after.length - 1] === shown[i]
    const next = page.getByRole('button', { name: last ? 'Finish module' : /^Next/ })
    // Blocked until the module, fetched again after the answer, says the segment is done.
    await expect(next).not.toHaveAttribute('aria-disabled', 'true')
    await press(page, next)
    if (last) break
    from = shown[i] + 1
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
  // The element drawn at the link's centre is the link, not the header painted over it.
  await expect
    .poll(
      () =>
        skip.evaluate((el) => {
          const r = el.getBoundingClientRect()
          const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2)
          return !!hit && el.contains(hit)
        }),
      { message: 'the skip link is drawn above the header' },
    )
    .toBe(true)

  // From the bottom of the page, back up through it with Shift+Tab, once the map has loaded
  // everything (the quick check links come in later and move the cards down).
  await page.waitForLoadState('networkidle')
  await expect(page.getByRole('link', { name: /Already know module 1\?/ })).toBeVisible()
  // Straight to the bottom, on the page's last control: the End key scrolls smoothly in Chromium,
  // and a scroll still under way carried on past the control Shift+Tab had just scrolled to; and
  // Shift+Tab from the page itself starts at the top in Firefox.
  await page.evaluate(() => {
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'instant' })
    const controls = document.querySelectorAll<HTMLElement>('main a[href], main button')
    controls[controls.length - 1]?.focus({ preventScroll: true })
  })
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeGreaterThan(0)
  const hidden: string[] = []
  // What the focused control is, if the header covers half of it or more. 2.4.11 (Minimum) fails
  // only when all of it is covered; without scroll-padding-top the map's cards end up more than
  // half under it, and Firefox, which scrolls only a control out of view, can leave a little.
  const covered = () =>
    page.evaluate(() => {
      const el = document.activeElement
      const header = document.querySelector('header')
      if (!el || el === document.body || !header || el.closest('header, a[href="#main"]'))
        return null
      const r = el.getBoundingClientRect()
      const h = header.getBoundingClientRect()
      return r.top + r.height / 2 >= h.bottom
        ? null
        : (el.textContent ?? el.tagName).trim().slice(0, 60)
    })
  // Up the page to the header: past it, Shift+Tab leaves the page.
  const inHeader = () =>
    page.evaluate(() => {
      const el = document.activeElement
      return !!el && !!el.closest('header, a[href="#main"]')
    })
  for (let i = 0; i < 40 && !(await inHeader()); i++) {
    await page.keyboard.press('Shift+Tab')
    const still = await covered()
    if (still !== null) hidden.push(still)
  }
  expect(await inHeader(), 'Shift+Tab reached the header').toBe(true)
  expect(hidden, 'controls under the sticky header').toEqual([])
})
