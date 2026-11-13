import type { Medal as MedalTier } from './skills.api.ts'

/** What each medal means (api/app/services/skills.py `medal_for`): for mastery, never effort,
 * attempts' speed or time. Shown with the medal, so the criteria are never hidden. */
export const MEDAL_RULES: Record<MedalTier, string> = {
  gold: 'every activity right first time, without a hint',
  silver: 'every activity right first time, without hint 3 or 4',
  finished: 'at least one activity right on your own',
}

export const MEDAL_NAMES: Record<MedalTier, string> = {
  gold: 'Gold',
  silver: 'Silver',
  finished: 'Finished',
}

/** "Gold medal: every activity right first time, without a hint." Only a first attempt counts
 * (the evidence rule, FR-9.6), so the levels differ by the hints used before it. */
export function medalText(tier: MedalTier): string {
  return `${MEDAL_NAMES[tier]} medal: ${MEDAL_RULES[tier]}`
}
