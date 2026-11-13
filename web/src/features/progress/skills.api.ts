import { api } from '../../api/client.ts'
import type { ObjectiveState } from '../mastery/mastery.api.ts'

/** Practice progress on one objective, in three coarse steps (api/app/services/skills.py). */
export type SkillLevel = 'not_started' | 'practising' | 'secure'

/** A module medal (FR-9.8). "finished", not bronze: bronze is an objective badge's level. */
export type Medal = 'gold' | 'silver' | 'finished'

/** Where to work on an objective (#214), worked out by the API from the content: `practise` in a
 * module (at `segment`, 0-based, when the student can open it there), `revisit` a module, or its
 * `review` path once module 6 has said "not yet". Never module 6 itself. */
export type Improve = {
  kind: 'practise' | 'revisit' | 'review'
  moduleId: number | null
  segment: number | null
  objectiveId: number | null
}

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
  /** Where to work on it next; null once met on your own (or nowhere to go). */
  improve?: Improve | null
  /** The modules, in course order, whose practice questions it has: where its badge's first
   * level, Practised, is earned. */
  modules?: number[]
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
