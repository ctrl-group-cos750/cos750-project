import { randomInt, randomUUID } from 'node:crypto'
import { readFileSync } from 'node:fs'
import AxeBuilder from '@axe-core/playwright'
import { expect, test as base, type APIRequestContext, type Page } from '@playwright/test'
import { activity, moduleOf, rightSubmission, type Activity } from './content'
import { PASSWORD, STAFF_STATE } from './env'
import { register } from './helpers'

/** A made-up client address, so the API's per-address limits on registering and logging in
 * (app/rate_limit.py) see each test as a different student. 198.18.0.0/15 is reserved for
 * testing, so it is nobody's real address. It reaches the API because every proxy in front of
 * it in the test stack passes X-Forwarded-For on (e2e/Caddyfile, web/nginx.conf). */
export function clientAddress() {
  return `198.${18 + randomInt(2)}.${randomInt(256)}.${randomInt(1, 255)}`
}

/** A new account's details, unique in every run. */
export function newAccount(label: string) {
  const id = randomUUID().slice(0, 8)
  return { email: `e2e-${label}-${id}@example.com`, displayName: `Student ${id}` }
}

export type Student = { email: string; displayName: string }

/** Matches `ModuleDetailOut` (GET /api/modules/:id), as much as the tests need. */
export type ModuleDetail = {
  id: number
  number: number
  title: string
  status: 'locked' | 'open' | 'in_progress' | 'complete'
  currentSegmentPosition: number
  segments: {
    position: number
    kind: string
    title: string
    activityId: number | null
    videoId: number | null
    done: boolean
    /** False for support this student isn't shown (FR-8.4, #172): it stays in the list, done,
     * and the page skips it and doesn't count it. Absent before #172. */
    shown?: boolean
  }[]
  retrieval: { id: number; answered: boolean }[]
}
/** The positions (0-based) of the segments the student is shown, in order. */
export function shownPositions(module: ModuleDetail): number[] {
  return module.segments.flatMap((s, i) => (s.shown === false ? [] : [i]))
}

type ModuleSummary = { id: number; number: number; status: string; segmentCount: number }

/** The API allows a student 60 answers a minute (#139). The course walk stays under it, and
 * leaves room for the answers a test then gives on screen. */
const ANSWERS_PER_MINUTE = 50

/**
 * The student's course through the API, from inside the page, so the browser sends its own
 * session cookie (as the app does; Playwright never copies it). For getting a new student to
 * the part of the course a test is about, as the seed's demo accounts are walked
 * (api/app/seed/demo_accounts.py, `_walk`). It goes through the same rules a student does
 * (FR-2.7: a segment is done before the walk moves past it) and answers every question right,
 * from the fixtures' solutions.
 */
export class Course {
  private readonly page: Page
  private readonly answeredAt: number[] = []

  constructor(page: Page) {
    this.page = page
  }

  private async call<T>(method: string, path: string, body?: unknown): Promise<T> {
    for (let attempt = 0; ; attempt++) {
      const res = await this.page.evaluate(
        async ({ method, path, body }) => {
          const r = await fetch(path, {
            method,
            credentials: 'same-origin',
            headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
            body: body === undefined ? undefined : JSON.stringify(body),
          })
          return { status: r.status, text: await r.text(), retry: r.headers.get('Retry-After') }
        },
        { method, path, body },
      )
      // Too many answers in a minute (#139), or the API busy (503 from its admission control,
      // seen with two suites on one SQLite API): wait as the API asks, as a student would.
      if ((res.status === 429 || res.status === 503) && attempt < 2) {
        await this.page.waitForTimeout((Number(res.retry ?? 5) + 1) * 1000)
        continue
      }
      expect(res.status < 300, `${method} ${path}: ${res.status} ${res.text}`).toBe(true)
      return JSON.parse(res.text) as T
    }
  }

  modules(): Promise<ModuleSummary[]> {
    return this.call('GET', '/api/modules')
  }

  /** The module numbered `number` (the API's id can differ from the number shown). */
  async module(number: number): Promise<ModuleDetail> {
    const summary = (await this.modules()).find((m) => m.number === number)
    if (!summary) throw new Error(`no module ${number}`)
    return this.call('GET', `/api/modules/${summary.id}`)
  }

  /** Wait until `count` more answers fit in the API's limit of answers a minute. */
  async roomFor(count: number) {
    for (;;) {
      const since = Date.now() - 61_000
      while (this.answeredAt.length && this.answeredAt[0] < since) this.answeredAt.shift()
      if (this.answeredAt.length + count <= ANSWERS_PER_MINUTE) return
      await this.page.waitForTimeout(this.answeredAt[0] - since + 100)
    }
  }

