import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ada, fakeApi, renderApp } from '../../test/app.tsx'
import { ActivityRenderer } from './ActivityRenderer.tsx'
import { ChooseTests } from './ChooseTests.tsx'
import { FixTheBug } from './FixTheBug.tsx'
import { TraceTable } from './TraceTable.tsx'
import { parseVertexList } from './traceInput.ts'
import type {
  Activity,
  AttemptResult,
  ChooseTestsActivity,
  FixTheBugActivity,
  Hint,
  TraceActivity,
  TraceRow,
} from './activities.types.ts'

// Module 3's practice graph (item 315): undirected, from B. BFS visits B, A, D, C, E.
const trace: TraceActivity = {
  id: 315,
  kind: 'trace',
  title: 'Trace BFS from B',
  visible: true,
  config: {
    directed: false,
    vertices: ['A', 'B', 'C', 'D', 'E'],
    edges: [
      { source: 'A', target: 'B' },
      { source: 'A', target: 'C' },
      { source: 'B', target: 'D' },
      { source: 'C', target: 'D' },
      { source: 'C', target: 'E' },
    ],
    start_vertex: 'B',
  },
}

const fix: FixTheBugActivity = {
  id: 622,
  kind: 'fix_the_bug',
  title: 'Fix the faulty BFS',
  visible: true,
  config: {
    prompt: 'This BFS gives the wrong order. Replace the faulty line with a correction.',
    lines: [
      { id: 1, text: 'def bfs(graph, start):' },
      { id: 2, text: '    queue = deque([start])' },
      { id: 3, text: '    while queue:' },
      { id: 4, text: '        v = queue.pop()' },
      { id: 5, text: '    return order' },
    ],
    corrections: [
      { id: 20, text: '        v = queue.popleft()' },
      { id: 21, text: '        v = queue[0]' },
    ],
  },
}

const choose: ChooseTestsActivity = {
  id: 623,
  kind: 'choose_tests',
  title: 'Choose the tests that catch the bug',
  visible: true,
  config: {
    prompt: 'Choose every test case this BFS fails.',
    code: 'def bfs(graph, start):\n    visited = set()\n        # deeper',
    tests: [
      {
        id: 'cycle',
        directed: false,
        vertices: ['A', 'B', 'C'],
        edges: [
          { source: 'A', target: 'B' },
          { source: 'B', target: 'C' },
          { source: 'C', target: 'A' },
        ],
        start_vertex: 'A',
        expected: ['A', 'B', 'C'],
      },
      { id: 'one-vertex', vertices: ['A'], start_vertex: 'A', expected: ['A'] },
      {
        id: 'one-way',
        directed: true,
        vertices: ['A', 'B'],
        edges: [{ source: 'B', target: 'A' }],
        start_vertex: 'A',
        expected: ['A'],
      },
    ],
  },
}

function attempt(overrides: Partial<AttemptResult>): AttemptResult {
  return {
    id: 1,
    activityId: 1,
    correct: false,
    score: 0,
    parts: [],
    feedback: '',
    hintLevel: 0,
    ...overrides,
  }
}

const noHints = {
  requestHint: vi.fn<(activityId: number) => Promise<Hint>>(),
  loadHints: vi.fn<(activityId: number) => Promise<readonly Hint[]>>().mockResolvedValue([]),
}

describe('parseVertexList', () => {
  const vertices = ['A', 'B', 'C', 'Main Gate']

  it.each([
    ['A, C', ['A', 'C']],
    ['a, c', ['A', 'C']],
    ['A C', ['A', 'C']],
    ['[A, C]', ['A', 'C']],
    ["('A', 'C')", ['A', 'C']],
    ['  A ,, C , ', ['A', 'C']],
    ['Main Gate, A', ['Main Gate', 'A']],
    ['', []],
    ['empty', []],
    ['–', []],
  ])('reads %j as %j', (text, values) => {
    expect(parseVertexList(text, vertices)).toEqual({ values, unknown: [] })
  })

  it('names what is not a vertex instead of dropping it', () => {
    expect(parseVertexList('A, Z, B C D', vertices)).toEqual({
      values: ['A'],
      unknown: ['Z', 'B C D'],
    })
  })

  it('keeps a repeated vertex, so the server can mark it wrong', () => {
    expect(parseVertexList('A, A', vertices).values).toEqual(['A', 'A'])
  })

  it('does not guess between two labels that differ only by case', () => {
    expect(parseVertexList('x', ['X', 'x']).values).toEqual(['x'])
    expect(parseVertexList('X', ['X', 'x']).values).toEqual(['X'])
    expect(parseVertexList('X', ['x', 'x2']).values).toEqual(['x'])
  })

  it('treats "empty" as a label when the graph has a vertex called that', () => {
    expect(parseVertexList('empty', ['empty', 'A']).values).toEqual(['empty'])
  })

  it('survives hostile input without throwing', () => {
    const huge = 'A,'.repeat(5_000)
    expect(parseVertexList(huge, vertices).values).toHaveLength(5_000)
    expect(parseVertexList('<script>alert(1)</script>', vertices).unknown).toHaveLength(1)
  })
})

