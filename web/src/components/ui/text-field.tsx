import { useId, type ComponentProps } from 'react'
import { cn } from 'cn'

import { Input } from './input'
import { Label } from './label'

type TextFieldProps = ComponentProps<'input'> & {
  label: string
  /** Help shown under the field, e.g. password rules. */
  hint?: string
  /** Shown in place of the hint and marks the field invalid. */
  error?: string
}

/** A labelled input with its hint or error linked for screen readers. */
function TextField({ label, hint, error, id, className, ...props }: TextFieldProps) {
  const generated = useId()
  const inputId = id ?? generated
  const messageId = `${inputId}-message`
  const message = error ?? hint

  return (
    <div data-slot="text-field" className={cn('grid gap-1.5', className)}>
      <Label htmlFor={inputId}>{label}</Label>
      <Input
        id={inputId}
        aria-invalid={error ? true : undefined}
        aria-describedby={message ? messageId : undefined}
        {...props}
      />
      {message && (
        <p
          id={messageId}
          className={cn('m-0 text-sm', error ? 'text-destructive' : 'text-muted-foreground')}
        >
          {message}
        </p>
      )}
    </div>
  )
}

export { TextField, type TextFieldProps }
