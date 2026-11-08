import { api } from '../../api/client.ts'
import type { ModuleDetail, ModuleSummary } from './module.types.ts'

/** `GET /api/modules` — returns the full module list with per-student status. */
export function fetchModules(): Promise<ModuleSummary[]> {
  return api<ModuleSummary[]>('/api/modules')
}

/** `GET /api/modules/{id}` — returns the module with its ordered segments. */
export function fetchModule(id: number): Promise<ModuleDetail> {
  return api<ModuleDetail>(`/api/modules/${id}`)
}

/**
 * `POST /api/modules/{moduleId}/position` — persists how far the student has reached
 * (FR-2.5) and returns the updated module detail.
 */
export function savePosition(moduleId: number, segmentPosition: number): Promise<ModuleDetail> {
  return api<ModuleDetail>(`/api/modules/${moduleId}/position`, {
    method: 'POST',
    body: { segmentPosition },
  })
}

export type RetrievalResult = { correct: boolean; feedback: string }

/** Record a retrieval response through the normal activity attempt endpoint. */
export function submitRetrieval(activityId: number, selected: string): Promise<RetrievalResult> {
  return api<RetrievalResult>(`/api/activities/${activityId}/attempts`, {
    method: 'POST',
    body: { submitted: { selected } },
  })
}
