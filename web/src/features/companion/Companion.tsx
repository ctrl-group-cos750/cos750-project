import { useEffect, useState, useSyncExternalStore } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { ACHIEVEMENTS } from '../../components'
import { useSkills } from '../progress/hooks.ts'
import { Button } from '../../components'
import { HiddenNote } from '../progress/HiddenNote.tsx'
import { HideMenu } from '../progress/HideMenu.tsx'
import { useCompanionChoice, type CompanionChoice } from '../progress/preferences.ts'
import type { AttemptResult } from '../activities/activities.types.ts'
import { character, type CompanionId } from './characters/index.ts'
import { answerLine, moduleDoneLine, type Line } from './companion.ts'
import styles from './Companion.module.css'

/** Where the companion is chosen in the profile. */
export const COMPANION_SETTINGS = '/profile#companion'

// The line to read out, kept outside React so the one live region (CompanionAnnouncer, in the
// signed-in layout and so always on the page) announces lines said anywhere.
let spoken: { id: number; text: string } | null = null
let nextId = 1
const listeners = new Set<() => void>()

function announce(text: string): void {
  spoken = { id: nextId++, text }
  listeners.forEach((listener) => listener())
}

/**
 * The companion's live region (#214): a polite <output> that is always on the page, so each new
 * line is read once, with the companion's name, without moving focus (the result itself takes
 * focus, FeedbackPanel). The bubble on screen is hidden from screen readers so the line is not
 * read twice.
 */
export function CompanionAnnouncer() {
  const line = useSyncExternalStore(
    (listener) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
    () => spoken,
  )
  return (
    <output aria-live="polite" className="visually-hidden" data-companion-announcer>
      {line && <span key={line.id}>{line.text}</span>}
    </output>
  )
}

/**
 * The companion beside a feedback message: the character in a pose, its line in a speech bubble
 * pointing back at it, and a "⋯" with Change companion and Turn off. With no words (a run of
 * right answers) only the character shows, in its pose. The character is decorative.
 */
export function CompanionLine({
  id,
  line,
  onTurnOff,
}: {
  id: CompanionId
  line: Line
  onTurnOff: () => void
}) {
  const { name, Drawing } = character(id)
  const navigate = useNavigate()
  useEffect(() => {
    if (line.text) announce(`${name}: ${line.text}`)
  }, [line, name])
  return (
    <div className={styles.companion} data-companion={id}>
      <Drawing pose={line.pose} size={56} className={styles.figure} />
      {line.text && (
        <p className={styles.bubble} aria-hidden="true">
          {line.text}
        </p>
      )}
      <HideMenu
        title={name}
        label={`${name}: companion options`}
        items={[
          { label: 'Change companion', onSelect: () => void navigate(COMPANION_SETTINGS) },
          { label: 'Turn off companion', onSelect: onTurnOff },
        ]}
      />
    </div>
  )
}

/** The chosen companion with this line, or nothing when it is off. Turned off from its menu, it
 * leaves a note in its place with Undo (focus moves there, HiddenNote). */
function CompanionSpot({ line }: { line: Line }) {
  const [choice, setChoice] = useCompanionChoice()
  const [offFrom, setOffFrom] = useState<CompanionId | null>(null)
  if (offFrom)
    return (
      <HiddenNote
        text="Study companion off."
        onUndo={() => {
          setChoice(offFrom)
          setOffFrom(null)
        }}
      />
    )
  if (choice === null || choice === 'off') return null
  return (
    <CompanionLine
      id={choice}
      line={line}
      onTurnOff={() => {
        setOffFrom(choice)
        setChoice('off')
      }}
    />
  )
}

/** The one question, the first time a student checks an answer (opt-in, research note). */
function CompanionPrompt({ onAnswer }: { onAnswer: (choice: CompanionChoice) => void }) {
  return (
    <div className={styles.prompt} data-companion-prompt>
      {(() => {
        const { Drawing } = character('inka')
        return <Drawing pose="neutral" size={40} className={styles.figure} />
      })()}
      <p className={styles.question}>Want a study companion? Inka can comment on your answers.</p>
      <div className={styles.answers}>
        <Button size="sm" onClick={() => onAnswer('inka')}>
          Yes
        </Button>
        <Button size="sm" variant="ghost" onClick={() => onAnswer('off')}>
          No thanks
        </Button>
      </div>
    </div>
  )
}

/**
 * The companion under the result of an answer just checked (FeedbackPanel), never in the
 * mastery check. Asks once if the student has never been asked: the question is recorded as
 * answered "no" as soon as it is shown, so ignoring it never brings it back; "Yes" turns Inka on
 * and she speaks about this answer straight away. One per result (keyed by the result).
 */
export function FeedbackCompanion({ result }: { result: AttemptResult }) {
  const [choice, setChoice] = useCompanionChoice()
  const [asking, setAsking] = useState(() => choice === null)
  // The line for this answer, worked out once (the run of right answers counts each answer once).
  const [line] = useState(() => answerLine(result))
  useEffect(() => {
    if (asking && choice === null) setChoice('off')
  }, [asking, choice, setChoice])
  if (asking)
    return (
      <CompanionPrompt
        onAnswer={(answer) => {
          setChoice(answer)
          setAsking(false)
        }}
      />
    )
  return <CompanionSpot line={line} />
}

/** The companion beside another feedback moment (a quick check marked, a module finished), when
 * the student has turned it on. Nothing otherwise: it asks only after an answer (FeedbackCompanion). */
export function CompanionSays({ line }: { line: Line }) {
  return <CompanionSpot line={line} />
}

/** Where a finished module sends the student (ModulePage): the map, with the module's id. */
export type FinishedState = { finishedModule?: number }

// Finishes already spoken about, by history entry, so going back to the map doesn't repeat one.
const spokenFinishes = new Set<string>()

/**
 * The companion's word on a module just finished (#214), at the top of the map the student lands
 * on, inline, not a pop-up: "Module 2 done. Map Maker is now secure." The objectives the module
 * practises that the skill profile now marks secure (or met), named by their badges. Waits for
 * the profile to be fetched again after the finish, and speaks once per finish.
 */
export function ModuleDoneCompanion({
  modules,
}: {
  modules: readonly { id: number; number: number }[]
}) {
  const location = useLocation()
  const state = location.state as FinishedState | null
  const finished = state?.finishedModule
  const skills = useSkills()
  const [line, setLine] = useState<Line | null>(null)
  const ready = finished !== undefined && skills.data !== undefined && !skills.isFetching
  useEffect(() => {
    if (!ready || spokenFinishes.has(location.key)) return
    spokenFinishes.add(location.key)
    const module = modules.find((m) => m.id === finished)
    const practises = skills.data?.modules.find((m) => m.moduleId === finished)?.objectives ?? []
    const secure = (skills.data?.objectives ?? [])
      .filter(
        (o) =>
          practises.includes(o.id) &&
          (o.level === 'secure' ||
            o.result === 'met_independently' ||
            o.result === 'met_with_support'),
      )
      .map((o) => ACHIEVEMENTS.find((a) => a.objective === o.id)?.name)
      .filter((name): name is string => name !== undefined)
    // oxlint-disable-next-line react/set-state-in-effect -- once per finish, recorded outside React
    setLine(moduleDoneLine(module?.number ?? finished, secure))
  }, [ready, finished, location.key, modules, skills.data])
  return line ? <CompanionSays line={line} /> : null
}
