import { Link } from 'react-router'
import { buttonVariants } from '@/components/ui/button-variants'
import { AppShell } from '../components'

/** Any address the app doesn't have: in the same frame as the rest of the app, with the way back. */
export function NotFoundPage() {
  return (
    <AppShell width="page">
      <h1>Page not found</h1>
      <p>This page doesn't exist, or it has moved.</p>
      <Link to="/" className={buttonVariants({ variant: 'default' })}>
        Go to your modules
      </Link>
    </AppShell>
  )
}
