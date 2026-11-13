import { useId } from 'react'
import { Link } from 'react-router'
import { AchievementBadge, ProgressBar } from '../../components'
import { useMediaQuery } from '../activities/pictures/useMediaQuery.ts'
import { useRewards } from '../rewards/hooks.ts'
import { buildShelf, type ShelfItem } from '../rewards/shelf.ts'
import { useSkills } from './hooks.ts'
import { Medal } from './Medal.tsx'
import { MEDAL_NAMES, MEDAL_RULES } from './medals.ts'
import { HiddenNote } from './HiddenNote.tsx'
import { HideMenu, type HideItem } from './HideMenu.tsx'
import { PanelHeader } from './PanelHeader.tsx'
import { usePanelMinimised } from './preferences.ts'
import { useHideable, useHideableRewards } from './useHideable.ts'
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
  /** The module's activities the student moved past without a right answer (FR-2.7), each a
   * link to its segment (#215 review). */
  lookAgain?: { position: number; title: string }[]
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
        Answer its activities to earn a medal: gold for every one right first time without a hint.
      </p>
    )
  return (
    <div className={styles.medalLine}>
      <Medal tier={tier} size={32} />
      <p>
        <strong>
          {medal.medal
            ? `${MEDAL_NAMES[tier]} medal`
            : `Heading for ${MEDAL_NAMES[tier].toLowerCase()}`}
        </strong>
        <span className={styles.muted}>
          {MEDAL_RULES[tier].charAt(0).toUpperCase() + MEDAL_RULES[tier].slice(1)}.
          {!medal.medal &&
            ` ${medal.firstTime} of ${medal.answered} answered so far right first time without a hint.`}
        </span>
      </p>
    </div>
  )
}

/** What the student can turn off from the panel itself (#214), shared by its header and its body:
 * the header's "⋯" hides, the body shows the note where the hidden part was. */
type Hiding = {
  profile: ReturnType<typeof useHideable>
  rewards: ReturnType<typeof useHideableRewards>
  panel: ReturnType<typeof useHideable>
}

function hideItems({ profile, rewards, panel }: Hiding): HideItem[] {
  return [
    ...(profile.on ? [{ label: 'Hide skill profile', onSelect: profile.hide }] : []),
    ...(rewards.on ? [{ label: 'Hide points and badges', onSelect: rewards.hide }] : []),
    { label: 'Hide progress panel', onSelect: panel.hide },
  ]
}

