import type { ButtonHTMLAttributes } from 'react'
import styles from './Button.module.css'
import { Spinner } from './Spinner.tsx'

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  /** primary: the one main action on a screen. secondary: everything else. */
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'md' | 'sm'
  /** Disables the button and shows a spinner while an action runs. */
  loading?: boolean
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled,
  type = 'button',
  className,
  children,
  ...rest
}: ButtonProps) {
  const classes = [styles.button, styles[variant], styles[size], className]
    .filter(Boolean)
    .join(' ')
  return (
    // Defaults to type="button" so a button inside a form never submits it by accident.
    // oxlint-disable-next-line react/button-has-type
    <button
      type={type}
      className={classes}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading && <Spinner size="sm" label="" />}
      {children}
    </button>
  )
}
