import { useEffect, useState } from 'react'
import { useCurrentUser } from '../auth/hooks.ts'
import { Card } from '../components'
import styles from './HomePage.module.css'

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
        <h2 className={styles.cardTitle}>Graphs and breadth-first search</h2>
        <p>The modules are on their way. You'll find them here soon.</p>
      </Card>
      <p className={styles.status}>
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
