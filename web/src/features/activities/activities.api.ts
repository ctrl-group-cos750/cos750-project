import { api } from '../../api/client.ts'
import type { AttemptResult, CodeActivity, Hint } from './activities.types.ts'

/** Fetches an activity configuration. The API deliberately omits its solution. */
export function fetchActivity(activityId: number): Promise<CodeActivity> {
  return api<CodeActivity>(`/api/activities/${activityId}`)
}

/** Sends only a line order or token choices, never student-authored executable code. */
export function submitActivityAttempt(
  activityId: number,
  submitted: { order: number[] } | { answers: Record<number, string> },
): Promise<AttemptResult> {
  return api<AttemptResult>(`/api/activities/${activityId}/attempts`, {
    method: 'POST',
    body: { submitted },
  })
}

/** Reveals the next hint on the server-managed four-level ladder. */
export function requestActivityHint(activityId: number): Promise<Hint> {
  return api<Hint>(`/api/activities/${activityId}/hints`, { method: 'POST' })
}

/** Fetches previously unlocked hints on the server-managed ladder. */
export function fetchActivityHints(activityId: number): Promise<readonly Hint[]> {
  return api<readonly Hint[]>(`/api/activities/${activityId}/hints`)
}
