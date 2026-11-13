import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { Alert, Button, Spinner, TextField } from '../../../components'
import styles from '../staff.module.css'
import { deleteGraph, getGraph, saveGraph, type GraphIn, type GraphOut } from './content.api.ts'
import { Provenance, SaveBar, SeedNote, TextArea } from './ContentFields.tsx'
import { usePageTitle } from '../../../pages/usePageTitle.ts'
import { useWarnBeforeLeaving } from './useWarnBeforeLeaving.ts'

/** The graph as the form holds it: vertices comma-separated, one edge per line ("A B"). */
type Draft = { name: string; directed: boolean; vertices: string; edges: string; start: string }

function toDraft(g: GraphIn): Draft {
  return {
    name: g.name,
    directed: g.directed ?? false,
    vertices: g.vertices.join(', '),
    edges: (g.edges ?? []).map((e) => `${e.source} ${e.target}`).join('\n'),
    start: g.startVertex,
  }
}

function fromDraft(d: Draft): GraphIn {
  return {
    name: d.name,
    directed: d.directed,
    vertices: d.vertices
      .split(',')
      .map((v) => v.trim())
      .filter(Boolean),
    edges: d.edges
      .split('\n')
      .map((line) => line.trim().split(/\s+/))
      .filter((parts) => parts.length === 2 && parts[0])
      .map(([source, target]) => ({ source, target })),
    startVertex: d.start.trim(),
  }
}

const EMPTY: Draft = {
  name: '',
  directed: false,
  vertices: 'A, B, C',
  edges: 'A B\nB C',
  start: 'A',
}

/** /staff/content/graphs/:graphId (or new): a graph scenario for the BFS visualiser. Saving
 * runs it through the BFS engine, so a graph the visualiser can't open is refused. */
export function StaffGraphEditorPage() {
  const param = useParams().graphId
  const id = param === 'new' ? undefined : Number(param)
  const [version, setVersion] = useState(0)
  const saved = useQuery({
    queryKey: ['staff', 'content', 'graph', id],
    queryFn: () => getGraph(id!),
    enabled: id !== undefined,
  })
  if (id !== undefined && saved.isPending) return <Spinner label="Loading the graph" />
  if (saved.isError) return <Alert tone="danger">{saved.error.message}</Alert>
  return (
    <GraphEditor
      key={`${id ?? 'new'}-${version}`}
      id={id}
      saved={saved.data}
      onRestored={() => void saved.refetch().then(() => setVersion((v) => v + 1))}
    />
  )
}

function GraphEditor(props: {
  id: number | undefined
  saved: GraphOut | undefined
  onRestored: () => void
}) {
  const { id, saved } = props
  const [draft, setDraft] = useState<Draft>(saved ? toDraft(saved) : EMPTY)
  const [dirty, setDirty] = useState(false)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const allowLeaving = useWarnBeforeLeaving(dirty)
  usePageTitle(id === undefined ? 'New graph' : (saved?.name ?? `Graph ${id}`))

  function change(next: Partial<Draft>) {
    setDraft((d) => ({ ...d, ...next }))
    setDirty(true)
  }
  const save = useMutation({
    mutationFn: () => saveGraph(id, fromDraft(draft)),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ['staff', 'content'] })
      setDraft(toDraft(result))
      setDirty(false)
      allowLeaving()
      if (id === undefined) void navigate(`/staff/content/graphs/${result.id}`, { replace: true })
    },
  })
  const remove = useMutation({
    mutationFn: () => deleteGraph(id!),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['staff', 'content'] })
      allowLeaving() // deleted: nothing left to save
      void navigate('/staff/content')
    },
  })

  return (
    <>
      <div className={styles.titleRow}>
        <h1 className="text-3xl font-semibold">{id === undefined ? 'New graph' : draft.name}</h1>
        <Link to="/staff/content">All content</Link>
      </div>
      <SeedNote />
      {saved && (
        <Provenance
          kind="graphs"
          id={id}
          edited={saved.edited}
          inRepository={saved.inRepository}
          onRestored={props.onRestored}
        />
      )}
      <section className={styles.section}>
        <TextField
          label="Name"
          value={draft.name}
          maxLength={200}
          onChange={(e) => change({ name: e.target.value })}
        />
        <label className={styles.row}>
          <input
            type="checkbox"
            checked={draft.directed}
            onChange={(e) => change({ directed: e.target.checked })}
          />
          <span>Directed (each edge goes one way only)</span>
        </label>
        <TextField
          label="Vertices, separated by commas"
          hint="Up to 50. BFS visits neighbours in alphabetical order."
          value={draft.vertices}
          onChange={(e) => change({ vertices: e.target.value })}
        />
        <TextArea
          label="Edges, one per line: two vertices separated by a space"
          monospace
          rows={8}
          value={draft.edges}
          onChange={(edges) => change({ edges })}
        />
        <TextField
          label="Start vertex"
          value={draft.start}
          onChange={(e) => change({ start: e.target.value })}
        />
      </section>
      <SaveBar
        label={id === undefined ? 'Create graph' : 'Save graph'}
        pending={save.isPending}
        dirty={dirty}
        saved={save.isSuccess}
        error={save.error}
        onSave={() => save.mutate()}
      >
        {saved && !saved.inRepository && (
          <Button
            variant="secondary"
            loading={remove.isPending}
            onClick={() => window.confirm('Delete this graph?') && remove.mutate()}
          >
            Delete graph
          </Button>
        )}
      </SaveBar>
      {remove.isError && <Alert tone="danger">{remove.error.message}</Alert>}
    </>
  )
}
