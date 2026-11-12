import type { Locator, Page } from '@playwright/test'
import {
  activity,
  bfsSteps,
  firstOrder,
  wrongOption,
  type Activity,
  type ActivityOf,
} from './content'
import { expect, type ModuleDetail } from './fixtures'
import { tabTo } from './helpers'

/**
 * Answering an activity through its screen, as a student does, from the fixture's solution: the
 * test knows which activity is on screen (from the module's segments), never its wording. Each
 * control is found by its role and accessible name, so these also check that every control has
 * one (NFR-A3).
 *
 * `scope` is the part of the page that holds the one activity (a segment's region, or the page).
 */
export type Answer = 'right' | 'wrong'

/** The result after "Check answer": "Correct" or "Not quite" (FeedbackPanel). */
export function result(scope: Locator) {
  return scope.getByRole('region', { name: 'Submission results' })
}

/** Check the answer, and what a right one shows: "Correct", the content's explanation of why it
 * is right when it has one (FR-4.2, #158), and no more hints (#160). A mastery check item says
 * only "Answer recorded" once #144 is merged, whether it is right or not; before that it says
 * "Correct" or "Not quite" like any other activity. */
export async function check(scope: Locator, answer: Answer, a?: Activity) {
  const button = scope.getByRole('button', { name: 'Check answer' })
  // No result yet: whatever shows after the click is this answer's.
  await expect(result(scope)).toHaveCount(0)
  await button.click()
  const verdict = answer === 'right' ? 'Correct' : 'Not quite'
  const shown = result(scope)
  if (a?.purpose === 'mastery') {
    await expect(shown).toContainText(new RegExp(`${verdict}|Answer recorded`))
    if ((await shown.textContent())?.includes('Answer recorded')) {
      // One answer only (#144): nothing left to answer with.
      await expect(button).toHaveCount(0)
      return
    }
  }
  await expect(shown).toContainText(verdict)
  if (answer !== 'right') return
  const explanation = (a?.solution as { explanation?: string | null } | undefined)?.explanation
  if (explanation) await expect(shown).toContainText(explanation.split('`').join(''))
  await expect(scope.getByRole('button', { name: 'Show next hint' })).toHaveCount(0)
}

/** Fill in the activity's controls with a right or a wrong answer, and check it. */
export async function answerActivity(page: Page, scope: Locator, a: Activity, answer: Answer) {
  switch (a.kind) {
    case 'multiple_choice':
      await multipleChoice(scope, a, answer)
      break
    case 'matching':
      // Wrong: every item matched, each to something other than its answer.
      for (const item of a.config.left) {
        const right = a.solution.pairs[item.id]
        const pick =
          answer === 'right' ? right : (a.config.right.find((r) => r.id !== right)?.id ?? right)
        await scope.getByLabel(item.label, { exact: true }).selectOption(pick)
      }
      break
    case 'fill_in':
      // Wrong: every blank filled, each with a token other than its answer.
      for (const blank of a.config.blanks) {
        const right = a.solution.answers[String(blank)]
        const pick =
          answer === 'right' ? right : (a.config.options.find((o) => o !== right) ?? right)
        await scope.getByLabel(`Blank ${blank}`, { exact: true }).selectOption(pick)
      }
      break
    case 'parsons':
      await parsons(page, scope, a, answer)
      break
    case 'trace':
      await trace(scope, a, answer)
      break
    case 'fix_the_bug':
      // Wrong: the faulty program as it is shown, bug and all.
      if (answer === 'right') await fixTheBug(scope, a)
      break
    case 'choose_tests':
      await chooseTests(scope, a, answer)
      break
  }
  await check(scope, answer, a)
}

async function multipleChoice(scope: Locator, a: ActivityOf<'multiple_choice'>, answer: Answer) {
  const id = answer === 'right' ? a.solution.correct : wrongOption(a)
  const label = a.config.options.find((o) => o.id === id)?.label ?? ''
  await scope.getByRole('radio', { name: label, exact: true }).check()
}

