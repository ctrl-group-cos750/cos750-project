/**
 * What the study companion says (#214), and when it stays quiet. Research:
 * vault/analysis/cos750-2026-11-13/feedback-research/04-companion.md (summarised in the ID
 * document). Every line is about the task, never the person: what was right and why, what to check
 * on a near miss, which hint helps next. No person praise and no exclamation marks. It speaks only
 * at a feedback moment the student asked for (an answer checked, a quick check marked, a module
 * finished), never mid-question and never in the mastery check (module 6).
 */
import type { PartResult } from '../activities/activities.types.ts'
import type { Pose } from './characters/index.ts'

export type Line = { pose: Pose; text: string | null }

/** The first sentence of the item's own explanation, or nothing if it only says "Correct". */
function firstSentence(feedback: string): string | null {
  const first = feedback.split(/(?<=[.?])\s/)[0]?.trim()
  return first && !/^\s*(all )?correct\.?\s*$/i.test(first) ? first : null
}

/** After a right answer: why it is right, in one line. */
export function rightLine(feedback: string): string {
  const first = firstSentence(feedback)
  return first ? `Right: ${first}` : 'Right.'
}

/** After a wrong answer: on a near miss, what to check; otherwise which hint helps next. */
export function wrongLine(parts: readonly PartResult[], hintLevel: number): string {
  const right = parts.filter((p) => p.correct).length
  if (parts.length > 1 && right > 0) {
    const wrong = parts.length - right
    return `${right} of ${parts.length} right. Check the ${wrong === 1 ? 'one' : `${wrong}`} marked, the rest can stay.`
  }
  const next = hintLevel + 1
  if (next === 1) return 'Not yet. Hint 1 points at where to look.'
  if (next === 2) return 'Not yet. Hint 2 gives the rule for this one.'
  if (next === 3) return 'Hint 3 walks through it step by step, then try once more.'
  if (next === 4) return 'Hint 4 shows a worked answer: follow it, then answer in your own words.'
  return 'Go through the last hint one step at a time and compare it with your answer.'
}

// Right answers in a row this visit: after three, the companion stays quiet for a while and only
// its pose changes (say less to students doing well, research note: D'Mello).
let streak = 0

/** The line for an answer just checked, or a pose with no words while the student is on a run. */
export function answerLine(result: {
  correct: boolean | null
  feedback: string
  parts: readonly PartResult[]
  hintLevel: number
}): Line {
  if (result.correct) {
    streak += 1
    // Quiet for the 4th to 7th in a row, a word again at the 8th, and so on.
    const quiet = streak > 3 && (streak - 3) % 5 !== 0
    return { pose: 'pleased', text: quiet ? null : rightLine(result.feedback) }
  }
  streak = 0
  return { pose: 'encouraging', text: wrongLine(result.parts, result.hintLevel) }
}

/** For tests: forget the run of right answers. */
export function resetStreak(): void {
  streak = 0
}

/** What each quick check item was about, for the one line after a near pass. Keyed by title. */
const QUICK_CHECK_TIP: Record<string, string> = {
  'Directed or undirected': 'the one on directed edges: a follow goes one way, so it is an arrow.',
  'Counting edges and neighbours': 'the one on neighbours: count the edges at the vertex.',
  'The four key terms': 'the one on the four key terms: a traversal visits every vertex.',
  'From a situation to a graph':
    'the one on turning a situation into a graph: who is next to whom.',
  'The queue after a step':
    'the one on the queue: a neighbour joins at the back, in the order you find it.',
  'When BFS fits': 'the one on when BFS fits: it finds the fewest edges, not the cheapest route.',
  'The BFS order': 'the one on the order: whoever joins the queue first is visited first.',
  'The fewest edges': 'the one on the fewest edges: count the rings out from the start.',
}

/** The line after a quick check is marked. */
export function quickCheckLine(
  moduleNumber: number | undefined,
  correct: number,
  total: number,
  missed: readonly { title: string }[],
): Line {
  const score = `${correct} of ${total}.`
  const module = moduleNumber === undefined ? 'This module' : `Module ${moduleNumber}`
  if (correct === total) return { pose: 'pleased', text: `${score} ${module} is tested out.` }
  if (missed.length === 1) {
    const tip = QUICK_CHECK_TIP[missed[0].title] ?? `“${missed[0].title}”.`
    return { pose: 'encouraging', text: `${score} Look again at ${tip}` }
  }
  return {
    pose: 'encouraging',
    text: `${score} The module covers the ${total - correct} missed, in order.`,
  }
}

/** "Module 2 done. Map Maker is now secure." from the skill profile's secure objectives. */
export function moduleDoneLine(moduleNumber: number, secure: readonly string[]): Line {
  const done = `Module ${moduleNumber} done.`
  if (secure.length === 0) return { pose: 'pleased', text: done }
  const names =
    secure.length === 1
      ? `${secure[0]} is`
      : `${secure.slice(0, -1).join(', ')} and ${secure[secure.length - 1]} are`
  return { pose: 'pleased', text: `${done} ${names} now secure.` }
}
