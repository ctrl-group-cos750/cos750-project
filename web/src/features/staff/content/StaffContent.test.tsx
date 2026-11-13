import { fireEvent, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { User } from '../../../auth/api.ts'
import { ada, fakeApi, renderApp } from '../../../test/app.tsx'
import { LEAVE_UNSAVED } from './useWarnBeforeLeaving.ts'
import type { ActivityOut, ContentOverview, ModuleOut } from './content.api.ts'

const grace: User = {
  id: 2,
  email: 'grace@example.com',
  displayName: 'Grace',
  isStaff: true,
  avatar: null,
  pictureUrl: null,
}

const overview: ContentOverview = {
  objectives: [
    {
      id: 1,
      text: 'Explain what a graph is.',
      bloomLevel: 'Understand',
      criterion: '4 of 5',
      passFraction: 0.8,
      maxWrong: null,
      edited: false,
      inRepository: true,
    },
  ],
  modules: [
    {
      id: 3,
      slug: 'meet-bfs',
      title: 'Meet BFS',
      segmentCount: 2,
      edited: false,
      segmentsEdited: true,
      inRepository: true,
    },
  ],
  reviewPaths: [{ objectiveId: 1, segmentCount: 3, edited: false, inRepository: true }],
  activities: [
    {
      id: 311,
      kind: 'multiple_choice',
      title: 'Which leaves first?',
      moduleId: 3,
      objectiveId: 1,
      purpose: 'practice',
      edited: false,
      inRepository: true,
    },
  ],
  graphs: [{ id: 1, name: 'Campus', edited: false, inRepository: true }],
  videos: [{ id: 7, title: 'Meet BFS video', segmentId: null }],
}

const module3: ModuleOut = {
  id: 3,
  slug: 'meet-bfs',
  title: 'Meet BFS',
  goals: ['Trace BFS.'],
  estimatedMinutes: 15,
  segments: [
    { id: 301, kind: 'text', title: 'Welcome', body: 'Hello' },
    { id: 302, kind: 'activity', title: 'Question', body: '', activityId: 311 },
  ],
  edited: false,
  segmentsEdited: true,
  inRepository: true,
}

const activity: ActivityOut = {
  id: 311,
  kind: 'multiple_choice',
  title: 'Which leaves first?',
  visible: true,
  moduleId: 3,
  objectiveId: 1,
  purpose: 'practice',
  config: { prompt: 'Q', options: [{ id: 'a', label: 'A' }] },
  solution: { correct: 'a' },
  hints: [{ level: 1, body: 'FIFO' }],
  edited: true,
  inRepository: true,
  inUse: false,
  shownIn: ['module 3: Question'],
}

describe('staff content editor', () => {
  it('lists the content, marking what was edited in the portal', async () => {
    fakeApi({
      user: grace,
      overrides: { 'GET /api/staff/content': () => Response.json(overview) },
    })
    renderApp('/staff/content')
    expect(await screen.findByRole('link', { name: '3. Meet BFS' })).toHaveAttribute(
      'href',
      '/staff/content/modules/3',
    )
    expect(screen.getByText('Edited in the portal')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Which leaves first?' })).toHaveAttribute(
      'href',
      '/staff/content/activities/311',
    )
    expect(screen.getByRole('button', { name: /Download as fixtures/ })).toBeInTheDocument()
  })

  it('saves a module with its segments in the new order', async () => {
    const api = fakeApi({
      user: grace,
      overrides: {
        'GET /api/staff/content': () => Response.json(overview),
        'GET /api/staff/content/modules/3': () => Response.json(module3),
        'PUT /api/staff/content/modules/3': (body) =>
          Response.json({ ...module3, ...(body as object) }),
      },
    })
    renderApp('/staff/content/modules/3')
    fireEvent.click(await screen.findByRole('button', { name: 'Move segment 2 up' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save module' }))
    await waitFor(() => expect(api.callsTo('PUT /api/staff/content/modules/3')).toHaveLength(1))
    const sent = api.callsTo('PUT /api/staff/content/modules/3')[0]!.body as ModuleOut
    expect(sent.segments.map((s) => s.id)).toEqual([302, 301])
    // In a status region, so a screen reader hears it (A10).
    expect((await screen.findByText('Saved.')).tagName).toBe('OUTPUT')
    expect(document.title).toBe('Module 3 · Content · Staff portal · Ctrl Academy')
  })

  it('marks a segment as support for an objective (FR-8.4)', async () => {
    const api = fakeApi({
      user: grace,
      overrides: {
        'GET /api/staff/content': () => Response.json(overview),
        'GET /api/staff/content/modules/3': () => Response.json(module3),
        'PUT /api/staff/content/modules/3': (body) =>
          Response.json({ ...module3, ...(body as object) }),
      },
    })
    renderApp('/staff/content/modules/3')
    const supportFor = await screen.findAllByLabelText('Support for (optional)')
    expect(supportFor).toHaveLength(2) // a text and an activity segment can both be support
    fireEvent.change(supportFor[1], { target: { value: '0' } }) // objective 1, the first choice
    fireEvent.click(screen.getByRole('button', { name: 'Save module' }))
    await waitFor(() => expect(api.callsTo('PUT /api/staff/content/modules/3')).toHaveLength(1))
    const sent = api.callsTo('PUT /api/staff/content/modules/3')[0]!.body as ModuleOut
    expect(sent.segments.map((s) => s.supportFor ?? null)).toEqual([null, 1])
  })

  it('offers no support in the mastery check', async () => {
    const module6 = { ...module3, id: 6 }
    fakeApi({
      user: grace,
      overrides: {
        'GET /api/staff/content': () => Response.json(overview),
        'GET /api/staff/content/modules/6': () => Response.json(module6),
      },
    })
    renderApp('/staff/content/modules/6')
    expect(await screen.findByRole('button', { name: 'Save module' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Support for (optional)')).not.toBeInTheDocument()
  })

  it('shows the reason the API refused a save', async () => {
    fakeApi({
      user: grace,
      overrides: {
        'GET /api/staff/content': () => Response.json(overview),
        'GET /api/staff/content/activities/311': () => Response.json(activity),
        'PUT /api/staff/content/activities/311': () =>
          Response.json(
            { detail: 'activity 311: a mastery item belongs in module 6' },
            { status: 422 },
          ),
      },
    })
    renderApp('/staff/content/activities/311')
    fireEvent.click(await screen.findByRole('button', { name: 'Save activity' }))
    expect(await screen.findByText(/a mastery item belongs in module 6/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /repository's version/ })).toBeInTheDocument()
  })

  it('refuses JSON it cannot read before sending anything', async () => {
    const api = fakeApi({
      user: grace,
      overrides: {
        'GET /api/staff/content': () => Response.json(overview),
        'GET /api/staff/content/activities/311': () => Response.json(activity),
      },
    })
    renderApp('/staff/content/activities/311')
    const config = await screen.findByLabelText(/Config/)
    fireEvent.change(config, { target: { value: '{ not json' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save activity' }))
    // The field is marked, its message tied to it, and focus taken there (A10).
    await waitFor(() => expect(config).toHaveFocus())
    expect(config).toHaveAttribute('aria-invalid', 'true')
    expect(config).toHaveAccessibleDescription(/The config is not valid JSON/)
    expect(api.callsTo('PUT /api/staff/content/activities/311')).toHaveLength(0)
  })

  it('asks before a link in the app discards unsaved changes (A10)', async () => {
    fakeApi({
      user: grace,
      overrides: {
        'GET /api/staff/content': () => Response.json(overview),
        'GET /api/staff/content/activities/311': () => Response.json(activity),
      },
    })
    const confirm = vi.fn<(message?: string) => boolean>(() => false)
    vi.stubGlobal('confirm', confirm)
    renderApp('/staff/content/activities/311')
    const config = await screen.findByLabelText(/Config/)
    fireEvent.change(config, { target: { value: '{}' } })
    fireEvent.click(screen.getByRole('link', { name: 'All content' }))
    await waitFor(() => expect(confirm).toHaveBeenCalledWith(LEAVE_UNSAVED))
    expect(screen.getByLabelText(/Config/)).toHaveValue('{}') // still here, edits kept
    confirm.mockReturnValue(true)
    fireEvent.click(screen.getByRole('link', { name: 'All content' }))
    expect(await screen.findByRole('heading', { name: 'Content', level: 1 })).toBeInTheDocument()
  })

  it('is refused to students', async () => {
    fakeApi({ user: ada })
    renderApp('/staff/content')
    expect(await screen.findByText('Only team members can open this page.')).toBeInTheDocument()
  })
})
