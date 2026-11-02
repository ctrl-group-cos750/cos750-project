export type Checkpoint = {
  id: number
  atSeconds: number
  activityId: number
}

export type VideoMetadata = {
  id: number
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

export type Hint = {
  level: number
  body: string
}
