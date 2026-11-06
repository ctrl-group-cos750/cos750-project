import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { Alert, AlertDescription, AlertTitle } from './ui/alert'
import { Badge } from './ui/badge'
import { Button } from './ui/button'
import { Card, CardContent } from './ui/card'
import { Progress } from './ui/progress'
import { Spinner } from './ui/spinner'
import { TextField } from './ui/text-field'
import {
  ACHIEVEMENTS,
  AchievementBadge,
  AppShell,
  ErrorBoundary,
  ErrorPage,
  MasteryStatus,
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
        <Alert variant="destructive">
          <AlertDescription>Could not save</AlertDescription>
        </Alert>
        <Alert variant="success">
          <AlertDescription>Saved</AlertDescription>
        </Alert>
      </>,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('Could not save')
    expect(screen.getByRole('status')).toHaveTextContent('Saved')
  })

  it('shows a title', () => {
    render(
      <Alert variant="success">
        <AlertTitle>Correct</AlertTitle>
        <AlertDescription>D is next.</AlertDescription>
      </Alert>,
    )
    expect(screen.getByText('Correct')).toBeInTheDocument()
    expect(screen.getByText('D is next.')).toBeInTheDocument()
  })
})

describe('Alert icons', () => {
  it('gives each tone an icon, so the meaning never relies on colour alone', () => {
    const { container } = render(
      <Alert variant="warning">
        <AlertDescription>Careful</AlertDescription>
      </Alert>,
    )
    expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
  })

  it('can leave the icon out', () => {
    const { container } = render(
      <Alert variant="info" icon={false}>
        <AlertDescription>Note</AlertDescription>
      </Alert>,
    )
    expect(container.querySelector('svg')).toBeNull()
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

describe('Badge', () => {
  it('hides its icon from screen readers', () => {
    render(<Badge icon="✓">Done</Badge>)
    expect(screen.getByText('✓')).toHaveAttribute('aria-hidden', 'true')
    expect(screen.getByText('Done')).toBeInTheDocument()
  })
})

describe('Progress', () => {
  it('reports its value to assistive technology', () => {
    render(<Progress label="Module 3 progress" value={4} max={7} showCount />)
    const bar = screen.getByRole('progressbar', { name: 'Module 3 progress' })
    expect(bar).toHaveAttribute('value', '4')
    expect(bar).toHaveAttribute('max', '7')
    expect(screen.getByText('4 of 7')).toBeInTheDocument()
  })

  it('keeps the value within range', () => {
    render(<Progress label="Progress" value={12} max={10} />)
    expect(screen.getByRole('progressbar')).toHaveAttribute('value', '10')
  })

  it('copes with a max of zero', () => {
    render(<Progress label="Progress" value={0} max={0} />)
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
    render(
      <Card>
        <CardContent>Module 1</CardContent>
      </Card>,
    )
    expect(screen.getByText('Module 1')).toBeInTheDocument()
  })
})

describe('AppShell', () => {
  it('has a skip link, the brand, navigation and the page in main', () => {
    render(
      <MemoryRouter>
        <AppShell nav={<a href="/modules">Modules</a>} actions={<Button>Log out</Button>}>
          <h1>Module map</h1>
        </AppShell>
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: 'Skip to content' })).toHaveAttribute('href', '#main')
    expect(screen.getByRole('link', { name: 'Ctrl Academy' })).toHaveAttribute('href', '/')
    expect(screen.getByRole('navigation', { name: 'Main' })).toContainElement(
      screen.getByRole('link', { name: 'Modules' }),
    )
    expect(screen.getByRole('main')).toContainElement(
      screen.getByRole('heading', { name: 'Module map' }),
    )
    expect(screen.getByRole('button', { name: 'Log out' })).toBeInTheDocument()
  })

  it('leaves out the navigation when there is none', () => {
    render(
      <MemoryRouter>
        <AppShell>Page</AppShell>
      </MemoryRouter>,
    )
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

  it('keeps the hidden badge secret until it is found', () => {
    const { rerender } = render(
      <AchievementBadge achievement={byId('off-the-map')} state="locked" />,
    )
    expect(screen.getByRole('img', { name: 'Hidden badge, not found yet' })).toBeInTheDocument()
    expect(screen.queryByText(/Off the Map/)).not.toBeInTheDocument()
    rerender(<AchievementBadge achievement={byId('off-the-map')} state="earned" />)
    expect(screen.getByRole('img', { name: 'Off the Map, earned' })).toBeInTheDocument()
  })

  it('has one badge per learning objective, and no ids repeat', () => {
    const objectives = ACHIEVEMENTS.filter((a) => a.kind === 'objective').map((a) => a.objective)
    expect(objectives).toEqual([1, 2, 3, 4, 5, 6, 7, 8])
    expect(new Set(ACHIEVEMENTS.map((a) => a.id)).size).toBe(ACHIEVEMENTS.length)
  })
})

describe('ErrorPage', () => {
  it('explains the problem and links back to the modules', () => {
    render(
      <MemoryRouter>
        <ErrorPage title="We can't find that page">
          <p>The link may be out of date.</p>
        </ErrorPage>
      </MemoryRouter>,
    )
    expect(screen.getByRole('heading', { level: 1, name: "We can't find that page" })).toBeVisible()
    expect(screen.getByRole('link', { name: 'Go to your modules' })).toHaveAttribute('href', '/')
    expect(screen.queryByRole('button', { name: 'Reload the page' })).not.toBeInTheDocument()
  })
})

describe('ErrorBoundary', () => {
  function Broken(): never {
    throw new Error('TypeError: cannot read properties of undefined (reading "segments")')
  }

  it('shows a message for students in place of a crashed page, never the error itself', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    render(
      <MemoryRouter>
        <ErrorBoundary>
          <Broken />
        </ErrorBoundary>
      </MemoryRouter>,
    )
    expect(screen.getByRole('heading', { name: 'Something went wrong on this page' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'Reload the page' })).toBeVisible()
    expect(screen.queryByText(/TypeError|segments/)).not.toBeInTheDocument()
    consoleError.mockRestore()
  })

  it('recovers when the reset key changes, e.g. on navigating to another page', () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    const { rerender } = render(
      <MemoryRouter>
        <ErrorBoundary resetKey="/broken">
          <Broken />
        </ErrorBoundary>
      </MemoryRouter>,
    )
    rerender(
      <MemoryRouter>
        <ErrorBoundary resetKey="/badges">
          <p>Your badges</p>
        </ErrorBoundary>
      </MemoryRouter>,
    )
    expect(screen.getByText('Your badges')).toBeVisible()
    consoleError.mockRestore()
  })
})
