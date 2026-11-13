import { Card } from '../../components'
import { useSkills } from './hooks.ts'
import { SkillProfile } from './SkillProfile.tsx'
import styles from './progress.module.css'

/** The skill profile as a card with its own heading, for the module map and the mastery report
 * (#214). Says nothing while it loads or if it can't be had: the page works without it. */
export function SkillProfileCard({
  id = 'skill-profile',
  className,
}: {
  id?: string
  className?: string
}) {
  const skills = useSkills()
  if (!skills.data || skills.data.objectives.length === 0) return null
  const checked = skills.data.objectives.some((s) => s.result !== null)
  return (
    <Card className={className}>
      <section aria-labelledby={id} className={styles.profileCard}>
        <h2 id={id} className={styles.profileHeading}>
          Skill profile
        </h2>
        <p className={styles.profileNote}>
          {checked
            ? 'Your results from the mastery check, with your practice before it. Open an objective for the detail.'
            : 'How your practice is going on each of the eight objectives. The mastery check in module 6 adds gold or bronze. Open an objective for the detail.'}
        </p>
        <SkillProfile skills={skills.data.objectives} />
      </section>
    </Card>
  )
}