/** The Parsons lines, moved with the arrow keys only (NFR-A1): each line of one accepted order
 * is brought up to its place with ArrowUp, and lines not in it are removed. Wrong: one line of
 * the answer removed, so the program is missing it. */
async function parsons(page: Page, scope: Locator, a: ActivityOf<'parsons'>, answer: Answer) {
  const answerList = scope.getByRole('list', { name: 'Your answer, in order' })
  const rows = answerList.getByRole('listitem')
  // The screen starts with every line in the answer, in the order the content gives them.
  const shown = a.config.lines.map((line) => line.id)
  const target = firstOrder(a.solution.order)
  const unwanted = shown.filter((id) => !target.includes(id))
  if (answer === 'wrong') unwanted.push(target[0])
  for (const id of unwanted) {
    await rows
      .nth(shown.indexOf(id))
      .getByRole('button', { name: /^Remove/ })
      .click()
    shown.splice(shown.indexOf(id), 1)
  }
  await expect(rows).toHaveCount(shown.length)
  if (answer === 'wrong') return
  for (const [place, id] of target.entries()) {
    const from = shown.indexOf(id)
    if (from === place) continue
    // The line itself is the first button in its row; focus stays on it as it moves. Reached
    // with Tab, as a keyboard user would (NFR-A1).
    await tabTo(page, rows.nth(from).getByRole('button').first())
    for (let i = from; i > place; i--) await page.keyboard.press('ArrowUp')
    shown.splice(from, 1)
    shown.splice(place, 0, id)
  }
}

/** The trace table: one step per vertex that leaves the queue, from the BFS the engine runs.
 * Wrong: every step's current vertex is another vertex, so every row is wrong (a single wrong
 * row still meets objective 5's criterion, "at most one error"). */
async function trace(scope: Locator, a: ActivityOf<'trace'>, answer: Answer) {
  const steps = bfsSteps(a.config)
  const { vertices } = a.config
  for (let i = 1; i < steps.length; i++)
    await scope.getByRole('button', { name: 'Add a step' }).click()
  for (const [i, step] of steps.entries()) {
    const n = i + 1
    const current =
      answer === 'right'
        ? step.visitedVertex
        : vertices[(vertices.indexOf(step.visitedVertex) + 1) % vertices.length]
    await scope.getByLabel(`Step ${n}, current vertex`, { exact: true }).selectOption(current)
    await scope.getByLabel(new RegExp(`^Step ${n}, queue`)).fill(step.queue.join(', '))
    await scope.getByLabel(new RegExp(`^Step ${n}, visited`)).fill(step.visited.join(', '))
    await scope.getByLabel(new RegExp(`^Step ${n}, order`)).fill(step.order.join(', '))
  }
}

/** Fix the bug with the screen's own controls: each correction goes in place of a line that
 * doesn't belong (or is inserted as a new line), lines left over are removed, then lines are
 * moved with Up and Down until the program is one accepted order. */
async function fixTheBug(scope: Locator, a: ActivityOf<'fix_the_bug'>) {
  const target = firstOrder(a.solution.order)
  const originals = a.config.lines.map((line) => line.id)
  // What each row holds, in screen order; at first, the faulty program's lines.
  const rows = [...originals]
  const spare = originals.filter((id) => !target.includes(id))
  for (const id of target.filter((t) => !originals.includes(t))) {
    const row = spare.shift()
    if (row !== undefined) {
      const index = rows.indexOf(row)
      await scope.getByLabel(`Line ${index + 1}`, { exact: true }).selectOption(String(id))
      rows[index] = id
    } else {
      await scope.getByLabel('Correction', { exact: true }).selectOption(String(id))
      await scope.getByRole('button', { name: 'Insert line' }).click()
      rows.push(id)
    }
  }
  for (const id of spare) {
    const index = rows.indexOf(id)
    await scope.getByRole('button', { name: `Remove line ${index + 1}`, exact: true }).click()
    rows.splice(index, 1)
  }
  for (const [place, id] of target.entries()) {
    for (let from = rows.indexOf(id); from > place; from--) {
      await scope.getByRole('button', { name: `Move line ${from + 1} up`, exact: true }).click()
      rows.splice(from, 1)
      rows.splice(from - 1, 0, id)
    }
  }
  await expect(
    scope.getByRole('list', { name: 'Your fixed program' }).getByRole('listitem'),
  ).toHaveCount(target.length)
}

