import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useParams } from 'react-router'
import { Alert, Button, Markdown, ProgressBar, Spinner } from '../../components'
import { fetchModule, savePosition } from './module.api.ts'
import { SegmentView } from './SegmentView.tsx'

/** /modules/:moduleId — plays a module's segments in order, saves position (FR-2.3, FR-2.5). */
export function ModulePage() {
  const id = Number(useParams().moduleId)
  const queryClient = useQueryClient()

  const query = useQuery({ queryKey: ['module', id], queryFn: () => fetchModule(id) })

  // Drive current index from the fetched position; update locally on navigation.
  const [segmentIndex, setSegmentIndex] = useState<number | null>(null)

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

  if (segments.length === 0) {
    return (
      <section className="grid gap-6">
        <h1 className="text-2xl font-bold">
          Module {module.number} · {module.title}
        </h1>
        <Alert tone="info">This module has no segments yet.</Alert>
      </section>
    )
  }

  // Initialise from the server's position; clamp to valid range.
  const currentIndex = segmentIndex ?? Math.min(module.currentSegmentPosition, segments.length - 1)
  const segment = segments[currentIndex]
  const isFirst = currentIndex === 0
  const isLast = currentIndex === segments.length - 1

  function navigateTo(newIndex: number) {
    const clamped = Math.max(0, Math.min(newIndex, segments.length - 1))
    setSegmentIndex(clamped)
    // Save position (1-based position matches the segment's `position` field).
    mutation.mutate(segments[clamped].position)
  }

  function handlePrevious() {
    navigateTo(currentIndex - 1)
  }

  function handleNext() {
    navigateTo(currentIndex + 1)
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

        {/* Goals rendered as Markdown (FR-2.3) */}
        {module.goals && (
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
              Learning goals
            </p>
            <Markdown>{module.goals}</Markdown>
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
          onClick={handleNext}
          disabled={(isLast && mutation.isPending) || mutation.isPending}
          loading={mutation.isPending}
        >
          {isLast ? 'Finish module' : 'Next →'}
        </Button>
      </nav>
    </section>
  )
}
