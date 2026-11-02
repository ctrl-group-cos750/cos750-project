import { describe, expect, it } from 'vitest'
import { passwordProblem, passwordRules } from './passwordRules.ts'

const message = (key: string) => passwordRules.find((r) => r.key === key)?.message

describe('password rules (the same as api/app/passwords.py)', () => {
  it.each([
    ['Ab1!', 'length'],
    ['ABCDEF1!', 'lower'],
    ['abcdef1!', 'upper'],
    ['Abcdefg!', 'number'],
    ['Abcdefg1', 'symbol'],
  ])('%s breaks the %s rule', (password, key) => {
    expect(passwordProblem(password)).toBe(message(key))
  })

  it.each([
    ['Grace-2024-x', 'grace@example.com', ''],
    ['I am Hopper 1!', 'x@example.com', 'Grace Hopper'],
    ['My ada pw 9!', 'ada@example.com', 'Ada'],
  ])('%s is too personal', (password, email, name) => {
    expect(passwordProblem(password, email, name)).toBe(message('personal'))
  })

  it.each(['Correct horse 1', 'Violet otter 41', 'Tr0ub4dor&3', 'Äpfel und Birnen 7'])(
    'accepts %s',
    (password) => {
      expect(passwordProblem(password, 'student@example.com', 'Sam Student')).toBeUndefined()
    },
  )

  it('counts characters, not UTF-16 units, for the length', () => {
    expect(passwordProblem('Aa1!🙂🙂🙂')).toBe(message('length'))
  })
})
