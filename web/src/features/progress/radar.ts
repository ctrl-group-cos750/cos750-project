/** The radar chart's scale and geometry (SkillRadar.tsx, #214). */
import type { CSSProperties } from 'react'
import { skillStatus } from './skillStatus.ts'
import type { Skill } from './skills.api.ts'

/**
 * The rings of the radar, centre outwards (#214), a radar ("spider") chart as Big Brain Academy
 * draws one. One step out per step up, so the further a point is from the centre, the stronger the
 * objective; the ring carries the level, never the colour alone:
 *
 *   0 centre: not started · 1 practising · 2 secure in practice
 *   3 bronze: met with support · 4 gold: met on your own (both from the mastery check)
 *
 * "Not yet" in the mastery check keeps the practice ring it had and is drawn as an open point.
 */
export const RINGS = [
  { ring: 1, name: 'Practising' },
  { ring: 2, name: 'Secure' },
  { ring: 3, name: 'Bronze' },
  { ring: 4, name: 'Gold' },
] as const

export const MAX_RING = RINGS.length

/** The ring an objective reaches. */
export function ringFor(skill: Skill): number {
  if (skill.result === 'met_independently') return 4
  if (skill.result === 'met_with_support') return 3
  if (skill.level === 'secure') return 2
  if (skill.level === 'practising') return 1
  return 0
}

// The drawing's own units. Wider than tall, so the names at the sides have room beside it.
export const WIDTH = 400
export const HEIGHT = 320
export const CX = WIDTH / 2
export const CY = HEIGHT / 2
/** The outer ring's radius. */
export const RADIUS = 104
/** How far outside the outer ring a name starts. */
const LABEL_GAP = 12

/** Axis `index` of `count`, clockwise from the top. */
export function point(index: number, count: number, radius: number): { x: number; y: number } {
  const angle = (2 * Math.PI * index) / count
  return { x: CX + radius * Math.sin(angle), y: CY - radius * Math.cos(angle) }
}

/** The radius an objective's point sits at, in the drawing's units. */
export function radiusFor(ring: number): number {
  return (RADIUS * ring) / MAX_RING
}

export function polygon(count: number, radius: number): string {
  return Array.from({ length: count }, (_, i) => {
    const p = point(i, count, radius)
    return `${p.x.toFixed(1)},${p.y.toFixed(1)}`
  }).join(' ')
}

/** Where a name goes around the chart: at the end of its axis, pushed outwards, so a name on the
 * right starts there, one on the left ends there, and one at the top or bottom is centred. */
export function labelStyle(index: number, count: number): CSSProperties {
  const angle = (2 * Math.PI * index) / count
  const dx = Math.sin(angle)
  const dy = -Math.cos(angle)
  const p = point(index, count, RADIUS + LABEL_GAP)
  const tx = Math.abs(dx) < 0.1 ? '-50%' : dx > 0 ? '0%' : '-100%'
  const ty = Math.abs(dy) < 0.1 ? '-50%' : dy > 0 ? '0%' : '-100%'
  return {
    left: `${(p.x / WIDTH) * 100}%`,
    top: `${(p.y / HEIGHT) * 100}%`,
    transform: `translate(${tx}, ${ty})`,
    textAlign: Math.abs(dx) < 0.1 ? 'center' : dx > 0 ? 'start' : 'end',
  }
}

/** One sentence for the chart as a whole: how many objectives sit at each level. */
export function radarSummary(skills: Skill[]): string {
  const counts = new Map<string, number>()
  for (const skill of skills) {
    const text = skillStatus(skill).text.split(':')[0].toLowerCase()
    counts.set(text, (counts.get(text) ?? 0) + 1)
  }
  const parts = [...counts].map(([text, n]) => `${n} ${text}`)
  return `Skill profile chart of the ${skills.length} objectives: ${parts.join(', ')}. Each objective is listed with its level below.`
}
