/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { toBfsScenario } from './bfs.api.ts'
import { EDGE_CLEARANCE, routeEdge, VERTEX_RADIUS, type Point } from './edgeRouting.ts'

type SeedGraph = {
  id: number
  name: string
  directed: boolean
  vertices: string[]
  edges: { source: string; target: string }[]
  start_vertex: string
}

// The graphs the seed loads (vitest runs from web/). Every graph a student can open is checked,
// including any added later.
const seedGraphs: SeedGraph[] = JSON.parse(
  readFileSync(`${process.cwd()}/../api/app/seed/graphs.json`, 'utf8'),
).graphs

/** The vertices exactly as the visualiser lays them out (bfs.api.ts). */
function layout(graph: SeedGraph) {
  return toBfsScenario({
    graph: { ...graph, startVertex: graph.start_vertex },
    bfs: { startVertex: graph.start_vertex, order: [], steps: [] },
  }).vertices
}

/** Points along a path's line or quadratic curve, read back from its `d`. */
function pointsOf(d: string): Point[] {
  const n = d.match(/-?\d+(\.\d+)?/g)!.map(Number)
  if (d.includes('L')) {
    return Array.from({ length: 101 }, (_, i) => ({
      x: n[0] + ((n[2] - n[0]) * i) / 100,
      y: n[1] + ((n[3] - n[1]) * i) / 100,
    }))
  }
  const [x0, y0, cx, cy, x1, y1] = n
  return Array.from({ length: 101 }, (_, i) => {
    const t = i / 100
    const u = 1 - t
    return {
      x: u * u * x0 + 2 * u * t * cx + t * t * x1,
      y: u * u * y0 + 2 * u * t * cy + t * t * y1,
    }
  })
}

const gap = (points: Point[], vertex: Point) =>
  Math.min(...points.map((p) => Math.hypot(p.x - vertex.x, p.y - vertex.y))) - VERTEX_RADIUS

describe('edge routing (#142: the A–C edge drawn through B)', () => {
  it('reads every graph in graphs.json', () => {
    expect(seedGraphs.length).toBeGreaterThanOrEqual(4)
  })

  it.each(seedGraphs)(
    'graph $id ($name): no edge passes within the clearance of a vertex it does not join',
    (graph) => {
      const vertices = layout(graph)
      const at = new Map(vertices.map((v) => [v.id, v]))
      for (const edge of graph.edges) {
        const others = vertices.filter((v) => v.id !== edge.source && v.id !== edge.target)
        const route = routeEdge({
          from: at.get(edge.source)!,
          to: at.get(edge.target)!,
          others,
          bounds: { width: 420, height: 280 },
        })
        const points = pointsOf(route.d)
        for (const other of others) {
          // A little under the target: the check samples the curve differently from the router.
          expect(
            gap(points, other),
            `${edge.source}–${edge.target} past ${other.id}`,
          ).toBeGreaterThan(EDGE_CLEARANCE - 1)
        }
        for (const p of points) {
          expect(p.x).toBeGreaterThanOrEqual(0)
          expect(p.x).toBeLessThanOrEqual(420)
          expect(p.y).toBeGreaterThanOrEqual(0)
          expect(p.y).toBeLessThanOrEqual(280)
        }
      }
    },
  )

  it('curves the campus graph’s A–C edge away from B, and leaves clear edges straight', () => {
    const campus = seedGraphs.find((graph) => graph.name === 'The campus graph')!
    const vertices = layout(campus)
    const at = new Map(vertices.map((v) => [v.id, v]))
    const route = (a: string, b: string) =>
      routeEdge({
        from: at.get(a)!,
        to: at.get(b)!,
        others: vertices.filter((v) => v.id !== a && v.id !== b),
        bounds: { width: 420, height: 280 },
      })

    // Straight, A–C passes about 13px from B's rim: the bug.
    const straightPastB = gap(
      pointsOf(`M${at.get('A')!.x},${at.get('A')!.y}L${at.get('C')!.x},${at.get('C')!.y}`),
      at.get('B')!,
    )
    expect(straightPastB).toBeLessThan(EDGE_CLEARANCE)

    const ac = route('A', 'C')
    expect(ac.curved).toBe(true)
    expect(gap(pointsOf(ac.d), at.get('B')!)).toBeGreaterThan(straightPastB)
    expect(route('A', 'E').curved).toBe(false) // A and E are next to each other on the circle
  })

  it('draws a straight line when nothing is in the way', () => {
    const route = routeEdge({ from: { x: 0, y: 0 }, to: { x: 100, y: 0 }, others: [] })
    expect(route).toMatchObject({ d: 'M0,0L100,0', curved: false })
  })

  it('bends away from the side the obstacle is on', () => {
    const below = routeEdge({
      from: { x: 0, y: 100 },
      to: { x: 200, y: 100 },
      others: [{ x: 100, y: 110 }],
    })
    const above = routeEdge({
      from: { x: 0, y: 100 },
      to: { x: 200, y: 100 },
      others: [{ x: 100, y: 90 }],
    })
    const controlY = (d: string) => Number(d.match(/Q-?[\d.]+,(-?[\d.]+)/)![1])
    expect(controlY(below.d)).toBeLessThan(100)
    expect(controlY(above.d)).toBeGreaterThan(100)
  })

  it('falls back to the best curve it can find when nothing clears (a crowded graph)', () => {
    const route = routeEdge({
      from: { x: 0, y: 50 },
      to: { x: 100, y: 50 },
      others: [
        { x: 50, y: 50 },
        { x: 50, y: 0 },
        { x: 50, y: 100 },
      ],
      bounds: { width: 100, height: 100 },
    })
    expect(route.d).toMatch(/^M0,50[LQ]/)
    expect(Number.isFinite(route.clearance)).toBe(true)
  })

  it('copes with an edge from a vertex to itself (zero length)', () => {
    const route = routeEdge({
      from: { x: 10, y: 10 },
      to: { x: 10, y: 10 },
      others: [{ x: 12, y: 10 }],
    })
    expect(route.d).toMatch(/^M10,10/)
  })
})
