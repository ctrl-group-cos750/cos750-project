import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { Alert, Button, Spinner, TextField } from '../../../components'
import styles from '../staff.module.css'
import {
  deleteModule,
  getModule,
  getOverview,
  OVERVIEW_KEY,
  getReviewPath,
  saveModule,
  saveReviewPath,
  type ContentOverview,
  type ModuleIn,
  type ModuleOut,
  type ReviewPathOut,
  type SegmentIn,
} from './content.api.ts'
import { Provenance, SaveBar, SeedNote, TextArea } from './ContentFields.tsx'
import { useWarnBeforeLeaving } from './useWarnBeforeLeaving.ts'
import { SegmentsEditor } from './SegmentsEditor.tsx'

const EMPTY: ModuleIn = { slug: '', title: '', goals: [], estimatedMinutes: 10, segments: [] }

function toInput(m: ModuleOut): ModuleIn {
  return {
    slug: m.slug,
    title: m.title,
    goals: m.goals,
    estimatedMinutes: m.estimatedMinutes,
    segments: m.segments,
  }
}

/** /staff/content/modules/:moduleId (or new): a module's details and its segments. */
export function StaffModuleEditorPage() {
  const param = useParams().moduleId
  const id = param === 'new' ? undefined : Number(param)
  // Bumped after "Use the repository's version", to remount the form with what was loaded.
  const [version, setVersion] = useState(0)
  const overview = useQuery({ queryKey: OVERVIEW_KEY, queryFn: getOverview })
  const saved = useQuery({
    queryKey: ['staff', 'content', 'module', id],
    queryFn: () => getModule(id!),
    enabled: id !== undefined,
  })
  if (overview.isPending || (id !== undefined && saved.isPending))
    return <Spinner label="Loading the module" />
  if (overview.isError) return <Alert tone="danger">{overview.error.message}</Alert>
  if (saved.isError) return <Alert tone="danger">{saved.error.message}</Alert>
  return (
    <ModuleEditor
      key={`${id ?? 'new'}-${version}`}
      id={id}
      saved={saved.data}
      overview={overview.data}
      onRestored={() => void saved.refetch().then(() => setVersion((v) => v + 1))}
    />
  )
}

function ModuleEditor(props: {
  id: number | undefined
  saved: ModuleOut | undefined
  overview: ContentOverview
  onRestored: () => void
}) {
  const { id, saved } = props
  const [draft, setDraft] = useState<ModuleIn>(saved ? toInput(saved) : EMPTY)
  const [dirty, setDirty] = useState(false)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  useWarnBeforeLeaving(dirty)

  function change(next: Partial<ModuleIn>) {
    setDraft((d) => ({ ...d, ...next }))
    setDirty(true)
  }

  const save = useMutation({
    mutationFn: () => saveModule(id, { ...draft, goals: draft.goals.filter((g) => g.trim()) }),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ['staff', 'content'] })
      setDraft(toInput(result))
      setDirty(false)
      if (id === undefined) void navigate(`/staff/content/modules/${result.id}`, { replace: true })
    },
  })
  const remove = useMutation({
    mutationFn: () => deleteModule(id!),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['staff', 'content'] })
      void navigate('/staff/content')
    },
  })

  return (
    <>
      <div className={styles.titleRow}>
        <h1 className="text-3xl font-semibold">
          {id === undefined ? 'New module' : `Module ${id}`}
        </h1>
        <Link to="/staff/content">All content</Link>
      </div>
      <SeedNote />
      {saved && (
        <Provenance
          kind="modules"
          id={id}
          edited={saved.edited || saved.segmentsEdited}
          inRepository={saved.inRepository}
          onRestored={props.onRestored}
        />
      )}

      <section className={styles.section} aria-labelledby="module-details">
        <h2 id="module-details" className="text-xl font-semibold">
          Details
        </h2>
        <div className={styles.twoColumns}>
          <TextField
            label="Title"
            value={draft.title}
            maxLength={200}
            onChange={(e) => change({ title: e.target.value })}
          />
          <TextField
            label="Slug"
            hint="Lowercase words joined by dashes, e.g. meet-bfs."
            value={draft.slug}
            onChange={(e) => change({ slug: e.target.value })}
          />
          <TextField
            label="Estimated minutes"
            type="number"
            min={1}
            max={120}
            value={draft.estimatedMinutes}
            onChange={(e) => change({ estimatedMinutes: Number(e.target.value) })}
          />
        </div>
        <TextArea
          label="Goals, one per line"
          hint='Each finishes "By the end of this module you can ...".'
          value={draft.goals.join('\n')}
          onChange={(text) => change({ goals: text.split('\n') })}
        />
      </section>

      <section className={styles.section} aria-labelledby="module-segments">
        <h2 id="module-segments" className="text-xl font-semibold">
          Segments
        </h2>
        <SegmentsEditor
          segments={draft.segments ?? []}
          overview={props.overview}
          moduleId={id}
          allowRefreshers={id === 0}
          allowSkipping
          onChange={(segments) => change({ segments })}
        />
      </section>

      <SaveBar
        label={id === undefined ? 'Create module' : 'Save module'}
        pending={save.isPending}
        dirty={dirty}
        saved={save.isSuccess}
        error={save.error}
        onSave={() => save.mutate()}
      >
        {id !== undefined && <Link to={`/modules/${id}`}>Open as a student</Link>}
        {saved && !saved.inRepository && (
          <Button
            variant="secondary"
            loading={remove.isPending}
            onClick={() => window.confirm('Delete this module?') && remove.mutate()}
          >
            Delete module
          </Button>
        )}
      </SaveBar>
      {remove.isError && <Alert tone="danger">{remove.error.message}</Alert>}
    </>
  )
}

