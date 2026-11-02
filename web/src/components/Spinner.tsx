import styles from './Spinner.module.css'

export type SpinnerProps = {
  size?: 'sm' | 'md'
  /** What is loading, for screen readers. Pass "" when the surrounding control already says it. */
  label?: string
}

export function Spinner({ size = 'md', label = 'Loading' }: SpinnerProps) {
  const spinner = <span className={`${styles.spinner} ${styles[size]}`} aria-hidden="true" />
  if (!label) return spinner
  // <output> is announced as a status, so screen readers say the label without moving focus.
  return (
    <output>
      {spinner}
      <span className="visually-hidden">{label}</span>
    </output>
  )
}
