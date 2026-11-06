import { useState, type FormEvent } from 'react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { Spinner } from '@/components/ui/spinner'
import { TextField } from '@/components/ui/text-field'
import { ACHIEVEMENTS, AchievementBadge, AppShell, MasteryStatus } from '../components'
import { BfsStatesSample } from './BfsStatesSample.tsx'
import styles from './UiKitPage.module.css'

const colours: { token: string; use: string }[] = [
  { token: '--color-bg', use: 'Page background' },
  { token: '--color-surface', use: 'Cards, inputs, header' },
  { token: '--color-surface-sunken', use: 'Code blocks, tracks, neutral tags' },
  { token: '--color-text', use: 'Body text' },
  { token: '--color-text-muted', use: 'Hints, captions, secondary text' },
  { token: '--color-line', use: 'Dividers and card edges' },
  { token: '--color-border', use: 'Input and control borders' },
  { token: '--color-accent', use: 'Primary buttons, progress, focus ring' },
  { token: '--color-accent-soft', use: 'Info backgrounds, selected items' },
  { token: '--color-success', use: 'Correct answers, met objectives' },
  { token: '--color-warning', use: 'Hints that cost support, "not yet"' },
  { token: '--color-danger', use: 'Errors and destructive actions only' },
]

const typeScale = [
  { token: '--text-3xl', sample: 'Page title', tag: 'h1' },
  { token: '--text-2xl', sample: 'Section heading', tag: 'h2' },
  { token: '--text-xl', sample: 'Card heading', tag: 'h3' },
  { token: '--text-md', sample: 'Body text for explanations and prompts.', tag: 'p' },
  { token: '--text-sm', sample: 'Hints, captions and help under fields.', tag: 'p' },
] as const

type Theme = 'system' | 'light' | 'dark'

function setTheme(theme: Theme) {
  if (theme === 'system') delete document.documentElement.dataset.theme
  else document.documentElement.dataset.theme = theme
}

