/** Public activity data only. Answers and solutions are intentionally never modelled in the UI. */
export type PartResult = {
  /** Position for a Parsons or fix-the-bug line, the blank number for fill-in code, the left
   * item's index for matching, the test case's index for choose tests, the row's index for a
   * trace table, or 0 for multiple choice. */
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
  /** This student has already answered it correctly: no more hints are offered (#158). */
  solved?: boolean
  config: { lines: readonly { id: number; text: string }[] }
}

export type FillInActivity = {
  id: number
  kind: 'fill_in'
  title: string
  visible: boolean
  /** This student has already answered it correctly: no more hints are offered (#158). */
  solved?: boolean
  config: { code: string; blanks: readonly number[]; options: readonly string[] }
}

export type CodeActivity = ParsonsActivity | FillInActivity

export type MultipleChoiceActivity = {
  id: number
  kind: 'multiple_choice'
  title: string
  visible: boolean
  /** This student has already answered it correctly: no more hints are offered (#158). */
  solved?: boolean
  config: { prompt: string; options: readonly { id: string; label: string }[] }
}

export type MatchingActivity = {
  id: number
  kind: 'matching'
  title: string
  visible: boolean
  /** This student has already answered it correctly: no more hints are offered (#158). */
  solved?: boolean
  /** `right` may hold more choices than `left`, and one right item may fit several left items. */
  config: {
    prompt: string
    left: readonly { id: string; label: string }[]
    right: readonly { id: string; label: string }[]
  }
}

/** One line of code with its id: a Parsons line, or a faulty line or correction in fix the bug. */
export type CodeLine = { id: number; text: string }

/** A graph edge as the API stores it. In an undirected graph it joins both ways. */
export type GraphEdge = { source: string; target: string }

/** Fix the bug (FR-5.5, objective 7): the faulty program in its faulty order, and the correction
 * lines the student may swap in. Line and correction ids share one namespace. */
export type FixTheBugActivity = {
  id: number
  kind: 'fix_the_bug'
  title: string
  visible: boolean
  /** This student has already answered it correctly: no more hints are offered (#158). */
  solved?: boolean
  config: { prompt: string; lines: readonly CodeLine[]; corrections: readonly CodeLine[] }
}

/** A test case for choose tests: a small graph, a start vertex and the order a correct BFS
 * visits it in. Keys are as stored (snake_case), because `config` is passed through as is. */
export type TestCase = {
  id: string
  directed?: boolean
  vertices: readonly string[]
  edges?: readonly GraphEdge[]
  start_vertex: string
  expected: readonly string[]
}

/** Choose tests (FR-5.5, objective 7): a faulty BFS and the test cases to choose from. */
export type ChooseTestsActivity = {
  id: number
  kind: 'choose_tests'
  title: string
  visible: boolean
  /** This student has already answered it correctly: no more hints are offered (#158). */
  solved?: boolean
  config: { prompt: string; code: string; tests: readonly TestCase[] }
}

/** Trace table (FR-4.1, FR-6.6, objective 5): only the graph and its start vertex. The traversal
 * is derived and checked on the server, so the answer never reaches the browser. */
export type TraceActivity = {
  id: number
  kind: 'trace'
  title: string
  visible: boolean
  /** This student has already answered it correctly: no more hints are offered (#158). */
  solved?: boolean
  config: {
    directed: boolean
    vertices: readonly string[]
    edges: readonly GraphEdge[]
    start_vertex: string
  }
}

/** One row of a submitted trace table: the vertex that left the queue at this step, and the
 * queue, visited set and order after it (the columns of module 3's worked example). */
export type TraceRow = {
  visitedVertex: string
  queue: string[]
  visited: string[]
  order: string[]
}

export type Activity =
  | CodeActivity
  | MultipleChoiceActivity
  | MatchingActivity
  | FixTheBugActivity
  | ChooseTestsActivity
  | TraceActivity

/** What a student submits for each kind: their choices only, never code or the answer. */
export type Submission =
  | { order: number[] }
  | { answers: Record<number, string> }
  | { selected: string }
  | { pairs: Record<string, string> }
  | { selected: string[] }
  | { rows: TraceRow[] }
