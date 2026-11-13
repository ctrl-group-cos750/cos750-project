import { useEffect, useId, useRef, useState, type MouseEvent } from 'react'
import { Link } from 'react-router'
import { AchievementBadge, Button } from '../../components'
import { focusedElement, focusSafely } from '../../lib/focus.ts'
import { PHONE, useMediaQuery } from '../activities/pictures/useMediaQuery.ts'
import { useMarkRewardsSeen, useRewards, useRewardsSettings } from './hooks.ts'
import { unseen, type ShelfItem } from './shelf.ts'
import styles from './BadgeAnnouncer.module.css'

const READY = 'ready-for-lecture'
// More than this at once (a burst after a mastery check) collapse into one line.
const MAX_NOTES = 3
// On a phone, how long a note stays before it goes by itself (the badges page keeps it).
const NOTE_SECONDS = 8

function announcement(item: ShelfItem) {
  // "Now gold" only for a real upgrade from bronze; met on their own first time, it is just gold.
  if (item.state === 'gold')
    return item.earned?.upgradedAt ? `${item.title} is now gold` : `${item.title}: gold`
  return item.title
}

/** The one full-screen moment: every objective met, ready for the lecture. A modal <dialog>
 * opened with showModal(), so the page behind is inert, Tab stays inside, Escape closes it and
 * ::backdrop dims the page; on close, focus goes back to where it was (or the page's h1). */
function Celebration({ item, onClose }: { item: ShelfItem; onClose: () => void }) {
  const titleId = useId()
  const dialog = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const element = dialog.current
    if (!element) return
    const returnTo = focusedElement()
    if (typeof element.showModal === 'function') {
      if (!element.open) element.showModal()
    } else {
      element.setAttribute('open', '') // jsdom has no showModal
    }
    element.focus()
    // Unmounting takes the dialog out of the top layer (no close(), whose late "close" event
    // would call onClose again). StrictMode's test unmount leaves the element connected.
    return () => {
      if (!element.isConnected) focusSafely(returnTo)
    }
  }, [])

  return (
    <dialog
      ref={dialog}
      aria-labelledby={titleId}
      tabIndex={-1}
      className={styles.dialog}
      onClose={onClose}
      onCancel={(event) => {
        event.preventDefault() // Escape: close through React, so state and the DOM agree
        onClose()
      }}
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
  )
}

/**
 * Announces badges as they are earned: a quiet note in the corner for most, and one full-screen
 * moment for Ready for the Lecture. Each badge is announced once (the server is told it was
 * seen), and nothing is announced while the student has hidden rewards.
 *
 * The notes are a polite live region. On a phone they take one card at most (a burst becomes
 * "3 new badges"), never more than 40% of the screen, and go by themselves after a few seconds
 * unless focus is in them, so they don't sit over the lesson's buttons; the badges page keeps
 * them. Dismissing one moves focus to the next note's ×, or back to where the student was.
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
  const phone = useMediaQuery(PHONE)
  const region = useRef<HTMLOutputElement>(null)
  // Where focus came from when it entered the notes, to go back to once they are all gone.
  const cameFrom = useRef<HTMLElement | null>(null)
  // After a dismiss: the position of the × to focus next, once the notes have re-rendered.
  const refocus = useRef<number | null>(null)
  const [focusInside, setFocusInside] = useState(false)

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

  // After every render, so it runs once the dismissed note has gone.
  useEffect(() => {
    if (refocus.current === null) return
    const position = refocus.current
    refocus.current = null
    const buttons = region.current?.querySelectorAll<HTMLElement>('[data-dismiss]') ?? []
    if (buttons.length > 0) buttons[Math.min(position, buttons.length - 1)]!.focus()
    else focusSafely(cameFrom.current)
  })

  useEffect(() => {
    const element = region.current
    if (!element) return
    const onFocusIn = (event: FocusEvent) => {
      setFocusInside(true)
      const from = event.relatedTarget
      if (from instanceof HTMLElement && !element.contains(from)) cameFrom.current = from
    }
    const onFocusOut = (event: FocusEvent) => {
      if (!element.contains(event.relatedTarget as Node | null)) setFocusInside(false)
    }
    element.addEventListener('focusin', onFocusIn)
    element.addEventListener('focusout', onFocusOut)
    return () => {
      element.removeEventListener('focusin', onFocusIn)
      element.removeEventListener('focusout', onFocusOut)
    }
  }, [])

  // Phones: the note goes by itself after a while, unless the student is in it.
  useEffect(() => {
    if (!phone || focusInside || notes.length === 0) return
    const timer = setTimeout(() => setNotes([]), NOTE_SECONDS * 1000)
    return () => clearTimeout(timer)
  }, [phone, focusInside, notes])

  /** Runs a dismiss, then moves focus to the × now in the same place (or back to the page). */
  const dismissing = (event: MouseEvent<HTMLElement>, change: () => void) => {
    const buttons = [...(region.current?.querySelectorAll('[data-dismiss]') ?? [])]
    if (region.current?.contains(document.activeElement)) {
      refocus.current = Math.max(0, buttons.indexOf(event.currentTarget))
    }
    change()
  }
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

  const max = phone ? 1 : MAX_NOTES
  const collapsed = notes.length > max
  // A phone shows one card: the badge, or "N new badges" for a burst. A wider screen shows the
  // newest three under "N more new badges".
  const cards = phone && collapsed ? [] : notes.slice(-max)
  const more = phone ? notes.length : notes.length - max

  return (
    <>
      <output ref={region} className={styles.region} aria-live="polite">
        {collapsed && (
          <div className={styles.note}>
            <div className={styles.text}>
              <strong>
                {more} {phone ? '' : 'more '}new {more === 1 ? 'badge' : 'badges'}
              </strong>
              <Link to="/badges" className={styles.link} onClick={() => setNotes([])}>
                See your badges
              </Link>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className={styles.dismiss}
              data-dismiss
              aria-label="Dismiss all"
              onClick={(event) => dismissing(event, () => setNotes([]))}
            >
              ×
            </Button>
          </div>
        )}
        {cards.map((item) => (
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
              className={styles.dismiss}
              data-dismiss
              aria-label={`Dismiss ${item.title}`}
              onClick={(event) => dismissing(event, () => dismiss(item.key))}
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
              className={styles.dismiss}
              data-dismiss
              aria-label="Dismiss"
              onClick={(event) => dismissing(event, () => setTurnedOff(false))}
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
