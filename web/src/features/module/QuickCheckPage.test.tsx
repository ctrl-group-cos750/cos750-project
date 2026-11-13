import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ada, fakeApi, renderApp } from '../../test/app.tsx'
import type { ModuleSummary, QuickCheck, QuickCheckResult } from './module.types.ts'

const modules: ModuleSummary[] = [2, 3, 4].map((n) => ({
  id: n,
  number: n,
  slug: `m${n}`,
  title: ['A graph in Python', 'Meet BFS', 'Build BFS'][n - 2],
  goals: [],
  estimatedMinutes: 10,
  status: 'open',
  segmentCount: 3,
  currentSegmentPosition: 0,
}))

const check: QuickCheck = {
  moduleId: 3,
  available: true,
  passMark: 3,
  questions: [1, 2, 3, 4].map((n) => ({
    id: 350 + n,
    title: `Topic ${n}`,
    prompt: `Question ${n}?`,
    options: [
      { id: 'a', label: `Right ${n}` },
      { id: 'b', label: `Wrong ${n}` },
    ],
  })),
}

function result(correct: number, extra: Partial<QuickCheckResult> = {}): QuickCheckResult {
  return {
    passed: correct >= 3,
    correct,
    total: 4,
    suggestion: correct >= 3 ? 'move_on' : 'work_through',
    suggestedModule: correct >= 3 ? 4 : 3,
    lookAt: [1, 2, 3, 4].filter((n) => n > correct).map((n) => `Topic ${n}`),
    items: [1, 2, 3, 4].map((n) => ({
      activityId: 350 + n,
      title: `Topic ${n}`,
      prompt: `Question ${n}?`,
      correct: n <= correct,
      chosen: n <= correct ? `Right ${n}` : `Wrong ${n}`,
      answer: `Right ${n}`,
      explanation: `Because ${n}.`,
    })),
    ...extra,
  }
}

function setup(state: QuickCheck, marked: QuickCheckResult = result(4)) {
  return fakeApi({
    user: ada,
    overrides: {
      'GET /api/modules': () => Response.json(modules),
      'GET /api/modules/:id/quick-check': () => Response.json(state),
      'POST /api/modules/:id/quick-check': () => Response.json(marked),
    },
  })
}

