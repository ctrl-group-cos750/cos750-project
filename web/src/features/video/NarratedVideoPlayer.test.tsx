import { act, fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest'
import { NarratedVideoPlayer } from './NarratedVideoPlayer.tsx'
import type { AttemptInput, AttemptResult, Hint } from './video.types.ts'

type OnHint = (input: { activityId: number }) => Promise<Hint>

const video = {
  id: 1,
  mediaPath: '/media/videos/x.mp4',
  captionsPath: '/media/videos/x.vtt',
  transcript: 'Line one.\nLine two.',
  checkpoints: [
    { id: 1, atSeconds: 20, activityId: 101 },
    { id: 2, atSeconds: 45, activityId: 102 },
  ],
}
const options = [
  { id: 'a', label: 'A' },
  { id: 'c', label: 'C' },
]
const activities = {
  101: { id: 101, prompt: 'First question?', options },
  102: { id: 102, prompt: 'Second question?', options },
}

let pause: Mock<() => void>
beforeEach(() => {
  pause = vi.fn<() => void>()
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(pause)
  vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined)
})
afterEach(() => vi.restoreAllMocks())

function hint(level: number, hasMore = true): Hint {
  return { level, body: `hint ${level}`, hasMore, nextCountsAsSupport: hasMore && level + 1 >= 3 }
}

/** Renders the player with a fake clock on the <video>: `at(s)` moves it and fires the event. */
function setup(props: { initialPassedIds?: number[]; onHint?: Mock<OnHint> } = {}) {
  const onHint = props.onHint ?? vi.fn<OnHint>()
  const view = render(
    <NarratedVideoPlayer
      video={video}
      activities={activities}
      initialPassedIds={props.initialPassedIds}
      onAttempt={vi
        .fn<(input: AttemptInput) => Promise<AttemptResult>>()
        .mockResolvedValue({ correct: false, feedback: 'Not that one.' })}
      onHint={onHint}
    />,
  )
  const el = view.container.querySelector('video')!
  let now = 0
  Object.defineProperty(el, 'currentTime', {
    configurable: true,
    get: () => now,
    set: (s: number) => {
      now = s
    },
  })
  const at = (s: number, event: 'timeUpdate' | 'seeking' = 'timeUpdate') => {
    now = s
    fireEvent[event](el)
  }
  return { el, at, now: () => now }
}

describe('NarratedVideoPlayer', () => {
  it('stops at a checkpoint and shows its question', () => {
    const { at } = setup()
    at(20)
    expect(pause).toHaveBeenCalled()
    expect(screen.getByText('First question?')).toBeInTheDocument()
  })

  it('pauses again if playback starts while a question is open', () => {
    const { el, at } = setup()
    at(20)
    pause.mockClear()
    fireEvent.play(el)
    expect(pause).toHaveBeenCalledTimes(1)
  })

  it('does not pause on play when no question is open', () => {
    const { el } = setup()
    fireEvent.play(el)
    expect(pause).not.toHaveBeenCalled()
  })

  it('holds a forward seek at the first unanswered checkpoint', () => {
    const { at, now } = setup()
    at(50, 'seeking')
    expect(now()).toBe(20)
  })

  it('lets a returning student seek past checkpoints they already passed', () => {
    const { at, now } = setup({ initialPassedIds: [1] })
    at(30, 'seeking')
    expect(now()).toBe(30)
    at(50, 'seeking')
    expect(now()).toBe(45)
  })

  it('shows one Checkpoint heading', () => {
    const { at } = setup()
    at(20)
    expect(screen.getAllByText('Checkpoint')).toHaveLength(1)
  })

  it('keeps the transcript line breaks', () => {
    setup()
    expect(screen.getByText(/Line one\./)).toHaveClass('whitespace-pre-line')
  })
})

describe('hint ladder at a checkpoint', () => {
  it('warns once before hint 3, then hides the button after the last hint', async () => {
    const onHint = vi
      .fn<OnHint>()
      .mockResolvedValueOnce(hint(1))
      .mockResolvedValueOnce(hint(2))
      .mockResolvedValueOnce(hint(3))
      .mockResolvedValueOnce(hint(4, false))
    const { at } = setup({ onHint })
    at(20)
    const button = () => screen.queryByRole('button', { name: 'Show next hint' })
    const user = userEvent.setup()

    await act(() => user.click(button()!))
    await act(() => user.click(button()!))
    expect(onHint).toHaveBeenCalledTimes(2)

    await act(() => user.click(button()!)) // warns instead of asking
    expect(onHint).toHaveBeenCalledTimes(2)
    expect(screen.getByText('The next hint gives a lot away')).toBeInTheDocument()

    await act(() => user.click(button()!)) // confirmed: hint 3
    await act(() => user.click(button()!)) // hint 4, no second warning
    expect(onHint).toHaveBeenCalledTimes(4)
    expect(screen.getByText('hint 4')).toBeInTheDocument()
    expect(button()).toBeNull()
  })
})
