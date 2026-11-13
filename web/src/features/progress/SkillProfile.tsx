import { Link } from 'react-router'
import { improveLink } from './improve.ts'
import { objectiveLabel } from './objectiveLabels.ts'
import { skillStatus } from './skillStatus.ts'
import type { Skill } from './skills.api.ts'
import styles from './progress.module.css'

/** The evidence behind a level, for whoever opens the row. */
function evidence(skill: Skill): string {
  if (skill.total === 0) return 'No practice questions on this objective yet.'
  // On your own: right at the first attempt ever, before hint 3 or 4 (FR-9.6, #222 re-review).
  const right = `${skill.onYourOwn} right at the first try, without hint 3 or 4`
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
 * Beside each row, a link to where the objective can be improved (`improveLink`): a real link
 * next to the disclosure, never inside its summary; in the compact panel, inside the opened row. `bars={false}` leaves the bars out, for the list under the radar chart (SkillRadar), which
 * draws the levels itself; the words and the evidence stay.
 */
export function SkillProfile({
  skills,
  highlight = NONE,
  compact = false,
  bars = true,
}: {
  skills: Skill[]
  highlight?: readonly number[]
  compact?: boolean
  bars?: boolean
}) {
  return (
    <ul
      className={`${styles.profile} ${compact ? styles.compact : ''} ${bars ? '' : styles.noBars}`}
    >
      {skills.map((skill) => {
        const status = skillStatus(skill)
        const here = highlight.includes(skill.id)
        const link = improveLink(skill)
        const improve = link && (
          <Link
            to={link.to}
            aria-label={link.label}
            className={`${styles.improve} ${link.quiet ? styles.quiet : ''}`}
          >
            {link.text}
          </Link>
        )
        return (
          <li
            key={skill.id}
            className={`${styles.row} ${here ? styles.here : ''}`}
            data-objective={skill.id}
          >
            <details className={styles.skill}>
              <summary className={styles.summary}>
                <span className={styles.label}>
                  <span className={styles.number}>{skill.id}</span>
                  {objectiveLabel(skill.id)}
                  {here && <span className="visually-hidden"> (this module)</span>}
                </span>
                {bars && (
                  <span className={`${styles.track} ${styles[status.tone]}`} aria-hidden="true">
                    {[1, 2, 3].map((step) => (
                      <span key={step} data-on={status.steps >= step || undefined} />
                    ))}
                  </span>
                )}
                <span className={styles.status}>{status.text}</span>
              </summary>
              <div className={styles.evidence}>
                <p>{skill.text}</p>
                <p>{evidence(skill)}</p>
                {/* In the narrow panel the link is in the opened row, so the panel stays one
                    screen tall (1366 × 900, #215 review). */}
                {compact && improve}
              </div>
            </details>
            {link && !compact && improve}
          </li>
        )
      })}
    </ul>
  )
}
