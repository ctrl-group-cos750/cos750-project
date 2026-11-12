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

/** Chooses the activity control and consistently adds server feedback and the hint ladder. */
export function ActivityRenderer(props: ActivityRendererProps) {
  const isSupported = SUPPORTED.has(props.activity.kind)
  const Title = props.heading ?? 'h1'
  // A mastery check item takes one answer, and says only that it was recorded (#144).
  const check = props.activity.masteryCheck === true
  const answeredInCheck = check && (props.activity.answered === true || !!props.result?.withheld)

  return (
    <Card>
      {props.showTitle !== false && <Title>{props.activity.title}</Title>}
      {check && !answeredInCheck && (
        <p className="mb-4 text-sm text-muted-foreground">
          Only your first answer counts, so check it before you send it. You will see your results
          in your mastery report when you finish the check.
        </p>
      )}
      {answeredInCheck ? (
        // Just answered: the feedback panel below says so. Answered before: say it here.
        !props.result && (
          <Alert tone="info" title="Answer recorded">
            You have answered this question. Only your first answer counts, so it can't be changed.
            Your results are in your mastery report when you finish the check.
          </Alert>
        )
      ) : props.activity.kind === 'parsons' ? (
        <ParsonsProblem
          activity={props.activity}
          result={props.result}
          submitting={props.submitting}
          onSubmit={(order) => props.onSubmit({ order })}
        />
      ) : props.activity.kind === 'fill_in' ? (
        <FillInCode
          activity={props.activity}
          result={props.result}
          submitting={props.submitting}
          onSubmit={(answers) => props.onSubmit({ answers })}
        />
      ) : props.activity.kind === 'multiple_choice' ? (
        <MultipleChoice
          activity={props.activity}
          result={props.result}
          submitting={props.submitting}
          onSubmit={(selected) => props.onSubmit({ selected })}
        />
      ) : props.activity.kind === 'matching' ? (
        <Matching
          activity={props.activity}
          result={props.result}
          submitting={props.submitting}
          onSubmit={(pairs) => props.onSubmit({ pairs })}
        />
      ) : props.activity.kind === 'trace' ? (
        <TraceTable
          activity={props.activity}
          result={props.result}
          submitting={props.submitting}
          onSubmit={(rows) => props.onSubmit({ rows })}
        />
      ) : props.activity.kind === 'fix_the_bug' ? (
        <FixTheBug
          activity={props.activity}
          result={props.result}
          submitting={props.submitting}
          onSubmit={(order) => props.onSubmit({ order })}
        />
      ) : props.activity.kind === 'choose_tests' ? (
        <ChooseTests
          activity={props.activity}
          result={props.result}
          submitting={props.submitting}
          onSubmit={(selected) => props.onSubmit({ selected })}
        />
      ) : (
        <Alert tone="warning">This activity kind is not available yet.</Alert>
      )}
      {isSupported && (
        <div className="mt-5 grid gap-4">
          <FeedbackPanel result={props.result} />
          <HintLadder
            activityId={props.activity.id}
            disabled={props.submitting}
            solved={
              props.result?.correct === true || props.activity.solved === true || answeredInCheck
            }
            requestHint={props.requestHint}
            loadHints={props.loadHints}
          />
        </div>
      )}
    </Card>
  )
}
