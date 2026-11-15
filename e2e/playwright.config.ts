import { defineConfig, devices } from '@playwright/test'
import { BASE_URL } from './tests/env'

const CI = !!process.env.CI

// Runs against a stack started with docker compose (see e2e/README.md), or any other running
// copy of the app named by BASE_URL.
export default defineConfig({
  testDir: './tests',
  // Each test that changes progress registers its own student, and the read-only ones only look
  // at the demo accounts, so tests can run side by side. Each test is a different client address
  // (fixtures.ts, clientAddress), so the per-address limits on registering and logging in
  // (NFR-S6) count each test on its own, as they would count students in a class.
  fullyParallel: true,
  workers: Number(process.env.E2E_WORKERS ?? 2),
  forbidOnly: CI,
  // No retries: a retry would hide a flaky test.
  retries: 0,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  // Stops a hung run well inside the CI step's own limit. The three browsers take about 45 minutes
  // on CI's two workers (193 tests on 15 November 2026), WebKit the slowest.
  globalTimeout: CI ? 60 * 60_000 : undefined,
  reporter: CI ? [['github'], ['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: BASE_URL,
    // Caddy's local certificate isn't trusted by the browsers; that's expected here.
    ignoreHTTPSErrors: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    // The app's own reduced-motion mode: no page fade-in (AppShell) and no badge note sliding up
    // (BadgeAnnouncer). On CI's slow WebKit, axe caught the report page mid-fade (its text at
    // 3.3:1 for a moment) and moving badge notes never counted as stable. These tests check
    // content and controls, not motion.
    reducedMotion: 'reduce',
  },
  // The stack is served over HTTPS (docker-compose.e2e.yml): WebKit only sends the Secure
  // session cookie over HTTPS. Students log in or register through the page; the `setup`
  // project runs first and makes the staff account the video tests use.
  projects: [
    { name: 'setup', testMatch: /setup\.ts$/ },
    {
      name: 'chromium',
      dependencies: ['setup'],
      use: {
        ...devices['Desktop Chrome'],
        // A Chromium of your own, for a machine that can't download Playwright's.
        launchOptions: process.env.E2E_CHROMIUM
          ? { executablePath: process.env.E2E_CHROMIUM }
          : undefined,
      },
    },
    { name: 'firefox', dependencies: ['setup'], use: { ...devices['Desktop Firefox'] } },
    {
      name: 'webkit',
      dependencies: ['setup'],
      // WebKit runs these tests three to four times slower than Chromium and Firefox on CI's
      // runners: the activity tests took 47-56 s of their 60 s there, and the trace activity and
      // the mastery walk ran out of time mid-click. Same tests, more time; test.slow() still
      // triples it.
      timeout: 180_000,
      use: { ...devices['Desktop Safari'] },
    },
  ],
})
