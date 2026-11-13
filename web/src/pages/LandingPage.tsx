import { Link } from 'react-router'
import { buttonVariants } from '@/components/ui/button-variants'
import mark from '../mark.svg'
import { ThemeToggle } from '../theme/ThemeToggle.tsx'
import styles from './LandingPage.module.css'

const MODULES: [string, string][] = [
  [
    'Warm-up and queue refresher',
    'A short check of queues, lists and loops, with a refresher only where you need one.',
  ],
  [
    'What is a graph?',
    'Vertices, edges, directed and undirected graphs, and turning a campus map into a graph.',
  ],
  [
    'A graph in Python',
    'Store a graph as a dictionary of neighbours, and write add_vertex and add_edge.',
  ],
  [
    'Meet BFS',
    'What breadth-first search is for, and tracing it by hand: the queue, the visited set, the order.',
  ],
  ['Build BFS', 'Write bfs(graph, start) yourself, with less help each time.'],
  ['Test and debug', 'Find the bug in a faulty BFS, and choose the test cases that expose it.'],
  [
    'Mastery check and report',
    'New questions on every objective, then a report of what to review before the lecture.',
  ],
]

const STEPS: [string, string][] = [
  [
    'See it worked, then try it',
    'Each idea comes as a worked example first, then a question of your own, with the help fading as you go.',
  ],
  [
    'Hints when you are stuck',
    'Four hints on every question, from a nudge to the worked answer. Feedback says why, not only "wrong".',
  ],
  [
    'Check what you know',
    'The mastery check asks new questions on each objective. Anything not met yet gets its own short review path.',
  ],
  [
    'Arrive ready',
    'Your report shows what you have mastered, so the lecture builds on it instead of starting from zero.',
  ],
]

const PRACTICE = [
  'Put lines of code in order (Parsons problems)',
  'Fill in the missing code',
  'Trace BFS step by step in a table',
  'Draw graphs and read them',
  'Find and fix the bug',
  'Choose the tests that catch a bug',
  'Videos that stop to ask you a question',
  'A BFS visualiser you can step through',
]

const RESEARCH: [string, string][] = [
  ['Worked examples, then fading', 'Sweller (1988); Renkl & Atkinson (2003)'],
  ['Mastery learning with review paths', 'Bloom (1984); Guskey (2007)'],
  ['Feedback that explains', 'Hattie & Timperley (2007); Shute (2008)'],
  ['Practice by answering, not rereading', 'Roediger & Karpicke (2006)'],
  ['Badges for skills, no leaderboard', 'Deci, Koestner & Ryan (1999); Hamari et al. (2014)'],
  ['Accessible to everyone', 'WCAG 2.1 AA, keyboard and screen reader, light and dark'],
]

/** A small graph, coloured by how far BFS has to go from the start: the course in one picture. */
function HeroGraph() {
  const vertices: [string, number, number, number][] = [
    ['A', 60, 110, 0],
    ['B', 160, 50, 1],
    ['C', 160, 170, 1],
    ['D', 270, 30, 2],
    ['E', 270, 120, 2],
    ['F', 270, 200, 2],
    ['G', 370, 80, 3],
  ]
  const edges = [
    ['A', 'B'],
    ['A', 'C'],
    ['B', 'D'],
    ['B', 'E'],
    ['C', 'E'],
    ['C', 'F'],
    ['D', 'G'],
    ['E', 'G'],
  ]
  const at = Object.fromEntries(vertices.map(([v, x, y]) => [v, [x, y]]))
  return (
    <svg
      viewBox="0 0 430 240"
      className={styles.graph}
      // An inline SVG drawing needs role="img" to be read as one image with a name.
      // oxlint-disable-next-line jsx-a11y/prefer-tag-over-role
      role="img"
      aria-label="A graph of seven vertices. Breadth-first search from A reaches B and C first, then D, E and F, then G."
    >
      {edges.map(([a, b]) => (
        <line key={a + b} x1={at[a][0]} y1={at[a][1]} x2={at[b][0]} y2={at[b][1]} />
      ))}
      {vertices.map(([v, x, y, level]) => (
        <g key={v} data-level={level}>
          <circle cx={x} cy={y} r={22} />
          <text x={x} y={y} dy="0.35em">
            {v}
          </text>
        </g>
      ))}
    </svg>
  )
}

