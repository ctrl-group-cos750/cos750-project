import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { Alert, Button, Spinner, TextField } from '../../../components'
import styles from '../staff.module.css'
import {
  ACTIVITY_KINDS,
  deleteActivity,
  getActivity,
  getOverview,
  OVERVIEW_KEY,
  PURPOSES,
  saveActivity,
  type ActivityIn,
  type ActivityKind,
  type ActivityOut,
  type ContentOverview,
} from './content.api.ts'
import { Provenance, SaveBar, SeedNote, Select, TextArea } from './ContentFields.tsx'
import { useWarnBeforeLeaving } from './useWarnBeforeLeaving.ts'

const LEVELS = [1, 2, 3, 4] as const
const HINT_HELP: Record<number, string> = {
  1: 'A nudge',
  2: 'Points at the idea',
  3: 'Gives a lot away (counts as support)',
  4: 'The worked answer (counts as support)',
}

/** A starting point for each kind: the smallest config and solution the checks accept. */
const TEMPLATES: Record<ActivityKind, { config: object; solution: object; help: string }> = {
  multiple_choice: {
    config: {
      prompt: 'The question',
      options: [
        { id: 'a', label: 'First option' },
        { id: 'b', label: 'Second option' },
      ],
    },
    solution: { correct: 'a', feedback: { b: 'Why b is wrong' } },
    help: 'solution.correct is an option id; feedback says why each wrong option is wrong.',
  },
  matching: {
    config: {
      prompt: 'Match each term to its meaning.',
      left: [{ id: 'l1', label: 'Term' }],
      right: [{ id: 'r1', label: 'Meaning' }],
    },
    solution: { pairs: { l1: 'r1' }, feedback: {} },
    help: 'solution.pairs maps each left id to its right id; feedback is keyed by left id.',
  },
  parsons: {
    config: {
      lines: [
        { id: 1, text: 'def bfs(graph, start):' },
        { id: 2, text: '    return [start]' },
      ],
    },
    solution: { order: [1, 2] },
    help: 'solution.order lists line ids in the correct order. A line not listed is a distractor. Indent with spaces inside the text.',
  },
  fill_in: {
    config: { code: 'vertex = queue.__1__()', blanks: [1], options: ['popleft', 'pop'] },
    solution: { answers: { '1': 'popleft' } },
    help: 'Write each blank as __1__, __2__ in the code; options are the tokens a student picks from.',
  },
  trace: {
    config: {
      directed: false,
      vertices: ['A', 'B', 'C'],
      edges: [
        { source: 'A', target: 'B' },
        { source: 'B', target: 'C' },
      ],
      start_vertex: 'A',
    },
    solution: {},
    help: 'The BFS engine works out the answer from the graph, so the solution stays {}.',
  },
  fix_the_bug: {
    config: {
      prompt: 'Replace the faulty line.',
      lines: [{ id: 1, text: '        vertex = queue.pop()' }],
      corrections: [{ id: 2, text: '        vertex = queue.popleft()' }],
    },
    solution: { order: [2], feedback: { '1': 'pop() takes the newest vertex.' } },
    help: 'Lines and corrections share one id space; solution.order is the fixed program; feedback is keyed by faulty line id.',
  },
  choose_tests: {
    config: {
      prompt: 'Choose every test case this BFS fails.',
      code: 'def bfs(graph, start):\n    ...',
      tests: [
        {
          id: 'path',
          vertices: ['A', 'B'],
          edges: [{ source: 'A', target: 'B' }],
          start_vertex: 'A',
          expected: ['A', 'B'],
        },
        { id: 'single', vertices: ['A'], edges: [], start_vertex: 'A', expected: ['A'] },
      ],
    },
    solution: { exposing: ['path'], feedback: {} },
    help: 'Each test needs the order correct BFS gives (checked by the engine); solution.exposing lists the tests the faulty code fails.',
  },
}

type Draft = Omit<ActivityIn, 'config' | 'solution'> & { config: string; solution: string }

