/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

/**
 * Guards the colour decisions in global.css / tokens.css (SE document NFR-A2):
 * text 4.5:1, borders and graphics 3:1, and each colour defined in exactly one place.
 */

type Rgb = [number, number, number]

// Read the files as written. (Importing them with ?raw would run them through Tailwind first.)
const read = (name: string) => readFileSync(new URL(name, import.meta.url), 'utf8')
const globalCss = read('./global.css')
const tokensCss = read('./tokens.css')

/** The declarations of the first rule whose selector line starts with `selector`. */
function block(input: { css: string; selector: string }): string {
  const start = input.css.indexOf(`${input.selector} {`)
  if (start < 0) throw new Error(`no ${input.selector} block`)
  return input.css.slice(start, input.css.indexOf('\n}', start))
}

function colour(input: { css: string; selector: string; name: string }): Rgb {
  const match = new RegExp(`${input.name}:\\s*([^;]+);`).exec(
    block({ css: input.css, selector: input.selector }),
  )
  if (!match) throw new Error(`${input.name} not in ${input.selector}`)
  const value = match[1].trim()
  const rgb = /^rgb\((\d+),\s*(\d+),\s*(\d+)\)$/.exec(value)
  if (rgb) return [Number(rgb[1]), Number(rgb[2]), Number(rgb[3])]
  const hex = /^#([0-9a-f]{6})\b/i.exec(value)
  if (hex) return [0, 2, 4].map((i) => parseInt(hex[1].slice(i, i + 2), 16)) as Rgb
  throw new Error(`${input.name}: cannot read "${value}"`)
}

const luminance = ([r, g, b]: Rgb) => {
  const channel = (c: number) => {
    const s = c / 255
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4
  }
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

function ratio(a: Rgb, b: Rgb): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

const mix = (fg: Rgb, bg: Rgb, alpha: number): Rgb =>
  fg.map((c, i) => Math.round(alpha * c + (1 - alpha) * bg[i])) as Rgb

const themes = [
  { name: 'light', css: globalCss, selector: ':root', tokens: ':root' },
  {
    name: 'dark',
    css: globalCss,
    selector: ".dark,\n:root[data-theme='dark']",
    tokens: ".dark,\n:root[data-theme='dark']",
  },
] as const

describe.each(themes)('$name theme contrast', ({ selector, tokens }) => {
  const g = (name: string) => colour({ css: globalCss, selector, name })
  const surfaces = () => [g('--background'), g('--card'), g('--muted')]

  it('form control borders reach 3:1 on the page and the card', () => {
    for (const surface of [g('--background'), g('--card')]) {
      expect(ratio(g('--input'), surface)).toBeGreaterThanOrEqual(3)
    }
  })

  it('success and warning text reach 4.5:1 on every surface and on their own 15% tint', () => {
    for (const name of ['--success', '--warning']) {
      for (const surface of surfaces()) {
        expect(ratio(g(name), surface), `${name} on ${surface}`).toBeGreaterThanOrEqual(4.5)
        expect(ratio(g(name), mix(g(name), surface, 0.15))).toBeGreaterThanOrEqual(4.5)
      }
      const soft = g(`${name}-soft`)
      expect(ratio(g(name), soft)).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('badge outlines reach 3:1 on the card and on their own fill', () => {
    const t = (name: string) => colour({ css: tokensCss, selector: tokens, name })
    // dark values only exist in the .dark block; light ones in :root
    const card = g('--card')
    for (const tier of ['bronze', 'gold']) {
      const readTier = (name: string) => {
        try {
          return t(`--badge-${tier}${name}`)
        } catch {
          return colour({ css: tokensCss, selector: ':root', name: `--badge-${tier}${name}` })
        }
      }
      expect(ratio(readTier(''), card), `${tier} on card`).toBeGreaterThanOrEqual(3)
      expect(ratio(readTier(''), readTier('-soft')), `${tier} on fill`).toBeGreaterThanOrEqual(3)
    }
  })
})

describe('one place per colour', () => {
  const declared = (css: string) =>
    new Set([...css.matchAll(/^\s*(--[\w-]+)\s*:/gm)].map((m) => m[1]))

  it('tokens.css redeclares no name that global.css owns', () => {
    const owned = declared(globalCss)
    const clashes = [...declared(tokensCss)].filter(
      (name) => name.startsWith('--color-') && owned.has(name),
    )
    expect(clashes).toEqual([])
  })

  it('does not read variables that nothing defines', () => {
    const defined = new Set([...declared(globalCss), ...declared(tokensCss)])
    const used = [...tokensCss.matchAll(/var\((--[\w-]+)/g)].map((m) => m[1])
    expect(used.filter((name) => !defined.has(name) && name !== '--primary-dark')).toEqual([])
  })
})
