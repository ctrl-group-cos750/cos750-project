/**
 * Where focus goes when the control that had it disappears (a dismissed note, a closed dialog,
 * a deleted row): the element given, if it is still on the page, otherwise the page's h1, and
 * failing that <main>. Never <body>, where a keyboard or screen-reader user is lost (WCAG 2.4.3).
 */
export function focusSafely(preferred?: Element | null) {
  if (preferred instanceof HTMLElement && preferred.isConnected && preferred !== document.body) {
    preferred.focus()
    if (document.activeElement === preferred) return
  }
  const target =
    document.querySelector<HTMLElement>('main h1') ?? document.querySelector<HTMLElement>('main')
  if (!target) return
  if (!target.hasAttribute('tabindex')) target.tabIndex = -1
  target.focus()
}

/** The focused element, or null when nothing is (focus on <body>). */
export function focusedElement(): HTMLElement | null {
  const active = document.activeElement
  return active instanceof HTMLElement && active !== document.body ? active : null
}
