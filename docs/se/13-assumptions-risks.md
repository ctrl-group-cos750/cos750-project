# Assumptions, Risks, and Open Questions

## Assumptions
- Single student role for Draft 1; content is seeded via **placeholder fixtures** (no authoring UI yet); real lesson videos/content are added later.
- Graphs are small (≤ ~50 nodes), so full BFS step precomputation per request is acceptable and SVG/D3 rendering is appropriate.
- Scoring authority is server-side; the client only reports events.
- One topic (Graphs + BFS) with one lesson and one assessment is sufficient for Draft 1.
- **Team size is 7.** This allows slightly more of the previously-provisional scope to be committed to Draft 1 (e.g. confirmed Postgres/Docker deployment, concrete scoring and gating), but the draft is kept honest and does not over-commit — advanced items (per-concept scaffolding, custom graphs, password reset/refresh tokens) remain deferred.

## Risks
- **Interactive video gating** — reliably enforcing pause/seek limits and the `retry_until_correct` gate across browsers can be fiddly; may need a vetted player library.
- **Adaptive scaffolding complexity** — rule-driven branching can balloon; Draft 1 deliberately uses a single global threshold, with per-concept weakness detection deferred to Draft 2.
- **Media hosting** — video storage/bandwidth for real content is not yet sized (placeholders used in Draft 1); affects deploy cost once real media lands.
- **Reverse-proxy/TLS setup** — correct HTTPS termination, routing, and certificate automation on the team's domain is new infrastructure work to validate before the demo.
- **Scope creep** — custom graph input, multiple topics, and an authoring UI are tempting but out of scope for Draft 1.

## Resolved decisions (previously open)
The following Draft-1 open questions have been decided and are now reflected throughout the document:
1. **Graph rendering** → **SVG via D3** (simpler for ≤~50-node graphs; §4, §10).
2. **Production database** → **PostgreSQL** confirmed; SQLite for local dev only (§3, §4, §12).
3. **Deployment** → **Docker containers** (FastAPI + PostgreSQL + static frontend) behind a reverse proxy (Nginx/Caddy/Traefik) terminating HTTPS on the team's **domain** (§12.4).
4. **Video gating policy** → **`retry_until_correct`**: wrong answers give feedback and allow retry, no hard-block/lockout; each attempt recorded (FR-1, §7).
5. **Scaffolding granularity** → **single global pass/fail threshold** in Draft 1; per-concept weakness detection deferred to Draft 2 (FR-3, §7).
6. **Leaderboard identity** → required **display name/handle** at signup with an **anonymised** opt-in (`is_anonymous_on_leaderboard`) (FR-2, §7).
7. **Scoring rules** → concrete Draft-1 default rules table (10 / 5 / 25 / 50 / 15), tunable, server-side (FR-2).
8. **Auth scope** → **email required**; JWT access tokens; password reset and refresh tokens deferred to Draft 2 (§4, §6.3, §7).
9. **Content source** → **placeholder content** seeded via fixtures for Draft 1; real content later (§12, §13.1).
10. **Team size** → confirmed **7** (§13.1).
11. **Custom graphs** → **deferred to Draft 2+**; predefined scenario library for Draft 1 (FR-4.7).

## Open questions remaining for Draft 2
- **Per-concept weakness detection** for scaffolding (mapping specific weaknesses → targeted scaffolds) — the `scaffold_rules` JSON shape is ready for it.
- **Custom student-input graphs** — UI, validation, and backend acceptance of student-authored scenarios.
- **Auth hardening** — password reset flow and refresh-token strategy.
- **Content authoring** — admin/author role and authoring UI to replace fixtures; sizing of real video media hosting/bandwidth.
- **Additional topics** beyond Graphs + BFS (DFS, Dijkstra, trees) and any multi-lesson/multi-assessment structure.
- **Materialised leaderboard** / caching if leaderboard query performance becomes a concern at larger user counts.
- **Rate limiting** on auth endpoints and other hardening noted as provisional in §6.3.

*End of DRAFT 1 — Software Engineering design document. Instructional-design content is maintained separately in the ID document per the exam specification.*
