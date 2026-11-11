import { Link } from 'react-router'
import { AppShell } from '../components'

export function NotFoundPage() {
  return (
    <AppShell width="reading">
      <h1>Page not found</h1>
      <p>
        This page doesn't exist. <Link to="/">Go to the start</Link>.
      </p>
    </AppShell>
  )
}
