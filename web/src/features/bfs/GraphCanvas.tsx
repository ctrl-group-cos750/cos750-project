import * as d3 from 'd3'
import { useEffect, useRef } from 'react'
import type { BfsFrame, BfsScenario, VertexState } from './bfs.types.ts'
import { stateForVertex } from './bfs.types.ts'

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

function graphLabel(input: { scenario: BfsScenario; frame: BfsFrame }): string {
  const current = input.frame.current ?? 'none'
  const queue = input.frame.queue.join(', ') || 'empty'
  return `${input.scenario.title}. Current vertex: ${current}. Queue: ${queue}.`
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

  svg
    .append('g')
    .attr('aria-hidden', 'true')
    .selectAll('line')
    .data(edges)
    .join('line')
    .attr('x1', (edge) => vertices.get(edge.from)!.x)
    .attr('y1', (edge) => vertices.get(edge.from)!.y)
    .attr('x2', (edge) => vertices.get(edge.to)!.x)
    .attr('y2', (edge) => vertices.get(edge.to)!.y)
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
    .attr('r', 23)
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
      return state === 'current' ? 'var(--bfs-current-text)' : 'var(--color-text)'
    })
    .text((vertex) => vertex.label)

  nodes
    .append('text')
    .attr('x', 20)
    .attr('y', -17)
    .attr('font-size', 16)
    .attr('font-weight', 700)
    .attr('fill', 'var(--color-text)')
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
      className="block min-h-72 w-full rounded-lg bg-muted/40 ring-1 ring-border"
      role="img"
      aria-label={graphLabel({ scenario, frame })}
    />
  )
}
