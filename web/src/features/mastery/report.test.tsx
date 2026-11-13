import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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

/** Module 6, the mastery check, as the module list gives it. */
function moduleSix(status: 'locked' | 'open' | 'in_progress' | 'complete') {
  return {
    id: 6,
    number: 6,
    slug: 'mastery',
    title: 'Mastery check and report',
    goals: [],
    estimatedMinutes: 10,
    status,
    segmentCount: 25,
    currentSegmentPosition: 0,
  }
}

function withReport(
  report: MasteryReport | (() => Response),
  checkStatus: 'locked' | 'open' | 'in_progress' | 'complete' = 'open',
) {
  return fakeApi({
    user: ada,
    overrides: {
      'GET /api/me/report': typeof report === 'function' ? report : () => Response.json(report),
      'GET /api/modules': () => Response.json([moduleSix(checkStatus)]),
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

  it('names module 6 without linking to it while it is still locked (#136 review)', async () => {
    withReport(
      {
        ready: false,
        objectives: [
          objective(1, { state: 'not_attempted', answered: 0, total: 2 }),
          objective(2, { state: 'not_attempted', answered: 0, total: 3 }),
        ],
      },
      'locked',
    )
    renderApp('/report')
    expect(
      await screen.findByText(
        'Not ready yet: 2 objectives to answer in module 6, once you reach it',
      ),
    ).toBeVisible()
    expect(row(1).getByText(/Not answered yet: its questions are in module 6/)).toBeVisible()
    expect(screen.queryByRole('link', { name: /questions in module 6/ })).not.toBeInTheDocument()
  })

  it('links module 6 once it is open, whatever its progress', async () => {
    withReport(
      {
        ready: false,
        objectives: [objective(5, { state: 'not_attempted', answered: 0, total: 1 })],
      },
      'complete',
    )
    renderApp('/report')
    expect(
      await screen.findByRole('link', { name: 'Answer its questions in module 6: objective 5' }),
    ).toHaveAttribute('href', '/modules/6')
    expect(screen.getByText('Not ready yet: 1 objective to answer in module 6')).toBeVisible()
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

  it('is linked from the account menu', async () => {
    withReport({ ready: false, objectives: [] })
    renderApp('/')
    await userEvent.click(await screen.findByRole('button', { name: /your account/ }))
    expect(screen.getByRole('link', { name: 'Mastery report' })).toHaveAttribute('href', '/report')
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

  it('sends a student whose review paths are done but still not yet to the lecture, not round in a circle', async () => {
    withReport({
      ready: false,
      objectives: [
        objective(1),
        objective(5, { state: 'not_yet', review: { answered: 2, total: 2 } }),
      ],
    })
    renderApp('/report')
    expect(
      await screen.findByText('Not ready yet: 1 objective to bring to the lecture'),
    ).toBeVisible()
    expect(screen.getByText(/bring to the lecture: it starts from here/)).toBeVisible()
    expect(screen.queryByRole('link', { name: /Continue your modules/ })).toBeNull()
  })

  it('has no review link for an objective whose path is not open', async () => {
    withReport({ ready: true, objectives: [objective(1)] })
    renderApp('/report')
    await screen.findByText('Ready for the lecture')
    expect(screen.queryByRole('link', { name: /review path/ })).toBeNull()
  })

  it('says an objective waits for the end of the check once its questions are answered (#144)', async () => {
    withReport({
      ready: false,
      objectives: [
        objective(1, { state: 'not_attempted', answered: 2, total: 2 }),
        objective(2, { state: 'not_attempted', answered: 0, total: 1 }),
      ],
    })
    renderApp('/report')
    await screen.findByRole('heading', { name: 'Your mastery report' })
    expect(row(1).getByText(/Its result shows when you finish the mastery check/)).toBeVisible()
    expect(
      row(1).getByRole('link', { name: 'Finish the mastery check in module 6: objective 1' }),
    ).toHaveAttribute('href', '/modules/6')
  })
})

describe('ReportPage: the summary and the one next step', () => {
  it('counts the objectives in each state', async () => {
    withReport({
      ready: false,
      objectives: [
        objective(1),
        objective(2, { state: 'met_with_support' }),
        objective(3, { state: 'not_yet', review: { answered: 0, total: 3 } }),
        objective(4, { state: 'not_attempted', answered: 0, total: 4 }),
      ],
    })
    renderApp('/report')
    await screen.findByRole('heading', { name: 'Your mastery report' })
    const tile = (label: string) =>
      screen
        .getAllByText(label)
        .find((e) => e.tagName === 'DT')!
        .closest('div')!
    expect(within(tile('Met on your own')).getByText('1')).toBeInTheDocument()
    expect(within(tile('Met with support')).getByText('1')).toBeInTheDocument()
    expect(within(tile('Not yet')).getByText('1')).toBeInTheDocument()
    expect(within(tile('Still to answer')).getByText('1')).toBeInTheDocument()
  })

  it('points first to a review path that is still open', async () => {
    withReport({
      ready: false,
      objectives: [
        objective(1),
        objective(5, { state: 'not_yet', review: { answered: 0, total: 3 } }),
      ],
    })
    renderApp('/report')
    expect(
      await screen.findByRole('link', { name: "Start with objective 5's review path →" }),
    ).toHaveAttribute('href', '/review/5')
  })

  it('points to the mastery check while its questions are unanswered', async () => {
    withReport({
      ready: false,
      objectives: [objective(1, { state: 'not_attempted', answered: 0, total: 5 })],
    })
    renderApp('/report')
    expect(await screen.findByRole('link', { name: 'Go to the mastery check →' })).toHaveAttribute(
      'href',
      '/modules/6',
    )
  })

  it('sends a ready student back to the modules', async () => {
    withReport({ ready: true, objectives: [objective(1)] })
    renderApp('/report')
    expect(await screen.findByRole('link', { name: 'Back to your modules →' })).toHaveAttribute(
      'href',
      '/',
    )
  })
})
