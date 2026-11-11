import { useEffect } from 'react'

/** Asks the browser to confirm leaving the page while there are unsaved changes. */
export function useWarnBeforeLeaving(dirty: boolean) {
  useEffect(() => {
    if (!dirty) return
    const warn = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])
}
