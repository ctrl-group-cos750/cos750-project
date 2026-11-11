// #155: the student's graph, drawn from their answer and judged against the map. The map here is
// read from the module 1 fixture (the walkways the text and the questions name), not from the
// drawing code, so a drawing that disagrees with the content fails.
import { readFileSync } from 'node:fs'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ActivityRenderer } from '../ActivityRenderer.tsx'
import type { AttemptResult, Hint, MatchingActivity } from '../activities.types.ts'
import { answerDrawing, correctDrawing } from './drawing.ts'
import { layOut, RADIUS } from './layout.ts'
import { PICTURED_ACTIVITY_IDS } from './pictures.ts'
import { BUS, CAMPUS, type Situation } from './situations.ts'

type FixtureActivity = {
  id: number
  kind: string
  purpose: string
  config: MatchingActivity['config'] & { prompt: string }
  solution: { pairs?: Record<string, string> }
}
const fixture = JSON.parse(
  readFileSync(`${process.cwd()}/../api/app/seed/module-1.json`, 'utf8'),
) as {
  modules: { segments: { id: number; body?: string }[] }[]
  activities: FixtureActivity[]
}
const activityById = (id: number) => fixture.activities.find((a) => a.id === id)!
const asActivity = (id: number): MatchingActivity => ({
  id,
  kind: 'matching',
  title: 'Question',
  visible: true,
  config: activityById(id).config,
})

/** "A–C, A–E, B–C and D–E" in a sentence of the fixture → unordered pairs. */
const pairsIn = (text: string) =>
  new Set([...text.matchAll(/\b([A-Z])–([A-Z])\b/g)].map((m) => [m[1], m[2]].sort().join('')))

// The campus walkways as module 1's text states them (segment 101), and the bus roads as the bus
// question's prompt states them.
const campusText = fixture.modules[0].segments.find((s) => s.id === 101)!.body!
const WALKWAYS = pairsIn(campusText.slice(campusText.indexOf('The walkways join')))
const ROADS = pairsIn(activityById(104).config.prompt)
const campus = asActivity(105)
const bus = asActivity(104)

const keyOf = (a: string, b: string) => [a, b].sort().join('')

/** A small seeded generator, so the "range of answers" is the same on every run. */
function* answers(activity: MatchingActivity, count: number) {
  let seed = 155
  const next = () => (seed = (seed * 1103515245 + 12345) % 2 ** 31) / 2 ** 31
  for (let i = 0; i < count; i++) {
    const pairs: Record<string, string> = {}
    for (const item of activity.config.left) {
      if (next() < 0.1) continue // left unanswered
      pairs[item.id] = activity.config.right[Math.floor(next() * activity.config.right.length)].id
    }
    yield pairs
  }
}

const edgeLabel = (activity: MatchingActivity, id: string) =>
  activity.config.right.find((r) => r.id === id)!.label

describe('the situations match the module 1 fixture', () => {
  it('draws the campus with exactly the walkways the text names', () => {
    expect(WALKWAYS.size).toBe(7)
    expect(new Set(CAMPUS.links.map(([a, b]) => keyOf(a, b)))).toEqual(WALKWAYS)
  })

  it('draws the bus map with exactly the roads the question names', () => {
    expect(new Set(BUS.links.map(([a, b]) => keyOf(a, b)))).toEqual(ROADS)
  })

  it('pictures only practice items, so a mastery item never shows a correct graph', () => {
    for (const id of PICTURED_ACTIVITY_IDS) expect(activityById(id).purpose).toBe('practice')
  })

  it('has no picture for the closing task, which would hint that stations are vertices', () => {
    expect(PICTURED_ACTIVITY_IDS).not.toContain(107)
  })

  it('says each place is a vertex, since the Green and the Fountain are not buildings', () => {
    expect(campus.config.prompt).toContain('Each place is a vertex')
  })
})

