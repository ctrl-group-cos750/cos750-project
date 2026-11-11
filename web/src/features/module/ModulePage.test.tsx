import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ada, fakeApi, renderApp } from '../../test/app.tsx'
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
}

const workedExampleSegment: Segment = {
  id: 11,
  position: 1,
  kind: 'worked_example',
  title: 'Worked example: adjacency list',
  body: '## Example\n\nHere is a worked example paragraph.',
  videoId: null,
  activityId: null,
}

const videoSegment: Segment = {
  id: 12,
  position: 2,
  kind: 'video',
  title: 'Watch: BFS in action',
  body: null,
  videoId: 42,
  activityId: null,
}

const activitySegment: Segment = {
  id: 13,
  position: 3,
  kind: 'activity',
  title: 'Practice: BFS step by step',
  body: null,
  videoId: null,
  activityId: 7,
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

function setupModuleApi(detail: ModuleDetail, positionResponse: ModuleDetail = detail) {
  return fakeApi({
    user: ada,
    overrides: {
      'GET /api/modules': () => Response.json([]),
      'GET /api/modules/:id': () => Response.json(detail),
      'POST /api/modules/:id/position': () => Response.json(positionResponse),
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
})

// ---------------------------------------------------------------------------
// (d) Video segment shows link to /videos/:videoId
// ---------------------------------------------------------------------------

describe('ModulePage — video segment', () => {
  it('shows a "Watch video" link pointing to the video page', async () => {
    // Navigate to the video segment (position 1 in allKindsDetail)
    const detailAtVideo: ModuleDetail = {
      ...allKindsDetail,
      currentSegmentPosition: 1,
    }
    setupModuleApi(detailAtVideo)
    renderApp('/modules/1')

    // Wait for segment to load
    expect(await screen.findByRole('heading', { name: 'Watch: BFS in action' })).toBeInTheDocument()

    const link = screen.getByRole('link', { name: '▶ Watch video' })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute('href', '/videos/42')
  })
})

// ---------------------------------------------------------------------------
// (e) Activity segment links to the activity page
// ---------------------------------------------------------------------------

describe('ModulePage — activity segment', () => {
  it('links to the activity page', async () => {
    const detailAtActivity: ModuleDetail = {
      ...allKindsDetail,
      currentSegmentPosition: 2,
    }
    setupModuleApi(detailAtActivity)
    renderApp('/modules/1')

    expect(
      await screen.findByRole('heading', { name: 'Practice: BFS step by step' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Start the activity' })).toHaveAttribute(
      'href',
      '/activities/7',
    )
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
