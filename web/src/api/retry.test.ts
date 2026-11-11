import { describe, expect, it } from 'vitest'
import { ApiError } from './client.ts'
import { retryUnlessRefused } from './retry.ts'

describe('retryUnlessRefused', () => {
  it('never retries a refusal', () => {
    for (const status of [400, 403, 404, 409, 422, 429]) {
      expect(retryUnlessRefused(0, new ApiError(status, 'No.'))).toBe(false)
    }
  })

  it('retries a server error or a network failure up to three times', () => {
    expect(retryUnlessRefused(0, new ApiError(503, 'Busy.'))).toBe(true)
    expect(retryUnlessRefused(2, new Error('Network down'))).toBe(true)
    expect(retryUnlessRefused(3, new Error('Network down'))).toBe(false)
  })
})
