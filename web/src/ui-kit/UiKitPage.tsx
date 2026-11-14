import { useState, type FormEvent } from 'react'
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
} from '../components'
import { BfsStatesSample } from './BfsStatesSample.tsx'
import styles from './UiKitPage.module.css'

const colours: { token: string; use: string }[] = [
  { token: '--color-bg', use: 'Page background' },
  { token: '--color-surface', use: 'Cards, inputs, header' },
  { token: '--color-surface-sunken', use: 'Code blocks, tracks, neutral tags' },
  { token: '--color-text', use: 'Body text' },
  { token: '--color-text-muted', use: 'Hints, captions, secondary text' },
  { token: '--color-line', use: 'Dividers and card edges' },
  { token: '--color-control-border', use: 'Input and control borders (3:1)' },
  { token: '--color-primary', use: 'Primary buttons, progress, focus ring' },
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
          <a href="#colours">Colours</a>
          <a href="#components">Components</a>
          <a href="#badges">Badges</a>
          <a href="#bfs">BFS states</a>
        </>
      }
      actions={
        <fieldset className={styles.themes}>
          <legend className="visually-hidden">Theme</legend>
          {(['system', 'light', 'dark'] as const).map((t) => (
            <Button
              key={t}
              size="sm"
              variant={theme === t ? 'primary' : 'secondary'}
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
        colours or one-off styles. Code: <code>web/src/components/</code> and{' '}
        <code>web/src/styles/tokens.css</code>. Guidance: <code>docs/brand/README.md</code>.
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
        <Card>
          {typeScale.map(({ token, sample, tag: Element }) => (
            <div key={token} className={styles.typeRow}>
              <code className={styles.muted}>{token}</code>
              <Element style={{ fontSize: `var(${token})`, margin: 0 }}>{sample}</Element>
            </div>
          ))}
          <div className={styles.typeRow}>
            <code className={styles.muted}>--font-mono</code>
            <pre className={styles.code}>{'queue.append(start)\nfound = {start}'}</pre>
          </div>
        </Card>
      </section>

      <section id="components" className={styles.section}>
        <h2>Buttons</h2>
        <p>
          One primary button per screen, for the main action. Danger only for things that delete.
        </p>
        <div className={styles.row}>
          <Button>Start module</Button>
          <Button variant="secondary">Show a hint</Button>
          <Button variant="ghost">Skip example</Button>
          <Button variant="danger">Reset progress</Button>
          <Button loading>Submitting</Button>
          <Button disabled>Locked</Button>
          <Button size="sm" variant="secondary">
            Small
          </Button>
        </div>
      </section>

      <section className={styles.section}>
        <h2>Form fields</h2>
        <p>Every field has a visible label. Errors say what to do next.</p>
        <Card className={styles.form}>
          <form onSubmit={onSubmit} noValidate>
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
            <Button type="submit">Log in</Button>
          </form>
          {submitted && <Alert tone="success">This is only a sample form.</Alert>}
        </Card>
      </section>

      <section className={styles.section}>
        <h2>Alerts</h2>
        <Alert tone="info" title="Before you start">
          This module takes about 10 minutes. Your progress is saved as you go.
        </Alert>
        <Alert tone="success" title="Correct">
          D is next: it was queued before E. +10 points.
        </Alert>
        <Alert tone="warning" title="This hint shows part of the answer">
          Using it now counts this objective as "met with support".
        </Alert>
        <Alert tone="danger" title="Could not save">
          Check your connection and try again.
        </Alert>
      </section>

      <section className={styles.section}>
        <h2>Status tags and mastery</h2>
        <p>
          Tags sit inline next to what they describe. Mastery results always use{' '}
          <code>MasteryStatus</code> so the wording matches the ID document.
        </p>
        <div className={styles.row}>
          <MasteryStatus mastery="independent" />
          <MasteryStatus mastery="supported" />
          <MasteryStatus mastery="not-yet" />
        </div>
        <div className={styles.row}>
          <Tag>Locked</Tag>
          <Tag tone="accent">In progress</Tag>
          <Tag tone="success" icon="✓">
            Done
          </Tag>
          <Tag tone="warning">Review</Tag>
        </div>
      </section>

      <section className={styles.section}>
        <h2>Cards and progress</h2>
        <div className={styles.grid}>
          <Card interactive>
            <h3>3. Meet BFS</h3>
            <p className={styles.muted}>About 12 minutes</p>
            <ProgressBar label="Module 3 progress" value={4} max={7} showCount />
          </Card>
          <Card>
            <h3>Mastery check</h3>
            <p className={styles.muted}>Unlocks after module 5</p>
            <Tag>Locked</Tag>
          </Card>
          <Card>
            <h3>Loading</h3>
            <Spinner label="Loading the module" />
          </Card>
        </div>
      </section>

      <section id="badges" className={styles.section}>
        <h2>Badges</h2>
        <p>
          Private badges (FR-9.3). Objective badges are hexagons with three levels: practised (an
          outline) when the objective is secure in the modules, bronze when it was met with support
          in the mastery check, gold (an inner outline and a star) when it was met independently.
          Milestones are medals, quests are shields, and the hidden badge is a diamond that shows
          &ldquo;?&rdquo; until it is found. Locked badges are dashed, faded and carry a padlock.
          Every state differs in shape, not only colour.
        </p>
        <ul className={styles.badges}>
          {ACHIEVEMENTS.map((achievement) => (
            <li key={achievement.id} className={styles.badgeItem}>
              <div className={styles.badgeStates}>
                {achievement.kind === 'objective' ? (
                  <>
                    <AchievementBadge achievement={achievement} state="gold" />
                    <AchievementBadge achievement={achievement} state="bronze" size={40} />
                    <AchievementBadge achievement={achievement} state="practised" size={40} />
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
          <BfsStatesSample />
        </Card>
      </section>
    </AppShell>
  )
}
