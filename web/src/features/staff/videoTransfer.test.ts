import { describe, expect, it } from 'vitest'
import type { SavedVideo } from './staff.api.ts'
import { exportFileName, fromExport, parseExport, toExport } from './videoTransfer.ts'

const saved: SavedVideo = {
  id: 4,
  title: 'Meet BFS!',
  mediaPath: '/media/videos/abc123.mp4',
  captionsPath: '/media/videos/def456.vtt',
  transcript: 'Words',
  durationSeconds: 90,
  checkpoints: [
    {
      id: 11,
      activityId: 30,
      atSeconds: 20,
      question: {
        prompt: 'Which leaves first?',
        options: [
          { id: 'a', label: 'A' },
          { id: 'b', label: 'B' },
        ],
        correct: 'a',
        feedback: { b: 'That is a stack.' },
      },
      hints: [{ level: 1, body: 'FIFO' }],
    },
  ],
}

describe('video transfer', () => {
  it('exports without the ids that belong to the old site', () => {
    const exported = toExport(saved)
    expect(exported.mediaFile).toBe('abc123.mp4')
    expect(exported.captionsFile).toBe('def456.vtt')
    expect(exported.checkpoints[0]).toEqual({
      atSeconds: 20,
      question: saved.checkpoints[0]!.question,
      hints: [{ level: 1, body: 'FIFO' }],
    })
    expect(JSON.stringify(exported)).not.toContain('activityId')
  })

  it('round-trips into a new video with the paths of the files uploaded here', () => {
    const back = fromExport(parseExport(JSON.stringify(toExport(saved))), {
      mediaPath: '/media/videos/new1.mp4',
      captionsPath: '/media/videos/new2.vtt',
    })
    expect(back).toEqual({
      title: 'Meet BFS!',
      transcript: 'Words',
      durationSeconds: 90,
      mediaPath: '/media/videos/new1.mp4',
      captionsPath: '/media/videos/new2.vtt',
      checkpoints: [
        {
          atSeconds: 20,
          question: saved.checkpoints[0]!.question,
          hints: [{ level: 1, body: 'FIFO' }],
        },
      ],
    })
  })

  it('names the file after the title', () => {
    expect(exportFileName('Meet BFS!')).toBe('meet-bfs.video.json')
    expect(exportFileName('***')).toBe('video.video.json')
  })

  it.each([
    ['not json', /not JSON/],
    ['{"format":"something-else"}', /not a Ctrl Academy video export/],
    ['{"format":"ctrl-academy-video","version":2}', /version 2/],
    ['{"format":"ctrl-academy-video","version":1,"title":"x"}', /incomplete/],
  ])('refuses %s', (text, message) => {
    expect(() => parseExport(text)).toThrow(message)
  })
})
