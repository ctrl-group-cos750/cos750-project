import { useEffect, useId, useRef, useState } from 'react'
import styles from './hiding.module.css'

export type HideItem = { label: string; onSelect: () => void }

/**
 * The one quiet control on a motivational element (#214): a "⋯" button that opens a short list
 * of ways to turn it off here, without going to the profile ("Hide skill profile"). A disclosure
 * of real buttons, not an ARIA menu: Tab reaches each, Escape or a press outside closes it and
 * focus goes back to the "⋯". 44 px on a touch screen.
 */
export function HideMenu({ title, items }: { title: string; items: HideItem[] }) {
  const [open, setOpen] = useState(false)
  const id = useId()
  const button = useRef<HTMLButtonElement>(null)
  const list = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    list.current?.querySelector('button')?.focus()
    const outside = (event: PointerEvent) => {
      const target = event.target as Node
      if (!list.current?.contains(target) && !button.current?.contains(target)) setOpen(false)
    }
    const escape = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return
      setOpen(false)
      button.current?.focus()
    }
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('pointerdown', outside)
      document.removeEventListener('keydown', escape)
    }
  }, [open])

  if (items.length === 0) return null
  return (
    <div className={styles.menu}>
      <button
        ref={button}
        type="button"
        className={styles.menuButton}
        aria-label={`Hide options for ${title}`}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((o) => !o)}
      >
        <span aria-hidden="true">⋯</span>
      </button>
      <div ref={list} id={id} hidden={!open} className={styles.menuList}>
        {items.map((item) => (
          <button
            key={item.label}
            type="button"
            className={styles.menuItem}
            onClick={() => {
              setOpen(false)
              item.onSelect()
            }}
          >
            {item.label}
          </button>
        ))}
      </div>
    </div>
  )
}
