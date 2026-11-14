import type { Medal as MedalTier } from './skills.api.ts'

/** What each medal means (api/app/services/skills.py `medal_for`): for mastery, never effort,
 * attempts' speed or time. Shown with the medal, so the criteria are never hidden. */
export const MEDAL_RULES: Record<MedalTier, string> = {
  gold: 'every first answer right, without a hint',
  silver: 'every first answer right, without hint 3 or 4',
  bronze: 'the module finished',
}

export const MEDAL_NAMES: Record<MedalTier, string> = {
  gold: 'Gold',
  silver: 'Silver',
  bronze: 'Bronze',
}

/** "Gold medal: every first answer right, without a hint." */
export function medalText(tier: MedalTier): string {
  return `${MEDAL_NAMES[tier]} medal: ${MEDAL_RULES[tier]}`
}
