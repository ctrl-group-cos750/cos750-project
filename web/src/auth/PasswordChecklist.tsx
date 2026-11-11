import { passwordRules } from './passwordRules.ts'
import styles from './PasswordChecklist.module.css'

/**
 * What a new password needs, ticked off as the student types. Each line says "done" or "still
 * needed" in words for screen readers, and shows a symbol as well as a colour.
 */
export function PasswordChecklist({
  id,
  password,
  email,
  name,
}: {
  id: string
  password: string
  email: string
  name: string
}) {
  return (
    <ul id={id} className={styles.list} aria-label="Your password needs">
      {passwordRules.map((rule) => {
        // "Not your name" is only meaningful once there is a password to check.
        const done = password.length > 0 && rule.passes(password, email, name)
        return (
          <li key={rule.key} className={done ? styles.done : styles.todo}>
            <span aria-hidden="true" className={styles.mark}>
              {done ? '✓' : '○'}
            </span>
            {rule.label}
            <span className="visually-hidden">{done ? ', done' : ', still needed'}</span>
          </li>
        )
      })}
    </ul>
  )
}
