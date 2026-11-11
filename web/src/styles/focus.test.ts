/// <reference types="node" />
import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

/**
 * Guards two CSS decisions jsdom can't render (#142); the browser check is in the PR.
 * - WCAG 2.4.7: the shared Button draws its own focus outline. Its box-shadow is unlayered CSS and
 *   beat the global :focus-visible ring (a box-shadow in @layer base), so focus was invisible.
 * - WCAG 1.4.1: a plain link in running text is underlined, not told apart by colour alone.
 */
const read = (path: string) => readFileSync(`${process.cwd()}/src/${path}`, 'utf8')

const rule = (css: string, selector: string) => {
  const start = css.indexOf(`${selector} {`)
  return start < 0 ? '' : css.slice(start, css.indexOf('}', start))
}

describe('focus and link styles', () => {
  it('gives the shared Button a visible focus outline that a box-shadow cannot hide', () => {
    const focus = rule(read('components/Button.module.css'), '.button:focus-visible')
    expect(focus).toMatch(/outline:\s*2px solid var\(--ring\)/)
    expect(focus).toMatch(/outline-offset:\s*\dpx/)
  })

  it('underlines links in running text', () => {
    expect(rule(read('styles/base.css'), 'a:not([class])')).toMatch(
      /text-decoration-line:\s*underline/,
    )
  })
})
