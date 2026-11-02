import { Tag, type TagTone } from './Tag.tsx'

/** The three results per objective: ID document §3.2, SE document FR-7.2. */
export type Mastery = 'independent' | 'supported' | 'not-yet'

const display: Record<Mastery, { text: string; tone: TagTone; icon: string }> = {
  independent: { text: 'Met independently', tone: 'success', icon: '✓' },
  supported: { text: 'Met with support', tone: 'accent', icon: '◐' },
  'not-yet': { text: 'Not yet', tone: 'warning', icon: '○' },
}

/**
 * "Not yet" is amber, not red: it means "review this before the lecture", not
 * "you failed". Use this everywhere a mastery result is shown so the wording
 * and colours never drift.
 */
export function MasteryStatus({ mastery }: { mastery: Mastery }) {
  const { text, tone, icon } = display[mastery]
  return (
    <Tag tone={tone} icon={icon}>
      {text}
    </Tag>
  )
}
