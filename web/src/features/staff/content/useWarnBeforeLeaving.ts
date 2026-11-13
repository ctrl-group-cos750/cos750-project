import { useEffect, useRef } from 'react'
import { useBlocker } from 'react-router'

export const LEAVE_UNSAVED = 'You have changes that are not saved. Leave this page and lose them?'

/**
 * While there are unsaved changes, asks before they are lost: the browser's own question when the
 * tab is closed or reloaded (beforeunload), and a confirm when a link in the app (the staff
 * navigation, "All content", Back) would leave the editor (useBlocker). Returns `allowLeaving`,
 * for the editor's own moves after a save or a delete, which must not ask.
 */
export function useWarnBeforeLeaving(dirty: boolean): () => void {
  const allowed = useRef(false)
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      dirty && !allowed.current && currentLocation.pathname !== nextLocation.pathname,
  )

  useEffect(() => {
    if (blocker.state !== 'blocked') return
    if (window.confirm(LEAVE_UNSAVED)) blocker.proceed()
    else blocker.reset()
  }, [blocker])

  useEffect(() => {
    allowed.current = false
    if (!dirty) return
    const warn = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])

  return () => {
    allowed.current = true
  }
}
