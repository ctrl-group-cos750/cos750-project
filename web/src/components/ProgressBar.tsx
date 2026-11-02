import styles from './ProgressBar.module.css'

export type ProgressBarProps = {
  /** What is progressing, read by screen readers: "Module 3 progress". */
  label: string
  value: number
  max?: number
  /** Shows "3 of 7" next to the bar. */
  showCount?: boolean
}

export function ProgressBar({ label, value, max = 100, showCount = false }: ProgressBarProps) {
  const clamped = Math.min(Math.max(value, 0), max)
  return (
    <div className={styles.wrap}>
      <progress className={styles.bar} aria-label={label} value={clamped} max={max} />
      {showCount && (
        <span className={styles.count}>
          {clamped} of {max}
        </span>
      )}
    </div>
  )
}
