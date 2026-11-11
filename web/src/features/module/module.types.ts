export type ModuleStatus = 'locked' | 'open' | 'in_progress' | 'complete'

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
