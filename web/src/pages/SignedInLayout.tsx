import { NavLink, Outlet, useNavigate } from 'react-router'
import { buttonVariants } from '@/components/ui/button-variants'
import { cn } from '@/lib/utils'
import { useCurrentUser, useLogout } from '../auth/hooks.ts'
import { Alert, AppShell } from '../components'
import { BadgeAnnouncer } from '../features/rewards/BadgeAnnouncer.tsx'
import { AccountMenu } from './AccountMenu.tsx'

const navClass = ({ isActive }: { isActive: boolean }) =>
  cn(buttonVariants({ variant: isActive ? 'secondary' : 'ghost', size: 'lg' }), 'text-foreground')

/** Every signed-in page: the header (Report, the staff portal link for team members, and the
 * account menu with the student's profile, badges and Log out), then the page, and new badges
 * announced as they are earned. */
export function SignedInLayout() {
  const { data: user } = useCurrentUser()
  const logout = useLogout()
  const navigate = useNavigate()

  return (
    <AppShell
      nav={
        <>
          <NavLink to="/report" className={navClass}>
            Report
          </NavLink>
          {user?.isStaff && (
            <NavLink to="/staff" className={navClass}>
              Staff portal
            </NavLink>
          )}
        </>
      }
      actions={
        user && (
          <AccountMenu
            user={user}
            loggingOut={logout.isPending}
            onLogout={() =>
              logout.mutate(undefined, {
                onSuccess: () => void navigate('/login', { replace: true }),
              })
            }
          />
        )
      }
    >
      {logout.error && (
        <Alert tone="danger" title="You are still logged in">
          {logout.error.message}
        </Alert>
      )}
      <Outlet />
      <BadgeAnnouncer />
    </AppShell>
  )
}
