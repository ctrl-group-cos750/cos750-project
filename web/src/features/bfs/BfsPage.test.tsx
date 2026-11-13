import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { BfsPage } from './BfsPage.tsx'
import { fetchBfsScenario } from './bfs.api.ts'

/** A path graph A-B-C-... whose BFS has one step per vertex, so frames = vertices + 1. */
function pathGraph(input: { id: number; name: string; vertices: string[] }) {
  const { id, name, vertices } = input
  const graph = {
    id,
    name,
    directed: false,
    vertices,
    edges: vertices.slice(1).map((target, index) => ({ source: vertices[index], target })),
    startVertex: vertices[0],
  }
  const bfs = {
    startVertex: vertices[0],
    order: vertices,
    steps: vertices.map((vertex, index) => ({
      visitedVertex: vertex,
      queue: vertices.slice(index + 1, index + 2),
      visited: vertices.slice(0, index + 1),
      order: vertices.slice(0, index + 1),
    })),
  }
  return { graph, bfs }
}

const longGraph = pathGraph({
  id: 1,
  name: 'Long path',
  vertices: ['A', 'B', 'C', 'D', 'E', 'F', 'G'],
})
const shortGraph = pathGraph({ id: 2, name: 'Short path', vertices: ['A', 'B'] })

function stubGraphApi() {
  const byPath: Record<string, unknown> = {
    '/api/graphs/1': longGraph.graph,
    '/api/graphs/1/bfs': longGraph.bfs,
    '/api/graphs/2': shortGraph.graph,
    '/api/graphs/2/bfs': shortGraph.bfs,
  }
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const body = byPath[String(input)]
      return body ? Response.json(body) : Response.json({ detail: 'Not Found' }, { status: 404 })
    }),
  )
}

function OpenGraph({ id }: { id: number }) {
  const navigate = useNavigate()
  return (
    <button type="button" onClick={() => void navigate(`/graphs/${id}`)}>
      Open graph {id}
    </button>
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('BfsPage', () => {
  it('leads back to the module it was opened from, else to the map (#146)', async () => {
    stubGraphApi()
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const fromModule = { backTo: '/modules/3', backLabel: 'Back to module 3' }
    const { unmount } = render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[{ pathname: '/graphs/2', state: fromModule }]}>
          <Routes>
            <Route path="/graphs/:scenarioId" element={<BfsPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(await screen.findByRole('link', { name: /Back to module 3/ })).toHaveAttribute(
      'href',
      '/modules/3',
    )
    unmount()

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/graphs/2']}>
          <Routes>
            <Route path="/graphs/:scenarioId" element={<BfsPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(await screen.findByRole('link', { name: /Back to your modules/ })).toHaveAttribute(
      'href',
      '/',
    )
  })

  it('records each prediction as an event, with whether it was right (#146)', async () => {
    stubGraphApi()
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/graphs/2']}>
          <Routes>
            <Route path="/graphs/:scenarioId" element={<BfsPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(await screen.findByRole('heading', { name: 'Short path' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Step forward' }))
    await userEvent.click(await screen.findByRole('button', { name: 'A' }))
    const fetchMock = vi.mocked(fetch)
    const posted = fetchMock.mock.calls
      .filter(([url]) => String(url) === '/api/events')
      .map(([, init]) => JSON.parse(String(init?.body)) as unknown)
    expect(posted).toEqual([{ type: 'prediction_made', targetId: 2, correct: true }])
  })

  it('starts a shorter graph at its first step instead of crashing on the old step position', async () => {
    stubGraphApi()
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    // Both graphs are already loaded, so switching shows the second one at once, with no
    // loading state in between. That is the case where the old visualiser instance was reused.
    await Promise.all(
      [1, 2].map((id) =>
        queryClient.prefetchQuery({
          queryKey: ['graphs', id, 'bfs'],
          queryFn: () => fetchBfsScenario({ scenarioId: id }),
        }),
      ),
    )

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/graphs/1']}>
          <OpenGraph id={2} />
          <Routes>
            <Route path="/graphs/:scenarioId" element={<BfsPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )

    expect(await screen.findByRole('heading', { name: 'Long path' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('checkbox', { name: 'Prediction mode' }))
    // Six clicks, one after the other, to reach the last frame of the long graph.
    await Array.from({ length: 6 }).reduce<Promise<void>>(async (previous) => {
      await previous
      await userEvent.click(screen.getByRole('button', { name: 'Step forward' }))
    }, Promise.resolve())
    expect(screen.getByText('Step 7 of 8')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Open graph 2' }))

    expect(await screen.findByRole('heading', { name: 'Short path' })).toBeInTheDocument()
    expect(screen.getByText('Step 1 of 3')).toBeInTheDocument()
  })

  it('keeps focus through a prediction and at either end of the steps (A3)', async () => {
    stubGraphApi()
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/graphs/2']}>
          <Routes>
            <Route path="/graphs/:scenarioId" element={<BfsPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(await screen.findByRole('heading', { name: 'Short path' })).toBeInTheDocument()
    // The graph's text alternative names its edges, not only the queue.
    expect(screen.getByRole('img', { name: /Edges: A–B\./ })).toBeInTheDocument()

    const back = screen.getByRole('button', { name: 'Step back' })
    expect(back).toHaveAttribute('aria-disabled', 'true')
    const forward = screen.getByRole('button', { name: 'Step forward' })
    forward.focus()
    await userEvent.keyboard('{Enter}')
    // The question takes focus, then the feedback, then Step forward again after Continue.
    expect(screen.getByRole('button', { name: 'A' })).toHaveFocus()
    await userEvent.keyboard('{Enter}')
    expect(screen.getByRole('alert')).toHaveFocus()
    await userEvent.click(screen.getByRole('button', { name: 'Continue' }))
    expect(forward).toHaveFocus()

    // Last step: Step forward is aria-disabled but keeps focus.
    await userEvent.click(screen.getByRole('checkbox', { name: 'Prediction mode' }))
    forward.focus()
    await userEvent.keyboard('{Enter}')
    expect(screen.getByText('Step 3 of 3')).toBeInTheDocument()
    expect(forward).toHaveAttribute('aria-disabled', 'true')
    expect(forward).toHaveFocus()
  })

  it('shows found (joined the queue) and visited (left the queue) as two rows (High 3)', async () => {
    stubGraphApi()
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/graphs/2']}>
          <Routes>
            <Route path="/graphs/:scenarioId" element={<BfsPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(await screen.findByRole('heading', { name: 'Short path' })).toBeInTheDocument()
    // Before the first step the start is found (it is in the queue) but not yet visited.
    expect(screen.getByText('Found (has joined the queue)').nextElementSibling).toHaveTextContent(
      'A',
    )
    expect(screen.getByText('Visited (has left the queue)').nextElementSibling).toHaveTextContent(
      'Empty',
    )
    // The text alternative names both states too, with the right article (review 13 Nov).
    const graph = screen.getByRole('img', { name: /^Short path, an undirected graph/ })
    expect(graph).toHaveAccessibleName(/Found \(has joined the queue\): A\./)
  })
})
