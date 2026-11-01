# Frontend Component Breakdown (React + TypeScript)

**[PROVISIONAL]** — component tree will evolve. Organised by feature.

- **App shell**
  - `AppRouter` — route definitions.
  - `AuthProvider` — holds auth token/session; guards routes.
  - `ApiClient` — typed REST client (fetch wrapper; consider OpenAPI-generated types).
- **Auth**
  - `LoginPage`, `RegisterPage`, `ProtectedRoute`.
- **Lesson & content**
  - `LessonListPage`, `LessonPage`.
  - `ContentModeSwitcher` — toggles between `video` / `text` / `interactive` items.
  - `TextContentView`, `InteractiveContentView`.
- **Interactive video**
  - `InteractiveVideoPlayer` — wraps the HTML5 video element, enforces checkpoint pauses and seek limits.
  - `CheckpointQuestionOverlay` — renders checkpoint question(s), gates resume.
- **BFS visualizer**
  - `GraphScenarioLoader` — fetches scenario + requests BFS steps.
  - `GraphCanvas` — renders nodes/edges as **SVG via D3** (layout + transitions).
  - `BfsAnimator` — consumes `steps`, drives highlighting.
  - `StepControls` — forward/back/play/pause/reset/speed.
  - `BfsStatePanel` — shows queue, visited order, current node.
- **Assessment**
  - `AssessmentPage`, `QuestionRenderer` (by question type), `AssessmentResultView`, `ScaffoldPanel` (renders returned scaffold content).
- **Gamification**
  - `ScoreBadge` / `PointsIndicator`, `LeaderboardPage`.
- **Shared**
  - `QuestionRenderer`, `Spinner`, `ErrorBoundary`, `Toast`/feedback components.
