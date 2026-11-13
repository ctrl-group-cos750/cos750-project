import { useMutation, useQuery } from '@tanstack/react-query'
import { Download, Plus } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router'
import { buttonVariants } from '@/components/ui/button-variants'
import { Alert, Button, Card, Spinner, Tag } from '../../../components'
import styles from '../staff.module.css'
import { downloadFixtures, getOverview, OVERVIEW_KEY, type ContentOverview } from './content.api.ts'

function EditedTag({ edited, inRepository }: { edited: boolean; inRepository: boolean }) {
  if (!inRepository) return <Tag tone="accent">Made in the portal</Tag>
  return edited ? <Tag tone="warning">Edited in the portal</Tag> : null
}

/**
 * /staff/content — every piece of course content: modules and their segments, objectives and
 * their review paths, activities and graphs. Each links to its editor. "Download as fixtures"
 * gives the repository's fixture files for what the database holds now.
 */
export function StaffContentPage() {
  const overview = useQuery({ queryKey: OVERVIEW_KEY, queryFn: getOverview })
  const exporting = useMutation({ mutationFn: downloadFixtures })
  return (
    <section
      className="grid grid-cols-[minmax(0,1fr)] gap-6"
      aria-labelledby="staff-content-heading"
    >
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h1 id="staff-content-heading" className="text-3xl font-semibold">
          Content
        </h1>
        <Button
          variant="secondary"
          loading={exporting.isPending}
          onClick={() => exporting.mutate()}
        >
          <Download aria-hidden />
          Download as fixtures
        </Button>
      </div>
      <p className={styles.muted}>
        The repository&apos;s fixtures fill an empty database; from then on this is the content
        students see. Anything you save here is kept on the next deploy. To bring your changes into
        the repository, download them as fixtures, unzip them into <code>api/app/seed/</code> and
        open a pull request.
      </p>
      {exporting.isError && <Alert tone="danger">{exporting.error.message}</Alert>}
      {overview.isPending && <Spinner label="Loading the content" />}
      {overview.isError && <Alert tone="danger">{overview.error.message}</Alert>}
      {overview.data && <Lists data={overview.data} />}
    </section>
  )
}

function Lists({ data }: { data: ContentOverview }) {
  const [moduleFilter, setModuleFilter] = useState<string>('all')
  const activities = data.activities.filter((a) =>
    moduleFilter === 'all'
      ? true
      : moduleFilter === 'none'
        ? (a.moduleId ?? null) === null
        : a.moduleId === Number(moduleFilter),
  )
  const newButton = buttonVariants({ variant: 'outline' })
  return (
    <>
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-xl font-semibold">Modules</h2>
          <Link className={newButton} to="/staff/content/modules/new">
            <Plus aria-hidden />
            New module
          </Link>
        </div>
        <ul className={styles.list}>
          {data.modules.map((m) => (
            <li key={m.id} className={styles.row}>
              <Link to={`/staff/content/modules/${m.id}`} className="text-primary">
                {m.id}. {m.title}
              </Link>
              <span className={styles.muted}>
                {m.segmentCount} segment{m.segmentCount === 1 ? '' : 's'}
              </span>
              <EditedTag edited={m.edited || m.segmentsEdited} inRepository={m.inRepository} />
            </li>
          ))}
        </ul>
      </Card>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-xl font-semibold">Objectives and review paths</h2>
          {data.objectives.length < 8 && (
            <Link className={newButton} to="/staff/content/objectives/new">
              <Plus aria-hidden />
              New objective
            </Link>
          )}
        </div>
        <ul className={styles.list}>
          {data.objectives.map((o) => {
            const path = data.reviewPaths.find((r) => r.objectiveId === o.id)
            return (
              <li key={o.id} className="grid gap-1">
                <div className={styles.row}>
                  <Link to={`/staff/content/objectives/${o.id}`} className="text-primary">
                    Objective {o.id}
                  </Link>
                  <EditedTag edited={o.edited} inRepository={o.inRepository} />
                  <span aria-hidden>·</span>
                  <Link to={`/staff/content/review-paths/${o.id}`} className="text-primary">
                    Review path ({path?.segmentCount ?? 0} segments)
                  </Link>
                  {path && <EditedTag edited={path.edited} inRepository={path.inRepository} />}
                </div>
                <span className={styles.muted}>{o.text}</span>
              </li>
            )
          })}
        </ul>
      </Card>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-xl font-semibold">Activities</h2>
          <div className={`${styles.row} min-w-0 max-w-full`}>
            <label className={styles.label} htmlFor="activity-filter">
              Show
            </label>
            <select
              id="activity-filter"
              className={styles.input}
              style={{ width: 'auto', minWidth: 0, maxWidth: '100%' }}
              value={moduleFilter}
              onChange={(e) => setModuleFilter(e.target.value)}
            >
              <option value="all">All</option>
              {data.modules.map((m) => (
                <option key={m.id} value={String(m.id)}>
                  Module {m.id}
                </option>
              ))}
              <option value="none">Review paths and unplaced</option>
            </select>
            <Link className={newButton} to="/staff/content/activities/new">
              <Plus aria-hidden />
              New activity
            </Link>
          </div>
        </div>
        <p className={styles.muted}>
          Video checkpoint questions are edited with their video, on the Videos page.
        </p>
        <ul className={styles.list}>
          {activities.map((a) => (
            <li key={a.id} className={styles.row}>
              <Link to={`/staff/content/activities/${a.id}`} className="text-primary">
                {a.title}
              </Link>
              <span className={styles.muted}>
                #{a.id} · {a.kind.replace(/_/g, ' ')} · {a.purpose}
                {(a.objectiveId ?? null) !== null && ` · objective ${a.objectiveId}`}
              </span>
              <EditedTag edited={a.edited} inRepository={a.inRepository} />
            </li>
          ))}
        </ul>
      </Card>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-xl font-semibold">Graphs (BFS visualiser)</h2>
          <Link className={newButton} to="/staff/content/graphs/new">
            <Plus aria-hidden />
            New graph
          </Link>
        </div>
        <ul className={styles.list}>
          {data.graphs.map((g) => (
            <li key={g.id} className={styles.row}>
              <Link to={`/staff/content/graphs/${g.id}`} className="text-primary">
                {g.name}
              </Link>
              <span className={styles.muted}>#{g.id}</span>
              <EditedTag edited={g.edited} inRepository={g.inRepository} />
            </li>
          ))}
        </ul>
      </Card>
    </>
  )
}
