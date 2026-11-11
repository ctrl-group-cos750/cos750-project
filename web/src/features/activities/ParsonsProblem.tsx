import { useEffect, useRef, useState } from 'react'
import { Button } from '../../components'
import type { AttemptResult, ParsonsActivity } from './activities.types.ts'
import { indentLabel, lineName } from './codeLines.ts'

type ParsonsProblemProps = {
  activity: ParsonsActivity
  result: AttemptResult | undefined
  submitting: boolean
  onSubmit: (order: number[]) => Promise<void>
}

type DraggedLine = { id: number; fromAnswer: boolean }

/** Where keyboard focus goes after a line changes list, so it isn't dropped on the page (2.4.3). */
type FocusTarget = { list: 'answer' | 'available'; id: number }

/**
 * One line of code with its indentation kept (#140). The indentation is drawn as padding of one
 * character width per leading space, so a line too long for a narrow screen wraps with a hanging
 * indent at its own level: the wrapped part never reads as a line at a shallower level, and the
 * page doesn't scroll sideways at 320 px (WCAG 1.4.10). Below 30rem each space is half a character
 * wide, which keeps every level distinct while leaving room for the code.
 *
 * A screen reader skips leading spaces, so the indentation is also given in words after the code,
 * visually hidden ("(indent level 2)"), and a screen-reader user gets what a sighted student sees
 * (#142 review). `data-indent` holds the number of spaces.
 */
export function CodeLine({ text }: { text: string }) {
  const code = text.trimStart()
  const indent = text.length - code.length
  const level = indentLabel(text)
  return (
    <code
      data-indent={indent}
      className="block whitespace-pre-wrap [overflow-wrap:anywhere] [padding-inline-start:calc(var(--indent)*1ch)] max-[30rem]:[padding-inline-start:calc(var(--indent)*0.5ch)]"
      style={{ '--indent': indent } as React.CSSProperties}
    >
      {code}
      {/* The space is a text node of its own: a screen reader keeps it, an edge space inside the
          hidden span may be dropped. At the end of a line it is invisible. */}
      {level && ' '}
      {level && <span className="visually-hidden">({level})</span>}
    </code>
  )
}

/**
 * A Parsons activity. Lines can be reordered by dragging, with the Up and Down Arrow keys on a
 * focused line, or with each line's move-up and move-down buttons: the buttons are the
 * single-pointer alternative to dragging for mouse and touch users (WCAG 2.2 SC 2.5.7), and
 * every control is at least 24 by 24 px (SC 2.5.8).
 */
