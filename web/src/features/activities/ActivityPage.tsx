import { useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router'
import { buttonVariants } from '@/components/ui/button-variants'
import { ApiError } from '../../api/client.ts'
import { retryUnlessRefused } from '../../api/retry.ts'
import { Alert, Spinner } from '../../components'
import { BackLink } from '../../components/BackLink.tsx'
import { ProgressPanel } from '../progress/ProgressPanel.tsx'
import { useRefreshRewards } from '../rewards/hooks.ts'
import {
  fetchActivity,
  fetchActivityHints,
  requestActivityHint,
  submitActivityAttempt,
} from './activities.api.ts'
import { ActivityRenderer } from './ActivityRenderer.tsx'
import type { AttemptResult, LastAttempt, Submission } from './activities.types.ts'

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
  /** An optional bonus quest (FR-8.3). */
  bonus?: boolean
}

/** One activity with its feedback and hint ladder: the activity page, an activity segment in a
 * module (SegmentView), which keeps the module's own navigation on screen, and a module's recall
 * questions. */
export function ActivityView({
  activityId,
  heading,
  showTitle,
  onResult,
  bonus,
}: ActivityViewProps) {
  const [result, setResult] = useState<AttemptResult>()
  const [submitting, setSubmitting] = useState(false)
  // Set synchronously, so a second Enter that lands before React re-renders the busy button
  // doesn't send the same answer twice.
  const inFlight = useRef(false)
  const [submitError, setSubmitError] = useState('')
  const refreshRewards = useRefreshRewards()
  const queryClient = useQueryClient()
  const query = useQuery({
    queryKey: ['activities', activityId],
    queryFn: () => fetchActivity(activityId),
    retry: retryUnlessRefused, // a locked or missing activity says so at once
  })
  // The answer the student gave last time, kept as it was on the first load (#171). A refetch (on
  // focus, or after an answer) brings a new copy, which mustn't count as a new result: that would
  // move focus to it (FeedbackPanel) and reset the control. Null until the activity has loaded.
  const [restored, setRestored] = useState<LastAttempt | undefined | null>(null)
  if (query.data && restored === null) setRestored(query.data.lastAttempt ?? undefined)

  if (query.isPending || (query.data && restored === null))
    return <Spinner label="Loading activity" />
  if (query.isError) return <NotAvailable error={query.error} heading={heading} />

  async function submit(submitted: Submission) {
    if (inFlight.current) return
    inFlight.current = true
    setSubmitting(true)
    setSubmitError('')
    try {
      const nextResult = await submitActivityAttempt(activityId, submitted)
      setResult(nextResult)
      onResult?.(nextResult)
      // After every answer, not only a correct one: a withheld (mastery check) answer may finish
      // the check (#144), and on a review path a wrong answer can still meet the objective, which
      // is judged on all its parts, and earn its badges (13 Nov audit). They are announced at once.
      refreshRewards()
      // The next time it is shown (Previous, a refresh), the server has this answer: it comes back
      // with the answer and its result (#171), and once solved or answered for good, with no hints
      // offered (#158, #144). After every answer, so a wrong one comes back too.
      void queryClient.invalidateQueries({ queryKey: ['activities', activityId] })
    } catch (error) {
      setSubmitError(
        error instanceof Error
          ? error.message
          : 'We could not check your answer. Please try again.',
      )
    } finally {
      inFlight.current = false
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
        bonus={bonus}
        activity={query.data}
        result={result ?? restored?.result}
        previous={restored?.submitted}
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

/** Why an activity or video can't be shown, in the API's words: not open yet (403, its module is
 * locked or its review path closed), no longer in the course (404), or a failure. Offers the way
 * back to the module map rather than a spinner that never ends. */
export function NotAvailable({
  error,
  heading: Heading = 'h1',
  title = 'This activity isn’t available',
}: {
  error: Error
  /** The level of the "isn't available" heading, as for the activity's own title. */
  heading?: 'h1' | 'h2' | 'h3'
  /** The heading's words, e.g. "This video isn't available". */
  title?: string
}) {
  const refused = error instanceof ApiError && (error.status === 403 || error.status === 404)
  if (!refused) return <Alert tone="danger">{error.message}</Alert>
  return (
    <div className="grid justify-items-start gap-3">
      <Heading className="text-xl font-semibold">{title}</Heading>
      <Alert tone="info">{error.message}</Alert>
      <Link to="/" className={buttonVariants({ variant: 'ghost', size: 'sm' })}>
        Back to your modules
      </Link>
    </div>
  )
}

/** /activities/:activityId — a standalone activity. */
export function ActivityPage() {
  const activityId = Number(useParams().activityId)
  const validActivityId = Number.isInteger(activityId) && activityId > 0

  if (!validActivityId)
    return <Alert tone="danger">The activity identifier must be a positive number.</Alert>

  // Opened from a review path's step: the way back to the path (#146); from anywhere else (a
  // bookmark, a link in a module's text), back to the modules. At the top, where a back link is
  // looked for, in the same centred column as a module.
  // The progress panel (#214) beside it on wide screens, under it on narrow ones.
  return (
    <div className="grid w-full items-start gap-6 lg:grid-cols-[minmax(0,1fr)_19rem] lg:gap-8">
      <div className="mx-auto grid w-full max-w-3xl justify-items-start gap-4">
        <BackLink fallback={{ backTo: '/', backLabel: 'Your modules' }} />
        <div className="w-full">
          <ActivityView key={activityId} activityId={activityId} />
        </div>
        <div className="w-full">
          <ProgressPanel placement="below" />
        </div>
      </div>
      <ProgressPanel placement="beside" />
    </div>
  )
}
