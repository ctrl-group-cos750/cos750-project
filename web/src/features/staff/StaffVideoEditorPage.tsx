import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useId, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { ApiError } from '../../api/client.ts'
import { Alert, Button, Card, Spinner, TextField } from '../../components'
import {
  createVideo,
  getVideo,
  updateVideo,
  uploadMedia,
  type MediaKind,
  type SavedVideo,
  type StaffCheckpoint,
  type StaffVideo,
} from './staff.api.ts'
import { formatTime } from './formatTime.ts'
import styles from './staff.module.css'

const EMPTY: StaffVideo = {
  title: '',
  mediaPath: '',
  captionsPath: '',
  transcript: '',
  durationSeconds: 0,
  checkpoints: [],
}
const LEVELS = [1, 2, 3, 4] as const
const HINT_HELP: Record<number, string> = {
  1: 'A nudge',
  2: 'Points at the idea',
  3: 'Gives a lot away (counts as support)',
  4: 'The worked answer (counts as support)',
}

/**
 * /staff/videos/new and /staff/videos/:videoId — upload a video and its captions, then add
 * checkpoints while watching: each is a multiple-choice question with feedback for the wrong
 * options and up to four hints. Saving sends the whole video (api/app/routers/staff.py).
 */
export function StaffVideoEditorPage() {
  const param = useParams().videoId
  const id = param === 'new' ? undefined : Number(param)
  const saved = useQuery({
    queryKey: ['staff', 'video', id],
    queryFn: () => getVideo(id!),
    enabled: id !== undefined,
  })
  if (id !== undefined && saved.isPending) return <Spinner label="Loading the video" />
  if (saved.isError) return <Alert tone="danger">{saved.error.message}</Alert>
  return <Editor key={id ?? 'new'} id={id} initial={saved.data ?? EMPTY} />
}

