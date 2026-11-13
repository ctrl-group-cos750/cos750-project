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

/**
 * `POST /api/modules/{moduleId}/restart` — start the module again to redo its questions: they show
 * unanswered, with hints from level 1. Points, badges and the module's completion stay.
 */
export function restartModule(moduleId: number): Promise<ModuleDetail> {
  return api<ModuleDetail>(`/api/modules/${moduleId}/restart`, { method: 'POST' })
}
