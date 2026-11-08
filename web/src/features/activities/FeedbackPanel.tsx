import { Alert } from '../../components'
import type { AttemptResult } from './activities.types.ts'

type FeedbackPanelProps = { result: AttemptResult | undefined; partName?: 'line' | 'blank' }

/** Summary of submission result. */
export function FeedbackPanel({ result }: FeedbackPanelProps) {
  if (!result) return null
  return (
    <section aria-label="Submission results" className="grid gap-3">
      <Alert
        tone={result.correct ? 'success' : 'warning'}
        title={result.correct ? 'Correct' : 'Not quite'}
      >
        {result.feedback}
      </Alert>
    </section>
  )
}
