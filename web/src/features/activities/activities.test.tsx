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
import { indentLabel, lineName } from './codeLines.ts'
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

  it('keeps the hints shown but offers no more once the answer is right', async () => {
    const loadHints = vi
      .fn<(activityId: number) => Promise<readonly Hint[]>>()
      .mockResolvedValue([
        { level: 1, body: 'First recorded hint.', hasMore: true, nextCountsAsSupport: false },
      ])
    const requestHint = vi.fn<(activityId: number) => Promise<Hint>>()

    render(<HintLadder activityId={7} solved loadHints={loadHints} requestHint={requestHint} />)

    expect(await screen.findByText('First recorded hint.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Show next hint' })).not.toBeInTheDocument()
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
    // A kind the API might add before its screen exists (KINDS_WITHOUT_STUDENT_UI).
    const unsupported = {
      id: 99,
      kind: 'label_vertices' as unknown as CodeActivity['kind'],
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
  const indentedFillIn = (
    <FillInCode
      activity={{
        ...fillIn,
        config: { ...fillIn.config, code: 'def bfs():\n    while q:\n        return __1__' },
      }}
      result={undefined}
      submitting={false}
      onSubmit={vi.fn<() => Promise<void>>()}
    />
  )

  it('keeps the leading spaces of each fill-in line, which renders white-space: pre', () => {
    render(indentedFillIn)
    const lines = [...document.querySelectorAll('section code')]
    expect(lines.map((code) => code.textContent?.match(/^ */)?.[0].length)).toEqual([0, 4, 8])
    for (const code of lines) expect(code).toHaveClass('whitespace-pre')
    // Code that fits is not a tab stop or a landmark (#142 review).
    expect(screen.queryByRole('region', { name: 'Python code with blanks' })).toBeNull()
    expect(document.querySelector('section')).not.toHaveAttribute('tabindex')
  })

  it('makes overflowing fill-in code a named region a keyboard user can scroll (WCAG 2.1.1)', () => {
    vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockReturnValue(900)
    vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(300)
    render(indentedFillIn)
    const region = screen.getByRole('region', { name: 'Python code with blanks' })
    expect(region).toHaveAttribute('tabindex', '0')
    // More code is off to the right, so the frame shows the scroll cue on that edge.
    expect(region.parentElement).toHaveAttribute('data-more-end')
    vi.restoreAllMocks()
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
    // The line's name gives its indentation in words, which a screen reader would otherwise skip.
    expect(indentOf('while queue:')).toMatchObject({ count: '0', css: '0' })
    expect(indentOf('v = queue.popleft() (indent level 1)')).toMatchObject({ count: '4', css: '4' })
    const deep = indentOf('if n not in visited: (indent level 2)')
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
    await user.click(
      screen.getByRole('button', { name: 'Remove “v = queue.popleft()” (indent level 1)' }),
    )
    const add = screen.getByRole('button', { name: 'Add: v = queue.popleft() (indent level 1)' })
    expect(add.querySelector('code')?.textContent).toBe('v = queue.popleft() (indent level 1)')
    expect(add.querySelector('code')?.dataset.indent).toBe('4')
  })
})

