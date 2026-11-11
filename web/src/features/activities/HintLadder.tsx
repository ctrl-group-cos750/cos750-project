import { useEffect, useState } from 'react'
import { Alert, Button } from '../../components'
import { fetchActivityHints } from './activities.api.ts'
import type { Hint } from './activities.types.ts'

type HintLadderProps = {
  activityId: number
  disabled?: boolean
  /** The student has answered correctly: the hints already shown stay, but no more are offered. */
  solved?: boolean
  requestHint: (activityId: number) => Promise<Hint>
  loadHints?: (activityId: number) => Promise<readonly Hint[]>
}

/** Shows one server-recorded hint at a time, warning before a support-level hint. */
export function HintLadder({
  activityId,
  disabled = false,
  solved = false,
  requestHint,
  loadHints = fetchActivityHints,
}: HintLadderProps) {
  const [hints, setHints] = useState<readonly Hint[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [loadingInitial, setLoadingInitial] = useState(true)
  const [loadFailed, setLoadFailed] = useState(false)
  const [confirmingSupport, setConfirmingSupport] = useState(false)

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
  const hasMore = !solved && !loadFailed && !loadingInitial && (lastHint?.hasMore ?? true)

  async function showNextHint() {
    if (lastHint?.nextCountsAsSupport && lastHint.level < 3 && !confirmingSupport) {
      setConfirmingSupport(true)
      return
    }
    setLoading(true)
    setError('')
    setConfirmingSupport(false)
    try {
      const hint = await requestHint(activityId)
      setHints((current) => [...current, hint])
    } catch {
      setError('We could not load a hint. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <section aria-label="Hints" className="grid gap-3">
      {hints.map((hint) => (
        <Alert key={hint.level} tone="info" title={`Hint ${hint.level}`}>
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
            loading={loading}
          >
            Show next hint
          </Button>
        </div>
      )}
    </section>
  )
}
