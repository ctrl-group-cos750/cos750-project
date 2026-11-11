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
import { CodeLine, ParsonsProblem } from './ParsonsProblem.tsx'
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

// ---------------------------------------------------------------------------
// #140 code indentation, #142 accessibility
// ---------------------------------------------------------------------------

const indented: ParsonsActivity = {
  id: 9,
  kind: 'parsons',
  title: 'Order the loop',
  visible: true,
  config: {
    lines: [
      { id: 1, text: 'while queue:' },
      { id: 2, text: '    v = queue.popleft()' },
      { id: 3, text: '        if n not in visited:' },
    ],
  },
}

const wrong = {
  id: 1,
  activityId: 7,
  correct: false,
  score: 0,
  parts: [],
  feedback: 'Not quite, 1 of 3 correct.',
  hintLevel: 0,
}

describe('code keeps its indentation (#140)', () => {
  it('keeps the leading spaces of each fill-in line, which renders white-space: pre', () => {
    render(
      <FillInCode
        activity={{
          ...fillIn,
          config: { ...fillIn.config, code: 'def bfs():\n    while q:\n        return __1__' },
        }}
        result={undefined}
        submitting={false}
        onSubmit={vi.fn<() => Promise<void>>()}
      />,
    )
    const region = screen.getByRole('region', { name: 'Python code with blanks' })
    const lines = [...region.querySelectorAll('code')]
    expect(lines.map((code) => code.textContent?.match(/^ */)?.[0].length)).toEqual([0, 4, 8])
    for (const code of lines) expect(code).toHaveClass('whitespace-pre')
    // A long line scrolls inside the region, which a keyboard user can reach (WCAG 2.1.1).
    expect(region).toHaveAttribute('tabindex', '0')
    expect(region).toHaveClass('overflow-x-auto')
  })

  it('keeps a Parsons line’s indentation, as a hanging indent of its own width', () => {
    render(
      <ParsonsProblem
        activity={indented}
        result={undefined}
        submitting={false}
        onSubmit={vi.fn<() => Promise<void>>()}
      />,
    )
    const indentOf = (name: string) => {
      const code = screen.getByRole('button', { name }).querySelector('code')!
      return { count: code.dataset.indent, css: code.style.getPropertyValue('--indent'), code }
    }
    expect(indentOf('while queue:')).toMatchObject({ count: '0', css: '0' })
    expect(indentOf('v = queue.popleft()')).toMatchObject({ count: '4', css: '4' })
    const deep = indentOf('if n not in visited:')
    expect(deep).toMatchObject({ count: '8', css: '8' })
    // Padding (not leading spaces) draws it, so a wrapped line stays at its level.
    expect(deep.code.className).toContain('[padding-inline-start:calc(var(--indent)*1ch)]')
    expect(deep.code).toHaveClass('whitespace-pre-wrap')
  })

  it('keeps the indentation of a line in the available lines too', async () => {
    const user = userEvent.setup()
    render(
      <ParsonsProblem
        activity={indented}
        result={undefined}
        submitting={false}
        onSubmit={vi.fn<() => Promise<void>>()}
      />,
    )
    await user.click(screen.getAllByRole('button', { name: 'Remove' })[1])
    const add = screen.getByRole('button', { name: /Add:/ })
    expect(add.querySelector('code')?.textContent).toBe('v = queue.popleft()')
    expect(add.querySelector('code')?.dataset.indent).toBe('4')
  })
})

describe('CodeLine edge cases', () => {
  it.each([
    ['', '0', ''],
    ['      ', '6', ''],
    ['x', '0', 'x'],
    ['  trailing  ', '2', 'trailing  '],
    [' '.repeat(400) + 'deep()', '400', 'deep()'],
    ['a'.repeat(5000), '0', 'a'.repeat(5000)],
  ])('renders %j with indent %s', (text, indent, shown) => {
    const { container } = render(<CodeLine text={text} />)
    const code = container.querySelector('code')!
    expect(code.dataset.indent).toBe(indent)
    expect(code.textContent).toBe(shown)
  })

  it('renders markup in a line as text, never as HTML', () => {
    const { container } = render(<CodeLine text={'    <img src=x onerror=alert(1)>'} />)
    expect(container.querySelector('img')).toBeNull()
    expect(container.textContent).toBe('<img src=x onerror=alert(1)>')
  })
})

