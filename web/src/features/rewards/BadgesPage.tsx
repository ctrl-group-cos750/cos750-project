import { useId } from 'react'
import { AchievementBadge, Alert, Card, Spinner } from '../../components'
import { useRewards, useRewardsSettings } from './hooks.ts'
import { buildShelf, type ShelfItem } from './shelf.ts'
import styles from './BadgesPage.module.css'

const tierWord = { bronze: 'Bronze: met with support', gold: 'Gold: met on your own' } as const

function BadgeCard({ item }: { item: ShelfItem }) {
  const secret = item.state === 'locked' && item.achievement.kind === 'hidden'
  return (
    <li className={styles.card} data-state={item.state}>
      <AchievementBadge achievement={item.achievement} state={item.state} size={72} />
      <div>
        <h3 className={styles.name}>{secret ? 'Hidden badge' : item.title}</h3>
        {item.state === 'bronze' || item.state === 'gold' ? (
          <p className={styles.tier}>{tierWord[item.state]}</p>
        ) : null}
        {!secret && <p className={styles.description}>{item.achievement.description}</p>}
        {item.next && <p className={styles.next}>{item.next}</p>}
      </div>
    </li>
  )
}

function Group({ title, items }: { title: string; items: ShelfItem[] }) {
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
  const settings = useRewardsSettings()
  const toggleId = useId()

  if (rewards.isPending) return <Spinner label="Loading your badges" />
  if (rewards.isError) return <Alert tone="danger">{rewards.error.message}</Alert>

  const { hideRewards, points, badges } = rewards.data
  const shelf = buildShelf(badges)
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
