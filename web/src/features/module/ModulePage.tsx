import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { Alert, Button, ProgressBar, Spinner } from '../../components'
import { ActivityView } from '../activities/ActivityPage.tsx'
import { fetchModule, savePosition } from './module.api.ts'
import { SegmentView } from './SegmentView.tsx'

/** /modules/:moduleId — plays a module's segments in order, saves position (FR-2.3, FR-2.5). */
export function ModulePage() {
  const id = Number(useParams().moduleId)
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const query = useQuery({ queryKey: ['module', id], queryFn: () => fetchModule(id) })

  // Drive current index from the fetched position; update locally on navigation.
  const [segmentIndex, setSegmentIndex] = useState<number | null>(null)
  // Which recall question is on screen; null until the student moves, so it starts at the first
  // one they haven't answered yet (FR-2.4).
  const [retrievalIndex, setRetrievalIndex] = useState<number | null>(null)
  const [retrievalChecked, setRetrievalChecked] = useState(false)

  // Saves how far the student has got. The server keeps the furthest segment reached, so only
  // moving forward is saved; stepping back just changes what's on screen.
  const mutation = useMutation({
    mutationFn: (position: number) => savePosition(id, position),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['modules'] })
      void queryClient.invalidateQueries({ queryKey: ['module', id] })
    },
  })
  if (query.isPending) return <Spinner label="Loading module" />
  if (query.isError) return <Alert tone="danger">{query.error.message}</Alert>

  const module = query.data
  const segments = module.segments
  const retrieval = module.retrieval ?? []

  // The recall questions come before the segments. Each is a full activity, with feedback and
  // hints; any checked answer moves the student on, and the server needs one for every question
  // before it saves a position.
  const firstUnanswered = retrieval.findIndex((item) => !item.answered)
  const recallIndex =
    retrievalIndex ?? (firstUnanswered === -1 ? retrieval.length : firstUnanswered)

  if (recallIndex < retrieval.length) {
    const item = retrieval[recallIndex]
    const next = retrieval.findIndex((other, index) => index > recallIndex && !other.answered)
    return (
      <section className="grid max-w-3xl gap-6" aria-label={`Module ${module.number} retrieval`}>
        <div className="grid gap-2">
          <h1 className="text-2xl font-bold">
            Module {module.number} · {module.title}
          </h1>
          <p className="text-sm text-muted-foreground">
            Quick recall · Question {recallIndex + 1} of {retrieval.length}
          </p>
        </div>
        <ActivityView
          key={item.id}
          activityId={item.id}
          heading="h2"
          onResult={() => setRetrievalChecked(true)}
        />
        <div className="flex justify-end">
          <Button
            disabled={!retrievalChecked && !item.answered}
            onClick={() => {
              setRetrievalChecked(false)
              setRetrievalIndex(next === -1 ? retrieval.length : next)
              if (next === -1) void queryClient.invalidateQueries({ queryKey: ['module', id] })
            }}
          >
            {next === -1 ? 'Start module' : 'Next question'}
          </Button>
        </div>
      </section>
    )
  }

  if (segments.length === 0) {
    return (
      <section className="grid gap-6">
        <h1 className="text-2xl font-bold">
          Module {module.number} · {module.title}
        </h1>
        <Alert tone="info">
          {retrieval.length > 0
            ? 'You’ve answered the retrieval questions. Lesson content for this module has not been added yet.'
            : 'This module has no segments yet.'}
        </Alert>
      </section>
    )
  }

  // Initialise from the server's position; clamp to valid range.
  const currentIndex = segmentIndex ?? Math.min(module.currentSegmentPosition, segments.length - 1)
  const segment = segments[currentIndex]
  const isFirst = currentIndex === 0
  const isLast = currentIndex === segments.length - 1
  // The server refuses to move past a segment that isn't done (FR-2.7); say why up front.
  const blocked = segment !== undefined && !segment.done && module.status !== 'complete'

  function handlePrevious() {
    setSegmentIndex(Math.max(0, currentIndex - 1))
  }

  function handleNext() {
    const next = currentIndex + 1
    mutation.mutate(segments[next].position, { onSuccess: () => setSegmentIndex(next) })
  }

  // The last segment was saved when the student reached it, which completed the module; saving it
  // again is harmless and covers a save that failed. Then back to the map, where the next module
  // is now open.
  function handleFinish() {
    mutation.mutate(segments[currentIndex].position, { onSuccess: () => void navigate('/') })
  }

  return (
    <section
      className="grid max-w-3xl gap-6"
      aria-label={`Module ${module.number}: ${module.title}`}
    >
      {/* Header */}
      <div className="grid gap-2">
        <h1 className="text-2xl font-bold">
          Module {module.number} · {module.title}
        </h1>

        {/* Goals (FR-2.3) */}
        {module.goals.length > 0 && (
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="mb-2 font-semibold">By the end of this module you can:</p>
            <ul className="ml-5 list-disc">
              {module.goals.map((goal) => (
                <li key={goal}>{goal}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Progress indicator (FR-2.5, AC5) */}
      <div className="grid gap-2">
        <ProgressBar
          label={`Module ${module.number} progress`}
          value={currentIndex + 1}
          max={segments.length}
          showCount
        />
        <p className="text-sm text-muted-foreground" aria-live="polite">
          Segment {currentIndex + 1} of {segments.length}
        </p>
      </div>

      {/* Current segment */}
      {segment && (
        <SegmentView
          key={segment.id}
          segment={segment}
          onAnswered={() => void queryClient.invalidateQueries({ queryKey: ['module', id] })}
        />
      )}

      {/* Save error */}
      {mutation.isError && (
        <Alert tone="warning" title="Could not save progress">
          {mutation.error.message}
        </Alert>
      )}

      {blocked && (
        <p id="segment-blocked" className="m-0 text-sm text-muted-foreground">
          {segment.kind === 'video'
            ? 'Answer the video’s checkpoints to continue.'
            : 'Answer the activity to continue. A wrong answer still counts.'}
        </p>
      )}

      {/* Navigation */}
      <nav className="flex justify-between" aria-label="Segment navigation">
        <Button
          variant="secondary"
          onClick={handlePrevious}
          disabled={isFirst || mutation.isPending}
        >
          ← Previous
        </Button>
        <Button
          variant={isLast ? 'primary' : 'secondary'}
          onClick={isLast ? handleFinish : handleNext}
          disabled={mutation.isPending || blocked}
          aria-describedby={blocked ? 'segment-blocked' : undefined}
          loading={mutation.isPending}
        >
          {isLast ? 'Finish module' : 'Next →'}
        </Button>
      </nav>
    </section>
  )
}
