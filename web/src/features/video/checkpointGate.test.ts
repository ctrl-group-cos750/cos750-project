import { describe, expect, it } from 'vitest'
import { canSeek, findFirstUnansweredCheckpoint, findReachedCheckpoint } from './checkpointGate.ts'

const checkpoints = [
  { id: 1, atSeconds: 20, activityId: 101 },
  { id: 2, atSeconds: 45, activityId: 102 },
]

describe('checkpoint gate', () => {
  it('finds an unanswered checkpoint once playback reaches it', () => {
    expect(
      findReachedCheckpoint({
        checkpoints,
        passedIds: new Set(),
        currentSeconds: 20,
      }),
    ).toMatchObject({ id: 1 })
  })

  it('allows seeking backwards', () => {
    expect(
      canSeek({
        checkpoints,
        passedIds: new Set(),
        targetSeconds: 5,
      }),
    ).toBe(true)
  })

  it('blocks seeking past the first unanswered checkpoint', () => {
    expect(
      findFirstUnansweredCheckpoint({
        checkpoints,
        passedIds: new Set([1]),
      }),
    ).toMatchObject({ id: 2 })
  })
})
