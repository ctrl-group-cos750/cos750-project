import { useState } from 'react'
import { Alert, Button } from '../../components'
import type {
  AttemptInput,
  AttemptResult,
  Hint,
  MultipleChoiceActivity,
} from './video.types.ts'

type CheckpointQuestionProps = {
  activity: MultipleChoiceActivity
  onAttempt: (input: AttemptInput) => Promise<AttemptResult>
  onHint: (input: { activityId: number }) => Promise<Hint>
  onPassed: () => void
}

export function CheckpointQuestion(props: CheckpointQuestionProps) {
  const [selectedOptionId, setSelectedOptionId] = useState('')
  const [result, setResult] = useState<AttemptResult>()
  const [hints, setHints] = useState<readonly Hint[]>([])
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedOptionId) {
      setError('Choose an answer before checking it.')
      return
    }

    setSubmitting(true)
    setError('')
    try {
      const nextResult = await props.onAttempt({
        activityId: props.activity.id,
        answer: { selectedOptionId },
      })
      setResult(nextResult)
    } catch {
      setError('We could not check your answer. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  async function handleHint() {
    setError('')
    try {
      const nextHint = await props.onHint({ activityId: props.activity.id })
      setHints((currentHints) => [...currentHints, nextHint])
    } catch {
      setError('We could not load a hint. Please try again.')
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <fieldset disabled={submitting || result?.correct)>
        <legend>{props.activity.prompt}</legend>
        {props.activity.options.map((option) => (
          <label key={option.id}>
            <input
              type="radio"
              name={`activity-${props.activity.id}`}
              value={option.id}
              checked={selectedOptionId === option.id}
              onChange={(event) => setSelectedOptionId(event.target.value)}
            />
            {option.label}
          </label>
        ))}
      </fieldset>

      {error && <Alert tone="danger">{error}</Alert>}

      {result && (
        <Alert tone={result.correct ? 'success' : 'warning'} title={result.correct ? 'Correct' : 'Try again'}>
          {result.feedback}
        </Alert>
      )}

      {hints.map((hint) => (
        <Alert key={hint.level} tone="info" title={`Hint ${hint.level}`}>
          {hint.body}
        </Alert>
      ))}

      {!result?.correct && {
        <>
          <Button type="submit" loading={submitting}>
            Check answer
          </Button>
          <Button variant="ghost" onClick={handleHint}>
            Show next hint
          </Button>
        </>
      )}

      {result?.correct && <Button onClick={props.onPassed}>Resume video</Button>}
    </form>
  )
}
