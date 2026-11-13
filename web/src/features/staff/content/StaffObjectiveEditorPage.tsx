import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { Alert, Spinner, TextField } from '../../../components'
import styles from '../staff.module.css'
import {
  getOverview,
  OVERVIEW_KEY,
  saveObjective,
  type ObjectiveIn,
  type ObjectiveOut,
} from './content.api.ts'
import { Provenance, SaveBar, SeedNote, TextArea } from './ContentFields.tsx'
import { usePageTitle } from '../../../pages/usePageTitle.ts'
import { useWarnBeforeLeaving } from './useWarnBeforeLeaving.ts'

const EMPTY: ObjectiveIn = {
  text: '',
  bloomLevel: '',
  criterion: '',
  passFraction: 0.8,
  maxWrong: null,
}

function toInput(o: ObjectiveOut): ObjectiveIn {
  return {
    text: o.text,
    bloomLevel: o.bloomLevel,
    criterion: o.criterion,
    passFraction: o.passFraction ?? null,
    maxWrong: o.maxWrong ?? null,
  }
}

/** /staff/content/objectives/:objectiveId (or new): an objective's wording and the rule that
 * decides it from the module 6 items. A changed rule applies to every student at once. */
export function StaffObjectiveEditorPage() {
  const param = useParams().objectiveId
  const id = param === 'new' ? undefined : Number(param)
  const [version, setVersion] = useState(0)
  const overview = useQuery({ queryKey: OVERVIEW_KEY, queryFn: getOverview })
  if (overview.isPending) return <Spinner label="Loading the objective" />
  if (overview.isError) return <Alert tone="danger">{overview.error.message}</Alert>
  const saved = overview.data.objectives.find((o) => o.id === id)
  if (id !== undefined && !saved) return <Alert tone="danger">There is no objective {id}.</Alert>
  return (
    <ObjectiveEditor
      key={`${id ?? 'new'}-${version}`}
      id={id}
      saved={saved}
      onRestored={() => void overview.refetch().then(() => setVersion((v) => v + 1))}
    />
  )
}

function ObjectiveEditor(props: {
  id: number | undefined
  saved: ObjectiveOut | undefined
  onRestored: () => void
}) {
  const { id, saved } = props
  const [draft, setDraft] = useState<ObjectiveIn>(saved ? toInput(saved) : EMPTY)
  const [dirty, setDirty] = useState(false)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const allowLeaving = useWarnBeforeLeaving(dirty)
  usePageTitle(id === undefined ? 'New objective' : `Objective ${id}`)
  const byFraction = (draft.passFraction ?? null) !== null

  function change(next: Partial<ObjectiveIn>) {
    setDraft((d) => ({ ...d, ...next }))
    setDirty(true)
  }
  const save = useMutation({
    mutationFn: () => saveObjective(id, draft),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ['staff', 'content'] })
      setDraft(toInput(result))
      setDirty(false)
      allowLeaving()
      if (id === undefined)
        void navigate(`/staff/content/objectives/${result.id}`, { replace: true })
    },
  })

  return (
    <>
      <div className={styles.titleRow}>
        <h1 className="text-3xl font-semibold">
          {id === undefined ? 'New objective' : `Objective ${id}`}
        </h1>
        <Link to="/staff/content">All content</Link>
      </div>
      <SeedNote />
      {saved && (
        <Provenance
          kind="objectives"
          id={id}
          edited={saved.edited}
          inRepository={saved.inRepository}
          onRestored={props.onRestored}
        />
      )}
      {id === undefined && (
        <p className={styles.muted}>
          A new objective also needs a mastery item in module 6 and a review path before module 6 is
          valid again, so add those right after creating it.
        </p>
      )}
      <section className={styles.section}>
        <TextArea
          label="Objective"
          hint="As in the ID document's Table 1."
          value={draft.text}
          rows={3}
          onChange={(text) => change({ text })}
        />
        <TextField
          label="Bloom level"
          value={draft.bloomLevel}
          maxLength={100}
          onChange={(e) => change({ bloomLevel: e.target.value })}
        />
        <TextArea
          label="Success criterion, in words"
          hint="What the mastery report shows the student."
          value={draft.criterion}
          rows={3}
          onChange={(criterion) => change({ criterion })}
        />
        <fieldset className={styles.section}>
          <legend className={styles.label}>Rule, over the parts of its module 6 items</legend>
          <label className={styles.row}>
            <input
              type="radio"
              name="rule"
              checked={byFraction}
              onChange={() => change({ passFraction: 0.8, maxWrong: null })}
            />
            <span>At least a fraction right</span>
          </label>
          <label className={styles.row}>
            <input
              type="radio"
              name="rule"
              checked={!byFraction}
              onChange={() => change({ passFraction: null, maxWrong: 1 })}
            />
            <span>At most a number wrong</span>
          </label>
          {byFraction ? (
            <TextField
              label="Fraction right (0.8 is 4 out of 5)"
              type="number"
              step={0.05}
              min={0.05}
              max={1}
              value={draft.passFraction ?? ''}
              onChange={(e) => change({ passFraction: Number(e.target.value) })}
            />
          ) : (
            <TextField
              label="Most wrong allowed"
              type="number"
              min={0}
              value={draft.maxWrong ?? ''}
              onChange={(e) => change({ maxWrong: Number(e.target.value) })}
            />
          )}
        </fieldset>
      </section>
      <SaveBar
        label={id === undefined ? 'Create objective' : 'Save objective'}
        pending={save.isPending}
        dirty={dirty}
        saved={save.isSuccess}
        error={save.error}
        onSave={() => save.mutate()}
      >
        {id !== undefined && (
          <Link to={`/staff/content/review-paths/${id}`}>Edit its review path</Link>
        )}
      </SaveBar>
    </>
  )
}
