import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router'
import { buttonVariants } from '@/components/ui/button-variants'
import { Alert, Card, MasteryStatus, Spinner, Tag, type Mastery } from '../../components'
import { fetchModules } from '../module/module.api.ts'
import { useReport } from './hooks.ts'
import type { ObjectiveReport, ObjectiveState } from './mastery.api.ts'
import styles from './ReportPage.module.css'

// The mastery check (api/app/services/mastery.py MASTERY_MODULE); the report's wording names it.
const MASTERY_MODULE = 6

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
      // Module 6 is marked as a whole, once every question in it is answered (#144).
      if (o.answered === o.total)
        return 'All its questions are answered. Its result shows when you finish the mastery check.'
      if (o.answered > 0) return `${o.answered} of ${o.total} questions answered in module 6.`
      return 'Not answered yet: its questions are in module 6, the mastery check.'
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

const countObjectives = (n: number) => `${n} objective${n === 1 ? '' : 's'}`

/** Ready, or what stands in the way: every objective still "not yet" (to review) and every one
 * not attempted (still to answer in module 6), so neither hides the other (#136 review). */
function summary(objectives: ObjectiveReport[], ready: boolean, checkOpen: boolean): string {
  if (ready) return 'Ready for the lecture'
  const notYet = objectives.filter((o) => o.state === 'not_yet').length
  const toAnswer = objectives.filter((o) => o.state === 'not_attempted' && o.total > 0).length
  const left = [
    notYet > 0 ? `${countObjectives(notYet)} to review` : '',
    toAnswer > 0
      ? `${countObjectives(toAnswer)} to answer in module 6${checkOpen ? '' : ', once you reach it'}`
      : '',
  ].filter(Boolean)
  return left.length > 0
    ? `Not ready yet: ${left.join(' and ')}`
    : 'Not ready yet: finish the mastery check'
}

/** The way into module 6 for an objective whose mastery questions aren't all answered, shown only
 * once module 6 is open to the student (a locked module would only refuse them). The module page
 * opens at the first segment the student passed without doing, so this lands on them. */
function MasteryCheckLink({ o, moduleId }: { o: ObjectiveReport; moduleId: number | null }) {
  if (moduleId === null || o.state !== 'not_attempted' || o.total === 0) return null
  return (
    <Link
      to={`/modules/${moduleId}`}
      className={buttonVariants({ variant: 'secondary', size: 'sm' })}
    >
      {o.answered === o.total
        ? 'Finish the mastery check in module 6'
        : o.answered > 0
          ? 'Finish its questions in module 6'
          : 'Answer its questions in module 6'}
      <span className="sr-only">: objective {o.id}</span>
    </Link>
  )
}

/**
 * /report — the student's mastery report: each objective's result in plain words, with what to do
 * next, and whether they are ready for the lecture (FR-7.3, FR-7.4). Never hidden, even when
 * points and badges are (FR-9.5).
 */
export function ReportPage() {
  const report = useReport()
  // Whether the mastery check is open to this student, from the module list the map already uses.
  const modules = useQuery({ queryKey: ['modules'], queryFn: fetchModules })
  const check = modules.data?.find((m) => m.number === MASTERY_MODULE)
  const checkId = check && check.status !== 'locked' ? check.id : null

  if (report.isPending) return <Spinner label="Loading your report" />
  if (report.isError) return <Alert tone="danger">{report.error.message}</Alert>

  const { ready, objectives } = report.data
  return (
    <>
      <div className={styles.heading}>
        <h1>Your mastery report</h1>
        <p className={styles.summary} data-ready={ready}>
          {summary(objectives, ready, modules.isPending || checkId !== null)}
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
                <MasteryCheckLink o={o} moduleId={checkId} />
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
