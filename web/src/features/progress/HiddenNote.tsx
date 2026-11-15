import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import styles from './hiding.module.css'

/** The profile's "What you see while you learn" group, where everything is turned back on. */
export const SETTINGS_LINK = '/profile#what-you-see'

/** How long "Undo" is offered after something is hidden. */
export const UNDO_MS = 10_000

/**
 * Where something was before the student hid it (#214): "Skill profile hidden. Turn it back on
 * in your profile.", with Undo for a few seconds. Focus moves here, since the button that was
 * pressed has gone (WCAG 2.4.3), and it is a polite status (`<output>`). The time doesn't run
 * while the pointer is over the note or focus is on Undo, as for the badge notes (WCAG 2.2.1):
 * it starts again when they leave.
 */
export function HiddenNote({
  text,
  onUndo,
  className,
}: {
  text: string
  onUndo?: () => void
  className?: string
}) {
  const note = useRef<HTMLOutputElement>(null)
  const [undo, setUndo] = useState(true)
  const [pointer, setPointer] = useState(false)
  const [focusOnUndo, setFocusOnUndo] = useState(false)
  const paused = pointer || focusOnUndo
  useEffect(() => {
    note.current?.focus()
  }, [])
  useEffect(() => {
    if (paused || !undo) return
    const timer = setTimeout(() => {
      // Undo goes after a while; if focus was on it, it stays on the note.
      if (note.current?.contains(document.activeElement)) note.current.focus()
      setUndo(false)
    }, UNDO_MS)
    return () => clearTimeout(timer)
  }, [paused, undo])
  return (
    <output
      ref={note}
      tabIndex={-1}
      className={`${styles.note} ${className ?? ''}`}
      data-hidden-note
      onPointerEnter={() => setPointer(true)}
      onPointerLeave={() => setPointer(false)}
    >
      <span>
        {text} Turn it back on in <Link to={SETTINGS_LINK}>your profile</Link>.
      </span>
      {undo && onUndo && (
        <button
          type="button"
          className={styles.undo}
          onClick={onUndo}
          onFocus={() => setFocusOnUndo(true)}
          onBlur={() => setFocusOnUndo(false)}
        >
          Undo
        </button>
      )}
    </output>
  )
}
