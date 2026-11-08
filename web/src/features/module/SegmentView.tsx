import { Link } from 'react-router'
import { Alert, Markdown } from '../../components'
import type { Segment } from './module.types.ts'

export type SegmentViewProps = {
  segment: Segment
}

/** Dispatches on segment.kind and renders the appropriate view. */
export function SegmentView({ segment }: SegmentViewProps) {
  switch (segment.kind) {
    case 'text':
    case 'worked_example':
    case 'refresher':
      return (
        <section aria-label={segment.title} className="grid gap-4">
          <h2 className="text-xl font-semibold">{segment.title}</h2>
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
          <h2 className="text-xl font-semibold">{segment.title}</h2>
          {segment.videoId !== null ? (
            <Link
              to={`/videos/${segment.videoId}`}
              className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-3 font-medium hover:bg-accent"
            >
              ▶ Watch video
            </Link>
          ) : (
            <Alert tone="warning">Video not available.</Alert>
          )}
        </section>
      )

    case 'activity':
      return (
        <section aria-label={segment.title} className="grid gap-4">
          <h2 className="text-xl font-semibold">{segment.title}</h2>
          {segment.activityId !== null ? (
            <Link
              to={`/activities/${segment.activityId}`}
              className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-4 py-3 font-medium hover:bg-accent"
            >
              Start the activity
            </Link>
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