function Editor({ id, initial }: { id?: number; initial: StaffVideo }) {
  const [draft, setDraft] = useState<StaffVideo>(initial)
  const [dirty, setDirty] = useState(false)
  const playerRef = useRef<HTMLVideoElement>(null)
  const navigate = useNavigate()
  useWarnBeforeLeaving(dirty)
  const queryClient = useQueryClient()

  function change(next: Partial<StaffVideo>) {
    setDraft((d) => ({ ...d, ...next }))
    setDirty(true)
  }
  function changeCheckpoint(index: number, next: StaffCheckpoint) {
    change({ checkpoints: draft.checkpoints.map((c, i) => (i === index ? next : c)) })
  }

  const save = useMutation({
    mutationFn: (video: StaffVideo) => (id ? updateVideo(id, video) : createVideo(video)),
    onSuccess: (result: SavedVideo) => {
      void queryClient.invalidateQueries({ queryKey: ['staff'] })
      setDraft(result)
      setDirty(false)
      if (!id) void navigate(`/staff/videos/${result.id}`, { replace: true })
    },
  })

  // What still stops the save, said next to the button rather than leaving it silently disabled.
  const missing = [
    !draft.mediaPath && 'the video',
    !draft.captionsPath && 'the captions',
    !draft.title.trim() && 'a title',
  ].filter((m) => m !== false)

  function addCheckpointHere() {
    const at = Math.round((playerRef.current?.currentTime ?? 0) * 10) / 10
    playerRef.current?.pause()
    const next = [...draft.checkpoints, newCheckpoint(at)].sort((a, b) => a.atSeconds - b.atSeconds)
    change({ checkpoints: next })
  }

  function jumpTo(seconds: number) {
    if (playerRef.current) playerRef.current.currentTime = seconds
  }

  return (
    <>
      <div className={styles.titleRow}>
        <h1>{id ? 'Edit video' : 'New video'}</h1>
        <Link to="/staff/videos">All videos</Link>
      </div>

      <section className={styles.section} aria-labelledby="files-heading">
        <h2 id="files-heading">1. Files</h2>
        <div className={styles.twoColumns}>
          <MediaUpload
            kind="video"
            label="Video (MP4, up to 95 MB)"
            accept="video/mp4"
            path={draft.mediaPath}
            onUploaded={(path, file) =>
              void readDuration(file).then((seconds) =>
                change({ mediaPath: path, durationSeconds: seconds }),
              )
            }
          />
          <MediaUpload
            kind="captions"
            label="Captions (WebVTT .vtt)"
            accept=".vtt,text/vtt"
            path={draft.captionsPath}
            onUploaded={(path) => change({ captionsPath: path })}
          />
        </div>
      </section>

      <section className={styles.section} aria-labelledby="details-heading">
        <h2 id="details-heading">2. Details</h2>
        <TextField
          label="Title"
          value={draft.title}
          maxLength={200}
          onChange={(e) => change({ title: e.target.value })}
        />
        <TextArea
          label="Transcript"
          hint="The text version of the video, shown under it (FR-3.2)."
          value={draft.transcript}
          rows={6}
          onChange={(transcript) => change({ transcript })}
        />
      </section>

      <section className={styles.section} aria-labelledby="checkpoints-heading">
        <h2 id="checkpoints-heading">3. Checkpoints</h2>
        {draft.mediaPath ? (
          <>
            <video
              ref={playerRef}
              className={styles.preview}
              src={draft.mediaPath}
              controls
              preload="metadata"
            >
              <track
                kind="captions"
                src={draft.captionsPath || undefined}
                srcLang="en"
                label="English"
                default
              />
            </video>
            <p className={styles.muted}>
              Length {formatTime(draft.durationSeconds)}. Pause where the video should stop, then
              add a checkpoint there.
            </p>
            <div>
              <Button variant="secondary" onClick={addCheckpointHere}>
                Add checkpoint at the current time
              </Button>
            </div>
          </>
        ) : (
          <p className={styles.muted}>Upload the video first.</p>
        )}

        {draft.checkpoints.map((checkpoint, index) => (
          <CheckpointEditor
            // A new checkpoint has no id until saved; its time and position identify it until then.
            key={checkpoint.id ?? `new-${index}-${checkpoint.atSeconds}`}
            number={index + 1}
            checkpoint={checkpoint}
            durationSeconds={draft.durationSeconds}
            onChange={(next) => changeCheckpoint(index, next)}
            onRemove={() =>
              change({ checkpoints: draft.checkpoints.filter((_, i) => i !== index) })
            }
            onJump={() => jumpTo(checkpoint.atSeconds)}
            onUseCurrentTime={() =>
              changeCheckpoint(index, {
                ...checkpoint,
                atSeconds: Math.round((playerRef.current?.currentTime ?? 0) * 10) / 10,
              })
            }
          />
        ))}
      </section>

      <div className={styles.saveBar}>
        <Button
          loading={save.isPending}
          disabled={missing.length > 0}
          onClick={() => save.mutate(forSaving(draft))}
        >
          {id ? 'Save changes' : 'Create video'}
        </Button>
        {missing.length > 0 && (
          <span className={styles.muted}>Still needs {missing.join(', ')}.</span>
        )}
        {id && <Link to={`/videos/${id}`}>Open as a student</Link>}
        {dirty && !save.isPending && <span className={styles.muted}>Unsaved changes</span>}
        {save.isSuccess && !dirty && <span className={styles.muted}>Saved.</span>}
      </div>
      {save.isError && <SaveError error={save.error} />}
    </>
  )
}

function SaveError({ error }: { error: Error }) {
  const fields = error instanceof ApiError ? Object.values(error.fields) : []
  return (
    <Alert tone="danger" title="Not saved">
      {fields.length > 0 ? (
        <ul>
          {fields.map((message) => (
            <li key={message}>{message}</li>
          ))}
        </ul>
      ) : (
        <p>{error.message}</p>
      )}
    </Alert>
  )
}

