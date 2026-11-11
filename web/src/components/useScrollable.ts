import { useEffect, useRef, useState } from 'react'

/**
 * Whether an element's content is wider than the element, kept current as either resizes.
 *
 * A container that scrolls sideways must be reachable by keyboard (WCAG 2.1.1) and should be
 * named, but one that fits is neither a tab stop nor a landmark: extra tab stops and regions
 * that do nothing are noise for keyboard and screen-reader users. So a table or code block gets
 * `tabIndex` and a name only while this says it overflows (#142 review).
 *
 * Watches the element and its children with a ResizeObserver (a child grows when fonts load or
 * text changes, without the element changing size). Where ResizeObserver doesn't exist it
 * measures once.
 */
export function useScrollable<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [scrollable, setScrollable] = useState(false)

  useEffect(() => {
    const element = ref.current
    if (!element) return
    const measure = () => setScrollable(element.scrollWidth > element.clientWidth + 1)
    measure()
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    for (const child of element.children) observer.observe(child)
    return () => observer.disconnect()
  }, [])

  return { ref, scrollable }
}
