import { useEffect, useId, useRef, useState } from 'react'
import { Button } from '../../components'
import type { AttemptResult, CodeLine, FixTheBugActivity } from './activities.types.ts'
import { IndentedCode } from './CodeListing.tsx'
import { lineName } from './codeLines.ts'

type FixTheBugProps = {
  activity: FixTheBugActivity
  result: AttemptResult | undefined
  submitting: boolean
  onSubmit: (order: number[]) => Promise<void>
}

/** One line of the student's program. `original` is the faulty program's line this row started
 * as (null for a correction inserted as a new line); `current` is the line or correction it
 * holds now. */
type Row = { key: number; original: number | null; current: number }

/** Fix a faulty BFS (FR-5.5; objective 7, ID document §4.4 and Table 1 row 7). The program starts
 * as the faulty version. For each line the student can keep it, replace it with one of the given
 * corrections, move it up or down, or remove it; a correction can also be inserted as a new line,
 * and a removed line put back. Everything is a button or a select, so it works with a keyboard,
 * a screen reader and a single pointer, with no dragging (WCAG 2.1.1, 2.5.7). Nothing typed is
 * ever code: the submission is the fixed program's line and correction ids, in order. Each line
 * keeps its indentation (`white-space: pre-wrap`); a line too long for a 320 px screen wraps rather
 * than scrolling, so no line needs a scroll stop of its own (WCAG 1.4.10).
 *
 * The server marks each position of the program right or wrong, with a reason (a bug left in, the
 * wrong correction, a line in the wrong place). Positions move as soon as the program changes,
 * so the marks are cleared on the first change, as in the Parsons problem.
 *
 * Corrections are offered in the order the content gives them, never sorted by id. The screen
 * doesn't hide which is right: the content must not list the right correction first (or in any
 * telling place), and the ids it carries can be read in the browser's developer tools. A line's
 * indentation is drawn and also given in words ("indent level 2"),
 * in the code, the option labels and the button names, as for the Parsons lines (#142). */
