import { useEffect, useId, useRef, useState } from 'react'
import { Link } from 'react-router'
import { Avatar, Button } from '../components'
import type { User } from '../auth/api.ts'
import styles from './AccountMenu.module.css'

type AccountMenuProps = {
  user: User
  onLogout: () => void
  loggingOut: boolean
}

/**
 * The `Account` menu in the header (SE document wireframes, #111): the student's picture and name,
 * opening their profile, their badges and log out. A disclosure (a button that shows a list of
 * links), not an ARIA menu, so it reads and works like any other links: Tab moves through it,
 * Escape or a click outside closes it and puts focus back on the button.
 */
export function AccountMenu({ user, onLogout, loggingOut }: AccountMenuProps) {
  const [open, setOpen] = useState(false)
  const wrapper = useRef<HTMLDivElement>(null)
  const button = useRef<HTMLButtonElement>(null)
  const listId = useId()

  useEffect(() => {
    if (!open) return
    function outside(event: PointerEvent) {
      if (!wrapper.current?.contains(event.target as Node)) setOpen(false)
    }
    function escape(event: KeyboardEvent) {
      if (event.key !== 'Escape') return
      setOpen(false)
      button.current?.focus()
    }
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('pointerdown', outside)
      document.removeEventListener('keydown', escape)
    }
  }, [open])

  const close = () => setOpen(false)

  return (
    <div className={styles.wrapper} ref={wrapper}>
      <button
        ref={button}
        type="button"
        className={styles.trigger}
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen((o) => !o)}
      >
        <Avatar avatar={user.avatar} name={user.displayName} size={32} />
        <span className={styles.name}>{user.displayName}</span>
        <span className="visually-hidden">: your account</span>
        <span aria-hidden="true" className={styles.chevron}>
          ▾
        </span>
      </button>
      <div id={listId} className={styles.panel} hidden={!open}>
        <ul className={styles.items}>
          <li>
            <Link to="/profile" className={styles.item} onClick={close}>
              Profile
            </Link>
          </li>
          <li>
            <Link to="/badges" className={styles.item} onClick={close}>
              Badges
            </Link>
          </li>
        </ul>
        <div className={styles.footer}>
          <Button variant="secondary" size="sm" loading={loggingOut} onClick={onLogout}>
            Log out
          </Button>
        </div>
      </div>
    </div>
  )
}
