import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ada, fakeApi, renderApp } from '../../test/app.tsx'
import type { AttemptResult } from '../activities/activities.types.ts'
import { CelebrationAllowed } from '../activities/celebration.ts'
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
import { HiddenNote, UNDO_MS } from './HiddenNote.tsx'
import { PRAISE_LINES, praiseFor, progressRemark } from './praise.ts'
import { setPreference, setPreferenceOwner } from './preferences.ts'
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
    <MemoryRouter>
      <QueryClientProvider client={client}>
        <FeedbackPanel result={result} />
      </QueryClientProvider>
    </MemoryRouter>
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
    // One quiet "⋯" beside the moment (#214), opening the ways to turn its parts off.
    const more = screen.getByRole('button', { name: 'Hide options for this feedback' })
    expect(more).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(more)
    expect(more).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('button', { name: 'Hide encouraging comments' })).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: 'Turn off confetti' }))
    expect(confettiEnabled()).toBe(false)
    expect(document.querySelector('canvas')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Turn off confetti' })).toBeNull()
    // Focus isn't dropped on the page with the button: it goes to the line saying it is off,
    // which links to the settings and offers Undo.
    const note = screen.getByText(/Confetti is off/).closest('output')!
    expect(note).toHaveFocus()
    expect(within(note).getByRole('link', { name: 'your profile' })).toHaveAttribute(
      'href',
      '/profile#what-you-see',
    )
    await userEvent.click(within(note).getByRole('button', { name: 'Undo' }))
    expect(confettiEnabled()).toBe(true)
  })

  it('hides encouraging comments from the moment itself', async () => {
    panel(false)(right)
    await userEvent.click(screen.getByRole('button', { name: 'Hide options for this feedback' }))
    await userEvent.click(screen.getByRole('button', { name: 'Hide encouraging comments' }))
    expect(screen.queryByText(praiseFor(right.id, 0), { exact: false })).toBeNull()
    expect(screen.getByText(/Encouraging comments hidden/).closest('output')).toHaveFocus()
    expect(localStorage.getItem('ctrl-academy.comments')).toBe('off')
  })

  it('closes the "⋯" with Escape and gives focus back to it', async () => {
    panel(false)(right)
    const more = screen.getByRole('button', { name: 'Hide options for this feedback' })
    await userEvent.click(more)
    // Focus goes to the first way to turn something off.
    expect(document.activeElement).toHaveTextContent(
      /^(Turn off confetti|Hide encouraging comments)$/,
    )
    await userEvent.keyboard('{Escape}')
    expect(more).toHaveAttribute('aria-expanded', 'false')
    expect(more).toHaveFocus()
  })

  it('is never shown in the mastery check, not even for its recall questions (#215)', () => {
    media()
    drawableCanvas()
    const client = new QueryClient()
    client.setQueryData(rewardsKey, { hideRewards: false, points: 0, badges: [] })
    const view = (result: AttemptResult | undefined) => (
      <QueryClientProvider client={client}>
        <CelebrationAllowed.Provider value={false}>
          <FeedbackPanel result={result} />
        </CelebrationAllowed.Provider>
      </QueryClientProvider>
    )
    const { rerender } = render(view(undefined))
    rerender(view(right))
    expect(document.querySelector('[data-success-moment]')).toBeNull()
    expect(document.querySelector('canvas')).toBeNull()
    expect(screen.queryByText(/points/)).toBeNull()
    expect(screen.getByRole('group', { name: 'Correct.' })).toHaveFocus()
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
      '3 of 4 practice questions answered, 2 right at the first try, without hint 3 or 4.',
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
        name: 'Module 3: Gold medal: every activity right first time, without a hint',
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

describe('the switches on the profile page', () => {
  it('are together under "What you see while you learn", on by default, and kept on this device', async () => {
    fakeApi({ user: ada })
    renderApp('/profile')
    const section = (
      await screen.findByRole('heading', { name: 'What you see while you learn' })
    ).closest('section')!
    await waitFor(() => expect(within(section).getAllByRole('checkbox')).toHaveLength(5))
    for (const name of [
      'Points and badges',
      'Skill profile',
      'Progress panel beside lessons',
      'Confetti when you get something right',
      'Encouraging comments',
    ])
      expect(within(section).getByRole('checkbox', { name })).toBeChecked()
    expect(section).toHaveTextContent(
      'Your mastery report and your quick check results are always shown.',
    )
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
    // Kept for this student on this device: a key with her id (#215 review).
    expect(localStorage.getItem(`ctrl-academy.${ada.id}.comments`)).toBe('off')
    expect(localStorage.getItem('ctrl-academy.comments')).toBeNull()
    // Each switch is described by its explanation and by where it is kept.
    expect(box).toHaveAccessibleDescription(/A short burst for a right answer.*kept on this device/)
    expect(comments).toHaveAccessibleDescription(/A short line under a right answer.*for you only/)
  })

  it('are each student’s own on a shared computer (#215 review)', () => {
    setPreferenceOwner(1)
    setPreference('confetti', false)
    expect(confettiEnabled()).toBe(false)
    setPreferenceOwner(2)
    expect(confettiEnabled()).toBe(true)
    setPreferenceOwner(1)
    expect(confettiEnabled()).toBe(false)
  })
})

describe('the progress panel: minimised, hidden or off (#214)', () => {
  const overrides = {
    'GET /api/activities/7': () =>
      Response.json({
        id: 7,
        kind: 'multiple_choice',
        title: 'Pick one',
        visible: true,
        config: { prompt: 'Q', options: [{ id: 'a', label: 'A' }] },
      }),
    'GET /api/activities/7/hints': () => Response.json([]),
    'GET /api/me/skills': () => Response.json({ objectives: eight(), modules: [] }),
    'GET /api/rewards': () => Response.json({ hideRewards: false, points: 135, badges: [] }),
  }

  it('minimises to a rail with its count, which opens it again; nothing else changes', async () => {
    media('(min-width: 64rem)')
    fakeApi({ user: ada, overrides })
    renderApp('/activities/7')
    const aside = await screen.findByRole('complementary', { name: 'Your progress' })
    await waitFor(() => expect(aside).toHaveTextContent('135 points'))
    const toggle = within(aside).getByRole('button', { name: 'Your progress' })
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    await userEvent.click(toggle)
    const rail = await screen.findByRole('complementary', { name: 'Your progress' })
    const open = within(rail).getByRole('button', { name: 'Your progress, 135 points' })
    expect(open).toHaveAttribute('aria-expanded', 'false')
    expect(within(rail).queryByRole('region', { name: 'Skill profile' })).toBeNull()
    expect(localStorage.getItem(`ctrl-academy.${ada.id}.minimised.progressPanel`)).toBe('yes')
    // The lesson gets the width: the page's column for the panel is a narrow rail.
    expect(rail.parentElement!.className).toContain('lg:grid-cols-[minmax(0,48rem)_3rem]')
    await userEvent.click(open)
    expect(await screen.findByRole('region', { name: 'Skill profile' })).toBeInTheDocument()
  })

  it('hides the skill profile from its "⋯", and shows the note where it was', async () => {
    media('(min-width: 64rem)')
    fakeApi({ user: ada, overrides })
    renderApp('/activities/7')
    const aside = await screen.findByRole('complementary', { name: 'Your progress' })
    await within(aside).findByRole('region', { name: 'Skill profile' })
    await userEvent.click(
      within(aside).getByRole('button', { name: 'Hide options for your progress' }),
    )
    await userEvent.click(within(aside).getByRole('button', { name: 'Hide skill profile' }))
    expect(within(aside).queryByRole('region', { name: 'Skill profile' })).toBeNull()
    expect(
      within(aside)
        .getByText(/Skill profile hidden/)
        .closest('output'),
    ).toHaveFocus()
  })

  it('hides the whole panel from its "⋯": the lesson takes the width', async () => {
    media('(min-width: 64rem)')
    fakeApi({ user: ada, overrides })
    renderApp('/activities/7')
    const aside = await screen.findByRole('complementary', { name: 'Your progress' })
    const page = aside.parentElement!
    await userEvent.click(
      within(aside).getByRole('button', { name: 'Hide options for your progress' }),
    )
    await userEvent.click(within(aside).getByRole('button', { name: 'Hide progress panel' }))
    expect(screen.queryByRole('complementary')).toBeNull()
    expect(screen.getByText(/Progress panel hidden/).closest('output')).toHaveFocus()
    expect(page.className).not.toContain('lg:grid-cols')
  })

  it('shows no panel and no strip once switched off, and none of its skill profile', async () => {
    localStorage.setItem(`ctrl-academy.${ada.id}.progressPanel`, 'off')
    fakeApi({ user: ada, overrides })
    renderApp('/activities/7')
    await screen.findByText('Q')
    expect(screen.queryByText('Your progress')).toBeNull()
    media('(min-width: 64rem)')
  })

  it('leaves the skill profile out of the panel when it is switched off', async () => {
    media('(min-width: 64rem)')
    localStorage.setItem(`ctrl-academy.${ada.id}.skillProfile`, 'off')
    fakeApi({ user: ada, overrides })
    renderApp('/activities/7')
    const aside = await screen.findByRole('complementary', { name: 'Your progress' })
    await waitFor(() => expect(aside).toHaveTextContent('135 points'))
    expect(within(aside).queryByRole('region', { name: 'Skill profile' })).toBeNull()
  })

  it('offers the same "⋯" inside the strip on a phone', async () => {
    fakeApi({ user: ada, overrides })
    renderApp('/activities/7')
    const strip = (await screen.findByText('Your progress')).closest('details')!
    await userEvent.click(within(strip).getByText('Your progress'))
    await userEvent.click(
      within(strip).getByRole('button', { name: 'Hide options for your progress' }),
    )
    await userEvent.click(within(strip).getByRole('button', { name: 'Hide progress panel' }))
    expect(screen.queryByRole('group', { name: /Your progress/ })).toBeNull()
    expect(screen.getByText(/Progress panel hidden/).closest('output')).toHaveFocus()
  })
})

describe('the note left where something was hidden', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('keeps Undo while the pointer is over it or focus is on Undo, and drops it after', () => {
    vi.useFakeTimers()
    render(
      <MemoryRouter>
        <HiddenNote text="Confetti is off." onUndo={() => {}} />
      </MemoryRouter>,
    )
    const note = document.querySelector('[data-hidden-note]') as HTMLElement
    const undo = screen.getByRole('button', { name: 'Undo' })
    fireEvent.pointerEnter(note)
    act(() => void vi.advanceTimersByTime(UNDO_MS * 2))
    expect(screen.getByRole('button', { name: 'Undo' })).toBeInTheDocument()
    fireEvent.pointerLeave(note)
    act(() => undo.focus())
    act(() => void vi.advanceTimersByTime(UNDO_MS * 2))
    expect(screen.getByRole('button', { name: 'Undo' })).toBeInTheDocument()
    act(() => undo.blur())
    act(() => void vi.advanceTimersByTime(UNDO_MS))
    expect(screen.queryByRole('button', { name: 'Undo' })).toBeNull()
  })
})
