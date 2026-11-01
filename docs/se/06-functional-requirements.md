# Functional Requirements

Each feature is broken into concrete, testable capabilities. IDs (FR-x.y) are for traceability in later drafts.

## Interactive Video (FR-1)
- **FR-1.1** Play a lesson video with standard controls (play/pause/seek within allowed bounds).
- **FR-1.2** Pause automatically at configured timestamps ("checkpoints") defined per video.
- **FR-1.3** At a checkpoint, present one or more questions tied to that checkpoint.
- **FR-1.4** At a checkpoint the student submits an answer and receives **immediate feedback**. A wrong answer does **not** hard-block or lock the student out: they may **retry**. Playback does not resume until the checkpoint question is answered **correctly** (gate policy = `retry_until_correct`). There is no permanent lockout.
- **FR-1.5** Record **each attempt** (correct and incorrect) at a checkpoint as a progress event and route it to scoring (scoring distinguishes first-attempt-correct from retry-correct — see FR-2).
- **FR-1.6** Resume playback from the checkpoint once the question has been answered correctly.
- **FR-1.7** Prevent seeking past an unanswered (not-yet-correct) checkpoint.

## Gamification: Points + Leaderboard (FR-2)
- **FR-2.1** Award points for defined actions per a server-side rules table. **Draft 1 default rules (tunable, stored server-side):**

  | Action | Points |
  |---|---|
  | Correct checkpoint answer (first attempt) | 10 |
  | Correct checkpoint answer on retry (not first attempt) | 5 |
  | Completing a lesson | 25 |
  | Passing an assessment | 50 |
  | Completing the scaffolding path | 15 |

  These values are the Draft-1 defaults and are intended to be tuned; they live in a server-side rules table/config, not in the client.
- **FR-2.2** Persist per-user cumulative score and the underlying scoring events.
- **FR-2.3** Expose the current user's score and breakdown.
- **FR-2.4** Provide a leaderboard ranking users by score (top-N + the current user's rank).
- **FR-2.5** Scoring is computed/validated server-side; client reports events only.
- **FR-2.6** Leaderboard identity/privacy: each student chooses a **display name / handle** at signup, shown on the public leaderboard. A student may opt to appear **anonymised** on the public leaderboard (`is_anonymous_on_leaderboard` flag); when set, their handle is replaced with an anonymised label while their own rank remains visible to them.

## Adaptive-Scaffolding Assessment (FR-3)
- **FR-3.1** Deliver an assessment (set of questions) on Graphs + BFS.
- **FR-3.2** Evaluate answers server-side and compute a performance measure.
- **FR-3.3** If performance is below a **single, configurable pass/fail threshold**, branch the student into a **scaffolding path** (additional/alternative content or easier guided questions) before the lecture.
- **FR-3.4** If performance meets the threshold, mark the topic ready and record completion.
- **FR-3.5** Persist assessment attempts and results for scoring and progress.
- **FR-3.6** Draft 1 uses a **single global pass/fail threshold** only (configurable). The `scaffold_rules` JSON shape is retained for forward-compatibility, but Draft 1 exercises only the global-threshold branch. **Per-concept weakness detection (mapping specific weaknesses to targeted scaffolds) is explicitly deferred to Draft 2.**

> *Note:* The pedagogical justification for scaffolding is intentionally out of scope here; this section specifies only the engineering mechanism (thresholded branching over content).

## BFS Visualization (FR-4)
- **FR-4.1** Load a graph scenario (nodes, edges, directedness, start node) from the backend.
- **FR-4.2** Request a computed BFS traversal from the backend for a given scenario + start node.
- **FR-4.3** Render the graph (nodes + edges) in the browser.
- **FR-4.4** Animate the BFS step-by-step: current node, visited set, queue state, and newly discovered neighbours per step.
- **FR-4.5** Provide playback controls: step forward, step back, play/pause, reset, and speed control. (Back-stepping is supported in Draft 1 — enabled cheaply by local playback over precomputed steps.)
- **FR-4.6** Display auxiliary state (queue contents, visited order) alongside the animation.
- **FR-4.7** Support a small library of **predefined** graph scenarios for Draft 1. **Custom student-input graphs are deferred to Draft 2+** (noted future item; see §13).

## Multi-Mode Content Delivery (FR-5)
- **FR-5.1** Represent a lesson as a set of content items each tagged with a mode: `video`, `text`, or `interactive`.
- **FR-5.2** Serve the content items for a lesson so the frontend can present available modes.
- **FR-5.3** Allow the student to switch between available modes for the same concept.
- **FR-5.4** Track which modes/items a student has engaged with (for progress/scoring). **[PROVISIONAL]**
