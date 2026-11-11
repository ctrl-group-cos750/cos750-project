import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router'
import { retryUnlessRefused } from '../../api/retry.ts'
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
  /** h1 on its own page; h2 for a module's recall questions, under the module's title; h3 inside
   * a module segment, under the segment's title. */
  heading?: 'h1' | 'h2' | 'h3'
  /** False inside a module segment, whose own heading already names the question. */
  showTitle?: boolean
  /** Called with each checked answer, e.g. so a module knows the segment is done, or that its
   * recall questions are answered. */
  onResult?: (result: AttemptResult) => void
}

/** One activity with its feedback and hint ladder: the activity page, an activity segment in a
 * module (SegmentView), which keeps the module's own navigation on screen, and a module's recall
 * questions. */
export function ActivityView({ activityId, heading, showTitle, onResult }: ActivityViewProps) {
  const [result, setResult] = useState<AttemptResult>()
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const refreshRewards = useRefreshRewards()
  const query = useQuery({
    queryKey: ['activities', activityId],
    queryFn: () => fetchActivity(activityId),
    retry: retryUnlessRefused, // a locked or missing activity says so at once
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
        showTitle={showTitle}
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
