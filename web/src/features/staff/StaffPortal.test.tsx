import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { User } from '../../auth/api.ts'
import { ada, fakeApi, renderApp } from '../../test/app.tsx'

const grace: User = { id: 2, email: 'grace@example.com', displayName: 'Grace', isStaff: true }

const twoVideos = () =>
  Response.json([
    { id: 1, title: 'Meet BFS', durationSeconds: 300, checkpointCount: 2 },
    { id: 2, title: 'What is a graph?', durationSeconds: 240, checkpointCount: 1 },
  ])

describe('staff portal', () => {
  it('is not in the navbar for a student', async () => {
    fakeApi({ user: ada })
    renderApp('/')
    await screen.findByRole('heading', { name: 'Welcome, Ada' })
    expect(screen.queryByRole('link', { name: 'Staff portal' })).not.toBeInTheDocument()
  })

  it('refuses a student who types the address', async () => {
    fakeApi({ user: ada })
    renderApp('/staff')
    expect(await screen.findByText('Only team members can open this page.')).toBeInTheDocument()
  })

  it('opens from the navbar and lists every setup area', async () => {
    fakeApi({ user: grace, overrides: { 'GET /api/staff/videos': twoVideos } })
    renderApp('/')
    const main = await screen.findByRole('navigation', { name: 'Main' })
    await userEvent.click(within(main).getByRole('link', { name: 'Staff portal' }))

    expect(await screen.findByRole('heading', { name: 'Staff portal' })).toBeInTheDocument()
    expect(within(main).getByRole('link', { name: 'Staff portal' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    expect(await screen.findByText('2 videos')).toBeInTheDocument()
  })

  it('goes from the overview to the videos page and back with its own menu', async () => {
    fakeApi({ user: grace, overrides: { 'GET /api/staff/videos': twoVideos } })
    renderApp('/staff')
    const cards = await screen.findByRole('list')
    await userEvent.click(within(cards).getByRole('link', { name: 'Videos' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Videos' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Meet BFS' })).toBeInTheDocument()

    const menu = screen.getByRole('navigation', { name: 'Staff portal' })
    expect(within(menu).getByRole('link', { name: 'Videos' })).toHaveAttribute(
      'aria-current',
      'page',
    )
    // The navbar link stays highlighted on every page in the portal.
    const main = screen.getByRole('navigation', { name: 'Main' })
    expect(within(main).getByRole('link', { name: 'Staff portal' })).toHaveAttribute(
      'aria-current',
      'page',
    )

    await userEvent.click(within(menu).getByRole('link', { name: 'Overview' }))
    expect(await screen.findByRole('heading', { name: 'Staff portal' })).toBeInTheDocument()
  })
})
