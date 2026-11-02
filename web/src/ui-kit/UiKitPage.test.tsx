import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import { UiKitPage } from './UiKitPage.tsx'

afterEach(() => {
  delete document.documentElement.dataset.theme
})

describe('UiKitPage', () => {
  it('shows every section of the kit', () => {
    render(<UiKitPage />)
    expect(
      screen.getByRole('heading', { level: 1, name: 'Ctrl Academy UI kit' }),
    ).toBeInTheDocument()
    for (const name of [
      'Colours',
      'Type',
      'Buttons',
      'Form fields',
      'Alerts',
      'BFS vertex states',
    ]) {
      expect(screen.getByRole('heading', { level: 2, name })).toBeInTheDocument()
    }
    expect(screen.getByRole('img', { name: /Sample graph/ })).toBeInTheDocument()
  })

  it('switches between light, dark and the system theme', async () => {
    render(<UiKitPage />)
    await userEvent.click(screen.getByRole('button', { name: 'Dark' }))
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(screen.getByRole('button', { name: 'Dark' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: 'Light' }))
    expect(document.documentElement.dataset.theme).toBe('light')
    await userEvent.click(screen.getByRole('button', { name: 'System' }))
    expect(document.documentElement.dataset.theme).toBeUndefined()
  })

  it('confirms the sample form without sending anything', async () => {
    render(<UiKitPage />)
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
    expect(screen.getByText('This is only a sample form.')).toBeInTheDocument()
  })
})
