import { describe, expect, it } from 'vitest'
import type { Segment } from './module.types.ts'
import {
  nearestShown,
  nextShown,
  previousShown,
  shownPlace,
  supportIntro,
} from './shownSegments.ts'

function seg(id: number, shown = true, supportFor: number | null = null): Segment {
  return {
    id,
    position: id,
    kind: 'text',
    title: `S${id}`,
    body: 'x',
    videoId: null,
    activityId: null,
    done: true,
    shown,
    supportFor,
  }
}

// Base, base, two hidden support segments, base: the confident student's view.
const hidden = [seg(0), seg(1), seg(2, false, 6), seg(3, false, 6), seg(4)]
// The same module for a student who gets the support.
const shown = [seg(0), seg(1), seg(2, true, 6), seg(3, true, 6), seg(4)]

describe('shown segments (FR-8.4)', () => {
  it('steps over hidden support both ways', () => {
    expect(nextShown(hidden, 1)).toBe(4)
    expect(previousShown(hidden, 4)).toBe(1)
    expect(nextShown(shown, 1)).toBe(2)
    expect(nextShown(hidden, 4)).toBe(-1)
    expect(previousShown(hidden, 0)).toBe(-1)
  })

  it('never opens on a hidden segment', () => {
    expect(nearestShown(hidden, 2)).toBe(4)
    expect(nearestShown(hidden, 1)).toBe(1)
    expect(nearestShown([seg(0), seg(1, false, 2)], 1)).toBe(0) // nothing shown after it
    expect(nearestShown(hidden, 99)).toBe(4)
  })

  it('counts only the shown segments in "Segment N of M"', () => {
    expect(shownPlace(hidden, 4)).toEqual({ number: 3, total: 3 })
    expect(shownPlace(shown, 4)).toEqual({ number: 5, total: 5 })
  })

  it('opens a run of support with one kind line, and says nothing else', () => {
    expect(supportIntro(shown, 2)).toMatch(/another way/)
    expect(supportIntro(shown, 2)).not.toMatch(/fail|wrong|mistake/i)
    expect(supportIntro(shown, 3)).toBeNull() // the same run
    expect(supportIntro(shown, 1)).toBeNull()
    expect(supportIntro(hidden, 2)).toBeNull()
    // A run for another objective straight after gets its own line.
    expect(supportIntro([seg(0), seg(1, true, 5), seg(2, true, 6)], 2)).toMatch(/another way/)
  })

  it('treats a segment from an API that doesn’t say as shown', () => {
    const plain: Segment = { ...seg(0), shown: undefined, supportFor: undefined }
    expect(nextShown([seg(9), plain], 0)).toBe(1)
    expect(supportIntro([plain], 0)).toBeNull()
  })
})
