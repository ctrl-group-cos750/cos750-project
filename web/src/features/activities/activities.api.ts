import { api } from '../../api/client.ts'
import type { Activity, AttemptResult, Hint, Submission } from './activities.types.ts'

/** Fetches an activity configuration. The API deliberately omits its solution. */
export function fetchActivity(activityId: number): Promise<Activity> {
  return api<Activity>(`/api/activities/${activityId}`)
}

/** Sends only the student's choices (a line order, tokens, an option or pairs), never
 * student-authored executable code. */
export function submitActivityAttempt(
  activityId: number,
  submitted: Submission,
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
