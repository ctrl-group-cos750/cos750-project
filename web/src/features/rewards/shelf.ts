import { ACHIEVEMENTS, type Achievement, type AchievementState } from '../../components'
import type { EarnedBadge } from './rewards.api.ts'

/** One badge on the shelf or in an announcement: the catalogue entry and where the student is. */
export type ShelfItem = {
  key: string
  achievement: Achievement
  state: AchievementState
  /** What it is called on screen; a quest badge names its quest. */
  title: string
  /** How to earn it while it is locked, or how to raise bronze to gold. Never a reproach. */
  next?: string
  earned?: EarnedBadge
}

const howToEarn: Record<string, string> = {
  'ready-for-lecture': 'Meet every objective, with or without support.',
  'came-back-stronger': 'Meet an objective through its review path.',
  'solo-run': 'Meet your bronze objectives again on your own.',
  quest: 'Finish a bonus quest.',
  'all-quests': 'Finish the bonus quests you have left.',
  'off-the-map': 'Keep exploring.',
}

function stateOf(achievement: Achievement, earned?: EarnedBadge): AchievementState {
  if (!earned) return 'locked'
  if (achievement.kind === 'objective') return earned.tier === 'gold' ? 'gold' : 'bronze'
  return 'earned'
}

function item(achievement: Achievement, earned?: EarnedBadge): ShelfItem {
  const state = stateOf(achievement, earned)
  const title = achievement.id === 'quest' && earned ? `Quest ${earned.ref}` : achievement.name
  let next: string | undefined
  if (state === 'locked') {
    next =
      achievement.kind === 'objective'
        ? `Meet learning objective ${achievement.objective}.`
        : howToEarn[achievement.id]
  } else if (state === 'bronze') {
    next = 'Meet it again on your own for gold.'
  }
  return {
    key: earned ? `${achievement.id}:${earned.ref}` : achievement.id,
    achievement,
    state,
    title,
    next,
    earned,
  }
}

/**
 * Every badge the student can see, earned or not, grouped for the shelf. Unearned badges show how
 * to earn them, so the shelf doubles as a map of the objectives; the hidden one stays a "?".
 * Quests get one badge each, so there is one card per quest finished, or a single locked one.
 * A badge the course can't award yet (`offered: false`) is left off unless the student has it.
 */
export function buildShelf(earned: EarnedBadge[]) {
  const held = (id: string) => earned.filter((e) => e.badge === id)
  const groups: Record<'objective' | 'milestone' | 'quest' | 'hidden', ShelfItem[]> = {
    objective: [],
    milestone: [],
    quest: [],
    hidden: [],
  }
  for (const achievement of ACHIEVEMENTS) {
    const mine = held(achievement.id)
    if (achievement.offered === false && mine.length === 0) continue
    const items = mine.length > 0 ? mine.map((e) => item(achievement, e)) : [item(achievement)]
    groups[achievement.kind].push(...items)
  }
  return groups
}

/** Badges earned (or raised to gold) that the student has not been shown yet. */
export function unseen(earned: EarnedBadge[]): ShelfItem[] {
  return earned
    .filter((e) => !e.seen)
    .flatMap((e) => {
      const achievement = ACHIEVEMENTS.find((a) => a.id === e.badge)
      return achievement ? [item(achievement, e)] : []
    })
}
