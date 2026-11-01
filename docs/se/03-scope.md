# Scope

## In scope for Draft 1
1. User accounts with authentication.
2. Interactive video player that pauses at defined timestamps and gates progression on answering questions.
3. Gamification: point system + leaderboard backed by persistent storage.
4. Adaptive-scaffolding assessment component (branching support based on performance).
5. BFS visualization: backend-computed traversal steps animated node-by-node on the frontend, with step controls.
6. Multi-mode content delivery (video / text / interactive) as a content-system capability.
7. REST API connecting frontend and backend.
8. GitHub repository with build/run/deploy instructions.
9. Placeholder lesson/content (videos, text, questions, graph scenarios) seeded via fixtures; real content is substituted later.

## Out of scope for Draft 1 **[PROVISIONAL]**
- Content authoring UI / admin dashboard (content seeded via fixtures/config initially).
- Topics beyond Graphs + BFS (e.g. DFS, Dijkstra, trees).
- Multi-course or multi-tenant support.
- Mobile-native apps (responsive web only).
- Social features beyond the leaderboard (comments, friends, chat).
- Offline mode / PWA installability.
- Production-grade analytics pipeline.

## Success criteria (engineering) **[PROVISIONAL]**
- A student can complete the full flow end-to-end in a deployed environment.
- BFS steps returned by the backend render a correct, repeatable animation.
- Points and leaderboard persist across sessions and reflect recorded events.
- Assessment branches to a scaffolding path when performance is below a configurable threshold.
