import { useId, useState } from 'react'
import { Button } from '../../components'
import { CodeListing } from './CodeListing.tsx'
import type { AttemptResult, ChooseTestsActivity, TestCase } from './activities.types.ts'

type ChooseTestsProps = {
  activity: ChooseTestsActivity
  result: AttemptResult | undefined
  submitting: boolean
  onSubmit: (selected: string[]) => Promise<void>
}

const EN_DASH = '–'
const ARROW = '→'

/** "A–B, B–C" for an undirected graph, "A→B" for a directed one, or "none". */
function describeEdges(test: TestCase): string {
  const joiner = test.directed ? ARROW : EN_DASH
  const edges = (test.edges ?? []).map((edge) => `${edge.source}${joiner}${edge.target}`)
  return edges.length > 0 ? edges.join(', ') : 'none'
}

/** Choose the test cases that expose the bug (FR-5.5; objective 7, ID document §4.4 and Table 1
 * row 7). The faulty program is shown with its indentation, and each test case as text: the
 * graph, the start vertex and the order a correct BFS gives, so it reads the same with a screen
 * reader and at 320 px. Test cases are numbered rather than shown by their stored id, because
 * an id such as "cycle" would name the very property the student has to spot.
 *
 * The server marks every test case (selected or not) right or wrong, with a reason for a wrong
 * one; that mark shows beside the test case until the student changes that choice. */
export function ChooseTests({ activity, result, submitting, onSubmit }: ChooseTestsProps) {
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set())
  const [checked, setChecked] = useState<ReadonlySet<string>>(new Set())
  const [missing, setMissing] = useState(false)
  const baseId = useId()
  const disabled = submitting || result?.correct === true
  const parts = new Map(result?.parts.map((part) => [part.ref, part]))

  function toggle(testId: string) {
    setMissing(false)
    setSelected((current) => {
      const next = new Set(current)
      if (next.has(testId)) next.delete(testId)
      else next.add(testId)
      return next
    })
  }

  return (
    <form
      className="grid grid-cols-[minmax(0,1fr)] gap-4"
      noValidate
      onSubmit={(event) => {
        event.preventDefault()
        if (selected.size === 0) {
          setMissing(true)
          return
        }
        setChecked(selected)
        // Sent in the order shown, so the request is the same whatever order they were ticked in.
        void onSubmit(activity.config.tests.filter((t) => selected.has(t.id)).map((t) => t.id))
      }}
    >
      <p className="m-0">{activity.config.prompt}</p>
      <CodeListing code={activity.config.code} label="The faulty BFS" />
      <fieldset
        className="m-0 grid min-w-0 gap-3 border-0 p-0"
        disabled={disabled}
        aria-describedby={missing ? `${baseId}-missing` : undefined}
      >
        <legend className="mb-2 font-medium">Which test cases does this BFS fail?</legend>
        {activity.config.tests.map((test, index) => {
          const id = `${baseId}-${index}`
          const isSelected = selected.has(test.id)
          const unchanged = checked.has(test.id) === isSelected
          const part = result && unchanged ? parts.get(index) : undefined
          return (
            <div
              key={test.id}
              className={`grid min-w-0 gap-2 rounded border p-3 ${part ? (part.correct ? 'border-success bg-success/10' : 'border-warning bg-warning/10') : 'border-border'}`}
            >
              <div className="flex items-start gap-3">
                <input
                  id={id}
                  type="checkbox"
                  className="mt-1 size-5 shrink-0"
                  checked={isSelected}
                  aria-describedby={`${id}-details${part ? ` ${id}-mark` : ''}`}
                  onChange={() => toggle(test.id)}
                />
                <label htmlFor={id} className="font-medium">
                  Test {index + 1}: start at {test.start_vertex}
                </label>
              </div>
              <dl id={`${id}-details`} className="m-0 grid gap-1 text-sm [overflow-wrap:anywhere]">
                <div>
                  <dt className="inline font-medium">Graph: </dt>
                  <dd className="inline">{test.directed ? 'directed' : 'undirected'}</dd>
                </div>
                <div>
                  <dt className="inline font-medium">Vertices: </dt>
                  <dd className="inline font-mono">{test.vertices.join(', ')}</dd>
                </div>
                <div>
                  <dt className="inline font-medium">Edges: </dt>
                  <dd className="inline font-mono">{describeEdges(test)}</dd>
                </div>
                <div>
                  <dt className="inline font-medium">Expected order: </dt>
                  <dd className="inline font-mono">{test.expected.join(', ')}</dd>
                </div>
              </dl>
              {part && (
                <p
                  id={`${id}-mark`}
                  className={`m-0 text-sm ${part.correct ? 'text-success' : 'text-warning'}`}
                >
                  {part.correct
                    ? 'Correct'
                    : `Check again${part.message ? `: ${part.message}` : ''}`}
                </p>
              )}
            </div>
          )
        })}
      </fieldset>
      {missing && (
        <p id={`${baseId}-missing`} className="m-0 text-sm text-warning" role="alert">
          Choose at least one test case before checking.
        </p>
      )}
      <div>
        {/* Focusable while the answer is checked, so a failed check leaves focus here and a
            result can take it from here (WCAG 2.4.3). */}
        <Button
          type="submit"
          loading={submitting}
          keepFocusWhileLoading
          disabled={result?.correct === true}
        >
          Check answer
        </Button>
      </div>
    </form>
  )
}
