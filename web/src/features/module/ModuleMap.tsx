import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router'
import { Alert, Button, Card, ProgressBar, Spinner, Tag } from '../../components'
import type { TagTone } from '../../components'
import type { ModuleStatus, ModuleSummary } from './module.types.ts'
import { fetchModules } from './module.api.ts'
import styles from './ModuleMap.module.css'

/** Maps a module status to a Tag tone and display label. */
function statusDisplay(status: ModuleStatus): { tone: TagTone; label: string; icon: string } {
  switch (status) {
    case 'locked':
      return { tone: 'neutral', label: 'locked', icon: '🔒' }
    case 'open':
      return { tone: 'accent', label: 'open', icon: '○' }
    case 'in_progress':
      return { tone: 'warning', label: 'in progress', icon: '◑' }
    case 'complete':
      return { tone: 'success', label: 'complete', icon: '✓' }
  }
}

/** Formats a minute count as e.g. "12 min". */
function formatDuration(minutes: number): string {
  return `${minutes} min`
}

/** A single module row on the map. Locked modules are shown but not interactive. */
function ModuleRow({ module }: { module: ModuleSummary }) {
  const { tone, label, icon } = statusDisplay(module.status)
  const isLocked = module.status === 'locked'

  const cardContent = (
    <Card interactive={!isLocked} className={`${styles.row} ${isLocked ? styles.locked : ''}`}>
      <span className={styles.number} aria-hidden="true">
        {module.number}
      </span>
      <div className={styles.info}>
        <span className={styles.title}>{module.title}</span>
        {module.status === 'in_progress' && module.segmentCount > 0 && (
          <ProgressBar
            label={`Module ${module.number} progress`}
            value={module.currentSegmentPosition + 1}
            max={module.segmentCount}
            showCount
          />
        )}
      </div>
      <span className={styles.duration}>{formatDuration(module.estimatedMinutes)}</span>
      <Tag tone={tone} icon={icon}>
        {label}
      </Tag>
    </Card>
  )

  return (
    <li>
      {isLocked ? (
        cardContent
      ) : (
        <Link to={`/modules/${module.id}`} className={styles.cardLink}>
          {cardContent}
        </Link>
      )}
    </li>
  )
}

/** Picks the first in-progress module, else the first open module, to continue from. */
function findContinueTarget(modules: ModuleSummary[]): ModuleSummary | undefined {
  return modules.find((m) => m.status === 'in_progress') ?? modules.find((m) => m.status === 'open')
}

/**
 * The module map (FR-2.6): all seven modules with their state, estimated duration, and a
 * Continue button that picks up where the student left off.
 *
 * Route: / (index)
 */
export function ModuleMap() {
  const navigate = useNavigate()
  const query = useQuery({ queryKey: ['modules'], queryFn: fetchModules })

  if (query.isPending) return <Spinner label="Loading modules" />
  if (query.isError) return <Alert tone="danger">{query.error.message}</Alert>

  const modules = query.data
  const continueTarget = findContinueTarget(modules)
  const totalMinutes = modules.reduce((sum, m) => sum + m.estimatedMinutes, 0)

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.heading}>Graphs and breadth-first search</h1>
        <span className={styles.totalDuration}>About {totalMinutes} minutes in total</span>
      </div>

      <ul className={styles.list}>
        {modules.map((m) => (
          <ModuleRow key={m.id} module={m} />
        ))}
      </ul>

      {continueTarget && (
        <div className={styles.continueBar}>
          <Button variant="primary" onClick={() => void navigate(`/modules/${continueTarget.id}`)}>
            Continue module {continueTarget.number} →
          </Button>
        </div>
      )}
    </div>
  )
}
