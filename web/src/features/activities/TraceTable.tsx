import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { Alert, Button } from '../../components'
import { toBfsScenario } from '../bfs/bfs.api.ts'
import { GraphCanvas } from '../bfs/GraphCanvas.tsx'
import type { AttemptResult, TraceActivity, TraceRow } from './activities.types.ts'
import { parseVertexList } from './traceInput.ts'

type TraceTableProps = {
  activity: TraceActivity
  result: AttemptResult | undefined
  submitting: boolean
  onSubmit: (rows: TraceRow[]) => Promise<void>
}

/** A row as the student typed it. */
type Draft = { key: number; current: string; queue: string; visited: string; order: string }
type ListColumn = 'queue' | 'visited' | 'order'

const EN_DASH = '–'
const ARROW = '→'
const LIST_COLUMNS: readonly { column: ListColumn; heading: string }[] = [
  { column: 'queue', heading: 'Queue after the step' },
  { column: 'visited', heading: 'Visited' },
  { column: 'order', heading: 'Order so far' },
]
const MAX_INPUT = 300

function sameDraft(a: Draft | undefined, b: Draft | undefined): boolean {
  return (
    !!a &&
    !!b &&
    a.current === b.current &&
    a.queue === b.queue &&
    a.visited === b.visited &&
    a.order === b.order
  )
}

/** The BFS trace table (FR-4.1, FR-6.6; objective 5, ID document Table 1 row 5). One row for each
 * vertex that leaves the queue, with the columns module 3's worked example uses: the current
 * vertex (the one that leaves the queue and is visited), the queue after the step, the visited
 * set and the order so far. A vertex is found when it joins the queue and visited when it leaves
 * it, which is the definition module 3 teaches and the server's BFS engine uses.
 *
 * The student picks the current vertex from the graph's vertices and types each list, e.g.
 * "C, E", front of the queue first. A label that is not in the graph is an input error, named
 * beside its cell before anything is sent. The table starts with one step and grows one step at
 * a time, up to one per vertex, so the number of rows gives nothing away.
 *
 * The server checks every row against the engine's step and returns one mark per row, with what
 * to look at in a wrong one (Hattie and Timperley 2007; Shute 2008). A row's mark shows until the
 * student edits that row. The table scrolls inside its own labelled region at 320 px, so the page
 * never does (WCAG 1.4.10). */
