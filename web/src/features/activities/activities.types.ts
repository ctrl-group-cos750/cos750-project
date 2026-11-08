/** Public activity data only. Answers and solutions are intentionally never modelled in the UI. */
export type PartResult = {
  /** Position for a Parsons line, the blank number for fill-in code, the left item's index for
   * matching, or 0 for multiple choice. */
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

export type MultipleChoiceActivity = {
  id: number
  kind: 'multiple_choice'
  title: string
  visible: boolean
  config: { prompt: string; options: readonly { id: string; label: string }[] }
}

export type MatchingActivity = {
  id: number
  kind: 'matching'
  title: string
  visible: boolean
  /** `right` may hold more choices than `left`, and one right item may fit several left items. */
  config: {
    prompt: string
    left: readonly { id: string; label: string }[]
    right: readonly { id: string; label: string }[]
  }
}

export type Activity = CodeActivity | MultipleChoiceActivity | MatchingActivity

/** What a student submits for each kind: their choices only, never code or the answer. */
export type Submission =
  | { order: number[] }
  | { answers: Record<number, string> }
  | { selected: string }
  | { pairs: Record<string, string> }
