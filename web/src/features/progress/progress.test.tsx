import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ada, fakeApi, renderApp } from '../../test/app.tsx'
import type { AttemptResult } from '../activities/activities.types.ts'
import { FeedbackPanel } from '../activities/FeedbackPanel.tsx'
import type { ModuleSummary } from '../module/module.types.ts'
import { rewardsKey } from '../rewards/hooks.ts'
import {
  celebrateOnce,
  confetti,
  confettiEnabled,
  setConfettiEnabled,
  stopConfetti,
} from './confetti.ts'
import { PRAISE_LINES, praiseFor, progressRemark } from './praise.ts'
import { setPreference } from './preferences.ts'
import { skillsKey } from './hooks.ts'
import { SkillProfile } from './SkillProfile.tsx'
import type { ModuleMedal, Skill, Skills } from './skills.api.ts'

// --- Fixtures ----------------------------------------------------------------------------------

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

function medal(moduleId: number, more: Partial<ModuleMedal> = {}): ModuleMedal {
  return {
    moduleId,
    complete: true,
    firstTime: 4,
    onYourOwn: 4,
    answered: 4,
    total: 4,
    medal: 'gold',
    headingFor: 'gold',
    objectives: [1, 2],
    ...more,
  }
}

const finished: ModuleSummary = {
  id: 4,
  number: 3,
  slug: 'meet-bfs',
  title: 'Meet BFS',
  goals: ['g'],
  estimatedMinutes: 12,
  status: 'complete',
  segmentCount: 2,
  currentSegmentPosition: 1,
}

const right: AttemptResult = {
  id: 11,
  activityId: 7,
  correct: true,
  score: 1,
  parts: [],
  feedback: 'Correct.',
  hintLevel: 0,
  points: 10,
}

/** A matchMedia stand-in: `matching` lists the queries that match. */
function media(...matching: string[]) {
  vi.stubGlobal(
    'matchMedia',
    (query: string) =>
      ({
        matches: matching.includes(query),
        media: query,
        addEventListener: () => {},
        removeEventListener: () => {},
      }) as unknown as MediaQueryList,
  )
}

/** A canvas that can draw, which jsdom's can't. */
function drawableCanvas() {
  const context = new Proxy({}, { get: () => () => {} })
  return vi
    .spyOn(HTMLCanvasElement.prototype, 'getContext')
    .mockReturnValue(context as unknown as CanvasRenderingContext2D)
}

beforeEach(() => localStorage.clear())
afterEach(() => {
  stopConfetti()
  vi.restoreAllMocks()
})

// --- Praise ------------------------------------------------------------------------------------

describe('praise under a correct answer', () => {
  it('is calm: no exclamation marks and nothing effusive', () => {
    for (const line of PRAISE_LINES) {
      expect(line).not.toMatch(/!|amazing|awesome|genius|superstar/i)
    }
  })

  it('varies from one answer to the next, and stays put for the same answer', () => {
    const lines = new Set([1, 2, 3, 4, 5, 6].map((id) => praiseFor(id, 0)))
    expect(lines.size).toBeGreaterThan(3)
    expect(praiseFor(5, 0)).toBe(praiseFor(5, 0))
  })

  it('remarks on progress in plain counts', () => {
    expect(progressRemark(eight())).toBeNull()
    expect(progressRemark(eight({ 1: { level: 'practising' }, 2: { level: 'secure' } }))).toBe(
      "You've practised 2 of 8 objectives so far.",
    )
    const all = Object.fromEntries(
      [1, 2, 3, 4, 5, 6, 7, 8].map((n) => [n, { level: 'practising' }]),
    )
    expect(progressRemark(eight({ ...all, 3: { level: 'secure' } }))).toBe(
      'Every objective practised, 1 of 8 secure.',
    )
  })

  it('is honest about hint 3 or 4', () => {
    expect(praiseFor(1, 3)).toMatch(/hint/i)
    expect(praiseFor(1, 0)).not.toBe(praiseFor(1, 3))
  })
})

// --- Confetti ----------------------------------------------------------------------------------

