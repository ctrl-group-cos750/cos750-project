import { onPreferenceChange, preference, setPreference, usePreference } from './preferences.ts'

/**
 * A short confetti burst for a moment worth marking (#214): small for a correct answer, fuller
 * for finishing a module or being ready for the lecture. Written for this app rather than taken
 * from a package: one canvas, a few dozen pieces, about 70 lines.
 *
 * - It never gets in the way: a fixed canvas over the page with `pointer-events: none` and
 *   `aria-hidden`, so it takes no space (no layout shift), can't be clicked or read, and is removed
 *   as soon as the pieces have fallen.
 * - It is off under `prefers-reduced-motion: reduce`, and when the student turns it off (on the
 *   profile page or the "Turn off confetti" link by a correct answer): preferences.ts.
 * - No sound, no timers the student sees, nothing about speed.
 */

export type Burst = 'small' | 'big'

const BURSTS: Record<Burst, { pieces: number; ms: number }> = {
  small: { pieces: 36, ms: 1300 },
  big: { pieces: 120, ms: 2000 },
}

/** Whether the student wants confetti on this device. On unless they turned it off. */
export function confettiEnabled(): boolean {
  return preference('confetti')
}

export function setConfettiEnabled(on: boolean): void {
  setPreference('confetti', on)
}

// Turning it off stops a burst already falling.
onPreferenceChange((name, on) => {
  if (name === 'confetti' && !on) stopConfetti()
})

/** The confetti switch. */
export function useConfettiSetting(): [boolean, (on: boolean) => void] {
  return usePreference('confetti')
}

export function prefersReducedMotion(): boolean {
  return typeof window.matchMedia === 'function'
    ? window.matchMedia('(prefers-reduced-motion: reduce)').matches
    : false
}

const running = new Set<HTMLCanvasElement>()

/** Removes every burst still on screen. */
export function stopConfetti(): void {
  for (const canvas of running) canvas.remove()
  running.clear()
}

/** The theme's own colours, so the pieces match light and dark. */
function colours(): string[] {
  const style = getComputedStyle(document.documentElement)
  const names = ['--primary', '--success', '--badge-gold', '--badge-bronze', '--badge-silver']
  const found = names.map((n) => style.getPropertyValue(n).trim()).filter(Boolean)
  return found.length > 0 ? found : ['#2f72c6', '#147047', '#8a6b00', '#c93b31']
}

type Piece = {
  x: number
  y: number
  vx: number
  vy: number
  turn: number
  spin: number
  w: number
  h: number
  colour: string
}

/**
 * Starts a burst, from `from` (an element, e.g. the result that was just shown) or, for a big
 * one, from both lower corners. Returns whether it started: not when turned off, under reduced
 * motion, or where there is no matchMedia or canvas (tests).
 */
export function confetti(size: Burst = 'small', from?: Element | null): boolean {
  // No matchMedia means no way to honour reduced motion (and, in practice, a test DOM): none.
  if (typeof window.matchMedia !== 'function') return false
  if (!confettiEnabled() || prefersReducedMotion()) return false
  const canvas = document.createElement('canvas')
  const context = canvas.getContext?.('2d')
  if (!context) return false
  const { pieces, ms } = BURSTS[size]
  const ratio = window.devicePixelRatio || 1
  const width = window.innerWidth
  const height = window.innerHeight
  canvas.width = width * ratio
  canvas.height = height * ratio
  canvas.setAttribute('aria-hidden', 'true')
  canvas.dataset.confetti = size
  Object.assign(canvas.style, {
    position: 'fixed',
    inset: '0',
    width: '100%',
    height: '100%',
    pointerEvents: 'none',
    zIndex: '60',
  })
  context.scale(ratio, ratio)
  document.body.append(canvas)
  running.add(canvas)

  const box = from?.getBoundingClientRect()
  const origins: [number, number, number][] = box
    ? [[box.left + Math.min(box.width, 240) / 2, box.top + 12, -Math.PI / 2]]
    : [
        [0, height * 0.9, -Math.PI / 3],
        [width, height * 0.9, (-2 * Math.PI) / 3],
      ]
  const palette = colours()
  const all: Piece[] = Array.from({ length: pieces }, (_, i) => {
    const [x, y, aim] = origins[i % origins.length]
    const angle = aim + (Math.random() - 0.5) * (box ? 1.6 : 0.9)
    const speed = (box ? 5 : 11) + Math.random() * (box ? 5 : 8)
    return {
      x,
      y,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed,
      turn: Math.random() * Math.PI,
      spin: (Math.random() - 0.5) * 0.3,
      w: 5 + Math.random() * 4,
      h: 3 + Math.random() * 3,
      colour: palette[i % palette.length],
    }
  })

  const start = performance.now()
  const frame = (now: number) => {
    if (!running.has(canvas)) return
    const t = (now - start) / ms
    if (t >= 1) {
      canvas.remove()
      running.delete(canvas)
      return
    }
    context.clearRect(0, 0, width, height)
    context.globalAlpha = t < 0.7 ? 1 : 1 - (t - 0.7) / 0.3
    for (const p of all) {
      p.vx *= 0.985
      p.vy = p.vy * 0.985 + 0.32
      p.x += p.vx
      p.y += p.vy
      p.turn += p.spin
      context.save()
      context.translate(p.x, p.y)
      context.rotate(p.turn)
      context.fillStyle = p.colour
      context.fillRect(-p.w / 2, -p.h / 2, p.w, p.h * Math.abs(Math.cos(p.turn * 2)))
      context.restore()
    }
    requestAnimationFrame(frame)
  }
  requestAnimationFrame(frame)
  return true
}

/** A big burst for a moment that happens once (`moment`, e.g. "ready-for-the-lecture"), the first
 * time this device sees it. Returns whether it played. */
export function celebrateOnce(moment: string): boolean {
  const key = `ctrl-academy.seen.${moment}`
  try {
    if (localStorage.getItem(key)) return false
    localStorage.setItem(key, '1')
  } catch {
    return false // storage blocked: better none than one on every visit
  }
  return confetti('big')
}
