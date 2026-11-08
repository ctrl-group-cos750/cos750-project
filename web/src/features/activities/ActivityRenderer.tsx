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
}

/** Chooses the activity control and consistently adds server feedback and the hint ladder. */
export function ActivityRenderer(props: ActivityRendererProps) {
  return (
    <Card>
      <h1>{props.activity.title}</h1>
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
      <div className="mt-5 grid gap-4">
        <FeedbackPanel
          result={props.result}
          partName={
            props.activity.kind === 'parsons'
              ? 'line'
              : props.activity.kind === 'fill_in'
                ? 'blank'
                : undefined
          }
        />
        <HintLadder
          activityId={props.activity.id}
          disabled={props.submitting}
          requestHint={props.requestHint}
        />
      </div>
    </Card>
  )
}