describe('confetti', () => {
  it('is on by default, and turning it off is kept on this device', () => {
    expect(confettiEnabled()).toBe(true)
    setConfettiEnabled(false)
    expect(confettiEnabled()).toBe(false)
    expect(localStorage.getItem('ctrl-academy.confetti')).toBe('off')
  })

  it('draws on a canvas that can’t be clicked or read, and is cleaned up', () => {
    media()
    drawableCanvas()
    expect(confetti('small')).toBe(true)
    const canvas = document.querySelector('canvas[data-confetti]') as HTMLCanvasElement
    expect(canvas).toHaveAttribute('aria-hidden', 'true')
    expect(canvas.style.pointerEvents).toBe('none')
    expect(canvas.style.position).toBe('fixed') // over the page: no layout shift
    stopConfetti()
    expect(document.querySelector('canvas')).toBeNull()
  })

  it('stops a burst on screen when turned off', () => {
    media()
    drawableCanvas()
    confetti('big')
    setConfettiEnabled(false)
    expect(document.querySelector('canvas')).toBeNull()
    expect(confetti('small')).toBe(false)
  })

  it('never plays under prefers-reduced-motion', () => {
    media('(prefers-reduced-motion: reduce)')
    drawableCanvas()
    expect(confetti('big')).toBe(false)
    expect(document.querySelector('canvas')).toBeNull()
  })

  it('plays a once-only moment once per device', () => {
    media()
    drawableCanvas()
    expect(celebrateOnce('ready-for-the-lecture')).toBe(true)
    expect(celebrateOnce('ready-for-the-lecture')).toBe(false)
  })
})

// --- The success moment ------------------------------------------------------------------------

function panel(hideRewards: boolean | undefined, skills?: Skill[]) {
  const client = new QueryClient()
  if (hideRewards !== undefined)
    client.setQueryData(rewardsKey, { hideRewards, points: 0, badges: [] })
  if (skills) client.setQueryData(skillsKey, { objectives: skills, modules: [] })
  const view = (result: AttemptResult | undefined) => (
    <QueryClientProvider client={client}>
      <FeedbackPanel result={result} />
    </QueryClientProvider>
  )
  const { rerender } = render(view(undefined))
  return (result: AttemptResult | undefined) => rerender(view(result))
}

