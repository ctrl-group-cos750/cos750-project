import { NavLink, Outlet, useLocation, useNavigate } from 'react-router'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { buttonVariants } from '@/components/ui/button-variants'
import { cn } from 'cn'
import { useCurrentUser, useLogout } from '../auth/hooks.ts'
import { AppShell } from '../components'
import { ErrorBoundary } from '../components/errors/ErrorBoundary.tsx'
import { BadgeAnnouncer } from '../features/rewards/BadgeAnnouncer.tsx'
import { useRewards } from '../features/rewards/hooks.ts'

const navClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    buttonVariants({ variant: isActive ? 'secondary' : 'ghost', size: 'lg' }),
    'text-foreground no-underline',
  )

/** "Points and badges", with the total when the student shows them (FR-9.4, FR-9.5). */
function RewardsLink() {
  const { data: rewards } = useRewards()
  const showPoints = rewards && !rewards.hideRewards
  return (
    <NavLink to="/badges" className={navClass}>
      {showPoints ? (
        <>
          Points and badges{' '}
          <span className="rounded-full bg-accent px-2 text-xs font-semibold text-accent-foreground tabular-nums">
            {rewards.points}
            <span className="visually-hidden"> points</span>
          </span>
        </>
      ) : (
        'Points and badges'
      )}
    </NavLink>
  )
}

/**
 * Every signed-in page: the header (the module map, points and badges, the staff portal for
 * team members, the user's name and Log out), then the page, and new badges announced as they
 * are earned. A page that crashes shows a message in place of the page, and the header stays.
 */
export function SignedInLayout() {
  const { data: user } = useCurrentUser()
  const logout = useLogout()
  const navigate = useNavigate()
  const { pathname } = useLocation()

  return (
    <AppShell
      nav={
        <>
          <NavLink to="/" end className={navClass}>
            Modules
          </NavLink>
          <RewardsLink />
          {user?.isStaff && (
            <NavLink to="/staff" className={navClass}>
              Staff portal
            </NavLink>
          )}
        </>
      }
      actions={
        <>
          <span className="hidden font-semibold text-muted-foreground sm:inline">
            {user?.displayName}
          </span>
          <Button
            variant="outline"
            loading={logout.isPending}
            onClick={() =>
              logout.mutate(undefined, {
                onSuccess: () => void navigate('/login', { replace: true }),
              })
            }
          >
            Log out
          </Button>
        </>
      }
    >
      {logout.error && (
        <Alert variant="destructive" className="mb-6">
          <AlertTitle>You are still logged in</AlertTitle>
          <AlertDescription>{logout.error.message}</AlertDescription>
        </Alert>
      )}
      <ErrorBoundary resetKey={pathname}>
        <Outlet />
      </ErrorBoundary>
      <BadgeAnnouncer />
    </AppShell>
  )
}
