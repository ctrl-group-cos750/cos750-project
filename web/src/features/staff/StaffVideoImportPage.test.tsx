import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { User } from '../../auth/api.ts'
import { fakeApi, renderApp } from '../../test/app.tsx'
import { FORMAT } from './videoTransfer.ts'

vi.mock('./staff.api.ts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./staff.api.ts')>()
  return {
    ...actual,
    uploadMedia: vi.fn<typeof actual.uploadMedia>((kind) =>
      Promise.resolve(kind === 'video' ? '/media/videos/new.mp4' : '/media/videos/new.vtt'),
    ),
  }
})

const grace: User = {
  id: 2,
  email: 'grace@example.com',
  displayName: 'Grace',
  isStaff: true,
  avatar: null,
}
const question = {
  prompt: 'Which leaves first?',
  options: [
    { id: 'a', label: 'A' },
    { id: 'b', label: 'B' },
  ],
  correct: 'a',
  feedback: {},
}
const exported = {
  format: FORMAT,
  version: 1,
  title: 'Meet BFS',
  transcript: 'Words',
  durationSeconds: 90,
  mediaFile: 'abc.mp4',
  captionsFile: 'abc.vtt',
  checkpoints: [{ atSeconds: 20, question, hints: [{ level: 1, body: 'FIFO' }] }],
}
const file = (name: string, text: string, type: string) => new File([text], name, { type })

describe('importing a video', () => {
  it('refuses a file that is not an export', async () => {
    fakeApi({ user: grace })
    renderApp('/staff/videos/import')
    await userEvent.upload(
      await screen.findByLabelText('Details (.video.json)'),
      file('x.json', '{"hello":1}', 'application/json'),
    )
    expect(await screen.findByText(/not a Ctrl Academy video export/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Import video' })).toBeDisabled()
  })

  it('uploads both files, creates the video and opens it in the editor', async () => {
    const api = fakeApi({
      user: grace,
      overrides: {
        'POST /api/staff/videos': (body) =>
          Response.json(
            {
              ...(body as object),
              id: 9,
              checkpoints: [{ ...exported.checkpoints[0], id: 1, activityId: 5 }],
            },
            { status: 201 },
          ),
        'GET /api/staff/videos/9': () =>
          Response.json({
            ...exported,
            id: 9,
            mediaPath: '/media/videos/new.mp4',
            captionsPath: '/media/videos/new.vtt',
            checkpoints: [{ ...exported.checkpoints[0], id: 1, activityId: 5 }],
          }),
      },
    })
    renderApp('/staff/videos/import')
    await userEvent.upload(
      await screen.findByLabelText('Details (.video.json)'),
      file('meet-bfs.video.json', JSON.stringify(exported), 'application/json'),
    )
    expect(await screen.findByText(/"Meet BFS", 1 checkpoint/)).toBeInTheDocument()
    await userEvent.upload(screen.getByLabelText('Video (.mp4)'), file('abc.mp4', 'x', 'video/mp4'))
    // A renamed file gets a gentle check, not a refusal.
    await userEvent.upload(
      screen.getByLabelText('Captions (.vtt)'),
      file('other.vtt', 'WEBVTT', 'text/vtt'),
    )
    expect(screen.getByText(/the captions are abc.vtt/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Import video' }))
    expect(await screen.findByDisplayValue('Meet BFS')).toBeInTheDocument() // the editor
    expect(api.callsTo('POST /api/staff/videos')[0]?.body).toEqual({
      title: 'Meet BFS',
      transcript: 'Words',
      durationSeconds: 90,
      mediaPath: '/media/videos/new.mp4',
      captionsPath: '/media/videos/new.vtt',
      checkpoints: [{ atSeconds: 20, question, hints: [{ level: 1, body: 'FIFO' }] }],
    })
  })
})