/** Only the fields the API takes back: it refuses unknown ones, such as `inUse`. */
function toDraft(a: ActivityIn): Draft {
  return {
    kind: a.kind,
    title: a.title,
    visible: a.visible ?? true,
    moduleId: a.moduleId ?? null,
    objectiveId: a.objectiveId ?? null,
    purpose: a.purpose ?? 'practice',
    hints: (a.hints ?? []).map(({ level, body }) => ({ level, body })),
    config: JSON.stringify(a.config, null, 2),
    solution: JSON.stringify(a.solution, null, 2),
  }
}

function fresh(kind: ActivityKind): Draft {
  const t = TEMPLATES[kind]
  return toDraft({
    kind,
    title: '',
    visible: true,
    moduleId: null,
    objectiveId: null,
    purpose: 'practice',
    config: t.config as ActivityIn['config'],
    solution: t.solution as ActivityIn['solution'],
    hints: [],
  })
}

function parse(label: string, text: string): Record<string, unknown> {
  let value: unknown
  try {
    value = JSON.parse(text)
  } catch (e) {
    throw new Error(`${label} is not valid JSON: ${(e as Error).message}`, { cause: e })
  }
  if (typeof value !== 'object' || value === null || Array.isArray(value))
    throw new Error(`${label} must be a JSON object, in { }.`)
  return value as Record<string, unknown>
}

/** /staff/content/activities/:activityId (or new): one activity, its answer and its hints. */
export function StaffActivityEditorPage() {
  const param = useParams().activityId
  const id = param === 'new' ? undefined : Number(param)
  const [version, setVersion] = useState(0)
  const overview = useQuery({ queryKey: OVERVIEW_KEY, queryFn: getOverview })
  const saved = useQuery({
    queryKey: ['staff', 'content', 'activity', id],
    queryFn: () => getActivity(id!),
    enabled: id !== undefined,
  })
  if (overview.isPending || (id !== undefined && saved.isPending))
    return <Spinner label="Loading the activity" />
  if (overview.isError) return <Alert tone="danger">{overview.error.message}</Alert>
  if (saved.isError) return <Alert tone="danger">{saved.error.message}</Alert>
  return (
    <ActivityEditor
      key={`${id ?? 'new'}-${version}`}
      id={id}
      saved={saved.data}
      overview={overview.data}
      onRestored={() => void saved.refetch().then(() => setVersion((v) => v + 1))}
    />
  )
}

