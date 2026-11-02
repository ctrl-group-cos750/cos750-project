import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import App from './App.tsx'

function stubFetch(response: Promise<Response>) {
  const fetch = vi.fn<typeof globalThis.fetch>(() => response)
  vi.stubGlobal('fetch', fetch)
  return fetch
}

describe('App', () => {
  it('shows the brand and asks the API for its health', () => {
    const fetch = stubFetch(new Promise(() => {}))
    render(<App />)
    expect(screen.getByRole('heading', { name: 'Ctrl Academy' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Control Group' })).toBeInTheDocument()
    expect(screen.getByText('API: checking…')).toBeInTheDocument()
    expect(fetch).toHaveBeenCalledWith('/api/health')
  })

  it('shows the API and database status when the API answers', async () => {
    stubFetch(Promise.resolve(Response.json({ status: 'ok', database: 'ok' })))
    render(<App />)
    expect(await screen.findByText('API: ok, database ok')).toBeInTheDocument()
  })

  it('says the API is unreachable when it returns an error', async () => {
    stubFetch(Promise.resolve(new Response(null, { status: 502 })))
    render(<App />)
    expect(await screen.findByText('API: unreachable')).toBeInTheDocument()
  })

  it('says the API is unreachable when the request fails', async () => {
    stubFetch(Promise.reject(new TypeError('Failed to fetch')))
    render(<App />)
    expect(await screen.findByText('API: unreachable')).toBeInTheDocument()
  })
})
