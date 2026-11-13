import { useState } from 'react'
import { Button } from '../../components'
import type { AttemptResult, MatchingActivity } from './activities.types.ts'

type MatchingProps = {
  activity: MatchingActivity
  result: AttemptResult | undefined
  submitting: boolean
  onSubmit: (pairs: Record<string, string>) => Promise<void>
  /** False when the prompt is shown beside the question's picture instead (#155). */
  showPrompt?: boolean
  /** The student's last answer, to start from when they come back to the activity (#171). */
  previous?: Record<string, string>
  /** Show the answer only, with no Check answer: an answered mastery item (#144, #171). */
  readOnly?: boolean
}

/** Pair each item on the left with one on the right, using a plain select per item so it works
 * with a keyboard, a screen reader and at 360 px. A left item may be left unmatched; the server
 * marks it wrong. Each item's mark from the last check shows only until the student changes that
 * item, so a mark never points at an answer it wasn't about. */
export function Matching({
  activity,
  result,
  submitting,
  onSubmit,
  showPrompt = true,
  previous,
  readOnly,
}: MatchingProps) {
  // A restored answer is the one its restored result is about, so its marks show (#171).
  const [pairs, setPairs] = useState<Record<string, string>>(previous ?? {})
  const [checked, setChecked] = useState<Record<string, string>>(previous ?? {})
  const disabled = submitting || result?.correct === true || !!readOnly
  const parts = new Map(result?.parts.map((part) => [part.ref, part]))

  return (
    <form
      className="grid gap-4"
      onSubmit={(event) => {
        event.preventDefault()
        // A select set back to its placeholder ("") is a pair not made, as the API counts it.
        const chosen = Object.fromEntries(Object.entries(pairs).filter(([, right]) => right !== ''))
        setChecked(chosen)
        void onSubmit(chosen)
      }}
    >
      {showPrompt && <p className="m-0 font-medium">{activity.config.prompt}</p>}
      <ul className="m-0 grid list-none gap-3 p-0">
        {activity.config.left.map((item, index) => {
          const id = `match-${activity.id}-${item.id}`
          const chosen = pairs[item.id] ?? ''
          const part = result && (checked[item.id] ?? '') === chosen ? parts.get(index) : undefined
          return (
            <li
              key={item.id}
              className={`grid gap-2 rounded border p-3 sm:grid-cols-[1fr_minmax(0,16rem)] sm:items-center ${part ? (part.correct ? 'border-success bg-success/10' : 'border-warning bg-warning/10') : 'border-border'}`}
            >
              <label htmlFor={id}>{item.label}</label>
              <select
                id={id}
                value={chosen}
                disabled={disabled}
                aria-describedby={part ? `${id}-mark` : undefined}
                className="w-full rounded border border-primary bg-background px-2 py-1"
                onChange={(event) =>
                  setPairs((current) => ({ ...current, [item.id]: event.target.value }))
                }
              >
                <option value="">Choose a match</option>
                {activity.config.right.map((choice) => (
                  <option key={choice.id} value={choice.id}>
                    {choice.label}
                  </option>
                ))}
              </select>
              {part && (
                <span
                  id={`${id}-mark`}
                  className={`text-sm sm:col-span-2 ${part.correct ? 'text-success' : 'text-warning'}`}
                >
                  {part.correct
                    ? 'Correct'
                    : `Check again${part.message ? `: ${part.message}` : ''}`}
                </span>
              )}
            </li>
          )
        })}
      </ul>
      {!readOnly && (
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
      )}
    </form>
  )
}