/** The panel's contents, the same beside the lesson and in the strip under it. */
function PanelBody({
  moduleId,
  moduleNumber,
  place,
  lookAgain,
  hiding,
}: ProgressPanelProps & { hiding: Hiding }) {
  const rewards = useRewards()
  const skills = useSkills()
  const hidden = rewards.data?.hideRewards !== false // hidden until known, never flashed
  const { profile } = hiding
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
      {moduleId !== undefined && lookAgain && lookAgain.length > 0 && (
        <section className={styles.block} aria-labelledby="look-again-heading">
          <h3 id="look-again-heading" className={styles.blockTitle}>
            To look at again
          </h3>
          <p className={styles.muted}>
            You moved on from {lookAgain.length === 1 ? 'this one' : 'these'} without a right
            answer, so {lookAgain.length === 1 ? 'it earns' : 'they earn'} nothing yet.
          </p>
          <ul className={styles.lookAgain}>
            {lookAgain.map((item) => (
              <li key={item.position}>
                <Link to={`/modules/${moduleId}?segment=${item.position}`} className={styles.link}>
                  {item.title}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
      {hiding.rewards.justHidden && (
        <HiddenNote text="Points and badges hidden." onUndo={hiding.rewards.undo} />
      )}
      {!hidden && (
        <p className={styles.points}>
          <span className={styles.pointsValue}>{rewards.data?.points ?? 0}</span> points
        </p>
      )}
      {profile.justHidden && <HiddenNote text="Skill profile hidden." onUndo={profile.undo} />}
      {profile.on && skills.data && skills.data.objectives.length > 0 && (
        <section className={styles.block} aria-label="Skill profile">
          <h3 className={styles.blockTitle}>Skill profile</h3>
          <SkillProfile skills={skills.data.objectives} highlight={medal?.objectives} compact />
        </section>
      )}
      {!hidden && recent.length > 0 && (
        <section className={styles.block} aria-label="Recent badges">
          {/* The link beside the heading, not under the list: at the foot of the panel it was cut
              off on a 1366 × 900 screen (#215 review). */}
          <div className={styles.blockHead}>
            <h3 className={styles.blockTitle}>Recent badges</h3>
            <Link to="/badges" className={styles.link}>
              See your badges
            </Link>
          </div>
          <ul className={styles.recent}>
            {recent.map((item) => (
              // One row of pictures, each named with its level (the badge's own label), so the
              // panel still fits a 1366 × 900 screen with three (#214: practised badges come
              // early, so most students have some).
              <li key={item.key} title={item.title}>
                <AchievementBadge achievement={item.achievement} state={item.state} size={36} />
              </li>
            ))}
          </ul>
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
 *
 * Its heading minimises it to a narrow rail beside the lesson (kept on this device), and its "⋯"
 * turns off the panel, the skill profile or points and badges where they are. Switched off
 * (`progressPanel` in preferences.ts), neither shows, and the page gives the lesson the width.
 */
export function ProgressPanel({
  placement,
  ...props
}: ProgressPanelProps & { placement: 'beside' | 'below' }) {
  const beside = useMediaQuery(PANEL_BESIDE)
  const rewards = useRewards()
  const hiding: Hiding = {
    profile: useHideable('skillProfile'),
    rewards: useHideableRewards(),
    panel: useHideable('progressPanel'),
  }
  const [minimised, setMinimised] = usePanelMinimised('progressPanel')
  const body = useId()
  if (beside !== (placement === 'beside')) return null
  if (hiding.panel.justHidden)
    return (
      <HiddenNote
        text="Progress panel hidden."
        onUndo={hiding.panel.undo}
        className={placement === 'beside' ? styles.hiddenToast : undefined}
      />
    )
  if (!hiding.panel.on) return null
  const hidden = rewards.data?.hideRewards !== false
  if (placement === 'beside' && minimised) {
    const count = !hidden ? rewards.data?.points : props.lookAgain?.length
    return (
      <aside className={styles.rail} aria-label="Your progress">
        <h2 className={styles.railHeading}>
          <button
            type="button"
            className={styles.railButton}
            aria-expanded={false}
            aria-controls={body}
            // The count's meaning in words; the visible number is in the name (WCAG 2.5.3).
            aria-label={
              count !== undefined && count > 0
                ? `Your progress, ${count} ${!hidden ? 'points' : 'to look at again'}`
                : 'Your progress'
            }
            onClick={() => setMinimised(false)}
          >
            <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
              <path d="M5 19V11M12 19V5M19 19v-6" />
            </svg>
            {count !== undefined && count > 0 && <span className={styles.railCount}>{count}</span>}
          </button>
        </h2>
        <div id={body} hidden />
      </aside>
    )
  }
  if (placement === 'beside')
    return (
      <aside className={styles.panel} aria-labelledby="progress-panel-heading">
        <PanelHeader
          id="progress-panel-heading"
          title="Your progress"
          minimised={false}
          onToggle={() => setMinimised(true)}
          controls={body}
          hide={hideItems(hiding)}
          className={styles.panelTitle}
        />
        <div id={body}>
          <PanelBody {...props} hiding={hiding} />
        </div>
      </aside>
    )
  return (
    <details className={styles.strip}>
      <summary>
        Your progress
        {!hidden && <span className={styles.muted}> · {rewards.data?.points ?? 0} points</span>}
        {props.lookAgain && props.lookAgain.length > 0 && (
          <span className={styles.muted}> · {props.lookAgain.length} to look at again</span>
        )}
      </summary>
      <div className={styles.stripMenu}>
        <HideMenu title="your progress" items={hideItems(hiding)} />
      </div>
      <PanelBody {...props} hiding={hiding} />
    </details>
  )
}