describe('trace table', () => {
  async function fillRow(
    user: ReturnType<typeof userEvent.setup>,
    step: number,
    row: { current: string; queue: string; visited: string; order: string },
  ) {
    await user.selectOptions(
      screen.getByRole('combobox', { name: `Step ${step}, current vertex` }),
      row.current,
    )
    for (const [name, value] of [
      ['queue after the step', row.queue],
      ['visited (has left the queue)', row.visited],
      ['order so far', row.order],
    ]) {
      const input = screen.getByRole('textbox', { name: `Step ${step}, ${name}` })
      // Typing is sequential, like a student's.
      // oxlint-disable-next-line no-await-in-loop
      await user.clear(input)
      // oxlint-disable-next-line no-await-in-loop
      if (value) await user.type(input, value)
    }
  }

  it('shows the graph, its edges and the start row, as in module 3', () => {
    render(
      <TraceTable
        activity={trace}
        result={undefined}
        submitting={false}
        onSubmit={vi.fn<(value: unknown) => Promise<void>>()}
      />,
    )
    expect(screen.getByRole('img', { name: /Graph to trace from B/ })).toBeInTheDocument()
    expect(screen.getByText('A–B, A–C, B–D, C–D, C–E')).toBeInTheDocument()
    const table = screen.getByRole('table', { name: 'Your trace table, from B' })
    expect(
      within(table)
        .getAllByRole('columnheader')
        .map((th) => th.textContent),
    ).toEqual([
      'Step',
      'Current vertex',
      'Queue after the step',
      'Visited (has left the queue)',
      'Order so far',
    ])
    // The "…" on the graph is explained in words.
    expect(screen.getByText(/At the start only B is in the queue/)).toHaveTextContent('“…” marks')
    // Found and visited are two states, named as the code names them (review 13 Nov, High 3).
    expect(screen.getByText(/The found vertices are the visited ones/)).toHaveTextContent(
      'found set',
    )
    expect(within(table).getByRole('rowheader', { name: 'start' })).toBeInTheDocument()
    // One empty step to start with: the number of rows gives nothing away.
    expect(screen.getAllByRole('combobox')).toHaveLength(1)
  })

  it("doesn't let a phone keyboard change what is typed: capitals, no autocorrect", () => {
    render(
      <TraceTable
        activity={trace}
        result={undefined}
        submitting={false}
        onSubmit={vi.fn<(value: unknown) => Promise<void>>()}
      />,
    )
    for (const input of screen.getAllByRole('textbox')) {
      expect(input).toHaveAttribute('autocapitalize', 'characters')
      expect(input).toHaveAttribute('autocorrect', 'off')
      expect(input).toHaveAttribute('spellcheck', 'false')
    }
  })

  it('submits each step as the server reads it, matching labels to the graph', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn<(rows: TraceRow[]) => Promise<void>>().mockResolvedValue(undefined)
    render(
      <TraceTable activity={trace} result={undefined} submitting={false} onSubmit={onSubmit} />,
    )

    await fillRow(user, 1, { current: 'B', queue: 'a, d', visited: 'B', order: 'B' })
    await user.click(screen.getByRole('button', { name: 'Add a step' }))
    // The new step's first cell takes focus, so a keyboard user carries straight on.
    expect(screen.getByRole('combobox', { name: 'Step 2, current vertex' })).toHaveFocus()
    await fillRow(user, 2, { current: 'A', queue: 'D C', visited: '[[B, A]', order: 'B, A' })
    await user.click(screen.getByRole('button', { name: 'Add a step' }))
    await fillRow(user, 3, { current: 'D', queue: 'empty', visited: 'B A D', order: 'B, A, D' })
    await user.click(screen.getByRole('button', { name: 'Check answer' }))

    expect(onSubmit).toHaveBeenCalledWith([
      { visitedVertex: 'B', queue: ['A', 'D'], visited: ['B'], order: ['B'] },
      { visitedVertex: 'A', queue: ['D', 'C'], visited: ['B', 'A'], order: ['B', 'A'] },
      { visitedVertex: 'D', queue: [], visited: ['B', 'A', 'D'], order: ['B', 'A', 'D'] },
    ])
  })

  it('names an input error beside its cell and sends nothing (WCAG 3.3.1)', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn<(rows: TraceRow[]) => Promise<void>>().mockResolvedValue(undefined)
    render(
      <TraceTable activity={trace} result={undefined} submitting={false} onSubmit={onSubmit} />,
    )

    await user.type(screen.getByRole('textbox', { name: 'Step 1, queue after the step' }), 'A, Z')
    await user.type(
      screen.getByRole('textbox', { name: 'Step 1, visited (has left the queue)' }),
      'B',
    )
    await user.type(screen.getByRole('textbox', { name: 'Step 1, order so far' }), 'B')
    await user.click(screen.getByRole('button', { name: 'Check answer' }))

    expect(onSubmit).not.toHaveBeenCalled()
    const current = screen.getByRole('combobox', { name: 'Step 1, current vertex' })
    const queue = screen.getByRole('textbox', { name: 'Step 1, queue after the step' })
    expect(current).toHaveFocus()
    expect(current).toBeInvalid()
    expect(current).toHaveAccessibleDescription(/Choose the vertex that leaves the queue/)
    expect(queue).toBeInvalid()
    expect(queue).toHaveAccessibleDescription(/Z is not a vertex in this graph/)
    const summary = screen.getByRole('status')
    expect(summary).toHaveTextContent('Step 1, current vertex: Choose the vertex')
    expect(summary).toHaveTextContent('Step 1, queue after the step: Z is not a vertex')

    // Fixing the cells clears their errors, and the answer goes.
    await user.selectOptions(current, 'B')
    await user.clear(queue)
    expect(queue).toBeValid()
    await user.click(screen.getByRole('button', { name: 'Check answer' }))
    expect(onSubmit).toHaveBeenCalledOnce()
  })

  it('grows one step at a time up to one per vertex, and shrinks back to one', async () => {
    const user = userEvent.setup()
    render(
      <TraceTable
        activity={trace}
        result={undefined}
        submitting={false}
        onSubmit={vi.fn<(value: unknown) => Promise<void>>()}
      />,
    )
    const add = screen.getByRole('button', { name: 'Add a step' })
    const remove = screen.getByRole('button', { name: 'Remove the last step' })
    expect(remove).toBeDisabled()
    // oxlint-disable-next-line no-await-in-loop -- one click at a time, like a student's
    for (let i = 0; i < 4; i += 1) await user.click(add)
    expect(screen.getAllByRole('combobox')).toHaveLength(5)
    expect(add).toBeDisabled()

    await user.click(remove)
    expect(screen.getAllByRole('combobox')).toHaveLength(4)
    expect(add).toHaveFocus()
  })

  it('marks each step, keeps a mark until that step is edited, and says when steps are missing', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn<(rows: TraceRow[]) => Promise<void>>().mockResolvedValue(undefined)
    const { rerender } = render(
      <TraceTable activity={trace} result={undefined} submitting={false} onSubmit={onSubmit} />,
    )
    await fillRow(user, 1, { current: 'B', queue: 'A, D', visited: 'B', order: 'B' })
    await user.click(screen.getByRole('button', { name: 'Add a step' }))
    await fillRow(user, 2, { current: 'A', queue: '', visited: 'B, A', order: 'B, A' })
    await user.click(screen.getByRole('button', { name: 'Check answer' }))
    expect(onSubmit).toHaveBeenCalledOnce()

    rerender(
      <TraceTable
        activity={trace}
        result={attempt({
          parts: [
            { ref: 0, correct: true, message: null },
            { ref: 1, correct: false, message: 'Queue: only new neighbours join.' },
            { ref: 2, correct: false, message: 'The traversal has more steps than this.' },
            { ref: 3, correct: false, message: 'The traversal has more steps than this.' },
            { ref: 4, correct: false, message: 'The traversal has more steps than this.' },
          ],
        })}
        submitting={false}
        onSubmit={onSubmit}
      />,
    )
    const step2Queue = screen.getByRole('textbox', { name: 'Step 2, queue after the step' })
    expect(screen.getByText('Step 1: correct')).toBeInTheDocument()
    expect(step2Queue).toHaveAccessibleDescription(/Queue: only new neighbours join\./)
    // Says the trace isn't finished, never how many steps are left.
    expect(screen.getByText(/The trace isn’t finished/)).toBeInTheDocument()
    expect(screen.queryByText(/3 more steps/)).not.toBeInTheDocument()

    await user.type(step2Queue, ', C')
    expect(step2Queue).not.toHaveAccessibleDescription(/only new neighbours/)
    expect(screen.queryByText(/only new neighbours/)).not.toBeInTheDocument()
    expect(screen.getByText('Step 1: correct')).toBeInTheDocument()
  })

  it('moves to the next cell on Enter and never submits on it (#136 review)', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn<(rows: TraceRow[]) => Promise<void>>().mockResolvedValue(undefined)
    render(
      <TraceTable activity={trace} result={undefined} submitting={false} onSubmit={onSubmit} />,
    )
    const current = screen.getByRole('combobox', { name: 'Step 1, current vertex' })
    await user.selectOptions(current, 'B')
    current.focus()
    await user.keyboard('{Enter}')
    const queue = screen.getByRole('textbox', { name: 'Step 1, queue after the step' })
    expect(queue).toHaveFocus()
    await user.keyboard('A, D{Enter}B{Enter}B{Enter}')
    // After the last cell of the last step, Enter goes to "Add a step", not to Check.
    expect(screen.getByRole('button', { name: 'Add a step' })).toHaveFocus()
    expect(onSubmit).not.toHaveBeenCalled()
    await user.keyboard('{Enter}')
    expect(screen.getByRole('combobox', { name: 'Step 2, current vertex' })).toHaveFocus()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('refuses a half-filled table: blank visited or order, or a last queue not empty', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn<(rows: TraceRow[]) => Promise<void>>().mockResolvedValue(undefined)
    render(
      <TraceTable activity={trace} result={undefined} submitting={false} onSubmit={onSubmit} />,
    )
    await fillRow(user, 1, { current: 'B', queue: 'A, D', visited: '', order: '' })
    await user.click(screen.getByRole('button', { name: 'Check answer' }))
    expect(onSubmit).not.toHaveBeenCalled()
    const queue = screen.getByRole('textbox', { name: 'Step 1, queue after the step' })
    expect(queue).toHaveFocus()
    expect(queue).toHaveAccessibleDescription(/BFS ends only when the queue is empty/)
    expect(
      screen.getByRole('textbox', { name: 'Step 1, visited (has left the queue)' }),
    ).toHaveAccessibleDescription(/Fill in every vertex that has left the queue/)
    expect(screen.getByRole('textbox', { name: 'Step 1, order so far' })).toBeInvalid()
    // No confirm dialog: the reason is inline.
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    // The same queue is fine on a step that isn't the last.
    await user.click(screen.getByRole('button', { name: 'Add a step' }))
    await fillRow(user, 1, { current: 'B', queue: 'A, D', visited: 'B', order: 'B' })
    expect(queue).toBeValid()
  })

  it('names a list longer than the graph as an input error, not a server error', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn<(rows: TraceRow[]) => Promise<void>>().mockResolvedValue(undefined)
    render(
      <TraceTable activity={trace} result={undefined} submitting={false} onSubmit={onSubmit} />,
    )
    await fillRow(user, 1, { current: 'B', queue: '', visited: 'B', order: 'B, A, A, A, A, A' })
    await user.click(screen.getByRole('button', { name: 'Check answer' }))
    expect(onSubmit).not.toHaveBeenCalled()
    expect(
      screen.getByRole('textbox', { name: 'Step 1, order so far' }),
    ).toHaveAccessibleDescription(/This lists 6 vertices, but the graph has only 5/)
  })

  it('locks once the trace is correct', () => {
    render(
      <TraceTable
        activity={trace}
        result={attempt({ correct: true, score: 1 })}
        submitting={false}
        onSubmit={vi.fn<(value: unknown) => Promise<void>>()}
      />,
    )
    expect(screen.getByRole('combobox', { name: 'Step 1, current vertex' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Check answer' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Add a step' })).toBeDisabled()
  })
})

