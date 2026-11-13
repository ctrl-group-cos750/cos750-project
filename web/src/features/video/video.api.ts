import { api } from '../../api/client.ts'
import type { AttemptInput, AttemptResult, Hint, LoadedVideo } from './video.types.ts'

/** `GET /api/videos/{id}` as the API sends it (api/app/schemas/videos.py). */
type VideoOut = {
  id: number
  title: string
  mediaPath: string
  captionsPath: string
  transcript: string
  durationSeconds: number
  checkpoints: {
    id: number
    atSeconds: number
    passed: boolean
    activity: {
      id: number
      kind: string
      config: { prompt: string; options: { id: string; label: string }[] }
    }
  }[]
}

/** Loads a video with its checkpoints' questions (never their answers) for the player. */
export async function fetchVideo(id: number): Promise<LoadedVideo> {
  const v = await api<VideoOut>(`/api/videos/${id}`)
  return {
    video: {
      id: v.id,
      title: v.title,
      mediaPath: v.mediaPath,
      captionsPath: v.captionsPath,
      transcript: v.transcript,
      checkpoints: v.checkpoints.map((c) => ({
        id: c.id,
        atSeconds: c.atSeconds,
        activityId: c.activity.id,
      })),
    },
    activities: Object.fromEntries(
      v.checkpoints.map((c) => [
        c.activity.id,
        { id: c.activity.id, prompt: c.activity.config.prompt, options: c.activity.config.options },
      ]),
    ),
    passedIds: v.checkpoints.filter((c) => c.passed).map((c) => c.id),
  }
}

/** Checks the answer on the server and records the attempt (FR-3.4, FR-4.2). */
export async function submitCheckpointAttempt(input: AttemptInput): Promise<AttemptResult> {
  const result = await api<AttemptResult>(`/api/activities/${input.activityId}/attempts`, {
    method: 'POST',
    body: { submitted: { selected: input.answer.selectedOptionId } },
  })
  return { correct: result.correct, feedback: result.feedback }
}

/** Reveals the next hint level. Rejects (409) once every level has been shown. */
export function requestCheckpointHint(input: { activityId: number }): Promise<Hint> {
  return api<Hint>(`/api/activities/${input.activityId}/hints`, { method: 'POST' })
}
