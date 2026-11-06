import { Badge, type BadgeVariant } from './ui/badge'

/** The three results per objective: ID document §3.2, SE document FR-7.2. */
export type Mastery = 'independent' | 'supported' | 'not-yet'

const display: Record<Mastery, { text: string; variant: BadgeVariant; icon: string }> = {
  independent: { text: 'Met independently', variant: 'success', icon: '✓' },
  supported: { text: 'Met with support', variant: 'accent', icon: '◐' },
  'not-yet': { text: 'Not yet', variant: 'warning', icon: '○' },
}

/**
 * "Not yet" is amber, not red: it means "review this before the lecture", not
 * "you failed". Use this everywhere a mastery result is shown so the wording
 * and colours never drift.
 */
export function MasteryStatus({ mastery }: { mastery: Mastery }) {
  const { text, variant, icon } = display[mastery]
  return (
    <Badge variant={variant} icon={icon}>
      {text}
    </Badge>
  )
}
