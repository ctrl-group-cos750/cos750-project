import { readdirSync, readFileSync } from 'node:fs'

/**
 * The course content as the API seeds it, read from the fixtures at test time
 * (api/app/seed/*.json), so the tests answer whatever questions the checkout holds. Nothing here
 * names a question's text or its right answer: content PRs change those, and the tests must
 * still pass. A test finds an activity by its kind, purpose or objective, and builds its answer
 * from the activity's stored solution, the way the seed's demo accounts do
 * (api/app/seed/demo_accounts.py, `answer_for`).
 */

const SEED_DIR = new URL('../../api/app/seed/', import.meta.url) // from e2e/tests/

export type Line = { id: number; text: string }
export type Edge = { source: string; target: string }
export type Graph = {
  directed?: boolean
  vertices: string[]
  edges?: Edge[]
  start_vertex: string
}
export type TestCase = Graph & { id: string; expected: string[] }

/** One step of an accepted line order: a line, or a group of lines that may come in any order. */
type OrderStep = number | number[]

type Base = {
  id: number
  title: string
  module_id?: number
  purpose: 'diagnostic' | 'practice' | 'retrieval' | 'mastery' | 'review'
  objective_id?: number | null
}

/** An activity with its server-only solution, exactly as the fixture holds it. */
export type Activity = Base &
  (
    | {
        kind: 'multiple_choice'
        config: { prompt: string; options: { id: string; label: string }[] }
        solution: { correct: string }
      }
    | {
        kind: 'matching'
        config: {
          prompt: string
          left: { id: string; label: string }[]
          right: { id: string; label: string }[]
        }
        solution: { pairs: Record<string, string> }
      }
    | {
        kind: 'fill_in'
        config: { code: string; blanks: number[]; options: string[] }
        solution: { answers: Record<string, string> }
      }
    | { kind: 'parsons'; config: { lines: Line[] }; solution: { order: OrderStep[] } }
    | {
        kind: 'fix_the_bug'
        config: { prompt: string; lines: Line[]; corrections: Line[] }
        solution: { order: OrderStep[] }
      }
    | {
        kind: 'choose_tests'
        config: { prompt: string; code: string; tests: TestCase[] }
        solution: { exposing: string[] }
      }
    | { kind: 'trace'; config: Graph & { directed: boolean; edges: Edge[] }; solution: object }
  )

export type Kind = Activity['kind']
export type ActivityOf<K extends Kind> = Extract<Activity, { kind: K }>

type ReviewPath = {
  objective_id: number
  segments: { id: number; kind: string; title: string; activity_id?: number }[]
}

function readJson<T>(name: string): T {
  return JSON.parse(readFileSync(new URL(name, SEED_DIR), 'utf8')) as T
}

const files = readdirSync(SEED_DIR).filter((name) => /^(module-\d+|review)\.json$/.test(name))

/** Every activity in the fixtures, by id. */
export const activities = new Map<number, Activity>(
  files.flatMap((name) =>
    readJson<{ activities: Activity[] }>(name).activities.map((a) => [a.id, a] as const),
  ),
)

/** The review path of each objective (FR-7.5), by objective id. */
export const reviewPaths = new Map<number, ReviewPath>(
  readJson<{ review_paths: ReviewPath[] }>('review.json').review_paths.map((p) => [
    p.objective_id,
    p,
  ]),
)

/** The seeded demo accounts (FR-1.4): their email's local part, display name and expected stage. */
export const demoAccounts = readJson<{
  accounts: { key: string; display_name: string; expect: { ready: boolean; not_yet?: number[] } }[]
}>('demo/accounts.json').accounts

export const objectives = readJson<{ objectives: { id: number; text: string }[] }>(
  'objectives.json',
).objectives

export function activity(id: number): Activity {
  const found = activities.get(id)
  if (!found) throw new Error(`activity ${id} is not in api/app/seed/*.json`)
  return found
}

/** The module each module segment's activity is shown in, by activity id (not the recall
 * questions or the review paths' activities). */
const segmentModule = new Map<number, number>(
  files
    .filter((name) => name.startsWith('module-'))
    .flatMap((name) =>
      readJson<{ modules: { id: number; segments: { activity_id?: number }[] }[] }>(
        name,
      ).modules.flatMap((m) =>
        m.segments.flatMap((s) => (s.activity_id === undefined ? [] : [[s.activity_id, m.id]])),
      ),
    ) as [number, number][],
)

/** The module (its id) a module segment's activity is shown in. */
export function moduleOf(a: Activity): number | undefined {
  return segmentModule.get(a.id)
}

/** The activity of a kind a student meets first: in a module segment, in the earliest module,
 * practice before mastery, then by id. */
export function firstOfKind<K extends Kind>(kind: K): ActivityOf<K> {
  const rank = (a: Activity) => (a.purpose === 'mastery' ? 1 : 0)
  const found = [...activities.values()]
    .filter((a) => a.kind === kind && moduleOf(a) !== undefined)
    .sort((a, b) => (moduleOf(a) ?? 0) - (moduleOf(b) ?? 0) || rank(a) - rank(b) || a.id - b.id)[0]
  if (!found) throw new Error(`no ${kind} activity in a module in the fixtures`)
  return found as ActivityOf<K>
}

/** One accepted order of an ordered solution: each group's lines in the order written (the
 * seed's `first_order`). */
export function firstOrder(order: OrderStep[]): number[] {
  return order.flatMap((step) => (typeof step === 'number' ? [step] : step))
}

export type TraceStep = {
  visitedVertex: string
  queue: string[]
  visited: string[]
  order: string[]
}

/** BFS as the API's engine runs it (api/app/services/bfs.py): neighbours in alphabetical order,
 * a vertex queued once, when it is found, and visited when it leaves the queue. One step per
 * vertex that leaves the queue: the trace table's rows. */
export function bfsSteps(graph: Graph): TraceStep[] {
  const neighbours = new Map(graph.vertices.map((v) => [v, new Set<string>()]))
  for (const { source, target } of graph.edges ?? []) {
    neighbours.get(source)?.add(target)
    if (!graph.directed) neighbours.get(target)?.add(source)
  }
  const queue = [graph.start_vertex]
  const found = new Set(queue)
  const order: string[] = []
  const steps: TraceStep[] = []
  while (queue.length > 0) {
    const current = queue.shift() as string
    order.push(current)
    for (const next of [...(neighbours.get(current) ?? [])].sort()) {
      if (!found.has(next)) {
        found.add(next)
        queue.push(next)
      }
    }
    steps.push({
      visitedVertex: current,
      queue: [...queue],
      visited: [...order],
      order: [...order],
    })
  }
  return steps
}

/** A submission the API's checker marks right, built from the stored solution (the body of
 * POST /api/activities/:id/attempts is `{ submitted: this }`). */
export function rightSubmission(a: Activity): Record<string, unknown> {
  switch (a.kind) {
    case 'multiple_choice':
      return { selected: a.solution.correct }
    case 'matching':
      return { pairs: a.solution.pairs }
    case 'fill_in':
      return { answers: a.solution.answers }
    case 'parsons':
    case 'fix_the_bug':
      return { order: firstOrder(a.solution.order) }
    case 'choose_tests':
      return { selected: a.solution.exposing }
    case 'trace':
      return { rows: bfsSteps(a.config) }
  }
}

/** An option of a multiple-choice question that is not its answer. */
export function wrongOption(a: ActivityOf<'multiple_choice'>): string {
  const option = a.config.options.find((o) => o.id !== a.solution.correct)
  if (!option) throw new Error(`activity ${a.id} has no wrong option`)
  return option.id
}
