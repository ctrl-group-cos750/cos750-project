// The rules for a new password, shown as a checklist while the student types. The API checks the
// same rules (api/app/passwords.py) with the same messages; change both together.

export const MIN_PASSWORD = 8

type Check = (password: string, email: string, name: string) => boolean

export type PasswordRule = {
  key: string
  /** The checklist line: what the password needs. */
  label: string
  /** What to fix, when it's the first rule broken. */
  message: string
  passes: Check
}

const notPersonal: Check = (password, email, name) => {
  const lowered = password.toLowerCase()
  const words = [email.split('@')[0].toLowerCase(), ...name.toLowerCase().split(/\s+/)]
  return !words.some((word) => word.length >= 3 && lowered.includes(word))
}

export const passwordRules: PasswordRule[] = [
  {
    key: 'length',
    label: `At least ${MIN_PASSWORD} characters`,
    message: `Use at least ${MIN_PASSWORD} characters.`,
    passes: (p) => [...p].length >= MIN_PASSWORD,
  },
  {
    key: 'lower',
    label: 'A lowercase letter',
    message: 'Use at least one lowercase letter.',
    passes: (p) => /\p{Ll}/u.test(p),
  },
  {
    key: 'upper',
    label: 'An uppercase letter',
    message: 'Use at least one uppercase letter.',
    passes: (p) => /\p{Lu}/u.test(p),
  },
  {
    key: 'number',
    label: 'A number',
    message: 'Use at least one number.',
    passes: (p) => /\p{Nd}/u.test(p),
  },
  {
    key: 'symbol',
    label: 'A symbol, such as ! # or a space',
    message: 'Use at least one symbol, such as ! # or a space.',
    passes: (p) => /[^\p{L}\p{N}]/u.test(p),
  },
  {
    key: 'personal',
    label: 'Not your name or email',
    message: "Don't use your name or email in your password.",
    passes: notPersonal,
  },
]

/** The first rule the password breaks, or undefined when it follows them all. */
export function passwordProblem(password: string, email = '', name = ''): string | undefined {
  return passwordRules.find((rule) => !rule.passes(password, email, name))?.message
}
