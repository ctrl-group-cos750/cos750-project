import { Button as ButtonPrimitive } from '@base-ui/react/button'
import { type VariantProps } from 'class-variance-authority'
import { cn } from 'cn'

import { buttonVariants } from './button-variants'
import { Spinner } from './spinner'

type ButtonProps = ButtonPrimitive.Props &
  VariantProps<typeof buttonVariants> & {
    /** Disables the button and shows a spinner while an action runs. */
    loading?: boolean
  }

/**
 * default: the one main action on a screen. outline or secondary: everything else. ghost: quiet
 * actions such as navigation. destructive: deleting something. A plain button unless `type` says
 * otherwise, so a button inside a form never submits it by accident.
 */
function Button({
  className,
  variant = 'default',
  size = 'default',
  loading = false,
  disabled,
  type = 'button',
  children,
  ...props
}: ButtonProps) {
  return (
    <ButtonPrimitive
      data-slot="button"
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    >
      {loading && <Spinner size="sm" label="" />}
      {children}
    </ButtonPrimitive>
  )
}

export { Button, type ButtonProps }
