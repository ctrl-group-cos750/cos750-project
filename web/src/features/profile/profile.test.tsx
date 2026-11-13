import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import type { User } from '../../auth/api.ts'
import { ada, fakeApi, renderApp } from '../../test/app.tsx'
import type { MasteryReport } from '../mastery/mastery.api.ts'
import * as picture from './squarePicture.ts'

function report(states: string[]): MasteryReport {
  return {
    ready: states.every((s) => s.startsWith('met_')),
    objectives: states.map((state, i) => ({
      id: i + 1,
      text: `Objective ${i + 1}`,
      criterion: 'c',
      state: state as MasteryReport['objectives'][number]['state'],
      answered: 1,
      total: 1,
      review: null,
    })),
  }
}

function setup({
  hideRewards = false,
  states = ['met_independently', 'met_with_support', 'not_yet'],
  password = (): Response => new Response(null, { status: 204 }),
  slowAvatar = false,
}: {
  slowAvatar?: boolean
  hideRewards?: boolean
  states?: string[]
  password?: (body: unknown) => Response
} = {}) {
  let me: User = { ...ada }
  return fakeApi({
    user: ada,
    overrides: {
      'GET /api/auth/me': () => Response.json(me),
      'GET /api/rewards': () =>
        Response.json({
          hideRewards,
          points: 120,
          badges: [
            { badge: 'lo1', ref: '', tier: 'gold', awardedAt: '', upgradedAt: null, seen: true },
          ],
        }),
      'GET /api/me/report': () => Response.json(report(states)),
      'PUT /api/me/avatar': async (body) => {
        if (slowAvatar) await new Promise((resolve) => setTimeout(resolve, 100))
        me = { ...me, ...(body as { avatar: User['avatar'] }) }
        return Response.json(me)
      },
      'PUT /api/me/picture': () => {
        me = { ...me, avatar: null, pictureUrl: '/api/me/picture?v=1' }
        return Response.json(me)
      },
      'DELETE /api/me/picture': () => {
        me = { ...me, pictureUrl: null }
        return Response.json(me)
      },
      'POST /api/me/password': password,
    },
  })
}

const openMenu = async () =>
  userEvent.click(await screen.findByRole('button', { name: /your account/ }))

describe('account menu', () => {
  it('opens to the profile, badges and log out, and closes with Escape', async () => {
    setup()
    renderApp('/')
    const trigger = await screen.findByRole('button', { name: /Ada: your account/ })
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('link', { name: 'Profile and settings' })).toHaveAttribute(
      'href',
      '/profile',
    )
    expect(screen.getByRole('link', { name: 'Badges' })).toHaveAttribute('href', '/badges')
    expect(screen.getByRole('button', { name: 'Log out' })).toBeVisible()

    await userEvent.keyboard('{Escape}')
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(trigger).toHaveFocus()
    expect(screen.queryByRole('link', { name: 'Profile and settings' })).toBeNull()
  })

  it('closes when Tab leaves it (A12)', async () => {
    setup()
    renderApp('/')
    await openMenu()
    screen.getByRole('button', { name: 'Log out' }).focus()
    await userEvent.tab()
    expect(screen.queryByRole('link', { name: 'Profile and settings' })).toBeNull()
    expect(screen.getByRole('button', { name: /your account/ })).toHaveAttribute(
      'aria-expanded',
      'false',
    )
  })

  it('closes on a click outside it, and after choosing a page', async () => {
    setup()
    renderApp('/')
    await openMenu()
    await userEvent.click(screen.getByRole('heading', { name: 'Graphs and breadth-first search' }))
    expect(screen.queryByRole('link', { name: 'Profile and settings' })).toBeNull()

    await openMenu()
    await userEvent.click(screen.getByRole('link', { name: 'Profile and settings' }))
    expect(await screen.findByRole('heading', { name: 'Ada' })).toBeVisible()
    expect(screen.queryByRole('link', { name: 'Profile and settings' })).toBeNull()
  })
})

describe('profile page', () => {
  it('shows the student their own progress', async () => {
    setup()
    renderApp('/profile')
    const stats = await screen.findByRole('region', { name: 'Your progress' })
    expect(await within(stats).findByText('2 of 3')).toBeVisible() // objectives met
    expect(await within(stats).findByText('120')).toBeVisible() // points
    expect(within(stats).getByText('Badges')).toBeVisible()
    expect(within(stats).getByRole('link', { name: 'See your mastery report' })).toHaveAttribute(
      'href',
      '/report',
    )
  })

  it('leaves points and badges out when they are hidden, but never the results', async () => {
    setup({ hideRewards: true })
    renderApp('/profile')
    const stats = await screen.findByRole('region', { name: 'Your progress' })
    expect(await within(stats).findByText('2 of 3')).toBeVisible()
    expect(within(stats).queryByText('Points')).toBeNull()
    expect(within(stats).queryByRole('link', { name: 'See your badges' })).toBeNull()
    expect(screen.getByRole('checkbox', { name: 'Hide points and badges' })).toBeChecked()
  })

  it('says when the student is ready for the lecture', async () => {
    setup({ states: ['met_independently', 'met_with_support'] })
    renderApp('/profile')
    expect(await screen.findByText("You're ready for the lecture.")).toBeVisible()
  })

  it('saves a chosen picture and shows it in the menu', async () => {
    const api = setup()
    renderApp('/profile')
    await userEvent.click(await screen.findByRole('radio', { name: 'A tree' }))
    await waitFor(() => expect(api.callsTo('PUT /api/me/avatar')).toHaveLength(1))
    expect(api.callsTo('PUT /api/me/avatar')[0]!.body).toEqual({ avatar: 'tree' })
    expect(await screen.findByText('Saved.')).toBeVisible()
    expect(screen.getByRole('radio', { name: 'A tree' })).toBeChecked()
    expect(screen.getByRole('radio', { name: 'Your initial' })).not.toBeChecked()
  })

  it('keeps focus on the pictures while arrowing through them, and saves the last (A2)', async () => {
    const api = setup({ slowAvatar: true })
    renderApp('/profile')
    await userEvent.click(await screen.findByRole('radio', { name: 'A tree' }))
    await userEvent.keyboard('{ArrowRight}{ArrowRight}')
    // Still saving the tree: the radios stay enabled, so focus stays on the one chosen.
    const focused = document.activeElement as HTMLInputElement
    expect(focused).toHaveAttribute('type', 'radio')
    expect(focused).toBeChecked()
    expect(focused).not.toBeDisabled()
    expect(api.callsTo('PUT /api/me/avatar')).toHaveLength(1)
    await waitFor(() =>
      expect(api.callsTo('PUT /api/me/avatar').at(-1)!.body).toEqual({ avatar: 'grid' }),
    )
    await screen.findByText('Saved.')
    expect(document.activeElement).toBe(focused)
  })
})

