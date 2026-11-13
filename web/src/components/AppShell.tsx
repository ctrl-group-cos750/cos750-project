import { useLayoutEffect, useRef, type ReactNode } from 'react'
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

/**
 * Keeps `--header-h` on the root element equal to the sticky header's height, as it wraps or the
 * text grows. base.css pads the page's scrolling by it, so a control reached with Tab or Shift+Tab
 * is scrolled clear of the header instead of under it (WCAG 2.2 2.4.11 Focus Not Obscured).
 * Firefox scrolls a focused control only when it is out of view, so one partly under the header
 * stayed there: a control that gets focus under the header is scrolled clear of it here too.
 */
function useHeaderHeight() {
  const header = useRef<HTMLElement>(null)
  useLayoutEffect(() => {
    const element = header.current
    const root = document.documentElement
    if (!element) return
    const measure = () => root.style.setProperty('--header-h', `${element.offsetHeight}px`)
    measure()
    const clear = (event: FocusEvent) => {
      const target = event.target
      if (!(target instanceof HTMLElement) || element.contains(target)) return
      if (getComputedStyle(target).position === 'fixed') return // the skip link, drawn above it
      const under = element.getBoundingClientRect().bottom - target.getBoundingClientRect().top
      if (under > 0) window.scrollBy({ top: -(under + 8), behavior: 'instant' })
    }
    document.addEventListener('focusin', clear)
    const observer = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(measure)
    observer?.observe(element)
    return () => {
      observer?.disconnect()
      document.removeEventListener('focusin', clear)
      root.style.removeProperty('--header-h')
    }
  }, [])
  return header
}

/** The frame around every signed-in page: header, then the page in <main>. */
export function AppShell({ nav, actions, width = 'wide', children }: AppShellProps) {
  const header = useHeaderHeight()
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
      <header ref={header} className={styles.header}>
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
