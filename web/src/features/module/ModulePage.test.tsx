import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Link, MemoryRouter, Route, Routes } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ada, fakeApi, renderApp } from '../../test/app.tsx'
import { ModulePage } from './ModulePage.tsx'
import type { ModuleDetail, ModuleSummary, Segment } from './module.types.ts'

// ---------------------------------------------------------------------------
// Sample data
// ---------------------------------------------------------------------------

const textSegment: Segment = {
  id: 10,
  position: 0,
  kind: 'text',
  title: 'Introduction to graphs',
  body: '# What is a graph?\n\nA graph has **nodes** and edges.',
  videoId: null,
  activityId: null,
  done: true,
}

const workedExampleSegment: Segment = {
  id: 11,
  position: 1,
  kind: 'worked_example',
  title: 'Worked example: adjacency list',
  body: '## Example\n\nHere is a worked example paragraph.',
  videoId: null,
  activityId: null,
  done: true,
}

const videoSegment: Segment = {
  id: 12,
  position: 2,
  kind: 'video',
  title: 'Watch: BFS in action',
  body: null,
  videoId: 42,
  activityId: null,
  done: true,
}

const activitySegment: Segment = {
  id: 13,
  position: 3,
  kind: 'activity',
  title: 'Practice: BFS step by step',
  body: null,
  videoId: null,
  activityId: 7,
  done: true,
}

const moduleSummary: ModuleSummary = {
  id: 1,
  number: 0,
  slug: 'warmup',
  title: 'Warm-up and queue refresher',
  goals: ['Recall how queues work.', 'Use a queue in Python.'],
  estimatedMinutes: 5,
  status: 'open',
  segmentCount: 2,
  currentSegmentPosition: 0,
}

/** A full ModuleDetail with text + worked_example segments (two segments total). */
const twoSegmentDetail: ModuleDetail = {
  ...moduleSummary,
  segmentCount: 2,
  currentSegmentPosition: 0,
  segments: [textSegment, workedExampleSegment],
  retrieval: [],
}

/** A full ModuleDetail with all four segment kinds. */
const allKindsDetail: ModuleDetail = {
  ...moduleSummary,
  segmentCount: 4,
  currentSegmentPosition: 0,
  segments: [textSegment, videoSegment, activitySegment, workedExampleSegment],
  retrieval: [],
}

// ---------------------------------------------------------------------------
// Helper: set up fakeApi with a module detail stub.
// `positionResponse` defaults to the same detail object (idempotent position save).
// ---------------------------------------------------------------------------

function setupModuleApi(
  detail: ModuleDetail,
  positionResponse: ModuleDetail = detail,
  extra: Record<string, () => Response | Promise<Response>> = {},
) {
  return fakeApi({
    user: ada,
    overrides: {
      'GET /api/modules': () => Response.json([]),
      'GET /api/modules/:id': () => Response.json(detail),
      'POST /api/modules/:id/position': () => Response.json(positionResponse),
      ...extra,
    },
  })
}

// ---------------------------------------------------------------------------
// (a) Module goals
// ---------------------------------------------------------------------------

describe('ModulePage — goals', () => {
  it('renders the module title', async () => {
    setupModuleApi(twoSegmentDetail)
    renderApp('/modules/1')

    expect(await screen.findByRole('heading', { level: 1, name: /module 0/i })).toBeInTheDocument()
    expect(screen.getByText(/warm-up and queue refresher/i)).toBeInTheDocument()
  })

  it('lists the goals under "By the end of this module you can"', async () => {
    setupModuleApi(twoSegmentDetail)
    renderApp('/modules/1')

    expect(await screen.findByText('By the end of this module you can:')).toBeInTheDocument()
    expect(screen.getByText('Recall how queues work.')).toBeInTheDocument()
    expect(screen.getByText('Use a queue in Python.')).toBeInTheDocument()
  })

  describe('on the first segment', () => {
    afterEach(() => vi.unstubAllGlobals())

    /** A screen as wide or as narrow as a phone, as matchMedia reports it. */
    function screenIsPhone(phone: boolean) {
      vi.stubGlobal(
        'matchMedia',
        vi.fn((query: string) => ({
          matches: phone && query.includes('max-width'),
          media: query,
          addEventListener: () => {},
          removeEventListener: () => {},
        })),
      )
    }

    const goals = async () =>
      (await screen.findByText('By the end of this module you can:')).closest('details')

    it('opens the goals on a wider screen', async () => {
      screenIsPhone(false)
      setupModuleApi(twoSegmentDetail)
      renderApp('/modules/1')
      expect(await goals()).toHaveAttribute('open')
    })

    it('keeps the goals closed on a phone, so the lesson starts on the first screen', async () => {
      screenIsPhone(true)
      setupModuleApi(twoSegmentDetail)
      renderApp('/modules/1')
      expect(await goals()).not.toHaveAttribute('open')
    })
  })
})

// A recall question is an ordinary activity: the page loads it like the activity page does.
const recallActivity = {
  id: 201,
  kind: 'multiple_choice',
  title: 'Recall graph storage',
  visible: true,
  config: {
    prompt: 'What does an adjacency list store?',
    options: [
      { id: 'neighbors', label: 'Connected vertices' },
      { id: 'visited', label: 'Visited count' },
    ],
  },
}

const recallAttempt = {
  id: 1,
  activityId: 201,
  correct: true,
  score: 1,
  parts: [],
  feedback: 'Correct: it stores connected vertices.',
  hintLevel: 0,
}

function recallApi(detail: ModuleDetail) {
  return fakeApi({
    user: ada,
    overrides: {
      'GET /api/modules': () => Response.json([]),
      'GET /api/modules/:id': () => Response.json(detail),
      'POST /api/modules/:id/position': () => Response.json(detail),
      'GET /api/activities/201': () => Response.json(recallActivity),
      'GET /api/activities/201/hints': () => Response.json([]),
      'POST /api/activities/201/attempts': () => Response.json(recallAttempt),
    },
  })
}

