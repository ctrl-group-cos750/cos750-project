import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router'
import { ApiError, retryUnlessRefused } from '../../api/client.ts'
import { Alert, Spinner } from '../../components'
import { useRefreshRewards } from '../rewards/hooks.ts'
import { NarratedVideoPlayer } from './NarratedVideoPlayer.tsx'
import { fetchVideo, requestCheckpointHint, submitCheckpointAttempt } from './video.api.ts'

/** /videos/:videoId — one narrated video with its checkpoints, on its own page. */
export function VideoPage() {
  return <VideoView videoId={Number(useParams().videoId)} />
}

/** A narrated video with its checkpoints: the video page, and a video segment in a module
 * (SegmentView), which keeps the module's own navigation on screen. */
export function VideoView({
  videoId: id,
  onResult,
  heading,
}: {
  videoId: number
  onResult?: () => void
  /** The level of its "Checkpoint" and "Transcript" headings: h3 inside a module segment. */
  heading?: 'h2' | 'h3'
}) {
  const query = useQuery({
    queryKey: ['video', id],
    queryFn: () => fetchVideo(id),
    retry: retryUnlessRefused, // a video that isn't open yet (403) won't open on a retry
  })
  const refreshRewards = useRefreshRewards()
  if (query.isPending) return <Spinner label="Loading the video" />
  if (query.isError)
    return (
      <Alert
        tone={query.error instanceof ApiError && query.error.status === 403 ? 'info' : 'danger'}
      >
        {query.error.message}
      </Alert>
    )
  return (
    <NarratedVideoPlayer
      key={id}
      video={query.data.video}
      activities={query.data.activities}
      initialPassedIds={query.data.passedIds}
      heading={heading}
      onAttempt={async (input) => {
        const result = await submitCheckpointAttempt(input)
        if (result.correct) refreshRewards() // a correct answer can earn points (FR-9.1)
        onResult?.()
        return result
      }}
      onHint={requestCheckpointHint}
    />
  )
}
