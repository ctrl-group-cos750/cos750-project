import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { User } from '../../auth/api.ts'
import { ada, fakeApi, renderApp } from '../../test/app.tsx'
import type { Readiness } from './staff.api.ts'

const grace: User = {
  id: 2,
  email: 'grace@example.com',
  displayName: 'Grace',
  isStaff: true,
  avatar: null,
  pictureUrl: null,
}

const readiness: Readiness = {
  students: 3,
  ready: 1,
  objectives: [
    { id: 5, text: 'Trace BFS by hand', metIndependently: 1, metWithSupport: 0, notYet: 2 },
  ],
  commonWrongAnswers: [
    {
      activityId: 614,
      title: 'Objective 4 · item 1 of 4',
      objectiveId: 4,
      answered: 3,
      wrong: 2,
      option: 'No. BFS will follow one path of word changes to its end',
      chosenBy: 2,
      whyWrong: 'Not quite. That describes depth-first search.',
    },
  ],
}

describe('Before the lecture (staff)', () => {
  it('shows who is ready, each objective, and the common wrong answer with its explanation', async () => {
    fakeApi({
      user: grace,
      overrides: { 'GET /api/staff/readiness': () => Response.json(readiness) },
    })
    renderApp('/staff/readiness')
    expect(await screen.findByRole('heading', { name: 'Before the lecture' })).toBeVisible()
    expect(await screen.findByText('1 of 3')).toBeVisible()
    expect(screen.getByText('On their own: 1 · With support: 0 · Not yet: 2')).toBeVisible()
    expect(screen.getByText(/2 of 3 got it wrong; 2 chose/)).toBeVisible()
    // The title names the objective already, so it isn't repeated (A13).
    expect(screen.getByText('Objective 4 · item 1 of 4')).toBeVisible()
    expect(screen.getByText('Not quite. That describes depth-first search.')).toBeVisible()
  })

  it('is listed in the staff portal', async () => {
    fakeApi({ user: grace })
    renderApp('/staff')
    const links = await screen.findAllByRole('link', { name: /Before the lecture/ })
    for (const link of links) expect(link).toHaveAttribute('href', '/staff/readiness')
  })

  it('is refused to a student', async () => {
    fakeApi({ user: ada })
    renderApp('/staff/readiness')
    expect(await screen.findByText('Only team members can open this page.')).toBeVisible()
  })
})
