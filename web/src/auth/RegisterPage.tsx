import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { ApiError } from '../api/client.ts'
import { Alert, Button, TextField } from '../components'
import { AuthLayout } from './AuthLayout.tsx'
import styles from './AuthLayout.module.css'
import { useRegister } from './hooks.ts'
import {
  displayNameError,
  emailError,
  focusFirstError,
  MIN_PASSWORD,
  newPasswordError,
  type FieldErrors,
} from './validation.ts'

type Field = 'displayName' | 'email' | 'password'
const order: Field[] = ['displayName', 'email', 'password']
const ids: Record<Field, string> = {
  displayName: 'register-name',
  email: 'register-email',
  password: 'register-password',
}

export function RegisterPage() {
  const navigate = useNavigate()
  const register = useRegister()
  const [values, setValues] = useState<Record<Field, string>>({
    displayName: '',
    email: '',
    password: '',
  })
  const [errors, setErrors] = useState<FieldErrors<Field>>({})

  const set = (field: Field) => (e: { target: { value: string } }) =>
    setValues((v) => ({ ...v, [field]: e.target.value }))

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    const found: FieldErrors<Field> = {
      displayName: displayNameError(values.displayName),
      email: emailError(values.email),
      password: newPasswordError(values.password),
    }
    setErrors(found)
    if (order.some((field) => found[field])) {
      focusFirstError(order, found, ids)
      return
    }
    register.mutate(
      {
        displayName: values.displayName.trim(),
        email: values.email.trim(),
        password: values.password,
      },
      {
        onSuccess: () => void navigate('/', { replace: true }),
        onError: (error) => {
          // A taken email belongs next to the email field, not in a general alert.
          if (error instanceof ApiError && error.status === 409) {
            setErrors({ email: error.message })
            focusFirstError(order, { email: error.message }, ids)
          }
        },
      },
    )
  }

  const generalError =
    register.error && !(register.error instanceof ApiError && register.error.status === 409)
      ? register.error.message
      : undefined

  return (
    <AuthLayout
      title="Create your account"
      intro="About 75 minutes of graphs and breadth-first search, at your own pace, before the lecture."
      footer={
        <>
          Already have an account? <Link to="/login">Log in</Link>
        </>
      }
    >
      {generalError && <Alert tone="danger">{generalError}</Alert>}
      <form onSubmit={onSubmit} noValidate className={styles.form}>
        <TextField
          id={ids.displayName}
          label="Your name"
          autoComplete="nickname"
          hint="Only you see this."
          value={values.displayName}
          onChange={set('displayName')}
          error={errors.displayName}
        />
        <TextField
          id={ids.email}
          label="Email"
          type="email"
          autoComplete="email"
          value={values.email}
          onChange={set('email')}
          error={errors.email}
        />
        <TextField
          id={ids.password}
          label="Password"
          type="password"
          autoComplete="new-password"
          hint={`At least ${MIN_PASSWORD} characters.`}
          value={values.password}
          onChange={set('password')}
          error={errors.password}
        />
        <section aria-label="What we keep" className={styles.notice}>
          <p>
            <strong>What we keep and why.</strong> Your email, to log you in. Your name, to greet
            you. What you do in the course, to save your progress and to see whether the app helps
            students learn.
          </p>
          <p>
            Nobody else sees your progress. When the team studies the results, you are a number, not
            a name or an email.
          </p>
        </section>
        <Button type="submit" loading={register.isPending}>
          Create account
        </Button>
      </form>
    </AuthLayout>
  )
}
