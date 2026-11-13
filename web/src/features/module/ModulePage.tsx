import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { Alert, Button, ProgressBar, Spinner } from '../../components'
import { ActivityView } from '../activities/ActivityPage.tsx'
import { useRefreshRewards } from '../rewards/hooks.ts'
import { fetchModule, savePosition } from './module.api.ts'
import { SegmentView } from './SegmentView.tsx'
import {
  nearestShown,
  nextShown,
  previousShown,
  shownPlace,
  supportIntro,
} from './shownSegments.ts'
// A line of its own, so it merges cleanly with fix/web-rendering-a11y's change to the imports above.
import { Link } from 'react-router'
import { buttonVariants } from '@/components/ui/button-variants'
import { ApiError } from '../../api/client.ts'

/** The API refused the request (any 4xx: 403 locked, 404 no such module, 429 too many): asking
 * again gets the same answer, so it isn't retried and the page says so at once instead of spinning
 * (#136 review). Once fix/api-integrity (A1) is merged, this and the refusal view below can become
 * its `retryUnlessRefused` and `NotAvailable`. */
const refused = (error: Error) =>
  error instanceof ApiError && error.status >= 400 && error.status < 500

/** Module 6, the mastery check: finishing it opens the report (#144). MASTERY_MODULE in
 * api/app/services/mastery.py. */
const MASTERY_MODULE_ID = 6

/** A module id as the route gives it: a whole number, or nothing the API is asked about. */
const MODULE_ID = /^\d{1,9}$/

