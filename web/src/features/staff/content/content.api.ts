import { api, ApiError, OFFLINE_MESSAGE } from '../../../api/client.ts'
import type { components } from '../../../api/schema.d.ts'

/**
 * The staff content editor's API (api/app/routers/staff_content.py). Content lives in the
 * database: the repository's fixtures seed it, and an item staff save here is marked "edited", so
 * the next deploy's seed leaves it as it is. Every save is checked with the same rules CI runs on
 * the fixtures; a broken one comes back as a 422 whose message names the problem.
 */

type Schemas = components['schemas']
export type ContentOverview = Schemas['EditorContentOverview']
export type ObjectiveIn = Schemas['EditorObjectiveIn']
export type ObjectiveOut = Schemas['EditorObjectiveOut']
export type SegmentIn = Schemas['EditorSegmentIn']
export type ModuleIn = Schemas['EditorModuleIn']
export type ModuleOut = Schemas['EditorModuleOut']
export type ReviewPathOut = Schemas['EditorReviewPathOut']
export type ActivityIn = Schemas['EditorActivityIn']
export type ActivityOut = Schemas['EditorActivityOut']
export type GraphIn = Schemas['EditorGraphIn']
export type GraphOut = Schemas['EditorGraphOut']
export type SegmentKind = SegmentIn['kind']
export type ActivityKind = ActivityIn['kind']
export type Purpose = NonNullable<ActivityIn['purpose']>

/** The kinds of item "Use the repository's version" works on, as the API's path names them. */
export type ItemKind = 'objectives' | 'modules' | 'review-paths' | 'activities' | 'graphs'

const BASE = '/api/staff/content'

/** The overview's query key; every save invalidates ['staff', 'content'], which covers it. */
export const OVERVIEW_KEY = ['staff', 'content', 'overview']

export const getOverview = () => api<ContentOverview>(BASE)

export const saveObjective = (id: number | undefined, body: ObjectiveIn) =>
  id === undefined
    ? api<ObjectiveOut>(`${BASE}/objectives`, { method: 'POST', body })
    : api<ObjectiveOut>(`${BASE}/objectives/${id}`, { method: 'PUT', body })

export const getModule = (id: number) => api<ModuleOut>(`${BASE}/modules/${id}`)
export const saveModule = (id: number | undefined, body: ModuleIn) =>
  id === undefined
    ? api<ModuleOut>(`${BASE}/modules`, { method: 'POST', body })
    : api<ModuleOut>(`${BASE}/modules/${id}`, { method: 'PUT', body })
export const deleteModule = (id: number) =>
  api<undefined>(`${BASE}/modules/${id}`, { method: 'DELETE' })

export const getReviewPath = (objectiveId: number) =>
  api<ReviewPathOut>(`${BASE}/review-paths/${objectiveId}`)
export const saveReviewPath = (objectiveId: number, segments: SegmentIn[]) =>
  api<ReviewPathOut>(`${BASE}/review-paths/${objectiveId}`, {
    method: 'PUT',
    body: { segments },
  })

export const getActivity = (id: number) => api<ActivityOut>(`${BASE}/activities/${id}`)
export const saveActivity = (id: number | undefined, body: ActivityIn) =>
  id === undefined
    ? api<ActivityOut>(`${BASE}/activities`, { method: 'POST', body })
    : api<ActivityOut>(`${BASE}/activities/${id}`, { method: 'PUT', body })
export const deleteActivity = (id: number) =>
  api<{ deleted: boolean }>(`${BASE}/activities/${id}`, { method: 'DELETE' })

export const getGraph = (id: number) => api<GraphOut>(`${BASE}/graphs/${id}`)
export const saveGraph = (id: number | undefined, body: GraphIn) =>
  id === undefined
    ? api<GraphOut>(`${BASE}/graphs`, { method: 'POST', body })
    : api<GraphOut>(`${BASE}/graphs/${id}`, { method: 'PUT', body })
export const deleteGraph = (id: number) =>
  api<undefined>(`${BASE}/graphs/${id}`, { method: 'DELETE' })

export const restoreRepositoryVersion = (kind: ItemKind, id: number) =>
  api<undefined>(`${BASE}/${kind}/${id}/use-repository`, { method: 'POST', body: {} })

/** Downloads every piece of content as fixture files (a zip laid out like api/app/seed). */
export async function downloadFixtures(): Promise<void> {
  let res: Response
  try {
    res = await fetch(`${BASE}/export`, { credentials: 'same-origin' })
  } catch {
    throw new ApiError(0, OFFLINE_MESSAGE)
  }
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as { detail?: unknown } | null
    const detail = typeof body?.detail === 'string' ? body.detail : 'The export failed.'
    throw new ApiError(res.status, detail)
  }
  const url = URL.createObjectURL(await res.blob())
  const a = document.createElement('a')
  a.href = url
  a.download = 'content-fixtures.zip'
  a.click()
  URL.revokeObjectURL(url)
}

export const SEGMENT_KINDS: { value: SegmentKind; label: string }[] = [
  { value: 'text', label: 'Text' },
  { value: 'video', label: 'Video' },
  { value: 'activity', label: 'Activity' },
  { value: 'worked_example', label: 'Worked example' },
  { value: 'refresher', label: 'Refresher (module 0)' },
]

export const ACTIVITY_KINDS: { value: ActivityKind; label: string }[] = [
  { value: 'multiple_choice', label: 'Multiple choice' },
  { value: 'matching', label: 'Matching' },
  { value: 'parsons', label: 'Parsons (order the lines)' },
  { value: 'fill_in', label: 'Fill in the blanks' },
  { value: 'trace', label: 'Trace BFS' },
  { value: 'fix_the_bug', label: 'Fix the bug' },
  { value: 'choose_tests', label: 'Choose tests' },
]

export const PURPOSES: { value: Purpose; label: string }[] = [
  { value: 'practice', label: 'Practice' },
  { value: 'retrieval', label: 'Retrieval (start of a module)' },
  { value: 'diagnostic', label: 'Diagnostic (module 0)' },
  { value: 'mastery', label: 'Mastery item (module 6 or a review path)' },
  { value: 'review', label: 'Review practice (review path)' },
  { value: 'bonus', label: 'Bonus quest' },
]
