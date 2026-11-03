import { useState } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
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
    try {
      const hint = await props.onHint({ activityId: props.activity.id })
      setHints((currentHints) => [...currentHints, nextHint])
    } catch {
      setError('We could not load a hint. Please try again.')
    }
  }

  return (
    <Card classname="border-primary/60">
      <CardHeader>
        <CardTitle classname="text-xl">Checkpoint</CardTitle>
      </CardHeader>

      <CardContent>
        <form className="grid gap-5" onSubmit={handleSubmit}>
          <fieldset disabled={submitting || result?.correct}>
            <legend className="mb-4 font-medium">{props.activity.prompt}</legend>

            <RadioGroup value={selectedOptionId} onValueChange={setSelectedOptionId}>
            {props.activity.options.map((option) => (
              <div key={option.id} classname="flex items-center gap-3">
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
                result.correct
                ? 'border-success bg-success/15'
                : 'border-warning bg-warning/15'
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

        {!result?.correct && (
          <div classname="flex flex-wrap gap-3">
            <Button type="submit" disabled={submitting}>
              {submitting ? 'Check answer...' : 'Check answer'}
            </Button>
            <Button type="button" variant="outline" onClick={handleHint}>
              Show next hint
            </Button>
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
