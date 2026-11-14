import { Outlet, useLocation, useNavigate } from 'react-router'
import { useCurrentUser, useLogout } from '../auth/hooks.ts'
import { Alert, AppShell } from '../components'
import { setPreferenceOwner } from '../features/progress/preferences.ts'
import { CompanionAnnouncer } from '../features/companion/Companion.tsx'
import { BadgeAnnouncer } from '../features/rewards/BadgeAnnouncer.tsx'
import { useAppliedBackground } from '../theme/background.ts'
import { ThemeMenu } from '../theme/ThemeMenu.tsx'
import { AccountMenu } from './AccountMenu.tsx'

/** Every signed-in page: the header (the logo, which goes to the modules; the theme and background
 * menu; the account menu with the report, badges, profile, the staff portal for team members and
 * Log out), then the page, and new badges announced as they are earned. No row of nav buttons: the modules
 * are home, and everything else is one click away in the menu. */
export function SignedInLayout() {
  const { data: user } = useCurrentUser()
  const logout = useLogout()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  // The feedback switches (confetti, comments) are this student's on this device (#215 review).
  setPreferenceOwner(user?.id ?? null)
  // The page background is theirs too (#214).
  useAppliedBackground()
  // One-thing pages sit in a centred column; the map, the visualiser, the staff portal and an
  // activity (which has the progress panel beside it, #214) use the full width.
  const width = /^\/(report|review|badges|profile|videos)(\/|$)/.test(pathname) ? 'page' : 'wide'
  // The overview pages let the background show through their cards; lessons, activities, the
  // quick check, the profile and the staff pages keep them solid behind reading (#214).
  const surfaces = /^\/(report|badges)?\/?$/.test(pathname) ? 'tinted' : 'solid'

  return (
    <AppShell
      width={width}
      surfaces={surfaces}
      actions={
        user && (
          <>
            <ThemeMenu />
            <AccountMenu
              user={user}
              loggingOut={logout.isPending}
              onLogout={() =>
                logout.mutate(undefined, {
                  onSuccess: () => void navigate('/login', { replace: true }),
                })
              }
            />
          </>
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
      <CompanionAnnouncer />
    </AppShell>
  )
}
