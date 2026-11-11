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
  /** The student has done it and can move past it (FR-2.7): its activity answered at least
   * once, or every checkpoint of its video passed. Always true for every other kind. */
  done: boolean
}

/** Matches `ModuleDetailOut` from `GET /api/modules/{id}` and `POST /api/modules/{id}/position`. */
export type ModuleDetail = ModuleSummary & {
  segments: Segment[]
}
