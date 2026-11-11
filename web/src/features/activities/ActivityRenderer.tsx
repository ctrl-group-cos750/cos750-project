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
import type { Activity, AttemptResult, Hint, Submission } from './activities.types.ts'
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
  const pictures = picturesForActivity(props.activity.id)
  const wide = useMediaQuery(WIDE)
  const [submitted, setSubmitted] = useState<Submission>()
  const [hintLevel, setHintLevel] = useState(0)
  const onLevel = useCallback((level: number) => setHintLevel(level), [])
  const onSubmit = (submission: Submission) => {
    setSubmitted(submission)
    return props.onSubmit(submission)
  }
  // The correct graph only after a right answer or once hint 4 is open.
  const compare =
    props.result?.correct === true || Math.max(hintLevel, props.result?.hintLevel ?? 0) >= 4

  const control =
    props.activity.kind === 'parsons' ? (
      <ParsonsProblem
        activity={props.activity}
        result={props.result}
        submitting={props.submitting}
        onSubmit={(order) => onSubmit({ order })}
      />
    ) : props.activity.kind === 'fill_in' ? (
      <FillInCode
        activity={props.activity}
        result={props.result}
        submitting={props.submitting}
        onSubmit={(answers) => onSubmit({ answers })}
      />
    ) : props.activity.kind === 'multiple_choice' ? (
      <MultipleChoice
        activity={props.activity}
        result={props.result}
        submitting={props.submitting}
        onSubmit={(selected) => onSubmit({ selected })}
      />
    ) : props.activity.kind === 'matching' ? (
      <Matching
        activity={props.activity}
        result={props.result}
        submitting={props.submitting}
        onSubmit={(pairs) => onSubmit({ pairs })}
        showPrompt={!pictures}
      />
    ) : props.activity.kind === 'trace' ? (
      <TraceTable
        activity={props.activity}
        result={props.result}
        submitting={props.submitting}
        onSubmit={(rows) => onSubmit({ rows })}
      />
    ) : props.activity.kind === 'fix_the_bug' ? (
      <FixTheBug
        activity={props.activity}
        result={props.result}
        submitting={props.submitting}
        onSubmit={(order) => onSubmit({ order })}
      />
    ) : props.activity.kind === 'choose_tests' ? (
      <ChooseTests
        activity={props.activity}
        result={props.result}
        submitting={props.submitting}
        onSubmit={(selected) => onSubmit({ selected })}
      />
    ) : (
      <Alert tone="warning">This activity kind is not available yet.</Alert>
    )
  const feedback = isSupported && <FeedbackPanel result={props.result} />
  const hints = isSupported && (
    <HintLadder
      activityId={props.activity.id}
      disabled={props.submitting}
      solved={props.result?.correct === true || props.activity.solved === true}
      requestHint={props.requestHint}
      loadHints={props.loadHints}
      onLevel={onLevel}
    />
  )
  const title = props.showTitle !== false && <Title>{props.activity.title}</Title>

  if (!pictures) {
    return (
      <Card>
        {title}
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