export function TraceTable({ activity, result, submitting, onSubmit }: TraceTableProps) {
  const { vertices, start_vertex: start, edges, directed } = activity.config
  const baseId = useId()
  const [rows, setRows] = useState<Draft[]>([
    { key: 0, current: '', queue: '', visited: '', order: '' },
  ])
  const [nextKey, setNextKey] = useState(1)
  const [checked, setChecked] = useState<Draft[]>([])
  const [showErrors, setShowErrors] = useState(false)
  // The control to focus once React has drawn the row it belongs to.
  const focusNext = useRef('')
  const disabled = submitting || result?.correct === true
  const parts = new Map(result?.parts.map((part) => [part.ref, part]))
  const missingSteps =
    result?.parts.filter((part) => part.ref >= rows.length && !part.correct) ?? []
  const maxRows = Math.min(vertices.length, 50)

  const scenario = useMemo(
    () =>
      toBfsScenario({
        graph: {
          id: activity.id,
          name: `Graph to trace from ${start}`,
          directed,
          vertices: [...vertices],
          edges: [...edges],
          startVertex: start,
        },
        bfs: { startVertex: start, order: [], steps: [] },
      }),
    [activity.id, directed, edges, start, vertices],
  )

  useEffect(() => {
    if (!focusNext.current) return
    document.getElementById(focusNext.current)?.focus()
    focusNext.current = ''
  })

  const cellId = (key: number, column: string) => `${baseId}-${key}-${column}`

  // Input errors, keyed by the id of the control they belong to: what is wrong, and where.
  const errors = new Map<string, { message: string; where: string }>()
  rows.forEach((row, index) => {
    if (!row.current)
      errors.set(cellId(row.key, 'current'), {
        message: 'Choose the vertex that leaves the queue.',
        where: `Step ${index + 1}, current vertex`,
      })
    for (const { column, heading } of LIST_COLUMNS) {
      const { unknown } = parseVertexList(row[column], vertices)
      if (unknown.length > 0)
        errors.set(cellId(row.key, column), {
          message: `${unknown.join(', ')} ${unknown.length === 1 ? 'is not a vertex' : 'are not vertices'} in this graph.`,
          where: `Step ${index + 1}, ${heading.toLowerCase()}`,
        })
    }
  })
  const visibleErrors = showErrors ? errors : new Map<string, { message: string; where: string }>()

  function update(index: number, change: Partial<Draft>) {
    setRows(rows.map((row, i) => (i === index ? { ...row, ...change } : row)))
  }

  function addRow() {
    const row = { key: nextKey, current: '', queue: '', visited: '', order: '' }
    setNextKey(nextKey + 1)
    setRows([...rows, row])
    focusNext.current = cellId(row.key, 'current')
  }

  function removeLastRow() {
    setRows(rows.slice(0, -1))
    focusNext.current = `${baseId}-add`
  }

  const edgeText = edges
    .map((edge) => `${edge.source}${directed ? ARROW : EN_DASH}${edge.target}`)
    .join(', ')

  return (
    <form
      className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-4"
      noValidate
      onSubmit={(event) => {
        event.preventDefault()
        if (errors.size > 0) {
          setShowErrors(true)
          document.getElementById(errors.keys().next().value ?? '')?.focus()
          return
        }
        setShowErrors(false)
        setChecked(rows)
        void onSubmit(
          rows.map((row) => ({
            visitedVertex: row.current,
            queue: parseVertexList(row.queue, vertices).values,
            visited: parseVertexList(row.visited, vertices).values,
            order: parseVertexList(row.order, vertices).values,
          })),
        )
      }}
    >
      <GraphCanvas scenario={scenario} frame={scenario.frames[0]} />
      <p className="m-0 text-sm">
        <span className="font-medium">{directed ? 'Directed' : 'Undirected'} graph.</span> Edges:{' '}
        <span className="font-mono [overflow-wrap:anywhere]">{edgeText || 'none'}</span>
      </p>
      <p id={`${baseId}-how`} className="m-0 text-sm text-muted-foreground">
        Add one step each time a vertex leaves the queue. Type the vertices of each list separated
        by commas, with the front of the queue first, e.g. “C, E”. Leave the queue blank when it is
        empty.
      </p>

      {showErrors && errors.size > 0 && (
        <Alert tone="warning" title="Check the highlighted cells">
          <ul className="m-0 grid gap-1 pl-4">
            {[...errors.entries()].map(([id, error]) => (
              <li key={id}>
                {error.where}: {error.message}
              </li>
            ))}
          </ul>
        </Alert>
      )}

      {/* A wide table scrolls here, not the page (WCAG 1.4.10). Its cells are inputs, so a
          keyboard scrolls it by moving through them. */}
      <section
        aria-labelledby={`${baseId}-caption`}
        className="min-w-0 overflow-x-auto rounded border border-border"
      >
        <table className="w-full min-w-[36rem] border-collapse text-sm">
          <caption id={`${baseId}-caption`} className="p-2 text-left font-medium">
            Your trace table, from {start}
          </caption>
          <thead>
            <tr className="border-b border-border bg-muted/40 text-left">
              <th scope="col" className="p-2">
                Step
              </th>
              <th scope="col" className="p-2">
                Current vertex
              </th>
              {LIST_COLUMNS.map(({ column, heading }) => (
                <th key={column} scope="col" className="p-2">
                  {heading}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-border text-muted-foreground">
              <th scope="row" className="p-2 text-left font-normal">
                start
              </th>
              <td className="p-2">{EN_DASH}</td>
              <td className="p-2 font-mono">{start}</td>
              <td className="p-2">{EN_DASH}</td>
              <td className="p-2">{EN_DASH}</td>
            </tr>
            {rows.map((row, index) => {
              const part = sameDraft(checked[index], row) ? parts.get(index) : undefined
              const markId = `${baseId}-${row.key}-mark`
              const describedBy = (control: string) =>
                [
                  `${baseId}-how`,
                  visibleErrors.has(cellId(row.key, control))
                    ? `${cellId(row.key, control)}-error`
                    : '',
                  part ? markId : '',
                ]
                  .filter(Boolean)
                  .join(' ')
              const tone = part ? (part.correct ? 'bg-success/10' : 'bg-warning/10') : ''
              return (
                <tr key={row.key} className={`border-b border-border align-top ${tone}`}>
                  <th scope="row" className="p-2 text-left whitespace-nowrap">
                    {index + 1}
                    {part && (
                      <span
                        aria-hidden="true"
                        className={part.correct ? 'text-success' : 'text-warning'}
                      >
                        {part.correct ? ' \u2713' : ' !'}
                      </span>
                    )}
                  </th>
                  <td className="p-2">
                    <select
                      id={cellId(row.key, 'current')}
                      aria-label={`Step ${index + 1}, current vertex`}
                      aria-invalid={visibleErrors.has(cellId(row.key, 'current')) || undefined}
                      aria-describedby={describedBy('current')}
                      className="w-full rounded border border-primary bg-background px-2 py-1 font-mono"
                      value={row.current}
                      disabled={disabled}
                      onChange={(event) => update(index, { current: event.target.value })}
                    >
                      <option value="">Choose</option>
                      {vertices.map((vertex) => (
                        <option key={vertex} value={vertex}>
                          {vertex}
                        </option>
                      ))}
                    </select>
                    <CellError id={cellId(row.key, 'current')} errors={visibleErrors} />
                  </td>
                  {LIST_COLUMNS.map(({ column, heading }) => (
                    <td key={column} className="p-2">
                      <input
                        id={cellId(row.key, column)}
                        type="text"
                        autoComplete="off"
                        spellCheck={false}
                        maxLength={MAX_INPUT}
                        aria-label={`Step ${index + 1}, ${heading.toLowerCase()}`}
                        aria-invalid={visibleErrors.has(cellId(row.key, column)) || undefined}
                        aria-describedby={describedBy(column)}
                        className="w-full rounded border border-primary bg-background px-2 py-1 font-mono"
                        value={row[column]}
                        disabled={disabled}
                        onChange={(event) => update(index, { [column]: event.target.value })}
                      />
                      <CellError id={cellId(row.key, column)} errors={visibleErrors} />
                    </td>
                  ))}
                </tr>
              )
            })}
          </tbody>
        </table>
      </section>

      {/* The marks sit under the table, not in it, so a long message is read in full at 320 px
          instead of scrolling with the table. Each cell of a step is described by its mark. */}
      {result && (
        <ul className="m-0 grid list-none gap-1 p-0 text-sm" aria-label="Result for each step">
          {rows.map((row, index) => {
            const part = sameDraft(checked[index], row) ? parts.get(index) : undefined
            if (!part) return null
            return (
              <li
                key={row.key}
                id={`${baseId}-${row.key}-mark`}
                className={part.correct ? 'text-success' : 'text-warning'}
              >
                {part.correct
                  ? `Step ${index + 1}: correct`
                  : `Step ${index + 1}: check again. ${part.message ?? ''}`.trim()}
              </li>
            )
          })}
        </ul>
      )}

      {missingSteps.length > 0 && rows.length === checked.length && (
        <p className="m-0 text-sm text-warning">
          {missingSteps.length === 1
            ? 'There is one more step'
            : `There are ${missingSteps.length} more steps`}{' '}
          after step {rows.length}: the traversal is not finished yet.
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <Button
          id={`${baseId}-add`}
          variant="secondary"
          size="sm"
          disabled={disabled || rows.length >= maxRows}
          onClick={addRow}
        >
          Add a step
        </Button>
        <Button
          variant="ghost"
          size="sm"
          disabled={disabled || rows.length <= 1}
          onClick={removeLastRow}
        >
          Remove the last step
        </Button>
      </div>
      <div>
        <Button type="submit" loading={submitting} disabled={disabled}>
          Check answer
        </Button>
      </div>
    </form>
  )
}

/** The input error for one cell, named beside it and linked to it by aria-describedby. */
function CellError({
  id,
  errors,
}: {
  id: string
  errors: ReadonlyMap<string, { message: string }>
}) {
  const error = errors.get(id)
  if (!error) return null
  return (
    <p id={`${id}-error`} className="m-0 mt-1 text-sm text-warning">
      {error.message}
    </p>
  )
}
