import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { User } from '../../auth/api.ts'
import { ada, fakeApi, renderApp } from '../../test/app.tsx'

const grace: User = {
  id: 2,
  email: 'grace@example.com',
  displayName: 'Grace',
  isStaff: true,
  avatar: null,
  pictureUrl: null,
}

const twoVideos = () =>
  Response.json([
    { id: 1, title: 'Meet BFS', durationSeconds: 300, checkpointCount: 2 },
    { id: 2, title: 'What is a graph?', durationSeconds: 240, checkpointCount: 1 },
  ])

describe('staff portal', () => {
  it('is not in the navbar for a student', async () => {
    fakeApi({ user: ada })
    renderApp('/')
    await screen.findByRole('heading', { name: 'Graphs and breadth-first search' })
    expect(screen.queryByRole('link', { name: 'Staff portal' })).not.toBeInTheDocument()
  })

  it('refuses a student who types the address', async () => {
    fakeApi({ user: ada })
    renderApp('/staff')
    expect(await screen.findByText('Only team members can open this page.')).toBeInTheDocument()
  })

  it('opens from the account menu and lists every setup area', async () => {
    fakeApi({ user: grace, overrides: { 'GET /api/staff/videos': twoVideos } })
    renderApp('/')
    await userEvent.click(await screen.findByRole('button', { name: /your account/ }))
    await userEvent.click(screen.getByRole('link', { name: 'Staff portal' }))

    expect(await screen.findByRole('heading', { name: 'Staff portal' })).toBeInTheDocument()
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

    await userEvent.click(within(menu).getByRole('link', { name: 'Overview' }))
    expect(await screen.findByRole('heading', { name: 'Staff portal' })).toBeInTheDocument()
  })
})

const adaRow = { id: 1, email: 'ada@example.com', displayName: 'Ada' }
const alanRow = { id: 3, email: 'alan@example.com', displayName: 'Alan' }
const graceRow = { id: grace.id, email: grace.email, displayName: grace.displayName }
const account = (m: typeof adaRow, isStaff: boolean) => ({
  ...m,
  isStaff,
  createdAt: '2026-11-01T10:00:00Z',
  lastActiveAt: m.id === 1 ? '2026-11-04T12:30:00Z' : null,
})

/** A fake API whose members and accounts lists change with POST and DELETE, like the real one. */
function portalApi(staffIds = [grace.id]) {
  let staff = new Set(staffIds)
  let people = [adaRow, alanRow, graceRow]
  const detail = (id: number) => ({
    ...account(
      people.find((p) => p.id === id)!,
      staff.has(id),
    ),
    stats: {
      attempts: 4,
      correctAttempts: 3,
      activitiesTried: 2,
      activitiesPassed: 2,
      hintsViewed: 1,
    },
    videos: [{ id: 7, title: 'Meet BFS', checkpointsPassed: 1, checkpointsTotal: 2 }],
    recentAttempts: [
      {
        id: 11,
        activityTitle: 'Which leaves first?',
        kind: 'multiple_choice',
        correct: true,
        hintLevel: 1,
        createdAt: '2026-11-04T12:30:00Z',
      },
    ],
  })
  const overrides: Record<string, (body: unknown) => Response> = {
    'GET /api/staff/members': () => Response.json(people.filter((p) => staff.has(p.id))),
    'GET /api/staff/accounts': () => Response.json(people.map((p) => account(p, staff.has(p.id)))),
    'POST /api/staff/members': (body) => {
      const found = people.find((p) => p.email === (body as { email: string }).email)!
      staff = new Set([...staff, found.id])
      return Response.json(found)
    },
  }
  for (const p of people) {
    overrides[`GET /api/staff/accounts/${p.id}`] = () => Response.json(detail(p.id))
    overrides[`DELETE /api/staff/members/${p.id}`] = () => {
      staff.delete(p.id)
      return new Response(null, { status: 204 })
    }
    overrides[`DELETE /api/staff/accounts/${p.id}`] = () => {
      people = people.filter((q) => q.id !== p.id)
      return new Response(null, { status: 204 })
    }
  }
  return fakeApi({ user: grace, overrides })
}

