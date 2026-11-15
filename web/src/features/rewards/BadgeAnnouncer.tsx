import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type MouseEvent,
} from 'react'
import { Link, useLocation } from 'react-router'
import { AchievementBadge, Button } from '../../components'
import { focusedElement, focusSafely } from '../../lib/focus.ts'
import { PHONE, useMediaQuery } from '../activities/pictures/useMediaQuery.ts'
import { useSkills } from '../progress/hooks.ts'
import { Medal } from '../progress/Medal.tsx'
import { MEDAL_NAMES, MEDAL_RULES } from '../progress/medals.ts'
import { useMarkRewardsSeen, useRewards, useRewardsSettings } from './hooks.ts'
import { newMedals, type MedalNote } from './medalNotes.ts'
import { unseen, type ShelfItem } from './shelf.ts'
import styles from './BadgeAnnouncer.module.css'
import { SETTINGS_LINK } from '../progress/HiddenNote.tsx'

const READY = 'ready-for-lecture'
// More than this at once (a burst after a mastery check) collapse into one line.
const MAX_NOTES = 3
// How long a note stays before it goes by itself, at every width (the badges page keeps it).
const NOTE_SECONDS = 8

function announcement(item: ShelfItem) {
  // "Now bronze" or "now gold" only for a real upgrade from a lower level (#214); a badge earned
  // straight at its level just names it.
  if (item.state === 'practised') return `${item.title}: practised`
  if (item.state === 'gold' || (item.state === 'bronze' && item.earned?.upgradedAt))
    return item.earned?.upgradedAt
      ? `${item.title} is now ${item.state}`
      : `${item.title}: ${item.state}`
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
 * The notes are a polite live region at the top right, under the header, at every width, so
 * they never cover a lesson's Previous and Next at the bottom (#215 review, 13 Nov review). On a
 * phone they take one card at most (a burst becomes "3 new badges"), a compact banner with the
 * badge's name and its links, not its description. They go by themselves after a few seconds
 * unless focus or the pointer is in them; the badges page keeps them. Their links are 44 px tall on a touch screen. Dismissing one moves focus to the next note's ×, or back to where the student was.
 */
export function BadgeAnnouncer() {
  const { data } = useRewards()
  const markSeen = useMarkRewardsSeen()
  const [notes, setNotes] = useState<ShelfItem[]>([])
  // Module medals as they are earned (#214), once each (medalNotes.ts).
  const skills = useSkills()
  const skillsPending = skills.isPending && !skills.isError
  const [medals, setMedals] = useState<MedalNote[]>([])
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
  const [pointerInside, setPointerInside] = useState(false)

  useEffect(() => {
    // Badges wait for the skill profile too, so a burst of badges and module medals (#214) comes
    // as one set of notes, not two a moment apart.
    if (!data || data.hideRewards || skillsPending) return
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
  }, [data, mutate, skillsPending])

  useEffect(() => {
    if (!data || !skills.data) return
    const fresh = newMedals(skills.data.modules, data.hideRewards)
    if (fresh.length === 0) return
    // The record of medals announced is in localStorage, outside React: reading it marks them
    // announced, so the notes can only be set here, once.
    // oxlint-disable-next-line react/set-state-in-effect
    setMedals((shown) => [
      ...shown.filter((n) => !fresh.some((f) => f.moduleId === n.moduleId)),
      ...fresh,
    ])
  }, [data, skills.data])

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

  // The notes go by themselves after a while at every width, unless the student is in them
  // (focus or the pointer); the badges page keeps them (13 Nov review).
  useEffect(() => {
    if (focusInside || pointerInside || notes.length + medals.length === 0) return
    const timer = setTimeout(() => {
      setNotes([])
      setMedals([])
    }, NOTE_SECONDS * 1000)
    return () => clearTimeout(timer)
  }, [focusInside, pointerInside, notes, medals])

  // On a phone the note is as wide as the page, so under the header it covered the page's heading
  // (#222 re-review, B3). While a note shows, the page moves down to make room for it (`--note-space`
  // on <main>, AppShell.module.css), but only when the note arrives near the top: further down,
  // pushing the page would move the text being read, so the note sits over it as before, and goes
  // by itself. After every render, so the space follows the notes as they come and go.
  //
  // The space is measured from the note's laid-out height (`offsetHeight`), not its on-screen box,
  // which includes the slide-in transform and came out about 60 px too tall (#222 re-review, nit 2).
  //
  // When the note goes while the page is scrolled, taking the space away would move everything up
  // by its height, and a focused control could end up under the header (WCAG 2.4.11; #222
  // re-review, new finding 1). So only as much is taken away as scrolling back by the same amount
  // makes up for, and nothing on screen moves. The rest goes in one step once the student has
  // scrolled down at least that far, so it can be made up for too, or on the next page. At the top
  // of the page it all goes at once: nothing can end up under the header from there. The page is
  // scrolled back by the space taken away at once, then on the next frame by whatever drift is
  // left against where the content was: the new layout isn't always readable straight away, and
  // a browser that anchors the scroll itself mustn't be corrected twice.
  const reserved = useRef(0) // the space set on <main>
  const forNote = useRef(false) // whether a note showing has room made for it
  const { pathname } = useLocation()
  const page = useRef(pathname) // the page the space was made on
  const shrink = useCallback((main: HTMLElement, wanted: number) => {
    const old = reserved.current
    if (wanted === old) return
    const scrolled = window.scrollY
    const space = wanted > old || scrolled <= 0 ? wanted : Math.max(wanted, old - scrolled)
    if (space === old) return
    const anchor = main.firstElementChild
    const before = anchor?.getBoundingClientRect().top
    if (space > 0) main.style.setProperty('--note-space', `${space}px`)
    else main.style.removeProperty('--note-space')
    reserved.current = space
    if (space < old && scrolled > 0) {
      window.scrollBy(0, space - old)
      requestAnimationFrame(() => {
        if (!anchor || before === undefined) return
        const drift = anchor.getBoundingClientRect().top - before
        if (Math.abs(drift) >= 1) window.scrollBy(0, drift)
      })
    }
  }, [])
  useLayoutEffect(() => {
    const element = region.current
    const main = element?.closest('main')
    if (!element || !main) return
    // A new page starts without what was left over from a note that has gone.
    if (page.current !== pathname) {
      page.current = pathname
      if (!forNote.current && reserved.current > 0) {
        main.style.removeProperty('--note-space')
        reserved.current = 0
      }
    }
    const height = element.offsetHeight
    const bottom = element.getBoundingClientRect().top + height
    forNote.current = phone && height > 0 && (forNote.current || window.scrollY < bottom)
    // How far the note reaches below the top of <main> (under the header), whatever the scroll.
    shrink(main, forNote.current ? Math.max(0, Math.ceil(bottom - main.offsetTop)) : 0)
  })
  // Space left over from a note that has gone: taken away once scrolled past it (above).
  useEffect(() => {
    const onScroll = () => {
      const main = region.current?.closest('main')
      const left = reserved.current
      if (main && !forNote.current && left > 0 && window.scrollY >= left) shrink(main, 0)
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [shrink])
  useEffect(
    () => () => {
      region.current?.closest('main')?.style.removeProperty('--note-space')
    },
    [],
  )

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
          setMedals([])
          setTurnedOff(true)
        },
      },
    )

  const max = phone ? 1 : MAX_NOTES
  // Medal notes (#214) count with the badge notes: together at most `max` cards.
  const total = notes.length + medals.length
  const collapsed = total > max
  // A phone shows one card: the badge, or "N new badges" for a burst. A wider screen shows the
  // newest three under "N more new badges".
  const shownMedals = phone && collapsed ? [] : medals.slice(-max)
  const room = max - shownMedals.length
  const cards = (phone && collapsed) || room <= 0 ? [] : notes.slice(-room)
  const more = total - shownMedals.length - cards.length
  const clearAll = () => {
    setNotes([])
    setMedals([])
  }

  return (
    <>
      <output
        ref={region}
        className={styles.region}
        aria-live="polite"
        onPointerEnter={() => setPointerInside(true)}
        onPointerLeave={() => setPointerInside(false)}
      >
        {collapsed && (
          <div className={styles.note}>
            <div className={styles.text}>
              <strong>
                {more} {phone ? '' : 'more '}new {more === 1 ? 'badge' : 'badges'}
              </strong>
              <Link to="/badges" className={styles.link} onClick={clearAll}>
                See your badges
              </Link>
            </div>
            <Button
              variant="ghost"
              size="sm"
              className={styles.dismiss}
              data-dismiss
              aria-label="Dismiss all"
              onClick={(event) => dismissing(event, clearAll)}
            >
              ×
            </Button>
          </div>
        )}
        {shownMedals.map((note) => {
          const title = `Module ${note.moduleId}: ${note.tier} medal`
          return (
            <div key={note.key} className={styles.note}>
              <Medal tier={note.tier} size={48} label={`${MEDAL_NAMES[note.tier]} medal`} />
              <div className={styles.text}>
                <strong>{title}</strong>
                <span className={styles.description}>
                  {MEDAL_NAMES[note.tier]}: {MEDAL_RULES[note.tier]}.
                </span>
                <span className={styles.links}>
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
                aria-label={`Dismiss ${title}`}
                onClick={(event) =>
                  dismissing(event, () =>
                    setMedals((shown) => shown.filter((n) => n.key !== note.key)),
                  )
                }
              >
                ×
              </Button>
            </div>
          )
        })}
        {cards.map((item) => (
          <div key={item.key} className={styles.note}>
            <AchievementBadge achievement={item.achievement} state={item.state} size={48} />
            <div className={styles.text}>
              <strong>{announcement(item)}</strong>
              <span className={styles.description}>{item.achievement.description}</span>
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
                <Link
                  to={SETTINGS_LINK}
                  className={styles.link}
                  onClick={() => setTurnedOff(false)}
                >
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
