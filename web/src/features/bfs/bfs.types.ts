export type VertexId = string

export type BfsVertex = {
  id: VertexId
  label: string
  x: number
  y: number
}

export type BfsEdge = {
  from: VertexId
  to: VertexId
}

export type BfsFrame = {
  current: VertexId | null
  queue: readonly VertexId[]
  visited: readonly VertexId[]
  traversal: readonly VertexId[]
}

export type BfsScenario = {
  id: string
  title: string
  directed: boolean
  vertices: readonly BfsVertex[]
  edges: readonly BfsEdge[]
  frames: readonly BfsFrame[]
}

export type VertexState = 'unvisited' | 'queued' | 'current' | 'visited'

export function expectedVertex(input: {
  scenario: BfsScenario
  frameIndex: number
}): VertexId | null {
  return input.scenario.frames[input.frameIndex + 1]?.current ?? null
}

export function stateForVertex(input: {
  vertexId: VertexId
  frame: BfsFrame
}): VertexState {
  if (input.frame.current === input.vertexId) return 'current'
  if (input.frame.queue.inclues(input.vertexId)) return 'queued'
  if (input.frame.visited.includes(input.vertexId)) return 'visited'
  return 'unvisited'
}