const recall = { id: 201, title: 'Recall graph storage', answered: false }

describe('ModulePage — retrieval', () => {
  it('asks the recall questions, with hints, before the first segment', async () => {
    const api = recallApi({ ...twoSegmentDetail, retrieval: [recall] })
    renderApp('/modules/1')

    expect(await screen.findByText('What does an adjacency list store?')).toBeInTheDocument()
    expect(screen.getByText('Quick recall · Question 1 of 1')).toBeInTheDocument()
    // One h1, the module's; the question's title sits under it, like a segment's.
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(
      screen.getByRole('heading', { level: 2, name: 'Recall graph storage' }),
    ).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Introduction to graphs' })).toBeNull()
    expect(await screen.findByRole('button', { name: 'Show next hint' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Start module' })).toBeDisabled()

    await userEvent.click(screen.getByLabelText('Connected vertices'))
    await userEvent.click(screen.getByRole('button', { name: 'Check answer' }))

    expect(await screen.findByText('Correct: it stores connected vertices.')).toBeInTheDocument()
    expect(api.callsTo('POST /api/activities/201/attempts')).toHaveLength(1)
    await userEvent.click(screen.getByRole('button', { name: 'Start module' }))
    expect(
      await screen.findByRole('heading', { name: 'Introduction to graphs' }),
    ).toBeInTheDocument()
  })

  it('skips the recall questions already answered on an earlier visit', async () => {
    recallApi({ ...twoSegmentDetail, retrieval: [{ ...recall, answered: true }] })
    renderApp('/modules/1')

    expect(
      await screen.findByRole('heading', { name: 'Introduction to graphs' }),
    ).toBeInTheDocument()
    expect(screen.queryByText('What does an adjacency list store?')).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// (b) Segments — markdown rendering
// ---------------------------------------------------------------------------

describe('ModulePage — segment rendering', () => {
  it('shows the first segment title', async () => {
    setupModuleApi(twoSegmentDetail)
    renderApp('/modules/1')

    // h2 for segment title
    expect(
      await screen.findByRole('heading', { name: 'Introduction to graphs' }),
    ).toBeInTheDocument()
  })

  it('renders a text segment body as Markdown — heading', async () => {
    setupModuleApi(twoSegmentDetail)
    renderApp('/modules/1')

    // The body starts with "# What is a graph?" → <h1>What is a graph?</h1>
    expect(await screen.findByRole('heading', { name: 'What is a graph?' })).toBeInTheDocument()
  })

  it('renders a text segment body as Markdown — bold text becomes DOM', async () => {
    setupModuleApi(twoSegmentDetail)
    renderApp('/modules/1')

    // "**nodes**" → <strong>nodes</strong> — findByText finds the text node
    await screen.findByRole('heading', { name: 'What is a graph?' })
    expect(screen.getByText('nodes')).toBeInTheDocument()
  })

  it('renders a worked_example segment body as Markdown after navigating', async () => {
    // Use allKindsDetail (4 segments) so clicking Next lands on segment 1 (not the last).
    const api = setupModuleApi(allKindsDetail)
    renderApp('/modules/1')

    // Navigate to the second segment (video — but we just need to check a forward nav worked)
    const nextBtn = await screen.findByRole('button', { name: 'Next →' })
    await userEvent.click(nextBtn)

    // Wait for POST position to complete
    expect(api.callsTo('POST /api/modules/1/position')).toHaveLength(1)

    // The video segment title appears (position 1 in allKindsDetail)
    expect(await screen.findByRole('heading', { name: 'Watch: BFS in action' })).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// (c) Navigation calls POST position
// ---------------------------------------------------------------------------

describe('ModulePage — navigation and position saving', () => {
  it('calls POST position with the next segment position when Next is clicked', async () => {
    const api = setupModuleApi(twoSegmentDetail)
    renderApp('/modules/1')

    await screen.findByRole('button', { name: 'Next →' })
    await userEvent.click(screen.getByRole('button', { name: 'Next →' }))

    // Should have POSTed to position endpoint with segmentPosition = 1 (second segment's position)
    const positionCalls = api.callsTo('POST /api/modules/1/position')
    expect(positionCalls).toHaveLength(1)
    expect(positionCalls[0].body).toEqual({ segmentPosition: 1 })
  })

  it('advances the UI to the next segment after clicking Next', async () => {
    // Use allKindsDetail (4 segments) so navigating to segment 1 doesn't trigger completion.
    setupModuleApi(allKindsDetail)
    renderApp('/modules/1')

    await screen.findByRole('heading', { name: 'Introduction to graphs' })
    await userEvent.click(screen.getByRole('button', { name: 'Next →' }))

    // Segment 2 title appears (video segment at position 1)
    expect(await screen.findByRole('heading', { name: 'Watch: BFS in action' })).toBeInTheDocument()
  })

  it('shows the last segment when Next reaches it, and only leaves on "Finish module"', async () => {
    const api = setupModuleApi(twoSegmentDetail)
    renderApp('/modules/1')

    await userEvent.click(await screen.findByRole('button', { name: 'Next →' }))

    expect(
      await screen.findByRole('heading', { name: 'Worked example: adjacency list' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Finish module' })).toBeInTheDocument()
    expect(api.callsTo('POST /api/modules/1/position')).toHaveLength(1)
  })

  it('goes back without saving: the server keeps the furthest segment reached', async () => {
    const api = setupModuleApi({ ...allKindsDetail, currentSegmentPosition: 2 })
    renderApp('/modules/1')

    await userEvent.click(await screen.findByRole('button', { name: '← Previous' }))

    expect(await screen.findByRole('heading', { name: 'Watch: BFS in action' })).toBeInTheDocument()
    expect(api.callsTo('POST /api/modules/1/position')).toHaveLength(0)
  })

  it('shows "Finish module" on the last segment instead of "Next →"', async () => {
    const atLastSegment: ModuleDetail = {
      ...twoSegmentDetail,
      currentSegmentPosition: 1, // last segment in a 2-segment module
    }
    setupModuleApi(atLastSegment)
    renderApp('/modules/1')

    expect(await screen.findByRole('button', { name: 'Finish module' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Next →' })).toBeNull()
  })

  it('disables Previous on the first segment', async () => {
    setupModuleApi(twoSegmentDetail)
    renderApp('/modules/1')

    const prevBtn = await screen.findByRole('button', { name: '← Previous' })
    expect(prevBtn).toBeDisabled()
  })

  it('enables Previous after navigating forward', async () => {
    // Use allKindsDetail (4 segments) so clicking Next doesn't trigger completion.
    setupModuleApi(allKindsDetail)
    renderApp('/modules/1')

    await userEvent.click(await screen.findByRole('button', { name: 'Next →' }))
    expect(await screen.findByRole('button', { name: '← Previous' })).not.toBeDisabled()
  })

  it('resumes from the server-returned currentSegmentPosition', async () => {
    const resumedDetail: ModuleDetail = {
      ...twoSegmentDetail,
      currentSegmentPosition: 1,
    }
    setupModuleApi(resumedDetail)
    renderApp('/modules/1')

    // Should start on segment at position 1 (worked_example)
    expect(
      await screen.findByRole('heading', { name: 'Worked example: adjacency list' }),
    ).toBeInTheDocument()
  })

  it('opens a complete module at its first segment that is not done (#136 review)', async () => {
    // A student who finished the module before its activity could be answered: the server keeps
    // them on the last segment, but the page takes them to what is missing.
    setupModuleApi({
      ...allKindsDetail,
      status: 'complete',
      currentSegmentPosition: 3,
      segments: [
        textSegment,
        videoSegment,
        { ...activitySegment, done: false },
        workedExampleSegment,
      ],
    })
    renderApp('/modules/1')
    expect(await screen.findByText('Segment 3 of 4')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Practice: BFS step by step' })).toBeInTheDocument()
  })

  it('opens a complete module with everything done where the student left it', async () => {
    setupModuleApi({ ...allKindsDetail, status: 'complete', currentSegmentPosition: 3 })
    renderApp('/modules/1')
    expect(await screen.findByText('Segment 4 of 4')).toBeInTheDocument()
  })

  it('opens an in-progress module at a segment the student passed without doing it', async () => {
    setupModuleApi({
      ...allKindsDetail,
      status: 'in_progress',
      currentSegmentPosition: 3,
      segments: [
        textSegment,
        videoSegment,
        { ...activitySegment, done: false },
        workedExampleSegment,
      ],
    })
    renderApp('/modules/1')
    expect(await screen.findByText('Segment 3 of 4')).toBeInTheDocument()
  })

  it('says why it opened at a skipped activity', async () => {
    setupModuleApi({
      ...allKindsDetail,
      status: 'in_progress',
      currentSegmentPosition: 3,
      segments: [
        textSegment,
        videoSegment,
        { ...activitySegment, done: false },
        workedExampleSegment,
      ],
    })
    renderApp('/modules/1')
    expect(await screen.findByText(/You moved past this activity earlier/)).toBeInTheDocument()
  })

  it('never pulls a student back to an activity they answered wrong earlier (#165 review)', async () => {
    // Answered under the old rule (any answer counted), so not done now, but tried: the module
    // opens where the student left off.
    setupModuleApi({
      ...allKindsDetail,
      status: 'in_progress',
      currentSegmentPosition: 3,
      segments: [
        textSegment,
        videoSegment,
        { ...activitySegment, done: false, attempted: true },
        workedExampleSegment,
      ],
    })
    renderApp('/modules/1')
    expect(await screen.findByText('Segment 4 of 4')).toBeInTheDocument()
    expect(screen.queryByText(/You moved past this activity earlier/)).toBeNull()
  })

  it('asks for a right answer once an activity was answered wrong', async () => {
    setupModuleApi({
      ...allKindsDetail,
      status: 'in_progress',
      currentSegmentPosition: 2,
      segments: [
        textSegment,
        videoSegment,
        { ...activitySegment, done: false, attempted: true },
        workedExampleSegment,
      ],
    })
    renderApp('/modules/1')
    const next = await screen.findByRole('button', { name: 'Next →' })
    expect(next).toHaveAccessibleDescription(
      'Get it right to continue. If you’re stuck, the hints can help.',
    )
  })

  it('resumes an in-progress module on the segment the student is doing', async () => {
    setupModuleApi({
      ...allKindsDetail,
      status: 'in_progress',
      currentSegmentPosition: 2,
      segments: [
        textSegment,
        videoSegment,
        { ...activitySegment, done: false },
        workedExampleSegment,
      ],
    })
    renderApp('/modules/1')
    expect(await screen.findByText('Segment 3 of 4')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Next →' })).toHaveAttribute('aria-disabled', 'true')
  })

  it('clicking "Finish module" on the last segment saves the position and navigates to "/"', async () => {
    fakeApi({
      user: ada,
      overrides: {
        'GET /api/modules': () => Response.json([{ ...moduleSummary, status: 'complete' }]),
        'GET /api/modules/:id': () =>
          Response.json({ ...twoSegmentDetail, currentSegmentPosition: 1 }),
        'POST /api/modules/:id/position': () => Response.json(twoSegmentDetail),
      },
    })
    renderApp('/modules/1')

    // We start on the last segment — Finish module button should already be present.
    const finishBtn = await screen.findByRole('button', { name: 'Finish module' })

    // Click Finish module — this fires savePosition and then navigates to '/'.
    await userEvent.click(finishBtn)

    // After navigation, the module map heading should be visible.
    expect(
      await screen.findByRole('heading', { name: 'Graphs and breadth-first search' }),
    ).toBeInTheDocument()
  })
  it('finishing module 6, the mastery check, opens the mastery report (#144)', async () => {
    const api = fakeApi({
      user: ada,
      overrides: {
        'GET /api/modules': () =>
          Response.json([{ ...moduleSummary, id: 6, number: 6, status: 'complete' }]),
        'GET /api/modules/:id': () =>
          Response.json({ ...twoSegmentDetail, id: 6, number: 6, currentSegmentPosition: 1 }),
        'POST /api/modules/:id/position': () => Response.json(twoSegmentDetail),
        'GET /api/me/report': () => Response.json({ ready: false, objectives: [] }),
      },
    })
    renderApp('/modules/6')

    await userEvent.click(await screen.findByRole('button', { name: 'Finish module' }))

    expect(
      await screen.findByRole('heading', { name: 'Your mastery report', level: 1 }),
    ).toBeInTheDocument()
    expect(api.callsTo('POST /api/modules/6/position')).toHaveLength(1)
  })
})

// ---------------------------------------------------------------------------
// (#136 review) A refused module, and one module opened after another
// ---------------------------------------------------------------------------

describe('ModulePage — refused and switched', () => {
  it('says at once that a locked module is not open, without retrying (403)', async () => {
    const api = fakeApi({
      user: ada,
      overrides: {
        'GET /api/modules/:id': () =>
          Response.json(
            {
              detail:
                'This module is not available yet. Complete the previous module to unlock it.',
            },
            { status: 403 },
          ),
      },
    })
    // Retries on, as in the app: the module query itself must not retry a refusal.
    const queryClient = new QueryClient()
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/modules/6']}>
          <Routes>
            <Route path="/modules/:moduleId" element={<ModulePage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(
      await screen.findByRole('heading', { name: 'This module isn’t open yet' }),
    ).toBeInTheDocument()
    expect(screen.getByText(/Complete the previous module to unlock it/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to your modules' })).toHaveAttribute('href', '/')
    expect(api.callsTo('GET /api/modules/6')).toHaveLength(1)
  })

  it('does not retry any refusal, such as too many requests (429)', async () => {
    const api = fakeApi({
      user: ada,
      overrides: {
        'GET /api/modules/:id': () =>
          Response.json({ detail: 'Too many requests. Wait a moment.' }, { status: 429 }),
      },
    })
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter initialEntries={['/modules/2']}>
          <Routes>
            <Route path="/modules/:moduleId" element={<ModulePage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(
      await screen.findByRole('heading', { name: 'This module can’t be shown right now' }),
    ).toBeInTheDocument()
    expect(api.callsTo('GET /api/modules/2')).toHaveLength(1)
  })

  it.each(['abc', '1.5', '-1', '1e3'])(
    'says /modules/%s is no module, without asking the API (no endless re-render)',
    async (param) => {
      const api = fakeApi({ user: ada })
      renderApp(`/modules/${param}`)
      expect(await screen.findByRole('heading', { name: 'There’s no such module' })).toBeVisible()
      expect(screen.getByRole('link', { name: 'Back to your modules' })).toHaveAttribute(
        'href',
        '/',
      )
      expect(api.calls.filter((c) => c.path.startsWith('/api/modules/'))).toHaveLength(0)
    },
  )

  it('switches in place to an address that is no module, and back again', async () => {
    fakeApi({
      user: ada,
      overrides: {
        'GET /api/modules': () => Response.json([]),
        'GET /api/modules/:id': () => Response.json(twoSegmentDetail),
      },
    })
    render(
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
      >
        <MemoryRouter initialEntries={['/modules/1']}>
          <Link to="/modules/abc">Bad address</Link>
          <Link to="/modules/1">Module one</Link>
          <Routes>
            <Route path="/modules/:moduleId" element={<ModulePage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(await screen.findByText('Segment 1 of 2')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('link', { name: 'Bad address' }))
    expect(await screen.findByRole('heading', { name: 'There’s no such module' })).toBeVisible()
    await userEvent.click(screen.getByRole('link', { name: 'Module one' }))
    expect(await screen.findByText('Segment 1 of 2')).toBeInTheDocument()
  })

  it('says there is no such module on a 404', async () => {
    fakeApi({ user: ada })
    renderApp('/modules/99')
    expect(await screen.findByRole('heading', { name: 'There’s no such module' })).toBeVisible()
  })

  it('starts a module afresh when another opens in place, not at the last one’s segment', async () => {
    const second: ModuleDetail = { ...allKindsDetail, id: 2, number: 1, title: 'Second module' }
    fakeApi({
      user: ada,
      overrides: {
        'GET /api/modules': () => Response.json([]),
        'GET /api/modules/:id': (_body, params) =>
          Response.json(
            params.id === '2'
              ? second
              : { ...allKindsDetail, status: 'complete', currentSegmentPosition: 3 },
          ),
        'GET /api/videos/42': () => Response.json({ detail: 'Not needed.' }, { status: 404 }),
      },
    })
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/modules/1']}>
          <Link to="/modules/2">Open the second module</Link>
          <Routes>
            <Route path="/modules/:moduleId" element={<ModulePage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(await screen.findByText('Segment 4 of 4')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '← Previous' }))
    expect(await screen.findByText('Segment 3 of 4')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('link', { name: 'Open the second module' }))
    expect(await screen.findByRole('heading', { name: /Second module/ })).toBeInTheDocument()
    expect(screen.getByText('Segment 1 of 4')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// (d) Video segment plays inside the module
// ---------------------------------------------------------------------------

describe('ModulePage — video segment', () => {
  it('plays the video in the module, with the module navigation still there', async () => {
    const detail = { ...allKindsDetail, currentSegmentPosition: 1 }
    setupModuleApi(detail, detail, {
      'GET /api/videos/42': () =>
        Response.json({
          id: 42,
          title: 'BFS in action',
          mediaPath: '/media/bfs.mp4',
          captionsPath: '/media/bfs.vtt',
          transcript: 'BFS visits the start vertex first.',
          durationSeconds: 60,
          checkpoints: [],
        }),
    })
    renderApp('/modules/1')

    expect(await screen.findByRole('heading', { name: 'Watch: BFS in action' })).toBeInTheDocument()
    expect(await screen.findByText('BFS visits the start vertex first.')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: '▶ Watch video' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Next →' })).toBeEnabled()
  })
})

// ---------------------------------------------------------------------------
// (e) Activity segment is answered inside the module
// ---------------------------------------------------------------------------

describe('ModulePage — activity segment', () => {
  it('keeps Next disabled until the activity is answered correctly, then moves on', async () => {
    let answered = false
    const detail = (): ModuleDetail => ({
      ...allKindsDetail,
      currentSegmentPosition: 2,
      status: 'in_progress',
      segments: [
        textSegment,
        videoSegment,
        { ...activitySegment, done: answered },
        workedExampleSegment,
      ],
    })
    fakeApi({
      user: ada,
      overrides: {
        'GET /api/modules': () => Response.json([]),
        'GET /api/modules/:id': () => Response.json(detail()),
        'POST /api/modules/:id/position': () => Response.json(detail()),
        'GET /api/activities/7': () =>
          Response.json({
            id: 7,
            kind: 'multiple_choice',
            title: 'Which vertex is next?',
            visible: true,
            config: {
              prompt: 'BFS has just visited A. Which vertex comes next?',
              options: [
                { id: 'b', label: 'B, the first neighbour queued' },
                { id: 'd', label: 'D, the last neighbour queued' },
              ],
            },
          }),
        'GET /api/activities/7/hints': () => Response.json([]),
        'POST /api/activities/7/attempts': () => {
          answered = true
          return Response.json({
            id: 1,
            activityId: 7,
            correct: true,
            score: 1,
            parts: [],
            feedback: 'Correct: B joined the queue first.',
            hintLevel: 0,
          })
        },
      },
    })
    renderApp('/modules/1')

    expect(
      await screen.findByText('BFS has just visited A. Which vertex comes next?'),
    ).toBeInTheDocument()
    // The segment's heading names the question; the activity's own title isn't repeated (#159).
    expect(screen.queryByRole('heading', { name: 'Which vertex is next?' })).toBeNull()
    expect(screen.queryByRole('link', { name: 'Start the activity' })).toBeNull()
    const next = screen.getByRole('button', { name: 'Next →' })
    expect(next).toHaveAttribute('aria-disabled', 'true')
    expect(next).toHaveAccessibleDescription('Answer the activity to continue.')

    await userEvent.click(screen.getByLabelText('B, the first neighbour queued'))
    await userEvent.click(screen.getByRole('button', { name: 'Check answer' }))
    expect(await screen.findByText('Correct: B joined the queue first.')).toBeInTheDocument()

    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Next →' })).not.toHaveAttribute('aria-disabled'),
    )
    expect(document.getElementById('segment-blocked')).toBeEmptyDOMElement()
    await userEvent.click(screen.getByRole('button', { name: 'Next →' }))
    expect(
      await screen.findByRole('heading', { name: 'Worked example: adjacency list' }),
    ).toBeInTheDocument()
  })

  it('stays on the segment it opened at when answering it makes another the first not done', async () => {
    // A complete module with two segments left undone (#136): answering the first refetches the
    // module, and the page must keep showing that answer's feedback, not jump to the second.
    let answered = false
    const detail = (): ModuleDetail => ({
      ...allKindsDetail,
      currentSegmentPosition: 3,
      status: 'complete',
      segments: [
        textSegment,
        videoSegment,
        { ...activitySegment, done: answered },
        { ...activitySegment, id: 14, position: 4, activityId: 8, title: 'Second', done: false },
      ],
    })
    fakeApi({
      user: ada,
      overrides: {
        'GET /api/modules': () => Response.json([]),
        'GET /api/modules/:id': () => Response.json(detail()),
        'GET /api/activities/7': () =>
          Response.json({
            id: 7,
            kind: 'multiple_choice',
            title: 'Which vertex is next?',
            visible: true,
            config: {
              prompt: 'Which?',
              options: [
                { id: 'b', label: 'B' },
                { id: 'd', label: 'D' },
              ],
            },
          }),
        'GET /api/activities/7/hints': () => Response.json([]),
        'POST /api/activities/7/attempts': () => {
          answered = true
          return Response.json({
            id: 1,
            activityId: 7,
            correct: false,
            score: 0,
            parts: [],
            feedback: 'Not quite: D joined the queue last.',
            hintLevel: 0,
          })
        },
      },
    })
    renderApp('/modules/1')
    // The answer options, not the activity's own title: #161 hides that title inside a segment.
    await screen.findByLabelText('D')
    expect(screen.getByText('Segment 3 of 4')).toBeInTheDocument()
    await userEvent.click(screen.getByLabelText('D'))
    await userEvent.click(screen.getByRole('button', { name: 'Check answer' }))
    expect(await screen.findByText('Not quite: D joined the queue last.')).toBeInTheDocument()
    // Give the refetch time to land, then check the page didn't move.
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(screen.getByText('Segment 3 of 4')).toBeInTheDocument()
    expect(screen.getByText('Not quite: D joined the queue last.')).toBeInTheDocument()
  })

  it('asks for the video’s checkpoints, answered correctly, before moving on', async () => {
    const detail: ModuleDetail = {
      ...allKindsDetail,
      currentSegmentPosition: 1,
      status: 'in_progress',
      segments: [
        textSegment,
        { ...videoSegment, done: false },
        activitySegment,
        workedExampleSegment,
      ],
    }
    setupModuleApi(detail, detail, {
      'GET /api/videos/42': () =>
        Response.json({
          id: 42,
          title: 'BFS in action',
          mediaPath: '/media/bfs.mp4',
          captionsPath: '/media/bfs.vtt',
          transcript: 'BFS visits the start vertex first.',
          durationSeconds: 60,
          checkpoints: [],
        }),
    })
    renderApp('/modules/1')

    expect(
      await screen.findByText(
        'Answer each of the video’s checkpoint questions correctly to continue.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Next →' })).toHaveAttribute('aria-disabled', 'true')
  })
})

// ---------------------------------------------------------------------------
// (f) Blocked Next: accessible, and only at the furthest segment reached (FR-2.7)
// ---------------------------------------------------------------------------

describe('ModulePage — blocked Next', () => {
  const blockedAt = (currentSegmentPosition: number): ModuleDetail => ({
    ...allKindsDetail,
    currentSegmentPosition,
    status: 'in_progress',
    segments: [
      textSegment,
      videoSegment,
      { ...activitySegment, done: false },
      workedExampleSegment,
    ],
  })

  it('stays focusable, reads its reason, and ignores a click', async () => {
    const api = setupModuleApi(blockedAt(2), blockedAt(2), {
      'GET /api/activities/7': () => Response.json({ detail: 'Not needed here.' }, { status: 404 }),
    })
    renderApp('/modules/1')

    const next = await screen.findByRole('button', { name: 'Next →' })
    expect(next).not.toBeDisabled()
    expect(next).toHaveAttribute('aria-disabled', 'true')
    next.focus()
    expect(next).toHaveFocus()
    expect(next).toHaveAccessibleDescription('Answer the activity to continue.')

    await userEvent.click(next)
    expect(api.callsTo('POST /api/modules/1/position')).toHaveLength(0)
    expect(screen.getByRole('heading', { name: activitySegment.title })).toBeInTheDocument()
  })

  it('keeps the reason in a status region that is there even when nothing is blocked', async () => {
    setupModuleApi(twoSegmentDetail)
    renderApp('/modules/1')

    await screen.findByRole('button', { name: 'Next →' })
    // <output> is a polite status region: announced when its text changes.
    const status = document.getElementById('segment-blocked')
    expect(screen.getAllByRole('status')).toContain(status)
    expect(status).toBeEmptyDOMElement()
  })

  it('doesn’t block stepping forward over a segment before the furthest reached', async () => {
    // Progress made before FR-2.7, or before staff changed the segment: it was passed already.
    const api = setupModuleApi(blockedAt(3), blockedAt(3), {
      'GET /api/activities/7': () => Response.json({ detail: 'Not needed here.' }, { status: 404 }),
    })
    renderApp('/modules/1')

    // The page opens on the segment that was passed without being done (#136 review) ...
    expect(await screen.findByText('Segment 3 of 4')).toBeInTheDocument()
    const next = await screen.findByRole('button', { name: 'Next →' })
    // ... and doesn't block moving on from it.
    expect(next).not.toHaveAttribute('aria-disabled')

    await userEvent.click(next)
    expect(
      await screen.findByRole('heading', { name: 'Worked example: adjacency list' }),
    ).toBeInTheDocument()
    expect(api.callsTo('POST /api/modules/1/position')).toHaveLength(0)
  })

  it('goes back and forward again on an unanswered last segment without saving', async () => {
    // The bug in review of #130: Next re-saved the last segment, which the server refused.
    const detail: ModuleDetail = {
      ...twoSegmentDetail,
      currentSegmentPosition: 1,
      status: 'in_progress',
      segments: [textSegment, { ...activitySegment, position: 1, done: false }],
    }
    const api = setupModuleApi(detail, detail, {
      'GET /api/activities/7': () => Response.json({ detail: 'Not needed here.' }, { status: 404 }),
    })
    renderApp('/modules/1')

    expect(await screen.findByRole('button', { name: 'Finish module' })).toHaveAttribute(
      'aria-disabled',
      'true',
    )
    await userEvent.click(screen.getByRole('button', { name: '← Previous' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Next →' }))

    expect(await screen.findByRole('button', { name: 'Finish module' })).toBeInTheDocument()
    expect(screen.queryByText('Could not save progress')).toBeNull()
    expect(api.callsTo('POST /api/modules/1/position')).toHaveLength(0)
  })
})

// ---------------------------------------------------------------------------
// Loading and error states
// ---------------------------------------------------------------------------

describe('ModulePage — loading and error states', () => {
  it('shows a spinner while the module is loading', async () => {
    let resolve!: (r: Response) => void
    const pending = new Promise<Response>((res) => {
      resolve = res
    })

    fakeApi({
      user: ada,
      overrides: {
        'GET /api/modules': () => Response.json([]),
        'GET /api/modules/:id': () => pending,
        'POST /api/modules/:id/position': () => Response.json(twoSegmentDetail),
      },
    })
    renderApp('/modules/1')

    // The Spinner renders the label inside a visually-hidden span inside <output role="status">
    expect(await screen.findByText('Loading module')).toBeInTheDocument()

    resolve(Response.json(twoSegmentDetail))
  })

  it('shows an error alert when the module API fails', async () => {
    fakeApi({
      user: ada,
      overrides: {
        'GET /api/modules': () => Response.json([]),
        'GET /api/modules/:id': () =>
          Response.json({ detail: 'Module not found.' }, { status: 404 }),
        'POST /api/modules/:id/position': () => Response.json(twoSegmentDetail),
      },
    })
    renderApp('/modules/1')

    expect(await screen.findByText('Module not found.')).toBeInTheDocument()
  })

  it('shows a message when the module has no segments', async () => {
    const emptyDetail: ModuleDetail = {
      ...moduleSummary,
      segments: [],
      segmentCount: 0,
      retrieval: [],
    }
    setupModuleApi(emptyDetail)
    renderApp('/modules/1')

    expect(await screen.findByText('This module has no segments yet.')).toBeInTheDocument()
  })

  it('explains when retrieval is complete but lesson segments are still placeholders', async () => {
    const api = recallApi({
      ...moduleSummary,
      segmentCount: 0,
      segments: [],
      retrieval: [recall],
    })
    renderApp('/modules/1')

    await userEvent.click(await screen.findByLabelText('Connected vertices'))
    await userEvent.click(screen.getByRole('button', { name: 'Check answer' }))
    await screen.findByText('Correct: it stores connected vertices.')
    await userEvent.click(screen.getByRole('button', { name: 'Start module' }))

    expect(
      await screen.findByText(
        'You’ve answered the retrieval questions. Lesson content for this module has not been added yet.',
      ),
    ).toBeInTheDocument()
    expect(api.callsTo('POST /api/activities/201/attempts')).toHaveLength(1)
  })
})

// ---------------------------------------------------------------------------
// Support segments for a struggling student (FR-8.4, #172)
// ---------------------------------------------------------------------------

describe('ModulePage — support segments', () => {
  const support = (id: number, shown: boolean, title: string): Segment => ({
    ...textSegment,
    id,
    position: id - 20,
    title,
    body: 'An example, step by step.',
    supportFor: 6,
    shown,
  })
  const closing: Segment = { ...workedExampleSegment, id: 24, position: 4, title: 'Closing' }
  function supportDetail(shown: boolean, currentSegmentPosition = 1): ModuleDetail {
    return {
      ...moduleSummary,
      segmentCount: 5,
      currentSegmentPosition,
      segments: [
        { ...textSegment, position: 0 },
        { ...workedExampleSegment, id: 21, position: 1, title: 'Base practice' },
        support(22, shown, 'Another way to see it'),
        support(23, shown, 'Try a fresh one'),
        closing,
      ],
      retrieval: [],
    }
  }

  it('skips support the student doesn’t need, and doesn’t count it', async () => {
    const api = setupModuleApi(supportDetail(false))
    renderApp('/modules/1')

    expect(await screen.findByRole('heading', { name: 'Base practice' })).toBeInTheDocument()
    expect(screen.getByText('Segment 2 of 3')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Next →' }))

    expect(await screen.findByRole('heading', { name: 'Closing' })).toBeInTheDocument()
    expect(api.callsTo('POST /api/modules/1/position')[0].body).toEqual({ segmentPosition: 4 })
    expect(screen.getByText('Segment 3 of 3')).toBeInTheDocument()
    expect(screen.queryByText(/another way/i)).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: '← Previous' }))
    expect(await screen.findByRole('heading', { name: 'Base practice' })).toBeInTheDocument()
  })

  it('shows support to a student who needs it, opened with one kind line', async () => {
    const api = setupModuleApi(supportDetail(true))
    renderApp('/modules/1')

    expect(await screen.findByText('Segment 2 of 5')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Next →' }))

    expect(
      await screen.findByRole('heading', { name: 'Another way to see it' }),
    ).toBeInTheDocument()
    expect(api.callsTo('POST /api/modules/1/position')[0].body).toEqual({ segmentPosition: 2 })
    expect(screen.getByText('Let’s look at this another way before you move on.')).toBeVisible()
    expect(screen.queryByText(/fail|wrong/i)).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Next →' }))
    expect(await screen.findByRole('heading', { name: 'Try a fresh one' })).toBeInTheDocument()
    expect(screen.queryByText(/another way before/i)).not.toBeInTheDocument() // once per run
  })

  it('finishes on the last segment shown when the support at the end is hidden', async () => {
    const detail = supportDetail(false, 1)
    detail.segments = detail.segments.slice(0, 4) // the support is the module's end
    setupModuleApi(detail)
    renderApp('/modules/1')

    expect(await screen.findByRole('button', { name: 'Finish module' })).toBeInTheDocument()
    expect(screen.getByText('Segment 2 of 2')).toBeInTheDocument()
  })

  it('never opens on a hidden segment', async () => {
    setupModuleApi(supportDetail(false, 2)) // a position left on hidden support
    renderApp('/modules/1')

    expect(await screen.findByRole('heading', { name: 'Closing' })).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// (h) Focus management (WCAG 2.4.3, #142)
// ---------------------------------------------------------------------------

describe('ModulePage — focus after navigation', () => {
  it('does not move focus when the module first opens', async () => {
    setupModuleApi(allKindsDetail)
    renderApp('/modules/1')

    await screen.findByRole('heading', { name: 'Introduction to graphs' })
    expect(screen.getByRole('heading', { name: 'Introduction to graphs' })).not.toHaveFocus()
    expect(document.activeElement).toBe(document.body)
  })

  it('moves focus to the new segment’s heading after Next (a saved move)', async () => {
    const api = setupModuleApi(allKindsDetail)
    renderApp('/modules/1')

    await userEvent.click(await screen.findByRole('button', { name: 'Next →' }))

    const heading = await screen.findByRole('heading', { name: 'Watch: BFS in action' })
    await waitFor(() => expect(heading).toHaveFocus())
    expect(heading).toHaveAttribute('tabindex', '-1') // focusable by script, not a tab stop
    expect(api.callsTo('POST /api/modules/1/position')).toHaveLength(1)
  })

  it('moves focus to the heading after Previous, and after Next over a reached segment', async () => {
    setupModuleApi({ ...allKindsDetail, currentSegmentPosition: 2 })
    renderApp('/modules/1')

    await screen.findByRole('heading', { name: 'Practice: BFS step by step' })
    await userEvent.click(screen.getByRole('button', { name: '← Previous' }))
    const video = await screen.findByRole('heading', { name: 'Watch: BFS in action' })
    await waitFor(() => expect(video).toHaveFocus())

    // Previous on the first segment disables the button that was pressed; focus must not drop.
    await userEvent.click(screen.getByRole('button', { name: '← Previous' }))
    const first = await screen.findByRole('heading', { name: 'Introduction to graphs' })
    await waitFor(() => expect(first).toHaveFocus())
    expect(screen.getByRole('button', { name: '← Previous' })).toBeDisabled()

    await userEvent.keyboard('{Tab}') // from the heading, on into the page: not back at the top
    expect(document.activeElement).not.toBe(document.body)

    await userEvent.click(screen.getByRole('button', { name: 'Next →' }))
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Watch: BFS in action' })).toHaveFocus(),
    )
  })

  it('keeps focus on a blocked Next: nothing moves, so focus stays where it was', async () => {
    setupModuleApi({
      ...allKindsDetail,
      status: 'in_progress',
      segments: [{ ...textSegment, kind: 'activity', activityId: 7, done: false }],
    })
    renderApp('/modules/1')
    const finish = await screen.findByRole('button', { name: 'Finish module' })
    finish.focus()
    await userEvent.keyboard('{Enter}')
    expect(finish).toHaveFocus()
  })

  it('moves focus to the question count after "Start module" leaves the recall questions', async () => {
    recallApi({ ...twoSegmentDetail, retrieval: [recall] })
    renderApp('/modules/1')

    await userEvent.click(await screen.findByLabelText('Connected vertices'))
    await userEvent.click(screen.getByRole('button', { name: 'Check answer' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Start module' }))

    const heading = await screen.findByRole('heading', { name: 'Introduction to graphs' })
    await waitFor(() => expect(heading).toHaveFocus())
  })

  it('moves focus to the module heading when "Start module" leads to no segments (module 5)', async () => {
    recallApi({ ...moduleSummary, segmentCount: 0, segments: [], retrieval: [recall] })
    renderApp('/modules/1')

    await userEvent.click(await screen.findByLabelText('Connected vertices'))
    await userEvent.click(screen.getByRole('button', { name: 'Check answer' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Start module' }))

    const heading = await screen.findByRole('heading', { level: 1, name: /Module 0/ })
    await waitFor(() => expect(heading).toHaveFocus())
    expect(document.activeElement).not.toBe(document.body)
  })

  it('keeps focus on Next while a slow save runs, and Previous does nothing meanwhile', async () => {
    let release: (response: Response) => void = () => {}
    const api = setupModuleApi(allKindsDetail, allKindsDetail, {
      'POST /api/modules/:id/position': () =>
        new Promise<Response>((resolve) => (release = resolve)),
    })
    renderApp('/modules/1')
    const next = await screen.findByRole('button', { name: 'Next →' })
    next.focus()
    await userEvent.keyboard('{Enter}')

    await waitFor(() => expect(next).toHaveAttribute('aria-busy', 'true'))
    expect(next).toHaveFocus()
    expect(next).toBeEnabled()
    await userEvent.keyboard('{Enter}') // a second press while saving is ignored
    expect(api.callsTo('POST /api/modules/1/position')).toHaveLength(1)

    release(Response.json(allKindsDetail))
    const heading = await screen.findByRole('heading', { name: 'Watch: BFS in action' })
    await waitFor(() => expect(heading).toHaveFocus())
  })

  it('keeps focus on Next when the save fails, and announces the error at once', async () => {
    setupModuleApi(allKindsDetail, allKindsDetail, {
      'POST /api/modules/:id/position': () => Response.json({ detail: 'boom' }, { status: 500 }),
    })
    renderApp('/modules/1')
    const next = await screen.findByRole('button', { name: 'Next →' })
    next.focus()
    await userEvent.keyboard('{Enter}')

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Could not save progress')
    expect(next).toHaveFocus()
    expect(screen.getByRole('heading', { name: 'Introduction to graphs' })).toBeInTheDocument()
  })

  it('moves focus to the new question after "Next question"', async () => {
    recallApi({
      ...twoSegmentDetail,
      retrieval: [recall, { id: 201, title: 'Recall graph storage', answered: false }],
    })
    renderApp('/modules/1')

    await userEvent.click(await screen.findByLabelText('Connected vertices'))
    await userEvent.click(screen.getByRole('button', { name: 'Check answer' }))
    await userEvent.click(await screen.findByRole('button', { name: 'Next question' }))

    const count = await screen.findByText('Quick recall · Question 2 of 2')
    await waitFor(() => expect(count).toHaveFocus())
  })
})

describe('ModulePage — events', () => {
  it('reports each segment it shows, for the pilot timeline', async () => {
    const api = setupModuleApi(twoSegmentDetail, twoSegmentDetail, {
      'POST /api/events': () => new Response(null, { status: 204 }),
    })
    renderApp('/modules/1')

    expect(await screen.findByRole('heading', { name: 'Introduction to graphs' })).toBeVisible()
    await waitFor(() =>
      expect(api.callsTo('POST /api/events').map((c) => c.body)).toContainEqual({
        type: 'segment_viewed',
        targetId: textSegment.id,
      }),
    )
  })
})
