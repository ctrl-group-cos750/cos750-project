import { cn } from 'cn'

type ProgressProps = {
  /** What is progressing, read by screen readers: "Module 3 progress". */
  label: string
  value: number
  max?: number
  /** Shows "3 of 7" next to the bar. */
  showCount?: boolean
  className?: string
}

/** A progress bar on the native <progress> element, so screen readers announce it as one. */
function Progress({ label, value, max = 100, showCount = false, className }: ProgressProps) {
  const clamped = Math.min(Math.max(value, 0), max)
  return (
    <div data-slot="progress" className={cn('flex items-center gap-3', className)}>
      <progress
        aria-label={label}
        value={clamped}
        max={max}
        className="h-2 w-full flex-1 appearance-none overflow-hidden rounded-full bg-muted [&::-moz-progress-bar]:bg-primary [&::-webkit-progress-bar]:bg-muted [&::-webkit-progress-value]:rounded-full [&::-webkit-progress-value]:bg-primary"
      />
      {showCount && (
        <span className="text-sm whitespace-nowrap text-muted-foreground tabular-nums">
          {clamped} of {max}
        </span>
      )}
    </div>
  )
}

export { Progress, type ProgressProps }
