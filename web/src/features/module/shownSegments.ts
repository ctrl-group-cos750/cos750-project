import type { Segment } from './module.types.ts'

/**
 * Which of a module's segments this student is shown (FR-8.4, #172). Support for an objective the
 * student doesn't need stays in the list, so every segment keeps its position, but is not shown:
 * Previous and Next skip it and "Segment N of M" doesn't count it. A segment from an API that
 * doesn't say is shown.
 */
export const isShown = (segment: Segment): boolean => segment.shown !== false

/** The next segment shown after `index`, or -1 if there is none. */
export function nextShown(segments: readonly Segment[], index: number): number {
  for (let i = index + 1; i < segments.length; i++) if (isShown(segments[i])) return i
  return -1
}

/** The segment shown before `index`, or -1 if there is none. */
export function previousShown(segments: readonly Segment[], index: number): number {
  for (let i = Math.min(index, segments.length) - 1; i >= 0; i--) if (isShown(segments[i])) return i
  return -1
}

/** `index` if that segment is shown; otherwise the next one shown, or failing that the one before. */
export function nearestShown(segments: readonly Segment[], index: number): number {
  if (segments[index] !== undefined && isShown(segments[index])) return index
  const next = nextShown(segments, index)
  return next >= 0 ? next : Math.max(previousShown(segments, index), 0)
}

/** "Segment N of M" for the segment at `index`, counting only the segments shown. */
export function shownPlace(
  segments: readonly Segment[],
  index: number,
): { number: number; total: number } {
  const shown = segments.filter(isShown)
  return {
    number: segments.slice(0, index + 1).filter(isShown).length,
    total: shown.length,
  }
}

/**
 * The line that opens a run of support segments for an objective, so the student knows why the
 * extra step is there. Kind and about the content, never about the student's mistakes (ID document
 * §7: feedback that is about the task, not the person). Null for every other segment.
 */
export function supportIntro(segments: readonly Segment[], index: number): string | null {
  const segment = segments[index]
  if (segment === undefined || (segment.supportFor ?? null) === null || !isShown(segment))
    return null
  const before = previousShown(segments, index)
  if (before >= 0 && segments[before].supportFor === segment.supportFor) return null
  return 'Let’s look at this another way before you move on.'
}
