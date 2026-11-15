import type { ElementType } from 'react'
import { HideMenu, type HideItem } from './HideMenu.tsx'
import styles from './hiding.module.css'

const NONE: HideItem[] = []

/**
 * A panel's header (#214): its heading is the button that minimises it and opens it again (a
 * disclosure: `aria-expanded`, `aria-controls` the panel's body), with a chevron that turns, and
 * beside it the one "⋯" for turning the element off. One control for each job, nothing more.
 */
export function PanelHeader({
  id,
  title,
  level: Heading = 'h2',
  minimised,
  onToggle,
  controls,
  hide = NONE,
  className,
}: {
  id: string
  title: string
  level?: ElementType
  minimised: boolean
  onToggle: () => void
  /** The id of the body it shows and hides. */
  controls: string
  hide?: HideItem[]
  className?: string
}) {
  return (
    <div className={`${styles.header} ${className ?? ''}`}>
      <Heading id={id} className={styles.heading}>
        <button
          type="button"
          className={styles.toggle}
          aria-expanded={!minimised}
          aria-controls={controls}
          onClick={onToggle}
        >
          {title}
          <svg className={styles.chevron} viewBox="0 0 16 16" aria-hidden="true" focusable="false">
            <path d="M4 6l4 4 4-4" />
          </svg>
        </button>
      </Heading>
      <HideMenu title={title.toLowerCase()} items={hide} />
    </div>
  )
}