/** /modules/:moduleId — plays a module's segments in order, saves position (FR-2.3, FR-2.5). */
export function ModulePage() {
  // The id exactly as it is in the address. "abc", "1.5" or "-1" names no module, so the API isn't
  // asked; and the raw text, not Number(), is what is compared below (NaN never equals itself).
  const param = useParams().moduleId ?? ''
  const validId = MODULE_ID.test(param)
  const id = Number(param)
  const queryClient = useQueryClient()
  const refreshRewards = useRefreshRewards()
  const navigate = useNavigate()

  const query = useQuery({
    queryKey: ['module', id],
    queryFn: () => fetchModule(id),
    enabled: validId,
    retry: (failures, error) => !refused(error) && failures < 3,
  })

  // Drive current index from the fetched position; update locally on navigation.
  const [segmentIndex, setSegmentIndex] = useState<number | null>(null)
  // Which recall question is on screen; null until the student moves, so it starts at the first
  // one they haven't answered yet (FR-2.4).
  const [retrievalIndex, setRetrievalIndex] = useState<number | null>(null)
  const [retrievalChecked, setRetrievalChecked] = useState(false)
  // Set by Previous, Next, "Next question" and "Start module": after the new content renders,
  // focus moves to its heading (WCAG 2.4.3 Focus Order, #142). The button that was pressed may be
  // gone or disabled, which would drop focus on the page, and a screen reader then reads where
  // the student now is. Never set on first load, so opening a module doesn't move focus.
  const moveFocus = useRef(false)
  const contentRef = useRef<HTMLElement>(null)
  useEffect(() => {
    if (!moveFocus.current) return
    const heading = contentRef.current?.querySelector<HTMLElement>('[data-focus-heading]')
    if (!heading) return // still loading the new content: try again after the next render
    moveFocus.current = false
    heading.focus()
  })

  // Saves how far the student has got. The server keeps the furthest segment reached, so only
  // moving forward is saved; stepping back just changes what's on screen.
  const mutation = useMutation({
    mutationFn: ({ position }: { position: number; finishing: boolean; wasComplete: boolean }) =>
      savePosition(id, position),
    onSuccess: (saved, { finishing, wasComplete }) => {
      void queryClient.invalidateQueries({ queryKey: ['modules'] })
      void queryClient.invalidateQueries({ queryKey: ['module', id] })
      // Completing a module can earn its points and the First Module badge: fetch them now, so the
      // badge note comes with the finish, not with the next answer (which read as if that answer
      // had earned it). Only then: a Next that completes nothing earns nothing.
      if (finishing || (saved.status === 'complete' && !wasComplete)) refreshRewards()
    },
  })
  // Another module opened in place (a link, or Back and Forward): start it afresh, so a segment
  // index from the last module never carries over (#136 review). React's pattern for state that
  // resets when a prop changes.
  const [shownParam, setShownParam] = useState(param)
  if (shownParam !== param) {
    setShownParam(param)
    setSegmentIndex(null)
    setRetrievalIndex(null)
    setRetrievalChecked(false)
  }

  if (!validId)
    return (
      <ModuleRefused
        title="There’s no such module"
        message="A module’s address ends in its number, such as /modules/3."
      />
    )
  if (query.isPending) return <Spinner label="Loading module" />
  if (query.isError) {
    if (!refused(query.error)) return <Alert tone="danger">{query.error.message}</Alert>
    const status = query.error instanceof ApiError ? query.error.status : 0
    return (
      <ModuleRefused
        title={
          status === 404
            ? 'There’s no such module'
            : status === 403
              ? 'This module isn’t open yet'
              : 'This module can’t be shown right now'
        }
        message={query.error.message}
      />
    )
  }

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
      <section
        ref={contentRef}
        className="mx-auto grid w-full max-w-3xl gap-6"
        aria-label={`Module ${module.number} retrieval`}
      >
        <div className="grid gap-2">
          <h1 className="text-2xl font-bold">
            Module {module.number} · {module.title}
          </h1>
          <p className="text-sm text-muted-foreground" tabIndex={-1} data-focus-heading>
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
              moveFocus.current = true
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
    // After "Start module" on a module with only recall questions (module 5 today), focus goes to
    // this heading, so it isn't dropped on the page.
    return (
      <section ref={contentRef} className="grid gap-6">
        <h1 className="text-2xl font-bold" tabIndex={-1} data-focus-heading>
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

  // Initialise from the server's position; clamp to valid range. But if the student passed an
  // activity without ever answering it (or any, in a complete module), open there instead: one
  // that had no screen yet (trace, fix the bug and choose tests until #136) lands them on it, not
  // on a later segment with nothing to show what is missing. An activity they did answer, even
  // wrongly under an earlier rule, never pulls them back (#165 review).
  const firstSkipped = segments.findIndex(
    (s) => !s.done && !(s.kind === 'activity' && s.attempted === true),
  )
  const skipped =
    firstSkipped >= 0 &&
    (module.status === 'complete' || firstSkipped < module.currentSegmentPosition)
  const openedAt = skipped
    ? firstSkipped
    : Math.min(module.currentSegmentPosition, segments.length - 1)
  // Only segments shown to this student are ever on screen: support they don't need is skipped
  // (FR-8.4), wherever the page would otherwise open.
  const currentIndex = nearestShown(segments, segmentIndex ?? openedAt)
  // Fix where the page opened: answering that segment refetches the module, and the page must stay
  // on it to show the feedback, not jump on to the next segment that isn't done. (Setting state
  // during render, guarded so it happens once, is React's pattern for state derived from props.)
  if (segmentIndex === null) setSegmentIndex(currentIndex)
  const segment = segments[currentIndex]
  const isFirst = previousShown(segments, currentIndex) === -1
  const isLast = nextShown(segments, currentIndex) === -1
  const place = shownPlace(segments, currentIndex)
  // The server refuses to move past a segment that isn't done (FR-2.7); say why up front. Like
  // the server, only the furthest segment reached gates: stepping back over earlier progress
  // (made before this rule, or before staff changed the content) is never blocked, and nor is
  // anything in a complete module.
  const blocked =
    segment !== undefined &&
    !segment.done &&
    module.status !== 'complete' &&
    currentIndex >= module.currentSegmentPosition
  const blockedReason = !blocked
    ? ''
    : segment.kind === 'video'
      ? 'Answer each of the video’s checkpoint questions correctly to continue.'
      : segment.attempted
        ? 'Get it right to continue. If you’re stuck, the hints can help.'
        : 'Answer the activity to continue.'
  // The page opened here because the student moved past this activity before answering it: say
  // so, until it is done, so the jump back isn't a mystery.
  const showSkippedNote = skipped && currentIndex === firstSkipped && !segment?.done

  function handlePrevious() {
    if (mutation.isPending) return // aria-disabled while Next saves: the press does nothing
    moveFocus.current = true
    setSegmentIndex(Math.max(0, previousShown(segments, currentIndex)))
  }

  // Only moving past the furthest segment reached is saved. Moving forward again over segments
  // already reached (after stepping back) just changes what's on screen, like going back does.
  function handleNext() {
    if (blocked) return // the button stays focusable (aria-disabled), so the click is ignored here
    const next = nextShown(segments, currentIndex) // past any support this student isn't shown
    if (next === -1) return
    if (next <= module.currentSegmentPosition) {
      moveFocus.current = true
      setSegmentIndex(next)
      return
    }
    mutation.mutate(
      {
        position: segments[next].position,
        finishing: false,
        wasComplete: module.status === 'complete',
      },
      {
        onSuccess: () => {
          moveFocus.current = true
          setSegmentIndex(next)
        },
      },
    )
  }

  // Saving the last segment again once it is done is what completes the module (the server
  // completes it when the furthest position is the last segment and that segment is done). Then
  // back to the map, where the next module is now open; after the mastery check (module 6), to
  // the mastery report, which now has the results (#144).
  function handleFinish() {
    if (blocked) return
    const next = module.id === MASTERY_MODULE_ID ? '/report' : '/'
    mutation.mutate(
      {
        position: segments[currentIndex].position,
        finishing: true,
        wasComplete: module.status === 'complete',
      },
      { onSuccess: () => void navigate(next) },
    )
  }

  return (
    <section
      ref={contentRef}
      className="mx-auto grid w-full min-w-0 max-w-3xl gap-6 has-[[data-two-column]]:max-w-[70rem]"
      aria-label={`Module ${module.number}: ${module.title}`}
    >
      {/* Header */}
      <div className="grid gap-3">
        <Link
          to="/"
          className="justify-self-start text-sm text-muted-foreground hover:text-foreground"
        >
          ← All modules
        </Link>
        <h1 className="text-2xl font-bold">
          Module {module.number} · {module.title}
        </h1>

        {/* Goals (FR-2.3): open on the first segment, where they set the scene (Gagné's event
            2), then one click away, so the question isn't pushed down the screen every time. */}
        {module.goals.length > 0 && (
          <details
            key={place.number === 1 ? 'first' : 'later'}
            open={place.number === 1}
            className="rounded-lg border border-border bg-card px-4 py-3"
          >
            <summary className="cursor-pointer font-semibold">
              By the end of this module you can:
            </summary>
            <ul className="mt-2 ml-5 list-disc">
              {module.goals.map((goal) => (
                <li key={goal}>{goal}</li>
              ))}
            </ul>
          </details>
        )}
      </div>

      {/* Progress indicator (FR-2.5, AC5) */}
      <div className="grid gap-2">
        <ProgressBar
          label={`Module ${module.number} progress`}
          value={place.number}
          max={place.total}
        />
        <p className="text-sm text-muted-foreground" aria-live="polite">
          Segment {place.number} of {place.total}
        </p>
      </div>

      {showSkippedNote && (
        <Alert tone="info">
          You moved past this activity earlier without answering it. Answer it now, then carry on
          where you left off.
        </Alert>
      )}

      {/* Current segment */}
      {segment && (
        <SegmentView
          key={segment.id}
          segment={segment}
          intro={supportIntro(segments, currentIndex)}
          onAnswered={() => void queryClient.invalidateQueries({ queryKey: ['module', id] })}
        />
      )}

      {/* Save error */}
      {mutation.isError && (
        // Danger, so it is announced at once (role="alert") while focus stays on Next.
        <Alert tone="danger" title="Could not save progress">
          {mutation.error.message}
        </Alert>
      )}

      {/* Navigation. The reason Next is blocked is always rendered, as a polite status
          (<output>), so a screen reader announces it when it appears and when it clears; only
          its text changes. It sits with the buttons so an empty one costs only a small gap. */}
      <div className="grid gap-2">
        <output id="segment-blocked" className="block text-sm text-muted-foreground">
          {blockedReason}
        </output>
        <nav className="flex justify-between" aria-label="Segment navigation">
          <Button
            variant="secondary"
            onClick={handlePrevious}
            // Not disabled while Next saves, so focus is never dropped on the page (2.4.3).
            disabled={isFirst}
            aria-disabled={mutation.isPending || undefined}
          >
            ← Previous
          </Button>
          <Button
            variant={isLast ? 'primary' : 'secondary'}
            onClick={isLast ? handleFinish : handleNext}
            // aria-disabled rather than disabled while blocked: a disabled button can't be
            // focused, so its reason would never be read. The handlers ignore the click. While
            // the position saves it stays focusable too (keepFocusWhileLoading), so a failed save
            // leaves focus here with the error announced.
            aria-disabled={blocked || undefined}
            aria-describedby={blocked ? 'segment-blocked' : undefined}
            loading={mutation.isPending}
            keepFocusWhileLoading
          >
            {isLast ? 'Finish module' : 'Next →'}
          </Button>
        </nav>
      </div>
    </section>
  )
}

/** Why a module can't be shown, in the API's words, with the way back to the map instead of a
 * spinner that never ends. */
function ModuleRefused({ title, message }: { title: string; message: string }) {
  return (
    <section className="grid justify-items-start gap-3">
      <h1 className="text-2xl font-bold">{title}</h1>
      <Alert tone="info">{message}</Alert>
      <Link to="/" className={buttonVariants({ variant: 'ghost', size: 'sm' })}>
        Back to your modules
      </Link>
    </section>
  )
}
