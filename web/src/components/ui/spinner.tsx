import { cn } from 'cn'

type SpinnerProps = {
  size?: 'sm' | 'md'
  /** What is loading, for screen readers. Pass "" when the surrounding control already says it. */
  label?: string
  className?: string
}

/** A loading indicator. With a label it is announced as a status, without moving focus. */
function Spinner({ size = 'md', label = 'Loading', className }: SpinnerProps) {
  const spinner = (
    <span
      data-slot="spinner"
      aria-hidden="true"
      className={cn(
        'inline-block shrink-0 animate-spin rounded-full border-2 border-current border-r-transparent align-middle',
        size === 'sm' ? 'size-3.5' : 'size-6 text-primary',
        className,
      )}
    />
  )
  if (!label) return spinner
  return (
    <output className="inline-flex items-center gap-2">
      {spinner}
      <span className="visually-hidden">{label}</span>
    </output>
  )
}

export { Spinner, type SpinnerProps }