  async answer(activityId: number, submitted = rightSubmission(activity(activityId))) {
    await this.roomFor(1)
    this.answeredAt.push(Date.now())
    return this.call<{ correct?: boolean }>('POST', `/api/activities/${activityId}/attempts`, {
      submitted,
    })
  }

  /** Move the student on to `position` (0-based) of a module, as Next does. */
  save(module: ModuleDetail, position: number): Promise<ModuleDetail> {
    return this.call('POST', `/api/modules/${module.id}/position`, { segmentPosition: position })
  }

  private async doSegment(module: ModuleDetail, position: number) {
    const segment = module.segments[position]
    if (segment.done) return
    if (segment.kind === 'activity' && segment.activityId !== null) {
      await this.answer(segment.activityId)
      return
    }
    throw new Error(
      `module ${module.number}, segment ${position + 1} (${segment.kind}) can't be done through the API`,
    )
  }

  /**
   * Walk module `number` from where the student is: its recall questions, then each segment, up
   * to `stopAt` (a position, 0-based: the module then opens there, not done), or to the end and
   * "Finish module".
   */
  async walk(number: number, stopAt?: number) {
    let module = await this.module(number)
    for (const item of module.retrieval) if (!item.answered) await this.answer(item.id)
    if (module.segments.length === 0) return // nothing to do yet (FR-2.1; "coming soon", #146)
    module = await this.module(number)
    // On from segment to segment shown, over support this student isn't shown (#172).
    const shown = () => shownPositions(module)
    const last = stopAt ?? shown()[shown().length - 1]
    let position = module.currentSegmentPosition
    while (position < last) {
      await this.doSegment(module, position)
      const next = shown().find((p) => p > position) ?? last
      module = await this.save(module, next)
      position = next
    }
    if (stopAt === undefined) {
      await this.doSegment(module, last)
      module = await this.save(module, last) // "Finish module"
      expect(module.status, `module ${number} is complete`).toBe('complete')
    }
  }

  /** Open the module an activity is in, without answering the activity: every module before it
   * is completed. For showing one activity on its own page as a student meets it. */
  async openModuleOf(a: Activity) {
    const module = (await this.modules()).find((m) => m.id === moduleOf(a))
    if (!module) throw new Error(`activity ${a.id} is in no module`)
    await this.completeBefore(module.number)
  }

  /** Complete every module numbered below `number`, so that one is open. */
  async completeBefore(number: number) {
    for (const m of await this.modules()) if (m.number < number) await this.walk(m.number)
  }
}

type Options = {
  /** Close the "every objective is met" dialog and dismiss badge notes whenever they show, as a
   * student does before going on. Off for a test about those notes. */
  dismissOverlays: boolean
}

type Fixtures = {
  /** A student registered for this test only, through the register page, signed in on `page`. */
  student: Student
  /** The student's course through the API, with the page's session. */
  course: Course
  /** API calls as the staff account the setup project made (never in a browser). */
  staff: APIRequestContext
}

export const test = base.extend<Options & Fixtures>({
  dismissOverlays: [true, { option: true }],
  // Every test is a student at its own address (see clientAddress).
  // Playwright reads a fixture's dependencies from this pattern, so it must be there, empty.
  // oxlint-disable-next-line no-empty-pattern
  extraHTTPHeaders: async ({}, use) => {
    await use({ 'X-Forwarded-For': clientAddress() })
  },
  page: async ({ page, dismissOverlays }, use) => {
    if (dismissOverlays) {
      // One handler for both, not one each: a handler's click waits for its target, and the
      // dialog is modal, so a note's Dismiss can't be clicked while it is open, and Playwright
      // runs no other handler meanwhile (it hung on module 6 at 360 px). The dialog goes first.
      const dialog = page.getByRole('dialog')
      const dismiss = page.getByRole('status').getByRole('button', { name: /^Dismiss/ })
      await page.addLocatorHandler(
        dialog.or(dismiss).first(),
        // Not real clicks: these overlays aren't what the tests check, and WebKit in CI never
        // saw their buttons as stable, so a handler's click hung the test it interrupted. Escape
        // closes the dialog (BadgeAnnouncer listens for it); a note's Dismiss gets its click
        // event. The note covering Next at 360 px has its own test (mobile.spec.ts).
        async () => {
          if (await dialog.isVisible()) {
            await page.keyboard.press('Escape')
            await dialog.waitFor({ state: 'hidden', timeout: 5_000 })
          }
          while (await dismiss.first().isVisible()) {
            const left = await dismiss.count()
            await dismiss.first().dispatchEvent('click')
            await expect.poll(() => dismiss.count()).toBeLessThan(left)
          }
        },
        { noWaitAfter: true },
      )
    }
    await use(page)
  },
  student: async ({ page }, use, testInfo) => {
    const account = newAccount(testInfo.project.name)
    await register(page, account)
    await use(account)
  },
  course: async ({ page, student }, use) => {
    void student // registered first: the course is the student's
    await use(new Course(page))
  },
  staff: async ({ playwright, baseURL }, use) => {
    const context = await playwright.request.newContext({
      baseURL,
      ignoreHTTPSErrors: true,
      storageState: STAFF_STATE,
      extraHTTPHeaders: { 'X-Forwarded-For': clientAddress() },
    })
    await use(context)
    await context.dispose()
  },
})

