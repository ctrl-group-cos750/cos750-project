import { defineConfig, devices } from '@playwright/test'

// Runs against a stack started with docker compose (see e2e/README.md).
export default defineConfig({
  testDir: './tests',
  // One test at a time: the tests share one database, and the API rate-limits
  // registration (20 per 10 minutes per address, NFR-S6).
  workers: 1,
  // No retries: a retry would register more accounts and hide flaky tests.
  retries: 0,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : 'list',
   use: {
        baseURL: process.env.BASE_URL ?? 'https://localhost:8443',
        // Caddy's local certificate isn't trusted by the browsers; that's expected here.
        ignoreHTTPSErrors: true,
        trace: 'retain-on-failure',
    },
    // The stack is served over HTTPS (docker-compose.e2e.yml): WebKit only sends the
    // Secure session cookie over HTTPS. Each test logs in through the page.
    projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  ],
})