import { NavLink, Outlet, useNavigate } from 'react-router'
import { buttonVariants } from '@/components/ui/button-variants'
import { cn } from '@/lib/utils'
import { useCurrentUser, useLogout } from '../auth/hooks.ts'
import { Alert, AppShell, Button } from '../components'
import { BadgeAnnouncer } from '../features/rewards/BadgeAnnouncer.tsx'
import { ThemeToggle } from '../theme/ThemeToggle.tsx'
import styles from './SignedInLayout.module.css'

const navClass = ({ isActive }: { isActive: boolean }) =>
  cn(buttonVariants({ variant: isActive ? 'secondary' : 'ghost', size: 'lg' }), 'text-foreground')

/** Every signed-in page: the header (Badges, the staff portal link for team members, the
 * student's name and Log out), then the page, and new badges announced as they are earned. */
export function SignedInLayout() {
  const { data: user } = useCurrentUser()
  const logout = useLogout()
  const navigate = useNavigate()

  return (
    <AppShell
      nav={
        <>
          <NavLink to="/badges" className={navClass}>
            Badges
          </NavLink>
          {user?.isStaff && (
            <NavLink to="/staff" className={navClass}>
              Staff portal
            </NavLink>
          )}
        </>
      }
      actions={
        <>
          <ThemeToggle />
          <span className={styles.name}>{user?.displayName}</span>
          <Button
            variant="secondary"
            size="sm"
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
        <Alert tone="danger" title="You are still logged in">
          {logout.error.message}
        </Alert>
      )}
      <Outlet />
      <BadgeAnnouncer />
    </AppShell>
  )
}
