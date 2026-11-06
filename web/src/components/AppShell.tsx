import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { cn } from 'cn'
import mark from '../mark.svg'

export type AppShellProps = {
  /** Links in the header: the module map, points and badges, the staff portal. */
  nav?: ReactNode
  /** Right side of the header: the user's name, Log out. */
  actions?: ReactNode
  /** "reading" keeps text lines short; "wide" is for the module map and the BFS visualiser. */
  width?: 'reading' | 'wide'
  children: ReactNode
}

/** The frame around every page: a skip link, the header, then the page in <main>. */
export function AppShell({ nav, actions, width = 'wide', children }: AppShellProps) {
  return (
    <>
      <a
        href="#main"
        className="absolute -top-12 left-4 z-10 rounded-md bg-primary px-3 py-2 text-primary-foreground no-underline focus:top-2"
      >
        Skip to content
      </a>
      <header className="border-b bg-card">
        <div className="mx-auto flex max-w-(--content-width) flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <Link
            to="/"
            className="flex items-center gap-2 font-heading text-lg font-bold text-foreground no-underline"
          >
            <img src={mark} alt="" className="h-8" />
            <span>Ctrl Academy</span>
          </Link>
          {nav && (
            <nav
              aria-label="Main"
              className="order-3 flex w-full flex-wrap gap-1 sm:order-none sm:w-auto"
            >
              {nav}
            </nav>
          )}
          {actions && <div className="ml-auto flex items-center gap-3">{actions}</div>}
        </div>
      </header>
      <main
        id="main"
        tabIndex={-1}
        className={cn(
          'mx-auto px-4 pt-8 pb-16 outline-none',
          width === 'reading' ? 'max-w-(--reading-width)' : 'max-w-(--content-width)',
        )}
      >
        {children}
      </main>
    </>
  )
}
