import { api } from '../../api/client.ts'
import type { ModuleDetail, ModuleSummary, QuickCheck, QuickCheckResult } from './module.types.ts'

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

/** `GET /api/modules/{moduleId}/quick-check` — the module's quick check, or its result once taken. */
export function fetchQuickCheck(moduleId: number): Promise<QuickCheck> {
  return api<QuickCheck>(`/api/modules/${moduleId}/quick-check`)
}

/** `POST /api/modules/{moduleId}/quick-check` — one answer per question, marked together. */
export function takeQuickCheck(
  moduleId: number,
  answers: { activityId: number; selected: string }[],
): Promise<QuickCheckResult> {
  return api<QuickCheckResult>(`/api/modules/${moduleId}/quick-check`, {
    method: 'POST',
    body: { answers },
  })
}
