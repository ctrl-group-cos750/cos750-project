import type { ButtonHTMLAttributes } from 'react'
import styles from './Button.module.css'
import { Spinner } from './Spinner.tsx'

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  /** primary: the one main action on a screen. secondary: everything else. */
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'md' | 'sm'
  /** Disables the button and shows a spinner while an action runs. */
  loading?: boolean
  /**
   * While `loading`, keep the button focusable instead of disabling it: it is marked
   * `aria-disabled` and `aria-busy`, shows the spinner, and ignores presses (a click, Enter,
   * Space, and a form's implicit submit, which clicks its submit button). A disabled button
   * drops keyboard focus on the page (WCAG 2.4.3), so use this where the student presses the
   * button with the keyboard and stays there: Check answer, a module's Next and Previous.
   * Off by default, so other forms are unchanged.
   */
  keepFocusWhileLoading?: boolean
}

export function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  keepFocusWhileLoading = false,
  disabled,
  onClick,
  type = 'button',
  className,
  children,
  ...rest
}: ButtonProps) {
  const classes = [styles.button, styles[variant], styles[size], className]
    .filter(Boolean)
    .join(' ')
  const busyButFocusable = loading && keepFocusWhileLoading
  return (
    // Defaults to type="button" so a button inside a form never submits it by accident.
    // oxlint-disable-next-line react/button-has-type
    <button
      type={type}
      className={classes}
      disabled={disabled || (loading && !keepFocusWhileLoading)}
      aria-busy={loading || undefined}
      {...rest}
      aria-disabled={busyButFocusable || rest['aria-disabled'] || undefined}
      onClick={(event) => {
        if (busyButFocusable) {
          event.preventDefault() // also stops a submit button submitting its form
          return
        }
        onClick?.(event)
      }}
    >
      {loading && <Spinner size="sm" label="" />}
      {children}
    </button>
  )
}
