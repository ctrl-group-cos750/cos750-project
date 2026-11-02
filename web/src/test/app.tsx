import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { vi } from 'vitest'
import App from '../App.tsx'
import type { User } from '../auth/api.ts'

export const ada: User = { id: 1, email: 'ada@example.com', displayName: 'Ada', isStaff: false }

type Call = { method: string; path: string; body: unknown }
type Override = (body: unknown) => Response | Promise<Response>

/**
 * A stand-in for the API that remembers who is logged in, like the real one does with its cookie.
 * `overrides` replace a route's answer, keyed "METHOD /path".
 */
export function fakeApi({
  user = null,
  overrides = {},
}: { user?: User | null; overrides?: Record<string, Override> } = {}) {
  let session: User | null = user
  const calls: Call[] = []

  const routes: Record<string, Override> = {
    'GET /api/auth/me': () =>
      session
        ? Response.json(session)
        : Response.json({ detail: 'Log in to continue.' }, { status: 401 }),
    'POST /api/auth/login': () => {
      session = ada
      return Response.json(ada)
    },
    'POST /api/auth/register': (body) => {
      const { email, displayName } = body as { email: string; displayName: string }
      session = { ...ada, email, displayName }
      return Response.json(session, { status: 201 })
    },
    'POST /api/auth/logout': () => {
      session = null
      return new Response(null, { status: 204 })
    },
    'GET /api/health': () => Response.json({ status: 'ok', database: 'ok' }),
    ...overrides,
  }

  const fetch = vi.fn<typeof globalThis.fetch>(async (input, init) => {
    const path = String(input)
    const method = init?.method ?? 'GET'
    const body: unknown = init?.body ? JSON.parse(String(init.body)) : undefined
    calls.push({ method, path, body })
    const route = routes[`${method} ${path}`]
    return route ? route(body) : Response.json({ detail: 'Not Found' }, { status: 404 })
  })
  vi.stubGlobal('fetch', fetch)
  return {
    fetch,
    calls,
    callsTo: (key: string) => calls.filter((c) => `${c.method} ${c.path}` === key),
  }
}

/** The whole app at `path`, with a fresh cache, as a student would open it. */
export function renderApp(path = '/') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}
