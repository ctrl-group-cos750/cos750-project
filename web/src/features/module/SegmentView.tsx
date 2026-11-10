import { Alert, Markdown } from '../../components'
import { ActivityView } from '../activities/ActivityPage.tsx'
import { VideoView } from '../video/VideoPage.tsx'
import type { Segment } from './module.types.ts'

export type SegmentViewProps = {
  segment: Segment
}

/** Dispatches on segment.kind and renders the appropriate view. Videos and activities are shown
 * here, inside the module, so its Previous and Next buttons stay on screen. */
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
            <VideoView videoId={segment.videoId} />
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
            <ActivityView activityId={segment.activityId} heading="h3" />
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
