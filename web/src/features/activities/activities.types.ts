/** Public activity data only. Answers and solutions are intentionally never modelled in the UI. */
export type PartResult = {
  /** Position for a Parsons line, or the blank number for fill-in code. */
  ref: number
  correct: boolean
  message: string | null
}

export type AttemptResult = {
  id: number
  activityId: number
  correct: boolean
  score: number
  parts: readonly PartResult[]
  feedback: string
  hintLevel: number
}

export type Hint = {
  level: number
  body: string
  hasMore: boolean
  nextCountsAsSupport: boolean
}

export type ParsonsActivity = {
  id: number
  kind: 'parsons'
  title: string
  visible: boolean
  config: { lines: readonly { id: number; text: string }[] }
}

export type FillInActivity = {
  id: number
  kind: 'fill_in'
  title: string
  visible: boolean
  config: { code: string; blanks: readonly number[]; options: readonly string[] }
}

export type CodeActivity = ParsonsActivity | FillInActivity
