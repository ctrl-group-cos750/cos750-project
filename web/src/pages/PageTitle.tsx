import { useEffect, useSyncExternalStore } from 'react'
import { useLocation } from 'react-router'
import { pageTitleStore } from './usePageTitle.ts'

/** Each route's name for the browser tab, most specific first. */
const TITLES: [RegExp, string][] = [
  [/^\/$/, 'Your modules'],
  [/^\/login$/, 'Log in'],
  [/^\/register$/, 'Create an account'],
  [/^\/modules\/\d+/, 'Module'],
  [/^\/activities\//, 'Activity'],
  [/^\/videos\//, 'Video'],
  [/^\/graphs\//, 'BFS visualiser'],
  [/^\/report$/, 'Mastery report'],
  [/^\/review\//, 'Review path'],
  [/^\/badges$/, 'Badges'],
  [/^\/profile$/, 'Profile and settings'],
  [/^\/staff\/videos/, 'Videos · Staff portal'],
  [/^\/staff\/content/, 'Content · Staff portal'],
  [/^\/staff\/accounts/, 'Accounts · Staff portal'],
  [/^\/staff\/readiness/, 'Before the lecture · Staff portal'],
  [/^\/staff\/pilot/, 'Pilot · Staff portal'],
  [/^\/staff\/members/, 'Team · Staff portal'],
  [/^\/staff/, 'Staff portal'],
]

/** Names the browser tab after the page (WCAG 2.4.2), so a student with several tabs, or a screen
 * reader announcing the page, knows where they are. */
export function PageTitle() {
  const { pathname } = useLocation()
  const own = useSyncExternalStore(pageTitleStore.subscribe, pageTitleStore.get)
  useEffect(() => {
    const general = TITLES.find(([pattern]) => pattern.test(pathname))?.[1]
    // A student page takes its own name ("Module 4: Build BFS"); a staff page keeps the section
    // after it ("Module 4: Build BFS · Content · Staff portal").
    const name =
      own?.path !== pathname
        ? general
        : pathname.startsWith('/staff') && general
          ? `${own.name} · ${general}`
          : own.name
    document.title = name ? `${name} · Ctrl Academy` : 'Ctrl Academy'
  }, [pathname, own])
  return null
}
