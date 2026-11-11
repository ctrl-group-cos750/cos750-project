import { useEffect, useRef, useState } from 'react'

export type Scrollable = {
  /** Content wider than the box: the box should be a named tab stop (WCAG 2.1.1). */
  scrollable: boolean
  /** Content hidden off the start or the end, for the visual scroll cue. */
  moreStart: boolean
  moreEnd: boolean
}

const NONE: Scrollable = { scrollable: false, moreStart: false, moreEnd: false }

/**
 * Whether an element's content is wider than the element, kept current as either resizes or
 * scrolls.
 *
 * A container that scrolls sideways must be reachable by keyboard (WCAG 2.1.1) and should be
 * named, but one that fits is neither a tab stop nor a landmark: extra tab stops and regions
 * that do nothing are noise for keyboard and screen-reader users. So a table or code block gets
 * `tabIndex` and a name only while this says it overflows.
 *
 * It never takes that away while the box, or something inside it, has focus: removing the
 * tabindex from the focused element would drop focus on the page (WCAG 2.4.3). It looks again
 * when focus leaves.
 *
 * Watches the element and its children with a ResizeObserver (a child grows when fonts load or
 * text changes, without the element changing size). Where ResizeObserver doesn't exist it
 * measures once.
 */
export function useScrollable<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [state, setState] = useState<Scrollable>(NONE)

  useEffect(() => {
    const element = ref.current
    if (!element) return
    const measure = () => {
      const overflow = element.scrollWidth > element.clientWidth + 1
      const hasFocus = element.contains(document.activeElement)
      setState((previous) => {
        const next: Scrollable = {
          scrollable: overflow || (previous.scrollable && hasFocus),
          moreStart: overflow && element.scrollLeft > 1,
          moreEnd: overflow && element.scrollLeft + element.clientWidth < element.scrollWidth - 1,
        }
        return next.scrollable === previous.scrollable &&
          next.moreStart === previous.moreStart &&
          next.moreEnd === previous.moreEnd
          ? previous
          : next
      })
    }
    // After focus has moved on (activeElement is only updated once focusout is over).
    const afterBlur = () => setTimeout(measure, 0)
    measure()
    element.addEventListener('scroll', measure, { passive: true })
    element.addEventListener('focusout', afterBlur)
    const observer = typeof ResizeObserver === 'undefined' ? undefined : new ResizeObserver(measure)
    observer?.observe(element)
    for (const child of element.children) observer?.observe(child)
    return () => {
      element.removeEventListener('scroll', measure)
      element.removeEventListener('focusout', afterBlur)
      observer?.disconnect()
    }
  }, [])

  return { ref, ...state }
}
