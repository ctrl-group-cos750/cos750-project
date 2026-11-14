import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ada, fakeApi, renderApp } from '../test/app.tsx'
import { applyBackground } from './background.ts'

const html = document.documentElement

beforeEach(() => {
  window.localStorage.clear()
  delete html.dataset.bg
  delete html.dataset.theme
})

async function home() {
  fakeApi({ user: ada })
  renderApp('/')
  await screen.findByRole('heading', { name: 'Graphs and breadth-first search' })
}

describe('page background (#214)', () => {
  it('is the glow by default, with see-through cards on the module map', async () => {
    await home()
    expect(html.dataset.bg).toBe('glow')
    expect(screen.getByRole('main')).toHaveAttribute('data-surfaces', 'tinted')
  })

  it.each([
    ['/modules/1', 'solid'],
    ['/activities/3', 'solid'],
    ['/modules/1/check', 'solid'],
    ['/profile', 'solid'],
    ['/staff', 'solid'],
    ['/badges', 'tinted'],
    ['/report', 'tinted'],
  ])('on %s the cards are %s', async (path, surfaces) => {
    fakeApi({ user: { ...ada, isStaff: true } })
    const view = renderApp(path)
    await waitFor(() => expect(view.container.querySelector('main')).not.toBeNull())
    expect(view.container.querySelector('main')).toHaveAttribute('data-surfaces', surfaces)
  })

  it('switches from the header menu, with Light and Dark beside it, and is kept per student', async () => {
    await home()
    const trigger = screen.getByRole('button', { name: 'Theme and background' })
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    await userEvent.click(trigger)
    expect(trigger).toHaveAttribute('aria-expanded', 'true')

    const background = screen.getByRole('group', { name: 'Background' })
    expect(within(background).getByRole('radio', { name: 'Glow' })).toBeChecked()
    await userEvent.click(within(background).getByRole('radio', { name: 'Doodles' }))
    expect(html.dataset.bg).toBe('doodles')
    expect(window.localStorage.getItem(`ctrl-academy.${ada.id}.background`)).toBe('doodles')

    await userEvent.click(within(background).getByRole('radio', { name: 'Plain' }))
    expect(html.dataset.bg).toBe('plain')

    const theme = screen.getByRole('group', { name: 'Theme' })
    await userEvent.click(within(theme).getByRole('radio', { name: 'Dark' }))
    expect(html.dataset.theme).toBe('dark')
    expect(window.localStorage.getItem('ctrl-academy-theme')).toBe('dark')

    // Escape closes it and puts focus back on the button.
    await userEvent.keyboard('{Escape}')
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    expect(trigger).toHaveFocus()
  })

  it('is chosen in the profile too, with a picture of each, and both stay in step', async () => {
    fakeApi({ user: ada })
    renderApp('/profile')
    const group = await screen.findByRole('group', { name: 'Background' })
    const radios = within(group).getAllByRole('radio')
    expect(radios.map((r) => r.getAttribute('value'))).toEqual(['glow', 'doodles', 'plain'])
    expect(group.querySelectorAll('[data-swatch]')).toHaveLength(3)
    expect(within(group).getByRole('radio', { name: 'Glow' })).toBeChecked()

    await userEvent.click(within(group).getByRole('radio', { name: 'Plain' }))
    expect(html.dataset.bg).toBe('plain')

    await userEvent.click(screen.getByRole('button', { name: 'Theme and background' }))
    const menu = screen
      .getAllByRole('group', { name: 'Background' })
      .find((g) => g !== group) as HTMLElement
    expect(within(menu).getByRole('radio', { name: 'Plain' })).toBeChecked()
  })

  it("does not carry one student's background to the next on the same device", async () => {
    window.localStorage.setItem('ctrl-academy.99.background', 'plain')
    await home()
    expect(html.dataset.bg).toBe('glow')
  })

  it('is plain under forced colours (high contrast), whatever was chosen', () => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn((query: string) => ({ matches: query.includes('forced-colors'), media: query })),
    )
    applyBackground({ background: 'doodles' })
    expect(html.dataset.bg).toBe('plain')
  })
})
