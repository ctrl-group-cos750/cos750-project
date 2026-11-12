import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ada, fakeApi, renderApp } from '../../test/app.tsx'
import type { ModuleSummary } from './module.types.ts'

// ---------------------------------------------------------------------------
// Sample data
// ---------------------------------------------------------------------------

const openModule: ModuleSummary = {
  id: 1,
  number: 0,
  slug: 'warmup',
  title: 'Warm-up and queue refresher',
  goals: ['By the end you can recall queues.'],
  estimatedMinutes: 5,
  status: 'open',
  segmentCount: 2,
  currentSegmentPosition: 0,
}

const lockedModule: ModuleSummary = {
  id: 2,
  number: 1,
  slug: 'what-is-a-graph',
  title: 'What is a graph?',
  goals: ['By the end you can define a graph.'],
  estimatedMinutes: 12,
  status: 'locked',
  segmentCount: 2,
  currentSegmentPosition: 0,
}

const inProgressModule: ModuleSummary = {
  id: 3,
  number: 2,
  slug: 'graph-in-python',
  title: 'A graph in Python',
  goals: ['By the end you can model a graph in Python.'],
  estimatedMinutes: 10,
  status: 'in_progress',
  segmentCount: 4,
  currentSegmentPosition: 2,
}

const completeModule: ModuleSummary = {
  id: 4,
  number: 3,
  slug: 'meet-bfs',
  title: 'Meet BFS',
  goals: ['By the end you understand BFS.'],
  estimatedMinutes: 12,
  status: 'complete',
  segmentCount: 2,
  currentSegmentPosition: 1,
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function moduleListApi(modules: ModuleSummary[]) {
  return fakeApi({
    user: ada,
    overrides: {
      'GET /api/modules': () => Response.json(modules),
    },
  })
}

// ---------------------------------------------------------------------------
// Status tags rendered for each module
// ---------------------------------------------------------------------------

describe('ModuleMap — status tags', () => {
  it('renders status tags for all modules', async () => {
    moduleListApi([openModule, lockedModule, completeModule])
    renderApp('/')

    // Wait for the list to appear
    expect(await screen.findByText('Warm-up and queue refresher')).toBeInTheDocument()

    expect(screen.getByText('open')).toBeInTheDocument()
    expect(screen.getByText('locked')).toBeInTheDocument()
    expect(screen.getByText('complete')).toBeInTheDocument()
  })

  it('renders an in_progress tag with the label "in progress"', async () => {
    moduleListApi([openModule, inProgressModule])
    renderApp('/')

    expect(await screen.findByText('in progress')).toBeInTheDocument()
  })

  it('shows every module title', async () => {
    moduleListApi([openModule, lockedModule])
    renderApp('/')

    expect(await screen.findByText('Warm-up and queue refresher')).toBeInTheDocument()
    expect(screen.getByText('What is a graph?')).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Module 0 open; locked module not a link
// ---------------------------------------------------------------------------

describe('ModuleMap — locked vs open affordances', () => {
  it('shows an open module', async () => {
    moduleListApi([openModule])
    renderApp('/')
    expect(await screen.findByText('Warm-up and queue refresher')).toBeInTheDocument()
    expect(screen.getByText('open')).toBeInTheDocument()
  })

  it('shows a locked module but not as a clickable link', async () => {
    moduleListApi([openModule, lockedModule])
    renderApp('/')

    expect(await screen.findByText('What is a graph?')).toBeInTheDocument()
    expect(screen.getByText('locked')).toBeInTheDocument()

    // The locked module title should NOT be inside an anchor element
    const lockedTitle = screen.getByText('What is a graph?')
    expect(lockedTitle.closest('a')).toBeNull()
  })

  it('open module card IS a link to /modules/:id', async () => {
    moduleListApi([openModule])
    renderApp('/')
    await screen.findByText('Warm-up and queue refresher')
    // The card for an open module should be wrapped in an anchor pointing to the module page.
    const link = screen.getByRole('link', { name: /warm-up/i })
    expect(link).toBeInTheDocument()
    expect(link).toHaveAttribute('href', `/modules/${openModule.id}`)
  })

  it('locked module card is NOT a link', async () => {
    moduleListApi([openModule, lockedModule])
    renderApp('/')
    await screen.findByText('What is a graph?')
    // The locked card must not be wrapped in an anchor.
    const lockedTitle = screen.getByText('What is a graph?')
    expect(lockedTitle.closest('a')).toBeNull()
  })

  it('clicking an open module card navigates to the module page', async () => {
    fakeApi({
      user: ada,
      overrides: {
        'GET /api/modules': () => Response.json([openModule]),
        'GET /api/modules/:id': () =>
          Response.json({
            ...openModule,
            segments: [],
          }),
      },
    })
    renderApp('/')
    const link = await screen.findByRole('link', { name: /warm-up/i })
    await userEvent.click(link)
    // ModulePage renders the module heading (even for the empty-segments state).
    expect(await screen.findByText(/module 0/i)).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Continue button
// ---------------------------------------------------------------------------

describe('ModuleMap — Continue button', () => {
  it('shows a Continue button targeting the in-progress module when one exists', async () => {
    moduleListApi([openModule, inProgressModule])
    renderApp('/')

    // in_progress beats open
    const btn = await screen.findByRole('button', { name: /continue module 2/i })
    expect(btn).toBeInTheDocument()
  })

  it('shows a Continue button targeting the first open module when none is in_progress', async () => {
    moduleListApi([openModule, lockedModule])
    renderApp('/')

    const btn = await screen.findByRole('button', { name: /continue module 0/i })
    expect(btn).toBeInTheDocument()
  })

  it('never points Continue at a module with no content yet, which reads "coming soon"', async () => {
    // Module 5 today: open (it doesn't lock the rest, #123) but nothing to work through (#146).
    const empty: ModuleSummary = {
      ...openModule,
      id: 6,
      number: 5,
      title: 'Test and debug',
      segmentCount: 0,
    }
    moduleListApi([
      completeModule,
      empty,
      { ...openModule, id: 7, number: 6, title: 'Mastery check' },
    ])
    renderApp('/')

    expect(await screen.findByRole('button', { name: /continue module 6/i })).toBeInTheDocument()
    expect(screen.getByText('coming soon')).toBeInTheDocument()
    expect(screen.getByText('open')).toBeInTheDocument() // module 6
  })

  it('hides the Continue button when all modules are locked or complete', async () => {
    moduleListApi([completeModule, lockedModule])
    renderApp('/')

    await screen.findByText('Meet BFS') // wait for data
    expect(screen.queryByRole('button', { name: /continue/i })).toBeNull()
  })

  it('navigates to the module page when Continue is clicked', async () => {
    // Stub the module detail so the navigation doesn't 404
    fakeApi({
      user: ada,
      overrides: {
        'GET /api/modules': () => Response.json([openModule]),
        'GET /api/modules/:id': () =>
          Response.json({
            ...openModule,
            segments: [],
          }),
      },
    })
    renderApp('/')

    const btn = await screen.findByRole('button', { name: /continue module 0/i })
    await userEvent.click(btn)

    // ModulePage renders the module title (even empty-segments state)
    expect(await screen.findByText(/module 0/i)).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Loading and error states
// ---------------------------------------------------------------------------

describe('ModuleMap — loading and error states', () => {
  it('shows a loading spinner while the modules are being fetched', async () => {
    let resolve!: (r: Response) => void
    const pending = new Promise<Response>((res) => {
      resolve = res
    })

    fakeApi({
      user: ada,
      overrides: {
        'GET /api/modules': () => pending,
      },
    })
    renderApp('/')

    // The Spinner renders the label inside a visually-hidden span inside <output role="status">
    expect(await screen.findByText('Loading modules')).toBeInTheDocument()

    // Resolve to avoid act() warning
    resolve(Response.json([]))
  })

  it('shows an error alert when the modules API fails', async () => {
    fakeApi({
      user: ada,
      overrides: {
        'GET /api/modules': () => Response.json({ detail: 'Service unavailable' }, { status: 503 }),
      },
    })
    renderApp('/')

    expect(await screen.findByText('Service unavailable')).toBeInTheDocument()
  })

  it('shows the module list heading when data loads', async () => {
    moduleListApi([openModule])
    renderApp('/')

    expect(
      await screen.findByRole('heading', { name: 'Graphs and breadth-first search' }),
    ).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Duration and progress bar
// ---------------------------------------------------------------------------

describe('ModuleMap — duration and progress', () => {
  it('shows the estimated duration for each module', async () => {
    moduleListApi([openModule])
    renderApp('/')

    expect(await screen.findByText('5 min')).toBeInTheDocument()
  })

  it('shows a progress bar for an in-progress module', async () => {
    moduleListApi([inProgressModule])
    renderApp('/')

    await screen.findByText('A graph in Python')
    expect(screen.getByRole('progressbar', { name: 'Module 2 progress' })).toBeInTheDocument()
  })

  it('does not show a progress bar for an open module', async () => {
    moduleListApi([openModule])
    renderApp('/')

    await screen.findByText('Warm-up and queue refresher')
    expect(screen.queryByRole('progressbar')).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// Course progress in minutes
// ---------------------------------------------------------------------------

describe('ModuleMap — minutes', () => {
  const emptyModule: ModuleSummary = {
    ...lockedModule,
    id: 5,
    number: 4,
    title: 'Build BFS',
    estimatedMinutes: 15,
    segmentCount: 0,
  }

  it('shows the total of every module, as the rows add up, before anything is done', async () => {
    moduleListApi([openModule, lockedModule, emptyModule])
    renderApp('/')

    // 5 + 12 + 15: the same sum the register page shows (#146).
    expect(await screen.findByText('About 32 minutes in total')).toBeInTheDocument()
    expect(screen.queryByRole('progressbar', { name: 'Course progress in minutes' })).toBeNull()
  })

  it('shows the minutes done and left', async () => {
    // Module 3 complete (12) and module 2 halfway (2 of 4 segments of 10): 17 of 54.
    moduleListApi([openModule, lockedModule, inProgressModule, completeModule, emptyModule])
    renderApp('/')

    expect(
      await screen.findByText('About 17 of 54 minutes done · about 37 left'),
    ).toBeInTheDocument()
    expect(screen.getByRole('progressbar', { name: 'Course progress in minutes' })).toHaveAttribute(
      'value',
      '17',
    )
  })

  it('says when everything is done', async () => {
    moduleListApi([completeModule])
    renderApp('/')

    expect(await screen.findByText('All 12 minutes done')).toBeInTheDocument()
  })

  it('still counts a module with no content yet once the rest is done', async () => {
    moduleListApi([completeModule, emptyModule])
    renderApp('/')

    expect(
      await screen.findByText('About 12 of 27 minutes done · about 15 left'),
    ).toBeInTheDocument()
  })
})
