import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router'
import { Alert, Spinner } from '../../components'
import { useRefreshRewards } from '../rewards/hooks.ts'
import {
  fetchActivity,
  fetchActivityHints,
  requestActivityHint,
  submitActivityAttempt,
} from './activities.api.ts'
import { ActivityRenderer } from './ActivityRenderer.tsx'
import type { AttemptResult, Submission } from './activities.types.ts'

type ActivityViewProps = {
  activityId: number
  /** h1 on its own page; h3 inside a module segment, under the segment's title. */
  heading?: 'h1' | 'h3'
  /** Called with each checked answer, e.g. so a module knows the segment is done. */
  onResult?: (result: AttemptResult) => void
}

/** One activity with its feedback and hint ladder: the activity page, and an activity segment in
 * a module (SegmentView), which keeps the module's own navigation on screen. */
export function ActivityView({ activityId, heading, onResult }: ActivityViewProps) {
  const [result, setResult] = useState<AttemptResult>()
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const refreshRewards = useRefreshRewards()
  const query = useQuery({
    queryKey: ['activities', activityId],
    queryFn: () => fetchActivity(activityId),
  })

  if (query.isPending) return <Spinner label="Loading activity" />
  if (query.isError) return <Alert tone="danger">{query.error.message}</Alert>

  async function submit(submitted: Submission) {
    setSubmitting(true)
    setSubmitError('')
    try {
      const nextResult = await submitActivityAttempt(activityId, submitted)
      setResult(nextResult)
      onResult?.(nextResult)
      if (nextResult.correct) refreshRewards()
    } catch (error) {
      setSubmitError(
        error instanceof Error
          ? error.message
          : 'We could not check your answer. Please try again.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      {submitError && (
        <Alert tone="danger" title="Try again">
          {submitError}
        </Alert>
      )}
      <ActivityRenderer
        activity={query.data}
        result={result}
        submitting={submitting}
        onSubmit={submit}
        requestHint={requestActivityHint}
        loadHints={fetchActivityHints}
        heading={heading}
      />
    </>
  )
}

/** /activities/:activityId — a standalone activity. */
export function ActivityPage() {
  const activityId = Number(useParams().activityId)
  const validActivityId = Number.isInteger(activityId) && activityId > 0

  if (!validActivityId)
    return <Alert tone="danger">The activity identifier must be a positive number.</Alert>

  return <ActivityView key={activityId} activityId={activityId} />
}
