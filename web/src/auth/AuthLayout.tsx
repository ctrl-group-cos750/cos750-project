import type { ReactNode } from 'react'
import { Card } from '../components'
import mark from '../mark.svg'
import { ThemeToggle } from '../theme/ThemeToggle.tsx'
import styles from './AuthLayout.module.css'

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
    <main className={styles.page}>
      <div className={styles.theme}>
        <ThemeToggle />
      </div>
      <div className={styles.column}>
        <div className={styles.brand}>
          <img src={mark} alt="" className={styles.mark} />
          <span>Ctrl Academy</span>
        </div>
        <Card>
          <h1 className={styles.title}>{title}</h1>
          <p className={styles.intro}>{intro}</p>
          {children}
        </Card>
        <p className={styles.footer}>{footer}</p>
      </div>
    </main>
  )
}
