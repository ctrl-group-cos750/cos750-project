import { useEffect, useRef } from 'react'
import { Alert } from '../../components'
import type { AttemptResult } from './activities.types.ts'

type FeedbackPanelProps = { result: AttemptResult | undefined; partName?: 'line' | 'blank' }

/**
 * Summary of a submission result.
 *
 * Each new result takes keyboard focus (WCAG 2.4.3, #142), because a status message inserted
 * together with its text is often not read. The focused element is the result itself (Alert announce="focus"):
 * a group named by its title and described by the feedback, or named by the feedback alone when
 * that already starts with the title, so a screen reader reads the result once, not a container.
 * It is not also a live region, so a second result in the same place is read once. Tab then
 * carries on to the hints and the module's Next. Focus moves only for a result the student just
 * asked for; a result already there when the panel first renders is left alone, so opening a
 * page never moves focus. "Check answer" stays focusable while checking (Button's
 * keepFocusWhileLoading), so a failed check leaves focus on it.
 */
export function FeedbackPanel({ result }: FeedbackPanelProps) {
  const alert = useRef<HTMLDivElement>(null)
  const shown = useRef(result)

  useEffect(() => {
    if (result === shown.current) return
    shown.current = result
    const element = alert.current
    if (!element) return
    // Focus again even if it already has focus, so the new result is read.
    if (document.activeElement === element) element.blur()
    element.focus()
  }, [result])

  if (!result) return null
  return (
    // The section (a "Submission results" region, as before) is not what takes focus; the result is.
    <section aria-label="Submission results" className="grid gap-3">
      <Alert
        ref={alert}
        announce="focus"
        tone={result.correct ? 'success' : 'warning'}
        title={result.correct ? 'Correct' : 'Not quite'}
      >
        {result.feedback}
      </Alert>
    </section>
  )
}
