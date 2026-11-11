import { useId, useState } from 'react'
import { Button } from '../../components'
import type { AttemptResult, MultipleChoiceActivity } from './activities.types.ts'

type MultipleChoiceProps = {
  activity: MultipleChoiceActivity
  result: AttemptResult | undefined
  submitting: boolean
  onSubmit: (selected: string) => Promise<void>
}

/** One question, one answer from a list of options. The server says why a wrong option is wrong
 * (FR-4.2); the page's feedback panel shows it. */
export function MultipleChoice({ activity, result, submitting, onSubmit }: MultipleChoiceProps) {
  const [selected, setSelected] = useState('')
  const [missing, setMissing] = useState(false)
  const name = useId()
  const disabled = submitting || result?.correct === true

  return (
    <form
      className="grid gap-4"
      onSubmit={(event) => {
        event.preventDefault()
        if (!selected) {
          setMissing(true)
          return
        }
        void onSubmit(selected)
      }}
    >
      <fieldset className="m-0 grid gap-2 border-0 p-0" disabled={disabled}>
        <legend className="mb-2 font-medium">{activity.config.prompt}</legend>
        {activity.config.options.map((option) => (
          <label
            key={option.id}
            className="flex cursor-pointer items-start gap-3 rounded border border-border p-3 has-[:checked]:border-primary"
          >
            <input
              type="radio"
              name={name}
              value={option.id}
              checked={selected === option.id}
              className="mt-1"
              onChange={() => {
                setSelected(option.id)
                setMissing(false)
              }}
            />
            <span>{option.label}</span>
          </label>
        ))}
      </fieldset>
      {missing && (
        <p className="m-0 text-sm text-warning" role="alert">
          Choose an answer before checking it.
        </p>
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
