import { describe, expect, it } from 'vitest'
import { minutesProgress } from './minutes.ts'
import type { ModuleStatus, ModuleSummary } from './module.types.ts'

function module(
  estimatedMinutes: number,
  status: ModuleStatus,
  segmentCount: number,
  currentSegmentPosition = 0,
): ModuleSummary {
  return {
    id: estimatedMinutes,
    number: 0,
    slug: 's',
    title: 'T',
    goals: [],
    estimatedMinutes,
    status,
    segmentCount,
    currentSegmentPosition,
  }
}

describe('minutesProgress', () => {
  it('counts complete modules in full and nothing for open or locked ones', () => {
    const modules = [module(5, 'complete', 5), module(12, 'open', 10), module(10, 'locked', 9)]
    expect(minutesProgress(modules)).toEqual({ done: 5, total: 27 })
  })

  it('counts a module in progress by the share of its segments moved past', () => {
    // Module 3 at its fifth segment (position 4) of 9: 4/9 of 12 minutes, about 5.
    expect(minutesProgress([module(12, 'in_progress', 9, 4)])).toEqual({ done: 5, total: 12 })
  })

  it('counts every module in the total, with content or not, like the rows and register (#146)', () => {
    const modules = [module(5, 'complete', 5), module(15, 'open', 0), module(10, 'locked', 0)]
    expect(minutesProgress(modules)).toEqual({ done: 5, total: 30 })
  })

  it('reaches the total once every module is complete', () => {
    const modules = [module(5, 'complete', 5), module(12, 'complete', 10)]
    expect(minutesProgress(modules)).toEqual({ done: 17, total: 17 })
  })

  it('never counts more than a module in progress is worth', () => {
    // A module staff shortened below where the student had got to (#128, #146).
    expect(minutesProgress([module(10, 'in_progress', 2, 7)])).toEqual({ done: 10, total: 10 })
  })
})
