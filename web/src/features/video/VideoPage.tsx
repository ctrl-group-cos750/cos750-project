import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router'
import { Alert, Spinner } from '../../components'
import { NarratedVideoPlayer } from './NarratedVideoPlayer.tsx'
import { fetchVideo, requestCheckpointHint, submitCheckpointAttempt } from './video.api.ts'

/** /videos/:videoId — one narrated video with its checkpoints. The module player (#15) will
 * show videos as segments; until then this page is how a video is reached and tested. */
export function VideoPage() {
  const id = Number(useParams().videoId)
  const query = useQuery({ queryKey: ['video', id], queryFn: () => fetchVideo(id) })
  if (query.isPending) return <Spinner label="Loading the video" />
  if (query.isError) return <Alert tone="danger">{query.error.message}</Alert>
  return (
    <NarratedVideoPlayer
      key={id}
      video={query.data.video}
      activities={query.data.activities}
      initialPassedIds={query.data.passedIds}
      onAttempt={submitCheckpointAttempt}
      onHint={requestCheckpointHint}
    />
  )
}