describe('staff members page', () => {
  it('lists the team, with no remove button on your own row', async () => {
    portalApi()
    renderApp('/staff/members')
    const row = (await screen.findByText('grace@example.com')).closest('li')!
    expect(within(row).getByText('(you)')).toBeInTheDocument()
    expect(within(row).queryByRole('button', { name: 'Remove access' })).not.toBeInTheDocument()
  })

  it('narrows the accounts as you type, then makes the chosen one staff', async () => {
    const api = portalApi()
    renderApp('/staff/members')
    const search = await screen.findByLabelText('Name or email')

    await userEvent.type(search, 'a')
    const matches = await screen.findByRole('list', { name: 'Matching accounts' })
    // Students only: Grace is staff already.
    expect(within(matches).getAllByRole('listitem')).toHaveLength(2)

    await userEvent.type(search, 'da')
    expect(within(matches).getAllByRole('listitem')).toHaveLength(1)
    await userEvent.click(within(matches).getByRole('button', { name: 'Make Ada staff' }))

    expect(await screen.findByText('Ada is a team member')).toBeInTheDocument()
    // The results went: focus is on the message, not the page (A9).
    await waitFor(() =>
      expect(screen.getByText('Ada is a team member').closest('[role="alert"]')).toHaveFocus(),
    )
    expect(api.callsTo('POST /api/staff/members')[0]?.body).toEqual({ email: 'ada@example.com' })
    expect(await screen.findByText('ada@example.com')).toBeInTheDocument() // now in the team
    expect(search).toHaveValue('')
  })

  it('says to register first when nothing matches', async () => {
    portalApi()
    renderApp('/staff/members')
    await userEvent.type(await screen.findByLabelText('Name or email'), 'nobody')
    expect(await screen.findByText(/register in\s+the app first/)).toBeInTheDocument()
  })

  it('removes access only after confirming, and can be cancelled', async () => {
    const api = portalApi([adaRow.id, grace.id])
    renderApp('/staff/members')
    const row = (await screen.findByText('ada@example.com')).closest('li')!

    await userEvent.click(within(row).getByRole('button', { name: 'Remove access' }))
    // Focus moves into the question, and back to the row's button on Cancel (A9).
    expect(within(row).getByRole('button', { name: 'Remove access' })).toHaveFocus()
    await userEvent.click(within(row).getByRole('button', { name: 'Cancel' }))
    expect(within(row).getByRole('button', { name: 'Remove access' })).toHaveFocus()
    expect(api.callsTo('DELETE /api/staff/members/1')).toHaveLength(0)

    await userEvent.click(within(row).getByRole('button', { name: 'Remove access' }))
    expect(within(row).getByText("Remove Ada's staff access?")).toBeInTheDocument()
    await userEvent.keyboard('{Escape}')
    expect(within(row).queryByText("Remove Ada's staff access?")).not.toBeInTheDocument()
    await userEvent.click(within(row).getByRole('button', { name: 'Remove access' }))
    await userEvent.click(within(row).getByRole('button', { name: 'Remove access' }))

    await waitFor(() => expect(screen.queryByText('ada@example.com')).not.toBeInTheDocument())
    expect(screen.getByRole('heading', { name: 'Current team members' })).toHaveFocus()
    expect(api.callsTo('DELETE /api/staff/members/1')).toHaveLength(1)
  })
})

describe('accounts pages', () => {
  it('lists every account and narrows it as you type', async () => {
    portalApi()
    renderApp('/staff/accounts')
    expect(await screen.findByText('3 accounts')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Search by name'), 'ALAN')
    expect(screen.getByText('1 of 3 accounts match')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Alan' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Ada' })).not.toBeInTheDocument()
  })

  it("opens an account's overview with its stats", async () => {
    portalApi()
    renderApp('/staff/accounts')
    await userEvent.click(await screen.findByRole('link', { name: 'Ada' }))
    expect(await screen.findByRole('heading', { level: 1, name: 'Ada' })).toBeInTheDocument()
    expect(screen.getByText('75% of answers')).toBeInTheDocument()
    expect(screen.getByText('1 of 2 checkpoints passed')).toBeInTheDocument()
    expect(screen.getByText('Which leaves first?')).toBeInTheDocument()
  })

  it('makes an account staff from its overview', async () => {
    const api = portalApi()
    renderApp('/staff/accounts/1')
    await userEvent.click(await screen.findByRole('button', { name: 'Make staff' }))
    expect(await screen.findByRole('button', { name: 'Remove staff access' })).toBeInTheDocument()
    expect(api.callsTo('POST /api/staff/members')).toHaveLength(1)
  })

  it('deletes an account only once its email is typed, then goes back to the list', async () => {
    const api = portalApi()
    renderApp('/staff/accounts/1')
    const button = await screen.findByRole('button', { name: 'Delete account' })
    expect(button).toBeDisabled()
    await userEvent.type(
      screen.getByLabelText('Type ada@example.com to confirm'),
      'ada@example.com',
    )
    await userEvent.click(button)

    expect(await screen.findByText('2 accounts')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Ada' })).not.toBeInTheDocument()
    expect(api.callsTo('DELETE /api/staff/accounts/1')).toHaveLength(1)
  })

  it('has no access or delete controls on your own account', async () => {
    portalApi()
    renderApp(`/staff/accounts/${grace.id}`)
    expect(await screen.findByRole('heading', { level: 1, name: /Grace/ })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Delete account' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /staff/i })).not.toBeInTheDocument()
  })
})

describe('video editor', () => {
  it('lists what a new video still needs without an empty item (#146)', async () => {
    portalApi()
    renderApp('/staff/videos/new')
    expect(
      await screen.findByText('Still needs the video, the captions, a title.'),
    ).toBeInTheDocument()
  })
})
