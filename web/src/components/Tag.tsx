import type { ReactNode } from 'react'
import styles from './Tag.module.css'

export type TagTone = 'neutral' | 'accent' | 'success' | 'warning' | 'danger'

export type TagProps = {
  tone?: TagTone
  /** A symbol before the text, so the meaning never relies on colour alone. */
  icon?: string
  children: ReactNode
}

/** A short inline status, e.g. a module's state or an objective's result. Not a heading label. */
export function Tag({ tone = 'neutral', icon, children }: TagProps) {
  return (
    <span className={`${styles.tag} ${styles[tone]}`}>
      {icon && <span aria-hidden="true">{icon}</span>}
      {children}
    </span>
  )
}
