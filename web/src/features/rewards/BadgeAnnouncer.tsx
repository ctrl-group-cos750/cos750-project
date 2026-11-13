import { useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router'
import { AchievementBadge, Button } from '../../components'
import { useMarkRewardsSeen, useRewards, useRewardsSettings } from './hooks.ts'
import { unseen, type ShelfItem } from './shelf.ts'
import styles from './BadgeAnnouncer.module.css'

const READY = 'ready-for-lecture'
// More than this at once (a burst after a mastery check) collapse into one line.
const MAX_NOTES = 3

function announcement(item: ShelfItem) {
  if (item.state === 'gold') return `${item.title} is now gold`
  return item.title
}

/** The one full-screen moment: every objective met, ready for the lecture. */
function Celebration({ item, onClose }: { item: ShelfItem; onClose: () => void }) {
  const titleId = useId()
  const dialog = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    dialog.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div className={styles.backdrop}>
      <dialog
        ref={dialog}
        open
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={styles.dialog}
      >
        <AchievementBadge achievement={item.achievement} state="earned" size={128} />
        <h2 id={titleId}>You're ready for the lecture</h2>
        <p>{item.achievement.description}</p>
        <div className={styles.actions}>
          <Link to="/badges" className={styles.link} onClick={onClose}>
            See your badges
          </Link>
          <Button onClick={onClose}>Close</Button>
        </div>
      </dialog>
    </div>
  )
}

/**
 * Announces badges as they are earned: a quiet note in the corner for most, and one full-screen
 * moment for Ready for the Lecture. Each badge is announced once (the server is told it was
 * seen), and nothing is announced while the student has hidden rewards.
 */
export function BadgeAnnouncer() {
  const { data } = useRewards()
  const markSeen = useMarkRewardsSeen()
  const [notes, setNotes] = useState<ShelfItem[]>([])
  const [celebrate, setCelebrate] = useState<ShelfItem | null>(null)
  // Set once the student turns badges off from a note: says where to turn them back on.
  const [turnedOff, setTurnedOff] = useState(false)
  const settings = useRewardsSettings()
  const announced = useRef(new Set<string>())
  const { mutate } = markSeen

  useEffect(() => {
    if (!data || data.hideRewards) return
    const fresh = unseen(data.badges).filter((i) => !announced.current.has(`${i.key}:${i.state}`))
    if (fresh.length === 0) return
    for (const item of fresh) announced.current.add(`${item.key}:${item.state}`)
    const ready = fresh.find((i) => i.achievement.id === READY)
    if (ready) setCelebrate(ready)
    setNotes((shown) => [
      ...shown.filter((n) => !fresh.some((f) => f.key === n.key)),
      ...fresh.filter((i) => i !== ready),
    ])
    mutate()
  }, [data, mutate])

  const dismiss = (key: string) => setNotes((shown) => shown.filter((n) => n.key !== key))
  // Right where the first badge appears, not only in the profile (FR-9.5): a student who finds
  // badges distracting or childish shouldn't have to hunt for the setting (overjustification:
  // Deci, Koestner & Ryan 1999; L05). Everything is still earned and comes back when turned on.
  const turnOff = () =>
    settings.mutate(
      { hideRewards: true },
      {
        onSuccess: () => {
          setNotes([])
          setTurnedOff(true)
        },
      },
    )

  return (
    <>
      <output className={styles.region} aria-live="polite">
        {notes.length > MAX_NOTES && (
          <div className={styles.note}>
            <div className={styles.text}>
              <strong>
                {notes.length - MAX_NOTES} more new{' '}
                {notes.length - MAX_NOTES === 1 ? 'badge' : 'badges'}
              </strong>
              <Link to="/badges" className={styles.link} onClick={() => setNotes([])}>
                See your badges
              </Link>
            </div>
            <Button variant="ghost" size="sm" aria-label="Dismiss all" onClick={() => setNotes([])}>
              ×
            </Button>
          </div>
        )}
        {notes.slice(-MAX_NOTES).map((item) => (
          <div key={item.key} className={styles.note}>
            <AchievementBadge achievement={item.achievement} state={item.state} size={48} />
            <div className={styles.text}>
              <strong>{announcement(item)}</strong>
              <span>{item.achievement.description}</span>
              <span className={styles.links}>
                <Link to="/badges" className={styles.link} onClick={() => dismiss(item.key)}>
                  See your badges
                </Link>
                <button
                  type="button"
                  className={styles.off}
                  disabled={settings.isPending}
                  onClick={turnOff}
                >
                  Turn off badges
                </button>
              </span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              aria-label={`Dismiss ${item.title}`}
              onClick={() => dismiss(item.key)}
            >
              ×
            </Button>
          </div>
        ))}
        {turnedOff && (
          <div className={styles.note}>
            <div className={styles.text}>
              <strong>Badges and points are off</strong>
              <span>
                You still earn them. Turn them back on in your{' '}
                <Link to="/profile" className={styles.link} onClick={() => setTurnedOff(false)}>
                  profile
                </Link>
                .
              </span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              aria-label="Dismiss"
              onClick={() => setTurnedOff(false)}
            >
              ×
            </Button>
          </div>
        )}
        {settings.isError && (
          <div className={styles.note}>
            <div className={styles.text}>
              <strong>Badges are still on</strong>
              <span>{settings.error.message}</span>
            </div>
          </div>
        )}
      </output>
      {celebrate && <Celebration item={celebrate} onClose={() => setCelebrate(null)} />}
    </>
  )
}
