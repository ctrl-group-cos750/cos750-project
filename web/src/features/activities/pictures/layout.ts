import { routeEdge, type Point } from '../../bfs/edgeRouting.ts'
import type { Drawing, DrawnEdge } from './drawing.ts'
import { placeById } from './situations.ts'

/** Vertex radius in the drawing's own units (the mock-ups' 30). */
export const RADIUS = 30

type Box = { x: number; y: number; w: number; h: number }

const overlaps = (a: Box, b: Box) =>
  a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h

/** About how wide a label is: half the font size per character is close for the system font. */
const textWidth = (text: string, size: number) => text.length * size * 0.56

export type Laid = {
  edge: DrawnEdge
  d: string
  label?: { x: number; y: number; box: Box }
}

/** Where every edge goes and where its label sits. Edges that would pass within the clearance of
 * a vertex they don't join curve away from it (the BFS visualiser's routing); a label takes the
 * first spot near its edge's middle that covers no vertex, vertex name, other label or line. */
export function layOut(drawing: Drawing, large: boolean): { laid: Laid[]; names: Box[] } {
  const { situation } = drawing
  const nameSize = large ? 22 : 15
  const labelSize = large ? 20 : 14
  const centre = (id: string): Point => {
    const place = placeById(situation, id)
    return { x: place?.x ?? 0, y: place?.y ?? 0 }
  }
  const names: Box[] = situation.places
    .filter((place) => place.name)
    .map((place) => {
      const w = textWidth(place.name, nameSize)
      return { x: place.x - w / 2, y: place.y + RADIUS + 4, w, h: nameSize + 4 }
    })
  const circles: Box[] = situation.places.map((place) => ({
    x: place.x - RADIUS - 2,
    y: place.y - RADIUS - 2,
    w: 2 * RADIUS + 4,
    h: 2 * RADIUS + 4,
  }))
  const routes = drawing.edges.map((edge) => {
    const from = centre(edge.from)
    const end = centre(edge.to)
    // An arrow stops at the rim of the vertex it points to.
    const length = Math.hypot(end.x - from.x, end.y - from.y) || 1
    const to = edge.directed
      ? {
          x: end.x - ((end.x - from.x) / length) * (RADIUS + 4),
          y: end.y - ((end.y - from.y) / length) * (RADIUS + 4),
        }
      : end
    const others = situation.places
      .filter((place) => place.id !== edge.from && place.id !== edge.to)
      // A vertex's name, under it, is kept clear too, so no line runs through a label.
      .flatMap((place) =>
        place.name
          ? [
              { x: place.x, y: place.y },
              { x: place.x, y: place.y + RADIUS + 12 },
            ]
          : [{ x: place.x, y: place.y }],
      )
    const route = routeEdge({
      from,
      to,
      others,
      bounds: { width: situation.width, height: situation.height },
    })
    return { edge, route, from, to }
  })
  // Sample every edge, so a label can keep off the lines too.
  const samples = routes.map(({ route, from, to }) => pointsOf(route.d, from, to))
  const taken: Box[] = [...circles, ...names]
  const vertexMarks: Box[] = []
  for (const vertex of drawing.vertices) {
    if (!vertex.label) continue
    const place = placeById(situation, vertex.id)
    if (!place) continue
    const w = textWidth(vertex.label, labelSize)
    const spots = [
      { x: place.x - w / 2, y: place.y - RADIUS - labelSize - 14 },
      { x: place.x + RADIUS + 8, y: place.y - labelSize / 2 },
      { x: place.x - RADIUS - 8 - w, y: place.y - labelSize / 2 },
    ]
    const spot =
      spots.find((s) => fits({ ...s, w, h: labelSize + 4 }, taken, samples, situation)) ?? spots[0]
    const box = { ...spot, w, h: labelSize + 4 }
    taken.push(box)
    vertexMarks.push(box)
  }

  const laid: Laid[] = routes.map(({ edge, route }, index) => {
    if (!edge.label) return { edge, d: route.d }
    const points = samples[index]
    const w = textWidth(edge.label, labelSize)
    const h = labelSize + 4
    let chosen: Box | undefined
    for (const t of [0.5, 0.4, 0.6, 0.3, 0.7, 0.2, 0.8]) {
      const p = points[Math.round(t * (points.length - 1))]
      const q = points[Math.min(points.length - 1, Math.round(t * (points.length - 1)) + 1)]
      const len = Math.hypot(q.x - p.x, q.y - p.y) || 1
      const normal = { x: -(q.y - p.y) / len, y: (q.x - p.x) / len }
      for (const offset of [12, -12, 22, -22, 34, -34, 50, -50]) {
        // Far enough along the normal that the whole box clears the line by |offset|.
        const reach =
          Math.sign(offset) *
          (Math.abs(offset) + (Math.abs(normal.x) * w + Math.abs(normal.y) * h) / 2)
        const cx = p.x + normal.x * reach
        const cy = p.y + normal.y * reach
        const box = { x: cx - w / 2, y: cy - h / 2, w, h }
        if (fits(box, taken, samples, situation)) {
          chosen = box
          break
        }
      }
      if (chosen) break
    }
    chosen ??= {
      x: points[Math.floor(points.length / 2)].x - w / 2,
      y: points[Math.floor(points.length / 2)].y - h - 6,
      w,
      h,
    }
    taken.push(chosen)
    return { edge, d: route.d, label: { x: chosen.x + w / 2, y: chosen.y + h - 5, box: chosen } }
  })
  return { laid, names: vertexMarks }
}

function fits(
  box: Box,
  taken: readonly Box[],
  lines: readonly Point[][],
  situation: { width: number; height: number },
): boolean {
  if (
    box.x < 4 ||
    box.y < 4 ||
    box.x + box.w > situation.width - 4 ||
    box.y + box.h > situation.height - 4
  )
    return false
  if (taken.some((other) => overlaps(box, other))) return false
  return !lines.some((points) =>
    points.some(
      (p) =>
        p.x > box.x - 3 && p.x < box.x + box.w + 3 && p.y > box.y - 3 && p.y < box.y + box.h + 3,
    ),
  )
}

/** Points along a route: a line or a quadratic curve, as routeEdge writes them. */
export function pointsOf(d: string, from: Point, to: Point): Point[] {
  const curve = /Q(-?[\d.]+),(-?[\d.]+)/.exec(d)
  const control = curve ? { x: Number(curve[1]), y: Number(curve[2]) } : undefined
  return Array.from({ length: 41 }, (_, i) => {
    const t = i / 40
    if (!control) return { x: from.x + (to.x - from.x) * t, y: from.y + (to.y - from.y) * t }
    const u = 1 - t
    return {
      x: u * u * from.x + 2 * u * t * control.x + t * t * to.x,
      y: u * u * from.y + 2 * u * t * control.y + t * t * to.y,
    }
  })
}