function MediaUpload(props: {
  kind: MediaKind
  label: string
  accept: string
  path: string
  onUploaded: (path: string, file: File) => void
}) {
  const inputId = useId()
  const [progress, setProgress] = useState<number>()
  const [error, setError] = useState('')

  async function upload(file: File | undefined) {
    if (!file) return
    setError('')
    setProgress(0)
    try {
      props.onUploaded(await uploadMedia(props.kind, file, setProgress), file)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'The upload failed.')
    } finally {
      setProgress(undefined)
    }
  }

  return (
    <Card>
      <div className={styles.field}>
        <label htmlFor={inputId} className={styles.label}>
          {props.label}
        </label>
        <input
          id={inputId}
          type="file"
          accept={props.accept}
          disabled={progress !== undefined}
          onChange={(e) => void upload(e.target.files?.[0])}
        />
        {progress !== undefined && (
          <progress className={styles.progress} value={progress} max={1}>
            {Math.round(progress * 100)}%
          </progress>
        )}
        {props.path && <p className={styles.muted}>Uploaded: {props.path}</p>}
        {error && <Alert tone="danger">{error}</Alert>}
      </div>
    </Card>
  )
}

function CheckpointEditor(props: {
  number: number
  checkpoint: StaffCheckpoint
  durationSeconds: number
  onChange: (next: StaffCheckpoint) => void
  onRemove: () => void
  onJump: () => void
  onUseCurrentTime: () => void
}) {
  const { checkpoint, onChange } = props
  const q = checkpoint.question
  const groupName = useId()

  function setQuestion(next: Partial<StaffCheckpoint['question']>) {
    onChange({ ...checkpoint, question: { ...q, ...next } })
  }
  function setOption(optionId: string, label: string) {
    setQuestion({ options: q.options.map((o) => (o.id === optionId ? { ...o, label } : o)) })
  }
  function removeOption(optionId: string) {
    const options = q.options.filter((o) => o.id !== optionId)
    const feedback = { ...q.feedback }
    delete feedback[optionId]
    setQuestion({ options, feedback, correct: q.correct === optionId ? options[0].id : q.correct })
  }
  function setHint(level: number, body: string) {
    const others = checkpoint.hints.filter((h) => h.level !== level)
    onChange({
      ...checkpoint,
      hints: [...others, { level, body }].sort((a, b) => a.level - b.level),
    })
  }

  return (
    <Card>
      <div className={styles.section}>
        <div className={styles.checkpointHeader}>
          <h3>Checkpoint {props.number}</h3>
          <div className={styles.row}>
            <TextField
              className={styles.time}
              label="Stops at (seconds)"
              type="number"
              min={0}
              max={Math.max(props.durationSeconds - 0.1, 0)}
              step={0.1}
              value={checkpoint.atSeconds}
              onChange={(e) => onChange({ ...checkpoint, atSeconds: Number(e.target.value) })}
            />
            <Button size="sm" variant="secondary" onClick={props.onJump}>
              Go to {formatTime(checkpoint.atSeconds)}
            </Button>
            <Button size="sm" variant="secondary" onClick={props.onUseCurrentTime}>
              Use current time
            </Button>
            <Button size="sm" variant="danger" onClick={props.onRemove}>
              Remove
            </Button>
          </div>
        </div>

        <TextArea
          label="Question"
          value={q.prompt}
          rows={2}
          onChange={(prompt) => setQuestion({ prompt })}
        />

        <fieldset className={styles.section}>
          <legend className={styles.label}>
            Options: mark the correct one, and say why each wrong one is wrong
          </legend>
          {q.options.map((option, i) => (
            <div key={option.id} className={styles.option}>
              <input
                type="radio"
                name={groupName}
                checked={q.correct === option.id}
                onChange={() => setQuestion({ correct: option.id })}
                aria-label={`Option ${i + 1} is correct`}
              />
              <input
                className={styles.input}
                value={option.label}
                placeholder={`Option ${i + 1}`}
                aria-label={`Option ${i + 1}`}
                onChange={(e) => setOption(option.id, e.target.value)}
              />
              {q.correct === option.id ? (
                <span className={styles.muted}>Correct answer</span>
              ) : (
                <input
                  className={styles.input}
                  value={q.feedback[option.id] ?? ''}
                  placeholder="Why this is wrong (shown after choosing it)"
                  aria-label={`Why option ${i + 1} is wrong`}
                  onChange={(e) =>
                    setQuestion({ feedback: { ...q.feedback, [option.id]: e.target.value } })
                  }
                />
              )}
              <Button
                size="sm"
                variant="ghost"
                disabled={q.options.length <= 2}
                onClick={() => removeOption(option.id)}
                aria-label={`Remove option ${i + 1}`}
              >
                ×
              </Button>
            </div>
          ))}
          <div>
            <Button
              size="sm"
              variant="secondary"
              disabled={q.options.length >= 10}
              onClick={() =>
                setQuestion({ options: [...q.options, { id: nextOptionId(q.options), label: '' }] })
              }
            >
              Add option
            </Button>
          </div>
        </fieldset>

        <fieldset className={styles.section}>
          <legend className={styles.label}>Hints, one level at a time (leave blank to skip)</legend>
          {LEVELS.map((level) => (
            <TextArea
              key={level}
              label={`Hint ${level}: ${HINT_HELP[level]}`}
              rows={2}
              value={checkpoint.hints.find((h) => h.level === level)?.body ?? ''}
              onChange={(body) => setHint(level, body)}
            />
          ))}
        </fieldset>
      </div>
    </Card>
  )
}

