import { api } from '../../api/client.ts'
import type { BfsEdge, BfsFrame, BfsScenario, BfsVertex } from './bfs.types.ts'

type GraphOut = {
  id: number
  name: string
  directed: boolean
  vertices: string[]
  edges: { source: string; target: string }[]
  startVertex: string
}

type BfsResultOut = {
  startVertex: string
  order: string[]
  steps: {
    visitedVertex: string
    queue: string[]
    visited: string[]
    order: string[]
  }[]
}

const graphWidth = 420
const graphHeight = 280
const vertexRadius = 95

export async function fetchBfsScenario(input: { scenarioId: number }): Promise<BfsScenario> {
  const [graph, bfs] = await Promise.all([
    api<GraphOut>(`/api/graphs/${input.scenarioId}`),
    api<BfsResultOut>(`/api/graphs/${input.scenarioId}/bfs`),
  ])

  return toBfsScenario({ graph, bfs })
}

export function toBfsScenario(input: { graph: GraphOut; bfs: BfsResultOut }): BfsScenario {
  return {
    id: input.graph.id,
    title: input.graph.name,
    directed: input.graph.directed,
    vertices: layoutVertices({ labels: input.graph.vertices }),
    edges: toEdges({ edges: input.graph.edges }),
    frames: toFrames({ startVertex: input.bfs.startVertex, steps: input.bfs.steps }),
  }
}

function layoutVertices(input: { labels: string[] }): BfsVertex[] {
  const total = input.labels.length
  const centreX = graphWidth / 2
  const centreY = graphHeight / 2

  if (total === 1) {
    return [{ id: input.labels[0], label: input.labels[0], x: centreX, y: centreY }]
  }

  return input.labels.map((label, index) => {
    const angle = (index / total) * Math.PI * 2 - Math.PI / 2

    return {
      id: label,
      label,
      x: centreX + vertexRadius * Math.cos(angle),
      y: centreY + vertexRadius * Math.sin(angle),
    }
  })
}

function toEdges(input: { edges: GraphOut['edges'] }): BfsEdge[] {
  return input.edges.map((edge) => ({
    from: edge.source,
    to: edge.target,
  }))
}

function toFrames(input: { startVertex: string; steps: BfsResultOut['steps'] }): BfsFrame[] {
  const initialFrame: BfsFrame = {
    current: null,
    queue: [input.startVertex],
    visited: [],
    traversal: [],
  }

  const traversalFrames = input.steps.map((step) => ({
    current: step.visitedVertex,
    queue: step.queue,
    visited: step.visited,
    traversal: step.order,
  }))

  return [initialFrame, ...traversalFrames]
}
