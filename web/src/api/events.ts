import { api } from './client.ts'

/** What only the browser sees, reported for the pilot's evaluation (FR-10.1). The server adds who
 * and when; `targetId` is the video, checkpoint or segment it was about. */
export type ClientEvent =
  'video_started' | 'video_completed' | 'checkpoint_reached' | 'segment_viewed'

/**
 * Report an event and carry on. Logging is for the evaluation, never for the student, so a failed
 * report (offline, rate-limited, logged out) is dropped silently and never interrupts a lesson.
 */
export function reportEvent(type: ClientEvent, targetId: number): void {
  api('/api/events', { method: 'POST', body: { type, targetId } }).catch(() => undefined)
}
