import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ada, fakeApi, renderApp } from '../../test/app.tsx'
import { Matching } from './Matching.tsx'
import { MultipleChoice } from './MultipleChoice.tsx'
import type { AttemptResult, MatchingActivity, MultipleChoiceActivity } from './activities.types.ts'

const choice: MultipleChoiceActivity = {
  id: 21,
  kind: 'multiple_choice',
  title: 'Which structure?',
  visible: true,
  config: {
    prompt: 'Which structure does BFS use for its frontier?',
    options: [
      { id: 'a', label: 'A stack' },
      { id: 'b', label: 'A queue' },
    ],
  },
}

const matching: MatchingActivity = {
  id: 22,
  kind: 'matching',
  title: 'Model the situation',
  visible: true,
  config: {
    prompt: 'Match each situation with the graph that models it.',
    left: [
      { id: 'roads', label: 'Two-way roads between towns' },
      { id: 'follows', label: 'Who follows whom online' },
    ],
    right: [
      { id: 'undirected', label: 'Undirected graph' },
      { id: 'directed', label: 'Directed graph' },
      { id: 'tree', label: 'Tree' },
    ],
  },
}

function attempt(overrides: Partial<AttemptResult>): AttemptResult {
  return {
    id: 1,
    activityId: 22,
    correct: false,
    score: 0,
    parts: [],
    feedback: '',
    hintLevel: 0,
    ...overrides,
  }
}

describe('multiple choice', () => {
  it('asks for an answer before checking, then submits the chosen option', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn<(selected: string) => Promise<void>>().mockResolvedValue(undefined)
    render(
      <MultipleChoice
        activity={choice}
        result={undefined}
        submitting={false}
        onSubmit={onSubmit}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'Check answer' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Choose an answer')
    expect(onSubmit).not.toHaveBeenCalled()

    await user.click(screen.getByRole('radio', { name: 'A queue' }))
    await user.click(screen.getByRole('button', { name: 'Check answer' }))
    expect(onSubmit).toHaveBeenCalledWith('b')
  })
})

describe('matching', () => {
  it('submits the pairs chosen, leaving an unmatched item out', async () => {
    const user = userEvent.setup()
    const onSubmit = vi
      .fn<(pairs: Record<string, string>) => Promise<void>>()
      .mockResolvedValue(undefined)
    render(
      <Matching activity={matching} result={undefined} submitting={false} onSubmit={onSubmit} />,
    )

    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Two-way roads between towns' }),
      'Undirected graph',
    )
    await user.click(screen.getByRole('button', { name: 'Check answer' }))

    expect(onSubmit).toHaveBeenCalledWith({ roads: 'undirected' })
  })

  it("marks each item, and drops an item's mark once the student changes it", async () => {
    const user = userEvent.setup()
    const onSubmit = vi
      .fn<(pairs: Record<string, string>) => Promise<void>>()
      .mockResolvedValue(undefined)
    const { rerender } = render(
      <Matching activity={matching} result={undefined} submitting={false} onSubmit={onSubmit} />,
    )
    const roads = screen.getByRole('combobox', { name: 'Two-way roads between towns' })
    const follows = screen.getByRole('combobox', { name: 'Who follows whom online' })
    await user.selectOptions(roads, 'Undirected graph')
    await user.selectOptions(follows, 'Tree')
    await user.click(screen.getByRole('button', { name: 'Check answer' }))

    rerender(
      <Matching
        activity={matching}
        result={attempt({
          parts: [
            { ref: 0, correct: true, message: null },
            { ref: 1, correct: false, message: 'Following goes one way only.' },
          ],
        })}
        submitting={false}
        onSubmit={onSubmit}
      />,
    )
    expect(roads).toHaveAccessibleDescription('Correct')
    expect(follows).toHaveAccessibleDescription('Check again: Following goes one way only.')

    await user.selectOptions(follows, 'Directed graph')
    expect(follows).not.toHaveAccessibleDescription()
    expect(screen.queryByText(/Following goes one way only/)).not.toBeInTheDocument()
    expect(roads).toHaveAccessibleDescription('Correct')
  })

  it('locks the answer once it is correct', () => {
    render(
      <Matching
        activity={matching}
        result={attempt({ correct: true, score: 1 })}
        submitting={false}
        onSubmit={vi.fn<(pairs: Record<string, string>) => Promise<void>>()}
      />,
    )
    for (const select of screen.getAllByRole('combobox')) expect(select).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Check answer' })).toBeDisabled()
  })
})

