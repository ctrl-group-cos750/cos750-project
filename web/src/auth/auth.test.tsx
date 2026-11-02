import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { fakeApi, renderApp } from '../test/app.tsx'

describe('log-in page', () => {
  it('asks for both fields before sending anything', async () => {
    const api = fakeApi()
    renderApp('/login')
    await userEvent.click(await screen.findByRole('button', { name: 'Log in' }))
    expect(screen.getByLabelText('Email')).toHaveAccessibleDescription('Enter your email address.')
    expect(screen.getByLabelText('Password')).toHaveAccessibleDescription('Enter your password.')
    expect(screen.getByLabelText('Email')).toHaveFocus()
    expect(api.callsTo('POST /api/auth/login')).toHaveLength(0)
  })

  it('explains what a valid email looks like', async () => {
    fakeApi()
    renderApp('/login')
    await userEvent.type(await screen.findByLabelText('Email'), 'ada@')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
    expect(screen.getByLabelText('Email')).toHaveAccessibleDescription(
      'Enter an email address like name@tuks.co.za.',
    )
  })

  it('logs in and returns to the page the student asked for', async () => {
    const api = fakeApi()
    renderApp('/')
    await userEvent.type(await screen.findByLabelText('Email'), ' ada@example.com ')
    await userEvent.type(screen.getByLabelText('Password'), 'Correct horse 1')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('heading', { name: 'Welcome, Ada' })).toBeInTheDocument()
    expect(api.callsTo('POST /api/auth/login')[0].body).toEqual({
      email: 'ada@example.com',
      password: 'Correct horse 1',
    })
  })

  it.each([
    ['a wrong password', 401, 'Email or password is incorrect.'],
    ['too many attempts', 429, 'Too many attempts. Wait a minute and try again.'],
  ])('shows the reason for %s', async (_case, status, detail) => {
    fakeApi({
      overrides: { 'POST /api/auth/login': () => Response.json({ detail }, { status }) },
    })
    renderApp('/login')
    await userEvent.type(await screen.findByLabelText('Email'), 'ada@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'wrong horse')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(detail)
    expect(screen.getByRole('heading', { name: 'Log in' })).toBeInTheDocument()
  })

  it('says when it cannot reach the server', async () => {
    fakeApi({
      overrides: { 'POST /api/auth/login': () => Promise.reject(new TypeError('Failed to fetch')) },
    })
    renderApp('/login')
    await userEvent.type(await screen.findByLabelText('Email'), 'ada@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'Correct horse 1')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      "Can't reach Ctrl Academy. Check your connection and try again.",
    )
  })

  it('links to the register page', async () => {
    fakeApi()
    renderApp('/login')
    await userEvent.click(await screen.findByRole('link', { name: 'Create an account' }))
    expect(screen.getByRole('heading', { name: 'Create your account' })).toBeInTheDocument()
  })
})

async function fillRegistration(name: string, email: string, password: string) {
  if (name) await userEvent.type(await screen.findByLabelText('Your name'), name)
  if (email) await userEvent.type(screen.getByLabelText('Email'), email)
  if (password) await userEvent.type(screen.getByLabelText('Password'), password)
  await userEvent.click(screen.getByRole('button', { name: 'Create account' }))
}

