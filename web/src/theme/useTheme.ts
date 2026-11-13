import { useCallback, useState } from 'react'
import { applyTheme, initialTheme, storeTheme, type Theme } from './theme.ts'

/** The current theme and ways to flip or choose it. The choice is applied at once and
 * remembered. */
export function useTheme(): {
  theme: Theme
  toggleTheme: () => void
  chooseTheme: (theme: Theme) => void
} {
  const [theme, setTheme] = useState<Theme>(() => initialTheme())

  const chooseTheme = useCallback((next: Theme) => {
    applyTheme({ theme: next })
    storeTheme({ theme: next })
    setTheme(next)
  }, [])

  const toggleTheme = useCallback(
    () => chooseTheme(theme === 'dark' ? 'light' : 'dark'),
    [theme, chooseTheme],
  )

  return { theme, toggleTheme, chooseTheme }
}
