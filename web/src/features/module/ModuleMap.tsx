import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router'
import { useCurrentUser } from '../../auth/hooks.ts'
import { Alert, Button, Card, ProgressBar, Spinner, Tag } from '../../components'
import type { TagTone } from '../../components'
import type { ModuleSummary } from './module.types.ts'
import { fetchModules } from './module.api.ts'
import { minutesProgress } from './minutes.ts'
import { useSkills } from '../progress/hooks.ts'
import { Medal } from '../progress/Medal.tsx'
import { medalText } from '../progress/medals.ts'
import type { Medal as MedalTier } from '../progress/skills.api.ts'
import { SkillProfileCard } from '../progress/SkillProfileCard.tsx'
import { useRewards } from '../rewards/hooks.ts'
import { useMediaQuery } from '../activities/pictures/useMediaQuery.ts'
import styles from './ModuleMap.module.css'

/** From here the map is two columns: "next up" and the skill profile beside the list
 * (ModuleMap.module.css). */
const TWO_COLUMNS = '(min-width: 72rem)'

/** A module with nothing to work through yet (no segments, so it can't be completed). It doesn't
 * lock the ones after it (#123), and it isn't shown as "open" for ever or offered by Continue:
 * it reads "coming soon" until it has content (#146). */
function notReady(module: ModuleSummary): boolean {
  return module.segmentCount === 0 && module.status === 'open'
}

/** Done: worked through, or tested out with the quick check (#214). */
function isDone(module: ModuleSummary): boolean {
  return module.status === 'complete' || module.status === 'tested_out'
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
    case 'tested_out':
      return { tone: 'success', label: 'tested out', icon: '»' }
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
  const allDone = modules.every((m) => isDone(m) || m.segmentCount === 0)
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

/** A single module row on the map. Only the mastery check is ever locked: shown but not
 * interactive. The recommended next module says so, and a module the student could test out of
 * offers its quick check under the card (FR-8.2, #214). */
function ModuleRow({ module, medal }: { module: ModuleSummary; medal?: MedalTier | null }) {
  const { tone, label, icon } = statusDisplay(module)
  const isLocked = module.status === 'locked'

  const cardContent = (
    <Card interactive={!isLocked} className={`${styles.row} ${isLocked ? styles.locked : ''}`}>
      <span className={styles.number} aria-hidden="true">
        {module.number}
      </span>
      <div className={styles.info}>
        <span className={styles.title}>{module.title}</span>
        {module.recommended && (
          <span>
            <Tag tone="accent" icon="→">
              recommended next
            </Tag>
          </span>
        )}
        {(module.lookAgainCount ?? 0) > 0 && (
          <span className={styles.lookAgain}>{module.lookAgainCount} marked to look at again</span>
        )}
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
        {medal && (module.status === 'complete' || module.status === 'tested_out') && (
          <Medal tier={medal} label={`Module ${module.number}: ${medalText(medal)}`} />
        )}
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
      {module.quickCheck === 'available' && !isDone(module) && (
        <Link to={`/modules/${module.id}/check`} className={styles.quickCheck}>
          Already know module {module.number}? Take the quick check
        </Link>
      )}
      {/* A taken quick check stays findable, passed or not (#215 review). */}
      {module.quickCheckScore && (
        <p className={styles.quickCheckScore}>
          Quick check: {module.quickCheckScore.correct} of {module.quickCheckScore.total},{' '}
          <Link
            to={`/modules/${module.id}/check`}
            aria-label={`Quick check: ${module.quickCheckScore.correct} of ${module.quickCheckScore.total}, see the results for module ${module.number}`}
          >
            see results
          </Link>
        </p>
      )}
    </li>
  )
}

/** Picks the first in-progress module, else the recommended one, else the first open one, to
 * continue from; never one with nothing in it yet (#146). */
function findContinueTarget(modules: ModuleSummary[]): ModuleSummary | undefined {
  const ready = modules.filter((m) => m.segmentCount > 0)
  return (
    ready.find((m) => m.status === 'in_progress') ??
    ready.find((m) => m.recommended === true) ??
    ready.find((m) => m.status === 'open')
  )
}

/**
 * The module map (FR-2.1, FR-2.6): all seven modules in order with their state and estimated
 * duration, the one recommended next, and a Continue button that picks up where the student left
 * off. The student may open any module but the mastery check (#214).
 *
 * Route: / (index)
 */
export function ModuleMap() {
  const query = useQuery({ queryKey: ['modules'], queryFn: fetchModules })
  const twoColumns = useMediaQuery(TWO_COLUMNS)
  const skills = useSkills()
  const rewards = useRewards()

  if (query.isPending) return <Spinner label="Loading modules" />
  if (query.isError) return <Alert tone="danger">{query.error.message}</Alert>

  const modules = query.data
  const continueTarget = findContinueTarget(modules)
  const minutes = minutesProgress(modules)
  // A finished module's medal (#214), unless points and badges are hidden (FR-9.5).
  const medals = new Map(
    rewards.data?.hideRewards === false
      ? (skills.data?.modules ?? []).map((m) => [m.moduleId, m.medal] as const)
      : [],
  )

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
        {twoColumns && <SkillProfileCard />}
      </div>

      <section aria-labelledby="all-modules" className={styles.all}>
        <h2 id="all-modules" className={styles.allHeading}>
          All modules
        </h2>
        <ul className={styles.list}>
          {modules.map((m) => (
            <ModuleRow key={m.id} module={m} medal={medals.get(m.id)} />
          ))}
        </ul>
      </section>
      {/* In one column the skill profile comes after the modules, so it doesn't push the list
          a screen or more down (about 1,500 px at 320 px, #215 review). */}
      {!twoColumns && <SkillProfileCard />}
    </div>
  )
}