describe('the success moment', () => {
  it('marks a correct answer just given with praise and the points it earned', () => {
    const show = panel(false)
    show(right)
    expect(screen.getByText(praiseFor(right.id, 0), { exact: false })).toBeInTheDocument()
    expect(screen.getByText('+10 points')).toBeInTheDocument()
    // The result is still what takes focus and is read (#142).
    expect(screen.getByRole('group', { name: 'Correct.' })).toHaveFocus()
  })

  it('leads with the explanation of why it is right, not a bare "Correct"', () => {
    const why = 'B comes next: it was queued before C.'
    panel(false)({ ...right, feedback: why })
    const shown = screen.getByRole('group', { name: `Correct. ${why}` })
    expect(shown).toHaveFocus()
    expect(within(shown).queryByText('Correct', { exact: true })).toBeNull() // no title above it
    expect(shown).toHaveTextContent(why)
  })

  it('adds a remark on progress from the skill profile', () => {
    panel(false, eight({ 1: { level: 'practising' }, 4: { level: 'secure' } }))(right)
    expect(screen.getByText("You've practised 2 of 8 objectives so far.")).toBeInTheDocument()
  })

  it('shows only the explanation and the points with encouraging comments off', () => {
    setPreference('comments', false)
    panel(false, eight({ 1: { level: 'practising' } }))(right)
    expect(screen.queryByText(praiseFor(right.id, 0), { exact: false })).toBeNull()
    expect(screen.queryByText(/objectives so far/)).toBeNull()
    expect(screen.getByText('+10 points')).toBeInTheDocument()
  })

  it('shows no points while rewards are hidden, or when the answer earned none', () => {
    panel(true)(right)
    expect(screen.queryByText(/points/)).toBeNull()
    expect(screen.getByText(praiseFor(right.id, 0), { exact: false })).toBeInTheDocument()
  })

  it('shows no points for an answer that earned none', () => {
    panel(false)({ ...right, points: 0 })
    expect(screen.queryByText(/points/)).toBeNull()
  })

  it('keeps a wrong answer calm', () => {
    panel(false)({ ...right, correct: false, feedback: 'Not quite.', points: 0 })
    expect(document.querySelector('[data-success-moment]')).toBeNull()
  })

  it('says nothing more on a mastery check answer', () => {
    panel(false)({ ...right, correct: null, withheld: true, feedback: 'Answer recorded.' })
    expect(document.querySelector('[data-success-moment]')).toBeNull()
  })

  it('is not replayed for an answer restored when the page opens (#171)', () => {
    const client = new QueryClient()
    render(
      <QueryClientProvider client={client}>
        <FeedbackPanel result={right} />
      </QueryClientProvider>,
    )
    expect(document.querySelector('[data-success-moment]')).toBeNull()
  })

  it('bursts confetti from the result, and offers to turn it off there', async () => {
    media()
    drawableCanvas()
    panel(false)(right)
    expect(document.querySelector('canvas[data-confetti="small"]')).not.toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Turn off confetti' }))
    expect(confettiEnabled()).toBe(false)
    expect(document.querySelector('canvas')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Turn off confetti' })).toBeNull()
  })
})

// --- The skill profile -------------------------------------------------------------------------

describe('the skill profile', () => {
  it('names all eight objectives with where the student is, in words', () => {
    render(
      <SkillProfile
        skills={eight({
          1: { level: 'secure', answered: 4, onYourOwn: 4 },
          2: { level: 'practising', answered: 1 },
        })}
      />,
    )
    const rows = screen.getAllByRole('listitem')
    expect(rows).toHaveLength(8)
    expect(rows[0]).toHaveTextContent('Key terms')
    expect(rows[0]).toHaveTextContent('Secure in practice')
    expect(rows[1]).toHaveTextContent('Practising')
    expect(rows[2]).toHaveTextContent('Not started')
  })

  it('shows gold, bronze or not yet once the mastery check has a result', () => {
    render(
      <SkillProfile
        skills={eight({
          1: { result: 'met_independently' },
          2: { result: 'met_with_support' },
          3: { result: 'not_yet', level: 'practising', answered: 2 },
        })}
      />,
    )
    const rows = screen.getAllByRole('listitem')
    expect(rows[0]).toHaveTextContent('Gold: met on your own')
    expect(rows[1]).toHaveTextContent('Bronze: met with support')
    expect(rows[2]).toHaveTextContent('Not yet')
  })

  it('opens a row to show the objective in full and the evidence, not a percentage', async () => {
    render(
      <SkillProfile skills={eight({ 5: { level: 'practising', answered: 3, onYourOwn: 2 } })} />,
    )
    const row = screen.getAllByRole('listitem')[4]
    await userEvent.click(within(row).getByText('Tracing BFS'))
    expect(row.querySelector('details')).toHaveAttribute('open')
    expect(row).toHaveTextContent('Objective 5 in full.')
    expect(row).toHaveTextContent(
      '3 of 4 practice questions answered, 2 right without hint 3 or 4.',
    )
    expect(row).not.toHaveTextContent('%')
  })

  it('marks the objectives this module teaches', () => {
    render(<SkillProfile skills={eight()} highlight={[2]} />)
    expect(screen.getAllByRole('listitem')[1]).toHaveTextContent('(this module)')
    expect(screen.getAllByRole('listitem')[0]).not.toHaveTextContent('(this module)')
  })
})

// --- On the pages ------------------------------------------------------------------------------

function api({
  hideRewards = false,
  skills = { objectives: eight(), modules: [medal(4)] } as Skills,
  modules = [finished],
}: { hideRewards?: boolean; skills?: Skills; modules?: ModuleSummary[] } = {}) {
  return fakeApi({
    user: ada,
    overrides: {
      'GET /api/modules': () => Response.json(modules),
      'GET /api/me/skills': () => Response.json(skills),
      'GET /api/rewards': () =>
        Response.json({
          hideRewards,
          points: 135,
          badges: [
            {
              badge: 'first-module',
              ref: '',
              tier: null,
              awardedAt: '2026-11-01',
              upgradedAt: null,
              seen: true,
            },
            {
              badge: 'lo1',
              ref: '',
              tier: 'bronze',
              awardedAt: '2026-11-03',
              upgradedAt: null,
              seen: true,
            },
          ],
        }),
    },
  })
}

describe('the module map', () => {
  it('shows the skill profile and a finished module’s medal with its rule', async () => {
    api()
    renderApp('/')
    expect(await screen.findByRole('heading', { name: 'Skill profile' })).toBeInTheDocument()
    expect(
      await screen.findByRole('img', {
        name: 'Module 3: Gold medal: every activity right first time, without hint 3 or 4',
      }),
    ).toBeInTheDocument()
  })

  it('shows no medal while points and badges are hidden', async () => {
    api({ hideRewards: true })
    renderApp('/')
    expect(await screen.findByRole('heading', { name: 'Skill profile' })).toBeInTheDocument()
    expect(screen.queryByRole('img', { name: /medal/ })).toBeNull()
  })

  it('shows no medal on a module that isn’t finished', async () => {
    api({ modules: [{ ...finished, status: 'in_progress' }] })
    renderApp('/')
    expect(await screen.findByRole('heading', { name: 'Skill profile' })).toBeInTheDocument()
    expect(screen.queryByRole('img', { name: /medal/ })).toBeNull()
  })
})

describe('the progress panel on an activity page', () => {
  const activity = {
    'GET /api/activities/7': () =>
      Response.json({
        id: 7,
        kind: 'multiple_choice',
        title: 'Pick one',
        visible: true,
        config: { prompt: 'Q', options: [{ id: 'a', label: 'A' }] },
      }),
    'GET /api/activities/7/hints': () => Response.json([]),
  }

  it('sits beside the lesson on wide screens: points, the profile and recent badges', async () => {
    media('(min-width: 64rem)')
    fakeApi({
      user: ada,
      overrides: {
        ...activity,
        'GET /api/me/skills': () => Response.json({ objectives: eight(), modules: [] }),
        'GET /api/rewards': () =>
          Response.json({
            hideRewards: false,
            points: 135,
            badges: [
              {
                badge: 'first-module',
                ref: '',
                tier: null,
                awardedAt: '2026-11-01',
                upgradedAt: null,
                seen: true,
              },
            ],
          }),
      },
    })
    renderApp('/activities/7')
    const aside = await screen.findByRole('complementary', { name: 'Your progress' })
    await waitFor(() => expect(aside).toHaveTextContent('135 points'))
    expect(within(aside).getByRole('region', { name: 'Skill profile' })).toBeInTheDocument()
    expect(within(aside).getByRole('link', { name: 'See your badges' })).toBeInTheDocument()
  })

  it('is a closed strip under the lesson on narrow screens, without points if hidden', async () => {
    fakeApi({
      user: ada,
      overrides: {
        ...activity,
        'GET /api/me/skills': () => Response.json({ objectives: eight(), modules: [] }),
        'GET /api/rewards': () => Response.json({ hideRewards: true, points: 135, badges: [] }),
      },
    })
    renderApp('/activities/7')
    const strip = (await screen.findByText('Your progress')).closest('details')
    expect(strip).not.toHaveAttribute('open')
    expect(screen.queryByRole('complementary')).toBeNull()
    await waitFor(() => expect(strip).not.toHaveTextContent('points'))
  })
})

describe('the mastery report', () => {
  const ready = {
    ready: true,
    objectives: [
      {
        id: 1,
        text: 'One',
        criterion: 'c',
        state: 'met_independently',
        answered: 1,
        total: 1,
        review: null,
      },
    ],
  }

  it('shows the skill profile with the results, and a full burst once when ready', async () => {
    media()
    drawableCanvas()
    fakeApi({
      user: ada,
      overrides: {
        'GET /api/me/report': () => Response.json(ready),
        'GET /api/me/skills': () =>
          Response.json({ objectives: [skill(1, { result: 'met_independently' })], modules: [] }),
      },
    })
    renderApp('/report')
    expect(await screen.findByText('Gold: met on your own')).toBeInTheDocument()
    expect(document.querySelector('canvas[data-confetti="big"]')).not.toBeNull()
    expect(celebrateOnce('ready-for-the-lecture')).toBe(false) // already played on this device
  })
})

describe('the feedback switches on the profile page', () => {
  it('are together under "Feedback", on by default, and kept on this device', async () => {
    fakeApi({ user: ada })
    renderApp('/profile')
    const section = (await screen.findByRole('heading', { name: 'Feedback' })).closest('section')!
    const box = within(section).getByRole('checkbox', {
      name: 'Confetti when you get something right',
    })
    const comments = within(section).getByRole('checkbox', { name: 'Encouraging comments' })
    expect(box).toBeChecked()
    expect(comments).toBeChecked()
    await userEvent.click(box)
    await userEvent.click(comments)
    expect(box).not.toBeChecked()
    expect(confettiEnabled()).toBe(false)
    expect(localStorage.getItem('ctrl-academy.comments')).toBe('off')
  })
})
