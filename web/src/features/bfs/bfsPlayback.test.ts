import { describe, expect, it } from 'vitest'
import { createPlayback, playbackReducer } from './bfsPlayback.ts'

describe('BFS playback', () => {
  it('pauses for a prediction instead of advancing', () => {
    const state = createPlayback({ frameCount: 3 })

    const next = playbackReducer(state, {
      type: 'REQUEST_NEXT',
      predictionRequired: true,
    })

    expect(next.frameIndex).toBe(0)
    expect(next.phase).toBe('answering')
    expect(next.playing).toBe(false)
  })

  it('advances only after prediction feedback is acknowledged', () => {
    const state = {
      ...createPlayback({ frameCount: 3 }),
      phase: 'feedback' as const,
      feedback: { selected: 'C', correct: false, expected: 'B' },
    }

    const next = playbackReducer(state, { type: 'CONTINUE' })

    expect(next.frameIndex).toBe(1)
    expect(next.phase).toBe('ready')
  })

  it('never steps back before the initial frame', () => {
    const state = createPlayback({ frameCount: 3 })
    const next = playbackReducer(state, { type: 'BACK' })

    expect(next.frameIndex).toBe(0)
  })
})
