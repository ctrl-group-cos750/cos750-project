import { useEffect } from 'react'
import { useLocation } from 'react-router'

// A page's own, more specific name once it has loaded ("Module 4: Build BFS"), for its address.
let specific: { path: string; name: string } | null = null
const listeners = new Set<() => void>()
function setSpecific(next: typeof specific) {
  specific = next
  for (const listener of listeners) listener()
}
function subscribe(listener: () => void) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/**
 * Names the tab after what the page shows, once it knows: the module, activity or video, or the
 * item being edited. Undefined while loading, when the route's general name stays.
 */
export function usePageTitle(name: string | undefined) {
  const { pathname } = useLocation()
  useEffect(() => {
    if (!name) return
    const mine = { path: pathname, name }
    setSpecific(mine)
    return () => {
      if (specific === mine) setSpecific(null)
    }
  }, [name, pathname])
}

/** Read by PageTitle, which puts the name in the tab. */
export const pageTitleStore = { subscribe, get: () => specific }
