import { useEffect } from 'react'
import { useBackground, type Background } from '../features/progress/preferences.ts'

/** What each background is called in the profile and the header menu. */
export const BACKGROUND_LABELS: Record<Background, string> = {
  glow: 'Glow',
  doodles: 'Doodles',
  plain: 'Plain',
}

/** Whether the system asks for its own colours (Windows high contrast and similar). */
function forcedColours(): boolean {
  return (
    typeof window.matchMedia === 'function' && window.matchMedia('(forced-colors: active)').matches
  )
}

/**
 * Sets the attribute styles/backgrounds.css reads. Under forced colours the page is always plain:
 * the stylesheet hides the decoration there too, and this keeps the attribute honest. Print gets
 * the plain page from the stylesheet alone.
 */
export function applyBackground(input: { background: Background }): void {
  document.documentElement.dataset.bg = forcedColours() ? 'plain' : input.background
}

/** Keeps <html data-bg> on the signed-in student's background (SignedInLayout). */
export function useAppliedBackground(): void {
  const [background] = useBackground()
  useEffect(() => {
    applyBackground({ background })
    // Signed out (the log in page after Log out): the default again, not this student's choice.
    return () => applyBackground({ background: 'glow' })
  }, [background])
}
