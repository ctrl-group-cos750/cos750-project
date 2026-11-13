import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ada, fakeApi, renderApp } from '../../test/app.tsx'
import type { ModuleSummary } from '../module/module.types.ts'
import { MAX_RING, RADIUS, radarSummary, radiusFor, ringFor } from './radar.ts'
import { SkillRadar } from './SkillRadar.tsx'
import type { Skill } from './skills.api.ts'

function skill(id: number, more: Partial<Skill> = {}): Skill {
  return {
    id,
    text: `Objective ${id} in full.`,
    answered: 0,
    correct: 0,
    onYourOwn: 0,
    total: 4,
    level: 'not_started',
    result: null,
    ...more,
  }
}

const eight = (more: Record<number, Partial<Skill>> = {}): Skill[] =>
  [1, 2, 3, 4, 5, 6, 7, 8].map((id) => skill(id, more[id]))

const partWay = eight({
  1: { level: 'secure' },
  2: { level: 'practising' },
  4: { level: 'secure' },
})

const finished = eight({
  1: { level: 'secure', result: 'met_independently' },
  2: { level: 'secure', result: 'met_with_support' },
  3: { level: 'practising', result: 'not_yet' },
})

beforeEach(() => localStorage.clear())
afterEach(() => vi.restoreAllMocks())

describe('the radar scale', () => {
  it('puts each level on its own ring, centre outwards', () => {
    expect(ringFor(skill(1))).toBe(0)
    expect(ringFor(skill(1, { level: 'practising' }))).toBe(1)
    expect(ringFor(skill(1, { level: 'secure' }))).toBe(2)
    expect(ringFor(skill(1, { result: 'met_with_support' }))).toBe(3)
    expect(ringFor(skill(1, { level: 'practising', result: 'met_independently' }))).toBe(4)
    // "Not yet" keeps the practice ring it had.
    expect(ringFor(skill(1, { level: 'practising', result: 'not_yet' }))).toBe(1)
  })

  it('spaces the rings evenly up to the outer one', () => {
    expect(MAX_RING).toBe(4)
    expect([0, 1, 2, 3, 4].map(radiusFor)).toEqual([
      0,
      RADIUS / 4,
      RADIUS / 2,
      (3 * RADIUS) / 4,
      RADIUS,
    ])
  })

  it('sums the chart up in one sentence', () => {
    expect(radarSummary(finished)).toBe(
      'Skill profile chart of the 8 objectives: 1 gold, 1 bronze, 1 not yet, 5 not started. Each objective is listed with its level below.',
    )
  })
})

describe('the radar chart', () => {
  it('draws an octagon: one axis and one name for each of the eight objectives', () => {
    const { container } = render(<SkillRadar skills={partWay} />)
    expect(container.querySelectorAll('line')).toHaveLength(8)
    // Four rings, each an octagon.
    const rings = container.querySelectorAll('polygon[data-ring]')
    expect(rings).toHaveLength(4)
    expect(rings[0]!.getAttribute('points')!.split(' ')).toHaveLength(8)
    const names = [...container.querySelectorAll('[data-objective]')].filter(
      (e) => e.tagName === 'SPAN',
    )
    expect(names.map((n) => n.textContent)).toEqual([
      '1 Key terms',
      '2 Vertices and edges',
      '3 Modelling a problem',
      '4 Why BFS',
      '5 Tracing BFS',
      '6 Coding BFS',
      '7 Testing BFS',
      '8 Shortest routes',
    ])
  })

  it('places each point on the ring of its level', () => {
    const { container } = render(<SkillRadar skills={finished} />)
    const points = [...container.querySelectorAll('circle[data-objective]')]
    expect(
      points.map((p) => [p.getAttribute('data-objective'), p.getAttribute('data-ring')]),
    ).toEqual([
      ['1', '4'],
      ['2', '3'],
      ['3', '1'],
    ])
    // Each point drawn by its level, not by colour alone: gold, bronze, an open "not yet".
    expect(points.map((p) => p.getAttribute('data-kind'))).toEqual(['gold', 'bronze', 'notYet'])
    // Objective 1 is at the top: straight up from the centre, at the outer ring.
    const top = points[0]!
    expect(Number(top.getAttribute('cx'))).toBeCloseTo(200)
    expect(Number(top.getAttribute('cy'))).toBeCloseTo(160 - RADIUS)
    // Objective 2, bronze, is on ring 3, at 45 degrees.
    const second = points[1]!
    const r = radiusFor(3)
    expect(Number(second.getAttribute('cx'))).toBeCloseTo(200 + r * Math.SQRT1_2)
    expect(Number(second.getAttribute('cy'))).toBeCloseTo(160 - r * Math.SQRT1_2)
  })

  it('draws a practising point apart from a secure one', () => {
    const { container } = render(<SkillRadar skills={partWay} />)
    const kinds = [...container.querySelectorAll('circle[data-objective]')].map((p) => [
      p.getAttribute('data-objective'),
      p.getAttribute('data-kind'),
    ])
    expect(kinds).toEqual([
      ['1', 'secure'],
      ['2', 'practising'],
      ['4', 'secure'],
    ])
  })

  it('draws no shape before anything is practised, only the rings', () => {
    const { container } = render(<SkillRadar skills={eight()} />)
    expect(container.querySelector('[data-testid="radar-shape"]')).toBeNull()
    expect(container.querySelectorAll('circle')).toHaveLength(0)
  })

  it('is one named picture for screen readers, with nothing in it that takes focus', () => {
    const { container } = render(<SkillRadar skills={partWay} />)
    const image = screen.getByRole('img', { name: radarSummary(partWay) })
    expect(image.tagName.toLowerCase()).toBe('svg')
    // The names around it repeat the list under it, so they are hidden from screen readers.
    expect(
      container.querySelector('span[data-objective]')!.closest('[aria-hidden="true"]'),
    ).not.toBeNull()
    expect(container.querySelectorAll('a, button, [tabindex]')).toHaveLength(0)
  })

  it('has a legend for the rings, in words', () => {
    render(<SkillRadar skills={finished} />)
    const legend = screen.getByText('Rings, centre outwards:').parentElement!
    const items = [...legend.children].map((c) => c.textContent?.trim())
    expect(items).toEqual([
      'Rings, centre outwards:',
      'centre: not started',
      'practising',
      'secure in practice',
      'bronze, met with support (dashed)',
      'gold, met on your own (outer)',
      'open point: not yet in the mastery check',
    ])
  })
})

