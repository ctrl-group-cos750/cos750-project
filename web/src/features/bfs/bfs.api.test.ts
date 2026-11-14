import { describe, expect, it } from 'vitest'
import { toBfsScenario } from './bfs.api.ts'
import { foundVertices } from './bfs.types.ts'

describe('toBfsScenario', () => {
  it('creates an initial frame before the server BFS steps', () => {
    const scenario = toBfsScenario({
      graph: {
        id: 1,
        name: 'Diamond',
        directed: false,
        vertices: ['A', 'B', 'C'],
        edges: [
          { source: 'A', target: 'B' },
          { source: 'A', target: 'C' },
        ],
        startVertex: 'A',
      },
      bfs: {
        startVertex: 'A',
        order: ['A', 'B', 'C'],
        steps: [
          {
            visitedVertex: 'A',
            queue: ['B', 'C'],
            visited: ['A'],
            order: ['A'],
          },
        ],
      },
    })

    expect(scenario.frames[0]).toEqual({
      current: null,
      queue: ['A'],
      visited: [],
      traversal: [],
    })

    expect(scenario.frames[1]).toEqual({
      current: 'A',
      queue: ['B', 'C'],
      visited: ['A'],
      traversal: ['A'],
    })
  })
})

describe('foundVertices', () => {
  // The code's `found` set (module 4): a vertex is found when it joins the queue, visited when it
  // leaves. The visualiser shows both, so its picture matches the code (review 13 Nov, High 3).
  it('is every vertex that has joined the queue: those that left it, then those still in it', () => {
    expect(
      foundVertices({
        frame: { current: 'A', queue: ['B', 'C'], visited: ['A'], traversal: ['A'] },
      }),
    ).toEqual(['A', 'B', 'C'])
    expect(
      foundVertices({ frame: { current: null, queue: ['A'], visited: [], traversal: [] } }),
    ).toEqual(['A'])
  })
})
