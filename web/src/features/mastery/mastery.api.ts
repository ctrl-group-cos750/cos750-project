import { api } from '../../api/client.ts'

/** An objective's result (FR-7.2). `not_attempted` until every module 6 item on it is answered. */
export type ObjectiveState = 'not_attempted' | 'met_independently' | 'met_with_support' | 'not_yet'

/** One objective on the report, as `GET /api/me/report` sends it (api/app/schemas/mastery.py). */
export type ObjectiveReport = {
  id: number
  text: string
  criterion: string
  state: ObjectiveState
  /** How many of its module 6 items the student has answered, of `total`. */
  answered: number
  total: number
  /** Set once module 6 marks the objective "not yet", which opens its review path (FR-7.5):
   * how many of the path's fresh questions are answered. When all are, they decide the result. */
  review: ReviewProgress | null
  /** Its module 6 questions with the student's answer marked and why, once every question in the
   * check is answered (review of 13 Nov); empty before, while the results are withheld. */
  answers?: MasteryAnswer[]
}

/** One mastery check question and how the student's (first and only) answer was marked. */
export type MasteryAnswer = {
  activityId: number
  title: string
  correct: boolean
  score: number
  /** Why it is right (the question's explanation), or the summary of what was wrong. */
  feedback: string
  /** What each wrong part said, each message once. */
  notes: string[]
  hintLevel: number
}

export type ReviewProgress = { answered: number; total: number }

export type MasteryReport = {
  /** Every objective met, with or without support (FR-7.4). */
  ready: boolean
  objectives: ObjectiveReport[]
}

/** The logged-in student's own mastery report. The server works it out from their attempts. */
export function fetchReport(): Promise<MasteryReport> {
  return api<MasteryReport>('/api/me/report')
}

/** One step of a review path (api/app/schemas/mastery.py). An activity step is practice
 * (`review`, with the full hint ladder) or a fresh question (`mastery`) that decides the result. */
export type ReviewStep = {
  id: number
  kind: 'video' | 'text' | 'worked_example' | 'activity' | 'refresher'
  title: string
  /** Markdown, for a text or worked example step. */
  body: string
  activityId: number | null
  purpose: 'review' | 'mastery' | null
  answered: boolean
  /** A fresh question that opens once the path's practice is done (review of 13 Nov). */
  locked?: boolean
}

export type ReviewPath = {
  objectiveId: number
  objectiveText: string
  criterion: string
  state: ObjectiveState
  progress: ReviewProgress
  steps: ReviewStep[]
}

/** An objective's review path. 403 until the mastery check marks the objective "not yet". */
export function fetchReviewPath(objectiveId: number): Promise<ReviewPath> {
  return api<ReviewPath>(`/api/me/review/${objectiveId}`)
}
