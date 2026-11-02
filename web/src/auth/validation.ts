// Checks in the browser, so students see a clear message before anything is sent.
// The API checks everything again (SE document NFR-S4).

export type FieldErrors<K extends string> = Partial<Record<K, string>>

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function emailError(email: string): string | undefined {
  if (!email.trim()) return 'Enter your email address.'
  if (!EMAIL.test(email.trim())) return 'Enter an email address like name@tuks.co.za.'
  return undefined
}

export const MIN_PASSWORD = 8

export function newPasswordError(password: string): string | undefined {
  if (!password) return 'Choose a password.'
  if (password.length < MIN_PASSWORD) return `Use at least ${MIN_PASSWORD} characters.`
  if (password.length > 128) return 'Use at most 128 characters.'
  return undefined
}

export function displayNameError(name: string): string | undefined {
  if (!name.trim()) return 'Enter the name you want to see in the app.'
  if (name.trim().length > 50) return 'Use at most 50 characters.'
  // Control and invisible characters (NUL, newline, zero-width, right-to-left override): the API
  // refuses them too, because they can crash the database or make one name look like another.
  if (/[\p{Cc}\p{Cf}]/u.test(name)) return 'Use letters, numbers, spaces and punctuation only.'
  return undefined
}

/** Moves focus to the first field with an error, so keyboard and screen reader users land on it. */
export function focusFirstError<K extends string>(
  order: K[],
  errors: FieldErrors<K>,
  ids: Record<K, string>,
) {
  const first = order.find((field) => errors[field])
  if (first) document.getElementById(ids[first])?.focus()
}
