import * as d3 from 'd3'
import { useEffect, useRef } from 'react'
import type { BfsFrame, BfsScenario, VertexState } from './bfs.types.ts'
import { stateForVertex } from './bfs.types.ts'
import { routeEdge, VERTEX_RADIUS } from './edgeRouting.ts'

type GraphCanvasProps = {
  scenario: BfsScenario
  frame: BfsFrame
}

const stateMarker: Record<VertexState, string> = {
  unvisited: '',
  queued: '…',
  current: '▶',
  visited: '✓',
}

/** The graph in words for a screen reader (WCAG 1.1.1): its vertices and edges, so a student
 * can work out neighbours, then where BFS is: current vertex, queue and visited set. */
function graphLabel(input: { scenario: BfsScenario; frame: BfsFrame }): string {
  const { scenario, frame } = input
  const label = new Map(scenario.vertices.map((v) => [v.id, v.label]))
  const name = (id: string) => label.get(id) ?? id
  const join = scenario.directed ? ' to ' : '–'
  const edges =
    scenario.edges
      .filter((e) => label.has(e.from) && label.has(e.to))
      .map((e) => `${name(e.from)}${join}${name(e.to)}`)
      .join(', ') || 'none'
  const list = (ids: readonly string[]) => ids.map(name).join(', ') || 'empty'
  return [
    `${scenario.title}, a ${scenario.directed ? 'directed' : 'undirected'} graph`,
    `Vertices: ${list(scenario.vertices.map((v) => v.id))}`,
    `Edges: ${edges}`,
    `Current vertex: ${frame.current ? name(frame.current) : 'none'}`,
    `Queue: ${list(frame.queue)}`,
    `Visited: ${list(frame.visited)}.`,
  ].join('. ')
}

function vertexById(input: {
  scenario: BfsScenario
}): Map<string, BfsScenario['vertices'][number]> {
  return new Map(input.scenario.vertices.map((vertex) => [vertex.id, vertex]))
}

function renderGraph(input: { svgElement: SVGSVGElement; scenario: BfsScenario; frame: BfsFrame }) {
  const svg = d3.select(input.svgElement)
  const vertices = vertexById({ scenario: input.scenario })
  const width = 420
  const height = 280
  const markerId = `arrow-${input.scenario.id}`

  svg.attr('viewBox', `0 0 ${width} ${height}`)
  svg.selectAll('*').remove()

  if (input.scenario.directed) {
    svg
      .append('defs')
      .append('marker')
      .attr('id', markerId)
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 29)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', 'var(--bfs-edge)')
  }

  const edges = input.scenario.edges.filter((edge) => {
    return vertices.has(edge.from) && vertices.has(edge.to)
  })

  // An edge that would pass beside a vertex it doesn't join is curved around it (edgeRouting.ts),
  // so A–C is never read as A–B plus B–C.
  svg
    .append('g')
    .attr('aria-hidden', 'true')
    .selectAll('path')
    .data(edges)
    .join('path')
    .attr('d', (edge) => {
      const from = vertices.get(edge.from)!
      const to = vertices.get(edge.to)!
      const others = input.scenario.vertices.filter((v) => v.id !== edge.from && v.id !== edge.to)
      return routeEdge({ from, to, others, bounds: { width, height } }).d
    })
    .attr('fill', 'none')
    .attr('stroke', 'var(--bfs-edge)')
    .attr('stroke-width', 2)
    .attr('marker-end', () => {
      return input.scenario.directed ? `url(#${markerId})` : null
    })

  const nodes = svg
    .append('g')
    .selectAll('g')
    .data(input.scenario.vertices)
    .join('g')
    .attr('transform', (vertex) => `translate(${vertex.x}, ${vertex.y})`)
    .attr('aria-label', (vertex) => {
      const state = stateForVertex({ vertexId: vertex.id, frame: input.frame })
      return `${vertex.label}: ${state}`
    })

  nodes
    .append('circle')
    .attr('r', VERTEX_RADIUS)
    .attr('fill', (vertex) => {
      const state = stateForVertex({ vertexId: vertex.id, frame: input.frame })
      return `var(--bfs-${state}-fill)`
    })
    .attr('stroke', (vertex) => {
      const state = stateForVertex({ vertexId: vertex.id, frame: input.frame })
      return `var(--bfs-${state}-stroke)`
    })
    .attr('stroke-width', (vertex) => {
      const state = stateForVertex({ vertexId: vertex.id, frame: input.frame })
      return state === 'current' ? 4 : 2
    })

  nodes
    .append('text')
    .attr('text-anchor', 'middle')
    .attr('dy', '0.35em')
    .attr('font-family', 'var(--font-mono)')
    .attr('font-size', 18)
    .attr('font-weight', 600)
    .attr('fill', (vertex) => {
      const state = stateForVertex({ vertexId: vertex.id, frame: input.frame })
      return state === 'current' ? 'var(--bfs-current-text)' : 'var(--foreground)'
    })
    .text((vertex) => vertex.label)

  nodes
    .append('text')
    .attr('x', 20)
    .attr('y', -17)
    .attr('font-size', 16)
    .attr('font-weight', 700)
    .attr('fill', 'var(--foreground)')
    .text((vertex) => {
      const state = stateForVertex({ vertexId: vertex.id, frame: input.frame })
      return stateMarker[state]
    })
}

export function GraphCanvas({ scenario, frame }: GraphCanvasProps) {
  const svgRef = useRef<SVGSVGElement>(null)

  useEffect(() => {
    if (svgRef.current) {
      renderGraph({ svgElement: svgRef.current, scenario, frame })
    }
  }, [frame, scenario])

  return (
    <svg
      ref={svgRef}
      className="block max-h-[60vh] min-h-72 w-full rounded-lg bg-muted/40 ring-1 ring-border"
      // An SVG needs role="img" to expose its text alternative as one accessible graphic.
      // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
      role="img"
      aria-label={graphLabel({ scenario, frame })}
    />
  )
}
