import { api } from '../../api/client.ts'
import type { ObjectiveState } from '../mastery/mastery.api.ts'

/** Practice progress on one objective, in three coarse steps (api/app/services/skills.py). */
export type SkillLevel = 'not_started' | 'practising' | 'secure'

/** A module medal (FR-9.8). "finished", not bronze: bronze is an objective badge's level. */
export type Medal = 'gold' | 'silver' | 'finished'

/** Where to work on an objective (#214), worked out by the API from the content: `practise` in a
 * module (at `segment`, 0-based, when the student can open it there), `revisit` a module, its
 * `review` path once module 6 has said "not yet", or the mastery `check` (module 6) once practice
 * this round can no longer make it secure (only a first attempt counts, FR-9.6), or `restart` a
 * finished module, which gives its questions a new first answer for the profile. Never module 6
 * to practise.
 * `locked`: that module isn't open to the student yet (the mastery check, before modules 1 to 5
 * are done). */
export type Improve = {
  kind: 'practise' | 'revisit' | 'review' | 'check' | 'restart'
  moduleId: number | null
  segment: number | null
  objectiveId: number | null
  locked?: boolean
}

/** One objective on the skill profile, as `GET /api/me/skills` sends it. */
export type Skill = {
  id: number
  text: string
  /** Of `total` practice items: answered at all, right at some point, right at the first attempt
   * before hint 3 or 4. */
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
