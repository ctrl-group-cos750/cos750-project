import type { ReactNode } from 'react'
import styles from './ScrollRegion.module.css'
import { useScrollable } from './useScrollable.ts'

export type ScrollRegionProps = {
  /** The region's name while it scrolls, e.g. "Table: Step, Queue" or "Code: class Graph:". Make
   * it unique on the page. */
  label: string
  /** Classes for the scrolling box (its border, padding, font). */
  className?: string
  children: ReactNode
}

/**
 * A box that scrolls sideways when its content (a table, a code block) is wider than the screen,
 * so the page itself never does (WCAG 1.4.10 lets two-dimensional content scroll).
 *
 * - Only while it overflows is it a named region and a tab stop, so a keyboard user can scroll it
 *   with the arrow keys (2.1.1); a box that fits adds no tab stop and no landmark. It keeps both
 *   while focus is inside it (useScrollable).
 * - A soft shade on the edge where more content is hidden shows sighted users that it scrolls. It
 *   is drawn in the text colour, so it works in light and dark.
 */
export function ScrollRegion({ label, className, children }: ScrollRegionProps) {
  const { ref, scrollable, moreStart, moreEnd } = useScrollable<HTMLElement>()
  return (
    <div
      className={styles.frame}
      data-more-start={moreStart || undefined}
      data-more-end={moreEnd || undefined}
    >
      <section
        ref={ref}
        className={[styles.scroller, className].filter(Boolean).join(' ')}
        // An unnamed section is not a region landmark; it becomes one only while it scrolls.
        aria-label={scrollable ? label : undefined}
        // oxlint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- a scroll container must be reachable by keyboard (WCAG 2.1.1)
        tabIndex={scrollable ? 0 : undefined}
      >
        {children}
      </section>
    </div>
  )
}
