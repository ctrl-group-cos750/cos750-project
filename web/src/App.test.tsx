import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ada, fakeApi, renderApp } from './test/app.tsx'

describe('routing', () => {
  it('sends a visitor who is not logged in to the log-in page', async () => {
    fakeApi()
    renderApp('/')
    expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument()
  })

  it('shows the signed-in home page to a logged-in student', async () => {
    fakeApi({ user: ada })
    renderApp('/')
    expect(
      await screen.findByRole('heading', { name: 'Graphs and breadth-first search' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Ada')).toBeInTheDocument() // in the header
  })

  it('sends a logged-in student away from the log-in and register pages', async () => {
    fakeApi({ user: ada })
    renderApp('/login')
    expect(
      await screen.findByRole('heading', { name: 'Graphs and breadth-first search' }),
    ).toBeInTheDocument()
  })

  it('shows a not-found page for unknown addresses', () => {
    fakeApi()
    renderApp('/no-such-page')
    expect(screen.getByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
  })

  it('says when the API cannot be reached, and tries again on request', async () => {
    let up = false
    const api = fakeApi({
      user: ada,
      overrides: {
        'GET /api/auth/me': () =>
          up ? Response.json(ada) : Response.json({ detail: 'Bad gateway' }, { status: 502 }),
      },
    })
    renderApp('/')
    expect(await screen.findByText("Can't reach Ctrl Academy")).toBeInTheDocument()
    up = true
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(
      await screen.findByRole('heading', { name: 'Graphs and breadth-first search' }),
    ).toBeInTheDocument()
    expect(api.callsTo('GET /api/auth/me')).toHaveLength(2)
  })
})

describe('home page', () => {
  it('shows the module map heading', async () => {
    fakeApi({ user: ada })
    renderApp('/')
    expect(
      await screen.findByRole('heading', { name: 'Graphs and breadth-first search' }),
    ).toBeInTheDocument()
  })

  it('shows an error when the modules API fails', async () => {
    fakeApi({
      user: ada,
      overrides: {
        'GET /api/modules': () => Response.json({ detail: 'Service unavailable' }, { status: 503 }),
      },
    })
    renderApp('/')
    expect(await screen.findByText('Service unavailable')).toBeInTheDocument()
  })
})

describe('logging out', () => {
  it('ends the session and returns to the log-in page', async () => {
    const api = fakeApi({ user: ada })
    renderApp('/')
    await userEvent.click(await screen.findByRole('button', { name: /your account/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Log out' }))
    expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument()
    expect(api.callsTo('POST /api/auth/logout')).toHaveLength(1)
  })

  it('says so when logging out fails', async () => {
    fakeApi({
      user: ada,
      overrides: {
        'POST /api/auth/logout': () => Promise.reject(new TypeError('Failed to fetch')),
      },
    })
    renderApp('/')
    await userEvent.click(await screen.findByRole('button', { name: /your account/ }))
    await userEvent.click(screen.getByRole('button', { name: 'Log out' }))
    expect(await screen.findByText('You are still logged in')).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: 'Graphs and breadth-first search' }),
    ).toBeInTheDocument()
  })
})
