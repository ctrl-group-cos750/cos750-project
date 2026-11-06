import type { ReactNode } from 'react'
import { Link } from 'react-router'
import { buttonVariants } from '@/components/ui/button-variants'
import { Button } from '@/components/ui/button'

export type ErrorPageProps = {
  title: string
  children: ReactNode
  /** Offer to reload the page: for something that broke, not for a page that doesn't exist. */
  reload?: boolean
}

/**
 * What a student sees instead of a page: a plain explanation and a way back. Never a stack
 * trace or an error code (SE document NFR-U3).
 */
export function ErrorPage({ title, children, reload = false }: ErrorPageProps) {
  return (
    <section aria-labelledby="error-title" className="py-8">
      <h1 id="error-title">{title}</h1>
      <div className="text-muted-foreground">{children}</div>
      <div className="mt-6 flex flex-wrap gap-3">
        {reload && (
          <Button size="lg" onClick={() => window.location.reload()}>
            Reload the page
          </Button>
        )}
        <Link
          to="/"
          reloadDocument={reload}
          className={buttonVariants({ variant: reload ? 'outline' : 'default', size: 'lg' })}
        >
          Go to your modules
        </Link>
      </div>
    </section>
  )
}
