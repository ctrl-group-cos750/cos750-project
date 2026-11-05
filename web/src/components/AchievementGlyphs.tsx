import type { ReactElement } from 'react'
import type { AchievementGlyph } from './achievements.ts'

/*
 * The pictures inside the badges, drawn on a 24-unit grid with a 2-unit round stroke (the same
 * grid as the app's icons). They use currentColor, so the badge decides the colour. Each one
 * shows the skill itself — a queue, BFS levels, a shortest route — rather than a generic trophy
 * (Malone & Lepper 1987: endogenous, not arbitrary).
 */

const dot = (cx: number, cy: number, r = 1.8) => (
  <circle cx={cx} cy={cy} r={r} fill="currentColor" stroke="none" />
)

function star(cx: number, cy: number, r: number) {
  const points = Array.from({ length: 10 }, (_, i) => {
    const radius = i % 2 === 0 ? r : r * 0.45
    const angle = (Math.PI / 5) * i - Math.PI / 2
    return `${(cx + radius * Math.cos(angle)).toFixed(2)},${(cy + radius * Math.sin(angle)).toFixed(2)}`
  })
  return <polygon points={points.join(' ')} fill="currentColor" strokeWidth={1} />
}

export const glyphs: Record<AchievementGlyph, ReactElement> = {
  // LO1: an open book of definitions.
  'word-smith': (
    <>
      <path d="M12 6.5C9.8 5 6.8 4.5 3.5 5v13c3.3-.5 6.3 0 8.5 1.5 2.2-1.5 5.2-2 8.5-1.5V5c-3.3-.5-6.3 0-8.5 1.5z" />
      <path d="M12 6.5v13" />
      <path d="M6.5 9.5h2.5M6.5 13h2.5M15 9.5h2.5M15 13h2.5" strokeWidth={1.5} />
    </>
  ),
  // LO2: vertices joined by an undirected edge and a directed one.
  'edge-spotter': (
    <>
      <path d="M6.2 9.4l4.6 6.6" />
      <path d="M8 6.5h7.5" />
      <path d="M13 3.8l3 2.7-3 2.7" />
      <circle cx="5" cy="6.5" r="2.5" />
      <circle cx="19" cy="6.5" r="2.5" />
      <circle cx="12" cy="18" r="2.5" />
    </>
  ),
  // LO3: a folded map with a graph drawn on it.
  'map-maker': (
    <>
      <path d="M2.5 6l6-2.5 7 2.5 6-2.5v14.5l-6 2.5-7-2.5-6 2.5z" />
      <path d="M7 15.5l4.5-6 5.5 4" strokeWidth={1.5} />
      {dot(7, 15.5)}
      {dot(11.5, 9.5)}
      {dot(17, 13.5)}
    </>
  ),
  // LO4: BFS spreading out from a start vertex, level by level.
  'right-tool': (
    <>
      {dot(12, 12, 2.4)}
      <circle cx="12" cy="12" r="5.5" />
      <circle cx="12" cy="12" r="9.5" strokeDasharray="2.2 2.6" />
      {dot(17.5, 12, 1.5)}
      {dot(7.2, 15.2, 1.5)}
    </>
  ),
  // LO5: a queue — first in at the back, out at the front.
  'queue-tracer': (
    <>
      <rect x="2.5" y="6" width="5.5" height="7" rx="1" fill="currentColor" fillOpacity={0.3} />
      <rect x="9.25" y="6" width="5.5" height="7" rx="1" />
      <rect x="16" y="6" width="5.5" height="7" rx="1" />
      <path d="M20.5 18.5H4.5" />
      <path d="M7.5 15.8l-3 2.7 3 2.7" />
    </>
  ),
  // LO6: code, built from lines put in order (a Parsons problem).
  'bfs-builder': (
    <>
      <path d="M7.5 6.5L2.5 12l5 5.5" />
      <path d="M16.5 6.5l5 5.5-5 5.5" />
      <path d="M10 8.5h4M10.5 12h4.5M10 15.5h3" strokeWidth={1.75} />
    </>
  ),
  // LO7: a bug, caught.
  'bug-hunter': (
    <>
      <ellipse cx="12" cy="14" rx="4.5" ry="5.5" />
      <path d="M9 7.8a3 3 0 0 1 6 0" />
      <path d="M12 9v10.5" strokeWidth={1.5} />
      <path d="M7.5 12H3.5M7.5 16H4M16.5 12h4M16.5 16H20M9.5 5l-1.5-2M14.5 5l1.5-2" />
    </>
  ),
  // LO8: the long way round (dashed) and the shortest route BFS finds.
  'shortcut-finder': (
    <>
      <path d="M4 19V5h16" strokeDasharray="0.1 3.2" />
      <path d="M4.5 18.5L19.5 5.5" strokeWidth={2.25} />
      {dot(12, 12, 1.8)}
      <circle cx="4" cy="19" r="2.4" fill="currentColor" />
      <circle cx="20" cy="5" r="2.4" fill="currentColor" />
    </>
  ),
  // Milestone: a graduation cap — ready for the lecture.
  'ready-for-lecture': (
    <>
      <path d="M1.5 9.5L12 4.5l10.5 5L12 14.5z" />
      <path d="M6 11.7v4.6c0 1.6 2.7 3.2 6 3.2s6-1.6 6-3.2v-4.6" />
      <path d="M22.5 9.5v5.5" />
    </>
  ),
  // Milestone: an arrow that comes round again, pointing up.
  'came-back-stronger': (
    <>
      <path d="M4.5 13.5a7.5 7.5 0 1 0 2.4-6.2" />
      <path d="M3.5 3.5v5h5" />
      <path d="M12 16.5v-7M9.2 12.2L12 9.4l2.8 2.8" />
    </>
  ),
  // Milestone: a flag on the summit, reached alone.
  'solo-run': (
    <>
      <path d="M1.5 20.5l7-11 4 6 2.5-3.5 7.5 8.5z" />
      <path d="M8.5 9.5V2.5l6 2.3-6 2.3" />
    </>
  ),
  // Quest: a compass.
  quest: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M15.8 8.2l-2 5.6-5.6 2 2-5.6z" fill="currentColor" fillOpacity={0.3} />
      {dot(12, 12, 1)}
    </>
  ),
  // All quests: the compass with every star collected.
  'all-quests': (
    <>
      <circle cx="12" cy="15" r="6.5" />
      <path d="M14.6 12.4l-1.4 4-4 1.2 1.4-4z" fill="currentColor" fillOpacity={0.3} />
      {star(4, 6, 2.6)}
      {star(12, 3.2, 2.6)}
      {star(20, 6, 2.6)}
    </>
  ),
  // Hidden: a vertex outside the edge of the map.
  'off-the-map': (
    <>
      <rect x="2.5" y="2.5" width="13" height="13" rx="1.5" strokeDasharray="2.2 2.2" />
      <path d="M6.5 11.5l3-4.5M9.5 7l9.5 12" strokeWidth={1.5} />
      {dot(6.5, 11.5)}
      {dot(9.5, 7)}
      <circle cx="19.5" cy="19.5" r="2.6" fill="currentColor" />
    </>
  ),
}

/** Shown instead of the picture while the hidden badge is still hidden. */
export const hiddenGlyph = (
  <>
    <path d="M8.8 8.5a3.3 3.3 0 1 1 4.6 3c-.9.5-1.4 1.1-1.4 2.2v.8" strokeWidth={2.25} />
    {dot(12, 18.5, 1.4)}
  </>
)

/** A small padlock for locked badges. */
export const lockGlyph = (
  <>
    <rect x="5" y="10.5" width="14" height="10" rx="2" fill="currentColor" stroke="none" />
    <path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" strokeWidth={2.5} />
  </>
)