export { expect, PASSWORD }
export type { Activity, Page }

/** The WCAG 2.0 and 2.1 A and AA rules (NFR-A2, NFR-A3; SE document §14.1). */
const WCAG_21_AA = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']

/** Fails, listing each violation and where it is, when axe-core finds a WCAG 2.1 A or AA
 * violation on the page as it is now. Run it again after anything that changes the page. */
export async function expectNoViolations(page: Page, label: string) {
  // Let entrance animations finish first: mid-fade, text is see-through and fails contrast
  // (seen on CI's slower WebKit). Endless ones, like spinners, are left alone.
  await page.waitForFunction(() =>
    document
      .getAnimations()
      .every((a) => a.playState !== 'running' || a.effect?.getTiming().iterations === Infinity),
  )
  const { violations } = await new AxeBuilder({ page }).withTags(WCAG_21_AA).analyze()
  const found = violations.map(
    (v) =>
      `${v.id} (${v.impact}): ${v.help}\n` +
      v.nodes.map((n) => `    ${n.target.join(' ')}: ${n.failureSummary}`).join('\n'),
  )
  // Soft: a test goes on to its next page or state, so one run lists every violation.
  expect.soft(found, `axe on ${label}`).toEqual([])
}

/** The test video: 8 seconds of a test pattern (VP9 in MP4, so every browser can decode it;
 * media/README.md) and its captions. */
const LESSON_MP4 = readFileSync(new URL('../media/lesson.mp4', import.meta.url))
const LESSON_VTT = readFileSync(new URL('../media/lesson.vtt', import.meta.url))

/** The checkpoint every test video asks. The test owns this content, so tests may name it. */
export const CHECKPOINT = {
  atSeconds: 2,
  question: {
    prompt: 'Which vertex does BFS visit first?',
    options: [
      { id: 'start', label: 'The start vertex' },
      { id: 'deepest', label: 'The deepest vertex' },
      { id: 'last', label: 'The last vertex added' },
    ],
    correct: 'start',
    feedback: {
      deepest: 'Going deep first is depth-first search.',
      last: 'BFS takes vertices from the front of the queue, not the back.',
    },
  },
  hints: [
    { level: 1, body: 'Think about where the search begins.' },
    { level: 2, body: 'The queue starts with one vertex in it.' },
    { level: 3, body: 'The start vertex is the only one in the queue at first.' },
    { level: 4, body: 'The answer is the start vertex.' },
  ],
}

/** A new video with one checkpoint, made through the staff API for one test, as staff make one
 * on the Videos page, so no other test (or browser) has passed its checkpoint. Not placed in a
 * module: that would change module 1 for every other test. Students watch it at /videos/:id. */
export async function createVideo(staff: APIRequestContext, title: string): Promise<number> {
  const upload = async (kind: 'video' | 'captions', contentType: string, data: Buffer) => {
    const res = await staff.post(`/api/staff/media?kind=${kind}`, {
      headers: { 'Content-Type': contentType },
      data,
    })
    expect(res.status(), await res.text()).toBe(201)
    return ((await res.json()) as { path: string }).path
  }
  const res = await staff.post('/api/staff/videos', {
    data: {
      title,
      mediaPath: await upload('video', 'video/mp4', LESSON_MP4),
      captionsPath: await upload('captions', 'text/vtt', LESSON_VTT),
      transcript: 'A short test video. BFS starts at the start vertex.',
      durationSeconds: 8,
      checkpoints: [CHECKPOINT],
    },
  })
  expect(res.status(), await res.text()).toBe(201)
  return ((await res.json()) as { id: number }).id
}

/** Move the video just past its checkpoint, as dragging the scrubber does: the player snaps back
 * to the checkpoint and asks its question (FR-3.3). Waits for the metadata first, since a browser
 * ignores a seek before it. */
export async function seekPastCheckpoint(page: Page) {
  const video = page.locator('video')
  await expect
    .poll(() => video.evaluate((v: HTMLVideoElement) => v.readyState), {
      message: 'the video loads its metadata',
    })
    .toBeGreaterThanOrEqual(1)
  await expect(page.getByRole('heading', { name: 'Checkpoint' })).toHaveCount(0)
  await video.evaluate((v: HTMLVideoElement, at) => {
    v.currentTime = at
  }, CHECKPOINT.atSeconds + 3)
  await expect(page.getByRole('heading', { name: 'Checkpoint' })).toBeVisible()
}
