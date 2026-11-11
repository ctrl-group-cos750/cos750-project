import type { Checkpoint } from './video.types.ts'

type ReachedCheckpointInput = {
  checkpoints: readonly Checkpoint[]
  passedIds: ReadonlySet<number>
  currentSeconds: number
}

type SeekInput = {
  checkpoints: readonly Checkpoint[]
  passedIds: ReadonlySet<number>
  targetSeconds: number
}

export function findReachedCheckpoint(input: ReachedCheckpointInput): Checkpoint | undefined {
  return input.checkpoints.find(
    (checkpoint) =>
      checkpoint.atSeconds <= input.currentSeconds && !input.passedIds.has(checkpoint.id),
  )
}

export function findFirstUnansweredCheckpoint(
  input: Omit<SeekInput, 'targetSeconds'>,
): Checkpoint | undefined {
  return input.checkpoints.find((checkpoint) => !input.passedIds.has(checkpoint.id))
}

export function canSeek(input: SeekInput): boolean {
  const checkpoint = findFirstUnansweredCheckpoint(input)
  return checkpoint === undefined || input.targetSeconds <= checkpoint.atSeconds
}
