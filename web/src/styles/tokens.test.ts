/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

/*
 * WCAG 2.1 AA for the brand tokens (SE document NFR-A2), in light and dark mode. The shadcn/ui
 * theme in global.css only points at these tokens, so checking them checks every component.
 * Text needs 4.5:1; control borders and the primary button's edge need 3:1.
 */

function declarations(css: string): Record<string, string> {
  const out: Record<string, string> = {}
  for (const [, name, value] of css.matchAll(/(--[\w-]+):\s*([^;]+);/g)) out[name] = value.trim()
  return out
}

// Read from disk (Vitest runs from web/): it turns CSS imports into empty modules.
const tokensCss = readFileSync('src/styles/tokens.css', 'utf8')
const globalCss = readFileSync('src/styles/global.css', 'utf8')

const light = declarations(tokensCss.split('@media')[0])
const dark = { ...light, ...declarations(tokensCss.split(":root[data-theme='dark']")[1]) }

function resolve(name: string, tokens: Record<string, string>): string {
  const value = tokens[name]
  if (value === undefined) throw new Error(`${name} is not defined`)
  const ref = /^var\((--[\w-]+)\)$/.exec(value)
  return ref ? resolve(ref[1], tokens) : value
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

// [foreground, background, minimum]: every pairing the components use.
const pairs: [string, string, number][] = [
  ...['--color-bg', '--color-surface', '--color-surface-sunken'].flatMap(
    (bg): [string, string, number][] => [
      ['--color-text', bg, 4.5],
      ['--color-text-muted', bg, 4.5],
    ],
  ),
  ['--color-accent-text', '--color-bg', 4.5],
  ['--color-accent-text', '--color-surface', 4.5],
  ['--color-on-accent', '--color-accent', 4.5],
  ['--color-on-accent', '--color-accent-hover', 4.5],
  ['--color-accent-soft-text', '--color-accent-soft', 4.5],
  ['--color-text', '--color-accent-soft', 4.5],
  ['--color-danger', '--color-bg', 4.5],
  ['--color-danger', '--color-surface', 4.5],
  ['--color-danger', '--color-danger-soft', 4.5],
  ['--color-text', '--color-danger-soft', 4.5],
  ['--color-success', '--color-success-soft', 4.5],
  ['--color-text', '--color-success-soft', 4.5],
  ['--color-success', '--color-surface', 4.5],
  ['--color-warning', '--color-warning-soft', 4.5],
  ['--color-text', '--color-warning-soft', 4.5],
  ['--color-warning', '--color-surface', 4.5],
  ['--color-border', '--color-bg', 3],
  ['--color-border', '--color-surface', 3],
  ['--color-accent', '--color-bg', 3],
  ['--color-accent', '--color-surface', 3],
]

describe.each([
  ['light', light],
  ['dark', dark],
])('%s mode', (_mode, tokens) => {
  it.each(pairs)('%s on %s meets %s:1', (fg, bg, minimum) => {
    expect(contrast(resolve(fg, tokens), resolve(bg, tokens))).toBeGreaterThanOrEqual(minimum)
  })
})

describe('shadcn/ui theme', () => {
  it('takes every colour from a brand token, never a raw value', () => {
    const root = /:root\s*\{([^}]*)\}/.exec(globalCss)?.[1] ?? ''
    const colours = Object.entries(declarations(root)).filter(([name]) => name !== '--radius')
    expect(colours.length).toBeGreaterThan(10)
    for (const [name, value] of colours) {
      // The name is in the string so a failure says which variable is wrong.
      expect(`${name}: ${value}`).toMatch(/: var\(--color-[\w-]+\)$/)
      expect(Object.keys(light)).toContain(value.slice(4, -1))
    }
  })
})
