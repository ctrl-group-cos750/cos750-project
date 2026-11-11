/// <reference types="node" />
import { readdirSync, readFileSync } from 'node:fs'
import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Markdown } from './index.ts'

const TABLE = [
  '| Step | Current vertex | Queue |',
  '|---|---|---|',
  '| 1 | A | C, E |',
  '| 2 | `C` | E, B, F |',
].join('\n')

/** Every Markdown body in the seed fixtures that holds a GFM table (#140). */
function fixtureTables(): { where: string; body: string }[] {
  // Vitest runs from web/ (outside the source tree, so not through import.meta.url).
  const seed = `${process.cwd()}/../api/app/seed/`
  const found: { where: string; body: string }[] = []
  const walk = (value: unknown, where: string) => {
    if (typeof value === 'string') {
      if (/^\|.*\|\s*\n\|[\s:|-]+\|/m.test(value)) found.push({ where, body: value })
    } else if (Array.isArray(value)) value.forEach((item, i) => walk(item, `${where}[${i}]`))
    else if (value && typeof value === 'object')
      for (const [key, item] of Object.entries(value)) walk(item, `${where}.${key}`)
  }
  for (const file of readdirSync(seed).filter((name) => /^module-\d+\.json$/.test(name))) {
    walk(JSON.parse(readFileSync(`${seed}${file}`, 'utf8')), file)
  }
  return found
}

describe('Markdown', () => {
  it('renders a heading from markdown', () => {
    render(<Markdown>{'# Hello World'}</Markdown>)
    expect(screen.getByRole('heading', { name: 'Hello World', level: 1 })).toBeInTheDocument()
  })

  it('renders a paragraph', () => {
    render(<Markdown>{'A simple paragraph.'}</Markdown>)
    expect(screen.getByText('A simple paragraph.')).toBeInTheDocument()
  })

  it('renders a fenced code block', () => {
    render(<Markdown>{'```js\nconsole.log("hi")\n```'}</Markdown>)
    // react-markdown renders fenced code blocks as <pre><code>
    const code = screen.getByText('console.log("hi")')
    expect(code.tagName).toBe('CODE')
    expect(code.closest('pre')).toBeInTheDocument()
    // It may scroll sideways at 320 px, so it is a named region a keyboard user can reach.
    expect(screen.getByRole('region', { name: 'Code' })).toHaveAttribute('tabindex', '0')
  })

  it('keeps a code block’s indentation', () => {
    render(<Markdown>{'```python\nwhile queue:\n    v = queue.popleft()\n```'}</Markdown>)
    expect(screen.getByRole('region', { name: 'Code' }).textContent).toContain(
      'while queue:\n    v = queue.popleft()',
    )
  })

  it('renders inline code', () => {
    render(<Markdown>{'Use `npm install` to install.'}</Markdown>)
    const code = screen.getByText('npm install')
    expect(code.tagName).toBe('CODE')
  })

  it('does not inject a raw <script> tag as a live DOM element (CSP safety)', () => {
    // react-markdown drops raw HTML nodes from its AST by default (no rehype-raw).
    // A <script> in the markdown source must NOT appear as an executable element.
    render(<Markdown>{'Before\n\n<script>window.xssProbe = true</script>\n\nAfter'}</Markdown>)

    // The script element must not exist in the DOM at all.
    expect(document.querySelector('script[src]')).not.toBeInTheDocument()
    expect(document.querySelectorAll('script').length).toBe(0)

    // The XSS payload must not have run.
    expect((window as Window & { xssProbe?: boolean }).xssProbe).toBeUndefined()
  })

  describe('GFM tables (#140)', () => {
    it('renders a pipe table as a table with column headers, not as text', () => {
      render(<Markdown>{TABLE}</Markdown>)
      const table = screen.getByRole('table')
      expect(
        within(table)
          .getAllByRole('columnheader')
          .map((th) => th.textContent),
      ).toEqual(['Step', 'Current vertex', 'Queue'])
      expect(within(table).getAllByRole('row')).toHaveLength(3)
      expect(within(table).getByText('C').tagName).toBe('CODE')
      expect(document.body.textContent).not.toContain('|---')
    })

    it('wraps the table in a named, keyboard-focusable scroll region (WCAG 1.4.10, 2.1.1)', () => {
      render(<Markdown>{TABLE}</Markdown>)
      const region = screen.getByRole('region', { name: 'Table: Step, Current vertex, Queue' })
      expect(region).toHaveAttribute('tabindex', '0')
      expect(region).toContainElement(screen.getByRole('table'))
    })

    it('names a table without a header row just "Table"', () => {
      // A delimiter row with empty header cells still parses as a table.
      render(<Markdown>{'| | |\n|---|---|\n| a | b |'}</Markdown>)
      expect(screen.getByRole('region', { name: 'Table' })).toBeInTheDocument()
    })

    it('renders an empty body as nothing, and a very wide table inside its scroll region', () => {
      const { container } = render(<Markdown>{''}</Markdown>)
      expect(container.textContent).toBe('')
      const cols = Array.from({ length: 60 }, (_, i) => `c${i}`)
      const wide = [`| ${cols.join(' | ')} |`, `|${'---|'.repeat(60)}`, `| ${cols.join(' | ')} |`]
      render(<Markdown>{wide.join('\n')}</Markdown>)
      expect(screen.getAllByRole('columnheader')).toHaveLength(60)
      expect(screen.getByRole('table').closest('section')).toHaveAttribute('tabindex', '0')
    })

    it('leaves text with stray pipes as text', () => {
      render(<Markdown>{'a | b | c'}</Markdown>)
      expect(screen.queryByRole('table')).not.toBeInTheDocument()
      expect(screen.getByText('a | b | c')).toBeInTheDocument()
    })

    it('still drops raw HTML inside a table cell (CSP safety)', () => {
      render(<Markdown>{'| a |\n|---|\n| <img src=x onerror=alert(1)> b |'}</Markdown>)
      expect(document.querySelector('img')).not.toBeInTheDocument()
      expect(screen.getByRole('cell')).toHaveTextContent('b')
    })

    const tables = fixtureTables()
    it('finds the worked-example tables in the fixtures', () => {
      // Modules 1 to 4 each have a worked example with a table; if this drops, the walk broke.
      expect(tables.length).toBeGreaterThanOrEqual(4)
    })

    it.each(tables)('renders the table in $where', ({ body }) => {
      render(<Markdown>{body}</Markdown>)
      expect(screen.getAllByRole('table').length).toBeGreaterThan(0)
      expect(screen.getAllByRole('columnheader').length).toBeGreaterThan(1)
      expect(document.body.textContent).not.toMatch(/\|\s*-{3}/)
    })
  })
})
