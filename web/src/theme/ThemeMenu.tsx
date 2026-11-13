import { Moon, Sun } from 'lucide-react'
import { useEffect, useId, useRef, useState } from 'react'
import { BACKGROUNDS, useBackground } from '../features/progress/preferences.ts'
import { BACKGROUND_LABELS } from './background.ts'
import { BackgroundSwatch } from './BackgroundSwatch.tsx'
import { useTheme } from './useTheme.ts'
import type { Theme } from './theme.ts'
import styles from './ThemeMenu.module.css'

const THEMES: [Theme, string][] = [
  ['light', 'Light'],
  ['dark', 'Dark'],
]

/**
 * The theme button in the signed-in header (#214): a small panel with two groups of real radio
 * buttons, Light or Dark, and the page background (Glow, Doodles, Plain). Like the account menu it
 * is a disclosure, not an ARIA menu: Tab reaches each group, the arrow keys choose within it, and
 * a choice applies at once. Escape or a click outside closes it and puts focus back on the button;
 * tabbing out of it closes it too. The background is also in the profile's "What you see while
 * you learn"; both write the same setting (per student on this device).
 */
export function ThemeMenu() {
  const { theme, chooseTheme } = useTheme()
  const [background, setBackground] = useBackground()
  const [open, setOpen] = useState(false)
  const wrapper = useRef<HTMLDivElement>(null)
  const button = useRef<HTMLButtonElement>(null)
  const panelId = useId()
  const name = useId()

  useEffect(() => {
    if (!open) return
    function outside(event: PointerEvent) {
      if (!wrapper.current?.contains(event.target as Node)) setOpen(false)
    }
    function focusLeft(event: FocusEvent) {
      const next = event.relatedTarget as Node | null
      if (next && !wrapper.current?.contains(next)) setOpen(false)
    }
    function escape(event: KeyboardEvent) {
      if (event.key !== 'Escape') return
      setOpen(false)
      button.current?.focus()
    }
    const element = wrapper.current
    document.addEventListener('pointerdown', outside)
    document.addEventListener('keydown', escape)
    element?.addEventListener('focusout', focusLeft)
    return () => {
      document.removeEventListener('pointerdown', outside)
      document.removeEventListener('keydown', escape)
      element?.removeEventListener('focusout', focusLeft)
    }
  }, [open])

  const dark = theme === 'dark'
  return (
    <div className={styles.wrapper} ref={wrapper}>
      <button
        ref={button}
        type="button"
        className={styles.trigger}
        aria-expanded={open}
        aria-controls={panelId}
        title="Theme and background"
        onClick={() => setOpen((o) => !o)}
      >
        {dark ? <Moon aria-hidden="true" /> : <Sun aria-hidden="true" />}
        <span className="visually-hidden">Theme and background</span>
      </button>
      <div id={panelId} className={styles.panel} hidden={!open}>
        <fieldset className={styles.group}>
          <legend>Theme</legend>
          {THEMES.map(([value, label]) => (
            <label key={value} className={styles.option}>
              <input
                type="radio"
                name={`${name}-theme`}
                value={value}
                checked={theme === value}
                onChange={() => chooseTheme(value)}
              />
              {value === 'dark' ? (
                <Moon aria-hidden="true" className={styles.icon} />
              ) : (
                <Sun aria-hidden="true" className={styles.icon} />
              )}
              {label}
            </label>
          ))}
        </fieldset>
        <fieldset className={styles.group}>
          <legend>Background</legend>
          {BACKGROUNDS.map((value) => (
            <label key={value} className={styles.option}>
              <input
                type="radio"
                name={`${name}-background`}
                value={value}
                checked={background === value}
                onChange={() => setBackground(value)}
              />
              <BackgroundSwatch background={value} small />
              {BACKGROUND_LABELS[value]}
            </label>
          ))}
        </fieldset>
      </div>
    </div>
  )
}
