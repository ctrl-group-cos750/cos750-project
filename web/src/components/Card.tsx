import type { HTMLAttributes } from 'react'
import styles from './Card.module.css'

export type CardProps = HTMLAttributes<HTMLDivElement> & {
  /** Interactive cards (a module on the map) lift on hover. */
  interactive?: boolean
}

export function Card({ interactive = false, className, ...rest }: CardProps) {
  const classes = [styles.card, interactive && styles.interactive, className]
    .filter(Boolean)
    .join(' ')
  return <div className={classes} {...rest} />
}
