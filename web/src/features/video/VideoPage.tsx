import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router'
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
export function VideoView({ videoId: id }: { videoId: number }) {
  const query = useQuery({ queryKey: ['video', id], queryFn: () => fetchVideo(id) })
  const refreshRewards = useRefreshRewards()
  if (query.isPending) return <Spinner label="Loading the video" />
  if (query.isError) return <Alert tone="danger">{query.error.message}</Alert>
  return (
    <NarratedVideoPlayer
      key={id}
      video={query.data.video}
      activities={query.data.activities}
      initialPassedIds={query.data.passedIds}
      onAttempt={async (input) => {
        const result = await submitCheckpointAttempt(input)
        if (result.correct) refreshRewards() // a correct answer can earn points (FR-9.1)
        return result
      }}
      onHint={requestCheckpointHint}
    />
  )
}