describe('your graph, judged against the map', () => {
  it('draws every chosen edge once: on the map plain, off the map red, dashed and labelled', () => {
    for (const pairs of answers(campus, 300)) {
      const drawing = answerDrawing(campus, CAMPUS, pairs, false)
      const chosen = new Set(
        Object.values(pairs).map((id) => {
          const [, a, b] = /Edge (\w)–(\w)/.exec(edgeLabel(campus, id))!
          return keyOf(a, b)
        }),
      )
      expect(new Set(drawing.edges.map((e) => keyOf(e.from, e.to)))).toEqual(chosen)
      for (const edge of drawing.edges) {
        const onMap = WALKWAYS.has(keyOf(edge.from, edge.to))
        expect([edge.mark, edge.label]).toEqual(
          onMap ? ['plain', undefined] : ['wrong', '✗ no such walkway'],
        )
      }
    }
  })

  it('never names a walkway the student left out before the comparison', () => {
    for (const pairs of answers(campus, 300)) {
      const drawing = answerDrawing(campus, CAMPUS, pairs, false)
      const drawn = new Set(drawing.edges.map((e) => keyOf(e.from, e.to)))
      for (const walkway of WALKWAYS) {
        if (drawn.has(walkway)) continue
        expect(drawing.description).not.toContain(`${walkway[0]}–${walkway[1]}`)
        expect(drawing.edges.some((e) => e.mark === 'missed')).toBe(false)
      }
    }
  })

  it('marks every walkway the student missed in green in the correct graph', () => {
    for (const pairs of answers(campus, 100)) {
      const drawn = new Set(
        answerDrawing(campus, CAMPUS, pairs, false).edges.map((e) => keyOf(e.from, e.to)),
      )
      const correct = correctDrawing(campus, CAMPUS, pairs)
      expect(new Set(correct.edges.map((e) => keyOf(e.from, e.to)))).toEqual(WALKWAYS)
      for (const edge of correct.edges) {
        const missed = !drawn.has(keyOf(edge.from, edge.to))
        expect([edge.mark, edge.label]).toEqual(
          missed ? ['missed', '✓ walkway on the map'] : ['plain', undefined],
        )
      }
    }
  })

  it('marks a stop chosen for a road, and a road chosen for a stop, with what it was chosen for', () => {
    const drawing = answerDrawing(
      bus,
      BUS,
      { 1: 'ePQ', 2: 'vQ', 3: 'vS', 4: 'ePQ', 5: 'eRS' },
      false,
    )
    expect(drawing.edges.find((e) => keyOf(e.from, e.to) === 'PQ')).toMatchObject({
      mark: 'wrong',
      label: '✗ your "Park bus stop"',
    })
    expect(drawing.vertices).toEqual([
      { id: 'Q', mark: 'wrong', label: '✗ your "road Quad – Residence"' },
    ])
    // The bus graph is given in the question, so every road on the map is drawn.
    expect(new Set(drawing.edges.map((e) => keyOf(e.from, e.to)))).toEqual(ROADS)
    expect(drawing.description).toContain('For the Park bus stop you chose edge P–Q')
  })

  it('keeps every label off the vertices, the vertex names and the other labels', () => {
    for (const [activity, situation] of [
      [campus, CAMPUS],
      [bus, BUS],
    ] as [MatchingActivity, Situation][]) {
      for (const pairs of answers(activity, 60)) {
        for (const drawing of [
          answerDrawing(activity, situation, pairs, false),
          correctDrawing(activity, situation, pairs),
        ]) {
          const { laid } = layOut(drawing, false)
          const boxes = laid.flatMap((l) => (l.label ? [l.label.box] : []))
          for (const box of boxes) {
            for (const place of situation.places) {
              const nearestX = Math.max(box.x, Math.min(place.x, box.x + box.w))
              const nearestY = Math.max(box.y, Math.min(place.y, box.y + box.h))
              expect(Math.hypot(place.x - nearestX, place.y - nearestY)).toBeGreaterThan(RADIUS)
            }
          }
          for (let i = 0; i < boxes.length; i++)
            for (let j = i + 1; j < boxes.length; j++) {
              const [a, b] = [boxes[i], boxes[j]]
              const apart =
                a.x + a.w <= b.x || b.x + b.w <= a.x || a.y + a.h <= b.y || b.y + b.h <= a.y
              expect(apart).toBe(true)
            }
        }
      }
    }
  })
})

