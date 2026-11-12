import { useState } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { refusalMessage } from '../../api/client.ts'
import type { AttemptInput, AttemptResult, Hint, MultipleChoiceActivity } from './video.types.ts'

type CheckpointQuestionProps = {
  activity: MultipleChoiceActivity
  onAttempt: (input: AttemptInput) => Promise<AttemptResult>
  onHint: (input: { activityId: number }) => Promise<Hint>
  onPassed: () => void
}

/** The question at a checkpoint: answer, get the server's feedback, retry, and climb the hint
 * ladder one level at a time (FR-3.4, FR-4.4). `onPassed` runs when the student chooses to resume
 * after a correct answer. */
export function CheckpointQuestion(props: CheckpointQuestionProps) {
  const [selectedOptionId, setSelectedOptionId] = useState('')
  const [result, setResult] = useState<AttemptResult>()
  const [hints, setHints] = useState<readonly Hint[]>([])
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [confirmingSupport, setConfirmingSupport] = useState(false)
  const lastHint = hints.at(-1)
  const moreHints = lastHint?.hasMore ?? true

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
    } catch (failure) {
      setError(refusalMessage(failure, 'We could not check your answer. Please try again.'))
    } finally {
      setSubmitting(false)
    }
  }

  async function handleHint() {
    // Hint 3 makes this objective count as "met with support": say so before it (ID doc §7.4).
    // After that, hint 4 changes nothing, so no second warning.
    if (lastHint?.nextCountsAsSupport && lastHint.level < 3 && !confirmingSupport) {
      setConfirmingSupport(true)
      return
    }
    setConfirmingSupport(false)
    try {
      const hint = await props.onHint({ activityId: props.activity.id })
      setHints((currentHints) => [...currentHints, hint])
    } catch (failure) {
      setError(refusalMessage(failure, 'We could not load a hint. Please try again.'))
    }
  }

  return (
    <Card className="border-primary/60">
      <CardContent>
        <form className="grid gap-5" onSubmit={handleSubmit}>
          <fieldset disabled={submitting || result?.correct}>
            <legend className="mb-4 font-medium">{props.activity.prompt}</legend>

            <RadioGroup value={selectedOptionId} onValueChange={setSelectedOptionId}>
              {props.activity.options.map((option) => (
                <div key={option.id} className="flex items-center gap-3">
                  <RadioGroupItem value={option.id} id={option.id} />
                  <Label htmlFor={option.id}>{option.label}</Label>
                </div>
              ))}
            </RadioGroup>
          </fieldset>

          {error && (
            <Alert variant="destructive">
              <AlertTitle>Try again</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {result && (
            <Alert
              className={
                result.correct ? 'border-success bg-success/15' : 'border-warning bg-warning/15'
              }
            >
              <AlertTitle>{result.correct ? 'Correct' : 'Not quite'}</AlertTitle>
              <AlertDescription>{result.feedback}</AlertDescription>
            </Alert>
          )}

          {hints.map((hint) => (
            <Alert key={hint.level}>
              <AlertTitle>Hint {hint.level}</AlertTitle>
              <AlertDescription>{hint.body}</AlertDescription>
            </Alert>
          ))}

          {confirmingSupport && (
            <Alert>
              <AlertTitle>The next hint gives a lot away</AlertTitle>
              <AlertDescription>
                If you use it, this objective counts as &quot;met with support&quot; instead of
                &quot;met independently&quot;. Press &quot;Show next hint&quot; again to see it.
              </AlertDescription>
            </Alert>
          )}

          {!result?.correct && (
            <div className="flex flex-wrap gap-3">
              <Button type="submit" disabled={submitting}>
                {submitting ? 'Checking...' : 'Check answer'}
              </Button>
              {moreHints && (
                <Button type="button" variant="outline" onClick={handleHint}>
                  Show next hint
                </Button>
              )}
            </div>
          )}

          {result?.correct && (
            <Button type="button" onClick={props.onPassed}>
              Resume video
            </Button>
          )}
        </form>
      </CardContent>
    </Card>
  )
}
