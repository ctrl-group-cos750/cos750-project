import { Link, Outlet, useNavigate } from 'react-router'
import { useCurrentUser, useLogout } from '../auth/hooks.ts'
import { Alert, AppShell, Button } from '../components'
import styles from './SignedInLayout.module.css'

/** Every signed-in page: the header with the student's name and Log out, then the page. */
export function SignedInLayout() {
  const { data: user } = useCurrentUser()
  const logout = useLogout()
  const navigate = useNavigate()

  return (
    <AppShell
      actions={
        <>
          {user?.isStaff && <Link to="/staff/videos">Videos</Link>}
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
