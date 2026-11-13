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

describe.each(themes)('$name theme contrast', ({ name: theme, selector, tokens }) => {
  const g = (name: string) => colour({ css: globalCss, selector, name })
  const surfaces = () => [g('--background'), g('--card'), g('--muted')]

  it('form control borders reach 3:1 on the page and the card', () => {
    for (const surface of [g('--background'), g('--card')]) {
      expect(ratio(g('--input'), surface)).toBeGreaterThanOrEqual(3)
    }
  })

  // #142: the neutral Tag ("Not attempted" on the report) is muted text on --muted; it was 4.34:1.
  it('muted (secondary) text reaches 4.5:1 on every surface and on the accent tint', () => {
    for (const surface of [...surfaces(), g('--accent')]) {
      expect(ratio(g('--muted-foreground'), surface), `on ${surface}`).toBeGreaterThanOrEqual(4.5)
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

  // #35: dark --destructive was 3.1:1 as text on the card (register errors, staff alerts). It is
  // text on the surfaces, on --destructive-soft (Tag, Alert) and on its own tint (shadcn's
  // destructive button and badge: 10%, 20% in the dark theme).
  it('danger text reaches 4.5:1 on every surface, its soft fill and its own tint', () => {
    const danger = g('--destructive')
    for (const surface of [...surfaces(), g('--destructive-soft')]) {
      expect(ratio(danger, surface), `on ${surface}`).toBeGreaterThanOrEqual(4.5)
    }
    const tint = theme === 'dark' ? 0.2 : 0.1
    for (const surface of [g('--background'), g('--card')]) {
      expect(ratio(danger, mix(danger, surface, tint))).toBeGreaterThanOrEqual(4.5)
    }
  })

  // The danger button's label is the page colour on --destructive (Button.module.css .danger).
  it('the danger button label reaches 4.5:1', () => {
    expect(ratio(g('--background'), g('--destructive'))).toBeGreaterThanOrEqual(4.5)
  })

  it('badge outlines reach 3:1 on the card and on their own fill', () => {
    const t = (name: string) => colour({ css: tokensCss, selector: tokens, name })
    // dark values only exist in the .dark block; light ones in :root
    const card = g('--card')
    for (const tier of ['bronze', 'silver', 'gold']) {
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

/**
 * The page backgrounds (#214, backgrounds.css). Text sits straight on the page and on the
 * see-through cards of the overview pages, so every text colour is checked at the strongest point
 * of each glow (its centre, the colour at full strength over the page), with the doodle ink on top,
 * and on a tinted card over each of those.
 */
describe('page backgrounds', () => {
  const backgroundsCss = read('./backgrounds.css')

  /** `rgb(r g b / a%)` or `rgb(r, g, b)`, with its alpha (1 when opaque). */
  function rgba(input: { css: string; selector: string; name: string }): [Rgb, number] {
    const match = new RegExp(`${input.name}:\\s*([^;]+);`).exec(
      block({ css: input.css, selector: input.selector }),
    )
    if (!match) throw new Error(`${input.name} not in ${input.selector}`)
    const value = match[1].trim()
    const m = /^rgb\((\d+)[ ,]+(\d+)[ ,]+(\d+)\s*(?:\/\s*(\d+)%)?\)$/.exec(value)
    if (!m) throw new Error(`${input.name}: cannot read "${value}"`)
    return [[Number(m[1]), Number(m[2]), Number(m[3])], m[4] ? Number(m[4]) / 100 : 1]
  }

  const decorated = ":root:is([data-bg='glow'], [data-bg='doodles'])"
  const cases = [
    {
      theme: 'light',
      global: ':root',
      bg: ':root',
      text: decorated,
      accentText: () => colour({ css: globalCss, selector: ':root', name: '--accent-foreground' }),
    },
    {
      theme: 'dark',
      global: ".dark,\n:root[data-theme='dark']",
      bg: ":root[data-theme='dark'],\n.dark",
      text: `${decorated}[data-theme='dark']`,
      accentText: () =>
        rgba({
          css: backgroundsCss,
          selector: `${decorated}[data-theme='dark']`,
          name: '--color-accent-text',
        })[0],
    },
  ] as const

  describe.each(cases)('$theme theme', ({ global, bg, text, accentText }) => {
    const g = (name: string) => colour({ css: globalCss, selector: global, name })
    const b = (name: string) => rgba({ css: backgroundsCss, selector: bg, name })
    const page = () => g('--background')

    /** Every glow at its centre over the page, and the doodle ink over the doodles' glows. */
    function strongestPoints(): Rgb[] {
      const glows = [
        '--bg-glow-blue',
        '--bg-glow-gold',
        '--bg-glow-blue-faint',
        '--bg-glow-soft-blue',
        '--bg-glow-soft-gold',
      ].map((name) => {
        const [c, a] = b(name)
        return mix(c, page(), a)
      })
      const [ink, inkAlpha] = b('--doodle-ink')
      return [...glows, ...glows.slice(3).map((glow) => mix(ink, glow, inkAlpha))]
    }

    /** Each strongest point, and a tinted card on top of it. */
    function surfaces(): Rgb[] {
      const [card, alpha] = b('--surface-tinted')
      return strongestPoints().flatMap((point) => [point, mix(card, point, alpha)])
    }

    it('body, muted and link text reach 4.5:1 at the strongest point of every background', () => {
      const muted = rgba({ css: backgroundsCss, selector: text, name: '--muted-foreground' })[0]
      for (const [name, value] of [
        ['--foreground', g('--foreground')],
        ['--muted-foreground', muted],
        ['link text', accentText()],
      ] as const) {
        for (const surface of surfaces()) {
          expect(ratio(value, surface), `${name} on ${surface}`).toBeGreaterThanOrEqual(4.5)
        }
      }
    })

    it('the darker muted text still reaches 4.5:1 on the solid surfaces and the accent tint', () => {
      const muted = rgba({ css: backgroundsCss, selector: text, name: '--muted-foreground' })[0]
      for (const surface of [g('--background'), g('--card'), g('--muted'), g('--accent')]) {
        expect(ratio(muted, surface), `on ${surface}`).toBeGreaterThanOrEqual(4.5)
      }
    })

    it('status text on a tinted card reaches 4.5:1 over every background', () => {
      const [card, alpha] = b('--surface-tinted')
      for (const name of ['--success', '--warning', '--destructive']) {
        for (const point of strongestPoints()) {
          const surface = mix(card, point, alpha)
          expect(ratio(g(name), surface), `${name} on ${surface}`).toBeGreaterThanOrEqual(4.5)
        }
      }
    })

    it('form control borders reach 3:1 on a tinted card over every background', () => {
      const [card, alpha] = b('--surface-tinted')
      for (const point of strongestPoints()) {
        expect(ratio(g('--input'), mix(card, point, alpha))).toBeGreaterThanOrEqual(3)
      }
    })
  })
})
