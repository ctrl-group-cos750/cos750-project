import { api } from '../../api/client.ts'
import type { AttemptInput, AttemptResult, Hint } from './video.types.ts'

export function submitCheckpointAttempt(input: AttemptInput): Promise<AttemptResult> {
  return api<AttemptResult>(`/api/activities/${input.activityId}/attempts`, {
    method: 'POST'
    body: { answer: input.answer },
  })
}

export function requestCheckpointHint(input: { activityId: number }): Promise<Hint> {
  return api<Hint>(`/api/activities/${input.activityId}/hints`, {
    method: 'POST',
  })
}
