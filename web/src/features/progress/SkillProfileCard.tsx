import { useId } from 'react'
import { Card } from '../../components'
import { HiddenNote } from './HiddenNote.tsx'
import { useSkills } from './hooks.ts'
import { PanelHeader } from './PanelHeader.tsx'
import { usePanelMinimised } from './preferences.ts'
import { SkillProfile } from './SkillProfile.tsx'
import { SkillRadar } from './SkillRadar.tsx'
import type { Skill } from './skills.api.ts'
import { useHideable } from './useHideable.ts'
import styles from './progress.module.css'

function note(checked: boolean): string {
  return checked
    ? 'Your results from the mastery check, with your practice before it. Open an objective for the detail.'
    : 'How your practice is going on each of the eight objectives. The mastery check in module 6 adds gold, or a review path bronze or gold after a not yet. Open an objective for the detail.'
}

/** The skill profile as a card with its own heading, for the mastery report (#214): the list
 * with its bars. Says nothing while it loads or if it can't be had: the page works without it. */
export function SkillProfileCard({
  id = 'skill-profile',
  className,
}: {
  id?: string
  className?: string
}) {
  const skills = useSkills()
  if (!skills.data || skills.data.objectives.length === 0) return null
  const objectives = skills.data.objectives
  return (
    <Card className={className}>
      <section aria-labelledby={id} className={styles.profileCard}>
        <h2 id={id} className={styles.profileHeading}>
          Skill profile
        </h2>
        <p className={styles.profileNote}>{note(objectives.some((s) => s.result !== null))}</p>
        <SkillProfile skills={objectives} />
      </section>
    </Card>
  )
}

/**
 * The skill profile on the home page (#214): the radar chart, with the list in words under it.
 * Its heading minimises it to the header and opens it again (kept on this device); its "⋯" turns
 * it off ("Hide skill profile"), leaving a note with the way back. Off in the profile, nothing.
 */
export function HomeSkillProfile() {
  const skills = useSkills()
  const { on, justHidden, hide, undo } = useHideable('skillProfile')
  const [minimised, setMinimised] = usePanelMinimised('skillProfile')
  const id = 'skill-profile'
  const body = useId()
  if (justHidden) return <HiddenNote text="Skill profile hidden." onUndo={undo} />
  if (!on || !skills.data || skills.data.objectives.length === 0) return null
  const objectives: Skill[] = skills.data.objectives
  return (
    <Card>
      <section aria-labelledby={id} className={styles.profileCard}>
        <PanelHeader
          id={id}
          title="Skill profile"
          minimised={minimised}
          onToggle={() => setMinimised(!minimised)}
          controls={body}
          hide={[{ label: 'Hide skill profile', onSelect: hide }]}
        />
        <div id={body} hidden={minimised} className={styles.profileBody}>
          <p className={styles.profileNote}>{note(objectives.some((s) => s.result !== null))}</p>
          <SkillRadar skills={objectives} />
          <SkillProfile skills={objectives} bars={false} />
        </div>
      </section>
    </Card>
  )
}