describe('the picture beside the question', () => {
  const wrongPairs = { DE: 'DE', BG: 'FG', AC: 'AC', EF: 'EF', CF: 'CF', AE: 'CE', BC: 'DF' }
  const result = (correct: boolean, hintLevel = 0): AttemptResult => ({
    id: correct ? 2 : 1,
    activityId: 105,
    correct,
    score: correct ? 1 : 4 / 7,
    parts: campus.config.left.map((_, ref) => ({ ref, correct, message: null })),
    feedback: correct ? 'Well done.' : '4 of 7 correct.',
    hintLevel,
  })

  async function answer(hintLevel = 0, correct = false) {
    const user = userEvent.setup()
    const onSubmit = vi.fn<() => Promise<void>>(() => Promise.resolve())
    const props = {
      activity: campus,
      submitting: false,
      onSubmit,
      requestHint: vi.fn<() => Promise<Hint>>(),
      loadHints: () => Promise.resolve([]),
      showTitle: false,
    }
    const view = render(<ActivityRenderer {...props} result={undefined} />)
    expect(screen.getByRole('img', { name: /campus map/i })).toBeInTheDocument()
    expect(screen.queryByRole('tablist')).not.toBeInTheDocument()
    const selects = screen.getAllByRole('combobox')
    for (const [index, item] of campus.config.left.entries()) {
      const id = (correct ? item.id : wrongPairs[item.id as keyof typeof wrongPairs]) ?? ''
      // oxlint-disable-next-line no-await-in-loop
      await user.selectOptions(selects[index], id)
    }
    await user.click(screen.getByRole('button', { name: 'Check answer' }))
    view.rerender(<ActivityRenderer {...props} result={result(correct, hintLevel)} />)
    return user
  }

  it('after a wrong answer shows your graph beside the campus map, never the correct graph', async () => {
    const user = await answer()
    const tabs = within(screen.getByRole('tablist')).getAllByRole('tab')
    expect(tabs.map((t) => t.textContent)).toEqual(['Your graph', 'Campus map'])
    expect(tabs[0]).toHaveAttribute('aria-selected', 'true')
    const graph = screen.getByRole('img', { name: /your graph/i })
    expect(graph).toHaveAccessibleDescription(/Not on the map: F–G, C–E and D–F\./)
    for (const missing of ['A–E', 'B–C', 'B–G']) {
      expect(graph).not.toHaveAccessibleDescription(new RegExp(missing))
    }
    expect(screen.queryByRole('tab', { name: 'Correct graph' })).not.toBeInTheDocument()
    // The map is on the page once: only in its tab.
    expect(screen.queryByRole('img', { name: /campus map/i })).not.toBeInTheDocument()
    // WAI-ARIA tabs: arrow keys move and select; only the selected tab is in the tab order.
    tabs[0].focus()
    await user.keyboard('{ArrowRight}')
    expect(tabs[1]).toHaveFocus()
    expect(tabs[1]).toHaveAttribute('aria-selected', 'true')
    expect(tabs[0]).toHaveAttribute('tabindex', '-1')
    expect(screen.getByRole('tabpanel')).toContainElement(
      screen.getByRole('img', { name: /campus map/i }),
    )
  })

  it('once hint 4 is open shows the correct graph, with the missed walkways named', async () => {
    const user = await answer(4)
    await user.click(screen.getByRole('tab', { name: 'Correct graph' }))
    expect(screen.getByRole('img', { name: 'Correct graph' })).toHaveAccessibleDescription(
      /The walkways you missed, A–E, B–C and B–G, are marked in green\./,
    )
  })

  it('after a right answer shows your graph beside the correct graph', async () => {
    await answer(0, true)
    const tabs = within(screen.getByRole('tablist')).getAllByRole('tab')
    expect(tabs.map((t) => t.textContent)).toEqual(['Your graph', 'Correct graph'])
  })
})

describe('directed or undirected', () => {
  it('redraws only the rows the student got wrong, as they classified them, with the meaning', async () => {
    const classify = asActivity(106)
    const user = userEvent.setup()
    const props = {
      activity: classify,
      submitting: false,
      onSubmit: vi.fn<() => Promise<void>>(() => Promise.resolve()),
      requestHint: vi.fn<() => Promise<Hint>>(),
      loadHints: () => Promise.resolve([]),
    }
    const view = render(<ActivityRenderer {...props} result={undefined} />)
    // The four situation pictures, in the same order as the rows.
    expect(screen.getAllByRole('img').map((img) => img.getAttribute('alt')?.split(':')[0])).toEqual(
      [
        'Friendships at a residence',
        'Who follows whom online',
        'A delivery route',
        'Roads join Johannesburg to Pretoria and Johannesburg to Soweto. Cars drive both ways.',
      ],
    )
    const chosen = ['directed', 'directed', 'undirected', 'undirected']
    for (const [index, select] of screen.getAllByRole('combobox').entries())
      // oxlint-disable-next-line no-await-in-loop
      await user.selectOptions(select, chosen[index])
    await user.click(screen.getByRole('button', { name: 'Check answer' }))
    const correctRows = [false, true, false, true]
    view.rerender(
      <ActivityRenderer
        {...props}
        result={{
          id: 9,
          activityId: 106,
          correct: false,
          score: 0.5,
          parts: correctRows.map((correct, ref) => ({ ref, correct, message: null })),
          feedback: '2 of 4 correct.',
          hintLevel: 0,
        }}
      />,
    )
    const drawings = screen.getAllByTestId('graph-drawing')
    expect(drawings).toHaveLength(2)
    expect(drawings[0]).toHaveAccessibleName('Friendships: if it were directed')
    expect(drawings[0].querySelectorAll('[marker-end]')).toHaveLength(3)
    expect(drawings[1]).toHaveAccessibleName('Delivery route: if it were undirected')
    expect(drawings[1].querySelectorAll('[marker-end]')).toHaveLength(0)
    for (const drawing of drawings)
      for (const edge of drawing.querySelectorAll('path[data-mark]')) {
        // Never colour alone: a wrong edge is also dashed.
        expect(edge).toHaveAttribute('data-mark', 'wrong')
        expect(edge).toHaveAttribute('stroke-dasharray')
      }
  })
})

describe('view full size', () => {
  it('opens the picture in a dialog and returns focus to the button when closed', async () => {
    const user = userEvent.setup()
    render(
      <ActivityRenderer
        activity={campus}
        result={undefined}
        submitting={false}
        onSubmit={vi.fn<() => Promise<void>>()}
        requestHint={vi.fn<() => Promise<Hint>>()}
        loadHints={() => Promise.resolve([])}
      />,
    )
    const open = screen.getByRole('button', { name: 'View full size' })
    await user.click(open)
    await user.click(screen.getByRole('button', { name: 'Close', hidden: true }))
    expect(open).toHaveFocus()
  })
})
