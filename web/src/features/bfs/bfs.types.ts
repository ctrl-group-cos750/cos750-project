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
  id: number
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

export function stateForVertex(input: { vertexId: VertexId; frame: BfsFrame }): VertexState {
  if (input.frame.current === input.vertexId) return 'current'
  if (input.frame.queue.includes(input.vertexId)) return 'queued'
  if (input.frame.visited.includes(input.vertexId)) return 'visited'
  return 'unvisited'
}

/** Every vertex BFS has found: those that have left the queue, then those still in it, in the
 * order they joined. This is the set the module 4 code calls `found` (a vertex goes in it when it
 * joins the queue), so the panel and the code name the same two states the same way (Sorva 2013:
 * the picture must match the machine that runs the code). */
export function foundVertices(input: { frame: BfsFrame }): VertexId[] {
  const found = [...input.frame.traversal]
  for (const vertex of input.frame.queue) if (!found.includes(vertex)) found.push(vertex)
  return found
}
