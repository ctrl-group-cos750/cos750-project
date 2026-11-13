/** Only the mastery check (module 6) is ever locked; `tested_out` is a module the student passed
 * the quick check for instead of working through it (#214). */
export type ModuleStatus = 'locked' | 'open' | 'in_progress' | 'complete' | 'tested_out'

/** A module's quick check for this student (FR-8.2, #214); absent for a module without one. */
export type QuickCheckState = 'available' | 'passed' | 'not_passed'

export type SegmentKind = 'video' | 'text' | 'worked_example' | 'activity' | 'refresher'

/** Matches `ModuleOut` from `GET /api/modules` and `GET /api/modules/{id}`. */
export type ModuleSummary = {
  id: number
  number: number
  slug: string
  title: string
  /** "By the end of this module you can …": one sentence per goal (FR-2.3). */
  goals: string[]
  estimatedMinutes: number
  status: ModuleStatus
  segmentCount: number
  /** The furthest segment the student has reached, 0-based: where the module resumes. */
  currentSegmentPosition: number
  /** How many segments this student is shown: `segmentCount` less the support they don't need
   * (FR-8.4). The map's minutes count these. */
  shownSegmentCount?: number
  /** How many of the segments shown come before `currentSegmentPosition`. */
  shownSegmentsPassed?: number
  /** The one module the map recommends next: the first in order not done (#214). */
  recommended?: boolean
  /** The module's quick check, for the "Already know this?" offer (FR-8.2, #214). */
  quickCheck?: QuickCheckState | null
}

/** Matches `SegmentOut` nested inside `ModuleDetailOut`. */
export type Segment = {
  id: number
  position: number
  kind: SegmentKind
  title: string
  body: string | null
  videoId: number | null
  activityId: number | null
  /** Support for this objective (FR-8.4): only shown to a student struggling with it here. */
  supportFor?: number | null
  /** False for support this student doesn't need: it keeps its position but is skipped. */
  shown?: boolean
  /** The student has done it and can move past it (FR-2.7): its activity answered at least
   * once, or every checkpoint of its video passed. Always true for every other kind. */
  done: boolean
  /** The student has answered its activity at least once, right or wrong. */
  attempted?: boolean
  /** An optional bonus quest (FR-8.3): done whether or not it is answered, so it never holds
   * Next back. */
  optional?: boolean
  /** Done without a right answer (two tries, or after the last hint): the student may move on,
   * and it is marked to look at again (FR-2.7, #214). */
  lookAgain?: boolean
}

/** A retrieval question the module asks before its segments (FR-2.4). */
export type RetrievalActivity = {
  id: number
  title: string
  /** The student has already made an attempt at it, so a later visit skips it. */
  answered: boolean
}

/** Matches `ModuleDetailOut` from `GET /api/modules/{id}` and `POST /api/modules/{id}/position`. */
export type ModuleDetail = ModuleSummary & {
  segments: Segment[]
  retrieval: RetrievalActivity[]
}

/** One quick check question: multiple choice, no hints, nothing marked until the end. */
export type QuickCheckQuestion = {
  id: number
  title: string
  prompt: string
  options: { id: string; label: string }[]
}

export type QuickCheckItemResult = {
  activityId: number
  title: string
  prompt: string
  correct: boolean
  chosen: string
  answer: string
  explanation: string
}

/** How the quick check went (`QuickCheckResultOut`). */
export type QuickCheckResult = {
  passed: boolean
  correct: number
  total: number
  suggestion: 'move_on' | 'start_with' | 'work_through'
  suggestedModule: number | null
  lookAt: string[]
  items: QuickCheckItemResult[]
}

/** `GET /api/modules/{id}/quick-check`. */
export type QuickCheck = {
  moduleId: number
  available: boolean
  passMark: number
  questions: QuickCheckQuestion[]
  result?: QuickCheckResult | null
}
