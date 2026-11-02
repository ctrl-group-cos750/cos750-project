import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router'
import { Alert, Button, TextField } from '../components'
import { AuthLayout } from './AuthLayout.tsx'
import styles from './AuthLayout.module.css'
import type { FromState } from './guards.tsx'
import { useLogin } from './hooks.ts'
import { emailError, focusFirstError, type FieldErrors } from './validation.ts'

type Field = 'email' | 'password'
const ids: Record<Field, string> = { email: 'login-email', password: 'login-password' }

export function LoginPage() {
  const navigate = useNavigate()
  const from = (useLocation().state as FromState)?.from ?? '/'
  const login = useLogin()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<FieldErrors<Field>>({})

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    const found: FieldErrors<Field> = {
      email: emailError(email),
      password: password ? undefined : 'Enter your password.',
    }
    setErrors(found)
    if (found.email || found.password) {
      focusFirstError(['email', 'password'], found, ids)
      return
    }
    login.mutate(
      { email: email.trim(), password },
      { onSuccess: () => void navigate(from, { replace: true }) },
    )
  }

  return (
    <AuthLayout
      title="Log in"
      intro="Pick up where you left off."
      footer={
        <>
          New here? <Link to="/register">Create an account</Link>
        </>
      }
    >
      {login.error && <Alert tone="danger">{login.error.message}</Alert>}
      <form onSubmit={onSubmit} noValidate className={styles.form}>
        <TextField
          id={ids.email}
          label="Email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={errors.email}
        />
        <TextField
          id={ids.password}
          label="Password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={errors.password}
        />
        <Button type="submit" loading={login.isPending}>
          Log in
        </Button>
      </form>
    </AuthLayout>
  )
}
