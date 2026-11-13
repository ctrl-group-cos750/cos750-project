import { useCallback, useState } from 'react'
import { Alert, Card } from '../../components'
import { ChooseTests } from './ChooseTests.tsx'
import { FeedbackPanel } from './FeedbackPanel.tsx'
import { FillInCode } from './FillInCode.tsx'
import { FixTheBug } from './FixTheBug.tsx'
import { HintLadder } from './HintLadder.tsx'
import { Matching } from './Matching.tsx'
import { MultipleChoice } from './MultipleChoice.tsx'
import { ParsonsProblem } from './ParsonsProblem.tsx'
import { TraceTable } from './TraceTable.tsx'
import type { Activity, AttemptResult, Hint, LastAttempt, Submission } from './activities.types.ts'
import { answerView } from './pictures/answerTabs.ts'
import { PicturePanel } from './pictures/PicturePanel.tsx'
import { useMediaQuery, WIDE } from './pictures/useMediaQuery.ts'
import { pictureName, picturesForActivity } from './pictures/pictures.ts'

type ActivityRendererProps = {
  activity: Activity
  result: AttemptResult | undefined
  submitting: boolean
  onSubmit: (submitted: Submission) => Promise<void>
  requestHint: (activityId: number) => Promise<Hint>
  loadHints?: (activityId: number) => Promise<readonly Hint[]>
  heading?: 'h1' | 'h2' | 'h3'
  /** False inside a module segment, whose own heading already names the question. */
  showTitle?: boolean
  /** The student's last answer, which each control starts from when they come back (#171). */
  previous?: LastAttempt['submitted']
}

// The kinds a student can answer: today every kind the API has (FR-4.1, FR-5.5). The API's
// KINDS_WITHOUT_STUDENT_UI (api/app/services/modules.py) is the mirror: a module segment of any
// other kind counts as done (FR-2.7), so a kind added to the API before its screen can't block a
// student. Add a kind here and remove it there together, once its control exists.
const SUPPORTED: ReadonlySet<string> = new Set<Activity['kind']>([
  'parsons',
  'fill_in',
  'multiple_choice',
  'matching',
  'trace',
  'fix_the_bug',
  'choose_tests',
])

/** Chooses the activity control and consistently adds server feedback and the hint ladder.
 *
 * A question with a picture (#155, module 1) is two columns from about 1100 px: the prompt and
 * the picture on the left, kept in view (sticky), and the answer rows, Check answer, the result
 * and the hints on the right, so the picture is beside the rows it refers to (Mayer's spatial
 * contiguity). Below that everything is stacked: prompt, picture, answer rows, Check answer,
 * result, the your-graph tabs, hints. Once the student's answer can be drawn, the picture
 * switches in place to tabs (Your graph | the map), so the map is never on the page twice. */
