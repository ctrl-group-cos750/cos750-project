import { describe, expect, it } from 'vitest'
import { toBfsScenario } from './bfs.api.ts'

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
