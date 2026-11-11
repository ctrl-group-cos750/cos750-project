import type { ModuleSummary } from './module.types.ts'

export type MinutesProgress = {
  /** Minutes of the course the student has worked through, rounded. */
  done: number
  /** Minutes of the course there is content for, rounded. */
  total: number
}

/**
 * How far through the course the student is, in the modules' estimated minutes.
 *
 * Only modules with content count towards the total: a module with no segments yet can't be
 * worked through (FR-2.1), so counting it would set a target nobody could reach. The total grows
 * as content is added. A complete module counts in full and one in progress by the share of its
 * segments the student has moved past; the content has no time per segment, so each segment of
 * a module counts the same. Only the segments shown to this student count: support they don't need
 * (FR-8.4) is neither time to spend nor time spent.
 */
export function minutesProgress(modules: readonly ModuleSummary[]): MinutesProgress {
  let done = 0
  let total = 0
  for (const m of modules) {
    if (m.segmentCount === 0 && m.status !== 'complete') continue
    total += m.estimatedMinutes
    if (m.status === 'complete') done += m.estimatedMinutes
    else if (m.status === 'in_progress') {
      const passed = m.shownSegmentsPassed ?? m.currentSegmentPosition
      const count = m.shownSegmentCount ?? m.segmentCount
      if (count > 0) done += (m.estimatedMinutes * passed) / count
    }
  }
  return { done: Math.round(done), total: Math.round(total) }
}
