import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ada, fakeApi, renderApp } from '../../test/app.tsx'
import type { ReviewPath } from './mastery.api.ts'
import { MemoryRouter } from 'react-router'
import { Markdown } from '../../components'

const PATH: ReviewPath = {
  objectiveId: 5,
  objectiveText: 'Trace BFS manually on a given graph.',
  criterion: 'Correct queue, visited set and next vertex at every step, with at most one error.',
  state: 'not_yet',
  progress: { answered: 0, total: 1 },
  steps: [
    {
      id: 1501,
      kind: 'worked_example',
      title: 'Tracing BFS, again',
      body: 'Take the vertex at the **front** of the queue.\n\nThen call `popleft()`.',
      activityId: null,
      purpose: null,
      answered: false,
    },
    {
      id: 1502,
      kind: 'activity',
      title: 'Practice trace',
      body: '',
      activityId: 1501,
      purpose: 'review',
      answered: true,
    },
    {
      id: 1503,
      kind: 'activity',
      title: 'Fresh trace',
      body: '',
      activityId: 1502,
      purpose: 'mastery',
      answered: false,
    },
  ],
}

function withPath(answer: () => Response) {
  return fakeApi({ user: ada, overrides: { 'GET /api/me/review/5': answer } })
}

function step(title: string) {
  const item = screen.getByRole('heading', { name: title }).closest('li')
  if (!item) throw new Error(`no step ${title}`)
  return within(item)
}

describe('ReviewPage', () => {
  it('opens a step whose page leads back to the path (#146)', async () => {
    fakeApi({
      user: ada,
      overrides: {
        'GET /api/me/review/5': () => Response.json(PATH),
        'GET /api/activities/1502': () =>
          Response.json({ detail: 'Activity not found.' }, { status: 404 }),
      },
    })
    renderApp('/review/5')
    await userEvent.click(await screen.findByRole('link', { name: 'Answer: Fresh trace' }))
    expect(await screen.findByRole('link', { name: /Back to the review path/ })).toHaveAttribute(
      'href',
      '/review/5',
    )
  })

  it('teaches the objective again, then practice, then the fresh questions', async () => {
    withPath(() => Response.json(PATH))
    renderApp('/review/5')
    expect(await screen.findByRole('heading', { name: 'Review: objective 5' })).toBeVisible()
    expect(screen.getByText('Not yet')).toBeVisible()
    expect(screen.getByText(/Fresh questions answered: 0 of 1/)).toBeVisible()
    expect(screen.getByText('front')).toContainHTML('<strong>front</strong>')

    expect(step('Practice trace').getByText('Answered')).toBeVisible()
    expect(step('Practice trace').getByRole('link', { name: /Practise again/ })).toHaveAttribute(
      'href',
      '/activities/1501',
    )
    expect(step('Fresh trace').getByText(/Your first answer counts/)).toBeVisible()
    expect(step('Fresh trace').getByRole('link', { name: 'Answer: Fresh trace' })).toHaveAttribute(
      'href',
      '/activities/1502',
    )
    expect(screen.getByRole('link', { name: 'Back to your report' })).toHaveAttribute(
      'href',
      '/report',
    )
  })

  it('says the result is up to date once every fresh question is answered', async () => {
    const steps = structuredClone(PATH.steps)
    for (const s of steps) s.answered = true
    withPath(() =>
      Response.json({
        ...PATH,
        state: 'met_independently',
        progress: { answered: 1, total: 1 },
        steps,
      }),
    )
    renderApp('/review/5')
    expect(await screen.findByText(/your result above is up to date/)).toBeVisible()
    expect(screen.getByText('Met independently')).toBeVisible()
    expect(step('Fresh trace').getByRole('link', { name: /See it again/ })).toBeVisible()
  })

  it('explains a path that is not open yet', async () => {
    withPath(() =>
      Response.json(
        { detail: "This review path opens when the mastery check marks the objective 'not yet'." },
        { status: 403 },
      ),
    )
    renderApp('/review/5')
    expect(await screen.findByText(/opens when the mastery check/)).toBeVisible()
    expect(screen.getByRole('link', { name: 'Back to your report' })).toBeVisible()
  })

  it('refuses an objective that is not a number', async () => {
    fakeApi({ user: ada })
    renderApp('/review/abc')
    expect(await screen.findByText('There is no such objective.')).toBeVisible()
  })
})

describe('Review step text', () => {
  it('renders code blocks and tables, and never runs the content as HTML', async () => {
    const { container } = render(
      <MemoryRouter>
        <Markdown>
          {
            'One **two** `three`\n\n```python\nqueue = deque()\n```\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n<img src=x onerror=alert(1)>'
          }
        </Markdown>
      </MemoryRouter>,
    )
    expect(container.querySelector('strong')).toHaveTextContent('two')
    expect(container.querySelector('pre')).toHaveTextContent('queue = deque()')
    expect(container.querySelector('table')).not.toBeNull()
    expect(container.querySelector('img')).toBeNull()
    expect(container).not.toHaveTextContent('```')
  })
})