/**
 * `/` for a visitor who isn't logged in: what Ctrl Academy is, who it is for, what is in it and
 * why it is built the way it is, with the way in. A logged-in student gets their modules instead.
 */
export function LandingPage() {
  return (
    <div className={styles.page}>
      <a className={styles.skip} href="#main">
        Skip to content
      </a>
      <header className={styles.header}>
        <div className={styles.bar}>
          <Link to="/" className={styles.brand}>
            <img src={mark} alt="" className={styles.logo} />
            <span>Ctrl Academy</span>
          </Link>
          <div className={styles.headerActions}>
            <ThemeToggle />
            <Link to="/login" className={`${buttonVariants({ variant: 'ghost' })} ${styles.logIn}`}>
              Log in
            </Link>
            <Link to="/register" className={buttonVariants({ variant: 'default' })}>
              Sign up
            </Link>
          </div>
        </div>
      </header>

      <main id="main">
        <section className={styles.hero}>
          <div className={styles.heroText}>
            <h1>Learn graphs and breadth-first search before your lecture</h1>
            <p className={styles.lead}>
              A self-paced course for students who have never met a graph. Seven short modules take
              you from what a graph is to writing, testing and debugging BFS in Python.
            </p>
            <div className={styles.cta}>
              <Link to="/register" className={buttonVariants({ variant: 'default', size: 'lg' })}>
                Create a free account
              </Link>
              <Link to="/login" className={buttonVariants({ variant: 'outline', size: 'lg' })}>
                I have an account
              </Link>
            </div>
          </div>
          <div className={styles.heroArt}>
            <HeroGraph />
            <ol className={styles.legend} aria-label="Visit order">
              <li data-level="0">Start</li>
              <li data-level="1">1 step</li>
              <li data-level="2">2 steps</li>
              <li data-level="3">3 steps</li>
            </ol>
          </div>
        </section>

        <section className={styles.band} aria-labelledby="how">
          <div className={styles.inner}>
            <h2 id="how">How it works</h2>
            <ol className={styles.steps}>
              {STEPS.map(([title, text], i) => (
                <li key={title} className={styles.step}>
                  <span className={styles.stepNumber} aria-hidden="true">
                    {i + 1}
                  </span>
                  <h3>{title}</h3>
                  <p>{text}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className={styles.section} aria-labelledby="modules">
          <div className={styles.inner}>
            <h2 id="modules">What you will learn</h2>
            <ol className={styles.modules}>
              {MODULES.map(([title, text], i) => (
                <li key={title} className={styles.module}>
                  <span className={styles.moduleNumber}>{i}</span>
                  <div>
                    <h3>{title}</h3>
                    <p>{text}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>
        </section>

        <section className={styles.band} aria-labelledby="practice">
          <div className={`${styles.inner} ${styles.split}`}>
            <div>
              <h2 id="practice">Learn by doing</h2>
              <p>
                You answer something every few minutes, in eight kinds of activity, each built for
                one part of thinking about graphs and code.
              </p>
            </div>
            <ul className={styles.ticks}>
              {PRACTICE.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </div>
        </section>

        <section className={styles.section} aria-labelledby="research">
          <div className={styles.inner}>
            <h2 id="research">Built on how people learn</h2>
            <p className={styles.sectionLead}>
              Each design choice comes from the research on teaching and learning, not from habit.
            </p>
            <dl className={styles.research}>
              {RESEARCH.map(([what, source]) => (
                <div key={what}>
                  <dt>{what}</dt>
                  <dd>{source}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        <section className={styles.final} aria-labelledby="start">
          <h2 id="start">Ready to start?</h2>
          <p>It's free, and needs only a name, an email address and a password.</p>
          <Link to="/register" className={buttonVariants({ variant: 'default', size: 'lg' })}>
            Create a free account
          </Link>
        </section>
      </main>

      <footer className={styles.footer}>
        <p>
          Ctrl Academy, made by Ctrl Group for COS750 Educational Software Development at the
          University of Pretoria, 2026.
        </p>
        <p>We keep only what the course needs: your name, email address and progress (POPIA).</p>
      </footer>
    </div>
  )
}
