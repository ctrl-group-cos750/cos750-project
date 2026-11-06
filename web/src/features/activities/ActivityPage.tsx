import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router'
import { Alert, Spinner } from '../../components'
import { useRefreshRewards } from '../rewards/hooks.ts'
import { fetchActivity, requestActivityHint, submitActivityAttempt } from './activities.api.ts'
import { ActivityRenderer } from './ActivityRenderer.tsx'
import type { AttemptResult } from './activities.types.ts'

/** /activities/:activityId — a standalone code activity. */
export function ActivityPage() {
  const activityId = Number(useParams().activityId)
  const validActivityId = Number.isInteger(activityId) && activityId > 0
  const [result, setResult] = useState<AttemptResult>()
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const refreshRewards = useRefreshRewards()
  const query = useQuery({
    queryKey: ['activities', activityId],
    queryFn: () => fetchActivity(activityId),
    enabled: validActivityId,
  })

  if (!validActivityId)
    return <Alert tone="danger">The activity identifier must be a positive number.</Alert>
  if (query.isPending) return <Spinner label="Loading activity" />
  if (query.isError) return <Alert tone="danger">{query.error.message}</Alert>

  async function submit(submitted: { order: number[] } | { answers: Record<number, string> }) {
    setSubmitting(true)
    setSubmitError('')
    try {
      const nextResult = await submitActivityAttempt(activityId, submitted)
      setResult(nextResult)
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
        key={query.data.id}
        activity={query.data}
        result={result}
        submitting={submitting}
        onSubmit={submit}
        requestHint={requestActivityHint}
      />
    </>
  )
}
