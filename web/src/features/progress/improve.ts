import { objectiveLabel } from './objectiveLabels.ts'
import type { Skill } from './skills.api.ts'

export type ImproveLink = {
  /** Where it goes; null when it can't be opened yet, so the text is shown without a link. */
  to: string | null
  /** What the link says. */
  text: string
  /** Its full name, starting from the objective, with `text` in it (WCAG 2.5.3). */
  label: string
  /** A revisit is offered, not urged: shown quieter. */
  quiet: boolean
}

/**
 * The link from an objective on the skill profile to where it can be improved (#214): practise
 * in a module (at the segment, when the student can open it there), revisit a module (secure, or
 * met with support: the result stands), the review path after a "not yet" in the mastery check,
 * or the mastery check itself once practice can no longer make it secure (#222 re-review, N1).
 * While the mastery check is still locked, that says when it will be shown instead of linking to a
 * page that isn't open (#222 re-review, nit 3). Nothing for gold. The API decides where
 * (`improve`); this only words it.
 */
export function improveLink(skill: Skill): ImproveLink | null {
  const improve = skill.improve
  if (!improve) return null
  const name = objectiveLabel(skill.id)
  if (improve.kind === 'review' && improve.objectiveId !== null)
    return {
      to: `/review/${improve.objectiveId}`,
      text: 'Follow its review path',
      label: `Improve ${name}: follow its review path`,
      quiet: false,
    }
  if (improve.moduleId === null) return null
  if (improve.kind === 'check' && improve.locked === true)
    return {
      to: null,
      text: 'Shown in the mastery check, once modules 1 to 5 are done',
      label: `${name}: shown in the mastery check, once modules 1 to 5 are done`,
      quiet: false,
    }
  if (improve.kind === 'check')
    return {
      to: `/modules/${improve.moduleId}`,
      text: 'Show it in the mastery check',
      label: `Improve ${name}: show it in the mastery check`,
      quiet: false,
    }
  if (improve.kind === 'revisit')
    return {
      to: `/modules/${improve.moduleId}`,
      text: `Revisit module ${improve.moduleId}`,
      label: `${name}: revisit module ${improve.moduleId}`,
      quiet: true,
    }
  return {
    to:
      improve.segment === null
        ? `/modules/${improve.moduleId}`
        : `/modules/${improve.moduleId}?segment=${improve.segment}`,
    text: `Practise in module ${improve.moduleId}`,
    label: `Improve ${name}: practise in module ${improve.moduleId}`,
    quiet: false,
  }
}
