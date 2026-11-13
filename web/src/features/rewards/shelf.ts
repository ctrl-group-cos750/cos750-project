import { ACHIEVEMENTS, type Achievement, type AchievementState } from '../../components'
import type { Skill } from '../progress/skills.api.ts'
import type { EarnedBadge } from './rewards.api.ts'

/** One badge on the shelf or in an announcement: the catalogue entry and where the student is. */
export type ShelfItem = {
  key: string
  achievement: Achievement
  state: AchievementState
  /** What it is called on screen; a quest badge names its quest. */
  title: string
  /** How to earn it while it is locked, or what the next level needs. Never a reproach. */
  next?: string
  /** A practised objective badge whose objective the mastery check said "not yet" for (#214):
   * its review path, once open. */
  review?: number
  earned?: EarnedBadge
}

/** "module 3", "modules 2 and 4", "modules 1, 2 and 5". */
export function modulesText(modules: readonly number[]): string {
  if (modules.length === 1) return `module ${modules[0]}`
  return `modules ${modules.slice(0, -1).join(', ')} and ${modules[modules.length - 1]}`
}

const howToEarn: Record<string, string> = {
  'ready-for-lecture': 'Meet every objective, with or without support.',
  'came-back-stronger': 'Meet an objective through its review path.',
  'solo-run': 'Meet every objective on your own, without hint 3 or 4.',
  quest: 'Finish a bonus quest.',
  'all-quests': 'Finish the bonus quests you have left.',
  'first-module': 'Finish a module with at least one answer right before hint 3.',
}

function stateOf(achievement: Achievement, earned?: EarnedBadge): AchievementState {
  if (!earned) return 'locked'
  if (achievement.kind === 'objective') {
    if (earned.tier === 'gold') return 'gold'
    return earned.tier === 'practised' ? 'practised' : 'bronze'
  }
  return 'earned'
}

/**
 * A quest badge is numbered by the quest's place in the course ("Quest 1" is always the module 3
 * quest), which the server sends, so a badge never changes name when another quest is finished
 * first (13 Nov audit). A quest no longer in the course falls back to the order the student earned.
 */
function questNumbers(earned: EarnedBadge[]): Map<string, number> {
  const quests = earned
    .filter((e) => e.badge === 'quest')
    .sort((a, b) => Number(a.ref) - Number(b.ref) || a.ref.localeCompare(b.ref))
  return new Map(quests.map((e, index) => [e.ref, e.questNumber ?? index + 1]))
}

function item(
  achievement: Achievement,
  earned?: EarnedBadge,
  number?: number,
  skill?: Skill,
): ShelfItem {
  const state = stateOf(achievement, earned)
  const title =
    achievement.id === 'quest' && earned && number !== undefined
      ? `Quest ${number}`
      : achievement.name
  let next: string | undefined
  let review: number | undefined
  if (state === 'locked') {
    // Objective badges: practised first, in the modules that practise the objective (#214);
    // once practice can no longer make it secure (only a first answer counts, FR-9.6), the
    // mastery check is where it is earned, so it never sends the student to practise in vain.
    next =
      achievement.kind === 'objective'
        ? skill?.improve?.kind === 'check'
          ? 'Only a first answer counts, so practice can no longer make it secure. Meet it in the mastery check in module 6.'
          : skill?.modules?.length
            ? `Practise it in ${modulesText(skill.modules)} until it is secure.`
            : `Practise learning objective ${achievement.objective} in the modules until it is secure.`
        : howToEarn[achievement.id]
  } else if (state === 'practised') {
    if (skill?.result === 'not_yet') {
      next = 'Practised; not yet met in the check.'
      if (skill.improve?.kind === 'review') review = skill.id
    } else {
      // Module 6 stops at hint 2, so meeting an objective there is always gold; bronze (met with
      // support, hint 3) only comes from a review path (#222 review, A2).
      next =
        'Next: gold when you meet it in the mastery check. If the check says not yet, its review path gives bronze, or gold without hint 3.'
    }
  } else if (state === 'bronze') {
    next = 'Met with support. Gold is for meeting it without hint 3 or 4.'
  }
  return {
    key: earned ? `${achievement.id}:${earned.ref}` : achievement.id,
    achievement,
    state,
    title,
    next,
    review,
    earned,
  }
}

/** Whether an objective was met with support (its badge bronze): Solo Run can't come then. */
function soloRunOutOfReach(earned: EarnedBadge[]): boolean {
  return earned.some((e) => /^lo\d+$/.test(e.badge) && e.tier === 'bronze')
}

/**
 * Every badge the student can see, earned or not, grouped for the shelf. Unearned badges show how
 * to earn them, so the shelf doubles as a map of the objectives; the hidden one stays a "?".
 * Quests get one badge each, so there is one card per quest finished, or a single locked one.
 * A badge the course can't award yet (`offered: false`) is left off unless the student has it.
 * With the skill profile (`skills`), an objective badge says which modules practise it and, once
 * the mastery check said "not yet", links its review path (#214).
 */
export function buildShelf(earned: EarnedBadge[], skills: readonly Skill[] = []) {
  const held = (id: string) => earned.filter((e) => e.badge === id)
  const groups: Record<'objective' | 'milestone' | 'quest' | 'hidden', ShelfItem[]> = {
    objective: [],
    milestone: [],
    quest: [],
    hidden: [],
  }
  const numbers = questNumbers(earned)
  for (const achievement of ACHIEVEMENTS) {
    const mine = held(achievement.id)
    if (achievement.offered === false && mine.length === 0) continue
    // Solo Run needs every objective met without hint 3 or 4; an objective met with support
    // (bronze) stays so, so once one is, it can't be earned and isn't offered (13 Nov review).
    if (achievement.id === 'solo-run' && mine.length === 0 && soloRunOutOfReach(earned)) continue
    const order = (e: EarnedBadge) => numbers.get(e.ref) ?? 0
    mine.sort((a, b) => order(a) - order(b))
    const skill = skills.find((x) => x.id === achievement.objective)
    const items =
      mine.length > 0
        ? mine.map((e) => item(achievement, e, numbers.get(e.ref), skill))
        : [item(achievement, undefined, undefined, skill)]
    groups[achievement.kind].push(...items)
  }
  return groups
}

/** Badges earned (or raised a level) that the student has not been shown yet. */
export function unseen(earned: EarnedBadge[]): ShelfItem[] {
  const numbers = questNumbers(earned)
  return earned
    .filter((e) => !e.seen)
    .flatMap((e) => {
      const achievement = ACHIEVEMENTS.find((a) => a.id === e.badge)
      return achievement ? [item(achievement, e, numbers.get(e.ref))] : []
    })
}
