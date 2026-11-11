import { useEffect, useRef, useState } from 'react'
import { Alert, Button } from '../../components'
import { fetchActivityHints } from './activities.api.ts'
import type { Hint } from './activities.types.ts'

type HintLadderProps = {
  activityId: number
  disabled?: boolean
  requestHint: (activityId: number) => Promise<Hint>
  loadHints?: (activityId: number) => Promise<readonly Hint[]>
}

/**
 * Shows one server-recorded hint at a time, warning before a support-level hint.
 *
 * Focus (WCAG 2.4.3, #142): the new hint takes focus when it arrives, named by its title
 * ("Hint 2") and described by its text, so it is read once and the student is where the new
 * content is. While a hint loads the button shows its spinner but stays focusable (Button's
 * keepFocusWhileLoading: aria-disabled and aria-busy, not disabled), and after the last hint,
 * when the button goes, focus is already on that hint.
 */
export function HintLadder({
  activityId,
  disabled = false,
  requestHint,
  loadHints = fetchActivityHints,
}: HintLadderProps) {
  const [hints, setHints] = useState<readonly Hint[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingInitial, setLoadingInitial] = useState(true)
  const [loadFailed, setLoadFailed] = useState(false)
  const [confirmingSupport, setConfirmingSupport] = useState(false)
  const newestHint = useRef<HTMLDivElement>(null)
  const focusNewest = useRef(false)

  // Only a hint the student asked for takes focus; hints loaded with the page don't. Runs after
  // every render; the flag is set only once the new hint is in state.
  useEffect(() => {
    if (!focusNewest.current) return
    focusNewest.current = false
    newestHint.current?.focus()
  })

  useEffect(() => {
    let active = true
    loadHints(activityId)
      .then((loaded) => {
        if (active) {
          setHints(loaded)
          setLoadingInitial(false)
          setLoadFailed(false)
        }
      })
      .catch(() => {
        if (active) {
          setLoadFailed(true)
          setLoadingInitial(false)
        }
      })
    return () => {
      active = false
    }
  }, [activityId, loadHints])

  const lastHint = hints.at(-1)
  const hasMore = !loadFailed && !loadingInitial && (lastHint?.hasMore ?? true)

  async function showNextHint() {
    if (loading) return // aria-disabled while loading: the button can be pressed, but does nothing
    if (lastHint?.nextCountsAsSupport && lastHint.level < 3 && !confirmingSupport) {
      setConfirmingSupport(true)
      return
    }
    setLoading(true)
    setError('')
    setConfirmingSupport(false)
    try {
      const hint = await requestHint(activityId)
      focusNewest.current = true
      setHints((current) => [...current, hint])
    } catch {
      setError('We could not load a hint. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section aria-label="Hints" className="grid gap-3">
      {hints.map((hint, index) => (
        <Alert
          key={hint.level}
          ref={index === hints.length - 1 ? newestHint : undefined}
          announce="focus"
          tone="info"
          title={`Hint ${hint.level}`}
        >
          {hint.body}
        </Alert>
      ))}
      {confirmingSupport && (
        <Alert tone="warning" title="The next hint gives a lot away">
          Using it means a later correct answer counts as met with support. Choose “Show next hint”
          again if you want to continue.
        </Alert>
      )}
      {error && <Alert tone="danger">{error}</Alert>}
      {hasMore && (
        <div>
          <Button
            variant="secondary"
            onClick={() => void showNextHint()}
            disabled={disabled}
            // Spinner and aria-busy while the hint loads, but still focusable (not disabled), so
            // focus isn't dropped on the page; presses are ignored meanwhile.
            loading={loading}
            keepFocusWhileLoading
          >
            Show next hint
          </Button>
        </div>
      )}
    </section>
  )
}
