import { AppShell } from '../components'
import { ErrorPage } from '../components/errors/ErrorPage.tsx'

/** Any address the app doesn't know, e.g. a mistyped or old link. */
export function NotFoundPage() {
  return (
    <AppShell width="reading">
      <ErrorPage title="We can't find that page">
        <p>The link may be mistyped or out of date. Your modules are where you left them.</p>
      </ErrorPage>
    </AppShell>
  )
}
