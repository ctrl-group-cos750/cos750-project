import { NavLink, Outlet, useNavigate } from 'react-router'
import { buttonVariants } from '@/components/ui/button-variants'
import { cn } from '@/lib/utils'
import { useCurrentUser, useLogout } from '../auth/hooks.ts'
import { Alert, AppShell, Button } from '../components'
import styles from './SignedInLayout.module.css'

/** Every signed-in page: the header (the staff portal link for team members, the student's name
 * and Log out), then the page. */
export function SignedInLayout() {
  const { data: user } = useCurrentUser()
  const logout = useLogout()
  const navigate = useNavigate()

  return (
    <AppShell
      nav={
        user?.isStaff && (
          <NavLink
            to="/staff"
            className={({ isActive }) =>
              cn(
                buttonVariants({ variant: isActive ? 'secondary' : 'ghost', size: 'lg' }),
                'text-foreground',
              )
            }
          >
            Staff portal
          </NavLink>
        )
      }
      actions={
        <>
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
    </AppShell>
  )
}
