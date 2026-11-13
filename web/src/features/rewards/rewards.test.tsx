import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ada, fakeApi, renderApp } from '../../test/app.tsx'
import type { EarnedBadge, Rewards } from './rewards.api.ts'
import { buildShelf, unseen } from './shelf.ts'

function badge(id: string, more: Partial<EarnedBadge> = {}): EarnedBadge {
  return {
    badge: id,
    ref: '',
    tier: null,
    awardedAt: '2026-11-05T10:00:00Z',
    upgradedAt: null,
    seen: true,
    ...more,
  }
}

function withRewards(rewards: Rewards) {
  let current = rewards
  return fakeApi({
    user: ada,
    overrides: {
      'GET /api/rewards': () => Response.json(current),
      'POST /api/rewards/seen': () => {
        current = { ...current, badges: current.badges.map((b) => ({ ...b, seen: true })) }
        return Response.json(current)
      },
      'PUT /api/rewards/settings': (body) => {
        current = { ...current, ...(body as { hideRewards: boolean }) }
        return Response.json(current)
      },
    },
  })
}

describe('buildShelf', () => {
  it('shows every badge, earned or not, with how to earn the locked ones', () => {
    const shelf = buildShelf([badge('lo5', { tier: 'gold' }), badge('lo2', { tier: 'bronze' })])
    expect(shelf.objective).toHaveLength(8)
    const states = Object.fromEntries(shelf.objective.map((i) => [i.achievement.id, i.state]))
    expect(states).toMatchObject({ lo5: 'gold', lo2: 'bronze', lo1: 'locked' })
    expect(shelf.objective.find((i) => i.achievement.id === 'lo1')?.next).toBe(
      'Meet learning objective 1.',
    )
    expect(shelf.objective.find((i) => i.achievement.id === 'lo2')?.next).toBe(
      'Met with support. Gold is for meeting it without hint 3 or 4.',
    )
    expect(shelf.milestone.map((i) => i.state)).toEqual(['locked', 'locked', 'locked', 'locked'])
  })

  it('offers Shortcut Finder now that objective 8 is assessed (#70)', () => {
    const ids = buildShelf([]).objective.map((i) => i.achievement.id)
    expect(ids).toEqual(['lo1', 'lo2', 'lo3', 'lo4', 'lo5', 'lo6', 'lo7', 'lo8'])
    expect(buildShelf([]).objective.find((i) => i.achievement.id === 'lo8')?.next).toBe(
      'Meet learning objective 8.',
    )
  })

  it('gives each finished quest its own badge, numbered in course order', () => {
    // A quest badge's ref is the quest's activity id; the shelf numbers them for display (#196).
    const shelf = buildShelf([badge('quest', { ref: '480' }), badge('quest', { ref: '380' })])
    expect(shelf.quest.map((i) => i.title)).toEqual(['Quest 1', 'Quest 2', 'All Quests'])
    expect(shelf.quest.map((i) => i.key)).toEqual(['quest:380', 'quest:480', 'all-quests'])
    expect(buildShelf([]).quest.map((i) => i.state)).toEqual(['locked', 'locked'])
  })

  it('announces a new quest by its number', () => {
    const fresh = unseen([
      badge('quest', { ref: '380' }),
      badge('quest', { ref: '480', seen: false }),
    ])
    expect(fresh.map((i) => i.title)).toEqual(['Quest 2'])
  })

  it('says First Module needs a right answer before hint 3, not just a finished module', () => {
    // Module 0's diagnostic earns no module reward, so the badge comes with the first module
    // answered right on your own, which isn't always module 1 (#212 review).
    const firstModule = (earned: EarnedBadge[]) =>
      buildShelf(earned).milestone.find((i) => i.achievement.id === 'first-module')
    expect(firstModule([])?.next).toBe(
      'Finish a module with at least one answer right before hint 3.',
    )
    expect(firstModule([])?.achievement.description).toBe(
      'You worked all the way through a module and got answers right on your own.',
    )
    expect(firstModule([badge('first-module')])?.next).toBeUndefined()
  })

  it('ignores badge ids the app does not know', () => {
    expect(unseen([badge('retired', { seen: false })])).toEqual([])
  })
})