export function ActivityRenderer(props: ActivityRendererProps) {
  const isSupported = SUPPORTED.has(props.activity.kind)
  const Title = props.heading ?? 'h1'
  // A mastery check item takes one answer, and says only that it was recorded (#144).
  const check = props.activity.masteryCheck === true
  const answeredInCheck = check && (props.activity.answered === true || !!props.result?.withheld)
  // Pictures are for practice items only: a mastery item never shows a correct graph (#155).
  const pictures = check ? undefined : picturesForActivity(props.activity.id)
  const wide = useMediaQuery(WIDE)
  const [submitted, setSubmitted] = useState<Submission | undefined>(
    () => props.previous as Submission | undefined,
  )
  // What each control starts from: the answer given on this screen, else the last one (#171).
  // A control reads it only when it first mounts, so this only matters if it is mounted again.
  const previous: LastAttempt['submitted'] | undefined = submitted ?? props.previous
  const [hintLevel, setHintLevel] = useState(0)
  const onLevel = useCallback((level: number) => setHintLevel(level), [])
  const onSubmit = (submission: Submission) => {
    setSubmitted(submission)
    return props.onSubmit(submission)
  }
  // The correct graph only after a right answer or once hint 4 is open.
  const compare =
    props.result?.correct === true || Math.max(hintLevel, props.result?.hintLevel ?? 0) >= 4

  // A mastery item always says why it takes one answer. Once answered with its result on screen,
  // the feedback panel says it was recorded and where the results are; with no result yet, the
  // "Answer recorded" alert above the answer says all of it (#144, #171).
  const checkNote =
    check &&
    (!answeredInCheck ? (
      <p className="mb-4 text-sm text-muted-foreground">
        Only your first answer counts, so check it before you send it. Your results are in your
        mastery report once every question in the check is answered.
      </p>
    ) : (
      props.result && (
        <p className="mb-4 text-sm text-muted-foreground">
          You have answered this question. Only your first answer counts, so it can't be changed.
        </p>
      )
    ))
  const screen =
    props.activity.kind === 'parsons' ? (
      <ParsonsProblem
        activity={props.activity}
        result={props.result}
        submitting={props.submitting}
        onSubmit={(order) => onSubmit({ order })}
        previous={previous?.order}
        readOnly={answeredInCheck}
      />
    ) : props.activity.kind === 'fill_in' ? (
      <FillInCode
        activity={props.activity}
        result={props.result}
        submitting={props.submitting}
        onSubmit={(answers) => onSubmit({ answers })}
        previous={previous?.answers}
        readOnly={answeredInCheck}
      />
    ) : props.activity.kind === 'multiple_choice' ? (
      <MultipleChoice
        activity={props.activity}
        result={props.result}
        submitting={props.submitting}
        onSubmit={(selected) => onSubmit({ selected })}
        previous={typeof previous?.selected === 'string' ? previous.selected : undefined}
        readOnly={answeredInCheck}
      />
    ) : props.activity.kind === 'matching' ? (
      <Matching
        activity={props.activity}
        result={props.result}
        submitting={props.submitting}
        onSubmit={(pairs) => onSubmit({ pairs })}
        showPrompt={!pictures}
        previous={previous?.pairs}
        readOnly={answeredInCheck}
      />
    ) : props.activity.kind === 'trace' ? (
      <TraceTable
        activity={props.activity}
        result={props.result}
        submitting={props.submitting}
        onSubmit={(rows) => onSubmit({ rows })}
        previous={previous?.rows}
        readOnly={answeredInCheck}
      />
    ) : props.activity.kind === 'fix_the_bug' ? (
      <FixTheBug
        activity={props.activity}
        result={props.result}
        submitting={props.submitting}
        onSubmit={(order) => onSubmit({ order })}
        previous={previous?.order}
        readOnly={answeredInCheck}
      />
    ) : props.activity.kind === 'choose_tests' ? (
      <ChooseTests
        activity={props.activity}
        result={props.result}
        submitting={props.submitting}
        onSubmit={(selected) => onSubmit({ selected })}
        previous={Array.isArray(previous?.selected) ? previous.selected : undefined}
        readOnly={answeredInCheck}
      />
    ) : (
      <Alert tone="warning">This activity kind is not available yet.</Alert>
    )
  // An answered mastery item shows the answer, read-only: only the first answer counts (#144).
  // Its result stays withheld; the feedback panel says it was recorded (#171). The control is
  // always inside the fieldset, answered or not, so answering doesn't remount it: a remounted
  // control would start again from the answer the page loaded with, which on a first answer is
  // none, and the answer just given would vanish.
  const control = (
    <>
      {answeredInCheck && !props.result && (
        <Alert tone="info" title="Answer recorded">
          You have answered this question. Only your first answer counts, so it can't be changed.
          Your results are in your mastery report once every question in the check is answered.
        </Alert>
      )}
      <fieldset
        disabled={answeredInCheck}
        aria-label={answeredInCheck ? 'Your answer' : undefined}
        className="m-0 min-w-0 border-0 p-0"
      >
        {screen}
      </fieldset>
    </>
  )
  const feedback = isSupported && <FeedbackPanel result={props.result} />
  const hints = isSupported && (
    <HintLadder
      activityId={props.activity.id}
      disabled={props.submitting}
      solved={props.result?.correct === true || props.activity.solved === true || answeredInCheck}
      requestHint={props.requestHint}
      loadHints={props.loadHints}
      onLevel={onLevel}
    />
  )
  const title = props.showTitle !== false && (
    <Title className="text-2xl font-semibold">{props.activity.title}</Title>
  )

  if (!pictures) {
    return (
      <Card>
        {title}
        {checkNote}
        {control}
        {isSupported && (
          <div className="mt-5 grid gap-4">
            {feedback}
            {hints}
          </div>
        )}
      </Card>
    )
  }

  const answer = answerView(props.activity, pictures, submitted, props.result, compare)
  const panel = answer ? (
    <PicturePanel tabs={answer.tabs} caption={answer.caption} version={props.result?.id} />
  ) : (
    <PicturePanel tabs={[{ name: pictureName(pictures.picture), picture: pictures.picture }]} />
  )
  // Matching's prompt is a plain paragraph, so it moves beside the picture; multiple choice keeps
  // its prompt as the legend that names its options.
  const prompt = props.activity.kind === 'matching' && (
    <p className="m-0 font-medium">{props.activity.config.prompt}</p>
  )

  if (wide) {
    return (
      <Card>
        {title}
        <div
          data-two-column
          className="grid grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)] items-start gap-7"
        >
          <div className="sticky top-4 grid gap-3">
            {prompt}
            {panel}
          </div>
          <div className="grid gap-4">
            {control}
            {feedback}
            {hints}
          </div>
        </div>
      </Card>
    )
  }
  return (
    <Card>
      {title}
      <div className="grid gap-4">
        {prompt}
        {!answer && <div className="max-w-[520px]">{panel}</div>}
        {control}
      </div>
      <div className="mt-5 grid gap-4">
        {feedback}
        {answer && <div className="max-w-[520px]">{panel}</div>}
        {hints}
      </div>
    </Card>
  )
}
