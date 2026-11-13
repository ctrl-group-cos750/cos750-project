import { objectiveLabel } from './objectiveLabels.ts'
import { skillStatus } from './skillStatus.ts'
import type { Skill } from './skills.api.ts'
import styles from './progress.module.css'

/** The evidence behind a level, for whoever opens the row. */
function evidence(skill: Skill): string {
  if (skill.total === 0) return 'No practice questions on this objective yet.'
  const right = `${skill.onYourOwn} right without hint 3 or 4`
  return `${skill.answered} of ${skill.total} practice questions answered, ${right}.`
}

const NONE: readonly number[] = []

/**
 * The eight learning objectives as a compact profile that fills in (#214): one row per
 * objective with its short name, a three-step bar (practising, secure, met in the mastery check)
 * and the same in words. Each row opens to show the objective in full and the evidence behind it,
 * so it never rests on a percentage of a handful of answers. Before the mastery check there are
 * only practice steps; once module 6 has a result, gold, bronze or not yet comes from the report.
 *
 * The rows are native disclosure widgets: the label and the words are the accessible text, the
 * bar is hidden from screen readers. `highlight` marks the objectives a module teaches.
 */
export function SkillProfile({
  skills,
  highlight = NONE,
  compact = false,
}: {
  skills: Skill[]
  highlight?: readonly number[]
  compact?: boolean
}) {
  return (
    <ul className={`${styles.profile} ${compact ? styles.compact : ''}`}>
      {skills.map((skill) => {
        const status = skillStatus(skill)
        const here = highlight.includes(skill.id)
        return (
          <li key={skill.id} className={here ? styles.here : undefined}>
            <details className={styles.skill}>
              <summary className={styles.summary}>
                <span className={styles.label}>
                  <span className={styles.number}>{skill.id}</span>
                  {objectiveLabel(skill.id)}
                  {here && <span className="visually-hidden"> (this module)</span>}
                </span>
                <span className={`${styles.track} ${styles[status.tone]}`} aria-hidden="true">
                  {[1, 2, 3].map((step) => (
                    <span key={step} data-on={status.steps >= step || undefined} />
                  ))}
                </span>
                <span className={styles.status}>{status.text}</span>
              </summary>
              <div className={styles.evidence}>
                <p>{skill.text}</p>
                <p>{evidence(skill)}</p>
              </div>
            </details>
          </li>
        )
      })}
    </ul>
  )
}
