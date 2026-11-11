import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ada, fakeApi, renderApp } from '../../test/app.tsx'
import type { MasteryReport, ObjectiveReport } from './mastery.api.ts'

function objective(id: number, more: Partial<ObjectiveReport> = {}): ObjectiveReport {
  return {
    id,
    text: `Objective ${id} text`,
    criterion: 'At least 4 of 5 items correct.',
    state: 'met_independently',
    answered: 1,
    total: 1,
    review: null,
    ...more,
  }
}

function withReport(report: MasteryReport | (() => Response)) {
  return fakeApi({
    user: ada,
    overrides: {
      'GET /api/me/report': typeof report === 'function' ? report : () => Response.json(report),
    },
  })
}

function row(n: number) {
  const item = screen.getByText(`Objective ${n} text`).closest('li')
  if (!item) throw new Error(`no row for objective ${n}`)
  return within(item)
}

describe('ReportPage', () => {
  it('shows each objective in plain words and says the student is ready', async () => {
    withReport({
      ready: true,
      objectives: [objective(1), objective(2, { state: 'met_with_support' })],
    })
    renderApp('/report')
    expect(await screen.findByRole('heading', { name: 'Your mastery report' })).toBeVisible()
    expect(screen.getByText('Ready for the lecture')).toBeVisible()
    expect(row(1).getByText('Met independently')).toBeVisible()
    expect(row(1).getByText('You met this on your own.')).toBeVisible()
    expect(row(2).getByText('Met with support')).toBeVisible()
    expect(row(2).getByText('You met this after using hint 3 or 4.')).toBeVisible()
    expect(row(1).getByText('To meet it: At least 4 of 5 items correct.')).toBeVisible()
    expect(screen.getByText(/is fine for the lecture/)).toBeVisible()
  })

  it('counts the objectives to review when one is not yet met', async () => {
    withReport({
      ready: false,
      objectives: [objective(1), objective(5, { state: 'not_yet' })],
    })
    renderApp('/report')
    expect(await screen.findByText('Not ready yet: 1 objective to review')).toBeVisible()
    expect(row(5).getByText('Not yet')).toBeVisible()
    expect(row(5).getByText('Work through its review path before the lecture.')).toBeVisible()
  })

  it('tells a student who has not finished the check what is left', async () => {
    withReport({
      ready: false,
      objectives: [
        objective(1, { state: 'not_attempted', answered: 0, total: 2 }),
        objective(2, { state: 'not_attempted', answered: 1, total: 3 }),
        objective(3, { state: 'not_attempted', answered: 0, total: 0 }),
        objective(4, { state: 'not_yet' }),
        objective(6, { state: 'not_yet' }),
      ],
    })
    renderApp('/report')
    // Both kinds of gap are counted: one never hides the other (#136 review).
    expect(
      await screen.findByText(
        'Not ready yet: 2 objectives to review and 2 objectives to answer in module 6',
      ),
    ).toBeVisible()
    expect(row(1).getByText('Not attempted')).toBeVisible()
    expect(row(1).getByText(/Not answered yet: its questions are in module 6/)).toBeVisible()
    expect(
      row(1).getByRole('link', { name: 'Answer its questions in module 6: objective 1' }),
    ).toHaveAttribute('href', '/modules/6')
    expect(row(2).getByText('1 of 3 questions answered in module 6.')).toBeVisible()
    expect(
      row(2).getByRole('link', { name: 'Finish its questions in module 6: objective 2' }),
    ).toHaveAttribute('href', '/modules/6')
    expect(row(3).getByText(/no questions on this objective yet/)).toBeVisible()
    expect(row(3).queryByRole('link')).not.toBeInTheDocument()
    expect(row(4).queryByRole('link', { name: /module 6/ })).not.toBeInTheDocument()
  })

  it('counts the objectives still to answer when nothing is not yet', async () => {
    withReport({ ready: false, objectives: [objective(1, { state: 'not_attempted' })] })
    renderApp('/report')
    expect(
      await screen.findByText('Not ready yet: 1 objective to answer in module 6'),
    ).toBeVisible()
  })

  it('asks the student to finish the check when nothing else explains it', async () => {
    withReport({
      ready: false,
      objectives: [objective(1, { state: 'not_attempted', answered: 0, total: 0 })],
    })
    renderApp('/report')
    expect(await screen.findByText('Not ready yet: finish the mastery check')).toBeVisible()
  })

  it('shows the error when the report cannot load', async () => {
    withReport(() => Response.json({ detail: 'Something went wrong.' }, { status: 500 }))
    renderApp('/report')
    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong.')
  })

  it('is linked from the header', async () => {
    withReport({ ready: false, objectives: [] })
    renderApp('/')
    expect(await screen.findByRole('link', { name: 'Report' })).toHaveAttribute('href', '/report')
  })

  it('links each open review path, worded for how far the student is', async () => {
    withReport({
      ready: false,
      objectives: [
        objective(2, { state: 'not_yet', review: { answered: 0, total: 2 } }),
        objective(3, { state: 'not_yet', review: { answered: 1, total: 2 } }),
        objective(5, { state: 'not_yet', review: { answered: 2, total: 2 } }),
        objective(6, { state: 'met_with_support', review: { answered: 1, total: 1 } }),
        objective(7, { review: { answered: 1, total: 1 } }),
      ],
    })
    renderApp('/report')
    const start = await screen.findByRole('link', { name: 'Start review path: objective 2' })
    expect(start).toHaveAttribute('href', '/review/2')
    expect(row(2).getByText('Work through its review path before the lecture.')).toBeVisible()
    expect(row(3).getByRole('link', { name: /Continue review path/ })).toBeVisible()
    expect(row(3).getByText('Review path: 1 of 2 fresh questions answered.')).toBeVisible()
    expect(row(5).getByText(/Still not yet after the review path/)).toBeVisible()
    expect(row(5).getByRole('link', { name: /Look back at the review path/ })).toBeVisible()
    expect(row(6).getByText('You met this after the review path, using hint 3 or 4.')).toBeVisible()
    expect(row(7).getByText('You met this on your own after the review path.')).toBeVisible()
  })

  it('has no review link for an objective whose path is not open', async () => {
    withReport({ ready: true, objectives: [objective(1)] })
    renderApp('/report')
    await screen.findByText('Ready for the lecture')
    expect(screen.queryByRole('link', { name: /review path/ })).toBeNull()
  })
})
