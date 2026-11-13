import type { Background } from '../features/progress/preferences.ts'
import styles from './BackgroundSwatch.module.css'

/** A small picture of a page background, beside its radio (the profile and the header menu). */
export function BackgroundSwatch({
  background,
  small = false,
}: {
  background: Background
  small?: boolean
}) {
  const classes = [
    styles.swatch,
    small && styles.small,
    background !== 'plain' && styles[background],
  ]
    .filter(Boolean)
    .join(' ')
  return <span aria-hidden="true" className={classes} data-swatch={background} />
}
