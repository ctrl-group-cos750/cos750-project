import { useState } from 'react'
import { Button } from '../../components'
import type { AttemptResult, ParsonsActivity } from './activities.types.ts'

type ParsonsProblemProps = {
  activity: ParsonsActivity
  result: AttemptResult | undefined
  submitting: boolean
  onSubmit: (order: number[]) => Promise<void>
}

type DraggedLine = { id: number; fromAnswer: boolean }

/** A Parsons activity that supports native drag/drop and ArrowUp/ArrowDown line movement. */
export function ParsonsProblem({ activity, result, submitting, onSubmit }: ParsonsProblemProps) {
  const [answerOrder, setAnswerOrder] = useState(() => activity.config.lines.map((line) => line.id))
  const [available, setAvailable] = useState<number[]>([])
  const [dragged, setDragged] = useState<DraggedLine>()
  const [announcement, setAnnouncement] = useState('')
  const lines = new Map(activity.config.lines.map((line) => [line.id, line]))
  const disabled = submitting || result?.correct === true

  function move(lineId: number, destination: number, inAnswer: boolean) {
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
      setAnnouncement(`Removed line ${lineId} from the answer.`)
    } else {
      setAvailable(nextSource)
      setAnswerOrder(nextTarget)
      setAnnouncement(`Added line ${lineId} to position ${destination + 1}.`)
    }
  }

  function reorder(lineId: number, destination: number) {
    const from = answerOrder.indexOf(lineId)
    if (from < 0 || from === destination) return
    const next = [...answerOrder]
    next.splice(from, 1)
    next.splice(destination, 0, lineId)
    setAnswerOrder(next)
    setAnnouncement(`Moved line ${lineId} to position ${destination + 1}.`)
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
      className="grid gap-4"
      onSubmit={(event) => {
        event.preventDefault()
        void onSubmit(answerOrder)
      }}
    >
      <p id="parsons-instructions" className="text-sm text-muted-foreground">
        Drag lines to reorder them. With a line focused, use the Up and Down Arrow keys. Remove a
        distractor with “Remove”.
      </p>
      <p className="visually-hidden" aria-live="polite">
        {announcement}
      </p>
      <ol className="m-0 grid list-none gap-2 p-0" aria-label="Your answer, in order">
        {answerOrder.map((lineId, index) => {
          const line = lines.get(lineId)
          const part = result?.parts.find((item) => item.ref === index)
          if (!line) return null
          return (
            <li
              key={line.id}
              className={`grid grid-cols-[auto_1fr_auto] items-center gap-2 rounded border p-2 ${part ? (part.correct ? 'border-success bg-success/10' : 'border-warning bg-warning/10') : 'border-border'}`}
            >
              <span aria-hidden="true" className="text-muted-foreground">
                {index + 1}
              </span>
              <button
                type="button"
                className="cursor-grab bg-transparent p-1 text-left font-mono text-sm disabled:cursor-not-allowed"
                aria-describedby="parsons-instructions"
                draggable={!disabled}
                onDragStart={() => setDragged({ id: line.id, fromAnswer: true })}
                onDragOver={(event) => event.preventDefault()}
                onDrop={() => handleDrop(index)}
                onKeyDown={(event) => keyboardMove(event, line.id, index)}
                disabled={disabled}
              >
                {line.text}
              </button>
              <Button
                variant="ghost"
                size="sm"
                disabled={disabled}
                onClick={() => move(line.id, available.length, true)}
              >
                Remove
              </Button>
              {part?.message && (
                <span className="col-span-3 text-sm text-warning">{part.message}</span>
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
                    disabled={disabled}
                    draggable={!disabled}
                    onDragStart={() => setDragged({ id: line.id, fromAnswer: false })}
                    onClick={() => move(line.id, answerOrder.length, false)}
                  >
                    Add: <code>{line.text}</code>
                  </Button>
                </li>
              )
            })}
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