// --- On the home page ---------------------------------------------------------------------------

const module0: ModuleSummary = {
  id: 1,
  number: 0,
  slug: 'warmup',
  title: 'Warm-up',
  goals: [],
  estimatedMinutes: 5,
  status: 'open',
  segmentCount: 2,
  currentSegmentPosition: 0,
}

function home(objectives = partWay) {
  return fakeApi({
    user: ada,
    overrides: {
      'GET /api/modules': () => Response.json([module0]),
      'GET /api/me/skills': () => Response.json({ objectives, modules: [] }),
    },
  })
}

describe('the skill profile on the home page', () => {
  it('is the radar chart, with every objective and its level in words under it', async () => {
    home()
    renderApp('/')
    const region = await screen.findByRole('region', { name: 'Skill profile' })
    expect(within(region).getByRole('img', { name: radarSummary(partWay) })).toBeInTheDocument()
    // The text alternative: the list, without bars, each row opening to its evidence.
    const rows = within(region).getAllByRole('listitem')
    expect(rows).toHaveLength(8)
    expect(rows[0]).toHaveTextContent('Key terms')
    expect(rows[0]).toHaveTextContent('Secure in practice')
    expect(rows[2]).toHaveTextContent('Not started')
    expect(region.querySelector('[class*="track"]')).toBeNull()
  })

  it('minimises to its heading and opens again, kept on this device', async () => {
    home()
    renderApp('/')
    const toggle = await screen.findByRole('button', { name: 'Skill profile' })
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    await userEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    // Still there as a region with its heading; the body is collapsed, not removed.
    const region = screen.getByRole('region', { name: 'Skill profile' })
    const body = document.getElementById(toggle.getAttribute('aria-controls')!)!
    expect(region).toContainElement(body)
    expect(body).not.toBeVisible()
    expect(within(region).queryByRole('img')).toBeNull()
    expect(localStorage.getItem(`ctrl-academy.${ada.id}.minimised.skillProfile`)).toBe('yes')
    await userEvent.click(toggle)
    expect(within(region).getByRole('img')).toBeVisible()
  })

  it('stays minimised when the page is opened again', async () => {
    home()
    localStorage.setItem(`ctrl-academy.${ada.id}.minimised.skillProfile`, 'yes')
    renderApp('/')
    expect(await screen.findByRole('button', { name: 'Skill profile' })).toHaveAttribute(
      'aria-expanded',
      'false',
    )
  })

  it('turns off from its "⋯", leaving a note with the way back and Undo', async () => {
    home()
    renderApp('/')
    await userEvent.click(
      await screen.findByRole('button', { name: 'Hide options for skill profile' }),
    )
    await userEvent.click(screen.getByRole('button', { name: 'Hide skill profile' }))
    expect(screen.queryByRole('region', { name: 'Skill profile' })).toBeNull()
    const note = screen.getByText(/Skill profile hidden/).closest('output')!
    expect(note).toHaveFocus()
    expect(within(note).getByRole('link', { name: 'your profile' })).toHaveAttribute(
      'href',
      '/profile#what-you-see',
    )
    expect(localStorage.getItem(`ctrl-academy.${ada.id}.skillProfile`)).toBe('off')
    await userEvent.click(within(note).getByRole('button', { name: 'Undo' }))
    expect(await screen.findByRole('region', { name: 'Skill profile' })).toBeInTheDocument()
  })

  it('is not shown at all when switched off in the profile, and the switch shows it off', async () => {
    home()
    localStorage.setItem(`ctrl-academy.${ada.id}.skillProfile`, 'off')
    renderApp('/')
    await screen.findByRole('heading', { name: 'All modules' })
    expect(screen.queryByRole('region', { name: 'Skill profile' })).toBeNull()
    expect(screen.queryByText(/Skill profile hidden/)).toBeNull() // no note: not hidden from here
  })

  it('shows as off on the profile once hidden', async () => {
    home()
    localStorage.setItem(`ctrl-academy.${ada.id}.skillProfile`, 'off')
    renderApp('/profile')
    expect(await screen.findByRole('checkbox', { name: 'Skill profile' })).not.toBeChecked()
    await userEvent.click(screen.getByRole('checkbox', { name: 'Skill profile' }))
    expect(localStorage.getItem(`ctrl-academy.${ada.id}.skillProfile`)).toBe('on')
  })
})

