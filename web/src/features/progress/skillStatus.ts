import type { ObjectiveState } from '../mastery/mastery.api.ts'
import type { Skill } from './skills.api.ts'

export type Status = {
  /** How many of the three steps are filled: practising, secure, met in the mastery check. */
  steps: 0 | 1 | 2 | 3
  text: string
  tone: 'none' | 'practice' | 'gold' | 'bronze' | 'notYet'
}

const RESULTS: Partial<Record<ObjectiveState, Status>> = {
  met_independently: { steps: 3, text: 'Gold: met on your own', tone: 'gold' },
  met_with_support: { steps: 3, text: 'Bronze: met with support', tone: 'bronze' },
}

/** Where the student stands on one objective, in words first (the bar only repeats it). */
export function skillStatus(skill: Skill): Status {
  const result = skill.result ? RESULTS[skill.result] : undefined
  if (result) return result
  const practice: Status =
    skill.level === 'secure'
      ? { steps: 2, text: 'Secure in practice', tone: 'practice' }
      : skill.level === 'practising'
        ? { steps: 1, text: 'Practising', tone: 'practice' }
        : { steps: 0, text: 'Not started', tone: 'none' }
  return skill.result === 'not_yet'
    ? { ...practice, text: 'Not yet: its review path is open', tone: 'notYet' }
    : practice
}