function TextArea(props: {
  label: string
  hint?: string
  value: string
  rows: number
  onChange: (value: string) => void
}) {
  const id = useId()
  return (
    <div className={styles.field}>
      <label htmlFor={id} className={styles.label}>
        {props.label}
      </label>
      <textarea
        id={id}
        className={styles.textarea}
        rows={props.rows}
        value={props.value}
        onChange={(e) => props.onChange(e.target.value)}
      />
      {props.hint && <p className={styles.muted}>{props.hint}</p>}
    </div>
  )
}

function newCheckpoint(atSeconds: number): StaffCheckpoint {
  return {
    atSeconds,
    question: {
      prompt: '',
      options: [
        { id: 'a', label: '' },
        { id: 'b', label: '' },
      ],
      correct: 'a',
      feedback: {},
    },
    hints: [],
  }
}

/** The first unused letter: a, b, c … */
function nextOptionId(options: readonly { id: string }[]) {
  const used = new Set(options.map((o) => o.id))
  return 'abcdefghijklmnopqrstuvwxyz'.split('').find((c) => !used.has(c)) ?? String(used.size)
}

/** Exactly what the API accepts: the fields a save sends, without the ids the API adds to its
 * answer (the video's `id`, each checkpoint's `activityId`), and without blank hints or feedback. */
function forSaving(video: StaffVideo): StaffVideo {
  return {
    title: video.title,
    mediaPath: video.mediaPath,
    captionsPath: video.captionsPath,
    transcript: video.transcript,
    durationSeconds: video.durationSeconds,
    checkpoints: video.checkpoints.map((c) => ({
      ...(c.id === undefined ? {} : { id: c.id }),
      atSeconds: c.atSeconds,
      hints: c.hints.filter((h) => h.body.trim()).map((h) => ({ level: h.level, body: h.body })),
      question: {
        prompt: c.question.prompt,
        options: c.question.options.map((o) => ({ id: o.id, label: o.label })),
        correct: c.question.correct,
        feedback: Object.fromEntries(
          Object.entries(c.question.feedback).filter(
            ([optionId, text]) => text.trim() && optionId !== c.question.correct,
          ),
        ),
      },
    })),
  }
}

/** The video's length in whole seconds, read in the browser from the chosen file. */
function readDuration(file: File): Promise<number> {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file)
    const probe = document.createElement('video')
    probe.preload = 'metadata'
    probe.onloadedmetadata = () => {
      URL.revokeObjectURL(url)
      resolve(Math.ceil(probe.duration))
    }
    probe.onerror = () => {
      URL.revokeObjectURL(url)
      resolve(0)
    }
    probe.src = url
  })
}

/** Asks before the tab is closed or reloaded with unsaved changes. */
function useWarnBeforeLeaving(dirty: boolean) {
  useEffect(() => {
    if (!dirty) return
    const warn = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [dirty])
}
