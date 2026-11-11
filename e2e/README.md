# End-to-end and accessibility tests

Playwright tests of the whole student path in Chromium, Firefox and WebKit, against the real
stack served over HTTPS (WebKit only sends the Secure session cookie over HTTPS). Issue #35;
SE document §14.1.

## Run them locally

From the repository root, start the stack (your `.env` needs `POSTGRES_PASSWORD`):

```bash
docker compose -f docker-compose.yml -f docker-compose.e2e.yml up --build -d --wait
```

Then, in `e2e/`:

```bash
npm ci
npx playwright install chromium firefox webkit   # once
npx playwright test                              # all tests, three browsers
npx playwright test --ui                         # watch them step by step
```

Rebuild the stack after changing `api/` or `web/`: the tests run against the containers.
If the API answers 429, restart it to reset its rate limits: `docker compose restart api`.

## What they cover

| File | Covers |
|---|---|
| `student-path.spec.ts` | Register, module 0, a code submission |
| `mastery.spec.ts` | The mastery report and a review path (demo accounts) |
| `accessibility.spec.ts` | No WCAG 2.1 AA violations (axe-core) on every main page |
| `keyboard.spec.ts` | Module 0 with the keyboard only (not WebKit: it skips links on Tab) |
| `mobile.spec.ts` | Modules 0, 1, 3 and 6 at 360 px wide |
| `no-timers.spec.ts` | Nothing expires or counts down after two hours |

Not yet covered: a video checkpoint, because a fresh stack has no uploaded videos.