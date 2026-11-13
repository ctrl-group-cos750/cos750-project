export type Checkpoint = {
  id: number
  atSeconds: number
  activityId: number
}

export type VideoMetadata = {
  id: number
  title: string
  mediaPath: string
  captionsPath: string
  transcript: string
  checkpoints: readonly Checkpoint[]
}

export type MultipleChoiceActivity = {
  id: number
  prompt: string
  options: readonly { id: string; label: string }[]
}

export type AttemptInput = {
  activityId: number
  answer: { selectedOptionId: string }
}

export type AttemptResult = {
  correct: boolean
  feedback: string
}

/** One rung of the hint ladder, as `POST /api/activities/{id}/hints` returns it. */
export type Hint = {
  level: number
  body: string
  /** False once the last level (the worked solution) has been shown. */
  hasMore: boolean
  /** True when the next hint is level 3 or 4: warn before asking for it (ID document §7.4). */
  nextCountsAsSupport: boolean
}

/** A video ready for the player: what to play, each checkpoint's question, and which
 * checkpoints this student has already passed (so they can seek past them). */
export type LoadedVideo = {
  video: VideoMetadata
  activities: Readonly<Record<number, MultipleChoiceActivity>>
  passedIds: readonly number[]
}