export function UiKitPage() {
  const [theme, setThemeState] = useState<Theme>('system')
  const [submitted, setSubmitted] = useState(false)

  function chooseTheme(next: Theme) {
    setTheme(next)
    setThemeState(next)
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    setSubmitted(true)
  }

  return (
    <AppShell
      nav={
        <>
          {[
            ['#colours', 'Colours'],
            ['#components', 'Components'],
            ['#badges', 'Badges'],
            ['#bfs', 'BFS states'],
          ].map(([href, text]) => (
            <a key={href} href={href} className="px-2 py-1">
              {text}
            </a>
          ))}
        </>
      }
      actions={
        <fieldset className={styles.themes}>
          <legend className="visually-hidden">Theme</legend>
          {(['system', 'light', 'dark'] as const).map((t) => (
            <Button
              key={t}
              size="sm"
              variant={theme === t ? 'default' : 'outline'}
              aria-pressed={theme === t}
              onClick={() => chooseTheme(t)}
            >
              {t[0].toUpperCase() + t.slice(1)}
            </Button>
          ))}
        </fieldset>
      }
    >
      <h1>Ctrl Academy UI kit</h1>
      <p className={styles.lead}>
        The shared look of the app. Build screens from these components and tokens rather than new
        colours or one-off styles. Controls are shadcn/ui components in{' '}
        <code>web/src/components/ui/</code>, themed from <code>web/src/styles/tokens.css</code>.
        Guidance: <code>docs/brand/README.md</code>.
      </p>

      <section id="colours" className={styles.section}>
        <h2>Colours</h2>
        <p>
          Use the token, never the hex value: the values change in dark mode. Every text colour
          meets WCAG 2.1 AA.
        </p>
        <ul className={styles.swatches}>
          {colours.map(({ token, use }) => (
            <li key={token} className={styles.swatch}>
              <span className={styles.chip} style={{ background: `var(${token})` }} />
              <code>{token}</code>
              <span className={styles.muted}>{use}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className={styles.section}>
        <h2>Type</h2>
        <p>Headings use Space Grotesk, body text the system font, and code JetBrains Mono.</p>
        <Card className="px-4">
          {typeScale.map(({ token, sample, tag: Element }) => (
            <div key={token} className={styles.typeRow}>
              <code className={styles.muted}>{token}</code>
              <Element style={{ fontSize: `var(${token})`, margin: 0 }}>{sample}</Element>
            </div>
          ))}
          <div className={styles.typeRow}>
            <code className={styles.muted}>--font-mono</code>
            <pre className={styles.code}>{'queue.append(start)\nvisited = {start}'}</pre>
          </div>
        </Card>
      </section>

      <section id="components" className={styles.section}>
        <h2>Buttons</h2>
        <p>
          One default (primary) button per screen, for the main action. Destructive only for things
          that delete.
        </p>
        <div className={styles.row}>
          <Button size="lg">Start module</Button>
          <Button size="lg" variant="outline">
            Show a hint
          </Button>
          <Button size="lg" variant="secondary">
            Back
          </Button>
          <Button size="lg" variant="ghost">
            Skip example
          </Button>
          <Button size="lg" variant="destructive">
            Reset progress
          </Button>
          <Button size="lg" variant="link">
            Read the worked example
          </Button>
          <Button size="lg" loading>
            Submitting
          </Button>
          <Button size="lg" disabled>
            Locked
          </Button>
          <Button size="sm" variant="outline">
            Small
          </Button>
        </div>
      </section>

      <section className={styles.section}>
        <h2>Form fields</h2>
        <p>Every field has a visible label. Errors say what to do next.</p>
        <Card className={styles.form}>
          <CardContent>
            <form onSubmit={onSubmit} noValidate className="grid gap-4">
              <TextField
                label="Email"
                type="email"
                autoComplete="email"
                defaultValue="student@"
                error="Enter an email address like name@tuks.co.za."
              />
              <TextField
                label="Password"
                type="password"
                autoComplete="current-password"
                hint="At least 8 characters."
              />
              <Button type="submit" size="lg" className="justify-self-start">
                Log in
              </Button>
            </form>
            {submitted && (
              <Alert variant="success" className="mt-4">
                <AlertDescription>This is only a sample form.</AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      </section>

      <section className={styles.section}>
        <h2>Alerts</h2>
        <div className="grid gap-3">
          <Alert variant="info">
            <AlertTitle>Before you start</AlertTitle>
            <AlertDescription>
              This module takes about 10 minutes. Your progress is saved as you go.
            </AlertDescription>
          </Alert>
          <Alert variant="success">
            <AlertTitle>Correct</AlertTitle>
            <AlertDescription>D is next: it was queued before E. +10 points.</AlertDescription>
          </Alert>
          <Alert variant="warning">
            <AlertTitle>This hint shows part of the answer</AlertTitle>
            <AlertDescription>
              Using it now counts this objective as "met with support".
            </AlertDescription>
          </Alert>
          <Alert variant="destructive">
            <AlertTitle>Could not save</AlertTitle>
            <AlertDescription>Check your connection and try again.</AlertDescription>
          </Alert>
        </div>
      </section>

      <section className={styles.section}>
        <h2>Status badges and mastery</h2>
        <p>
          Badges sit inline next to what they describe. Mastery results always use{' '}
          <code>MasteryStatus</code> so the wording matches the ID document.
        </p>
        <div className={styles.row}>
          <MasteryStatus mastery="independent" />
          <MasteryStatus mastery="supported" />
          <MasteryStatus mastery="not-yet" />
        </div>
        <div className={styles.row}>
          <Badge variant="secondary">Locked</Badge>
          <Badge variant="accent">In progress</Badge>
          <Badge variant="success" icon="✓">
            Done
          </Badge>
          <Badge variant="warning">Review</Badge>
        </div>
      </section>

      <section className={styles.section}>
        <h2>Cards and progress</h2>
        <div className={styles.grid}>
          <Card>
            <CardHeader>
              <CardTitle>3. Meet BFS</CardTitle>
              <CardDescription>About 12 minutes</CardDescription>
            </CardHeader>
            <CardContent>
              <Progress label="Module 3 progress" value={4} max={7} showCount />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Mastery check</CardTitle>
              <CardDescription>Unlocks after module 5</CardDescription>
            </CardHeader>
            <CardContent>
              <Badge variant="secondary">Locked</Badge>
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Loading</CardTitle>
            </CardHeader>
            <CardContent>
              <Spinner label="Loading the module" />
            </CardContent>
          </Card>
        </div>
      </section>

      <section id="badges" className={styles.section}>
        <h2>Badges</h2>
        <p>
          Private badges (FR-9.3). Objective badges are hexagons with two tiers: bronze when the
          objective was met with support, gold (an inner outline and a star) when it was later met
          independently. Milestones are medals, quests are shields, and the hidden badge is a
          diamond that shows &ldquo;?&rdquo; until it is found. Locked badges are dashed, faded and
          carry a padlock. Every state differs in shape, not only colour.
        </p>
        <ul className={styles.badges}>
          {ACHIEVEMENTS.map((achievement) => (
            <li key={achievement.id} className={styles.badgeItem}>
              <div className={styles.badgeStates}>
                {achievement.kind === 'objective' ? (
                  <>
                    <AchievementBadge achievement={achievement} state="gold" />
                    <AchievementBadge achievement={achievement} state="bronze" size={40} />
                  </>
                ) : (
                  <AchievementBadge achievement={achievement} state="earned" />
                )}
                <AchievementBadge achievement={achievement} state="locked" size={40} />
              </div>
              <strong>{achievement.name}</strong>
              <span className={styles.muted}>{achievement.description}</span>
            </li>
          ))}
        </ul>
      </section>

      <section id="bfs" className={styles.section}>
        <h2>BFS vertex states</h2>
        <p>
          The visualiser shows each state with a colour, a symbol and the vertex label, never colour
          alone. Tokens: <code>--bfs-*</code>.
        </p>
        <Card>
          <CardContent>
            <BfsStatesSample />
          </CardContent>
        </Card>
      </section>
    </AppShell>
  )
}