describe('CodeLine edge cases', () => {
  it.each([
    ['', '0', '', ''],
    ['      ', '6', 'indented 6 spaces', ''],
    ['x', '0', '', 'x'],
    ['  trailing  ', '2', 'indented 2 spaces', 'trailing  '],
    [' '.repeat(400) + 'deep()', '400', 'indent level 100', 'deep()'],
    ['a'.repeat(5000), '0', '', 'a'.repeat(5000)],
  ])('renders %j with indent %s', (text, indent, words, shown) => {
    const { container } = render(<CodeLine text={text} />)
    const code = container.querySelector('code')!
    expect(code.dataset.indent).toBe(indent)
    const hidden = code.querySelector('.visually-hidden')
    expect(hidden?.textContent ?? '').toBe(words ? `(${words})` : '')
    expect(code.textContent).toBe(shown + (words ? ` (${words})` : ''))
    expect(indentLabel(text)).toBe(words)
  })

  it('renders markup in a line as text, never as HTML', () => {
    const { container } = render(<CodeLine text={'    <img src=x onerror=alert(1)>'} />)
    expect(container.querySelector('img')).toBeNull()
    expect(container.textContent).toBe('<img src=x onerror=alert(1)> (indent level 1)')
  })

  it('names two lines that differ only by indentation differently', () => {
    expect(lineName('    queue.append(n)')).toBe('“queue.append(n)” (indent level 1)')
    expect(lineName('            queue.append(n)')).toBe('“queue.append(n)” (indent level 3)')
    expect(lineName('order = []')).toBe('“order = []”')
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
    await user.click(screen.getByRole('button', { name: 'Move “third()” up' })) // → 2nd
    await user.click(screen.getByRole('button', { name: 'Move “third()” up' })) // → 1st
    await user.click(screen.getByRole('button', { name: 'Move “first()” down' })) // → 3rd
    await user.click(screen.getByRole('button', { name: 'Check answer' }))
    expect(onSubmit).toHaveBeenCalledWith([3, 2, 1])
  })

  it('announces each move by the line’s code, not its internal id', async () => {
    const { user } = setup()
    await user.click(screen.getByRole('button', { name: 'Move “first()” down' }))
    expect(screen.getByText('Moved “first()” to position 2.')).toBeInTheDocument()
  })

  it('does nothing at the ends of the list, and keeps the end buttons focusable', async () => {
    const { user, onSubmit } = setup()
    const up = screen.getByRole('button', { name: 'Move “first()” up' })
    const down = screen.getByRole('button', { name: 'Move “third()” down' })
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
    await user.click(screen.getByRole('button', { name: 'Move “second()” up' }))
    // second() is now first, and its button still has focus, now at the top of the list.
    expect(screen.getByRole('button', { name: 'Move “second()” up' })).toHaveFocus()
    expect(screen.getByRole('button', { name: 'Move “second()” up' })).toHaveAttribute(
      'aria-disabled',
      'true',
    )
  })

  it('moves focus with a removed line to its Add button, and back again', async () => {
    const { user } = setup()
    await user.click(screen.getByRole('button', { name: 'Remove “first()”' }))
    expect(screen.getByRole('button', { name: /Add:\s*first\(\)/ })).toHaveFocus()
    await user.click(screen.getByRole('button', { name: 'Remove “second()”' }))
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
    for (const name of [/^Move “/, /^Remove “/]) {
      const buttons = screen.getAllByRole('button', { name })
      expect(buttons.length).toBeGreaterThan(2)
      for (const button of buttons) expect(button).toBeDisabled()
    }
  })
})

