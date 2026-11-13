import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router'
import { Alert, Button, ProgressBar, Spinner } from '../../components'
import { ActivityView } from '../activities/ActivityPage.tsx'
import { CelebrationAllowed } from '../activities/celebration.ts'
import { useRewards } from '../rewards/hooks.ts'
import { fetchModule, restartModule, savePosition } from './module.api.ts'
import type { ModuleDetail, ModuleSummary } from './module.types.ts'
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
import { useMediaQuery } from '../activities/pictures/useMediaQuery.ts'
import { confetti } from '../progress/confetti.ts'
import { skillsKey } from '../progress/hooks.ts'
import { ProgressPanel } from '../progress/ProgressPanel.tsx'

/** Phones, where the module's goals start closed so the lesson starts on the first screen. */
const PHONE_WIDTH = '(max-width: 40rem)'
import { usePageTitle } from '../../pages/usePageTitle.ts'

/** The API refused the request (any 4xx: 403 locked, 404 no such module, 429 too many): asking
 * again gets the same answer, so it isn't retried and the page says so at once instead of spinning
 * (#136 review). Once fix/api-integrity (A1) is merged, this and the refusal view below can become
 * its `retryUnlessRefused` and `NotAvailable`. */
const refused = (error: Error) =>
  error instanceof ApiError && error.status >= 400 && error.status < 500

/** Module 6, the mastery check: finishing it opens the report (#144). MASTERY_MODULE in
 * api/app/services/mastery.py. */
const MASTERY_MODULE_ID = 6

/** A segment to open at, from `?segment=<position>`: a link from the list of activities to look
 * at again (ProgressPanel, #215 review). */
