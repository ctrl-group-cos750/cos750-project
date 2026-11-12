import type { ReactNode } from 'react'
import { Link, useInRouterContext } from 'react-router'
import mark from '../mark.svg'
import styles from './AppShell.module.css'

export type AppShellProps = {
  /** Links in the header, e.g. the module map. */
  nav?: ReactNode
  /** Right side of the header: points, the user's name, Log out. */
  actions?: ReactNode
  /** "reading" keeps text lines short; "page" is a centred column for one-thing pages (the
   * report, a review path, badges, the profile, an activity); "wide" is for the module map, the
   * BFS visualiser and the staff portal. */
  width?: 'reading' | 'page' | 'wide'
  children: ReactNode
}

/** The frame around every signed-in page: header, then the page in <main>. */
export function AppShell({ nav, actions, width = 'wide', children }: AppShellProps) {
  // A client-side link inside the app, so the logo doesn't reload everything; a plain one in
  // the UI kit and the component tests, which have no router.
  const inRouter = useInRouterContext()
  const brand = (
    <>
      <img src={mark} alt="" className={styles.logo} />
      <span>Ctrl Academy</span>
      <span className="visually-hidden">: your modules</span>
    </>
  )
  return (
    <>
      <a className={styles.skip} href="#main">
        Skip to content
      </a>
      <header className={styles.header}>
        <div className={`${styles.bar} ${styles.wide}`}>
          {inRouter ? (
            <Link to="/" className={styles.brand}>
              {brand}
            </Link>
          ) : (
            <a href="/" className={styles.brand}>
              {brand}
            </a>
          )}
          {nav && (
            <nav aria-label="Main" className={styles.nav}>
              {nav}
            </nav>
          )}
          {actions && <div className={styles.actions}>{actions}</div>}
        </div>
      </header>
      <main id="main" className={`${styles.main} ${styles[width]}`}>
        {children}
      </main>
    </>
  )
}
