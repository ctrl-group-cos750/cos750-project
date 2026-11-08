import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { Alert, Button, ProgressBar, Spinner } from '../../components'
import { fetchModule, savePosition, submitRetrieval } from './module.api.ts'
import { SegmentView } from './SegmentView.tsx'

/** /modules/:moduleId — plays a module's segments in order, saves position (FR-2.3, FR-2.5). */
export function ModulePage() {
  const id = Number(useParams().moduleId)
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const query = useQuery({ queryKey: ['module', id], queryFn: () => fetchModule(id) })

  // Drive current index from the fetched position; update locally on navigation.
  const [segmentIndex, setSegmentIndex] = useState<number | null>(null)
  const [retrievalIndex, setRetrievalIndex] = useState(0)
  const [selected, setSelected] = useState('')
  const [retrievalResult, setRetrievalResult] = useState<{
    correct: boolean
    feedback: string
  } | null>(null)

  // Saves how far the student has got. The server keeps the furthest segment reached, so only
  // moving forward is saved; stepping back just changes what's on screen.
  const mutation = useMutation({
    mutationFn: (position: number) => savePosition(id, position),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['modules'] })
      void queryClient.invalidateQueries({ queryKey: ['module', id] })
    },
  })
  const retrievalMutation = useMutation({
    mutationFn: () => submitRetrieval(query.data!.retrieval[retrievalIndex].id, selected),
    onSuccess: setRetrievalResult,
  })

  if (query.isPending) return <Spinner label="Loading module" />
  if (query.isError) return <Alert tone="danger">{query.error.message}</Alert>

  const module = query.data
  const segments = module.segments
  const retrieval = module.retrieval ?? []

  if (retrievalIndex < retrieval.length) {
    const item = retrieval[retrievalIndex]
    return (
      <section className="grid max-w-3xl gap-6" aria-label={`Module ${module.number} retrieval`}>
        <div className="grid gap-2">
          <h1 className="text-2xl font-bold">
            Module {module.number} · {module.title}
          </h1>
          <p className="text-sm text-muted-foreground">
            Quick recall · Question {retrievalIndex + 1} of {retrieval.length}
          </p>
        </div>
        <fieldset className="grid gap-3" disabled={retrievalResult !== null}>
          <legend className="mb-3 text-lg font-semibold">{item.prompt}</legend>
          {item.options.map((option) => (
            <label
              key={option.id}
              className="flex cursor-pointer items-start gap-3 rounded-md border border-border p-3"
            >
              <input
                type="radio"
                name={`retrieval-${item.id}`}
                value={option.id}
                checked={selected === option.id}
                onChange={() => setSelected(option.id)}
              />
              <span>{option.label}</span>
            </label>
          ))}
        </fieldset>
        {retrievalResult && (
          <Alert
            tone={retrievalResult.correct ? 'success' : 'info'}
            title={retrievalResult.correct ? 'Correct' : 'Review'}
          >
            {retrievalResult.feedback}
          </Alert>
        )}
        {retrievalMutation.isError && (
          <Alert tone="danger">{retrievalMutation.error.message}</Alert>
        )}
        <div className="flex justify-end">
          {retrievalResult ? (
            <Button
              onClick={() => {
                setRetrievalIndex((index) => index + 1)
                setSelected('')
                setRetrievalResult(null)
              }}
            >
              {retrievalIndex + 1 === retrieval.length ? 'Start module' : 'Next question'}
            </Button>
          ) : (
            <Button
              onClick={() => retrievalMutation.mutate()}
              disabled={!selected || retrievalMutation.isPending}
              loading={retrievalMutation.isPending}
            >
              Check answer
            </Button>
          )}
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
      {segment && <SegmentView key={segment.id} segment={segment} />}

      {/* Save error */}
      {mutation.isError && (
        <Alert tone="warning" title="Could not save progress">
          {mutation.error.message}
        </Alert>
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
          disabled={mutation.isPending}
          loading={mutation.isPending}
        >
          {isLast ? 'Finish module' : 'Next →'}
        </Button>
      </nav>
    </section>
  )
}
