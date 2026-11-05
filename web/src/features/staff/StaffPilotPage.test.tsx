import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { User } from '../../auth/api.ts'
import { ada, fakeApi, renderApp } from '../../test/app.tsx'

const grace: User = { id: 2, email: 'grace@example.com', displayName: 'Grace', isStaff: true }

const insights = {
  students: 2,
  attempts: 4,
  hintsViewed: 3,
  activities: [
    {
      id: 1,
      title: 'Which leaves first?',
      kind: 'multiple_choice',
      students: 2,
      attempts: 3,
      wrongAttempts: 1,
      studentsPassed: 2,
      studentsWithSupport: 1,
    },
  ],
  videos: [
    {
      id: 7,
      title: 'Meet BFS',
      students: 2,
      checkpoints: [
        { id: 1, atSeconds: 20, activityTitle: 'Which leaves first?', studentsPassed: 2 },
        { id: 2, atSeconds: 45, activityTitle: 'What stops a loop?', studentsPassed: 1 },
      ],
    },
  ],
}

describe('pilot data page', () => {
  it('shows totals, the activities students struggle with, and where they stop', async () => {
    fakeApi({
      user: grace,
      overrides: { 'GET /api/staff/insights': () => Response.json(insights) },
    })
    renderApp('/staff/pilot')

    const table = await screen.findByRole('table')
    const row = within(table).getByText('Which leaves first?').closest('tr')!
    expect(within(row).getByText('2 of 2')).toBeInTheDocument() // passed
    expect(within(row).getByText('1 of 3')).toBeInTheDocument() // wrong answers
    expect(within(row).getByText('1 of 2')).toBeInTheDocument() // needed hint 3 or 4

    const video = screen.getByText('Meet BFS').closest('[data-slot=card]') as HTMLElement
    const checkpoints = within(video).getAllByRole('listitem')
    expect(within(checkpoints[0]!).getByText('2 of 2')).toBeInTheDocument()
    expect(within(checkpoints[1]!).getByText('1 of 2')).toBeInTheDocument()
    expect(within(checkpoints[1]!).getByText('0:45')).toBeInTheDocument()
  })

  it('links to the CSV downloads', async () => {
    fakeApi({
      user: grace,
      overrides: { 'GET /api/staff/insights': () => Response.json(insights) },
    })
    renderApp('/staff/pilot')
    const link = await screen.findByRole('link', { name: 'Download attempts.csv' })
    expect(link).toHaveAttribute('href', '/api/staff/export/attempts.csv')
    expect(screen.getByRole('link', { name: 'Download hints.csv' })).toHaveAttribute(
      'href',
      '/api/staff/export/hints.csv',
    )
  })

  it('says so before anyone has answered', async () => {
    fakeApi({
      user: grace,
      overrides: {
        'GET /api/staff/insights': () =>
          Response.json({ ...insights, students: 0, attempts: 0, activities: [], videos: [] }),
      },
    })
    renderApp('/staff/pilot')
    expect(await screen.findByText('No student has answered anything yet.')).toBeInTheDocument()
  })

  it('is refused to students', async () => {
    fakeApi({ user: ada })
    renderApp('/staff/pilot')
    expect(await screen.findByText('Only team members can open this page.')).toBeInTheDocument()
  })
})
