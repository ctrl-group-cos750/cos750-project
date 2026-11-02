import type { ReactNode } from 'react'
import styles from './Alert.module.css'

export type AlertTone = 'info' | 'success' | 'warning' | 'danger'

const icons: Record<AlertTone, string> = { info: 'i', success: '✓', warning: '!', danger: '×' }

export type AlertProps = {
  tone?: AlertTone
  title?: string
  children: ReactNode
}

/** Feedback after an action. Danger alerts interrupt screen readers; the rest wait their turn. */
export function Alert({ tone = 'info', title, children }: AlertProps) {
  return (
    <div
      className={`${styles.alert} ${styles[tone]}`}
      role={tone === 'danger' ? 'alert' : 'status'}
    >
      <span className={styles.icon} aria-hidden="true">
        {icons[tone]}
      </span>
      <div>
        {title && <p className={styles.title}>{title}</p>}
        <div className={styles.body}>{children}</div>
      </div>
    </div>
  )
}