export function ParsonsProblem({ activity, result, submitting, onSubmit }: ParsonsProblemProps) {
  const [answerOrder, setAnswerOrder] = useState(() => activity.config.lines.map((line) => line.id))
  const [available, setAvailable] = useState<number[]>([])
  const [dragged, setDragged] = useState<DraggedLine>()
  const [announcement, setAnnouncement] = useState('')
  const [cleared, setCleared] = useState(false)
  const [prevResult, setPrevResult] = useState(result)
  const formRef = useRef<HTMLFormElement>(null)
  const focusTarget = useRef<FocusTarget | null>(null)

  // After a line moves between the answer and the available lines its button is a new element,
  // so put focus on it in its new place. Only set by a student's action, never on first render.
  useEffect(() => {
    const target = focusTarget.current
    if (!target) return
    focusTarget.current = null
    formRef.current
      ?.querySelector<HTMLElement>(`[data-list="${target.list}"][data-line="${target.id}"]`)
      ?.focus()
  })

  if (result !== prevResult) {
    setPrevResult(result)
    setCleared(false)
  }

  const lines = new Map(activity.config.lines.map((line) => [line.id, line]))
  const disabled = submitting || result?.correct === true
  // How a line is announced after a move: its code, which is what the student sees (the id isn't).
  const said = (lineId: number) => {
    const line = lines.get(lineId)
    return line ? lineName(line.text) : `line ${lineId}`
  }
  const checkedParts = cleared ? undefined : result?.parts

  function move(lineId: number, destination: number, inAnswer: boolean) {
    setCleared(true)
    const source = inAnswer ? answerOrder : available
    const target = inAnswer ? available : answerOrder
    const from = source.indexOf(lineId)
    if (from < 0) return
    const nextSource = source.filter((id) => id !== lineId)
    const nextTarget = [...target]
    nextTarget.splice(Math.max(0, Math.min(destination, nextTarget.length)), 0, lineId)
    if (inAnswer) {
      setAnswerOrder(nextSource)
      setAvailable(nextTarget)
      setAnnouncement(`Removed ${said(lineId)} from the answer.`)
      focusTarget.current = { list: 'available', id: lineId }
    } else {
      setAvailable(nextSource)
      setAnswerOrder(nextTarget)
      setAnnouncement(`Added ${said(lineId)} at position ${destination + 1}.`)
      // Stay in the available lines while there are more to add; then go to the line added.
      const nextAvailable = nextSource[Math.min(from, nextSource.length - 1)]
      focusTarget.current =
        nextAvailable === undefined
          ? { list: 'answer', id: lineId }
          : { list: 'available', id: nextAvailable }
    }
  }

  function reorder(lineId: number, destination: number) {
    const from = answerOrder.indexOf(lineId)
    if (from < 0 || from === destination) return
    setCleared(true)
    const next = [...answerOrder]
    next.splice(from, 1)
    next.splice(destination, 0, lineId)
    setAnswerOrder(next)
    setAnnouncement(`Moved ${said(lineId)} to position ${destination + 1}.`)
  }

  function handleDrop(destination: number) {
    if (!dragged) return
    if (dragged.fromAnswer) reorder(dragged.id, destination)
    else move(dragged.id, destination, false)
    setDragged(undefined)
  }

  function keyboardMove(
    event: React.KeyboardEvent<HTMLButtonElement>,
    lineId: number,
    index: number,
  ) {
    if (event.key === 'ArrowUp' && index > 0) {
      event.preventDefault()
      reorder(lineId, index - 1)
    }
    if (event.key === 'ArrowDown' && index < answerOrder.length - 1) {
      event.preventDefault()
      reorder(lineId, index + 1)
    }
  }

  return (
    <form
      ref={formRef}
      className="grid min-w-0 gap-4"
      onSubmit={(event) => {
        event.preventDefault()
        void onSubmit(answerOrder)
      }}
    >
      <p id="parsons-instructions" className="text-sm text-muted-foreground">
        Put the lines in order: drag them, or use the ↑ and ↓ buttons. With a line focused, the Up
        and Down Arrow keys move it too. Remove a distractor with “Remove”.
      </p>
      <p className="visually-hidden" aria-live="polite">
        {announcement}
      </p>
      <ol className="m-0 grid list-none gap-2 p-0" aria-label="Your answer, in order">
        {answerOrder.map((lineId, index) => {
          const line = lines.get(lineId)
          const part = checkedParts?.find((item) => item.ref === index)
          if (!line) return null
          return (
            <li
              key={line.id}
              className={`flex flex-wrap items-center gap-2 rounded border p-2 ${part ? (part.correct ? 'border-success bg-success/10' : 'border-warning bg-warning/10') : 'border-border'}`}
            >
              {/* The number and the code stay on one row; on a narrow screen the buttons wrap
                  below them. */}
              <span className="flex min-w-0 flex-[1_1_16rem] items-center gap-2">
                <span aria-hidden="true" className="w-6 shrink-0 text-right text-muted-foreground">
                  {index + 1}
                </span>
                <button
                  type="button"
                  data-list="answer"
                  data-line={line.id}
                  className="min-h-9 min-w-0 flex-1 cursor-grab bg-transparent p-1 text-left font-mono text-sm disabled:cursor-not-allowed"
                  aria-describedby="parsons-instructions"
                  draggable={!disabled}
                  onDragStart={() => setDragged({ id: line.id, fromAnswer: true })}
                  onDragOver={(event) => event.preventDefault()}
                  onDrop={() => handleDrop(index)}
                  onKeyDown={(event) => keyboardMove(event, line.id, index)}
                  disabled={disabled}
                >
                  <CodeLine text={line.text} />
                </button>
              </span>
              <span className="ml-auto flex shrink-0 gap-1">
                {/* aria-disabled, not disabled, at the ends of the list: a button that becomes
                    disabled while focused drops keyboard focus on the page. */}
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={disabled}
                  aria-disabled={index === 0 || undefined}
                  onClick={() => index > 0 && reorder(line.id, index - 1)}
                >
                  <span aria-hidden="true">↑</span>
                  <span className="visually-hidden">Move {lineName(line.text)} up</span>
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={disabled}
                  aria-disabled={index === answerOrder.length - 1 || undefined}
                  onClick={() => index < answerOrder.length - 1 && reorder(line.id, index + 1)}
                >
                  <span aria-hidden="true">↓</span>
                  <span className="visually-hidden">Move {lineName(line.text)} down</span>
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={disabled}
                  onClick={() => move(line.id, available.length, true)}
                >
                  Remove <span className="visually-hidden">{lineName(line.text)}</span>
                </Button>
              </span>
              {part?.message && (
                <span className="basis-full text-sm text-warning">{part.message}</span>
              )}
            </li>
          )
        })}
      </ol>

      {available.length > 0 && (
        <section aria-label="Available lines" className="grid gap-2">
          <h2 className="text-lg">Available lines</h2>
          <ul className="m-0 grid list-none gap-2 p-0">
            {available.map((lineId) => {
              const line = lines.get(lineId)
              if (!line) return null
              return (
                <li key={line.id}>
                  <Button
                    variant="secondary"
                    className="max-w-full text-left"
                    // The Button's own padding is for one-line labels; a wrapped code line needs room.
                    style={{ paddingBlock: 'var(--space-2)', justifyContent: 'flex-start' }}
                    data-list="available"
                    data-line={line.id}
                    disabled={disabled}
                    draggable={!disabled}
                    onDragStart={() => setDragged({ id: line.id, fromAnswer: false })}
                    onClick={() => move(line.id, answerOrder.length, false)}
                  >
                    <span className="shrink-0">Add:</span>{' '}
                    <span className="min-w-0">
                      <CodeLine text={line.text} />
                    </span>
                  </Button>
                </li>
              )
            })}
          </ul>
        </section>
      )}
      <div>
        {/* Focusable while the answer is checked, so a failed check leaves focus here and a
            result can take it from here (WCAG 2.4.3). */}
        <Button
          type="submit"
          loading={submitting}
          keepFocusWhileLoading
          disabled={result?.correct === true}
        >
          Check answer
        </Button>
      </div>
    </form>
  )
}
