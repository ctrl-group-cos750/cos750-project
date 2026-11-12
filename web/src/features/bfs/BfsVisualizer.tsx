import { reportEvent } from '../../api/events.ts'
import { useEffect, useReducer } from 'react'
import { Gauge, Lightbulb, Pause, Play, RotateCcw, StepBack, StepForward } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { GraphCanvas } from './GraphCanvas.tsx'
import { createPlayback, playbackReducer } from './bfsPlayback.ts'
import type { BfsScenario, VertexId } from './bfs.types.ts'
import { expectedVertex } from './bfs.types.ts'

type BfsVisualizerProps = {
  scenario: BfsScenario
}

const speeds = [1500, 900, 450] as const

function displayItems(input: { items: readonly string[] }): string {
  return input.items.join(', ') || 'Empty'
}

function speedName(input: { speed: number }): string {
  if (input.speed === 1500) return 'Slow'
  if (input.speed === 900) return 'Normal'
  return 'Fast'
}

export function BfsVisualizer({ scenario }: BfsVisualizerProps) {
  const [playback, dispatch] = useReducer(
    playbackReducer,
    { frameCount: scenario.frames.length },
    createPlayback,
  )

  const frame = scenario.frames[playback.frameIndex] ?? scenario.frames[0]
  const expected = expectedVertex({
    scenario,
    frameIndex: Math.min(playback.frameIndex, scenario.frames.length - 1),
  })
  const isComplete = playback.frameIndex === playback.lastFrameIndex
  const predictionRequired = playback.predictionMode && expected !== null

  useEffect(() => {
    if (!playback.playing || playback.frameIndex === playback.lastFrameIndex) return

    const timer = window.setTimeout(() => {
      dispatch({ type: 'REQUEST_NEXT', predictionRequired })
    }, playback.speedMs)

    return () => window.clearTimeout(timer)
  }, [
    playback.frameIndex,
    playback.lastFrameIndex,
    playback.playing,
    playback.speedMs,
    predictionRequired,
  ])

  function requestNext() {
    dispatch({ type: 'REQUEST_NEXT', predictionRequired })
  }

  function chooseVertex(vertexId: VertexId) {
    if (expected === null) return

    dispatch({
      type: 'ANSWER',
      feedback: {
        selected: vertexId,
        correct: vertexId === expected,
        expected,
      },
    })
    // Prediction mode is recorded for the pilot's evaluation (FR-10.1, #146): each prediction,
    // with whether it was right. Still checked here, from the engine's steps (FR-6.4).
    reportEvent('prediction_made', scenario.id, vertexId === expected)
  }

  return (
    <section
      className="mx-auto w-full max-w-6xl space-y-5 px-4 py-6 sm:px-6"
      aria-labelledby="bfs-title"
    >
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 id="bfs-title" className="text-2xl font-semibold tracking-tight">
              {scenario.title}
            </h1>
          </div>
          <p className="text-sm text-muted-foreground">
            Step {playback.frameIndex + 1} of {scenario.frames.length}
          </p>
        </div>

        <label className="flex cursor-pointer items-center gap-2 rounded-lg border bg-card px-3 py-2 text-sm font-medium">
          <input
            type="checkbox"
            className="size-4 accent-primary"
            checked={playback.predictionMode}
            onChange={(event) => {
              dispatch({ type: 'SET_PREDICTION_MODE', enabled: event.target.checked })
            }}
          />
          Prediction mode
        </label>
      </header>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(20rem,0.8fr)]">
        <Card className="border">
          <CardContent className="space-y-3">
            <GraphCanvas scenario={scenario} frame={frame} />

            <div
              className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground"
              aria-label="Graph legend"
            >
              <span>
                <strong>▶ Current</strong> — being processed
              </span>
              <span>
                <strong>… Queued</strong> — waiting
              </span>
              <span>
                <strong>✓ Visited</strong> — processed
              </span>
            </div>
          </CardContent>
        </Card>

        <Card className="border">
          <CardContent className="space-y-5">
            <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-3 text-sm">
              <dt className="font-medium text-muted-foreground">Current vertex</dt>
              <dd className="font-mono font-semibold">{frame.current ?? 'None yet'}</dd>

              <dt className="font-medium text-muted-foreground">Queue</dt>
              <dd className="font-mono">{displayItems({ items: frame.queue })}</dd>

              <dt className="font-medium text-muted-foreground">Visited set</dt>
              <dd className="font-mono">{displayItems({ items: frame.visited })}</dd>

              <dt className="font-medium text-muted-foreground">Traversal order</dt>
              <dd className="font-mono">{displayItems({ items: frame.traversal })}</dd>
            </dl>

            {playback.phase === 'answering' && (
              <fieldset className="space-y-3 rounded-lg border border-primary/40 bg-primary/5 p-4">
                <legend className="px-1 text-sm font-semibold">
                  Which vertex will BFS process next?
                </legend>

                <div className="flex flex-wrap gap-2">
                  {scenario.vertices.map((vertex) => (
                    <Button
                      key={vertex.id}
                      type="button"
                      variant="outline"
                      onClick={() => chooseVertex(vertex.id)}
                    >
                      {vertex.label}
                    </Button>
                  ))}
                </div>
              </fieldset>
            )}

            {playback.phase === 'feedback' && playback.feedback && (
              <Alert
                className={
                  playback.feedback.correct
                    ? 'border-success bg-success-soft'
                    : 'border-destructive/50 bg-destructive/10'
                }
              >
                <Lightbulb aria-hidden="true" />
                <AlertTitle>{playback.feedback.correct ? 'Correct' : 'Not quite'}</AlertTitle>
                <AlertDescription>
                  {playback.feedback.correct
                    ? `${playback.feedback.selected} is first in the queue, so BFS processes it next.`
                    : `${playback.feedback.expected} is first in the queue, so BFS processes it next.`}
                </AlertDescription>

                <Button
                  type="button"
                  size="sm"
                  className="mt-3 w-fit"
                  onClick={() => dispatch({ type: 'CONTINUE' })}
                >
                  Continue
                </Button>
              </Alert>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="border">
        <CardContent className="flex flex-wrap items-center gap-2">
          <Button type="button" variant="outline" onClick={() => dispatch({ type: 'RESET' })}>
            <RotateCcw aria-hidden="true" />
            Reset
          </Button>

          <Button
            type="button"
            variant="outline"
            disabled={playback.frameIndex === 0}
            onClick={() => dispatch({ type: 'BACK' })}
          >
            <StepBack aria-hidden="true" />
            Step back
          </Button>

          <Button
            type="button"
            variant="secondary"
            disabled={playback.phase !== 'ready' || isComplete}
            onClick={() => dispatch({ type: 'TOGGLE_PLAY' })}
          >
            {playback.playing ? <Pause aria-hidden="true" /> : <Play aria-hidden="true" />}
            {playback.playing ? 'Pause' : 'Play'}
          </Button>

          <Button type="button" disabled={isComplete} onClick={requestNext}>
            <StepForward aria-hidden="true" />
            Step forward
          </Button>

          <label className="ml-auto flex items-center gap-2 text-sm font-medium">
            <Gauge aria-hidden="true" className="size-4 text-muted-foreground" />
            Speed
            <select
              className="h-8 rounded-md border border-input bg-background px-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={playback.speedMs}
              onChange={(event) => {
                dispatch({ type: 'SET_SPEED', speedMs: Number(event.target.value) })
              }}
            >
              {speeds.map((speed) => (
                <option key={speed} value={speed}>
                  {speedName({ speed })}
                </option>
              ))}
            </select>
          </label>
        </CardContent>
      </Card>

      <p className="sr-only" aria-live="polite">
        {playback.phase === 'answering'
          ? 'Choose the next vertex before continuing.'
          : `Current BFS step: ${playback.frameIndex + 1}.`}
      </p>
    </section>
  )
}
