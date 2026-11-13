import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import {
  ACHIEVEMENTS,
  AchievementBadge,
  Alert,
  AppShell,
  Button,
  Card,
  MasteryStatus,
  ProgressBar,
  Spinner,
  Tag,
  TextField,
} from './index.ts'

describe('Button', () => {
  it('is a plain button by default, so it never submits a form by accident', () => {
    render(<Button>Save</Button>)
    expect(screen.getByRole('button', { name: 'Save' })).toHaveAttribute('type', 'button')
  })

  it('calls onClick', async () => {
    const onClick = vi.fn<() => void>()
    render(<Button onClick={onClick}>Save</Button>)
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('is disabled and busy while loading', async () => {
    const onClick = vi.fn<() => void>()
    render(
      <Button loading onClick={onClick}>
        Save
      </Button>,
    )
    const button = screen.getByRole('button', { name: 'Save' })
    expect(button).toBeDisabled()
    expect(button).toHaveAttribute('aria-busy', 'true')
    await userEvent.click(button)
    expect(onClick).not.toHaveBeenCalled()
  })

  it('keeps focus while loading when asked to: busy, aria-disabled, and presses ignored', async () => {
    const user = userEvent.setup()
    const onClick = vi.fn<() => void>()
    const onSubmit = vi.fn<(event: React.FormEvent) => void>((event) => event.preventDefault())
    render(
      <form onSubmit={onSubmit}>
        <input aria-label="Answer" />
        <Button type="submit" loading keepFocusWhileLoading onClick={onClick}>
          Check answer
        </Button>
      </form>,
    )
    const button = screen.getByRole('button', { name: 'Check answer' })
    expect(button).toBeEnabled() // so it can keep focus
    expect(button).toHaveAttribute('aria-disabled', 'true')
    expect(button).toHaveAttribute('aria-busy', 'true')
    button.focus()
    await user.keyboard('{Enter}')
    await user.keyboard(' ')
    await user.click(button)
    // Enter in a field submits a form by clicking its submit button: blocked too.
    await user.type(screen.getByRole('textbox', { name: 'Answer' }), 'x{Enter}')
    expect(onClick).not.toHaveBeenCalled()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('works as normal once loading ends, with keepFocusWhileLoading set', async () => {
    const onClick = vi.fn<() => void>()
    render(
      <Button keepFocusWhileLoading onClick={onClick}>
        Save
      </Button>,
    )
    const button = screen.getByRole('button', { name: 'Save' })
    expect(button).not.toHaveAttribute('aria-disabled')
    expect(button).not.toHaveAttribute('aria-busy')
    await userEvent.click(button)
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('can submit a form when asked to', () => {
    render(<Button type="submit">Log in</Button>)
    expect(screen.getByRole('button', { name: 'Log in' })).toHaveAttribute('type', 'submit')
  })
})

describe('TextField', () => {
  it('labels the input', () => {
    render(<TextField label="Email" />)
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
  })

  it('links the hint to the input', () => {
    render(<TextField label="Password" hint="At least 8 characters." />)
    const input = screen.getByLabelText('Password')
    expect(input).toHaveAccessibleDescription('At least 8 characters.')
    expect(input).not.toBeInvalid()
  })

  it('shows the error instead of the hint and marks the input invalid', () => {
    render(
      <TextField label="Email" hint="Your university email." error="Enter an email address." />,
    )
    const input = screen.getByLabelText('Email')
    expect(input).toBeInvalid()
    expect(input).toHaveAccessibleDescription('Enter an email address.')
    expect(screen.queryByText('Your university email.')).not.toBeInTheDocument()
  })

  it('passes typing through', async () => {
    render(<TextField label="Email" />)
    await userEvent.type(screen.getByLabelText('Email'), 'a@b.co')
    expect(screen.getByLabelText('Email')).toHaveValue('a@b.co')
  })
})

describe('Alert', () => {
  it('interrupts screen readers for errors only', () => {
    render(
      <>
        <Alert tone="danger">Could not save</Alert>
        <Alert tone="success">Saved</Alert>
      </>,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('Could not save')
    expect(screen.getByRole('status')).toHaveTextContent('Saved')
  })

  it('shows a title', () => {
    render(<Alert title="Correct">D is next.</Alert>)
    expect(screen.getByText('Correct')).toBeInTheDocument()
    expect(screen.getByText('D is next.')).toBeInTheDocument()
  })
})

describe('MasteryStatus', () => {
  it.each([
    ['independent', 'Met independently'],
    ['supported', 'Met with support'],
    ['not-yet', 'Not yet'],
  ] as const)('shows %s as "%s"', (mastery, text) => {
    render(<MasteryStatus mastery={mastery} />)
    expect(screen.getByText(text)).toBeInTheDocument()
  })
})

describe('Tag', () => {
  it('hides its icon from screen readers', () => {
    render(<Tag icon="✓">Done</Tag>)
    expect(screen.getByText('✓')).toHaveAttribute('aria-hidden', 'true')
    expect(screen.getByText('Done')).toBeInTheDocument()
  })
})

describe('ProgressBar', () => {
  it('reports its value to assistive technology', () => {
    render(<ProgressBar label="Module 3 progress" value={4} max={7} showCount />)
    const bar = screen.getByRole('progressbar', { name: 'Module 3 progress' })
    expect(bar).toHaveAttribute('value', '4')
    expect(bar).toHaveAttribute('max', '7')
    expect(screen.getByText('4 of 7')).toBeInTheDocument()
  })

  it('keeps the value within range', () => {
    render(<ProgressBar label="Progress" value={12} max={10} />)
    expect(screen.getByRole('progressbar')).toHaveAttribute('value', '10')
  })

  it('copes with a max of zero', () => {
    render(<ProgressBar label="Progress" value={0} max={0} />)
    expect(screen.getByRole('progressbar')).toHaveAttribute('value', '0')
  })
})

describe('Spinner', () => {
  it('announces what is loading', () => {
    render(<Spinner label="Loading the module" />)
    expect(screen.getByRole('status')).toHaveTextContent('Loading the module')
  })

  it('is silent when the label is empty', () => {
    render(<Spinner label="" />)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})

describe('Card', () => {
  it('renders its children', () => {
    render(<Card interactive>Module 1</Card>)
    expect(screen.getByText('Module 1')).toBeInTheDocument()
  })
})

describe('AppShell', () => {
  it('has a skip link, the brand, navigation and the page in main', () => {
    render(
      <AppShell nav={<a href="/modules">Modules</a>} actions={<Button>Log out</Button>}>
        <h1>Module map</h1>
      </AppShell>,
    )
    expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveAttribute('href', '#main')
    expect(screen.getByRole('link', { name: /^Ctrl Academy/ })).toHaveAttribute('href', '/')
    expect(screen.getByRole('navigation', { name: 'Main' })).toContainElement(
      screen.getByRole('link', { name: 'Modules' }),
    )
    expect(screen.getByRole('main')).toContainElement(
      screen.getByRole('heading', { name: 'Module map' }),
    )
    expect(screen.getByRole('button', { name: 'Log out' })).toBeInTheDocument()
  })

  it('leaves out the navigation when there is none', () => {
    render(<AppShell>Page</AppShell>)
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
  })
})

describe('AchievementBadge', () => {
  const byId = (id: string) => ACHIEVEMENTS.find((a) => a.id === id)!

  it('names the badge and its tier, so the tier is never shown by colour alone', () => {
    render(<AchievementBadge achievement={byId('lo5')} state="gold" />)
    expect(
      screen.getByRole('img', { name: 'Queue Tracer, gold, met independently' }),
    ).toBeInTheDocument()
  })

  it('says a locked badge is not earned yet', () => {
    render(<AchievementBadge achievement={byId('lo5')} state="locked" />)
    expect(screen.getByRole('img', { name: 'Queue Tracer, not earned yet' })).toBeInTheDocument()
  })

  it('keeps a hidden badge secret until it is found', () => {
    // The catalogue has no hidden badge today (#141 removed Off the Map, which nothing could
    // earn), but the badge still supports one for the ID team to add.
    const secret = {
      id: 'secret',
      name: 'Secret Path',
      kind: 'hidden' as const,
      glyph: 'quest' as const,
      description: 'You found it.',
    }
    const { rerender } = render(<AchievementBadge achievement={secret} state="locked" />)
    expect(screen.getByRole('img', { name: 'Hidden badge, not found yet' })).toBeInTheDocument()
    expect(screen.queryByText(/Secret Path/)).not.toBeInTheDocument()
    rerender(<AchievementBadge achievement={secret} state="earned" />)
    expect(screen.getByRole('img', { name: 'Secret Path, earned' })).toBeInTheDocument()
  })

  it('has one badge per learning objective, and no ids repeat', () => {
    const objectives = ACHIEVEMENTS.filter((a) => a.kind === 'objective').map((a) => a.objective)
    expect(objectives).toEqual([1, 2, 3, 4, 5, 6, 7, 8])
    expect(new Set(ACHIEVEMENTS.map((a) => a.id)).size).toBe(ACHIEVEMENTS.length)
  })
})
