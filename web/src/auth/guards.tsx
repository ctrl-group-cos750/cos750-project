import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'
import { Alert, Button, Spinner } from '../components'
import { LandingPage } from '../pages/LandingPage.tsx'
import { useCurrentUser } from './hooks.ts'
import styles from './guards.module.css'

/** Where to go back to after logging in. */
export type FromState = { from?: string } | null

function Checking() {
  return (
    <div className={styles.centre}>
      <Spinner label="Checking your session" />
    </div>
  )
}

function Unreachable({ retry }: { retry: () => void }) {
  return (
    <div className={styles.centre}>
      <Alert tone="danger" title="Can't reach Ctrl Academy">
        <p>Check your connection and try again.</p>
        <Button variant="secondary" size="sm" onClick={retry}>
          Try again
        </Button>
      </Alert>
    </div>
  )
}

/** Signed-in pages. A visitor at `/` sees the landing page (what Ctrl Academy is, and the way in);
 * anywhere else, they go to the log-in page and come back here afterwards. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { data: user, isPending, isError, refetch } = useCurrentUser()
  const location = useLocation()
  if (isPending) return <Checking />
  if (isError) return <Unreachable retry={() => void refetch()} />
  if (!user) {
    if (location.pathname === '/') return <LandingPage />
    const from = location.pathname + location.search
    return <Navigate to="/login" replace state={{ from } satisfies FromState} />
  }
  return children
}

/** The log-in and register pages. Someone already logged in goes to the app instead: to the page
 * they were sent here from, if any. (This also runs the moment a login succeeds, before the log-in
 * page's own redirect, so it must honour `from` too, or the student always lands on the home page.) */
export function GuestOnly({ children }: { children: ReactNode }) {
  const { data: user, isPending } = useCurrentUser()
  const from = (useLocation().state as FromState)?.from
  if (isPending) return <Checking />
  if (user)
    return <Navigate to={from?.startsWith('/') && !from.startsWith('//') ? from : '/'} replace />
  return children
}

/** The staff portal (/staff and everything under it). Inside RequireAuth; a student gets a plain refusal. */
export function RequireStaff({ children }: { children: ReactNode }) {
  const { data: user } = useCurrentUser()
  if (!user?.isStaff) {
    return <Alert tone="danger">Only team members can open this page.</Alert>
  }
  return children
}
