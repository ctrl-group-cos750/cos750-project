import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { fakeApi } from '../../test/app.tsx'
import { SegmentView } from './SegmentView.tsx'
import type { Segment } from './module.types.ts'

// A video segment's body is its narration as text (FR-3.2, #149).
const videoSegment: Segment = {
  id: 315,
  position: 2,
  kind: 'video',
  title: 'BFS step by step on the campus',
  body: 'BFS uses a **queue**: first in, first out.',
  videoId: null,
  activityId: null,
  done: true,
}

function renderSegment(segment: Segment) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <SegmentView segment={segment} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('SegmentView — video segment text (#149)', () => {
  it('teaches from the text when no video is attached', () => {
    fakeApi()
    renderSegment(videoSegment)

    const region = screen.getByRole('region', { name: 'BFS step by step on the campus' })
    expect(within(region).getByRole('heading', { level: 2 })).toHaveTextContent(
      'BFS step by step on the campus',
    )
    expect(within(region).getByText('queue')).toBeVisible()
    expect(screen.queryByText('Video not available.')).toBeNull()
  })

  it('still says the video is missing when there is no text either', () => {
    fakeApi()
    renderSegment({ ...videoSegment, body: null })

    expect(screen.getByText('Video not available.')).toBeInTheDocument()
  })

  it('offers the text version below an attached video, reachable from the keyboard', async () => {
    fakeApi({
      overrides: {
        'GET /api/videos/42': () =>
          Response.json({
            id: 42,
            title: 'BFS step by step',
            mediaPath: '/media/bfs.mp4',
            captionsPath: '/media/bfs.vtt',
            transcript: 'The recorded transcript.',
            durationSeconds: 60,
            checkpoints: [],
          }),
      },
    })
    renderSegment({ ...videoSegment, videoId: 42 })

    expect(await screen.findByText('The recorded transcript.')).toBeInTheDocument()
    const summary = screen.getByText('Text version')
    expect(summary.tagName).toBe('SUMMARY')
    expect(screen.getByText('queue')).not.toBeVisible()

    const user = userEvent.setup()
    // Tab through the player's controls until the summary has focus: each Tab must follow the last.
    for (let i = 0; i < 20 && document.activeElement !== summary; i++) {
      // oxlint-disable-next-line no-await-in-loop -- key presses happen one after another
      await user.tab()
    }
    expect(summary).toHaveFocus()
    // Browsers open a focused summary on Enter or Space by clicking it; jsdom only does the click.
    await user.click(summary)
    expect(screen.getByText('queue')).toBeVisible()
  })
})
