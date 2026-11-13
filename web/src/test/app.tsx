import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { vi } from 'vitest'
import App from '../App.tsx'
import type { User } from '../auth/api.ts'

export const ada: User = {
  id: 1,
  email: 'ada@example.com',
  displayName: 'Ada',
  isStaff: false,
  avatar: null,
  pictureUrl: null,
}

type Call = { method: string; path: string; body: unknown }
type Override = (body: unknown, params: Record<string, string>) => Response | Promise<Response>

/**
 * Converts a route pattern like "GET /api/modules/:id/position" into a RegExp.
 * Named capture groups are created for each `:param` segment.
 * Returns null for exact-match keys (no colon segments).
 */
function patternToRegex(key: string): RegExp | null {
  if (!key.includes(':')) return null
  const escaped = key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const source = escaped.replace(/:([A-Za-z_][A-Za-z0-9_]*)/g, '(?<$1>[^/]+)')
  return new RegExp(`^${source}$`)
}

/**
 * A stand-in for the API that remembers who is logged in, like the real one does with its cookie.
 * `overrides` replace a route's answer, keyed "METHOD /path".
 *
 * Parameterised routes are supported: use `:param` in the key, e.g.
 *   `'GET /api/modules/:id'`  — matches `GET /api/modules/42`, passes `{ id: '42' }` to handler
 *   `'POST /api/modules/:id/position'` — matches the position endpoint for any id
 *
 * Exact keys take precedence over pattern keys. Default handlers are provided for:
 *   - `GET /api/modules/:id`         → 404
 *   - `POST /api/modules/:id/position` → 404
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
    'GET /api/modules': () => Response.json([]),
    'GET /api/rewards': () => Response.json({ hideRewards: false, points: 0, badges: [] }),
    'GET /api/me/skills': () => Response.json({ objectives: [], modules: [] }),
    // Default handlers for parameterised module routes (overridable)
    'GET /api/modules/:id': () => Response.json({ detail: 'Not Found' }, { status: 404 }),
    'POST /api/modules/:id/position': () => Response.json({ detail: 'Not Found' }, { status: 404 }),
    ...overrides,
  }

  // Pre-compile patterns once so the fetch handler is fast.
  const patterns: Array<{ regex: RegExp; key: string; handler: Override }> = Object.entries(routes)
    .map(([key, handler]) => ({ regex: patternToRegex(key), key, handler }))
    .filter((e): e is { regex: RegExp; key: string; handler: Override } => e.regex !== null)

  const fetch = vi.fn<typeof globalThis.fetch>(async (input, init) => {
    const path = String(input)
    const method = init?.method ?? 'GET'
    const body: unknown = init?.body ? JSON.parse(String(init.body)) : undefined
    calls.push({ method, path, body })

    const routeKey = `${method} ${path}`

    // 1. Exact match (highest priority)
    const exact = routes[routeKey]
    if (exact) return exact(body, {})

    // 2. Pattern match (first wins; overrides appear after defaults in the object, so they take
    //    precedence because we rebuild the patterns array from the merged routes object in order —
    //    but overrides that use the *same* key string simply replace the default via object spread)
    for (const { regex, handler } of patterns) {
      const m = regex.exec(routeKey)
      if (m) {
        const params = (m.groups ?? {}) as Record<string, string>
        return handler(body, params)
      }
    }

    return Response.json({ detail: 'Not Found' }, { status: 404 })
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
      <RouterProvider
        router={createMemoryRouter([{ path: '*', element: <App /> }], { initialEntries: [path] })}
      />
    </QueryClientProvider>,
  )
}
