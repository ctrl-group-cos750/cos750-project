// The seeded demo accounts (api/app/seed/demo/accounts.json). DEMO_PASSWORD is a
// test-only password for local and CI stacks, never the deployed one.
export const DEMO_PASSWORD = process.env.DEMO_PASSWORD ?? 'Demo-pass-2026!'

export const demo = {
  mid: 'mid@demo.example.com',
  ready: 'ready@demo.example.com',
  notYet: 'not-yet@demo.example.com',
} as const