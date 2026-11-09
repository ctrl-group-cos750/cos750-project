export type Theme = 'light' | 'dark'

const storageKey = 'ctrl-academy-theme'

function isTheme(value: unknown): value is Theme {
  return value === 'light' || value === 'dark'
}

/** The theme the student chose last time, or null if they never chose (or storage is blocked). */
export function readStoredTheme(): Theme | null {
  try {
    const stored = window.localStorage.getItem(storageKey)
    return isTheme(stored) ? stored : null
  } catch {
    return null
  }
}

export function storeTheme(input: { theme: Theme }) {
  try {
    window.localStorage.setItem(storageKey, input.theme)
  } catch {
    // Private mode or blocked storage: the choice just lasts until the page is closed.
  }
}

/** What the operating system prefers; light where the browser cannot say. */
export function systemTheme(): Theme {
  if (typeof window.matchMedia !== 'function') return 'light'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function initialTheme(): Theme {
  return readStoredTheme() ?? systemTheme()
}

/**
 * Switches the whole app. tokens.css and global.css key their dark values on
 * :root[data-theme='dark'] (the UI kit uses the same attribute), so that is all that is set.
 */
export function applyTheme(input: { theme: Theme }) {
  document.documentElement.dataset.theme = input.theme
}
