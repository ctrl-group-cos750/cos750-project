import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ada, fakeApi, renderApp } from '../../test/app.tsx'
import { FillInCode } from './FillInCode.tsx'
import { HintLadder } from './HintLadder.tsx'
import { ParsonsProblem } from './ParsonsProblem.tsx'
import type { FillInActivity, Hint, ParsonsActivity } from './activities.types.ts'

const parsons: ParsonsActivity = {
  id: 7,
  kind: 'parsons',
  title: 'Order BFS',
  visible: true,
  config: {
    lines: [
      { id: 1, text: 'first()' },
      { id: 2, text: 'second()' },
      { id: 3, text: 'third()' },
    ],
  },
}

const fillIn: FillInActivity = {
  id: 8,
  kind: 'fill_in',
  title: 'Complete BFS',
  visible: true,
  config: { code: 'def bfs():\n    return __1__', blanks: [1], options: ['queue', 'visited'] },
}

describe('code activities', () => {
  it('reorders Parsons lines with both arrows and drag/drop, then submits the chosen order', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn<(order: number[]) => Promise<void>>().mockResolvedValue(undefined)
    render(
      <ParsonsProblem
        activity={parsons}
        result={undefined}
        submitting={false}
        onSubmit={onSubmit}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'third()' }))
    await user.keyboard('{ArrowUp}')
    fireEvent.dragStart(screen.getByRole('button', { name: 'first()' }))
    fireEvent.drop(screen.getByRole('button', { name: 'third()' }))
    await user.click(screen.getByRole('button', { name: 'Check answer' }))

    expect(onSubmit).toHaveBeenCalledWith([3, 1, 2])
  })

  it('submits token selections rather than editable code', async () => {
    const user = userEvent.setup()
    const onSubmit = vi
      .fn<(answers: Record<number, string>) => Promise<void>>()
      .mockResolvedValue(undefined)
    render(
      <FillInCode activity={fillIn} result={undefined} submitting={false} onSubmit={onSubmit} />,
    )

    await user.selectOptions(screen.getByRole('combobox', { name: 'Blank 1' }), 'queue')
    await user.click(screen.getByRole('button', { name: 'Check answer' }))

    expect(onSubmit).toHaveBeenCalledWith({ 1: 'queue' })
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  })

  it('uses the GET and POST activity endpoints from the standalone activity route', async () => {
    const api = fakeApi({
      user: ada,
      overrides: {
        'GET /api/activities/7': () => Response.json(parsons),
        'POST /api/activities/7/attempts': () =>
          Response.json({
            id: 11,
            activityId: 7,
            correct: false,
            score: 0,
            parts: [{ ref: 0, correct: false, message: 'Wrong place.' }],
            feedback: '0 of 1 correct.',
            hintLevel: 0,
          }),
      },
    })
    const user = userEvent.setup()
    renderApp('/activities/7')

    await user.click(await screen.findByRole('button', { name: 'Check answer' }))
    await waitFor(() => expect(api.callsTo('POST /api/activities/7/attempts')).toHaveLength(1))
    expect(api.callsTo('POST /api/activities/7/attempts')[0]?.body).toEqual({
      submitted: { order: [1, 2, 3] },
    })
  })

  it('warns before requesting a support-level hint', async () => {
    const user = userEvent.setup()
    const requestHint = vi
      .fn<(activityId: number) => Promise<Hint>>()
      .mockResolvedValueOnce({
        level: 2,
        body: 'Look at the queue.',
        hasMore: true,
        nextCountsAsSupport: true,
      })
      .mockResolvedValueOnce({
        level: 3,
        body: 'Try this order.',
        hasMore: true,
        nextCountsAsSupport: true,
      })
    render(<HintLadder activityId={7} requestHint={requestHint} />)

    await user.click(screen.getByRole('button', { name: 'Show next hint' }))
    await screen.findByText('Look at the queue.')
    await user.click(screen.getByRole('button', { name: 'Show next hint' }))
    expect(requestHint).toHaveBeenCalledTimes(1)
    expect(screen.getByText(/The next hint gives a lot away/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Show next hint' }))
    await screen.findByText('Try this order.')
    expect(requestHint).toHaveBeenCalledTimes(2)
  })
})
