import { Alert } from '../../components'
import { useRef, useState } from 'react'
import { findFirstUnansweredCheckpoint, findReachedCheckpoint } from './checkpointGate.ts'
import { CheckpointQuestion } from './CheckpointQuestion.tsx'
import type {
  AttemptInput,
  AttemptResult,
  Checkpoint,
  Hint,
  MultipleChoiceActivity,
  VideoMetadata,
} from './video.types.ts'
import styles from './NarratedVideoPlayer.module.css'

type NarratedVideoPlayerProps = {
  video: VideoMetadata
  activities: Readonly<Record<number, MultipleChoiceActivity>>
  onAttempt: (input: AttemptInput) => Promise<AttemptResult>
  onHint: (input: { activityId: number }) => Promise<Hint>
}

export function NarratedVideoPlayer(props: NarratedVideoPlayerProps) {
  const playerRef = useRef<HTMLVideoElement>(null)
  const [passedIds, setPassedIds] = useState<ReadonlySet<number>>(() => new Set())
  const [activeCheckpoint, setActiveCheckpoint] = useState<Checkpoint>()

  function pauseAtCheckpoint(checkpoint: Checkpoint) {
    playerRef.current?.pause()
    setActiveCheckpoint(checkpoint)
  }

  function handleTimeUpdate() {
    if (activeCheckpoint) return
    const player = playerRef.current
    if (!player) return

    const checkpoint = findReachedCheckpoint({
      checkpoints: props.video.checkpoints,
      passedIds,
      currentSeconds: player.currentTime,
    })
    if (checkpoint) pauseAtCheckpoint(checkpoint)
  }

  function handleSeeking() {
    const player = playerRef.current
    if (!player) return

    const checkpoint = findFirstUnansweredCheckpoint({
      checkpoints: props.video.checkpoints,
      passedIds,
    })
    if (!checkpoint || player.currentTime <= checkpoint.atSeconds) return

    player.currentTime = checkpoint.atSeconds
    pauseAtCheckpoint(checkpoint)
  }

  function handleCheckpointPassed() {
    if (!activeCheckpoint) return

    setPassedIds((currentIds: ReadonlySet<number>) => new Set([...currentIds, activeCheckpoint.id]))
    setActiveCheckpoint(undefined)
    void playerRef.current?.play()
  }

  const activity = activeCheckpoint ? props.activities[activeCheckpoint.activityId] : undefined

  return (
    <section className="grid max-w-5xl gap-6" aria-label="Narrated lesson video">
      <video
        ref={playerRef}
        className="w-full rounded-lg border border-border bg-black"
        controls
        preload="metadata"
        onTimeUpdate={handleTimeUpdate}
        onSeeking={handleSeeking}
      >
        <source src={props.video.mediaPath} type="video/mp4" />
        <track
          kind="captions"
          src={props.video.captionsPath}
          srcLang="en"
          label="English captions"
          default
        />
        Your browser does not support HTML video.
      </video>

      {activeCheckpoint && !activity && (
        <Alert tone="danger">This checkpoint could not load. Please refresh the page.</Alert>
      )}
      {activeCheckpoint && activity && (
        <section className={styles.checkpoint} aria-labelledby="checkpoint-heading">
          <h2 id="checkpoint-heading">Checkpoint</h2>
          <CheckpointQuestion
            activity={activity}
            onAttempt={props.onAttempt}
            onHint={props.onHint}
            onPassed={handleCheckpointPassed}
          />
        </section>
      )}
      <section
        className="max-w-3xl rounded-lg border border-border bg-card p-6"
        aria-labelledby="transcript-heading"
      >
        <h2 id="transcript-heading" className="mb-3 text-xl font-semibold">
          Transcript
        </h2>
        <p className="text-muted-foreground">{props.video.transcript}</p>
      </section>
    </section>
  )
}
