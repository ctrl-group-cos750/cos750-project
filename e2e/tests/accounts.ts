// The seeded demo accounts (api/app/seed/demo/accounts.json). DEMO_PASSWORD is a
// test-only password for local and CI stacks, never the deployed one.
export { DEMO_PASSWORD } from './env'

export const demo = {
  mid: 'mid@demo.example.com',
  ready: 'ready@demo.example.com',
  notYet: 'not-yet@demo.example.com',
  bronze: 'bronze@demo.example.com',
} as const
