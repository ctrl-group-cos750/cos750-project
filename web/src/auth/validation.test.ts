import { describe, expect, it } from 'vitest'
import { displayNameError } from './validation.ts'

const char = (code: number) => String.fromCodePoint(code)

describe('displayNameError', () => {
  it.each([
    ['NUL', `Ada${char(0)}`],
    ['newline', `Ada${char(10)}Admin`],
    ['zero-width space', `A${char(0x200b)}da`],
    ['right-to-left override', `Ada${char(0x202e)}gnp.exe`],
  ])('refuses a hidden %s', (_case, name) => {
    expect(displayNameError(name)).toBe('Use letters, numbers, spaces and punctuation only.')
  })

  it.each(["Zoë O'Brien-Nkosi", '李小龍', 'Ada 🙂'])('accepts %s', (name) => {
    expect(displayNameError(name)).toBeUndefined()
  })
})
