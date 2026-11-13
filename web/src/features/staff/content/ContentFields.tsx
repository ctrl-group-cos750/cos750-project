import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useId, type ReactNode, type Ref } from 'react'
import { ApiError } from '../../../api/client.ts'
import { Alert, Button, Tag } from '../../../components'
import styles from '../staff.module.css'
import { restoreRepositoryVersion, type ItemKind } from './content.api.ts'

/** The form pieces every content editor page shares. */

export function TextArea({
  inputRef,
  ...props
}: {
  label: string
  hint?: string
  value: string
  rows?: number
  monospace?: boolean
  /** What is wrong with the value: shown under it, tied to it (aria-describedby), and the field
   * marked aria-invalid. */
  error?: string
  inputRef?: Ref<HTMLTextAreaElement>
  onChange: (value: string) => void
}) {
  const id = useId()
  const errorId = `${id}-error`
  return (
    <div className={styles.field}>
      <label htmlFor={id} className={styles.label}>
        {props.label}
      </label>
      <textarea
        ref={inputRef}
        id={id}
        className={styles.textarea}
        style={props.monospace ? { fontFamily: 'var(--font-mono)' } : undefined}
        rows={props.rows ?? 4}
        value={props.value}
        spellCheck={!props.monospace}
        aria-invalid={props.error ? true : undefined}
        aria-describedby={props.error ? errorId : undefined}
        onChange={(e) => props.onChange(e.target.value)}
      />
      {props.error && (
        <p id={errorId} className="text-sm text-destructive">
          {props.error}
        </p>
      )}
      {props.hint && <p className={styles.muted}>{props.hint}</p>}
    </div>
  )
}

export function Select<T extends string | number>(props: {
  label: string
  hint?: string
  value: T | null
  options: { value: T; label: string }[]
  /** Shown as the first choice and means "none" (null). Leave out when a value is required. */
  none?: string
  onChange: (value: T | null) => void
}) {
  const id = useId()
  const index = props.options.findIndex((o) => o.value === props.value)
  return (
    <div className={styles.field}>
      <label htmlFor={id} className={styles.label}>
        {props.label}
      </label>
      <select
        id={id}
        className={styles.input}
        value={index === -1 ? '' : String(index)}
        onChange={(e) =>
          props.onChange(e.target.value === '' ? null : props.options[Number(e.target.value)].value)
        }
      >
        {(props.none !== undefined || index === -1) && <option value="">{props.none ?? ''}</option>}
        {props.options.map((o, i) => (
          <option key={String(o.value)} value={String(i)}>
            {o.label}
          </option>
        ))}
      </select>
      {props.hint && <p className={styles.muted}>{props.hint}</p>}
    </div>
  )
}

/** Where the item's current version comes from, with "Use the repository's version" when the
 * portal has changed one the repository also has. */
export function Provenance(props: {
  kind: ItemKind
  id: number | undefined
  edited: boolean
  inRepository: boolean
  /** Called after the repository's version is loaded, to reload the page's data. */
  onRestored: () => void
}) {
  const queryClient = useQueryClient()
  const restore = useMutation({
    mutationFn: () => restoreRepositoryVersion(props.kind, props.id!),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['staff', 'content'] })
      props.onRestored()
    },
  })
  if (props.id === undefined) return null
  return (
    <div className={styles.row}>
      {props.edited ? (
        <Tag tone="warning">Edited in the portal</Tag>
      ) : (
        <Tag tone="neutral">As in the repository</Tag>
      )}
      {!props.inRepository && <Tag tone="accent">Made in the portal</Tag>}
      {props.edited && props.inRepository && (
        <Button
          variant="secondary"
          loading={restore.isPending}
          onClick={() => {
            if (
              window.confirm(
                "Throw away the portal's changes to this and use the repository's version?",
              )
            )
              restore.mutate()
          }}
        >
          Use the repository&apos;s version
        </Button>
      )}
      {restore.isError && <span className="text-destructive">{restore.error.message}</span>}
    </div>
  )
}

/** The sticky bar at the bottom of an editor: save, and what happened. */
export function SaveBar(props: {
  label: string
  pending: boolean
  dirty: boolean
  saved: boolean
  error: Error | null
  onSave: () => void
  children?: ReactNode
}) {
  return (
    <>
      <div className={styles.saveBar}>
        <Button loading={props.pending} onClick={props.onSave}>
          {props.label}
        </Button>
        {props.children}
        {/* Always on the page, so a screen reader hears "Saved." when it appears (WCAG 4.1.3). */}
        <output className={styles.muted}>
          {props.dirty && !props.pending
            ? 'Unsaved changes'
            : props.saved && !props.dirty
              ? 'Saved.'
              : ''}
        </output>
      </div>
      {props.error && (
        <Alert tone="danger" title="Not saved">
          <ErrorText error={props.error} />
        </Alert>
      )}
    </>
  )
}

/** The note every editor page starts with: what saving does. */
export function SeedNote() {
  return (
    <p className={styles.muted}>
      Changes go live for students as soon as you save. Once saved here, the next deploy keeps your
      version instead of the repository&apos;s.
    </p>
  )
}

/** An API refusal: the content rule it broke, or each field the request got wrong. */
function ErrorText({ error }: { error: Error }) {
  const fields = error instanceof ApiError ? Object.entries(error.fields) : []
  if (fields.length === 0) return <p style={{ whiteSpace: 'pre-line' }}>{error.message}</p>
  return (
    <ul>
      {fields.map(([field, message]) => (
        <li key={field}>
          {field}: {message}
        </li>
      ))}
    </ul>
  )
}
