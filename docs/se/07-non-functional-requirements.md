# Non-Functional Requirements

## Performance
- **NFR-P1** BFS computation for Draft 1 scenario sizes (≤ ~50 nodes) returns in well under 200 ms server-side.
- **NFR-P2** API p95 latency target < 300 ms for non-media endpoints under light load. **[PROVISIONAL target]**
- **NFR-P3** Frontend BFS animation sustains a smooth frame rate for Draft 1 graph sizes; animation is driven by precomputed steps (no per-frame server calls).
- **NFR-P4** Video media served from a static/CDN-style host, not proxied through the API.

## Usability
- **NFR-U1** Responsive layout for desktop and tablet widths.
- **NFR-U2** Clear, consistent controls for video, BFS stepping, and assessment navigation.
- **NFR-U3** Visible feedback for scoring events and assessment outcomes.

## Security & Authentication
- **NFR-S1** Passwords stored only as salted hashes (Argon2, via pwdlib).
- **NFR-S2** Authenticated endpoints require a valid **JWT in the session cookie**; authorization checks tie resources to the owning user. Email is required as account identity (used for recovery in later drafts). Password reset and refresh tokens are **deferred to Draft 2**.
- **NFR-S3** All traffic over HTTPS in deployed environments.
- **NFR-S4** Server-side validation of all inputs (Pydantic schemas); never trust client-reported scores/results.
- **NFR-S5** No secrets in the repository; configuration via environment variables.
- **NFR-S6** Standard protections: the session cookie is httpOnly, Secure and SameSite=Lax; state-changing requests require JSON bodies (blocking cross-site form posts); parameterised queries via the ORM; rate limiting on auth endpoints **[PROVISIONAL]**. The app and the API share one origin, so no CORS is configured.

## Maintainability
- **NFR-M1** Layered backend (routers → services → data) with the BfsEngine isolated from web concerns and unit-testable in isolation.
- **NFR-M2** Typed boundaries both sides (Pydantic + TypeScript); API types kept in sync (consider generating a TS client from OpenAPI **[PROVISIONAL]**).
- **NFR-M3** ruff, mypy --strict, oxlint and Prettier enforced in CI on every PR.
- **NFR-M4** Database migrations tracked with Alembic.

## Accessibility **[PROVISIONAL]**
- **NFR-A1** Keyboard operability for primary controls (video, stepping, assessment).
- **NFR-A2** Sufficient colour contrast; BFS state not conveyed by colour alone (also labels/shapes).
- **NFR-A3** Semantic HTML and ARIA roles for custom controls.
- **NFR-A4** Captions/transcripts for videos (ties into the `text` content mode).