describe('fix the bug', () => {
  function program() {
    return within(screen.getByRole('list', { name: 'Your fixed program' }))
      .getAllByRole('listitem')
      .map((item) => {
        // The code as drawn: its indentation (padding of one space each) and its text, without
        // the visually hidden words for a screen reader.
        const code = item.querySelector('code')
        return ' '.repeat(Number(code?.dataset.indent)) + (code?.firstChild?.textContent ?? '')
      })
  }

  it('starts as the faulty program, with indentation kept', () => {
    render(
      <FixTheBug
        activity={fix}
        result={undefined}
        submitting={false}
        onSubmit={vi.fn<(value: unknown) => Promise<void>>()}
      />,
    )
    expect(program()).toEqual(fix.config.lines.map((line) => line.text))
    const list = screen.getByRole('list', { name: 'Your fixed program' })
    expect(list.querySelector('code')?.className).toMatch(/whitespace-pre/)
    // A screen reader skips leading spaces, so the level is also in words (#136 review).
    const codes = list.querySelectorAll('code')
    expect(codes[0]?.textContent).toBe('def bfs(graph, start):')
    expect(codes[3]?.textContent).toBe('v = queue.pop() (indent level 2)')
    // Corrections are offered in the content's order, never sorted by id (A5 reorders them).
    const line4 = screen.getByRole('combobox', { name: 'Line 4' })
    expect(
      within(line4)
        .getAllByRole('option')
        .map((o) => o.textContent),
    ).toEqual([
      'Keep this line',
      'Replace with: “v = queue.popleft()” (indent level 2)',
      'Replace with: “v = queue[0]” (indent level 2)',
    ])
  })

  it('replaces a faulty line with a correction and submits the fixed program in order', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn<(order: number[]) => Promise<void>>().mockResolvedValue(undefined)
    render(<FixTheBug activity={fix} result={undefined} submitting={false} onSubmit={onSubmit} />)

    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Line 4' }),
      'Replace with: “v = queue.popleft()” (indent level 2)',
    )
    expect(program()[3]).toBe('        v = queue.popleft()')
    await user.click(screen.getByRole('button', { name: 'Check answer' }))
    expect(onSubmit).toHaveBeenCalledWith([1, 2, 3, 20, 5])
  })

  it('moves lines with buttons, keeping focus on the moved line (no dragging, WCAG 2.5.7)', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn<(order: number[]) => Promise<void>>().mockResolvedValue(undefined)
    render(<FixTheBug activity={fix} result={undefined} submitting={false} onSubmit={onSubmit} />)

    await user.click(screen.getByRole('button', { name: 'Move line 5 up' }))
    expect(screen.getByRole('button', { name: 'Move line 4 up' })).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(screen.getByRole('button', { name: 'Move line 3 up' })).toHaveFocus()
    expect(screen.getByText('Moved line 4 to line 3.')).toBeInTheDocument()

    // Down to the bottom: the Down button is then disabled, so focus goes to Up.
    await user.click(screen.getByRole('button', { name: 'Move line 3 down' }))
    await user.click(screen.getByRole('button', { name: 'Move line 4 down' }))
    expect(screen.getByRole('button', { name: 'Move line 5 down' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Move line 5 up' })).toHaveFocus()
    expect(screen.getByRole('button', { name: 'Move line 1 up' })).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'Check answer' }))
    expect(onSubmit).toHaveBeenCalledWith([1, 2, 3, 4, 5])
  })

  it('removes a line, puts it back where it was, and inserts a correction as a new line', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn<(order: number[]) => Promise<void>>().mockResolvedValue(undefined)
    render(<FixTheBug activity={fix} result={undefined} submitting={false} onSubmit={onSubmit} />)

    await user.click(screen.getByRole('button', { name: 'Remove line 2' }))
    expect(program()).toHaveLength(4)
    expect(screen.getByRole('combobox', { name: 'Line 2' })).toHaveFocus()
    expect(screen.getByText('Removed lines')).toBeInTheDocument()

    await user.click(
      screen.getByRole('button', { name: 'Put back: “queue = deque([start])” (indent level 1)' }),
    )
    expect(program()[1]).toBe('    queue = deque([start])')
    expect(screen.queryByText('Removed lines')).not.toBeInTheDocument()

    const insert = screen.getByRole('button', { name: 'Insert line' })
    expect(insert).toBeDisabled()
    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Correction' }),
      '“v = queue[0]” (indent level 2)',
    )
    await user.selectOptions(
      screen.getByRole('combobox', { name: 'Where' }),
      'After line 3: “while queue:” (indent level 1)',
    )
    await user.click(insert)
    expect(program()[3]).toBe('        v = queue[0]')
    expect(screen.getByRole('combobox', { name: 'Line 4' })).toHaveFocus()

    await user.click(screen.getByRole('button', { name: 'Check answer' }))
    expect(onSubmit).toHaveBeenCalledWith([1, 2, 3, 21, 4, 5])
  })

  it('removing every line leaves an empty program that can still be checked', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn<(order: number[]) => Promise<void>>().mockResolvedValue(undefined)
    render(<FixTheBug activity={fix} result={undefined} submitting={false} onSubmit={onSubmit} />)
    for (let i = 0; i < fix.config.lines.length; i += 1)
      // oxlint-disable-next-line no-await-in-loop -- one click at a time, like a student's
      await user.click(screen.getByRole('button', { name: 'Remove line 1' }))
    expect(screen.getByRole('combobox', { name: 'Correction' })).toHaveFocus()
    await user.click(screen.getByRole('button', { name: 'Check answer' }))
    expect(onSubmit).toHaveBeenCalledWith([])
  })

  it('shows a mark per line and for missing lines, and clears them on the next change', async () => {
    const user = userEvent.setup()
    render(
      <FixTheBug
        activity={fix}
        result={attempt({
          parts: [
            { ref: 0, correct: true, message: null },
            { ref: 3, correct: false, message: 'pop() takes the newest vertex.' },
            { ref: 5, correct: false, message: 'A line is missing from this position.' },
          ],
        })}
        submitting={false}
        onSubmit={vi.fn<(value: unknown) => Promise<void>>()}
      />,
    )
    expect(screen.getByRole('combobox', { name: 'Line 4' })).toHaveAccessibleDescription(
      /Check again: pop\(\) takes the newest vertex\./,
    )
    expect(screen.getByText('Line 6: A line is missing from this position.')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Move line 2 down' }))
    expect(screen.queryByText(/pop\(\) takes the newest/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Line 6:/)).not.toBeInTheDocument()
  })

  it('locks once the program is fixed', () => {
    render(
      <FixTheBug
        activity={fix}
        result={attempt({ correct: true, score: 1 })}
        submitting={false}
        onSubmit={vi.fn<(value: unknown) => Promise<void>>()}
      />,
    )
    expect(screen.getByRole('combobox', { name: 'Line 1' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Remove line 1' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Check answer' })).toBeDisabled()
  })
})