const SEGMENT = /^\d{1,4}$/

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
  const navigate = useNavigate()
  const [search] = useSearchParams()
  const segmentParam = search.get('segment') ?? ''
  const askedFor = SEGMENT.test(segmentParam) ? Number(segmentParam) : null
  const hideRewards = useRewards().data?.hideRewards !== false

  const query = useQuery({
    queryKey: ['module', id],
    queryFn: () => fetchModule(id),
    enabled: validId,
    retry: (failures, error) => !refused(error) && failures < 3,
  })
  usePageTitle(query.data && `Module ${query.data.number}: ${query.data.title}`)

  // Drive current index from the fetched position; update locally on navigation.
  const [segmentIndex, setSegmentIndex] = useState<number | null>(null)
  const phone = useMediaQuery(PHONE_WIDTH)
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
  // A link to another segment of the same module (the look-again list) moves focus to it, as
  // Next does. Not on first load. Before the effect below, which then moves it.
  const linkedFrom = useRef(`${param}?${segmentParam}`)
  useEffect(() => {
    const now = `${param}?${segmentParam}`
    if (linkedFrom.current === now) return
    if (linkedFrom.current.split('?')[0] === param && segmentParam) moveFocus.current = true
    linkedFrom.current = now
  }, [param, segmentParam])
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
    mutationFn: (position: number) => savePosition(id, position),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['modules'] })
      void queryClient.invalidateQueries({ queryKey: ['module', id] })
    },
  })
  // Restart the module to redo its questions: it reopens at its start (or its recall questions),
  // and every activity on screen is fetched afresh, so no earlier answer is restored.
  const [restarts, setRestarts] = useState(0)
  const restart = useMutation({
    mutationFn: () => restartModule(id),
    onSuccess: (detail) => {
      queryClient.removeQueries({ queryKey: ['activities'] })
      queryClient.removeQueries({ queryKey: ['video'] })
      queryClient.setQueryData(['module', id], detail)
      void queryClient.invalidateQueries({ queryKey: ['modules'] })
      moveFocus.current = true
      setSegmentIndex(null)
      setRetrievalIndex(null)
      setRetrievalChecked(false)
      setRestarts((n) => n + 1)
      // Opened from a look-again link (`?segment=`): a restart opens at the start, not there.
      if (segmentParam) void navigate(`/modules/${id}`, { replace: true })
    },
  })
  // Another module opened in place (a link, or Back and Forward): start it afresh, so a segment
  // index from the last module never carries over (#136 review). React's pattern for state that
  // resets when a prop changes.
  // A link to another segment of this module (`?segment=`) opens that one in the same way.
  const [shownParam, setShownParam] = useState(`${param}?${segmentParam}`)
  if (shownParam !== `${param}?${segmentParam}`) {
    setShownParam(`${param}?${segmentParam}`)
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
          <h1 className="text-xl font-bold sm:text-2xl">
            Module {module.number} · {module.title}
          </h1>
          <ChoiceNote module={module} />
          <p className="text-sm text-muted-foreground" tabIndex={-1} data-focus-heading>
            Quick recall · Question {recallIndex + 1} of {retrieval.length}
          </p>
        </div>
        <CelebrationAllowed.Provider value={module.id !== MASTERY_MODULE_ID}>
          <ActivityView
            key={item.id}
            activityId={item.id}
            heading="h2"
            onResult={() => setRetrievalChecked(true)}
          />
        </CelebrationAllowed.Provider>
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
  // A restarted module opens at its start, not at its first question (they are all undone).
  const skipped =
    firstSkipped >= 0 &&
    ((module.status === 'complete' && !module.restarted) ||
      firstSkipped < module.currentSegmentPosition)
  // A link to one segment (`?segment=`, the look-again list) opens there if the student has
  // reached it; a segment further on can't be opened by its address.
  const reachable =
    askedFor !== null &&
    askedFor < segments.length &&
    (module.status === 'complete' || askedFor <= module.currentSegmentPosition)
  const openedAt = reachable
    ? askedFor
    : skipped
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
        ? hideRewards
          ? 'Not yet right. Try again: after one more answer you can move on, though it won’t count as right, and the hints can help.'
          : 'Not yet right. Try again: after one more answer you can move on, though it earns no points then, and the hints can help.'
        : 'Answer the activity to continue.'
  // Two answers, or one after the last hint, and the student may move on without getting it right
  // (FR-2.7, #214): say so, that it is marked to look at again, and plainly that moving on earns
  // nothing for it (#215 review). The progress panel lists every one marked.
  const statusLine =
    blockedReason ||
    (segment?.lookAgain
      ? hideRewards
        ? 'You can move on: this one is marked to look at again. It doesn’t count as right until you answer it right.'
        : 'You can move on: this one is marked to look at again. Moving on earns no points for it; answer it right later and it does.'
      : '')
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
    mutation.mutate(segments[next].position, {
      onSuccess: () => {
        moveFocus.current = true
        setSegmentIndex(next)
      },
    })
  }

  // Saving the last segment again once it is done is what completes the module (the server
  // completes it when the furthest position is the last segment and that segment is done). Then
  // back to the map, where the next module is now open; after the mastery check (module 6), to
  // the mastery report, which now has the results (#144).
  function handleFinish() {
    if (blocked) return
    const next = module.id === MASTERY_MODULE_ID ? '/report' : '/'
    mutation.mutate(segments[currentIndex].position, {
      onSuccess: () => {
        // Finishing a module is worth a full burst (#214); not the mastery check, whose results
        // the report gives, with its own moment if the student is ready for the lecture.
        if (module.id !== MASTERY_MODULE_ID) confetti('big')
        void queryClient.invalidateQueries({ queryKey: skillsKey }) // the medal is now earned
        void navigate(next)
      },
    })
  }

  // On wide screens the progress panel sits beside the lesson (#214). The lesson column is a
  // container (`@container`): a segment's picture goes beside its text only when the column itself
  // is wide enough (72rem, `@6xl`), measured after the panel, so the picture always gets at least
  // about 28rem (450 px); a viewport breakpoint would squeeze it to 200 px beside the panel.
  // A segment with two columns lets the lesson widen to 100rem, so wide screens are used.
  // The activities marked to look at again, each a link to its segment (#215 review).
  const lookAgain = segments.flatMap((s, index) =>
    s.lookAgain && s.shown !== false ? [{ position: index, title: s.title }] : [],
  )
  const panel = { moduleId: module.id, moduleNumber: module.number, place, lookAgain }
  return (
    // Nothing in the mastery check celebrates a right answer (#215 review).
    <CelebrationAllowed.Provider value={module.id !== MASTERY_MODULE_ID}>
      <div className="grid w-full items-start gap-6 lg:grid-cols-[minmax(0,1fr)_19rem] lg:gap-8">
        <div className="@container min-w-0">
          <section
            ref={contentRef}
            className="mx-auto grid w-full min-w-0 max-w-3xl gap-4 sm:gap-6 has-[[data-two-column]]:max-w-[100rem] @6xl:has-[[data-picture-beside]]:max-w-[100rem]"
            aria-label={`Module ${module.number}: ${module.title}`}
          >
            {/* Header. Compact on a phone, so the lesson starts on the first screen of a 320 × 568 one. */}
            <div className="grid gap-2 sm:gap-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Link
                  to="/"
                  className="inline-flex min-h-11 items-center text-sm text-muted-foreground hover:text-foreground sm:min-h-0"
                >
                  ← All modules
                </Link>
                {module.canRestart && (
                  <RestartModule
                    // Remounted after each restart, so its "Restart this module?" question closes.
                    key={restarts}
                    pending={restart.isPending}
                    error={restart.error?.message ?? null}
                    onRestart={() => restart.mutate()}
                    // A failed restart's message belongs to that try: cancelling or asking again
                    // starts without it.
                    onReset={() => restart.reset()}
                  />
                )}
              </div>
              <h1 className="text-xl font-bold sm:text-2xl">
                Module {module.number} · {module.title}
              </h1>
              <ChoiceNote module={module} />

              {/* Goals (FR-2.3): open on the first segment, where they set the scene (Gagné's event
            2), then one click away, so the question isn't pushed down the screen every time. On
            a phone they start closed: open, they fill the first screen. */}
              {module.goals.length > 0 && (
                <details
                  key={place.number === 1 && !phone ? 'first' : 'later'}
                  open={place.number === 1 && !phone}
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

            {/* Progress indicator (FR-2.5, AC5): the count beside the bar on a phone, under it on a
            wider screen. */}
            <div className="flex items-center gap-3 sm:grid sm:gap-2">
              <div className="min-w-0 flex-1">
                <ProgressBar
                  label={`Module ${module.number} progress`}
                  value={place.number}
                  max={place.total}
                />
              </div>
              <p className="m-0 shrink-0 text-sm text-muted-foreground" aria-live="polite">
                Segment {place.number} of {place.total}
              </p>
            </div>

            {showSkippedNote && (
              <Alert tone="info">
                You moved past this activity earlier without answering it. Answer it now, then carry
                on where you left off.
              </Alert>
            )}

            {/* Current segment */}
            {segment && (
              <SegmentView
                key={`${segment.id}:${restarts}`}
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
                {statusLine}
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
            <ProgressPanel placement="below" {...panel} />
          </section>
        </div>
        <ProgressPanel placement="beside" {...panel} />
      </div>
    </CelebrationAllowed.Provider>
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

/** At the top of a module (#214): the quick check offer ("Already know this?", FR-8.2) while the
 * student can take it, or a note that they tested out of the module. */
function ChoiceNote({ module }: { module: ModuleDetail }) {
  if (module.status === 'tested_out')
    return (
      <p className="m-0 text-sm text-muted-foreground">
        You tested out of this module with its quick check. Working through it is up to you.{' '}
        <QuickCheckScore module={module} />
      </p>
    )
  // Once taken, the result stays one click away, passed or not (#215 review).
  if (module.quickCheckScore)
    return (
      <p className="m-0 text-sm text-muted-foreground">
        <QuickCheckScore module={module} />
      </p>
    )
  if (module.quickCheck !== 'available' || module.status === 'complete') return null
  return (
    <p className="m-0 text-sm text-muted-foreground">
      Already know this?{' '}
      <Link to={`/modules/${module.id}/check`} className="font-medium text-foreground underline">
        Take the quick check
      </Link>
      : four questions, and if you know it you can move on.
    </p>
  )
}

/** "Quick check: 2 of 4, see results": the way back to a taken quick check's result page. */
export function QuickCheckScore({ module }: { module: ModuleSummary }) {
  const score = module.quickCheckScore
  if (!score) return null
  return (
    <>
      Quick check: {score.correct} of {score.total},{' '}
      <Link
        to={`/modules/${module.id}/check`}
        className="font-medium text-foreground underline"
        aria-label={`Quick check: ${score.correct} of ${score.total}, see the results for module ${module.number}`}
      >
        see results
      </Link>
    </>
  )
}

/** "Restart module": asks first, in place (no dialog to trap focus in), then starts the module
 * again. Says what stays (points, badges, the module being complete) and what changes (the
 * questions show unanswered, with hints from the first again), so nobody fears losing progress. */
function RestartModule({
  pending,
  error,
  onRestart,
  onReset,
}: {
  pending: boolean
  error: string | null
  onRestart: () => void
  onReset: () => void
}) {
  const [asking, setAsking] = useState(false)
  const box = useRef<HTMLDivElement>(null)
  // Keyboard focus follows the question (WCAG 2.4.3): into it when it opens, onto Cancel (the
  // safe choice), and back to the button that opened it when it closes.
  const reopened = useRef(false)
  useEffect(() => {
    const buttons = box.current?.querySelectorAll('button')
    if (asking) buttons?.[1]?.focus()
    else if (reopened.current) buttons?.[0]?.focus()
  }, [asking])
  const open = () => {
    onReset()
    setAsking(true)
  }
  const close = () => {
    reopened.current = true
    onReset()
    setAsking(false)
  }
  // Escape closes the question, as it would a dialog, unless the restart is already on its way.
  // Only while focus is in it: Escape elsewhere on the page (a video, a hint) is not for it.
  useEffect(() => {
    if (!asking || pending) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      if (!(event.target instanceof Node) || !box.current?.contains(event.target)) return
      reopened.current = true
      onReset()
      setAsking(false)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [asking, pending, onReset])
  if (!asking)
    return (
      <div ref={box}>
        <Button variant="ghost" size="sm" onClick={open}>
          Restart module
        </Button>
      </div>
    )
  return (
    <div ref={box} className="w-full">
      <fieldset className="grid w-full gap-2 rounded-lg border border-border bg-card p-4 m-0 min-w-0">
        <legend className="float-left mb-1 w-full p-0 font-semibold">Restart this module?</legend>
        <p className="m-0 text-sm text-muted-foreground">
          Its questions will show unanswered, with their hints from the first again, so you can try
          them afresh. You keep your points and badges, and the module stays complete.
        </p>
        {error && <Alert tone="danger">{error}</Alert>}
        <div className="flex flex-wrap gap-2">
          <Button size="sm" loading={pending} onClick={onRestart}>
            Restart module
          </Button>
          <Button variant="ghost" size="sm" disabled={pending} onClick={close}>
            Cancel
          </Button>
        </div>
      </fieldset>
    </div>
  )
}
