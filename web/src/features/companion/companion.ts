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

/**
 * After a right answer: not the explanation again (the result above already gives it, and a
 * screen reader would hear it twice: the coherence principle, #222 review), but what it adds, how
 * the answer was reached and what to try next, on the process, never the person.
 */
export function rightLine(hintLevel: number): string {
  if (hintLevel <= 0) return 'Right, without a hint.'
  if (hintLevel < 3) return `Right, with hint ${hintLevel}. Try the next one before opening a hint.`
  return 'Right, after the worked steps. Try the next one with fewer hints.'
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
  // Hints 3 and 4 give a lot away and lower what a right answer earns (the hint ladder warns
  // before hint 3), so the companion never sends a student to them without saying so.
  if (next === 3)
    return 'Try once more first if you can. Hint 3 walks through it, but an answer after it counts for less.'
  if (next === 4)
    return 'Hint 4 shows a worked answer, and an answer after it counts for less. Read it, then try the next one on your own.'
  return 'Go through the last hint one step at a time and compare it with your answer.'
}

// Right answers in a row this visit: after three, the companion stays quiet for a while and only
// its pose changes (say less to students doing well, research note: D'Mello).
let streak = 0

/** After a right answer that came after a wrong one: it counts for no medal, but still helps. */
export const RIGHT_AFTER_WRONG =
  'Right this time. Only a first answer counts toward a medal, but working it out still helps.'

/** The line for an answer just checked, or a pose with no words while the student is on a run. */
// Only a first attempt counts (the evidence rule, FR-9.6), so a right answer after a wrong first one
// isn't "right, without a hint" for its medal. The API says so (`afterWrongFirst`), across reloads,
// visits and restarts, rather than this tab remembering it (#222 re-review, nit 4).
export function answerLine(result: {
  correct: boolean | null
  parts: readonly PartResult[]
  hintLevel: number
  afterWrongFirst?: boolean
}): Line {
  if (result.correct && result.afterWrongFirst === true) {
    streak = 1
    return { pose: 'pleased', text: RIGHT_AFTER_WRONG }
  }
  if (result.correct) {
    streak += 1
    // Quiet for the 4th to 7th in a row, a word again at the 8th, and so on.
    const quiet = streak > 3 && (streak - 3) % 5 !== 0
    return { pose: 'pleased', text: quiet ? null : rightLine(result.hintLevel) }
  }
  streak = 0
  return { pose: 'encouraging', text: wrongLine(result.parts, result.hintLevel) }
}

/** For tests: forget the run of right answers. */
export function resetStreak(): void {
  streak = 0
}

/** What each quick check item was about, for the one line after a near pass. Keyed by activity
 * id, not title, so renaming an item (#223) never loses its tip: every module's quick check (1 to
 * 5) has its items here, each tip fitting its question. */
const QUICK_CHECK_TIP: Record<number, string> = {
  // Module 1
  151: 'the one on directed edges: a follow goes one way, so it is an arrow.',
  103: 'the one on neighbours: count the edges at the vertex.',
  // The question asks which is a traversal (#222 re-review): moving along connections.
  150: 'the one on the four key terms: a traversal moves along the connections, from each thing to the next.',
  152: 'the one on turning a situation into a graph: who is next to whom.',
  // Module 2
  203: "the one on add_edge: an undirected edge goes in both vertices' lists.",
  250: "the one on the directed graph: add_edge(u, v) adds v to u's list only.",
  251: 'the one on reading the dictionary: an undirected edge is listed twice but is one edge.',
  252: 'the one on add_vertex: a new vertex starts with an empty list.',
  // Module 3
  314: 'the one on the queue: a neighbour joins at the back, in the order you find it.',
  // The question asks which job is not for BFS (#222 review): the tip says what BFS is for.
  350: 'the one on when BFS fits: BFS follows connections, ring by ring, so look for the job with none to follow.',
  351: 'the one on the order: whoever joins the queue first is visited first.',
  352: 'the one on the fewest edges: count the rings out from the start.',
  // Module 4
  403: 'the one on bfs line by line: a vertex already found is not added again.',
  450: 'the one on what bfs returns: neighbours are taken in sorted order, whatever order the edges were added in.',
  451: 'the one on the neighbour loop: mark a neighbour found as it joins the queue.',
  452: 'the one on the queue: popleft() takes the oldest vertex, from the front.',
  // Module 5: the bug named by what goes wrong, not by the set's name, which #223 changes.
  503: 'the one on spotting the bug: a vertex marked only as it leaves the queue can join it twice.',
  550: 'the one on testing for that bug: the graph needs two routes to one vertex.',
  551: 'the one on unreachable vertices: only a graph in separate pieces has any.',
  552: 'the one on what to expect: BFS returns only what it can reach from the start.',
}

/** The line after a quick check is marked. */
export function quickCheckLine(
  moduleNumber: number | undefined,
  correct: number,
  total: number,
  missed: readonly { activityId: number; title: string }[],
): Line {
  const score = `${correct} of ${total}.`
  // "Passed the quick check", the words the module page and the map use (#223), not "tested out".
  if (correct === total)
    return {
      pose: 'pleased',
      text: `${score} You passed ${moduleNumber === undefined ? 'this module' : `module ${moduleNumber}`}'s quick check.`,
    }
  if (missed.length === 1) {
    const tip = QUICK_CHECK_TIP[missed[0].activityId] ?? `“${missed[0].title}”.`
    return { pose: 'encouraging', text: `${score} Look again at ${tip}` }
  }
  return {
    pose: 'encouraging',
    text: `${score} The module covers the ${total - correct} missed, in order.`,
  }
}

/** "Module 2 done. Map Maker is now secure." Only the objectives that became secure (or met) in
 * this module: one already secure before it is not news (#222 review). */
export function moduleDoneLine(moduleNumber: number, secure: readonly string[]): Line {
  const done = `Module ${moduleNumber} done.`
  if (secure.length === 0) return { pose: 'pleased', text: done }
  const names =
    secure.length === 1
      ? `${secure[0]} is`
      : `${secure.slice(0, -1).join(', ')} and ${secure[secure.length - 1]} are`
  return { pose: 'pleased', text: `${done} ${names} now secure.` }
}

/** The objectives the skill profile marks secure in practice, or met. */
export function secureObjectives(
  objectives: readonly { id: number; level: string; result?: string | null }[],
): number[] {
  return objectives
    .filter(
      (o) =>
        o.level === 'secure' || o.result === 'met_independently' || o.result === 'met_with_support',
    )
    .map((o) => o.id)
}
