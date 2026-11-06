import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { useCurrentUser } from './hooks.ts'

/** Where to go back to after logging in. */
export type FromState = { from?: string } | null

function Checking() {
  return (
    <div className="grid min-h-[60vh] place-items-center p-4">
      <Spinner label="Checking your session" />
    </div>
  )
}

function Unreachable({ retry }: { retry: () => void }) {
  return (
    <div className="grid min-h-[60vh] place-items-center p-4">
      <Alert variant="destructive" className="max-w-md">
        <AlertTitle>Can't reach Ctrl Academy</AlertTitle>
        <AlertDescription>
          <p>Check your connection and try again.</p>
          <Button variant="outline" size="sm" onClick={retry}>
            Try again
          </Button>
        </AlertDescription>
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
    return (
      <Alert variant="destructive">
        <AlertDescription>Only team members can open this page.</AlertDescription>
      </Alert>
    )
  }
  return children
}
