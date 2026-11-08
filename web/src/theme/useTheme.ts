import { useCallback, useState } from 'react'
import { applyTheme, initialTheme, storeTheme, type Theme } from './theme.ts'

/** The current theme and a way to flip it. The choice is applied at once and remembered. */
export function useTheme(): { theme: Theme; toggleTheme: () => void } {
  const [theme, setTheme] = useState<Theme>(() => initialTheme())

  const toggleTheme = useCallback(() => {
    const next: Theme = theme === 'dark' ? 'light' : 'dark'
    applyTheme({ theme: next })
    storeTheme({ theme: next })
    setTheme(next)
  }, [theme])

  return { theme, toggleTheme }
}