/** Tick the test cases that expose the bug. Wrong: one that doesn't, instead. */
async function chooseTests(scope: Locator, a: ActivityOf<'choose_tests'>, answer: Answer) {
  const exposing = new Set(a.solution.exposing)
  const pick =
    answer === 'right'
      ? a.config.tests.filter((t) => exposing.has(t.id))
      : [a.config.tests.find((t) => !exposing.has(t.id)) ?? a.config.tests[0]]
  for (const t of pick) {
    const n = a.config.tests.indexOf(t) + 1
    await scope.getByRole('checkbox', { name: new RegExp(`^Test ${n}:`) }).check()
  }
}

/** The region a module segment is shown in: a section named by the segment's title. */
export function segmentRegion(page: Page, title: string) {
  return page.getByRole('region', { name: title, exact: true })
}

/**
 * Work through a module on its page, as a student does, from wherever the page opens: its recall
 * questions, then every segment, answering each activity (right, unless `answerFor` says
 * otherwise) and pressing Next, then "Finish module", which goes back to the map (or, for the
 * mastery check once #144 is merged, to the report). `onSegment`
 * runs on each segment once it is answered, e.g. to run axe or measure the page.
 */
export async function walkModule(
  page: Page,
  module: ModuleDetail,
  {
    answerFor = () => 'right',
    onSegment,
    beforeAnswer,
  }: {
    answerFor?: (a: Activity) => Answer
    onSegment?: (label: string) => Promise<void>
    beforeAnswer?: (a: Activity) => Promise<void>
  } = {},
) {
  await page.goto(`/modules/${module.id}`)
  const recall = module.retrieval.filter((item) => !item.answered)
  for (const [i, item] of recall.entries()) {
    const region = page.getByRole('region', { name: `Module ${module.number} retrieval` })
    await expect(region).toBeVisible()
    const a = activity(item.id)
    await beforeAnswer?.(a)
    await answerActivity(page, region, a, answerFor(a))
    await onSegment?.(`module ${module.number}, recall question ${i + 1}`)
    await region
      .getByRole('button', { name: i === recall.length - 1 ? 'Start module' : 'Next question' })
      .click()
  }
  const total = module.segments.length
  for (let i = module.currentSegmentPosition; i < total; i++) {
    const segment = module.segments[i]
    await expect(page.getByText(`Segment ${i + 1} of ${total}`, { exact: true })).toBeVisible()
    const region = segmentRegion(page, segment.title)
    await expect(region).toBeVisible()
    if (segment.kind === 'activity' && segment.activityId !== null && !segment.done) {
      const a = activity(segment.activityId)
      await beforeAnswer?.(a)
      await answerActivity(page, region, a, answerFor(a))
    }
    await onSegment?.(`module ${module.number}, segment ${i + 1} (${segment.kind})`)
    const last = i === total - 1
    const next = page
      .getByRole('navigation', { name: 'Segment navigation' })
      .getByRole('button', { name: last ? 'Finish module' : /^Next/ })
    // Next stays blocked until the module, fetched again after the answer, says the segment is done.
    await expect(next).not.toHaveAttribute('aria-disabled', 'true')
    await next.click()
  }
  await expect(page).toHaveURL(/\/(report)?$/)
}