/** /staff/content/review-paths/:objectiveId: the path a student marked "not yet" on that
 * objective works through (a worked example, practice, then fresh mastery items). */
export function StaffReviewPathEditorPage() {
  const objectiveId = Number(useParams().objectiveId)
  const [version, setVersion] = useState(0)
  const overview = useQuery({ queryKey: OVERVIEW_KEY, queryFn: getOverview })
  const saved = useQuery({
    queryKey: ['staff', 'content', 'review-path', objectiveId],
    queryFn: () => getReviewPath(objectiveId),
  })
  if (overview.isPending || saved.isPending) return <Spinner label="Loading the review path" />
  if (overview.isError) return <Alert tone="danger">{overview.error.message}</Alert>
  if (saved.isError) return <Alert tone="danger">{saved.error.message}</Alert>
  return (
    <ReviewPathEditor
      key={`${objectiveId}-${version}`}
      saved={saved.data}
      overview={overview.data}
      onRestored={() => void saved.refetch().then(() => setVersion((v) => v + 1))}
    />
  )
}

function ReviewPathEditor(props: {
  saved: ReviewPathOut
  overview: ContentOverview
  onRestored: () => void
}) {
  const { saved } = props
  const [segments, setSegments] = useState<SegmentIn[]>(saved.segments)
  const [dirty, setDirty] = useState(false)
  const queryClient = useQueryClient()
  useWarnBeforeLeaving(dirty)
  const objective = props.overview.objectives.find((o) => o.id === saved.objectiveId)
  const save = useMutation({
    mutationFn: () => saveReviewPath(saved.objectiveId, segments),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ['staff', 'content'] })
      setSegments(result.segments)
      setDirty(false)
    },
  })
  return (
    <>
      <div className={styles.titleRow}>
        <h1 className="text-3xl font-semibold">Review path, objective {saved.objectiveId}</h1>
        <Link to="/staff/content">All content</Link>
      </div>
      {objective && <p>{objective.text}</p>}
      <SeedNote />
      <p className={styles.muted}>
        It starts by teaching the objective again (a worked example or text), then practice
        activities with all four hints, then fresh mastery items for this objective.
      </p>
      <Provenance
        kind="review-paths"
        id={saved.objectiveId}
        edited={saved.edited}
        inRepository={saved.inRepository}
        onRestored={props.onRestored}
      />
      <SegmentsEditor
        segments={segments}
        overview={props.overview}
        allowRefreshers={false}
        allowSkipping={false}
        onChange={(next) => {
          setSegments(next)
          setDirty(true)
        }}
      />
      <SaveBar
        label="Save review path"
        pending={save.isPending}
        dirty={dirty}
        saved={save.isSuccess}
        error={save.error}
        onSave={() => save.mutate()}
      >
        <Link to={`/review/${saved.objectiveId}`}>Open as a student</Link>
      </SaveBar>
    </>
  )
}
