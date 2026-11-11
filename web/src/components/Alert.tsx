import { useId, type ReactNode, type Ref } from 'react'
import styles from './Alert.module.css'

export type AlertTone = 'info' | 'success' | 'warning' | 'danger'

const icons: Record<AlertTone, string> = { info: 'i', success: '✓', warning: '!', danger: '×' }

export type AlertProps = {
  tone?: AlertTone
  title?: string
  children: ReactNode
  /**
   * How a screen reader learns about the alert.
   * - `live` (default): a live region (`role="status"`, or `role="alert"` for danger), read
   *   when it appears or changes.
   * - `focus`: the caller moves focus to it instead. It is then a group named by its title and
   *   described by its text, focusable from script only, and not live: being live as well would
   *   read it twice when it changes in place (#142 review). When the text already starts with
   *   the title ("Not quite. …" under "Not quite"), the text alone names it, so the title isn't
   *   read twice.
   */
  announce?: 'live' | 'focus'
  /** The alert's root element, e.g. to focus it when `announce` is `focus`. */
  ref?: Ref<HTMLDivElement>
}

/** Feedback after an action. Danger alerts interrupt screen readers; the rest wait their turn. */
export function Alert({ tone = 'info', title, children, announce = 'live', ref }: AlertProps) {
  const id = useId()
  const focus = announce === 'focus'
  // "Not quite" + "Not quite. Q must also list P." would read the title twice.
  const textRepeatsTitle =
    typeof children === 'string' &&
    !!title &&
    children.trimStart().toLowerCase().startsWith(title.toLowerCase())
  const labelledBy = !focus ? undefined : textRepeatsTitle || !title ? `${id}-body` : `${id}-title`
  return (
    <div
      ref={ref}
      className={`${styles.alert} ${styles[tone]}`}
      // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role -- a fieldset would add form semantics; this is a named group of text
      role={focus ? 'group' : tone === 'danger' ? 'alert' : 'status'}
      aria-labelledby={labelledBy}
      aria-describedby={focus && labelledBy !== `${id}-body` ? `${id}-body` : undefined}
      tabIndex={focus ? -1 : undefined}
    >
      <span className={styles.icon} aria-hidden="true">
        {icons[tone]}
      </span>
      <div className={styles.content}>
        {title && (
          <p id={`${id}-title`} className={styles.title}>
            {title}
          </p>
        )}
        <div id={`${id}-body`} className={styles.body}>
          {children}
        </div>
      </div>
    </div>
  )
}
