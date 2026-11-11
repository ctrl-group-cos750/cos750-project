import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ApiError, refusalMessage } from '../../api/client.ts'
import { ada, fakeApi, renderApp } from '../../test/app.tsx'
import { HintLadder } from './HintLadder.tsx'
import type { Hint } from './activities.types.ts'

// The API refuses an activity whose module is locked or review path closed (403), and one that is
// no longer in the course (404) (#137). The page says so at once instead of retrying behind a
// spinner, and offers the way back.

const LOCKED =
  "This activity is in a module that isn't open yet. Complete the module before it to unlock it."
const RETIRED = 'This activity is no longer part of the course.'

describe('an activity the student may not open', () => {
  it.each([
    [403, LOCKED],
    [404, RETIRED],
  ])('says why at once on %i and offers the module map', async (status, detail) => {
    const api = fakeApi({
      user: ada,
      overrides: {
        'GET /api/activities/601': () => Response.json({ detail }, { status }),
      },
    })
    renderApp('/activities/601')

    expect(await screen.findByText(detail)).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 1, name: 'This activity isn’t available' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to your modules' })).toHaveAttribute('href', '/')
    expect(screen.queryByText('Loading activity')).not.toBeInTheDocument()
    // Not retried: asking again would get the same answer.
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(api.callsTo('GET /api/activities/601')).toHaveLength(1)
  })

  it('a video that is not open yet says so without retrying', async () => {
    const detail = "This video is in a part of the course that isn't open yet."
    const api = fakeApi({
      user: ada,
      overrides: { 'GET /api/videos/3': () => Response.json({ detail }, { status: 403 }) },
    })
    renderApp('/videos/3')
    expect(await screen.findByText(detail)).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 1, name: 'This video isn’t available' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back to your modules' })).toHaveAttribute('href', '/')
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(api.callsTo('GET /api/videos/3')).toHaveLength(1)
  })

  it('a closed review path is not retried', async () => {
    const detail = "This review path opens when the mastery check marks the objective 'not yet'."
    const api = fakeApi({
      user: ada,
      overrides: { 'GET /api/me/review/2': () => Response.json({ detail }, { status: 403 }) },
    })
    renderApp('/review/2')
    expect(await screen.findByText(detail)).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 1, name: 'Review: objective 2' }),
    ).toBeInTheDocument()
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(api.callsTo('GET /api/me/review/2')).toHaveLength(1)
  })
})

describe('the hint ladder when the API refuses', () => {
  it('shows the rate limit message rather than a generic failure', async () => {
    const user = userEvent.setup()
    const message = "That's a lot of hints at once. Wait a moment and try again."
    const requestHint = vi
      .fn<(activityId: number) => Promise<Hint>>()
      .mockRejectedValue(new ApiError(429, message))
    render(<HintLadder activityId={7} loadHints={async () => []} requestHint={requestHint} />)
    await user.click(await screen.findByRole('button', { name: 'Show next hint' }))
    expect(await screen.findByText(message)).toBeInTheDocument()
  })

  it('keeps the general message when the server failed', async () => {
    const user = userEvent.setup()
    const requestHint = vi
      .fn<(activityId: number) => Promise<Hint>>()
      .mockRejectedValue(new ApiError(500, 'Something went wrong on our side.'))
    render(<HintLadder activityId={7} loadHints={async () => []} requestHint={requestHint} />)
    await user.click(await screen.findByRole('button', { name: 'Show next hint' }))
    await waitFor(() =>
      expect(screen.getByText('We could not load a hint. Please try again.')).toBeInTheDocument(),
    )
  })
})

describe('refusalMessage', () => {
  it('uses the API’s words only for a refusal', () => {
    expect(refusalMessage(new ApiError(429, 'Slow down.'), 'fallback')).toBe('Slow down.')
    expect(refusalMessage(new ApiError(500, 'Boom.'), 'fallback')).toBe('fallback')
    expect(refusalMessage(new ApiError(0, 'Offline.'), 'fallback')).toBe('fallback')
    expect(refusalMessage(new Error('x'), 'fallback')).toBe('fallback')
  })
})