describe('the way to improve each objective (#214)', () => {
  const practise = { kind: 'practise', moduleId: 2, segment: 3, objectiveId: null } as const
  const objectives = [
    skill(1, { improve: { ...practise, moduleId: 1, segment: null } }),
    skill(2, { level: 'practising', improve: practise }),
    skill(3, {
      level: 'secure',
      improve: { kind: 'revisit', moduleId: 2, segment: null, objectiveId: null },
    }),
    skill(4, {
      result: 'not_yet',
      improve: { kind: 'review', moduleId: null, segment: null, objectiveId: 4 },
    }),
    skill(5, {
      result: 'met_with_support',
      improve: { kind: 'revisit', moduleId: 3, segment: null, objectiveId: null },
    }),
    skill(6, { result: 'met_independently', improve: null }),
    skill(7, {
      level: 'practising',
      improve: { kind: 'check', moduleId: 6, segment: null, objectiveId: null },
    }),
  ]

  it('links each level to the right place, as a real link named from the objective', async () => {
    home(objectives)
    renderApp('/')
    const region = await screen.findByRole('region', { name: 'Skill profile' })
    const link = (name: string) => within(region).getByRole('link', { name })
    // Not started: the module, where it resumes.
    expect(link('Improve Key terms: practise in module 1')).toHaveAttribute('href', '/modules/1')
    expect(link('Improve Key terms: practise in module 1')).toHaveTextContent(
      'Practise in module 1',
    )
    // Practising: at the segment with the next item to do.
    expect(link('Improve Vertices and edges: practise in module 2')).toHaveAttribute(
      'href',
      '/modules/2?segment=3',
    )
    // Secure, and bronze: a quieter revisit.
    expect(link('Modelling a problem: revisit module 2')).toHaveAttribute('href', '/modules/2')
    expect(link('Tracing BFS: revisit module 3')).toHaveAttribute('href', '/modules/3')
    // Not yet: the review path.
    expect(link('Improve Why BFS: follow its review path')).toHaveAttribute('href', '/review/4')
    // Practice can no longer make it secure: the mastery check (#222 re-review, N1).
    expect(link('Improve Testing BFS: show it in the mastery check')).toHaveAttribute(
      'href',
      '/modules/6',
    )
    // Gold: nothing to improve.
    const gold = region.querySelector('li[data-objective="6"]')!
    expect(within(gold as HTMLElement).queryByRole('link')).toBeNull()
  })

  it('shows the same links in the progress panel’s list, in the opened row', async () => {
    vi.stubGlobal(
      'matchMedia',
      (query: string) =>
        ({
          matches: query === '(min-width: 64rem)',
          media: query,
          addEventListener: () => {},
          removeEventListener: () => {},
        }) as unknown as MediaQueryList,
    )
    fakeApi({
      user: ada,
      overrides: {
        'GET /api/activities/7': () =>
          Response.json({
            id: 7,
            kind: 'multiple_choice',
            title: 'Pick one',
            visible: true,
            config: { prompt: 'Q', options: [{ id: 'a', label: 'A' }] },
          }),
        'GET /api/activities/7/hints': () => Response.json([]),
        'GET /api/me/skills': () => Response.json({ objectives, modules: [] }),
      },
    })
    renderApp('/activities/7')
    const aside = await screen.findByRole('complementary', { name: 'Your progress' })
    // In the narrow panel, inside the opened row.
    await userEvent.click(await within(aside).findByText('Why BFS'))
    expect(
      within(aside).getByRole('link', { name: 'Improve Why BFS: follow its review path' }),
    ).toHaveAttribute('href', '/review/4')
  })
})
