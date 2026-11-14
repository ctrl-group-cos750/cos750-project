import { useId } from 'react'
import { Link } from 'react-router'
import { AchievementBadge, Alert, Card, Spinner, type AchievementState } from '../../components'
import { useSkills } from '../progress/hooks.ts'
import { useRewards, useRewardsSettings } from './hooks.ts'
import { buildShelf, type ShelfItem } from './shelf.ts'
import styles from './BadgesPage.module.css'

const tierWord = {
  practised: 'Practised: secure in the modules',
  bronze: 'Bronze: met with support',
  gold: 'Gold: met on your own',
} as const

// An objective badge's three levels, lowest first (#214).
const LEVELS = [
  ['practised', 'Practised'],
  ['bronze', 'Bronze'],
  ['gold', 'Gold'],
] as const

/** The three levels in a row, those reached filled in and the current one marked, so the shelf
 * shows how far a badge can go. In words as well as the marks (NFR-A2). */
function Levels({ state }: { state: AchievementState }) {
  const reached = LEVELS.findIndex(([level]) => level === state)
  return (
    <ol className={styles.levels} aria-label="Levels">
      {LEVELS.map(([level, label], index) => (
        <li
          key={level}
          data-reached={index <= reached ? 'yes' : 'no'}
          aria-current={index === reached ? 'step' : undefined}
        >
          <span aria-hidden="true">{index <= reached ? '●' : '○'}</span> {label}
          {index <= reached && <span className="visually-hidden">, reached</span>}
        </li>
      ))}
    </ol>
  )
}

function BadgeCard({ item }: { item: ShelfItem }) {
  const secret = item.state === 'locked' && item.achievement.kind === 'hidden'
  const objective = item.achievement.kind === 'objective'
  return (
    <li className={styles.card} data-state={item.state}>
      <AchievementBadge achievement={item.achievement} state={item.state} size={72} />
      <div>
        <h3 className={styles.name}>{secret ? 'Hidden badge' : item.title}</h3>
        {item.state === 'practised' || item.state === 'bronze' || item.state === 'gold' ? (
          <p className={styles.tier}>{tierWord[item.state]}</p>
        ) : null}
        {!secret && <p className={styles.description}>{item.achievement.description}</p>}
        {objective && <Levels state={item.state} />}
        {item.next && <p className={styles.next}>{item.next}</p>}
        {item.review !== undefined && (
          <Link to={`/review/${item.review}`} className={styles.review}>
            Go over it on its review path
          </Link>
        )}
      </div>
    </li>
  )
}

function Group({ title, items }: { title: string; items: ShelfItem[] }) {
  // An empty group has nothing to show: today the hidden group, since Off the Map was removed.
  if (items.length === 0) return null
  return (
    <section className={styles.group}>
      <h2>{title}</h2>
      <ul className={styles.cards}>
        {items.map((item) => (
          <BadgeCard key={item.key} item={item} />
        ))}
      </ul>
    </section>
  )
}

/**
 * /badges — the student's own points and badges (FR-9.4: nobody else sees them), and the setting
 * that hides them (FR-9.5). Hidden or not, the mastery report is unaffected.
 */
export function BadgesPage() {
  const rewards = useRewards()
  const skills = useSkills()
  const settings = useRewardsSettings()
  const toggleId = useId()

  if (rewards.isPending) return <Spinner label="Loading your badges" />
  if (rewards.isError) return <Alert tone="danger">{rewards.error.message}</Alert>

  const { hideRewards, points, badges } = rewards.data
  const shelf = buildShelf(badges, skills.data?.objectives)
  const earnedCount = badges.length

  return (
    <>
      <h1>Your badges</h1>
      <p className={styles.lead}>
        Only you can see your points and badges. Each badge stands for something you can now do.
      </p>

      <Card className={styles.settings}>
        <div className={styles.toggle}>
          <input
            id={toggleId}
            type="checkbox"
            checked={hideRewards}
            disabled={settings.isPending}
            onChange={(e) => settings.mutate({ hideRewards: e.target.checked })}
          />
          <label htmlFor={toggleId}>Hide points and badges</label>
        </div>
        <p className={styles.muted}>
          You'll still earn them, and you can turn them back on at any time. Your results for each
          objective are always shown.
        </p>
        {settings.isError && <Alert tone="danger">{settings.error.message}</Alert>}
      </Card>

      {hideRewards ? (
        <p className={styles.muted}>Points and badges are hidden.</p>
      ) : (
        <>
          <dl className={styles.totals}>
            <div>
              <dt>Points</dt>
              <dd>{points}</dd>
            </div>
            <div>
              <dt>Badges</dt>
              <dd>{earnedCount}</dd>
            </div>
          </dl>
          <Group title="Learning objectives" items={shelf.objective} />
          <Group title="Milestones" items={shelf.milestone} />
          <Group title="Bonus quests" items={shelf.quest} />
          <Group title="Something to find" items={shelf.hidden} />
        </>
      )}
    </>
  )
}