describe('the activity page', () => {
  it('runs a matching activity end to end: load, pair, check, feedback', async () => {
    const api = fakeApi({
      user: ada,
      overrides: {
        'GET /api/activities/22': () => Response.json(matching),
        'POST /api/activities/22/attempts': () =>
          Response.json(
            attempt({
              parts: [
                { ref: 0, correct: true, message: null },
                { ref: 1, correct: false, message: 'Choose a match for this one.' },
              ],
              score: 0.5,
              feedback: '1 of 2 correct.',
            }),
          ),
      },
    })
    const user = userEvent.setup()
    renderApp('/activities/22')

    await user.selectOptions(
      await screen.findByRole('combobox', { name: 'Two-way roads between towns' }),
      'Undirected graph',
    )
    await user.click(screen.getByRole('button', { name: 'Check answer' }))

    await waitFor(() => expect(api.callsTo('POST /api/activities/22/attempts')).toHaveLength(1))
    expect(api.callsTo('POST /api/activities/22/attempts')[0]?.body).toEqual({
      submitted: { pairs: { roads: 'undirected' } },
    })
    const results = await screen.findByRole('region', { name: 'Submission results' })
    expect(within(results).getByText('1 of 2 correct.')).toBeInTheDocument()
    // Matching marks each item inline, so the panel doesn't list them a second time.
    expect(within(results).queryByRole('list')).not.toBeInTheDocument()
    expect(screen.getByText('Check again: Choose a match for this one.')).toBeInTheDocument()
  })

  it('runs a multiple-choice activity end to end and shows why the answer is wrong', async () => {
    const api = fakeApi({
      user: ada,
      overrides: {
        'GET /api/activities/21': () => Response.json(choice),
        'POST /api/activities/21/attempts': () =>
          Response.json(
            attempt({
              activityId: 21,
              parts: [{ ref: 0, correct: false, message: 'A stack gives depth-first order.' }],
              feedback: 'A stack gives depth-first order.',
            }),
          ),
      },
    })
    const user = userEvent.setup()
    renderApp('/activities/21')

    await user.click(await screen.findByRole('radio', { name: 'A stack' }))
    await user.click(screen.getByRole('button', { name: 'Check answer' }))

    await waitFor(() => expect(api.callsTo('POST /api/activities/21/attempts')).toHaveLength(1))
    expect(api.callsTo('POST /api/activities/21/attempts')[0]?.body).toEqual({
      submitted: { selected: 'a' },
    })
    const results = await screen.findByRole('region', { name: 'Submission results' })
    expect(within(results).getByText('A stack gives depth-first order.')).toBeInTheDocument()
    expect(within(results).queryByRole('list')).not.toBeInTheDocument()
  })
})

describe('a select set back to its placeholder', () => {
  it('is left out of a matching answer, as a pair not made', async () => {
    const user = userEvent.setup()
    const onSubmit = vi
      .fn<(pairs: Record<string, string>) => Promise<void>>()
      .mockResolvedValue(undefined)
    render(
      <Matching activity={matching} result={undefined} submitting={false} onSubmit={onSubmit} />,
    )
    const roads = screen.getByRole('combobox', { name: 'Two-way roads between towns' })
    const follows = screen.getByRole('combobox', { name: 'Who follows whom online' })
    await user.selectOptions(roads, 'Undirected graph')
    await user.selectOptions(follows, 'Tree')
    await user.selectOptions(follows, 'Choose a match') // reset
    await user.click(screen.getByRole('button', { name: 'Check answer' }))
    expect(onSubmit).toHaveBeenCalledWith({ roads: 'undirected' })
  })
})
