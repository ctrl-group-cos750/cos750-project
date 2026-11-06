import { Alert } from '../../components'
import type { AttemptResult } from './activities.types.ts'

type FeedbackPanelProps = { result: AttemptResult | undefined; partName: 'line' | 'blank' }

/** Summary plus the result for each checked line or blank. */
export function FeedbackPanel({ result, partName }: FeedbackPanelProps) {
  if (!result) return null
  return (
    <section aria-label="Submission results" className="grid gap-3">
      <Alert
        tone={result.correct ? 'success' : 'warning'}
        title={result.correct ? 'Correct' : 'Not quite'}
      >
        {result.feedback}
      </Alert>
      <ul className="m-0 grid list-none gap-2 p-0" aria-label={`Result for each ${partName}`}>
        {result.parts.map((part) => (
          <li
            key={part.ref}
            className={`rounded border px-3 py-2 ${part.correct ? 'border-success bg-success/10' : 'border-warning bg-warning/10'}`}
          >
            <strong>{part.correct ? 'Correct' : 'Check again'}:</strong> {partName}{' '}
            {part.ref + (partName === 'line' ? 1 : 0)}
            {part.message && ` — ${part.message}`}
          </li>
        ))}
      </ul>
    </section>
  )
}