export function FixTheBug({ activity, result, submitting, onSubmit }: FixTheBugProps) {
  const { lines, corrections } = activity.config
  const [rows, setRows] = useState<Row[]>(() =>
    lines.map((line) => ({ key: line.id, original: line.id, current: line.id })),
  )
  const [removed, setRemoved] = useState<number[]>([])
  const [nextKey, setNextKey] = useState(() => Math.max(0, ...lines.map((l) => l.id)) + 1000)
  const [insertId, setInsertId] = useState('')
  const [insertAfter, setInsertAfter] = useState('end')
  const [announcement, setAnnouncement] = useState('')
  const [cleared, setCleared] = useState(false)
  const [prevResult, setPrevResult] = useState(result)
  const baseId = useId()
  const controlId = (key: number | 'add', control = '') => `${baseId}-${key}${control}`

  if (result !== prevResult) {
    setPrevResult(result)
    setCleared(false)
  }

  // Keep focus on the control the student used (or its nearest partner), once React has moved
  // or removed its row.
  const focusNext = useRef('')
  useEffect(() => {
    if (!focusNext.current) return
    document.getElementById(focusNext.current)?.focus()
    focusNext.current = ''
  })

  const byId = new Map<number, CodeLine>([...lines, ...corrections].map((l) => [l.id, l]))
  const disabled = submitting || result?.correct === true
  const parts = cleared ? undefined : result?.parts
  const partAt = new Map(parts?.map((part) => [part.ref, part]))
  const missingParts = parts?.filter((part) => part.ref >= rows.length && !part.correct) ?? []

  function text(id: number): string {
    return byId.get(id)?.text ?? ''
  }

  function changed(message: string) {
    setCleared(true)
    setAnnouncement(message)
  }

  function move(index: number, by: -1 | 1) {
    const to = index + by
    if (to < 0 || to >= rows.length) return
    const next = [...rows]
    const [row] = next.splice(index, 1)
    next.splice(to, 0, row)
    setRows(next)
    // At the top or bottom that button is now disabled, so focus its partner instead.
    const edge = (by < 0 && to === 0) || (by > 0 && to === rows.length - 1)
    focusNext.current = controlId(row.key, edge === by < 0 ? '-down' : '-up')
    changed(`Moved line ${index + 1} to line ${to + 1}.`)
  }

  function replace(index: number, value: number) {
    setRows(rows.map((row, i) => (i === index ? { ...row, current: value } : row)))
    changed(`Line ${index + 1} is now: ${lineName(text(value))}`)
  }

  function remove(index: number) {
    const row = rows[index]
    setRows(rows.filter((_, i) => i !== index))
    if (row.original !== null) setRemoved([...removed, row.original])
    const neighbour = rows[index + 1] ?? rows[index - 1]
    // With no line left, the Insert button is disabled until a correction is chosen, so focus
    // goes to the choice of correction.
    focusNext.current = neighbour ? controlId(neighbour.key, '-change') : `${baseId}-insert`
    changed(`Removed line ${index + 1}.`)
  }

  // `after` is "start", "end" or the key of the row to insert after.
  function insert(lineId: number, after: string, original: number | null) {
    const anchor = rows.findIndex((row) => String(row.key) === after)
    const at = after === 'start' ? 0 : anchor < 0 ? rows.length : anchor + 1
    const row: Row = { key: nextKey, original, current: lineId }
    setNextKey(nextKey + 1)
    setRows([...rows.slice(0, at), row, ...rows.slice(at)])
    if (original !== null) setRemoved(removed.filter((id) => id !== original))
    focusNext.current = controlId(row.key, '-change')
    changed(`Inserted line ${at + 1}: ${lineName(text(lineId))}`)
  }

  // A removed line goes back where it was in the faulty program, as near as the rows allow.
  function putBack(original: number) {
    const home = lines.findIndex((line) => line.id === original)
    const after = rows.findLastIndex((row) => {
      const at = lines.findIndex((line) => line.id === row.original)
      return at >= 0 && at < home
    })
    insert(original, after < 0 ? 'start' : String(rows[after].key), original)
  }

  return (
    <form
      className="grid grid-cols-[minmax(0,1fr)] gap-4"
      onSubmit={(event) => {
        event.preventDefault()
        void onSubmit(rows.map((row) => row.current))
      }}
    >
      <p className="m-0">{activity.config.prompt}</p>
      <p id={`${baseId}-how`} className="m-0 text-sm text-muted-foreground">
        For each line, keep it or replace it with a correction. Move a line that is in the wrong
        place with Up and Down, remove a line that doesn’t belong, or insert a correction as a new
        line.
      </p>
      <p className="visually-hidden" aria-live="polite">
        {announcement}
      </p>
      <ol
        className="m-0 grid min-w-0 list-none grid-cols-[minmax(0,1fr)] gap-2 p-0"
        aria-label="Your fixed program"
      >
        {rows.map((row, index) => {
          const part = partAt.get(index)
          const selectId = controlId(row.key, '-change')
          const markId = `${selectId}-mark`
          const replaced = row.original !== null && row.current !== row.original
          return (
            <li
              key={row.key}
              className={`grid min-w-0 grid-cols-[minmax(0,1fr)] gap-2 rounded border p-2 ${part ? (part.correct ? 'border-success bg-success/10' : 'border-warning bg-warning/10') : replaced || row.original === null ? 'border-primary' : 'border-border'}`}
            >
              <div className="grid min-w-0 grid-cols-[2rem_minmax(0,1fr)] items-start gap-2">
                <span
                  className={`pt-0.5 text-right font-mono text-sm ${part ? 'text-foreground' : 'text-muted-foreground'}`}
                >
                  {index + 1}
                </span>
                <IndentedCode text={text(row.current)} className="text-sm leading-6" />
              </div>
              <div className="flex flex-wrap items-center gap-2 sm:pl-10">
                <label htmlFor={selectId} className="visually-hidden">
                  Line {index + 1}
                </label>
                <select
                  id={selectId}
                  className="w-full min-w-0 rounded border border-primary bg-background px-2 py-1 font-mono text-sm sm:w-auto sm:max-w-full"
                  value={row.current}
                  disabled={disabled}
                  aria-describedby={`${baseId}-how${part ? ` ${markId}` : ''}`}
                  onChange={(event) => replace(index, Number(event.target.value))}
                >
                  {row.original !== null && <option value={row.original}>Keep this line</option>}
                  {corrections.map((correction) => (
                    <option key={correction.id} value={correction.id}>
                      {row.original === null ? 'Correction' : 'Replace with'}:{' '}
                      {lineName(correction.text)}
                    </option>
                  ))}
                </select>
                <Button
                  size="sm"
                  variant="secondary"
                  id={controlId(row.key, '-up')}
                  aria-label={`Move line ${index + 1} up`}
                  disabled={disabled || index === 0}
                  onClick={() => move(index, -1)}
                >
                  Up
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  id={controlId(row.key, '-down')}
                  aria-label={`Move line ${index + 1} down`}
                  disabled={disabled || index === rows.length - 1}
                  onClick={() => move(index, 1)}
                >
                  Down
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  aria-label={`Remove line ${index + 1}`}
                  disabled={disabled}
                  onClick={() => remove(index)}
                >
                  Remove
                </Button>
              </div>
              {part && (
                <p
                  id={markId}
                  className={`m-0 text-sm sm:pl-10 ${part.correct ? 'text-success' : 'text-warning'}`}
                >
                  {part.correct
                    ? 'Correct'
                    : `Check again${part.message ? `: ${part.message}` : ''}`}
                </p>
              )}
            </li>
          )
        })}
      </ol>
      {missingParts.length > 0 && (
        <ul className="m-0 grid list-none gap-1 p-0 text-sm text-warning">
          {missingParts.map((part) => (
            <li key={part.ref}>
              Line {part.ref + 1}: {part.message ?? 'A line is missing here.'}
            </li>
          ))}
        </ul>
      )}

      <fieldset
        className="m-0 grid min-w-0 grid-cols-[minmax(0,1fr)] gap-2 rounded border border-border p-3"
        disabled={disabled}
      >
        <legend className="px-1 font-medium">Insert a correction as a new line</legend>
        <label htmlFor={`${baseId}-insert`} className="text-sm">
          Correction
        </label>
        <select
          id={`${baseId}-insert`}
          className="min-w-0 max-w-full rounded border border-primary bg-background px-2 py-1 font-mono text-sm"
          value={insertId}
          onChange={(event) => setInsertId(event.target.value)}
        >
          <option value="">Choose a correction</option>
          {corrections.map((correction) => (
            <option key={correction.id} value={correction.id}>
              {lineName(correction.text)}
            </option>
          ))}
        </select>
        <label htmlFor={`${baseId}-after`} className="text-sm">
          Where
        </label>
        <select
          id={`${baseId}-after`}
          className="min-w-0 max-w-full rounded border border-primary bg-background px-2 py-1 font-mono text-sm"
          value={
            insertAfter === 'start' || rows.some((row) => String(row.key) === insertAfter)
              ? insertAfter
              : 'end'
          }
          onChange={(event) => setInsertAfter(event.target.value)}
        >
          <option value="start">At the start</option>
          {rows.map((row, index) => (
            <option key={row.key} value={row.key}>
              After line {index + 1}: {lineName(text(row.current))}
            </option>
          ))}
          <option value="end">At the end</option>
        </select>
        <div>
          <Button
            size="sm"
            variant="secondary"
            id={controlId('add')}
            disabled={disabled || insertId === ''}
            onClick={() => {
              insert(Number(insertId), insertAfter, null)
              setInsertId('')
              setInsertAfter('end')
            }}
          >
            Insert line
          </Button>
        </div>
      </fieldset>

      {removed.length > 0 && (
        <section aria-labelledby={`${baseId}-removed`} className="grid gap-2">
          <p id={`${baseId}-removed`} className="m-0 font-medium">
            Removed lines
          </p>
          <ul className="m-0 grid list-none gap-2 p-0">
            {removed.map((lineId) => (
              <li key={lineId} className="flex min-w-0 flex-wrap items-center gap-2">
                <IndentedCode text={text(lineId)} className="min-w-0 text-sm" />
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={disabled}
                  aria-label={`Put back: ${lineName(text(lineId))}`}
                  onClick={() => putBack(lineId)}
                >
                  Put back
                </Button>
              </li>
            ))}
          </ul>
        </section>
      )}
      <div>
        <Button type="submit" loading={submitting} disabled={disabled}>
          Check answer
        </Button>
      </div>
    </form>
  )
}
