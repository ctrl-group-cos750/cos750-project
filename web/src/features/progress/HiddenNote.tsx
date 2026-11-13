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
 * pressed has gone (WCAG 2.4.3), and it is a polite status (`<output>`).
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
  useEffect(() => {
    note.current?.focus()
    const timer = setTimeout(() => {
      // Undo goes after a while; if focus was on it, it stays on the note.
      if (note.current?.contains(document.activeElement)) note.current.focus()
      setUndo(false)
    }, UNDO_MS)
    return () => clearTimeout(timer)
  }, [])
  return (
    <output
      ref={note}
      tabIndex={-1}
      className={`${styles.note} ${className ?? ''}`}
      data-hidden-note
    >
      <span>
        {text} Turn it back on in <Link to={SETTINGS_LINK}>your profile</Link>.
      </span>
      {undo && onUndo && (
        <button type="button" className={styles.undo} onClick={onUndo}>
          Undo
        </button>
      )}
    </output>
  )
}
