import { QueryClientContext } from '@tanstack/react-query'
import { useContext, useEffect, useRef, useState } from 'react'
import { Alert } from '../../components'
import { confetti, prefersReducedMotion, useConfettiSetting } from '../progress/confetti.ts'
import { useSkills } from '../progress/hooks.ts'
import { usePreference } from '../progress/preferences.ts'
import { praiseFor, progressRemark } from '../progress/praise.ts'
import { HiddenNote } from '../progress/HiddenNote.tsx'
import { HideMenu, type HideItem } from '../progress/HideMenu.tsx'
import { rewardsKey } from '../rewards/hooks.ts'
import { updateRewardsSettings, type Rewards } from '../rewards/rewards.api.ts'
import type { AttemptResult } from './activities.types.ts'
import { CelebrationAllowed } from './celebration.ts'
import styles from './FeedbackPanel.module.css'

type FeedbackPanelProps = { result: AttemptResult | undefined; partName?: 'line' | 'blank' }

/**
 * Summary of a submission result.
 *
 * Each new result takes keyboard focus (WCAG 2.4.3, #142), because a status message inserted
 * together with its text is often not read. The focused element is the result itself (Alert announce="focus"):
 * a group named by its title and described by the feedback, or named by the feedback alone when
 * that already starts with the title, so a screen reader reads the result once, not a container.
 * It is not also a live region, so a second result in the same place is read once. Tab then
 * carries on to the hints and the module's Next. Focus moves only for a result the student just
 * asked for; a result already there when the panel first renders is left alone, so opening a
 * page never moves focus. "Check answer" stays focusable while checking (Button's
 * keepFocusWhileLoading), so a failed check leaves focus on it.
 *
 * A correct answer leads with the content's explanation of why it is right. One just given also
 * gets a short success moment (#214): a check mark that draws itself, a calm varied line and a
 * progress remark (both only with "Encouraging comments" on), the points it earned (unless
 * rewards are hidden) and a small confetti burst from the result, with a quiet "⋯" beside it to
 * turn any of them off right there. A wrong answer stays
 * as calm as before, and nothing in the mastery check (module 6: `CelebrationAllowed`) gets any of
 * it, withheld or not. Under
 * prefers-reduced-motion the check mark is drawn at once and there is no confetti.
 */
export function FeedbackPanel({ result }: FeedbackPanelProps) {
  const alert = useRef<HTMLDivElement>(null)
  const shown = useRef(result)
  // The result there when the panel first rendered (restored on load, #171) is shown as before,
  // without the moment; any later one is an answer just given.
  const [initial] = useState(result)
  const allowed = useContext(CelebrationAllowed)
  const celebrate = allowed && result !== initial && result?.correct === true && !result.withheld

  useEffect(() => {
    if (result === shown.current) return
    shown.current = result
    const element = alert.current
    if (allowed && result?.correct === true && !result.withheld) confetti('small', element)
    if (!element) return
    // Focus again even if it already has focus, so the new result is read.
    if (document.activeElement === element) element.blur()
    element.focus()
  }, [result, allowed])

  if (!result) return null
  // A right answer leads with why it is right: the content's explanation, read first, with
  // "Correct" only for screen readers (the tick and the colour say it on screen). Where the
  // content has no explanation the feedback is just "Correct.", and the title stays (#214).
  const explained = result.correct === true && !result.withheld && !GENERIC.test(result.feedback)
  return (
    // The section (a "Submission results" region, as before) is not what takes focus; the result is.
    // `data-result-id` tells a new result from one restored on load (#171), for the e2e tests.
    <section aria-label="Submission results" data-result-id={result.id} className="grid gap-3">
      <Alert
        ref={alert}
        announce="focus"
        // A mastery check answer says only that it was recorded (#144).
        tone={result.withheld ? 'info' : result.correct ? 'success' : 'warning'}
        title={
          explained
            ? undefined
            : result.withheld
              ? 'Answer recorded'
              : result.correct
                ? 'Correct'
                : 'Not quite'
        }
      >
        {explained ? (
          <>
            <span className="visually-hidden">Correct.</span> {result.feedback}
          </>
        ) : (
          result.feedback
        )}
      </Alert>
      {celebrate && <SuccessMoment result={result} />}
    </section>
  )
}