function ActivityEditor(props: {
  id: number | undefined
  saved: ActivityOut | undefined
  overview: ContentOverview
  onRestored: () => void
}) {
  const { id, saved, overview } = props
  const [draft, setDraft] = useState<Draft>(saved ? toDraft(saved) : fresh('multiple_choice'))
  const [dirty, setDirty] = useState(false)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  useWarnBeforeLeaving(dirty)

  function change(next: Partial<Draft>) {
    setDraft((d) => ({ ...d, ...next }))
    setDirty(true)
  }
  function setHint(level: number, body: string) {
    const others = (draft.hints ?? []).filter((h) => h.level !== level)
    const hints = body.trim() ? [...others, { level, body }] : others
    change({ hints: hints.sort((a, b) => a.level - b.level) })
  }

  const save = useMutation({
    mutationFn: () =>
      saveActivity(id, {
        ...draft,
        config: parse('The config', draft.config),
        solution: parse('The solution', draft.solution),
      } as ActivityIn),
    onSuccess: (result) => {
      void queryClient.invalidateQueries({ queryKey: ['staff', 'content'] })
      setDraft(toDraft(result))
      setDirty(false)
      if (id === undefined)
        void navigate(`/staff/content/activities/${result.id}`, { replace: true })
    },
  })
  const remove = useMutation({
    mutationFn: () => deleteActivity(id!),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['staff', 'content'] })
      void navigate('/staff/content')
    },
  })

  const moduleOptions = overview.modules.map((m) => ({
    value: m.id,
    label: `${m.id}. ${m.title}`,
  }))
  const objectiveOptions = overview.objectives.map((o) => ({
    value: o.id,
    label: `${o.id}. ${o.text.slice(0, 70)}`,
  }))

  return (
    <>
      <div className={styles.titleRow}>
        <h1 className="text-3xl font-semibold">
          {id === undefined ? 'New activity' : `Activity #${id}`}
        </h1>
        <Link to="/staff/content">All content</Link>
      </div>
      <SeedNote />
      {saved && (
        <>
          <Provenance
            kind="activities"
            id={id}
            edited={saved.edited}
            inRepository={saved.inRepository}
            onRestored={props.onRestored}
          />
          <p className={styles.muted}>
            {saved.shownIn.length
              ? `Shown in ${saved.shownIn.join('; ')}.`
              : 'No segment shows it yet: add it to a module or review path.'}
            {saved.inUse &&
              ' Students have answered it: their earlier results stay as they were graded.'}
          </p>
        </>
      )}

      <section className={styles.section} aria-labelledby="activity-details">
        <h2 id="activity-details" className="text-xl font-semibold">
          Details
        </h2>
        <div className={styles.twoColumns}>
          <TextField
            label="Title"
            value={draft.title}
            maxLength={200}
            onChange={(e) => change({ title: e.target.value })}
          />
          <Select
            label="Kind"
            hint={id === undefined ? 'Changing it starts from that kind’s template.' : undefined}
            value={draft.kind}
            options={ACTIVITY_KINDS}
            onChange={(kind) => {
              if (!kind || kind === draft.kind) return
              const t = TEMPLATES[kind]
              change({
                kind,
                config: JSON.stringify(t.config, null, 2),
                solution: JSON.stringify(t.solution, null, 2),
              })
            }}
          />
          <Select
            label="Purpose"
            value={draft.purpose ?? 'practice'}
            options={PURPOSES}
            onChange={(purpose) => purpose && change({ purpose })}
          />
          <Select
            label="Module"
            value={draft.moduleId ?? null}
            options={moduleOptions}
            none="None (review path, or not placed yet)"
            onChange={(moduleId) => change({ moduleId })}
          />
          <Select
            label="Objective it is evidence for"
            value={draft.objectiveId ?? null}
            options={objectiveOptions}
            none="None"
            onChange={(objectiveId) => change({ objectiveId })}
          />
          <label className={styles.row}>
            <input
              type="checkbox"
              checked={draft.visible ?? true}
              onChange={(e) => change({ visible: e.target.checked })}
            />
            <span>Show why an answer is wrong (off: only general messages)</span>
          </label>
        </div>
      </section>

      <section className={styles.section} aria-labelledby="activity-answer">
        <h2 id="activity-answer" className="text-xl font-semibold">
          Question and answer
        </h2>
        <p className={styles.muted}>{TEMPLATES[draft.kind].help}</p>
        <div className={styles.twoColumns}>
          <TextArea
            label="Config (what the student sees), JSON"
            monospace
            rows={18}
            value={draft.config}
            onChange={(config) => change({ config })}
          />
          <TextArea
            label="Solution (never sent to students), JSON"
            monospace
            rows={18}
            value={draft.solution}
            onChange={(solution) => change({ solution })}
          />
        </div>
      </section>

      <fieldset className={styles.section}>
        <legend className="text-xl font-semibold">Hints, one level at a time</legend>
        <p className={styles.muted}>
          Leave a level blank to skip it. Practice on a review path needs all four.
        </p>
        {LEVELS.map((level) => (
          <TextArea
            key={level}
            label={`Level ${level}: ${HINT_HELP[level]}`}
            rows={2}
            value={draft.hints?.find((h) => h.level === level)?.body ?? ''}
            onChange={(body) => setHint(level, body)}
          />
        ))}
      </fieldset>

      <SaveBar
        label={id === undefined ? 'Create activity' : 'Save activity'}
        pending={save.isPending}
        dirty={dirty}
        saved={save.isSuccess}
        error={save.error}
        onSave={() => save.mutate()}
      >
        {id !== undefined && <Link to={`/activities/${id}`}>Open as a student</Link>}
        {saved && saved.shownIn.length === 0 && (
          <Button
            variant="secondary"
            loading={remove.isPending}
            onClick={() =>
              window.confirm(
                saved.inUse || saved.inRepository
                  ? 'Take this activity out of use? It is kept (hidden) because students answered it or the repository has it.'
                  : 'Delete this activity?',
              ) && remove.mutate()
            }
          >
            {saved.inUse || saved.inRepository ? 'Take out of use' : 'Delete activity'}
          </Button>
        )}
      </SaveBar>
      {remove.isError && <Alert tone="danger">{remove.error.message}</Alert>}
    </>
  )
}
