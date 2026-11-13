import { useEffect } from 'react'
import { useLocation } from 'react-router'

/** Each route's name for the browser tab, most specific first. */
const TITLES: [RegExp, string][] = [
  [/^\/$/, 'Your modules'],
  [/^\/login$/, 'Log in'],
  [/^\/register$/, 'Create an account'],
  [/^\/modules\/\d+\/check$/, 'Quick check'],
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
  useEffect(() => {
    const name = TITLES.find(([pattern]) => pattern.test(pathname))?.[1]
    document.title = name ? `${name} · Ctrl Academy` : 'Ctrl Academy'
  }, [pathname])
  return null
}
