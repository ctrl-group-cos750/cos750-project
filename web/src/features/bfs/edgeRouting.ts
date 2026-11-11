/**
 * Edge routing for the BFS visualiser (#142).
 *
 * The visualiser places vertices on a circle (bfs.api.ts). A straight edge between two vertices
 * that are not neighbours on the circle can pass right beside a third vertex: on the campus graph
 * A–C ran past B and read as A–B plus B–C. The student predicts the next vertex from this
 * drawing (FR-6.4). Byrne et al. (1999) found that prediction is what helps students learn from
 * algorithm animations; that a drawing suggesting a wrong neighbour undermines it is our own
 * inference, not their finding. Any edge that comes closer than `EDGE_CLEARANCE` to a vertex it doesn't join
 * is drawn as a gentle curve, bent away from that vertex, with the smallest bend that clears every
 * vertex. This works for any graph and layout, not just the campus graph.
 */

export type Point = { x: number; y: number }

/** Radius of a vertex circle in GraphCanvas, in viewBox units. */
export const VERTEX_RADIUS = 23
/** The smallest gap allowed between an edge and the rim of a vertex it doesn't join. */
export const EDGE_CLEARANCE = 26

export type EdgeRoute = {
  /** SVG path data: a line, or a quadratic curve. */
  d: string
  curved: boolean
  /** The smallest gap between the drawn edge and the rim of any other vertex. */
  clearance: number
}

const SAMPLES = 48

function distanceToSegment(p: Point, a: Point, b: Point): number {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const lengthSquared = dx * dx + dy * dy
  const t =
    lengthSquared === 0
      ? 0
      : Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / lengthSquared))
  return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy))
}

function quadraticPoints(a: Point, control: Point, b: Point): Point[] {
  return Array.from({ length: SAMPLES + 1 }, (_, i) => {
    const t = i / SAMPLES
    const u = 1 - t
    return {
      x: u * u * a.x + 2 * u * t * control.x + t * t * b.x,
      y: u * u * a.y + 2 * u * t * control.y + t * t * b.y,
    }
  })
}

/** The smallest gap between a polyline and the rim of any of the obstacles. */
function clearanceOf(polyline: Point[], obstacles: readonly Point[]): number {
  let smallest = Infinity
  for (const obstacle of obstacles) {
    for (let i = 1; i < polyline.length; i++) {
      smallest = Math.min(smallest, distanceToSegment(obstacle, polyline[i - 1], polyline[i]))
    }
  }
  return smallest - VERTEX_RADIUS
}

const round = (n: number) => Math.round(n * 10) / 10

/**
 * The path for one edge from `from` to `to`, given the centres of every other vertex.
 *
 * Straight when it clears them all by `EDGE_CLEARANCE`. Otherwise a quadratic curve: the bend
 * grows in small steps, trying first the side away from the nearest vertex, until the whole curve
 * clears every vertex and stays inside `bounds`. If nothing clears (a very crowded graph), the
 * curve with the largest clearance is used.
 */
export function routeEdge(input: {
  from: Point
  to: Point
  others: readonly Point[]
  bounds?: { width: number; height: number }
}): EdgeRoute {
  const { from, to, others } = input
  const straight = clearanceOf([from, to], others)
  if (straight >= EDGE_CLEARANCE || others.length === 0) {
    return {
      d: `M${round(from.x)},${round(from.y)}L${round(to.x)},${round(to.y)}`,
      curved: false,
      clearance: straight,
    }
  }

  const length = Math.hypot(to.x - from.x, to.y - from.y) || 1
  const normal = { x: -(to.y - from.y) / length, y: (to.x - from.x) / length }
  const mid = { x: (from.x + to.x) / 2, y: (from.y + to.y) / 2 }
  const nearest = others.reduce((best, other) =>
    distanceToSegment(other, from, to) < distanceToSegment(best, from, to) ? other : best,
  )
  // Which side of the edge the nearest vertex is on; bend to the other side first.
  const side = Math.sign((nearest.x - mid.x) * normal.x + (nearest.y - mid.y) * normal.y) || 1
  const inBounds = (points: Point[]) =>
    !input.bounds ||
    points.every(
      (p) => p.x >= 0 && p.y >= 0 && p.x <= input.bounds!.width && p.y <= input.bounds!.height,
    )

  let best: { control: Point; clearance: number } | undefined
  for (let bend = 8; bend <= length; bend += 4) {
    for (const direction of [-side, side]) {
      // A quadratic curve's furthest point from its chord is half the control point's offset.
      const control = {
        x: mid.x + normal.x * direction * bend * 2,
        y: mid.y + normal.y * direction * bend * 2,
      }
      const points = quadraticPoints(from, control, to)
      if (!inBounds(points)) continue
      const clearance = clearanceOf(points, others)
      if (clearance >= EDGE_CLEARANCE) return curve(from, control, to, clearance)
      if (!best || clearance > best.clearance) best = { control, clearance }
    }
  }
  return best
    ? curve(from, best.control, to, best.clearance)
    : {
        d: `M${round(from.x)},${round(from.y)}L${round(to.x)},${round(to.y)}`,
        curved: false,
        clearance: straight,
      }
}

function curve(from: Point, control: Point, to: Point, clearance: number): EdgeRoute {
  return {
    d: `M${round(from.x)},${round(from.y)}Q${round(control.x)},${round(control.y)} ${round(to.x)},${round(to.y)}`,
    curved: true,
    clearance,
  }
}
