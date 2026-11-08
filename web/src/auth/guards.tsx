import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'
import { Alert, Button, Spinner } from '../components'
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

/** Signed-in pages. Anyone else goes to the log-in page and comes back here afterwards. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { data: user, isPending, isError, refetch } = useCurrentUser()
  const location = useLocation()
  if (isPending) return <Checking />
  if (isError) return <Unreachable retry={() => void refetch()} />
  if (!user) {
    const from = location.pathname + location.search
    return <Navigate to="/login" replace state={{ from } satisfies FromState} />
  }
  return children
}

/** The log-in and register pages. Someone already logged in goes to the app instead. */
export function GuestOnly({ children }: { children: ReactNode }) {
  const { data: user, isPending } = useCurrentUser()
  if (isPending) return <Checking />
  if (user) return <Navigate to="/" replace />
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
