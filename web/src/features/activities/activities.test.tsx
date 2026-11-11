import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Link, MemoryRouter, Route, Routes } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { ada, fakeApi, renderApp } from '../../test/app.tsx'
import { ActivityPage } from './ActivityPage.tsx'
import { ActivityRenderer } from './ActivityRenderer.tsx'
import { FeedbackPanel } from './FeedbackPanel.tsx'
import { FillInCode } from './FillInCode.tsx'
import { HintLadder } from './HintLadder.tsx'
import { ParsonsProblem } from './ParsonsProblem.tsx'
import type { CodeActivity, FillInActivity, Hint, ParsonsActivity } from './activities.types.ts'

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

  it('leaves a blank set back to its placeholder out of the answer', async () => {
    const user = userEvent.setup()
    const onSubmit = vi
      .fn<(answers: Record<number, string>) => Promise<void>>()
      .mockResolvedValue(undefined)
    const twoBlanks: FillInActivity = {
      ...fillIn,
      config: { ...fillIn.config, code: 'a = __1__\nb = __2__', blanks: [1, 2] },
    }
    render(
      <FillInCode activity={twoBlanks} result={undefined} submitting={false} onSubmit={onSubmit} />,
    )
    await user.selectOptions(screen.getByRole('combobox', { name: 'Blank 1' }), 'queue')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Blank 2' }), 'visited')
    await user.selectOptions(screen.getByRole('combobox', { name: 'Blank 2' }), 'blank 2') // reset
    await user.click(screen.getByRole('button', { name: 'Check answer' }))
    expect(onSubmit).toHaveBeenCalledWith({ 1: 'queue' })
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
        'GET /api/activities/7/hints': () => Response.json([]),
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

  it('resets attempt result and unlocks when navigating to a new activity', async () => {
    fakeApi({
      user: ada,
      overrides: {
        'GET /api/activities/7': () => Response.json(parsons),
        'GET /api/activities/7/hints': () => Response.json([]),
        'POST /api/activities/7/attempts': () =>
          Response.json({
            id: 11,
            activityId: 7,
            correct: true,
            score: 1,
            parts: [{ ref: 0, correct: true, message: null }],
            feedback: 'All correct!',
            hintLevel: 0,
          }),
        'GET /api/activities/8': () => Response.json(fillIn),
        'GET /api/activities/8/hints': () => Response.json([]),
      },
    })
    const user = userEvent.setup()
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    })

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={['/activities/7']}>
          <Link to="/activities/8">Go to next</Link>
          <Routes>
            <Route path="/activities/:activityId" element={<ActivityPage />} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    )

    // Submit correct answer on activity 7
    await user.click(await screen.findByRole('button', { name: 'Check answer' }))
    await screen.findByText('All correct!')
    expect(screen.getByRole('button', { name: 'Check answer' })).toBeDisabled()

    // Navigate to activity 8
    await user.click(screen.getByRole('link', { name: 'Go to next' }))

    // Activity 8 is unlocked and does not show the previous "All correct!" feedback
    expect(await screen.findByRole('combobox', { name: 'Blank 1' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Check answer' })).toBeEnabled()
    expect(screen.queryByText('All correct!')).not.toBeInTheDocument()
  })

  it('loads recorded hints on mount and warns before support level hint', async () => {
    const user = userEvent.setup()
    const loadHints = vi.fn<(activityId: number) => Promise<readonly Hint[]>>().mockResolvedValue([
      {
        level: 1,
        body: 'First recorded hint.',
        hasMore: true,
        nextCountsAsSupport: false,
      },
      {
        level: 2,
        body: 'Second recorded hint.',
        hasMore: true,
        nextCountsAsSupport: true,
      },
    ])
    const requestHint = vi.fn<(activityId: number) => Promise<Hint>>().mockResolvedValue({
      level: 3,
      body: 'Third hint.',
      hasMore: true,
      nextCountsAsSupport: true,
    })

    render(<HintLadder activityId={7} loadHints={loadHints} requestHint={requestHint} />)

    // Recorded hints appear on mount
    expect(await screen.findByText('First recorded hint.')).toBeInTheDocument()
    expect(screen.getByText('Second recorded hint.')).toBeInTheDocument()

    // Requesting next hint when nextCountsAsSupport warns before calling requestHint
    await user.click(screen.getByRole('button', { name: 'Show next hint' }))
    expect(requestHint).not.toHaveBeenCalled()
    expect(screen.getByText(/The next hint gives a lot away/)).toBeInTheDocument()

    // Clicking again confirms and requests the hint
    await user.click(screen.getByRole('button', { name: 'Show next hint' }))
    expect(requestHint).toHaveBeenCalledWith(7)
    expect(await screen.findByText('Third hint.')).toBeInTheDocument()
  })

  it('does not offer hints when recorded hints cannot be loaded', async () => {
    const loadHints = vi
      .fn<(activityId: number) => Promise<readonly Hint[]>>()
      .mockRejectedValue(new Error('network error'))
    const requestHint = vi.fn<(activityId: number) => Promise<Hint>>()

    render(<HintLadder activityId={7} loadHints={loadHints} requestHint={requestHint} />)

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Show next hint' })).not.toBeInTheDocument()
    })
    expect(requestHint).not.toHaveBeenCalled()
  })

  it('clears Parsons per-line highlights as soon as the answer is changed', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn<(order: number[]) => Promise<void>>().mockResolvedValue(undefined)
    render(
      <ParsonsProblem
        activity={parsons}
        result={{
          id: 1,
          activityId: 7,
          correct: false,
          score: 0,
          parts: [{ ref: 0, correct: false, message: 'Wrong place' }],
          feedback: '0 of 1 correct.',
          hintLevel: 0,
        }}
        submitting={false}
        onSubmit={onSubmit}
      />,
    )

    expect(screen.getByText('Wrong place')).toBeInTheDocument()

    // Moving a line clears the per-line highlight
    await user.click(screen.getByRole('button', { name: 'third()' }))
    await user.keyboard('{ArrowUp}')

    expect(screen.queryByText('Wrong place')).not.toBeInTheDocument()
  })

  it('FeedbackPanel shows only the summary and no duplicate list', () => {
    render(
      <FeedbackPanel
        result={{
          id: 1,
          activityId: 7,
          correct: false,
          score: 0,
          parts: [{ ref: 0, correct: false, message: 'Wrong place' }],
          feedback: 'Not quite, 0 of 1 correct.',
          hintLevel: 0,
        }}
      />,
    )

    expect(screen.getByText('Not quite, 0 of 1 correct.')).toBeInTheDocument()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it('hides the hint ladder and feedback panel when activity kind is not supported', () => {
    const unsupported = {
      id: 99,
      kind: 'trace' as unknown as CodeActivity['kind'],
      title: 'Unsupported kind',
      visible: true,
      config: {} as unknown as CodeActivity['config'],
    } as CodeActivity

    render(
      <ActivityRenderer
        activity={unsupported}
        result={undefined}
        submitting={false}
        onSubmit={vi.fn<(submitted: unknown) => Promise<void>>().mockResolvedValue(undefined)}
        requestHint={vi.fn<(activityId: number) => Promise<Hint>>()}
        loadHints={vi.fn<(activityId: number) => Promise<readonly Hint[]>>().mockResolvedValue([])}
      />,
    )

    expect(screen.getByText('This activity kind is not available yet.')).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Hints' })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Submission results' })).not.toBeInTheDocument()
  })
})