describe('choose tests', () => {
  it('shows the faulty code with its indentation, and each test case as text', () => {
    render(
      <ChooseTests
        activity={choose}
        result={undefined}
        submitting={false}
        onSubmit={vi.fn<(value: unknown) => Promise<void>>()}
      />,
    )
    const code = screen.getByRole('figure', { name: 'The faulty BFS' })
    const lines = within(code)
      .getAllByRole('listitem')
      .map((li) => li.querySelector('code'))
    expect(lines.map((line) => line?.textContent)).toEqual([
      'def bfs(graph, start):',
      '    visited = set() (indent level 1)',
      '        # deeper (indent level 2)',
    ])
    expect(lines[1]?.className).toMatch(/whitespace-pre/)

    const first = screen.getByRole('checkbox', { name: 'Test 1: start at A' })
    expect(first).toHaveAccessibleDescription(
      'Graph: undirected Vertices: A, B, C Edges: A–B, B–C, C–A Expected order: A, B, C',
    )
    expect(
      screen.getByRole('checkbox', { name: 'Test 2: start at A' }),
    ).toHaveAccessibleDescription(/Edges: none/)
    expect(
      screen.getByRole('checkbox', { name: 'Test 3: start at A' }),
    ).toHaveAccessibleDescription(/Graph: directed .*Edges: B→A/)
    // The stored ids ("cycle") would name the property to spot, so they are not shown.
    expect(screen.queryByText(/cycle/)).not.toBeInTheDocument()
  })

  it('asks for a choice before checking, then submits the chosen ids in the order shown', async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn<(selected: string[]) => Promise<void>>().mockResolvedValue(undefined)
    render(
      <ChooseTests activity={choose} result={undefined} submitting={false} onSubmit={onSubmit} />,
    )

    await user.click(screen.getByRole('button', { name: 'Check answer' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Choose at least one test case')
    expect(onSubmit).not.toHaveBeenCalled()

    await user.click(screen.getByRole('checkbox', { name: 'Test 3: start at A' }))
    await user.click(screen.getByRole('checkbox', { name: 'Test 1: start at A' }))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Check answer' }))
    expect(onSubmit).toHaveBeenCalledWith(['cycle', 'one-way'])
  })

  it('toggles with the Space key', async () => {
    const user = userEvent.setup()
    render(
      <ChooseTests
        activity={choose}
        result={undefined}
        submitting={false}
        onSubmit={vi.fn<(value: unknown) => Promise<void>>()}
      />,
    )
    const box = screen.getByRole('checkbox', { name: 'Test 2: start at A' })
    box.focus()
    await user.keyboard(' ')
    expect(box).toBeChecked()
    await user.keyboard(' ')
    expect(box).not.toBeChecked()
  })

  it("marks every test case, and drops a case's mark once its choice changes", async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn<(selected: string[]) => Promise<void>>().mockResolvedValue(undefined)
    const { rerender } = render(
      <ChooseTests activity={choose} result={undefined} submitting={false} onSubmit={onSubmit} />,
    )
    await user.click(screen.getByRole('checkbox', { name: 'Test 2: start at A' }))
    await user.click(screen.getByRole('button', { name: 'Check answer' }))
    rerender(
      <ChooseTests
        activity={choose}
        result={attempt({
          parts: [
            { ref: 0, correct: false, message: 'C is found twice: it fails.' },
            { ref: 1, correct: false, message: 'Nothing can repeat: it passes.' },
            { ref: 2, correct: true, message: null },
          ],
        })}
        submitting={false}
        onSubmit={onSubmit}
      />,
    )
    const first = screen.getByRole('checkbox', { name: 'Test 1: start at A' })
    const second = screen.getByRole('checkbox', { name: 'Test 2: start at A' })
    expect(first).toHaveAccessibleDescription(/Check again: C is found twice: it fails\.$/)
    expect(second).toHaveAccessibleDescription(/Check again: Nothing can repeat: it passes\.$/)
    expect(
      screen.getByRole('checkbox', { name: 'Test 3: start at A' }),
    ).toHaveAccessibleDescription(/Correct$/)

    await user.click(second)
    expect(screen.queryByText(/Nothing can repeat/)).not.toBeInTheDocument()
    expect(screen.getByText(/C is found twice/)).toBeInTheDocument()
  })
})

describe('the renderer and the activity page', () => {
  it.each<Activity>([trace, fix, choose])(
    'wraps a $kind activity in the feedback panel and hint ladder',
    async (activity) => {
      render(
        <ActivityRenderer
          activity={activity}
          result={attempt({ feedback: '1 of 3 correct.' })}
          submitting={false}
          onSubmit={vi.fn<(value: unknown) => Promise<void>>()}
          {...noHints}
        />,
      )
      expect(screen.queryByText('This activity kind is not available yet.')).not.toBeInTheDocument()
      expect(screen.getByRole('region', { name: 'Submission results' })).toHaveTextContent(
        '1 of 3 correct.',
      )
      expect(await screen.findByRole('region', { name: 'Hints' })).toBeInTheDocument()
    },
  )

  it('runs a trace activity end to end: load, fill in, check, per-step feedback', async () => {
    const api = fakeApi({
      user: ada,
      overrides: {
        'GET /api/activities/315': () => Response.json(trace),
        'GET /api/activities/315/hints': () => Response.json([]),
        'POST /api/activities/315/attempts': () =>
          Response.json(
            attempt({
              activityId: 315,
              parts: [
                { ref: 0, correct: false, message: 'Order so far: the vertices in order.' },
                { ref: 1, correct: false, message: 'The traversal has more steps than this.' },
              ],
              feedback: '0 of 2 correct.',
            }),
          ),
      },
    })
    const user = userEvent.setup()
    renderApp('/activities/315')

    await user.selectOptions(
      await screen.findByRole('combobox', { name: 'Step 1, current vertex' }),
      'B',
    )
    await user.type(
      screen.getByRole('textbox', { name: 'Step 1, visited (has left the queue)' }),
      'B',
    )
    await user.type(screen.getByRole('textbox', { name: 'Step 1, order so far' }), 'B')
    await user.click(screen.getByRole('button', { name: 'Check answer' }))

    await waitFor(() => expect(api.callsTo('POST /api/activities/315/attempts')).toHaveLength(1))
    expect(api.callsTo('POST /api/activities/315/attempts')[0]?.body).toEqual({
      submitted: { rows: [{ visitedVertex: 'B', queue: [], visited: ['B'], order: ['B'] }] },
    })
    expect(await screen.findByText('0 of 2 correct.')).toBeInTheDocument()
    expect(screen.getByText(/Step 1: check again\. Order so far/)).toBeInTheDocument()
    expect(screen.getByText(/The trace isn’t finished/)).toBeInTheDocument()
  })

  it('posts the chosen test ids and the fixed program from the activity page', async () => {
    const api = fakeApi({
      user: ada,
      overrides: {
        'GET /api/activities/623': () => Response.json(choose),
        'GET /api/activities/623/hints': () => Response.json([]),
        'POST /api/activities/623/attempts': () => Response.json(attempt({ activityId: 623 })),
        'GET /api/activities/622': () => Response.json(fix),
        'GET /api/activities/622/hints': () => Response.json([]),
        'POST /api/activities/622/attempts': () => Response.json(attempt({ activityId: 622 })),
      },
    })
    const user = userEvent.setup()
    const { unmount } = renderApp('/activities/623')
    await user.click(await screen.findByRole('checkbox', { name: 'Test 1: start at A' }))
    await user.click(screen.getByRole('button', { name: 'Check answer' }))
    await waitFor(() => expect(api.callsTo('POST /api/activities/623/attempts')).toHaveLength(1))
    expect(api.callsTo('POST /api/activities/623/attempts')[0]?.body).toEqual({
      submitted: { selected: ['cycle'] },
    })
    unmount()

    renderApp('/activities/622')
    await user.click(await screen.findByRole('button', { name: 'Check answer' }))
    await waitFor(() => expect(api.callsTo('POST /api/activities/622/attempts')).toHaveLength(1))
    expect(api.callsTo('POST /api/activities/622/attempts')[0]?.body).toEqual({
      submitted: { order: [1, 2, 3, 4, 5] },
    })
  })
})

// #142 follow-up to #164: Check answer on these three screens keeps focus while the answer is
// checked (Button's keepFocusWhileLoading), so focus never drops to <body>: it stays on the busy
// button, moves to the result when it arrives, and stays on the button when the check fails.
describe('focus while checking (WCAG 2.4.3)', () => {
  const screens: {
    name: string
    activity: Activity
    fillIn: (user: ReturnType<typeof userEvent.setup>) => Promise<void>
  }[] = [
    {
      name: 'trace table',
      activity: trace,
      fillIn: async (user) => {
        await user.selectOptions(
          await screen.findByRole('combobox', { name: 'Step 1, current vertex' }),
          'B',
        )
        await user.type(
          screen.getByRole('textbox', { name: 'Step 1, visited (has left the queue)' }),
          'B',
        )
        await user.type(screen.getByRole('textbox', { name: 'Step 1, order so far' }), 'B')
      },
    },
    { name: 'fix the bug', activity: fix, fillIn: async () => {} },
    {
      name: 'choose tests',
      activity: choose,
      fillIn: async (user) => {
        await user.click(await screen.findByRole('checkbox', { name: 'Test 1: start at A' }))
      },
    },
  ]

  function page(activity: Activity, attemptResponse: () => Response | Promise<Response>) {
    const api = fakeApi({
      user: ada,
      overrides: {
        [`GET /api/activities/${activity.id}`]: () => Response.json(activity),
        [`GET /api/activities/${activity.id}/hints`]: () => Response.json([]),
        [`POST /api/activities/${activity.id}/attempts`]: attemptResponse,
      },
    })
    renderApp(`/activities/${activity.id}`)
    return api
  }

  it.each(screens)(
    '$name: stays on a busy Check answer, then focuses the result',
    async ({ activity, fillIn }) => {
      let release: (response: Response) => void = () => {}
      const api = page(activity, () => new Promise<Response>((resolve) => (release = resolve)))
      const user = userEvent.setup()
      await fillIn(user)
      const button = await screen.findByRole('button', { name: 'Check answer' })
      button.focus()
      await user.keyboard('{Enter}')

      await waitFor(() => expect(button).toHaveAttribute('aria-busy', 'true'))
      expect(button).toHaveAttribute('aria-disabled', 'true')
      expect(button).toBeEnabled()
      expect(button).toHaveFocus()
      await user.keyboard('{Enter}') // ignored while busy
      expect(api.callsTo(`POST /api/activities/${activity.id}/attempts`)).toHaveLength(1)

      release(
        Response.json(attempt({ activityId: activity.id, feedback: 'Not quite, 0 of 2 correct.' })),
      )
      const result = await screen.findByRole('group', { name: 'Not quite, 0 of 2 correct.' })
      await waitFor(() => expect(result).toHaveFocus())
    },
  )

  it.each(screens)(
    '$name: keeps focus on Check answer when the check fails, with the error announced',
    async ({ activity, fillIn }) => {
      page(activity, () => Response.json({ detail: 'Internal Server Error' }, { status: 500 }))
      const user = userEvent.setup()
      await fillIn(user)
      const button = await screen.findByRole('button', { name: 'Check answer' })
      button.focus()
      await user.keyboard('{Enter}')

      expect(await screen.findByRole('alert')).toHaveTextContent('Try again')
      expect(button).toHaveFocus()
      expect(button).not.toHaveAttribute('aria-busy')
      expect(document.activeElement).not.toBe(document.body)
    },
  )
})

describe('coming back to an answered activity (#171)', () => {
  it('fix the bug starts from the program the student sent', async () => {
    const onSubmit = vi.fn<(order: number[]) => Promise<void>>().mockResolvedValue(undefined)
    render(
      <FixTheBug
        activity={fix}
        result={undefined}
        submitting={false}
        onSubmit={onSubmit}
        previous={[1, 2, 3, 20, 5]}
      />,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Check answer' }))
    expect(onSubmit).toHaveBeenCalledWith([1, 2, 3, 20, 5])
  })

  it('fix the bug pairs a correction with the line it replaced, by position (#171 review)', () => {
    // Line 2 removed and line 4 replaced: the correction after line 3 goes with line 4, and
    // line 2 is the removed one, offered to put back.
    render(
      <FixTheBug
        activity={fix}
        result={undefined}
        submitting={false}
        onSubmit={vi.fn<(order: number[]) => Promise<void>>()}
        previous={[1, 3, 20, 5]}
      />,
    )
    const corrected = screen.getByRole('combobox', { name: 'Line 3' })
    expect(corrected).toHaveValue('20')
    expect(within(corrected).getByRole('option', { name: 'Keep this line' })).toHaveValue('4')
    const removed = screen.getByRole('region', { name: 'Removed lines' })
    expect(within(removed).getByRole('button', { name: /Put back: .*deque/ })).toBeInTheDocument()
    expect(within(removed).queryByText(/queue\.pop\(\)/)).not.toBeInTheDocument()
  })

  it('an answered fix the bug item can’t be changed (#171 review)', () => {
    render(
      <FixTheBug
        activity={fix}
        result={undefined}
        submitting={false}
        onSubmit={vi.fn<(order: number[]) => Promise<void>>()}
        previous={[1, 3, 20, 5]}
        readOnly
      />,
    )
    expect(screen.getByRole('combobox', { name: 'Line 1' })).toBeDisabled()
    expect(screen.getByRole('button', { name: /Put back/ })).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Check answer' })).not.toBeInTheDocument()
  })

  it('a trace table starts from the rows sent, each with its own mark (#171 review)', () => {
    render(
      <TraceTable
        activity={trace}
        result={attempt({
          parts: [
            { ref: 0, correct: true, message: null },
            { ref: 1, correct: false, message: 'Queue: only new neighbours join.' },
            { ref: 2, correct: false, message: 'The traversal has more steps than this.' },
          ],
        })}
        submitting={false}
        onSubmit={vi.fn<(rows: TraceRow[]) => Promise<void>>()}
        previous={[
          { visitedVertex: 'B', queue: ['A', 'D'], visited: ['B'], order: ['B'] },
          { visitedVertex: 'A', queue: ['D', 'B'], visited: ['B', 'A'], order: ['B', 'A'] },
        ]}
      />,
    )
    expect(screen.getByRole('combobox', { name: 'Step 1, current vertex' })).toHaveValue('B')
    expect(screen.getByRole('combobox', { name: 'Step 2, current vertex' })).toHaveValue('A')
    const step2Queue = screen.getByRole('textbox', { name: 'Step 2, queue after the step' })
    expect(step2Queue).toHaveValue('D, B')
    // Row 1's mark is on row 1 and row 2's on row 2.
    expect(screen.getByText('Step 1: correct')).toBeInTheDocument()
    expect(step2Queue).toHaveAccessibleDescription(/Queue: only new neighbours join\./)
    expect(
      screen.getByRole('textbox', { name: 'Step 1, queue after the step' }),
    ).not.toHaveAccessibleDescription(/only new neighbours/)
    expect(screen.getByText(/The trace isn’t finished/)).toBeInTheDocument()
  })

  it('an answered trace item can’t be changed (#171 review)', () => {
    render(
      <TraceTable
        activity={trace}
        result={undefined}
        submitting={false}
        onSubmit={vi.fn<(rows: TraceRow[]) => Promise<void>>()}
        previous={[{ visitedVertex: 'B', queue: [], visited: ['B'], order: ['B'] }]}
        readOnly
      />,
    )
    expect(screen.getByRole('combobox', { name: 'Step 1, current vertex' })).toBeDisabled()
    expect(screen.getByRole('textbox', { name: 'Step 1, order so far' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Add a step' })).toBeDisabled()
  })

  it('choose tests starts from the tests the student chose', async () => {
    const onSubmit = vi.fn<(selected: string[]) => Promise<void>>().mockResolvedValue(undefined)
    render(
      <ChooseTests
        activity={choose}
        result={undefined}
        submitting={false}
        onSubmit={onSubmit}
        previous={['cycle']}
      />,
    )
    expect(
      screen.getAllByRole('checkbox').filter((box) => (box as HTMLInputElement).checked),
    ).toHaveLength(1)
    await userEvent.click(screen.getByRole('button', { name: 'Check answer' }))
    expect(onSubmit).toHaveBeenCalledWith(['cycle'])
  })
})
