import { Alert, Card } from '../../components'
import { FeedbackPanel } from './FeedbackPanel.tsx'
import { FillInCode } from './FillInCode.tsx'
import { HintLadder } from './HintLadder.tsx'
import { Matching } from './Matching.tsx'
import { MultipleChoice } from './MultipleChoice.tsx'
import { ParsonsProblem } from './ParsonsProblem.tsx'
import type { Activity, AttemptResult, Hint, Submission } from './activities.types.ts'

type ActivityRendererProps = {
  activity: Activity
  result: AttemptResult | undefined
  submitting: boolean
  onSubmit: (submitted: Submission) => Promise<void>
  requestHint: (activityId: number) => Promise<Hint>
  loadHints?: (activityId: number) => Promise<readonly Hint[]>
  heading?: 'h1' | 'h2' | 'h3'
}

// The kinds a student can answer. The API's KINDS_WITHOUT_STUDENT_UI (api/app/services/modules.py)
// is the mirror: a module segment of any other kind counts as done (FR-2.7), so it can't block.
// Add a kind here and remove it there together, once its control exists.
const SUPPORTED: ReadonlySet<Activity['kind']> = new Set([
  'parsons',
  'fill_in',
  'multiple_choice',
  'matching',
])

/** Chooses the activity control and consistently adds server feedback and the hint ladder. */
export function ActivityRenderer(props: ActivityRendererProps) {
  const isSupported = SUPPORTED.has(props.activity.kind)
  const Title = props.heading ?? 'h1'

  return (
    <Card>
      <Title>{props.activity.title}</Title>
      {props.activity.kind === 'parsons' ? (
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
      ) : (
        <Alert tone="warning">This activity kind is not available yet.</Alert>
      )}
      {isSupported && (
        <div className="mt-5 grid gap-4">
          <FeedbackPanel result={props.result} />
          <HintLadder
            activityId={props.activity.id}
            disabled={props.submitting}
            solved={props.result?.correct === true}
            requestHint={props.requestHint}
            loadHints={props.loadHints}
          />
        </div>
      )}
    </Card>
  )
}
