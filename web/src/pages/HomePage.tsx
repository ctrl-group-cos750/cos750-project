import { useEffect, useState } from 'react'
import { useCurrentUser } from '../auth/hooks.ts'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

type Health = { status: string; database: string }

/** Placeholder until the module map (#15) replaces it. */
export function HomePage() {
  const { data: user } = useCurrentUser()
  const [health, setHealth] = useState<Health | 'down' | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then(setHealth)
      .catch(() => setHealth('down'))
  }, [])

  return (
    <>
      <h1>Welcome, {user?.displayName}</h1>
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">
            <h2 className="m-0 text-xl">Graphs and breadth-first search</h2>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="m-0">The modules are on their way. You'll find them here soon.</p>
        </CardContent>
      </Card>
      <p className="mt-8 font-mono text-sm text-muted-foreground">
        API:{' '}
        {health === null
          ? 'checking…'
          : health === 'down'
            ? 'unreachable'
            : `${health.status}, database ${health.database}`}
      </p>
    </>
  )
}