describe('register page', () => {
  it('says what is kept and why (POPIA)', async () => {
    fakeApi()
    renderApp('/register')
    const notice = await screen.findByRole('region', { name: 'What we keep' })
    expect(notice).toHaveTextContent('Your email, to log you in.')
    expect(notice).toHaveTextContent('Nobody else sees your progress.')
  })

  it('checks every field before sending anything', async () => {
    const api = fakeApi()
    renderApp('/register')
    await screen.findByLabelText('Your name')
    await fillRegistration('', '', '')
    expect(screen.getByLabelText('Your name')).toHaveAccessibleDescription(
      'Enter the name you want to see in the app.',
    )
    expect(screen.getByLabelText('Email')).toHaveAccessibleDescription('Enter your email address.')
    expect(screen.getByLabelText('Password')).toHaveAccessibleDescription(
      expect.stringContaining('Choose a password.'),
    )
    expect(screen.getByLabelText('Your name')).toHaveFocus()
    expect(api.callsTo('POST /api/auth/register')).toHaveLength(0)
  })

  it('asks for a longer password', async () => {
    fakeApi()
    renderApp('/register')
    await fillRegistration('Ada', 'ada@example.com', 'short')
    expect(screen.getByLabelText('Password')).toHaveAccessibleDescription(
      expect.stringContaining('Use at least 8 characters.'),
    )
    expect(screen.getByLabelText('Password')).toHaveFocus()
  })

  it('lists the password rules and ticks them off while the student types', async () => {
    fakeApi()
    renderApp('/register')
    const rules = await screen.findByRole('list', { name: 'Your password needs' })
    const line = (text: string) => within(rules).getByText(text, { exact: false })
    expect(line('An uppercase letter')).toHaveTextContent('still needed')
    expect(screen.getByLabelText('Password')).toHaveAccessibleDescription(
      expect.stringContaining('At least 8 characters'),
    )
    await userEvent.type(screen.getByLabelText('Password'), 'Violet otter 41')
    for (const text of [
      'At least 8 characters',
      'A lowercase letter',
      'An uppercase letter',
      'A number',
      'A symbol',
      'Not your name or email',
    ]) {
      expect(line(text)).toHaveTextContent('done')
    }
  })

  it('says which rule a password breaks before sending it', async () => {
    const api = fakeApi()
    renderApp('/register')
    await fillRegistration('Ada', 'ada@example.com', 'violet otter 41')
    expect(screen.getByLabelText('Password')).toHaveAccessibleDescription(
      expect.stringContaining('Use at least one uppercase letter.'),
    )
    expect(api.callsTo('POST /api/auth/register')).toHaveLength(0)
  })

  it("refuses a password containing the student's own name", async () => {
    fakeApi()
    renderApp('/register')
    await fillRegistration('Grace', 'g@example.com', 'Grace rocks 1!')
    expect(screen.getByLabelText('Password')).toHaveAccessibleDescription(
      expect.stringContaining("Don't use your name or email in your password."),
    )
  })

  it('creates the account and goes straight into the app', async () => {
    const api = fakeApi()
    renderApp('/register')
    await fillRegistration('  Grace ', 'grace@example.com', 'Correct horse 1')
    expect(await screen.findByRole('heading', { name: 'Welcome, Grace' })).toBeInTheDocument()
    expect(api.callsTo('POST /api/auth/register')[0].body).toEqual({
      displayName: 'Grace',
      email: 'grace@example.com',
      password: 'Correct horse 1',
    })
  })

  it('shows a taken email next to the email field', async () => {
    const detail = 'An account with this email already exists.'
    fakeApi({
      overrides: { 'POST /api/auth/register': () => Response.json({ detail }, { status: 409 }) },
    })
    renderApp('/register')
    await fillRegistration('Ada', 'ada@example.com', 'Correct horse 1')
    expect(await screen.findByText(detail)).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toHaveAccessibleDescription(detail)
    expect(screen.getByLabelText('Email')).toHaveFocus()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows a password the API refuses next to the password field', async () => {
    const msg = "Don't use your name or email in your password."
    fakeApi({
      overrides: {
        'POST /api/auth/register': () =>
          Response.json(
            { detail: [{ loc: ['body', 'password'], msg, type: 'value_error' }] },
            { status: 422 },
          ),
      },
    })
    renderApp('/register')
    await fillRegistration('Ada', 'ada@example.com', 'Violet otter 41')
    expect(await screen.findByText(msg)).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toHaveAccessibleDescription(
      expect.stringContaining(msg),
    )
    expect(screen.getByLabelText('Password')).toHaveFocus()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows other failures above the form', async () => {
    fakeApi({
      overrides: { 'POST /api/auth/register': () => new Response('oops', { status: 500 }) },
    })
    renderApp('/register')
    await fillRegistration('Ada', 'ada@example.com', 'Correct horse 1')
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Something went wrong. Try again in a moment.',
    )
  })

  it('links back to the log-in page', async () => {
    fakeApi()
    renderApp('/register')
    await userEvent.click(await screen.findByRole('link', { name: 'Log in' }))
    expect(screen.getByRole('heading', { name: 'Log in' })).toBeInTheDocument()
  })
})