describe('focus after Check answer (WCAG 2.4.3, #142)', () => {
  // The fixture's feedback starts with the title, so the feedback alone names the group: the
  // title would otherwise be read twice ("Not quite" then "Not quite, 1 of 3 correct.").
  const result = () => screen.getByRole('group', { name: 'Not quite, 1 of 3 correct.' })

  it('moves focus to the result itself, named once, with no repeated title', () => {
    const { rerender } = render(<FeedbackPanel result={undefined} />)
    rerender(<FeedbackPanel result={wrong} />)
    expect(result()).toHaveFocus()
    expect(result()).not.toHaveAttribute('aria-describedby')
    expect(result()).toHaveAttribute('tabindex', '-1')
    // Still inside the "Submission results" region the page had before.
    expect(screen.getByRole('region', { name: 'Submission results' })).toContainElement(result())
  })

  it('names the result by its title and describes it by the feedback when they differ', () => {
    const { rerender } = render(<FeedbackPanel result={undefined} />)
    rerender(<FeedbackPanel result={{ ...wrong, feedback: 'Q must also list P.' }} />)
    const group = screen.getByRole('group', { name: 'Not quite' })
    expect(group).toHaveFocus()
    expect(group).toHaveAccessibleDescription('Q must also list P.')
  })

  it('announces a second result in the same place once: focused again, and not a live region', () => {
    const { rerender } = render(<FeedbackPanel result={undefined} />)
    rerender(<FeedbackPanel result={wrong} />)
    const first = result()
    const focusEvents = vi.fn<() => void>()
    first.addEventListener('focus', focusEvents)

    rerender(<FeedbackPanel result={{ ...wrong, id: 2, feedback: 'Still not quite.' }} />)
    const second = screen.getByRole('group', { name: 'Not quite' })
    expect(second).toBe(first) // the same node, updated in place
    expect(second).toHaveFocus()
    expect(focusEvents).toHaveBeenCalledTimes(1) // re-focused, so it is read again
    expect(second).toHaveAccessibleDescription('Still not quite.')
    expect(screen.queryByRole('status')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(document.querySelector('[aria-live]')).toBeNull()
  })

  it('names a correct result once ("Correct." under "Correct")', () => {
    const { rerender } = render(<FeedbackPanel result={undefined} />)
    rerender(<FeedbackPanel result={{ ...wrong, correct: true, feedback: 'Correct.' }} />)
    expect(screen.getByRole('group', { name: 'Correct.' })).toHaveFocus()
  })

  it('does not take focus for a result already there when it first renders', () => {
    render(<FeedbackPanel result={wrong} />)
    expect(result()).not.toHaveFocus()
  })

  /** The activity page with a controllable attempts endpoint. */
  function activityPage(attempt: () => Response | Promise<Response>) {
    const api = fakeApi({
      user: ada,
      overrides: {
        'GET /api/activities/7': () => Response.json(parsons),
        'GET /api/activities/7/hints': () => Response.json([]),
        'POST /api/activities/7/attempts': attempt,
      },
    })
    renderApp('/activities/7')
    return api
  }

  it('lands on the feedback after a keyboard user checks an answer on the activity page', async () => {
    activityPage(() => Response.json({ ...wrong, activityId: 7 }))
    const user = userEvent.setup()
    ;(await screen.findByRole('button', { name: 'Check answer' })).focus()
    await user.keyboard('{Enter}')

    const panel = await screen.findByRole('group', { name: 'Not quite, 1 of 3 correct.' })
    await waitFor(() => expect(panel).toHaveFocus())
  })

  it('keeps focus on a busy Check answer while a slow check runs, and ignores more presses', async () => {
    let release: (response: Response) => void = () => {}
    const api = activityPage(() => new Promise<Response>((resolve) => (release = resolve)))
    const user = userEvent.setup()
    const button = await screen.findByRole('button', { name: 'Check answer' })
    button.focus()
    await user.keyboard('{Enter}')

    await waitFor(() => expect(button).toHaveAttribute('aria-busy', 'true'))
    expect(button).toHaveAttribute('aria-disabled', 'true')
    expect(button).toBeEnabled()
    expect(button).toHaveFocus() // not <body>
    await user.keyboard('{Enter}')
    await user.click(button)
    expect(api.callsTo('POST /api/activities/7/attempts')).toHaveLength(1)

    release(Response.json({ ...wrong, activityId: 7 }))
    const panel = await screen.findByRole('group', { name: 'Not quite, 1 of 3 correct.' })
    await waitFor(() => expect(panel).toHaveFocus())
  })

  it('sends one attempt for two submits in the same moment (a fast double Enter)', async () => {
    const api = activityPage(() => Response.json({ ...wrong, activityId: 7 }))
    const button = await screen.findByRole('button', { name: 'Check answer' })
    const form = button.closest('form')!
    fireEvent.submit(form)
    fireEvent.submit(form) // before React has re-rendered the busy button
    await screen.findByRole('group', { name: 'Not quite, 1 of 3 correct.' })
    expect(api.callsTo('POST /api/activities/7/attempts')).toHaveLength(1)
  })

  it.each([500, 422])(
    'keeps focus on Check answer when the check fails (%i), with the error announced',
    async (status) => {
      activityPage(() => Response.json({ detail: 'Internal Server Error' }, { status }))
      const user = userEvent.setup()
      const button = await screen.findByRole('button', { name: 'Check answer' })
      button.focus()
      await user.keyboard('{Enter}')

      const alert = await screen.findByRole('alert')
      expect(alert).toHaveTextContent('Try again')
      expect(button).toHaveFocus()
      expect(button).not.toHaveAttribute('aria-busy')
      expect(document.activeElement).not.toBe(document.body)
    },
  )
})

describe('focus in the hint ladder (WCAG 2.4.3, #142 review)', () => {
  const hint = (level: number, hasMore: boolean): Hint => ({
    level,
    body: `Hint body ${level}.`,
    hasMore,
    nextCountsAsSupport: false,
  })

  it('keeps focus on a busy "Show next hint", then moves it to the new hint', async () => {
    const user = userEvent.setup()
    let release: (value: Hint) => void = () => {}
    const requestHint = vi
      .fn<(activityId: number) => Promise<Hint>>()
      .mockImplementation(() => new Promise<Hint>((resolve) => (release = resolve)))
    render(
      <HintLadder
        activityId={7}
        loadHints={vi.fn<(id: number) => Promise<readonly Hint[]>>().mockResolvedValue([])}
        requestHint={requestHint}
      />,
    )
    const button = await screen.findByRole('button', { name: 'Show next hint' })
    button.focus()
    await user.keyboard('{Enter}')

    // Loading: still focused and enabled to the browser, but marked busy and ignored.
    expect(button).toHaveFocus()
    expect(button).toBeEnabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
    expect(button).toHaveAttribute('aria-disabled', 'true')
    await user.keyboard('{Enter}')
    expect(requestHint).toHaveBeenCalledTimes(1)

    release(hint(1, true))
    const shown = await screen.findByRole('group', { name: 'Hint 1' })
    await waitFor(() => expect(shown).toHaveFocus())
    expect(shown).toHaveAccessibleDescription('Hint body 1.')
    expect(screen.getByRole('button', { name: 'Show next hint' })).not.toHaveAttribute('aria-busy')
  })

  it('leaves focus on the last hint when the ladder ends and the button goes', async () => {
    const user = userEvent.setup()
    render(
      <HintLadder
        activityId={7}
        loadHints={vi
          .fn<(id: number) => Promise<readonly Hint[]>>()
          .mockResolvedValue([hint(1, true), hint(2, true), hint(3, true)])}
        requestHint={vi.fn<(id: number) => Promise<Hint>>().mockResolvedValue(hint(4, false))}
      />,
    )
    // Hints already recorded don't take focus when the page opens.
    expect(await screen.findByRole('group', { name: 'Hint 3' })).not.toHaveFocus()
    await user.click(screen.getByRole('button', { name: 'Show next hint' }))

    const last = await screen.findByRole('group', { name: 'Hint 4' })
    await waitFor(() => expect(last).toHaveFocus())
    expect(screen.queryByRole('button', { name: 'Show next hint' })).toBeNull()
    expect(document.activeElement).not.toBe(document.body)
  })

  it('stays in the tab order while an answer is checked, but ignores presses', async () => {
    const user = userEvent.setup()
    const requestHint = vi.fn<(id: number) => Promise<Hint>>()
    render(
      <HintLadder
        activityId={7}
        disabled
        loadHints={vi.fn<(id: number) => Promise<readonly Hint[]>>().mockResolvedValue([])}
        requestHint={requestHint}
      />,
    )
    const button = await screen.findByRole('button', { name: 'Show next hint' })
    expect(button).toBeEnabled()
    expect(button).toHaveAttribute('aria-disabled', 'true')
    await user.click(button)
    expect(requestHint).not.toHaveBeenCalled()
  })

  it('keeps focus on the button when a hint can’t be loaded', async () => {
    const user = userEvent.setup()
    render(
      <HintLadder
        activityId={7}
        loadHints={vi.fn<(id: number) => Promise<readonly Hint[]>>().mockResolvedValue([])}
        requestHint={vi.fn<(id: number) => Promise<Hint>>().mockRejectedValue(new Error('down'))}
      />,
    )
    const button = await screen.findByRole('button', { name: 'Show next hint' })
    await user.click(button)
    expect(
      await screen.findByText('We could not load a hint. Please try again.'),
    ).toBeInTheDocument()
    expect(button).toHaveFocus()
  })
})

describe('hints once an activity is solved (#158)', () => {
  const solved = {
    id: 31,
    kind: 'multiple_choice',
    title: 'Already answered',
    visible: true,
    solved: true,
    config: {
      prompt: 'Which leaves the queue first?',
      options: [
        { id: 'a', label: 'The first to join' },
        { id: 'b', label: 'The last to join' },
      ],
    },
  }

  it('offers no hints for an activity the student already answered correctly, after a refresh too', async () => {
    fakeApi({
      user: ada,
      overrides: {
        'GET /api/activities/31': () => Response.json(solved),
        'GET /api/activities/31/hints': () =>
          Response.json([
            { level: 1, body: 'First recorded hint.', hasMore: true, nextCountsAsSupport: false },
          ]),
      },
    })
    renderApp('/activities/31')

    expect(await screen.findByText('First recorded hint.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Show next hint' })).not.toBeInTheDocument()
  })

  it('takes the support warning away once the answer is right', async () => {
    const user = userEvent.setup()
    const loadHints = vi
      .fn<(activityId: number) => Promise<readonly Hint[]>>()
      .mockResolvedValue([
        { level: 2, body: 'Second recorded hint.', hasMore: true, nextCountsAsSupport: true },
      ])
    const requestHint = vi.fn<(activityId: number) => Promise<Hint>>()
    const { rerender } = render(
      <HintLadder activityId={7} loadHints={loadHints} requestHint={requestHint} />,
    )
    await user.click(await screen.findByRole('button', { name: 'Show next hint' }))
    expect(screen.getByText(/The next hint gives a lot away/)).toBeInTheDocument()

    rerender(<HintLadder activityId={7} solved loadHints={loadHints} requestHint={requestHint} />)
    expect(screen.queryByText(/The next hint gives a lot away/)).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Show next hint' })).not.toBeInTheDocument()
  })
})
