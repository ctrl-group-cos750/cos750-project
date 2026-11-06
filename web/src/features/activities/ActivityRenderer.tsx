import { Alert, Card } from '../../components'
import { FeedbackPanel } from './FeedbackPanel.tsx'
import { FillInCode } from './FillInCode.tsx'
import { HintLadder } from './HintLadder.tsx'
import { ParsonsProblem } from './ParsonsProblem.tsx'
import type { AttemptResult, CodeActivity, Hint } from './activities.types.ts'

type ActivityRendererProps = {
  activity: CodeActivity
  result: AttemptResult | undefined
  submitting: boolean
  onSubmit: (submitted: { order: number[] } | { answers: Record<number, string> }) => Promise<void>
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
      ) : (
        <Alert tone="warning">This activity kind is not available yet.</Alert>
      )}
      <div className="mt-5 grid gap-4">
        <FeedbackPanel
          result={props.result}
          partName={props.activity.kind === 'parsons' ? 'line' : 'blank'}
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
