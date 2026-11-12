import { useEffect } from 'react'
import { reportEvent } from '../../api/events.ts'
import { Alert, Markdown } from '../../components'
import { ActivityView } from '../activities/ActivityPage.tsx'
import { VideoView } from '../video/VideoPage.tsx'
import type { Segment } from './module.types.ts'

export type SegmentViewProps = {
  segment: Segment
  /** Called after each answer in the segment, so the module can check whether it is done. */
  onAnswered?: () => void
  /** A short line under the heading saying why the segment is there: the module page gives one
   * to the first of a run of support segments (FR-8.4). */
  intro?: string | null
}

/** A video segment's narration as text, below its video (FR-3.2, #149): closed by default, so it
 * doesn't push the module's buttons down, and opened with a native disclosure (keyboard: Tab to
 * the summary, then Enter or Space). Named "Text version" because the player has its own
 * "Transcript" heading. */
function TextVersion({ body }: { body: string }) {
  return (
    <details className="max-w-3xl rounded-lg border border-border bg-card p-6">
      <summary className="cursor-pointer text-lg font-semibold">Text version</summary>
      <div className="mt-3">
        <Markdown>{body}</Markdown>
      </div>
    </details>
  )
}

/** Dispatches on segment.kind and renders the appropriate view. Videos and activities are shown
 * here, inside the module, so its Previous and Next buttons stay on screen. Each segment's heading
 * is focusable from script only (tabIndex -1, data-focus-heading): ModulePage moves focus to it
 * after Previous or Next. */
export function SegmentView({ segment, onAnswered, intro }: SegmentViewProps) {
  // The pilot's timeline of what each student saw (FR-10.1, #141): one event per segment shown.
  useEffect(() => reportEvent('segment_viewed', segment.id), [segment.id])
  const introLine = intro ? <p className="text-muted-foreground">{intro}</p> : null

  switch (segment.kind) {
    case 'text':
    case 'worked_example':
    case 'refresher':
      return (
        <section aria-label={segment.title} className="grid gap-4">
          <h2 className="text-xl font-semibold" tabIndex={-1} data-focus-heading>
            {segment.title}
          </h2>
          {introLine}
          {segment.body ? (
            <Markdown>{segment.body}</Markdown>
          ) : (
            <Alert tone="info">This segment has no content yet.</Alert>
          )}
        </section>
      )

    case 'video':
      return (
        <section aria-label={segment.title} className="grid gap-4">
          <h2 className="text-xl font-semibold" tabIndex={-1} data-focus-heading>
            {segment.title}
          </h2>
          {introLine}
          {segment.videoId !== null ? (
            <>
              <VideoView videoId={segment.videoId} heading="h3" onResult={onAnswered} />
              {segment.body && <TextVersion body={segment.body} />}
            </>
          ) : segment.body ? (
            // No video yet (or it can't be played): the narration as text is the lesson (FR-3.2, #149).
            <Markdown>{segment.body}</Markdown>
          ) : (
            <Alert tone="warning">Video not available.</Alert>
          )}
        </section>
      )

    case 'activity':
      return (
        <section aria-label={segment.title} className="grid gap-4">
          <h2 className="text-xl font-semibold" tabIndex={-1} data-focus-heading>
            {segment.title}
          </h2>
          {introLine}
          {segment.activityId !== null ? (
            <ActivityView activityId={segment.activityId} showTitle={false} onResult={onAnswered} />
          ) : (
            <Alert tone="warning">Activity not available.</Alert>
          )}
        </section>
      )

    default: {
      // exhaustiveness check — segment.kind narrows to never here
      const exhaustiveCheck: never = segment.kind
      return <Alert tone="warning">Unknown segment kind: {String(exhaustiveCheck)}</Alert>
    }
  }
}
