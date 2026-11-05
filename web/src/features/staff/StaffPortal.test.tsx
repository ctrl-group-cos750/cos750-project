import { screen, waitFor, within } from '@testing-library/react'
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

describe('staff members page', () => {
  const adaRow = { id: 1, email: 'ada@example.com', displayName: 'Ada' }
  const graceRow = { id: grace.id, email: grace.email, displayName: grace.displayName }

  /** A members list that the fake POST and DELETE change, like the real API. */
  function membersApi(initial = [graceRow]) {
    let members = [...initial]
    return fakeApi({
      user: grace,
      overrides: {
        'GET /api/staff/members': () => Response.json(members),
        'POST /api/staff/members': (body) => {
          const { email } = body as { email: string }
          if (email !== adaRow.email) {
            return Response.json(
              { detail: 'No account uses this email. They need to register in the app first.' },
              { status: 404 },
            )
          }
          members = [adaRow, ...members]
          return Response.json(adaRow)
        },
        'DELETE /api/staff/members/1': () => {
          members = members.filter((m) => m.id !== 1)
          return new Response(null, { status: 204 })
        },
      },
    })
  }

  it('lists the team, with no remove button on your own row', async () => {
    membersApi()
    renderApp('/staff/members')
    const row = (await screen.findByText('grace@example.com')).closest('li')!
    expect(within(row).getByText('(you)')).toBeInTheDocument()
    expect(within(row).queryByRole('button', { name: 'Remove access' })).not.toBeInTheDocument()
  })

  it('makes a registered account staff by email', async () => {
    const api = membersApi()
    renderApp('/staff/members')
    await userEvent.type(await screen.findByLabelText('Email'), 'ada@example.com')
    await userEvent.click(screen.getByRole('button', { name: 'Make staff' }))

    expect(await screen.findByText('Ada is a team member')).toBeInTheDocument()
    expect(await screen.findByText('ada@example.com')).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toHaveValue('')
    expect(api.callsTo('POST /api/staff/members')[0]?.body).toEqual({ email: 'ada@example.com' })
  })

  it('says to register first when no account uses the email', async () => {
    membersApi()
    renderApp('/staff/members')
    await userEvent.type(await screen.findByLabelText('Email'), 'nobody@example.com')
    await userEvent.click(screen.getByRole('button', { name: 'Make staff' }))
    expect(await screen.findByText(/register in the app first/)).toBeInTheDocument()
  })

  it('removes access only after confirming, and can be cancelled', async () => {
    const api = membersApi([adaRow, graceRow])
    renderApp('/staff/members')
    const row = (await screen.findByText('ada@example.com')).closest('li')!

    await userEvent.click(within(row).getByRole('button', { name: 'Remove access' }))
    await userEvent.click(within(row).getByRole('button', { name: 'Cancel' }))
    expect(api.callsTo('DELETE /api/staff/members/1')).toHaveLength(0)

    await userEvent.click(within(row).getByRole('button', { name: 'Remove access' }))
    expect(within(row).getByText("Remove Ada's staff access?")).toBeInTheDocument()
    await userEvent.click(within(row).getByRole('button', { name: 'Remove access' }))

    await waitFor(() => expect(screen.queryByText('ada@example.com')).not.toBeInTheDocument())
    expect(api.callsTo('DELETE /api/staff/members/1')).toHaveLength(1)
  })
})
