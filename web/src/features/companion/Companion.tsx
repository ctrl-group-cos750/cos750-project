import { useEffect, useRef, useState, useSyncExternalStore } from 'react'
import { useLocation, useNavigate } from 'react-router'
import { ACHIEVEMENTS } from '../../components'
import { useSkills } from '../progress/hooks.ts'
import { Button } from '../../components'
import { HiddenNote } from '../progress/HiddenNote.tsx'
import { HideMenu } from '../progress/HideMenu.tsx'
import {
  setStoredCompanion,
  storedCompanion,
  useCompanionChoice,
  type CompanionChoice,
} from '../progress/preferences.ts'
import type { AttemptResult } from '../activities/activities.types.ts'
import { character, type CompanionId } from './characters/index.ts'
import { answerLine, moduleDoneLine, secureObjectives, type Line } from './companion.ts'
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

// How long the question must have been on screen, and read out, before leaving it unanswered
// counts as "no": long enough for the polite live region to have spoken it (#222 review).
export const PROMPT_SEEN_MS = 4000

const QUESTION = 'Want a study companion? Inka can comment on your answers.'

/**
 * The one question, the first time a student checks an answer (opt-in, research note). It is read
 * out through the companion's polite live region, after the result (which has focus), so a screen
 * reader user hears it too. Answering moves focus back to the result (`onAnswered`), never to the
 * page: the pressed button goes away (WCAG 2.4.3).
 */
function CompanionPrompt({ onAnswer }: { onAnswer: (choice: CompanionChoice) => void }) {
  useEffect(() => {
    announce(`${QUESTION} Yes or No thanks, under the result. Kept on this device.`)
  }, [])
  return (
    <div className={styles.prompt} data-companion-prompt>
      {(() => {
        const { Drawing } = character('inka')
        return <Drawing pose="neutral" size={40} className={styles.figure} />
      })()}
      <p className={styles.question}>
        {QUESTION} <span className={styles.aside}>Your choice is kept on this device.</span>
      </p>
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
 * mastery check or on a review path's fresh items. Asks if the student has never been asked
 * (per student, on this device). The question counts as answered "no" only after a real choice,
 * or once it has been on screen, and read out, for `PROMPT_SEEN_MS` and the student moves on
 * without answering: a prompt that flashed by unheard is asked again next time (#222 review).
 * "Yes" turns Inka on and she speaks about this answer straight away. One per result (keyed by
 * the result). `onAnswered` moves focus once the prompt is answered (to the result).
 */
export function FeedbackCompanion({
  result,
  onAnswered,
}: {
  result: AttemptResult
  onAnswered?: () => void
}) {
  const [choice, setChoice] = useCompanionChoice()
  // The line for this answer, worked out once (the run of right answers counts each answer once).
  const [line] = useState(() => answerLine(result))
  const asking = choice === null
  const shownAt = useRef<number | null>(null)
  useEffect(() => {
    if (!asking) return
    shownAt.current = Date.now()
    return () => {
      // Left unanswered after it was seen and heard: don't ask again.
      const since = shownAt.current
      if (since !== null && Date.now() - since >= PROMPT_SEEN_MS && storedCompanion() === null)
        setStoredCompanion('off')
    }
  }, [asking])
  if (asking)
    return (
      <CompanionPrompt
        onAnswer={(answer) => {
          // Focus first, while the pressed button is still there, so it never falls to the page.
          onAnswered?.()
          shownAt.current = null
          setChoice(answer)
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

/** Where a finished module sends the student (ModulePage): the map, with the module's id and
 * the objectives that were secure (or met) when the module was opened. */
export type FinishedState = { finishedModule?: number; secureBefore?: number[] }

// Finishes already spoken about, by history entry, so going back to the map doesn't repeat one.
const spokenFinishes = new Set<string>()

/**
 * The companion's word on a module just finished (#214), at the top of the map the student lands
 * on, inline, not a pop-up: "Module 2 done. Map Maker is now secure." The objectives the module
 * practises that the skill profile now marks secure (or met) and did not when the module was
 * opened (`secureBefore`), named by their badges. Waits for the profile to be fetched again after
 * the finish, and speaks once per finish.
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
    // Only news: an objective already secure when the module was opened isn't "now secure".
    // Unknown (no record of before), nothing is claimed.
    const before = state?.secureBefore
    const secure = secureObjectives(skills.data?.objectives ?? [])
      .filter((id) => practises.includes(id) && before !== undefined && !before.includes(id))
      .map((id) => ACHIEVEMENTS.find((a) => a.objective === id)?.name)
      .filter((name): name is string => name !== undefined)
    // oxlint-disable-next-line react/set-state-in-effect -- once per finish, recorded outside React
    setLine(moduleDoneLine(module?.number ?? finished, secure))
  }, [ready, finished, location.key, modules, skills.data, state])
  return line ? <CompanionSays line={line} /> : null
}
