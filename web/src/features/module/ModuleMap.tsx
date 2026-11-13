import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router'
import { useCurrentUser } from '../../auth/hooks.ts'
import { Alert, Button, Card, ProgressBar, Spinner, Tag } from '../../components'
import type { TagTone } from '../../components'
import type { ModuleSummary } from './module.types.ts'
import { fetchModules } from './module.api.ts'
import { minutesProgress } from './minutes.ts'
import styles from './ModuleMap.module.css'

/** A module with nothing to work through yet (no segments, so it can't be completed). It doesn't
 * lock the ones after it (#123), and it isn't shown as "open" for ever or offered by Continue:
 * it reads "coming soon" until it has content (#146). */
function notReady(module: ModuleSummary): boolean {
  return module.segmentCount === 0 && module.status !== 'complete' && module.status !== 'locked'
}

/** Maps a module status to a Tag tone and display label. */
function statusDisplay(module: ModuleSummary): { tone: TagTone; label: string; icon: string } {
  if (notReady(module)) return { tone: 'neutral', label: 'coming soon', icon: '…' }
  switch (module.status) {
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

/** Where the student is in a module, counted the way the module page counts it ("Segment 4 of
 * 8"): only the segments this student is shown, so support they don't need isn't counted. */
function segmentProgress(module: ModuleSummary): { value: number; max: number } {
  const max = module.shownSegmentCount ?? module.segmentCount
  const passed = module.shownSegmentsPassed ?? module.currentSegmentPosition
  return { value: Math.min(passed + 1, max), max }
}

/** The one thing to do next, at the top of the page: the module to continue, what it is about,
 * and one button; or, when every module is done, the way to the report. */
function NextUp({ modules, next }: { modules: ModuleSummary[]; next: ModuleSummary | undefined }) {
  const navigate = useNavigate()
  const { data: user } = useCurrentUser()
  const started = modules.some((m) => m.status !== 'open' && m.status !== 'locked')
  const allDone = modules.every((m) => m.status === 'complete' || m.segmentCount === 0)
  const name = user?.displayName
  if (allDone)
    return (
      <Card className={styles.next}>
        <h2 className={styles.nextTitle}>Every module is done{name ? `, ${name}` : ''}</h2>
        <p className={styles.nextText}>
          Your mastery report shows which objectives you've met and offers a review path for any you
          haven't.
        </p>
        <Button variant="primary" onClick={() => void navigate('/report')}>
          See your mastery report →
        </Button>
      </Card>
    )
  if (!next) return null
  return (
    <Card className={styles.next}>
      <p className={styles.nextText}>
        {started
          ? `Welcome back${name ? `, ${name}` : ''}. Next up:`
          : `Welcome${name ? `, ${name}` : ''}. Start here:`}
      </p>
      <h2 className={styles.nextTitle}>
        Module {next.number} · {next.title}
      </h2>
      {next.goals.length > 0 && (
        <ul className={styles.goals}>
          {next.goals.map((goal) => (
            <li key={goal}>{goal}</li>
          ))}
        </ul>
      )}
      {next.status === 'in_progress' && (
        <ProgressBar
          label={`Where you are in module ${next.number}`}
          {...segmentProgress(next)}
          showCount
        />
      )}
      <div className={styles.nextActions}>
        <Button variant="primary" onClick={() => void navigate(`/modules/${next.id}`)}>
          {next.status === 'in_progress'
            ? `Continue module ${next.number}`
            : `Start module ${next.number}`}{' '}
          →
        </Button>
        <span className={styles.duration}>About {next.estimatedMinutes} min</span>
      </div>
    </Card>
  )
}

/** A single module row on the map. Locked modules are shown but not interactive. */
function ModuleRow({ module }: { module: ModuleSummary }) {
  const { tone, label, icon } = statusDisplay(module)
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
            {...segmentProgress(module)}
            showCount
          />
        )}
      </div>
      <span className={styles.meta}>
        <span className={styles.duration}>{formatDuration(module.estimatedMinutes)}</span>
        <Tag tone={tone} icon={icon}>
          {label}
        </Tag>
      </span>
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

/** Picks the first in-progress module, else the first open module, to continue from; never one
 * with nothing in it yet (#146). */
function findContinueTarget(modules: ModuleSummary[]): ModuleSummary | undefined {
  const ready = modules.filter((m) => m.segmentCount > 0)
  return ready.find((m) => m.status === 'in_progress') ?? ready.find((m) => m.status === 'open')
}

/**
 * The module map (FR-2.6): all seven modules with their state, estimated duration, and a
 * Continue button that picks up where the student left off.
 *
 * Route: / (index)
 */
export function ModuleMap() {
  const query = useQuery({ queryKey: ['modules'], queryFn: fetchModules })

  if (query.isPending) return <Spinner label="Loading modules" />
  if (query.isError) return <Alert tone="danger">{query.error.message}</Alert>

  const modules = query.data
  const continueTarget = findContinueTarget(modules)
  const minutes = minutesProgress(modules)

  return (
    <div className={styles.page}>
      <div className={styles.top}>
        <div className={styles.header}>
          <h1 className={styles.heading}>Graphs and breadth-first search</h1>
          <span className={styles.totalDuration}>
            {minutes.done === 0
              ? `About ${minutes.total} minutes in total`
              : minutes.done >= minutes.total
                ? `All ${minutes.total} minutes done`
                : `About ${minutes.done} of ${minutes.total} minutes done · about ${minutes.total - minutes.done} left`}
          </span>
        </div>
        {minutes.done > 0 && (
          <ProgressBar
            label="Course progress in minutes"
            value={minutes.done}
            max={minutes.total}
          />
        )}
      </div>

      <div className={styles.side}>
        <NextUp modules={modules} next={continueTarget} />
      </div>

      <section aria-labelledby="all-modules" className={styles.all}>
        <h2 id="all-modules" className={styles.allHeading}>
          All modules
        </h2>
        <ul className={styles.list}>
          {modules.map((m) => (
            <ModuleRow key={m.id} module={m} />
          ))}
        </ul>
      </section>
    </div>
  )
}
