import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AppShell } from '../AppShell.tsx'
import { ErrorPage } from './ErrorPage.tsx'

type Props = {
  children: ReactNode
  /** Changing it clears the error, e.g. the URL, so navigating away recovers. */
  resetKey?: unknown
  /** Draw the header around the message: for the outermost boundary, which has no layout. */
  shell?: boolean
}

type State = { failed: boolean; resetKey: unknown }

/**
 * Catches a crash while rendering a page and shows a student-facing message in its place, so
 * one broken screen never leaves a blank app or shows a stack trace (NFR-U3). The details go to
 * the browser console for the team, not to the screen.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false, resetKey: this.props.resetKey }

  static getDerivedStateFromError(): Partial<State> {
    return { failed: true }
  }

  static getDerivedStateFromProps(props: Props, state: State): Partial<State> | null {
    if (props.resetKey !== state.resetKey) return { failed: false, resetKey: props.resetKey }
    return null
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('A page crashed', error, info.componentStack)
  }

  render() {
    if (!this.state.failed) return this.props.children
    const page = (
      <ErrorPage title="Something went wrong on this page" reload>
        <p>It's not something you did. Reload the page to try again, or go back to your modules.</p>
      </ErrorPage>
    )
    return this.props.shell ? <AppShell width="reading">{page}</AppShell> : page
  }
}
