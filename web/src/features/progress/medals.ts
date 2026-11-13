import type { Medal as MedalTier } from './skills.api.ts'

/** What each medal means (api/app/services/skills.py `medal_for`): for mastery, never effort,
 * attempts' speed or time. Shown with the medal, so the criteria are never hidden. */
export const MEDAL_RULES: Record<MedalTier, string> = {
  gold: 'every activity right first time, without hint 3 or 4',
  silver: 'every activity right without hint 3 or 4',
  finished: 'the module finished, with at least one activity right without hint 3 or 4',
}

export const MEDAL_NAMES: Record<MedalTier, string> = {
  gold: 'Gold',
  silver: 'Silver',
  finished: 'Finished',
}

/** "Gold medal: every activity right first time, without hint 3 or 4." */
export function medalText(tier: MedalTier): string {
  return `${MEDAL_NAMES[tier]} medal: ${MEDAL_RULES[tier]}`
}
