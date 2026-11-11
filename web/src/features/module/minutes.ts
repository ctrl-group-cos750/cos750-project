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
 * The total is every module's estimate, the same sum the register page shows
 * (GET /api/modules/length) and the rows add up to: one number everywhere (#146). A module with no
 * content yet still counts towards it, and reads "coming soon" on the map. A complete module
 * counts in full and one in progress by the share of its segments the student has moved past;
 * the content has no time per segment, so each segment of a module counts the same.
 */
export function minutesProgress(modules: readonly ModuleSummary[]): MinutesProgress {
  let done = 0
  let total = 0
  for (const m of modules) {
    total += m.estimatedMinutes
    if (m.status === 'complete') done += m.estimatedMinutes
    else if (m.status === 'in_progress' && m.segmentCount > 0)
      done +=
        (m.estimatedMinutes * Math.min(m.currentSegmentPosition, m.segmentCount)) / m.segmentCount
  }
  return { done: Math.round(done), total: Math.round(total) }
}
