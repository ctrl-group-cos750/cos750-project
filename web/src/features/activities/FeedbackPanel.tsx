import { useEffect, useRef } from 'react'
import { Alert } from '../../components'
import type { AttemptResult } from './activities.types.ts'

type FeedbackPanelProps = { result: AttemptResult | undefined; partName?: 'line' | 'blank' }

/**
 * Summary of a submission result.
 *
 * Each new result takes keyboard focus (WCAG 2.4.3, #142): "Check answer" is disabled while the
 * answer is checked, which drops focus on the page, and a status message inserted together with
 * its text is often not read. Focusing the panel reads it, and Tab carries on to the hints and the
 * module's Next. This is the APG practice of moving focus to content that appears in response to
 * the user's own action; a result already there when the panel first renders is left alone, so
 * opening a page never moves focus.
 */
export function FeedbackPanel({ result }: FeedbackPanelProps) {
  const panel = useRef<HTMLElement>(null)
  const shown = useRef(result)

  useEffect(() => {
    if (result === shown.current) return
    shown.current = result
    panel.current?.focus()
  }, [result])

  if (!result) return null
  return (
    <section ref={panel} tabIndex={-1} aria-label="Submission results" className="grid gap-3">
      <Alert
        tone={result.correct ? 'success' : 'warning'}
        title={result.correct ? 'Correct' : 'Not quite'}
      >
        {result.feedback}
      </Alert>
    </section>
  )
}
