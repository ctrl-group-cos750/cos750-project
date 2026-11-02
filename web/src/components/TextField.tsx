import { useId, type InputHTMLAttributes } from 'react'
import styles from './TextField.module.css'

export type TextFieldProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string
  /** Help shown under the field, e.g. password rules. */
  hint?: string
  /** Shown in place of the hint and marks the field invalid. */
  error?: string
}

export function TextField({ label, hint, error, id, className, ...rest }: TextFieldProps) {
  const generated = useId()
  const inputId = id ?? generated
  const messageId = `${inputId}-message`
  const message = error ?? hint

  return (
    <div className={[styles.field, className].filter(Boolean).join(' ')}>
      <label htmlFor={inputId} className={styles.label}>
        {label}
      </label>
      <input
        id={inputId}
        className={styles.input}
        aria-invalid={error ? true : undefined}
        aria-describedby={message ? messageId : undefined}
        {...rest}
      />
      {message && (
        <p id={messageId} className={error ? styles.error : styles.hint}>
          {message}
        </p>
      )}
    </div>
  )
}
