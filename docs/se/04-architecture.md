# System Architecture

## High-level architecture (text diagram)
Three tiers with a clear client/server boundary:

```
+---------------------------------------------------------------+
|                        CLIENT (Browser)                       |
|   React + TypeScript SPA (Vite build)                         |
|   - Auth UI            - Interactive Video Player             |
|   - Lesson/Content UI  - BFS Visualizer (SVG/D3)             |
|   - Assessment UI      - Leaderboard & Points UI              |
|            |  HTTPS / JSON (REST)                             |
+------------|--------------------------------------------------+
             v
+---------------------------------------------------------------+
|                   APPLICATION TIER (Backend)                  |
|   Python + FastAPI (ASGI, served by Uvicorn)                  |
|   Routers:  auth | content | questions | bfs | scoring |      |
|             leaderboard | assessment                          |
|   Services: AuthService | ContentService | BfsEngine |        |
|             ScoringService | AssessmentService               |
|   Cross-cutting: validation (Pydantic), auth middleware,      |
|                  error handling, logging                      |
|            |  ORM (SQLAlchemy)                                |
+------------|--------------------------------------------------+
             v
+---------------------------------------------------------------+
|                         DATA TIER                             |
|   Relational DB (PostgreSQL prod / SQLite local dev)          |
|   Tables: users, lessons, content_items, videos,             |
|           questions, progress_events, scores, assessments,    |
|           assessment_results, graph_scenarios                 |
|   Media assets (video files) via object storage/static host  |
+---------------------------------------------------------------+
```

## Tier responsibilities
- **Frontend (client tier):** presentation, interaction, animation, client-side validation. Holds no business authority over scores — it reports events; the backend decides and persists.
- **Backend (application tier):** authoritative logic — authentication, BFS computation, scoring rules, assessment branching, content retrieval, persistence orchestration.
- **Data tier:** durable storage of structured data; media served from a static/object store rather than the database.

## Key architectural decisions
- **Thin client for authority-bearing logic.** Score/assessment decisions are server-side to prevent client tampering and keep rules in one place.
- **BFS computed server-side.** Guarantees a single correct implementation (the canonical algorithm being taught) and keeps the frontend a pure renderer of returned steps.
- **Stateless API with token auth.** Enables horizontal scaling and simple deployment.
- **Content as data.** Lessons, questions, and graph scenarios are stored/configured as data so new content does not require frontend code changes.
