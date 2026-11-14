import { Link, useParams } from 'react-router'
import { buttonVariants } from '@/components/ui/button-variants'
import { cn } from '@/lib/utils'
import { ApiError } from '../../api/client.ts'
import { Alert, Card, Markdown, MasteryStatus, Spinner, Tag, type Mastery } from '../../components'
import { backState } from '../../components/backState.ts'
import { useReviewPath } from './hooks.ts'
import type { ObjectiveState, ReviewStep } from './mastery.api.ts'
import styles from './ReviewPage.module.css'

const asMastery: Partial<Record<ObjectiveState, Mastery>> = {
  met_independently: 'independent',
  met_with_support: 'supported',
  not_yet: 'not-yet',
}

function Step({ step, objectiveId }: { step: ReviewStep; objectiveId: number }) {
  if (step.activityId === null) {
    return (
      <li className={styles.step}>
        <h2 className={styles.title}>{step.title}</h2>
        <div className={styles.prose}>
          <Markdown>{step.body}</Markdown>
        </div>
      </li>
    )
  }
  const fresh = step.purpose === 'mastery'
  return (
    <li className={styles.step}>
      <div className={styles.activity}>
        <div>
          <h2 className={styles.title}>{step.title}</h2>
          <p className={styles.muted}>
            {fresh
              ? 'A new question. Your first answer counts towards your result, with up to three hints.'
              : 'Practice, with all four hints. It doesn’t count towards your result.'}
          </p>
        </div>
        {step.answered ? (
          <Tag tone="success" icon="✓">
            Answered
          </Tag>
        ) : null}
      </div>
      {step.locked ? (
        // The path shows every step at once, so a fresh question says why it can't be opened yet.
        <p className={styles.muted}>Opens once you have done the practice above.</p>
      ) : (
        <ActivityLink step={step} objectiveId={objectiveId} fresh={fresh} />
      )}
    </li>
  )
}

function ActivityLink({
  step,
  objectiveId,
  fresh,
}: {
  step: ReviewStep
  objectiveId: number
  fresh: boolean
}) {
  return (
    <Link
      to={`/activities/${step.activityId}`}
      // The activity page leads back to this path (#146).
      state={backState(`/review/${objectiveId}`, 'Back to the review path')}
      className={cn(
        buttonVariants({ variant: step.answered ? 'outline' : 'default' }),
        'justify-self-start',
      )}
    >
      {step.answered ? (fresh ? 'See it again' : 'Practise again') : fresh ? 'Answer' : 'Practise'}
      <span className="sr-only">: {step.title}</span>
    </Link>
  )
}

/**
 * /review/:objectiveId — the review path for an objective the mastery check marked "not yet"
 * (FR-7.5, ID document §7.6): the objective taught again, practice with the full hint ladder, then
 * fresh questions that decide the result once all are answered.
 */
export function ReviewPage() {
  const objectiveId = Number(useParams().objectiveId)
  const path = useReviewPath(objectiveId)

  if (!Number.isInteger(objectiveId) || objectiveId <= 0)
    return <Alert tone="danger">There is no such objective.</Alert>
  if (path.isPending) return <Spinner label="Loading your review path" />
  if (path.isError) {
    const closed = path.error instanceof ApiError && path.error.status === 403
    return (
      <>
        <div className={styles.heading}>
          <h1>Review: objective {objectiveId}</h1>
        </div>
        <Alert tone={closed ? 'info' : 'danger'}>{path.error.message}</Alert>
        <Link to="/report" className={buttonVariants({ variant: 'ghost', size: 'sm' })}>
          Back to your report
        </Link>
      </>
    )
  }

  const { objectiveText, criterion, state, progress, steps } = path.data
  const mastery = asMastery[state]
  const done = progress.answered === progress.total
  return (
    <>
      <div className={styles.heading}>
        <h1>Review: objective {objectiveId}</h1>
        {mastery && <MasteryStatus mastery={mastery} />}
      </div>
      <p className={styles.lead}>{objectiveText}</p>
      <p className={styles.muted}>To meet it: {criterion}</p>
      <p className={styles.progress}>
        {done
          ? 'You have answered every fresh question, so your result above is up to date.'
          : `Fresh questions answered: ${progress.answered} of ${progress.total}. Your result updates when you have answered them all.`}
      </p>

      <Card>
        <ol className={styles.steps}>
          {steps.map((step) => (
            <Step key={step.id} step={step} objectiveId={objectiveId} />
          ))}
        </ol>
      </Card>

      <Link to="/report" className={buttonVariants({ variant: 'ghost', size: 'sm' })}>
        Back to your report
      </Link>
    </>
  )
}
