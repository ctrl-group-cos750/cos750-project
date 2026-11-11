import { ArrowDown, ArrowUp, Plus, Trash2 } from 'lucide-react'
import { Link } from 'react-router'
import { Button, Card, TextField } from '../../../components'
import styles from '../staff.module.css'
import { SEGMENT_KINDS, type ContentOverview, type SegmentIn } from './content.api.ts'
import { Select, TextArea } from './ContentFields.tsx'

/**
 * A module's (or a review path's) segments, in the order a student meets them: move, remove, add,
 * and edit each one. What a segment needs depends on its kind: a body for text, a worked example
 * or a refresher; an activity for an activity step; a video for a video step.
 */
export function SegmentsEditor(props: {
  segments: SegmentIn[]
  overview: ContentOverview
  /** The module these segments are in, to list its activities first. */
  moduleId?: number
  /** Refreshers only belong in module 0. */
  allowRefreshers: boolean
  /** Nothing on a review path can be skipped. */
  allowSkipping: boolean
  onChange: (segments: SegmentIn[]) => void
}) {
  const { segments, onChange } = props
  const kinds = SEGMENT_KINDS.filter((k) => props.allowRefreshers || k.value !== 'refresher')
  const activityOptions = [...props.overview.activities]
    .sort((a, b) => Number(b.moduleId === props.moduleId) - Number(a.moduleId === props.moduleId))
    .map((a) => ({
      value: a.id,
      label: `#${a.id} ${a.title}${(a.moduleId ?? null) !== null ? ` (module ${a.moduleId})` : ''}`,
    }))
  const videoOptions = props.overview.videos.map((v) => ({ value: v.id, label: v.title }))

  function set(index: number, next: Partial<SegmentIn>) {
    onChange(segments.map((s, i) => (i === index ? { ...s, ...next } : s)))
  }
  function move(index: number, by: -1 | 1) {
    const next = [...segments]
    const [item] = next.splice(index, 1)
    next.splice(index + by, 0, item)
    onChange(next)
  }
  function add() {
    onChange([...segments, { kind: 'text', title: '', body: '' }])
  }

  return (
    <div className={styles.section}>
      {segments.length === 0 && <p className={styles.muted}>No segments yet.</p>}
      {segments.map((seg, index) => (
        // A new segment has no id until saved; its place identifies it until then.
        <Card key={seg.id ?? `new-${index}`}>
          <div className={styles.section}>
            <div className={styles.checkpointHeader}>
              <h3 className="font-semibold">
                {index + 1}. {seg.title || 'Untitled'}
                {(seg.id ?? null) === null && <span className={styles.muted}> (new)</span>}
              </h3>
              <div className={styles.row}>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={index === 0}
                  aria-label={`Move segment ${index + 1} up`}
                  onClick={() => move(index, -1)}
                >
                  <ArrowUp aria-hidden />
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={index === segments.length - 1}
                  aria-label={`Move segment ${index + 1} down`}
                  onClick={() => move(index, 1)}
                >
                  <ArrowDown aria-hidden />
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  aria-label={`Remove segment ${index + 1}`}
                  onClick={() => onChange(segments.filter((_, i) => i !== index))}
                >
                  <Trash2 aria-hidden />
                </Button>
              </div>
            </div>
            <div className={styles.twoColumns}>
              <Select
                label="Kind"
                value={seg.kind}
                options={kinds}
                onChange={(kind) =>
                  kind &&
                  set(index, {
                    kind,
                    activityId: kind === 'activity' ? seg.activityId : null,
                    videoId: kind === 'video' ? seg.videoId : null,
                    refresherFor: kind === 'refresher' ? seg.refresherFor : null,
                  })
                }
              />
              <TextField
                label="Title"
                value={seg.title}
                maxLength={200}
                onChange={(e) => set(index, { title: e.target.value })}
              />
            </div>
            {seg.kind === 'activity' && (
              <div className={styles.row}>
                <Select
                  label="Activity"
                  value={seg.activityId ?? null}
                  options={activityOptions}
                  onChange={(activityId) => set(index, { activityId })}
                />
                {(seg.activityId ?? null) !== null && (
                  <Link to={`/staff/content/activities/${seg.activityId}`} className="text-primary">
                    Edit the activity
                  </Link>
                )}
              </div>
            )}
            {seg.kind === 'video' && (
              <Select
                label="Video"
                hint="Videos are uploaded on the Videos page. A video plays in one place only: choosing it here moves it."
                value={seg.videoId ?? null}
                options={videoOptions}
                none="No video yet"
                onChange={(videoId) => set(index, { videoId })}
              />
            )}
            {seg.kind === 'refresher' && (
              <TextField
                label="Diagnostic topic"
                hint="The module 0 diagnostic topic that decides whether a student sees this, e.g. queues."
                value={seg.refresherFor ?? ''}
                onChange={(e) => set(index, { refresherFor: e.target.value || null })}
              />
            )}
            {(seg.kind !== 'activity' || (seg.body ?? '') !== '') && (
              <TextArea
                label={seg.kind === 'activity' || seg.kind === 'video' ? 'Text (optional)' : 'Text'}
                hint="Markdown: **bold**, `code`, lists, and a blank line between paragraphs."
                rows={seg.kind === 'text' || seg.kind === 'worked_example' ? 8 : 4}
                value={seg.body ?? ''}
                onChange={(body) => set(index, { body })}
              />
            )}
            {props.allowSkipping && seg.kind !== 'video' && (
              <Select
                label="Skippable by passing (optional)"
                hint="A student who answers this activity correctly may skip the segment."
                value={seg.skipCheckActivityId ?? null}
                options={activityOptions}
                none="Not skippable"
                onChange={(skipCheckActivityId) => set(index, { skipCheckActivityId })}
              />
            )}
          </div>
        </Card>
      ))}
      <div>
        <Button variant="secondary" onClick={add}>
          <Plus aria-hidden />
          Add a segment
        </Button>
      </div>
    </div>
  )
}
