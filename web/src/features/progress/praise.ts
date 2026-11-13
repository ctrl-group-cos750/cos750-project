import type { Skill } from './skills.api.ts'

/**
 * The line shown under a correct answer (#214). Calm and specific, never effusive: no
 * exclamation marks, no "Amazing", nothing that talks down to a university student. The line is
 * picked from the result's id, so it stays the same when the page renders again, and varies from
 * one answer to the next.
 */
const ON_YOUR_OWN = [
  'That’s it, worked out on your own.',
  'Right. You’ve got the idea.',
  'Spot on.',
  'Nicely reasoned.',
  'Correct, and without the step-by-step hints.',
  'That’s the one. On to the next step.',
] as const

// After hint 3 or 4: it still counts, and saying so plainly is more honest than more praise.
const WITH_SUPPORT = [
  'Right. The hints got you there, and now you’ve done it once.',
  'Correct. Try the next one with fewer hints.',
  'That’s it. Worth coming back to this one later.',
] as const

export function praiseFor(resultId: number, hintLevel: number): string {
  const lines = hintLevel >= 3 ? WITH_SUPPORT : ON_YOUR_OWN
  return lines[Math.abs(resultId) % lines.length]
}

export const PRAISE_LINES: readonly string[] = [...ON_YOUR_OWN, ...WITH_SUPPORT]

/** A short remark on the student's progress, from the skill profile: how many objectives they
 * have practised, or that one is now secure. Plain counts, never a comparison with anyone. */
export function progressRemark(skills: readonly Skill[]): string | null {
  if (skills.length === 0) return null
  const practised = skills.filter((s) => s.level !== 'not_started').length
  const secure = skills.filter((s) => s.level === 'secure').length
  if (practised === 0) return null
  if (practised === skills.length && secure > 0)
    return `Every objective practised, ${secure} of ${skills.length} secure.`
  return `You've practised ${practised} of ${skills.length} objectives so far.`
}
