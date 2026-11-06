import type { ReactNode } from 'react'
import { Card, CardContent } from '@/components/ui/card'
import mark from '../mark.svg'

/** The frame for the log-in and register pages: logo, one card, a link to the other page. */
export function AuthLayout({
  title,
  intro,
  footer,
  children,
}: {
  title: string
  intro: string
  footer: ReactNode
  children: ReactNode
}) {
  return (
    <main className="grid min-h-screen place-items-center px-4 py-8">
      <div className="w-full max-w-104">
        <div className="mb-6 flex items-center justify-center gap-2 font-heading text-xl font-bold">
          <img src={mark} alt="" className="h-10" />
          <span>Ctrl Academy</span>
        </div>
        <Card className="py-6">
          <CardContent className="px-6">
            <h1 className="text-2xl">{title}</h1>
            <p className="text-muted-foreground">{intro}</p>
            {children}
          </CardContent>
        </Card>
        <p className="mt-6 text-center">{footer}</p>
      </div>
    </main>
  )
}