/** Feedback that only says the answer is right: nothing to explain. */
const GENERIC = /^\s*(all )?correct\.?\s*$/i

/** The success moment under a correct answer just given (#214): the tick, then, with
 * encouraging comments on, a varied line and a remark on progress; the points unless rewards
 * are hidden; and the way to turn confetti off. */
function SuccessMoment({ result }: { result: AttemptResult }) {
  // The rewards the page already has (the header's badge announcer loads them); points only when
  // they are known to be shown (FR-9.5). Read from the cache, so the panel makes no request.
  const client = useContext(QueryClientContext)
  const rewards = client?.getQueryData<Rewards>(rewardsKey)
  // Points and badges are kept on the account: saved straight to the API and the cache (no
  // mutation hook, so the panel still needs no provider, as above).
  const setHideRewards = (hideRewards: boolean, then?: () => void) =>
    void updateRewardsSettings({ hideRewards })
      .then((saved) => {
        client?.setQueryData<Rewards>(rewardsKey, saved)
        then?.()
      })
      .catch(() => {})
  const [confettiOn, setConfetti] = useConfettiSetting()
  const [comments, setComments] = usePreference('comments')
  // What was just turned off from here, for the note that takes its place (and focus, WCAG 2.4.3).
  const [turnedOff, setTurnedOff] = useState<{ text: string; undo: () => void } | null>(null)
  const points = result.points ?? 0
  const showPoints = points > 0 && rewards?.hideRewards === false
  // The one "⋯" beside the moment (#214): each part of it can be turned off right here.
  const items: HideItem[] = [
    ...(confettiOn && !prefersReducedMotion()
      ? [
          {
            label: 'Turn off confetti',
            onSelect: () => {
              setConfetti(false)
              setTurnedOff({ text: 'Confetti is off.', undo: () => setConfetti(true) })
            },
          },
        ]
      : []),
    ...(comments
      ? [
          {
            label: 'Hide encouraging comments',
            onSelect: () => {
              setComments(false)
              setTurnedOff({
                text: 'Encouraging comments hidden.',
                undo: () => setComments(true),
              })
            },
          },
        ]
      : []),
    ...(showPoints
      ? [
          {
            label: 'Hide points and badges',
            onSelect: () =>
              setHideRewards(true, () =>
                setTurnedOff({
                  text: 'Points and badges hidden.',
                  undo: () => setHideRewards(false),
                }),
              ),
          },
        ]
      : []),
  ]
  return (
    <div className={styles.moment} data-success-moment>
      <svg className={styles.check} viewBox="0 0 32 32" aria-hidden="true" focusable="false">
        <circle cx="16" cy="16" r="14" />
        <path d="M9.5 16.5l4.5 4.5 8.5-9" />
      </svg>
      <div className={styles.words}>
        {(comments || showPoints) && (
          <p className={styles.praise}>
            {comments && praiseFor(result.id, result.hintLevel)}
            {showPoints && <span className={styles.points}>+{points} points</span>}
          </p>
        )}
        {comments && client && <ProgressRemark />}
      </div>
      <HideMenu title="this feedback" items={items} />
      {turnedOff && (
        <HiddenNote
          key={turnedOff.text}
          text={turnedOff.text}
          onUndo={() => {
            turnedOff.undo()
            setTurnedOff(null)
          }}
        />
      )}
    </div>
  )
}

/** "You've practised 3 of 8 objectives so far." From the skill profile, refreshed after the
 * answer; nothing until it has arrived. */
function ProgressRemark() {
  const skills = useSkills()
  const remark = skills.data && progressRemark(skills.data.objectives)
  return remark ? <p className={styles.remark}>{remark}</p> : null
}
