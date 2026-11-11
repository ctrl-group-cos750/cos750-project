/// <reference types="node" />
import { readdirSync, readFileSync } from 'node:fs'
import { render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
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

/** Makes every element report content wider than itself, as a wide table or long code line does
 * at 320 px (jsdom does no layout, so both widths are otherwise 0). */
function overflowing() {
  vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockReturnValue(900)
  vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(300)
}

afterEach(() => {
  vi.restoreAllMocks()
})

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
  })

  it('keeps a code block’s indentation', () => {
    render(<Markdown>{'```python\nwhile queue:\n    v = queue.popleft()\n```'}</Markdown>)
    expect(document.querySelector('pre')?.textContent).toContain(
      'while queue:\n    v = queue.popleft()',
    )
  })

  describe('scroll regions only when they scroll (#142 review)', () => {
    const body = ['```python', 'class Graph:', '    pass', '```', '', TABLE].join('\n')

    it('adds no tab stop and no region when the table and code fit', () => {
      render(<Markdown>{body}</Markdown>)
      expect(screen.queryAllByRole('region')).toHaveLength(0)
      expect(document.querySelectorAll('[tabindex]')).toHaveLength(0)
    })

    it('makes each overflowing block a named tab stop, with a different name each', () => {
      overflowing()
      render(<Markdown>{body}</Markdown>)
      const code = screen.getByRole('region', { name: 'Code: class Graph:' })
      const table = screen.getByRole('region', { name: 'Table: Step, Current vertex, Queue' })
      for (const region of [code, table]) expect(region).toHaveAttribute('tabindex', '0')
      expect(code).toContainElement(document.querySelector('pre'))
    })

    it('shortens a long first line in a code block’s name', () => {
      overflowing()
      render(<Markdown>{'```\n\n' + 'x'.repeat(100) + '\n```'}</Markdown>)
      expect(screen.getByRole('region', { name: `Code: ${'x'.repeat(40)}…` })).toBeInTheDocument()
    })
  })

  describe('only the GFM table extension (#142 review)', () => {
    it.each([
      [
        'a footnote',
        'Text[^1]\n\n[^1]: Note.',
        () => document.querySelector('sup, section, [id*="fn"], h2'),
      ],
      ['a task list', '- [ ] todo', () => document.querySelector('input')],
      ['strikethrough', '~~gone~~', () => document.querySelector('del')],
      ['a bare URL', 'see https://example.com now', () => document.querySelector('a')],
    ])(
      'turns on nothing for %s (no footnote section, checkbox, del or autolink)',
      (_, source, find) => {
        render(<Markdown>{source}</Markdown>)
        expect(find()).toBeNull()
      },
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

    it('wraps an overflowing table in a named, keyboard-focusable scroll region (WCAG 1.4.10, 2.1.1)', () => {
      overflowing()
      render(<Markdown>{TABLE}</Markdown>)
      const region = screen.getByRole('region', { name: 'Table: Step, Current vertex, Queue' })
      expect(region).toHaveAttribute('tabindex', '0')
      expect(region).toContainElement(screen.getByRole('table'))
    })

    it('names a table without a header row just "Table"', () => {
      overflowing()
      // A delimiter row with empty header cells still parses as a table.
      render(<Markdown>{'| | |\n|---|---|\n| a | b |'}</Markdown>)
      expect(screen.getByRole('region', { name: 'Table' })).toBeInTheDocument()
    })

    it('renders an empty body as nothing, and a very wide table inside its scroll region', () => {
      const { container } = render(<Markdown>{''}</Markdown>)
      expect(container.textContent).toBe('')
      const cols = Array.from({ length: 60 }, (_, i) => `c${i}`)
      const wide = [`| ${cols.join(' | ')} |`, `|${'---|'.repeat(60)}`, `| ${cols.join(' | ')} |`]
      overflowing()
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
