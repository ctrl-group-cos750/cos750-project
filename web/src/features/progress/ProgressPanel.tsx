import { Link } from 'react-router'
import { AchievementBadge, ProgressBar } from '../../components'
import { useMediaQuery } from '../activities/pictures/useMediaQuery.ts'
import { useRewards } from '../rewards/hooks.ts'
import { buildShelf, type ShelfItem } from '../rewards/shelf.ts'
import { useSkills } from './hooks.ts'
import { Medal } from './Medal.tsx'
import { MEDAL_NAMES, MEDAL_RULES } from './medals.ts'
import { SkillProfile } from './SkillProfile.tsx'
import type { ModuleMedal } from './skills.api.ts'
import styles from './progress.module.css'

/** From here (Tailwind's lg) the panel sits beside the lesson; below it, a strip under it. */
export const PANEL_BESIDE = '(min-width: 64rem)'

export type ProgressPanelProps = {
  /** The module being worked through, if any: its progress and its medal. */
  moduleId?: number
  moduleNumber?: number
  /** Where the student is in the module, as the module page counts it. */
  place?: { number: number; total: number }
}

/** The badges most recently earned or raised to gold, newest first. */
function recentBadges(items: ShelfItem[], count = 3): ShelfItem[] {
  const when = (i: ShelfItem) => i.earned?.upgradedAt ?? i.earned?.awardedAt ?? ''
  return items
    .filter((i) => i.earned)
    .sort((a, b) => when(b).localeCompare(when(a)))
    .slice(0, count)
}

/** The medal this module is heading for, or has, with its rule in words. */
function MedalLine({ medal }: { medal: ModuleMedal | undefined }) {
  if (!medal) return null
  const tier = medal.medal ?? medal.headingFor
  if (!tier)
    return (
      <p className={styles.muted}>
        Answer its activities to earn a medal: gold for every one right first time without hint 3 or
        4.
      </p>
    )
  return (
    <div className={styles.medalLine}>
      <Medal tier={tier} size={32} />
      <p>
        <strong>
          {medal.medal ? `${MEDAL_NAMES[tier]} medal` : `Heading for ${MEDAL_NAMES[tier]}`}
        </strong>
        <span className={styles.muted}>
          {MEDAL_RULES[tier].charAt(0).toUpperCase() + MEDAL_RULES[tier].slice(1)}.
          {!medal.medal &&
            ` ${medal.firstTime} of ${medal.answered} answered so far right first time.`}
        </span>
      </p>
    </div>
  )
}

/** The panel's contents, the same beside the lesson and in the strip under it. */
function PanelBody({ moduleId, moduleNumber, place }: ProgressPanelProps) {
  const rewards = useRewards()
  const skills = useSkills()
  const hidden = rewards.data?.hideRewards !== false // hidden until known, never flashed
  const medal = skills.data?.modules.find((m) => m.moduleId === moduleId)
  const recent = rewards.data
    ? recentBadges(Object.values(buildShelf(rewards.data.badges)).flat())
    : []

  return (
    <div className={styles.panelBody}>
      {place && moduleNumber !== undefined && (
        <section className={styles.block} aria-label={`Module ${moduleNumber}`}>
          <h3 className={styles.blockTitle}>Module {moduleNumber}</h3>
          <ProgressBar
            label={`Module ${moduleNumber}: segments done`}
            value={place.number}
            max={place.total}
            showCount
          />
          {!hidden && <MedalLine medal={medal} />}
        </section>
      )}
      {!hidden && (
        <p className={styles.points}>
          <span className={styles.pointsValue}>{rewards.data?.points ?? 0}</span> points
        </p>
      )}
      {skills.data && skills.data.objectives.length > 0 && (
        <section className={styles.block} aria-label="Skill profile">
          <h3 className={styles.blockTitle}>Skill profile</h3>
          <SkillProfile skills={skills.data.objectives} highlight={medal?.objectives} compact />
        </section>
      )}
      {!hidden && recent.length > 0 && (
        <section className={styles.block} aria-label="Recent badges">
          <h3 className={styles.blockTitle}>Recent badges</h3>
          <ul className={styles.recent}>
            {recent.map((item) => (
              <li key={item.key}>
                <AchievementBadge achievement={item.achievement} state={item.state} size={36} />
                <span>{item.title}</span>
              </li>
            ))}
          </ul>
          <Link to="/badges" className={styles.link}>
            See your badges
          </Link>
        </section>
      )}
    </div>
  )
}

/**
 * The progress panel on module and activity pages (#214): this module's progress, the points
 * (unless rewards are hidden), the skill profile with this module's objectives marked, the medal
 * the module is heading for and the latest badges. It updates after each answer with the rewards.
 *
 * On wide screens it is a column beside the lesson (`placement="beside"`); below that it is a
 * one-line strip that opens, placed under the lesson (`placement="below"`), so it never pushes the
 * lesson down. The page renders it in both places and each shows only where it belongs.
 */
export function ProgressPanel({
  placement,
  ...props
}: ProgressPanelProps & { placement: 'beside' | 'below' }) {
  const beside = useMediaQuery(PANEL_BESIDE)
  const rewards = useRewards()
  if (beside !== (placement === 'beside')) return null
  if (placement === 'beside')
    return (
      <aside className={styles.panel} aria-labelledby="progress-panel-heading">
        <h2 id="progress-panel-heading" className={styles.panelTitle}>
          Your progress
        </h2>
        <PanelBody {...props} />
      </aside>
    )
  const hidden = rewards.data?.hideRewards !== false
  return (
    <details className={styles.strip}>
      <summary>
        Your progress
        {!hidden && <span className={styles.muted}> · {rewards.data?.points ?? 0} points</span>}
      </summary>
      <PanelBody {...props} />
    </details>
  )
}
