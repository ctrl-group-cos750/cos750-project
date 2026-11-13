import { api } from '../../api/client.ts'
import type { ObjectiveState } from '../mastery/mastery.api.ts'

/** Practice progress on one objective, in three coarse steps (api/app/services/skills.py). */
export type SkillLevel = 'not_started' | 'practising' | 'secure'

export type Medal = 'gold' | 'silver' | 'bronze'

/** One objective on the skill profile, as `GET /api/me/skills` sends it. */
export type Skill = {
  id: number
  text: string
  /** Of `total` practice items: answered at all, right at some point, right without hint 3 or 4. */
  answered: number
  correct: number
  onYourOwn: number
  total: number
  level: SkillLevel
  /** The mastery result once the mastery check (or a review path) has decided it. */
  result: ObjectiveState | null
}

/** A module's medal (FR-9.8): `medal` once complete, `headingFor` while in progress. */
export type ModuleMedal = {
  moduleId: number
  complete: boolean
  firstTime: number
  onYourOwn: number
  answered: number
  total: number
  medal: Medal | null
  headingFor: Medal | null
  /** The objectives its activities practise. */
  objectives: number[]
}

export type Skills = { objectives: Skill[]; modules: ModuleMedal[] }

/** The logged-in student's skill profile and module medals. */
export function fetchSkills(): Promise<Skills> {
  return api<Skills>('/api/me/skills')
}
