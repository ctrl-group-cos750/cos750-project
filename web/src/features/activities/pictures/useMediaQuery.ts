import { useEffect, useState } from 'react'

/** True while a media query matches; false where matchMedia doesn't exist (tests). */
export function useMediaQuery(query: string): boolean {
  const get = () => typeof window.matchMedia === 'function' && window.matchMedia(query).matches
  const [matches, setMatches] = useState(get)
  useEffect(() => {
    if (typeof window.matchMedia !== 'function') return
    const list = window.matchMedia(query)
    const update = () => setMatches(list.matches)
    update()
    list.addEventListener('change', update)
    return () => list.removeEventListener('change', update)
  }, [query])
  return matches
}

/** Phones: labels in drawings are larger, so they stay readable at 320 px. */
export const PHONE = '(max-width: 480px)'
/** From about 1100 px a question with a picture is two columns. */
export const WIDE = '(min-width: 1100px)'
