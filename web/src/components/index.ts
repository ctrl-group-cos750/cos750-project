// App-level components, built only from the shadcn/ui controls in ./ui. Import controls
// (Button, Card, Alert, Badge, TextField, ...) from '@/components/ui/<name>', and these from
// here: `import { AppShell, MasteryStatus } from '../components'`.
// Every component is shown on /ui-kit.html; see docs/brand/README.md for when to use which.
export {
  AchievementBadge,
  type AchievementBadgeProps,
  type AchievementState,
} from './AchievementBadge.tsx'
export {
  ACHIEVEMENTS,
  type Achievement,
  type AchievementGlyph,
  type AchievementKind,
} from './achievements.ts'
export { AppShell, type AppShellProps } from './AppShell.tsx'
export { ErrorBoundary } from './errors/ErrorBoundary.tsx'
export { ErrorPage, type ErrorPageProps } from './errors/ErrorPage.tsx'
export { MasteryStatus, type Mastery } from './MasteryStatus.tsx'
