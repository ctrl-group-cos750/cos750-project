import type { ReactNode } from 'react'
import mark from '../mark.svg'
import styles from './AppShell.module.css'

export type AppShellProps = {
  /** Links in the header, e.g. the module map. */
  nav?: ReactNode
  /** Right side of the header: points, the user's name, Log out. */
  actions?: ReactNode
  /** "reading" keeps text lines short; "wide" is for the module map and the BFS visualiser. */
  width?: 'reading' | 'wide'
  children: ReactNode
}

/** The frame around every signed-in page: header, then the page in <main>. */
export function AppShell({ nav, actions, width = 'wide', children }: AppShellProps) {
  return (
    <>
      <a className={styles.skip} href="#main">
        Skip to content
      </a>
      <header className={styles.header}>
        <div className={styles.bar}>
          <a href="/" className={styles.brand}>
            <img src={mark} alt="" className={styles.logo} />
            <span>Ctrl Academy</span>
          </a>
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