describe('QuickCheckPage (#214)', () => {
  it('asks every question at once, with no hints, and sends one answer each', async () => {
    const api = setup(check)
    renderApp('/modules/3/check')
    expect(
      await screen.findByRole('heading', { name: 'Module 3 · Meet BFS: quick check' }),
    ).toBeInTheDocument()
    expect(screen.getAllByRole('radio')).toHaveLength(8)
    expect(screen.queryByRole('button', { name: /hint/i })).toBeNull()
    const user = userEvent.setup()
    await user.click(screen.getByLabelText('Right 1'))
    await user.click(screen.getByLabelText('Right 2'))
    await user.click(screen.getByLabelText('Right 3'))
    await user.click(screen.getByRole('button', { name: 'Check my answers' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('question 4 has no answer yet')
    expect(api.calls.some((c) => c.method === 'POST')).toBe(false)

    await user.click(screen.getByLabelText('Wrong 4'))
    await user.click(screen.getByRole('button', { name: 'Check my answers' }))
    // The result names the module (#215 review).
    expect(
      await screen.findByRole('heading', {
        name: 'Module 3 · Meet BFS: quick check, 4 of 4 right',
      }),
    ).toBeInTheDocument()
    const post = api.calls.find((c) => c.method === 'POST')
    expect(post?.body).toEqual({
      answers: [
        { activityId: 351, selected: 'a' },
        { activityId: 352, selected: 'a' },
        { activityId: 353, selected: 'a' },
        { activityId: 354, selected: 'b' },
      ],
    })
  })

  it('after a pass: says so and moves the student on to the next module', async () => {
    setup({ ...check, available: false, questions: [], result: result(3) })
    renderApp('/modules/3/check')
    expect(await screen.findByText('You know this already')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Go to module 4: Build BFS/ })).toHaveAttribute(
      'href',
      '/modules/4',
    )
    expect(screen.getByText(/Worth a second look: Topic 4/)).toBeInTheDocument()
  })

  it('after a fail: names what to look at and suggests working through the module', async () => {
    setup({ ...check, available: false, questions: [], result: result(2) })
    renderApp('/modules/3/check')
    expect(await screen.findByText(/Now you know what to look at: Topic 3, Topic 4/)).toBeVisible()
    expect(screen.getByRole('link', { name: 'Work through this module →' })).toHaveAttribute(
      'href',
      '/modules/3',
    )
    expect(screen.getAllByText('to look at')).toHaveLength(2)
    expect(screen.getByText('The answer: Right 3')).toBeInTheDocument()
  })

  it('after nearly everything wrong: suggests starting with an earlier module', async () => {
    setup({
      ...check,
      available: false,
      questions: [],
      result: result(1, { suggestion: 'start_with', suggestedModule: 2 }),
    })
    renderApp('/modules/3/check')
    expect(await screen.findByRole('link', { name: 'Start with module 2 →' })).toHaveAttribute(
      'href',
      '/modules/2',
    )
    expect(screen.getByRole('link', { name: 'Work through this module' })).toHaveAttribute(
      'href',
      '/modules/3',
    )
  })

  it('sends the answers once, however fast "Check my answers" is pressed (#215)', async () => {
    let release: () => void = () => {}
    const api = fakeApi({
      user: ada,
      overrides: {
        'GET /api/modules': () => Response.json(modules),
        'GET /api/modules/:id/quick-check': () => Response.json(check),
        'POST /api/modules/:id/quick-check': () =>
          new Promise<Response>((resolve) => {
            release = () => resolve(Response.json(result(4)))
          }),
      },
    })
    renderApp('/modules/3/check')
    const user = userEvent.setup()
    await screen.findByLabelText('Right 1')
    await user.click(screen.getByLabelText('Right 1'))
    await user.click(screen.getByLabelText('Right 2'))
    await user.click(screen.getByLabelText('Right 3'))
    await user.click(screen.getByLabelText('Right 4'))
    const button = screen.getByRole('button', { name: 'Check my answers' })
    // Pressed, then the form sent again before the first answer comes back: Enter in a field
    // submits a form without going through the button (implicit submission).
    const form = button.closest('form')!
    fireEvent.submit(form)
    fireEvent.submit(form)
    await user.click(button)
    release()
    expect(await screen.findByRole('heading', { name: /4 of 4 right/ })).toBeInTheDocument()
    expect(api.callsTo('POST /api/modules/3/quick-check')).toHaveLength(1)
  })

  it('refreshes the rewards once marked, and names the module in the tab (#215)', async () => {
    const api = setup(check)
    renderApp('/modules/3/check')
    const user = userEvent.setup()
    await screen.findByLabelText('Right 1')
    await user.click(screen.getByLabelText('Right 1'))
    await user.click(screen.getByLabelText('Right 2'))
    await user.click(screen.getByLabelText('Right 3'))
    await user.click(screen.getByLabelText('Right 4'))
    await waitFor(() => expect(document.title).toMatch(/Quick check: module 3, Meet BFS/))
    // The badge announcer has the rewards on screen: they are fetched again at once (the skills,
    // not on screen here, are marked stale, so the map fetches them when it opens).
    await waitFor(() => expect(api.callsTo('GET /api/rewards').length).toBeGreaterThan(0))
    const before = api.callsTo('GET /api/rewards').length
    await user.click(screen.getByRole('button', { name: 'Check my answers' }))
    await screen.findByRole('heading', { name: /4 of 4 right/ })
    await waitFor(() => expect(api.callsTo('GET /api/rewards').length).toBeGreaterThan(before))
  })
})