describe('Parsons without dragging (WCAG 2.2 SC 2.5.7, #142)', () => {
  function setup() {
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
    return { user, onSubmit }
  }

  it('reorders with the move buttons alone, by pointer, and submits that order', async () => {
    const { user, onSubmit } = setup()
    await user.click(screen.getByRole('button', { name: 'Move line 3 up' })) // third() → 2
    await user.click(screen.getByRole('button', { name: 'Move line 2 up' })) // third() → 1
    await user.click(screen.getByRole('button', { name: 'Move line 2 down' })) // first() → 3
    await user.click(screen.getByRole('button', { name: 'Check answer' }))
    expect(onSubmit).toHaveBeenCalledWith([3, 2, 1])
  })

  it('announces each move by the line’s code, not its internal id', async () => {
    const { user } = setup()
    await user.click(screen.getByRole('button', { name: 'Move line 1 down' }))
    expect(screen.getByText('Moved “first()” to position 2.')).toBeInTheDocument()
  })

  it('does nothing at the ends of the list, and keeps the end buttons focusable', async () => {
    const { user, onSubmit } = setup()
    const up = screen.getByRole('button', { name: 'Move line 1 up' })
    const down = screen.getByRole('button', { name: 'Move line 3 down' })
    expect(up).toHaveAttribute('aria-disabled', 'true')
    expect(down).toHaveAttribute('aria-disabled', 'true')
    expect(up).toBeEnabled()
    await user.click(up)
    await user.click(down)
    await user.click(screen.getByRole('button', { name: 'Check answer' }))
    expect(onSubmit).toHaveBeenCalledWith([1, 2, 3])
  })

  it('keeps focus on the move button as the line moves (the button moves with its line)', async () => {
    const { user } = setup()
    await user.click(screen.getByRole('button', { name: 'Move line 2 up' }))
    // second() is now line 1, and its button is the one with focus, now named for line 1.
    expect(screen.getByRole('button', { name: 'Move line 1 up' })).toHaveFocus()
    expect(screen.getByRole('button', { name: 'Move line 1 up' })).toHaveAttribute(
      'aria-disabled',
      'true',
    )
  })

  it('moves focus with a removed line to its Add button, and back again', async () => {
    const { user } = setup()
    await user.click(screen.getAllByRole('button', { name: 'Remove' })[0])
    expect(screen.getByRole('button', { name: /Add:\s*first\(\)/ })).toHaveFocus()
    await user.click(screen.getAllByRole('button', { name: 'Remove' })[0]) // second()
    expect(screen.getByRole('button', { name: /Add:\s*second\(\)/ })).toHaveFocus()

    // Adding goes on to the next line still to add, then to the last line added.
    await user.click(screen.getByRole('button', { name: /Add:\s*first\(\)/ }))
    expect(screen.getByRole('button', { name: /Add:\s*second\(\)/ })).toHaveFocus()
    await user.click(screen.getByRole('button', { name: /Add:\s*second\(\)/ }))
    expect(screen.getByRole('button', { name: 'second()' })).toHaveFocus()
  })

  it('locks every control once the answer is correct', () => {
    render(
      <ParsonsProblem
        activity={parsons}
        result={{ ...wrong, correct: true, score: 1, feedback: 'All correct.' }}
        submitting={false}
        onSubmit={vi.fn<() => Promise<void>>()}
      />,
    )
    for (const name of ['Move line 1 down', 'Move line 2 up', 'Remove']) {
      for (const button of screen.getAllByRole('button', { name })) expect(button).toBeDisabled()
    }
  })
})

describe('focus after Check answer (WCAG 2.4.3, #142)', () => {
  it('moves focus to the feedback when a result arrives, and again for the next one', () => {
    const { rerender } = render(<FeedbackPanel result={undefined} />)
    rerender(<FeedbackPanel result={wrong} />)
    const panel = screen.getByRole('region', { name: 'Submission results' })
    expect(panel).toHaveFocus()
    expect(panel).toHaveAttribute('tabindex', '-1')

    panel.blur()
    rerender(<FeedbackPanel result={{ ...wrong, id: 2, feedback: 'Still not quite.' }} />)
    expect(screen.getByRole('region', { name: 'Submission results' })).toHaveFocus()
  })

  it('does not take focus for a result already there when it first renders', () => {
    render(<FeedbackPanel result={wrong} />)
    expect(screen.getByRole('region', { name: 'Submission results' })).not.toHaveFocus()
  })

  it('lands on the feedback after a keyboard user checks an answer on the activity page', async () => {
    fakeApi({
      user: ada,
      overrides: {
        'GET /api/activities/7': () => Response.json(parsons),
        'GET /api/activities/7/hints': () => Response.json([]),
        'POST /api/activities/7/attempts': () => Response.json({ ...wrong, activityId: 7 }),
      },
    })
    const user = userEvent.setup()
    renderApp('/activities/7')

    ;(await screen.findByRole('button', { name: 'Check answer' })).focus()
    await user.keyboard('{Enter}')

    const panel = await screen.findByRole('region', { name: 'Submission results' })
    await waitFor(() => expect(panel).toHaveFocus())
    expect(panel).toHaveTextContent('Not quite, 1 of 3 correct.')
  })
})
