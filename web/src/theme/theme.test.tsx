import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ThemeToggle } from './ThemeToggle.tsx'
import { applyTheme, initialTheme } from './theme.ts'

function preferDark(dark: boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn((query: string) => ({ matches: dark && query.includes('dark'), media: query })),
  )
}

beforeEach(() => {
  window.localStorage.clear()
  delete document.documentElement.dataset.theme
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('theme', () => {
  it('follows the operating system until the student chooses', () => {
    preferDark(true)
    expect(initialTheme()).toBe('dark')
    preferDark(false)
    expect(initialTheme()).toBe('light')
  })

  it('prefers the saved choice over the operating system', () => {
    preferDark(true)
    window.localStorage.setItem('ctrl-academy-theme', 'light')
    expect(initialTheme()).toBe('light')
  })

  it('ignores a saved value it does not know', () => {
    preferDark(false)
    window.localStorage.setItem('ctrl-academy-theme', 'purple')
    expect(initialTheme()).toBe('light')
  })

  it('sets the attribute the stylesheets use', () => {
    applyTheme({ theme: 'dark' })
    expect(document.documentElement.dataset.theme).toBe('dark')
  })
})

describe('ThemeToggle', () => {
  it('switches the app to dark and back, and remembers the choice', async () => {
    preferDark(false)
    render(<ThemeToggle />)
    const toggle = screen.getByRole('button', { name: 'Dark mode' })
    expect(toggle).toHaveAttribute('aria-pressed', 'false')

    await userEvent.click(toggle)
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(toggle).toHaveAttribute('aria-pressed', 'true')
    expect(window.localStorage.getItem('ctrl-academy-theme')).toBe('dark')

    await userEvent.click(toggle)
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(window.localStorage.getItem('ctrl-academy-theme')).toBe('light')
  })

  it('starts pressed when dark mode was saved', () => {
    window.localStorage.setItem('ctrl-academy-theme', 'dark')
    render(<ThemeToggle />)
    expect(screen.getByRole('button', { name: 'Dark mode' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })
})
