import { Link } from 'react-router'
import { buttonVariants } from '@/components/ui/button-variants'
import { Alert, Card, MasteryStatus, Spinner, Tag, type Mastery } from '../../components'
import { useReport } from './hooks.ts'
import type { ObjectiveReport, ObjectiveState } from './mastery.api.ts'
import styles from './ReportPage.module.css'

const asMastery: Partial<Record<ObjectiveState, Mastery>> = {
  met_independently: 'independent',
  met_with_support: 'supported',
  not_yet: 'not-yet',
}

/** What the result means for this student, in plain words, and what to do next (FR-7.3). */
function nextStep(o: ObjectiveReport): string {
  switch (o.state) {
    case 'met_independently':
      return reviewDone(o)
        ? 'You met this on your own after the review path.'
        : 'You met this on your own.'
    case 'met_with_support':
      return reviewDone(o)
        ? 'You met this after the review path, using hint 3 or 4.'
        : 'You met this after using hint 3 or 4.'
    case 'not_yet':
      if (reviewDone(o))
        return 'Still not yet after the review path. Bring this one to the lecture.'
      if (o.review && o.review.answered > 0)
        return `Review path: ${o.review.answered} of ${o.review.total} fresh questions answered.`
      return 'Work through its review path before the lecture.'
    case 'not_attempted':
      if (o.total === 0) return 'There are no questions on this objective yet.'
      if (o.answered > 0) return `${o.answered} of ${o.total} questions answered in module 6.`
      return 'Answer its questions in module 6, the mastery check.'
  }
}

/** The review path's fresh questions are all answered, so they decided the result. */
function reviewDone(o: ObjectiveReport): boolean {
  return o.review !== null && o.review.answered === o.review.total
}

/** The way into an open review path, worded for how far the student is through it. */
function ReviewLink({ o }: { o: ObjectiveReport }) {
  if (!o.review) return null
  const label = reviewDone(o)
    ? 'Look back at the review path'
    : o.review.answered > 0
      ? 'Continue review path'
      : 'Start review path'
  return (
    <Link
      to={`/review/${o.id}`}
      className={buttonVariants({ variant: reviewDone(o) ? 'ghost' : 'secondary', size: 'sm' })}
    >
      {label}
      <span className="sr-only">: objective {o.id}</span>
    </Link>
  )
}

function Result({ state }: { state: ObjectiveState }) {
  const mastery = asMastery[state]
  return mastery ? <MasteryStatus mastery={mastery} /> : <Tag icon="–">Not attempted</Tag>
}

function summary(objectives: ObjectiveReport[], ready: boolean): string {
  if (ready) return 'Ready for the lecture'
  const notYet = objectives.filter((o) => o.state === 'not_yet').length
  if (notYet > 0) return `Not ready yet: ${notYet} objective${notYet === 1 ? '' : 's'} to review`
  return 'Not ready yet: finish the mastery check'
}

/**
 * /report — the student's mastery report: each objective's result in plain words, with what to do
 * next, and whether they are ready for the lecture (FR-7.3, FR-7.4). Never hidden, even when
 * points and badges are (FR-9.5).
 */
export function ReportPage() {
  const report = useReport()

  if (report.isPending) return <Spinner label="Loading your report" />
  if (report.isError) return <Alert tone="danger">{report.error.message}</Alert>

  const { ready, objectives } = report.data
  return (
    <>
      <div className={styles.heading}>
        <h1>Your mastery report</h1>
        <p className={styles.summary} data-ready={ready}>
          {summary(objectives, ready)}
        </p>
      </div>

      <Card>
        <ol className={styles.objectives}>
          {objectives.map((o) => (
            <li key={o.id} className={styles.objective}>
              <span className={styles.number}>{o.id}</span>
              <div>
                <p className={styles.text}>{o.text}</p>
                <p className={styles.next}>{nextStep(o)}</p>
                <p className={styles.criterion}>To meet it: {o.criterion}</p>
                <ReviewLink o={o} />
              </div>
              <Result state={o.state} />
            </li>
          ))}
        </ol>
      </Card>

      <p className={styles.note}>
        Each question in the mastery check counts once: your first answer is the one used here.
        &ldquo;Met with support&rdquo; is fine for the lecture: you don&rsquo;t need to meet every
        objective on your own.
      </p>
    </>
  )
}
