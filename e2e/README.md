# End-to-end and accessibility tests

Playwright tests of the whole student path in Chromium, Firefox and WebKit, against the real
stack served over HTTPS (WebKit only sends the Secure session cookie over HTTPS), with axe-core
accessibility checks in the light and the dark theme. Issue #35; SE document §14.1.

## When they run

CI runs them only on the pull request that takes `staging` to `master`: a full run in three
browsers takes about 36 minutes of Actions time. For a pull request into `staging`, run them
locally (below) and paste the summary into the PR. CI still builds the images on every PR that
touches the stack.

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

Rebuild the stack after changing `api/` or `web/`: the tests run against the containers. If you
started it with `-p <name>`, set `COMPOSE_PROJECT_NAME=<name>` too: the setup makes a staff
account with `docker compose exec` (`tests/env.ts`, `E2E_STAFF_GRANT`).

### Without Docker (Chromium only)

`./serve-local.sh` serves the API on SQLite and the built app on plain HTTP, and prints the
command that runs the tests against it (`BASE_URL`, `E2E_STAFF_GRANT`). Only Chromium keeps the
Secure cookie over plain `http://localhost`, so run `--project=chromium`. `E2E_CHROMIUM=<path>`
uses a Chromium of your own (a machine that can't download Playwright's).

## How they work

- Questions and answers come from the fixtures (`tests/content.ts` reads `api/app/seed`), so a
  content change doesn't break a test. `tests/drive.ts` answers each kind of activity through its
  screen.
- A test that changes progress registers its own student through the register page; the demo
  accounts are only looked at. The course is walked through the API from inside the page, kept
  under the API's 60 answers a minute.
- Each test sends its own `X-Forwarded-For` (198.18.0.0/15, reserved for tests), and the test
  stack's proxies pass it on (`Caddyfile`), so the per-address register and login limits count
  each test on its own. That is why two workers can run at once.
- The `setup` project makes a staff account; the video tests upload `media/lesson.mp4` with a
  checkpoint through the staff API, so a fresh stack needs no videos.

## What they cover

| File | Covers |
|---|---|
| `smoke.spec.ts` | A demo student logs in, cookie included, in each browser |
| `student-path.spec.ts` | Register, log out and in, refused passwords, every demo account's stage, module 0 on screen, a code activity wrong then right (module 4) |
| `video-checkpoint.spec.ts` | A video stops at its checkpoint, feedback, the hint ladder, resume; a passed checkpoint doesn't ask again |
| `mastery.spec.ts` | The report (ready, not yet), the mastery check on screen (all seven kinds), a review path that makes the student ready |
| `accessibility.spec.ts` | No WCAG 2.2 AA violations (axe-core) on every page, staff pages included, and each activity kind unanswered, wrong with hints, and right; light and dark |
| `keyboard.spec.ts` | Module 0 with the keyboard only; visible focus on every control |
| `mobile.spec.ts` | Modules 0, 1, 3 and 6 at 360 px, every activity answered; the pages around them |
| `no-timers.spec.ts` | Nothing counts down or expires in two hours: a checkpoint, a module activity, each activity kind |

Known app bugs are `test.fixme` with the reason, so they run again once fixed: at 360 px a new
badge's note covers the module's Next button (`mobile.spec.ts`).
