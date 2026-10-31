import { useEffect, useState } from 'react'
import logo from './logo.svg'

type Health = { status: string; database: string }

function App() {
  const [health, setHealth] = useState<Health | 'down' | null>(null)

  useEffect(() => {
    fetch('/api/health')
      .then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
      .then(setHealth)
      .catch(() => setHealth('down'))
  }, [])

  return (
    <main>
      <img src={logo} alt="Control Group" className="logo" />
      <h1>Ctrl Academy</h1>
      <p>Graphs and breadth-first search, before the lecture.</p>
      <p className="status">
        API:{' '}
        {health === null
          ? 'checking…'
          : health === 'down'
            ? 'unreachable'
            : `${health.status}, database ${health.database}`}
      </p>
    </main>
  )
}

export default App