describe('changing the password', () => {
  const field = (name: string) => screen.getByLabelText(name, { selector: 'input' })

  it('sends the current and new password, then clears the form', async () => {
    const api = setup()
    renderApp('/profile')
    await screen.findByRole('heading', { name: 'Change your password' })
    await userEvent.type(field('Current password'), 'Correct horse 1')
    await userEvent.type(field('New password'), 'Purple kettle 42')
    await userEvent.type(field('New password again'), 'Purple kettle 42')
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }))

    expect(await screen.findByText('Password changed')).toBeVisible()
    expect(api.callsTo('POST /api/me/password')[0]!.body).toEqual({
      currentPassword: 'Correct horse 1',
      newPassword: 'Purple kettle 42',
    })
    expect(field('Current password')).toHaveValue('')
  })

  it('checks the form before sending anything', async () => {
    const api = setup()
    renderApp('/profile')
    await screen.findByRole('heading', { name: 'Change your password' })
    await userEvent.type(field('New password'), 'Purple kettle 42')
    await userEvent.type(field('New password again'), 'Purple kettle 43')
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }))

    expect(screen.getByText('Enter your current password.')).toBeVisible()
    expect(screen.getByText("The two new passwords don't match.")).toBeVisible()
    expect(field('Current password')).toHaveFocus()
    expect(api.callsTo('POST /api/me/password')).toHaveLength(0)
  })

  it('puts a wrong current password next to that field', async () => {
    setup({
      password: () =>
        Response.json({ detail: 'Your current password is not right.' }, { status: 400 }),
    })
    renderApp('/profile')
    await screen.findByRole('heading', { name: 'Change your password' })
    await userEvent.type(field('Current password'), 'Not it 1!')
    await userEvent.type(field('New password'), 'Purple kettle 42')
    await userEvent.type(field('New password again'), 'Purple kettle 42')
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }))

    expect(await screen.findByText('Your current password is not right.')).toBeVisible()
    expect(field('Current password')).toHaveAttribute('aria-invalid', 'true')
    expect(field('Current password')).toHaveFocus()
  })
})

describe('an uploaded picture (FR-1.6)', () => {
  it('uploads the picture, shows it here and in the menu, and removes it', async () => {
    const calls = setup()
    // jsdom has no canvas: the square is made by a real browser (e2e); here, the upload itself.
    const square = vi
      .spyOn(picture, 'squarePicture')
      .mockResolvedValue('data:image/webp;base64,AA==')
    renderApp('/profile')
    await screen.findByRole('heading', { name: 'Profile picture' })
    expect(screen.queryByRole('button', { name: 'Remove it' })).toBeNull()

    const input = document.querySelector<HTMLInputElement>('input[type="file"]')!
    await userEvent.upload(input, new File(['x'], 'me.jpg', { type: 'image/jpeg' }))
    await screen.findByRole('button', { name: 'Remove it' })
    expect(calls.callsTo('PUT /api/me/picture')[0]?.body).toEqual({
      image: 'data:image/webp;base64,AA==',
    })
    expect(screen.getByRole('img', { name: 'Your picture' })).toHaveAttribute(
      'src',
      '/api/me/picture?v=1',
    )
    expect(screen.getByText('Saved.')).toBeVisible()

    await userEvent.click(screen.getByRole('button', { name: 'Remove it' }))
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Remove it' })).toBeNull())
    // Focus goes to the upload button, not the page (A2).
    expect(screen.getByRole('button', { name: 'Upload a picture' })).toHaveFocus()
    square.mockRestore()
  })

  it('refuses a file that is not a picture, saying why', async () => {
    setup()
    renderApp('/profile')
    await screen.findByRole('heading', { name: 'Profile picture' })
    const input = document.querySelector<HTMLInputElement>('input[type="file"]')
    expect(input).not.toBeNull()
    await userEvent.upload(input!, new File(['hello'], 'notes.txt', { type: 'text/plain' }), {
      applyAccept: false,
    })
    expect(await screen.findByText(/Choose a picture/)).toBeVisible()
  })
})
