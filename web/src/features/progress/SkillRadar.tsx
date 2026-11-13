import { objectiveLabel } from './objectiveLabels.ts'
import {
  CX,
  CY,
  HEIGHT,
  RADIUS,
  RINGS,
  WIDTH,
  labelStyle,
  point,
  polygon,
  radarSummary,
  radiusFor,
  ringFor,
} from './radar.ts'
import { skillStatus } from './skillStatus.ts'
import type { Skill } from './skills.api.ts'
import styles from './SkillRadar.module.css'

/**
 * The skill profile as a radar chart for the home page (#214): one axis per objective, clockwise
 * from the top, and a filled shape reaching out to the ring each objective has got to. Plain SVG.
 * The names around it are HTML, so they wrap and keep their size at any width; below 22rem only
 * the objective's number is shown there, and the list under the chart names them. The legend
 * names the rings, centre outwards.
 *
 * The drawing is one image with a summary as its name; its points and names are hidden from
 * screen readers, because the list that goes with it (`SkillProfile`) says the same in words and
 * opens to the evidence. Nothing in it takes focus.
 */
export function SkillRadar({ skills }: { skills: Skill[] }) {
  const count = skills.length
  const shape = skills.map((skill, i) => ({
    skill,
    ring: ringFor(skill),
    tone: skillStatus(skill).tone,
    at: point(i, count, radiusFor(ringFor(skill))),
  }))
  const reached = shape.some((s) => s.ring > 0)
  const notYet = skills.some((s) => s.result === 'not_yet')

  return (
    <figure className={styles.radar}>
      <div className={styles.chart}>
        <svg
          viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
          className={styles.svg}
          // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role -- an inline SVG named as one picture; an <img> couldn't take the theme's colours
          role="img"
          aria-label={radarSummary(skills)}
        >
          {RINGS.map(({ ring }) => (
            <polygon
              key={ring}
              points={polygon(count, radiusFor(ring))}
              className={styles.ring}
              data-ring={ring}
            />
          ))}
          {skills.map((skill, i) => {
            const end = point(i, count, RADIUS)
            return (
              <line key={skill.id} x1={CX} y1={CY} x2={end.x} y2={end.y} className={styles.axis} />
            )
          })}
          {reached && (
            <polygon
              points={shape.map((s) => `${s.at.x.toFixed(1)},${s.at.y.toFixed(1)}`).join(' ')}
              className={styles.shape}
              data-testid="radar-shape"
            />
          )}
          {shape
            .filter((s) => s.ring > 0)
            .map((s) => (
              <circle
                key={s.skill.id}
                cx={s.at.x}
                cy={s.at.y}
                r={5}
                className={`${styles.point} ${styles[s.tone]}`}
                data-objective={s.skill.id}
                data-ring={s.ring}
              />
            ))}
        </svg>
        <div className={styles.labels} aria-hidden="true">
          {skills.map((skill, i) => (
            <span
              key={skill.id}
              className={styles.label}
              style={labelStyle(i, count)}
              data-objective={skill.id}
            >
              <span className={styles.labelNumber}>{skill.id}</span>
              <span className={styles.labelName}> {objectiveLabel(skill.id)}</span>
            </span>
          ))}
        </div>
      </div>
      <figcaption className={styles.legend}>
        <span className={styles.legendTitle}>Rings, centre outwards:</span>
        <span>centre: not started</span>
        <span>
          <i className={`${styles.swatch} ${styles.practice}`} aria-hidden="true" />
          practising
        </span>
        <span>
          <i className={`${styles.swatch} ${styles.practice}`} aria-hidden="true" />
          secure in practice
        </span>
        <span>
          <i className={`${styles.swatch} ${styles.bronze}`} aria-hidden="true" />
          bronze, met with support (dashed)
        </span>
        <span>
          <i className={`${styles.swatch} ${styles.gold}`} aria-hidden="true" />
          gold, met on your own (outer)
        </span>
        {notYet && (
          <span>
            <i className={`${styles.swatch} ${styles.notYet}`} aria-hidden="true" />
            open point: not yet in the mastery check
          </span>
        )}
      </figcaption>
    </figure>
  )
}