describe('Badges page', () => {
  it('shows the student their points and badges', async () => {
    withRewards({
      hideRewards: false,
      points: 145,
      badges: [badge('lo5', { tier: 'gold' }), badge('lo2', { tier: 'bronze' })],
    })
    renderApp('/badges')
    expect(await screen.findByRole('heading', { level: 1, name: 'Your badges' })).toBeVisible()
    expect(screen.getByText('145')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Queue Tracer, gold, met independently' })).toBeVisible()
    expect(
      screen.getByRole('img', { name: 'Edge Spotter, bronze, met with support' }),
    ).toBeVisible()
    expect(screen.getByRole('img', { name: 'Word Smith, not earned yet' })).toBeVisible()
    expect(screen.getByRole('img', { name: 'First Module, not earned yet' })).toBeVisible()
    // No hidden badge exists today, so its group isn't shown as an empty heading (#166 review).
    expect(screen.queryByRole('heading', { name: 'Something to find' })).toBeNull()
  })

  it('can hide points and badges, and show them again', async () => {
    const api = withRewards({ hideRewards: false, points: 30, badges: [badge('lo1')] })
    renderApp('/badges')
    const toggle = await screen.findByRole('checkbox', { name: 'Hide points and badges' })
    await userEvent.click(toggle)
    expect(await screen.findByText('Points and badges are hidden.')).toBeVisible()
    expect(screen.queryByText('30')).not.toBeInTheDocument()
    expect(api.callsTo('PUT /api/rewards/settings')[0].body).toEqual({ hideRewards: true })
    await userEvent.click(screen.getByRole('checkbox', { name: 'Hide points and badges' }))
    expect(await screen.findByText('30')).toBeVisible()
  })

  it('is linked from the account menu', async () => {
    withRewards({ hideRewards: false, points: 0, badges: [] })
    renderApp('/')
    await userEvent.click(await screen.findByRole('button', { name: /your account/ }))
    expect(screen.getByRole('link', { name: 'Badges' })).toHaveAttribute('href', '/badges')
  })
})

describe('Badge announcements', () => {
  it('announces a new badge once, then tells the server it was seen', async () => {
    const api = withRewards({
      hideRewards: false,
      points: 15,
      badges: [badge('lo5', { tier: 'bronze', seen: false })],
    })
    renderApp('/')
    expect(await screen.findByText('Queue Tracer')).toBeVisible()
    await waitFor(() => expect(api.callsTo('POST /api/rewards/seen')).toHaveLength(1))
    await userEvent.click(screen.getByRole('button', { name: 'Dismiss Queue Tracer' }))
    expect(screen.queryByText('Queue Tracer')).not.toBeInTheDocument()
  })

  it('collapses a burst of badges into a "more" line', async () => {
    withRewards({
      hideRewards: false,
      points: 75,
      badges: ['lo1', 'lo2', 'lo3', 'lo4', 'lo5'].map((id) =>
        badge(id, { tier: 'bronze', seen: false }),
      ),
    })
    renderApp('/')
    expect(await screen.findByText('2 more new badges')).toBeVisible()
    expect(screen.getByText('Queue Tracer')).toBeVisible()
    expect(screen.queryByText('Word Smith')).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Dismiss all' }))
    expect(screen.queryByText('Queue Tracer')).not.toBeInTheDocument()
  })

  it('says when a badge goes up to gold', async () => {
    withRewards({
      hideRewards: false,
      points: 30,
      badges: [badge('lo5', { tier: 'gold', seen: false, upgradedAt: '2026-11-05T11:00:00Z' })],
    })
    renderApp('/')
    expect(await screen.findByText('Queue Tracer is now gold')).toBeVisible()
  })

  it('celebrates being ready for the lecture in a dialog', async () => {
    withRewards({
      hideRewards: false,
      points: 300,
      badges: [badge('ready-for-lecture', { seen: false })],
    })
    renderApp('/')
    const dialog = await screen.findByRole('dialog', { name: "You're ready for the lecture" })
    expect(dialog).toHaveFocus()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Close' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    // Focus goes back to the page, not <body> (A1).
    expect(screen.getByRole('heading', { level: 1 })).toHaveFocus()
  })

  it('moves focus to the next note when one is dismissed, then back to the page (A5)', async () => {
    withRewards({
      hideRewards: false,
      points: 30,
      badges: ['lo4', 'lo5'].map((id) => badge(id, { tier: 'bronze', seen: false })),
    })
    renderApp('/')
    const first = await screen.findByRole('button', { name: 'Dismiss Queue Tracer' })
    first.focus()
    await userEvent.keyboard('{Enter}')
    const next = screen.getByRole('button', { name: /^Dismiss / })
    expect(next).toHaveFocus()
    await userEvent.keyboard('{Enter}')
    expect(screen.queryByRole('button', { name: /^Dismiss / })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1 })).toHaveFocus()
  })

  it('shows a phone one card for a burst of badges (D9)', async () => {
    vi.stubGlobal('matchMedia', (query: string) => ({
      matches: query === '(max-width: 480px)',
      addEventListener: () => {},
      removeEventListener: () => {},
    }))
    withRewards({
      hideRewards: false,
      points: 75,
      badges: ['lo1', 'lo2', 'lo3'].map((id) => badge(id, { tier: 'bronze', seen: false })),
    })
    renderApp('/')
    expect(await screen.findByText('3 new badges')).toBeVisible()
    expect(screen.queryByText('Queue Tracer')).not.toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: /^Dismiss/ })).toHaveLength(1)
  })

  it('announces nothing while rewards are hidden', async () => {
    const api = withRewards({
      hideRewards: true,
      points: 15,
      badges: [badge('lo5', { tier: 'bronze', seen: false })],
    })
    renderApp('/')
    await screen.findByRole('heading', { level: 1 })
    await waitFor(() => expect(api.callsTo('GET /api/rewards')).toHaveLength(1))
    expect(screen.queryByText('Queue Tracer')).not.toBeInTheDocument()
    expect(api.callsTo('POST /api/rewards/seen')).toHaveLength(0)
  })

  it('can turn badges off from the note, and says where to turn them back on', async () => {
    const api = withRewards({
      hideRewards: false,
      points: 15,
      badges: [badge('lo5', { tier: 'bronze', seen: false })],
    })
    renderApp('/')
    expect(await screen.findByText('Queue Tracer')).toBeVisible()
    await userEvent.click(screen.getByRole('button', { name: 'Turn off badges' }))
    expect(await screen.findByText('Badges and points are off')).toBeVisible()
    expect(api.callsTo('PUT /api/rewards/settings')[0]!.body).toEqual({ hideRewards: true })
    expect(screen.queryByText('Queue Tracer')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'profile' })).toHaveAttribute(
      'href',
      '/profile#what-you-see',
    )
  })
})
