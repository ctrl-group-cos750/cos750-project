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
}

export type MasteryReport = {
  /** Every objective met, with or without support (FR-7.4). */
  ready: boolean
  objectives: ObjectiveReport[]
}

/** The logged-in student's own mastery report. The server works it out from their attempts. */
export function fetchReport(): Promise<MasteryReport> {
  return api<MasteryReport>('/api/me/report')
}
