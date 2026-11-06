import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { ApiError } from '../api/client.ts'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { TextField } from '@/components/ui/text-field'
import { AuthLayout } from './AuthLayout.tsx'
import { PasswordChecklist } from './PasswordChecklist.tsx'
import { useRegister } from './hooks.ts'
import {
  displayNameError,
  emailError,
  focusFirstError,
  newPasswordError,
  type FieldErrors,
} from './validation.ts'

type Field = 'displayName' | 'email' | 'password'
const order: Field[] = ['displayName', 'email', 'password']
const rulesId = 'register-password-rules'
const ids: Record<Field, string> = {
  displayName: 'register-name',
  email: 'register-email',
  password: 'register-password',
}

/** The API's complaints that belong to one of this form's fields, or null if there are none. */
function fieldProblems(error: Error): FieldErrors<Field> | null {
  if (!(error instanceof ApiError)) return null
  if (error.status === 409) return { email: error.message }
  const found: FieldErrors<Field> = {}
  for (const field of order) if (error.fields[field]) found[field] = error.fields[field]
  return Object.keys(found).length ? found : null
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
      password: newPasswordError(values.password, values.email.trim(), values.displayName.trim()),
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
          // A taken email, or a password the API finds too easy to guess, belongs next to its
          // field, not in a general alert.
          const problems = fieldProblems(error)
          if (problems) {
            setErrors(problems)
            focusFirstError(order, problems, ids)
          }
        },
      },
    )
  }

  const generalError =
    register.error && !fieldProblems(register.error) ? register.error.message : undefined

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
      {generalError && (
        <Alert variant="destructive" className="mb-4">
          <AlertDescription>{generalError}</AlertDescription>
        </Alert>
      )}
      <form onSubmit={onSubmit} noValidate className="grid gap-4">
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
          value={values.password}
          onChange={set('password')}
          error={errors.password}
          aria-describedby={errors.password ? `${ids.password}-message ${rulesId}` : rulesId}
        />
        <PasswordChecklist
          id={rulesId}
          password={values.password}
          email={values.email.trim()}
          name={values.displayName.trim()}
        />
        <Button type="submit" size="lg" className="w-full" loading={register.isPending}>
          Create account
        </Button>
      </form>
    </AuthLayout>
  )
}
