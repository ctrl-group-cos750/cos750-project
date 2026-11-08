import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Markdown } from './index.ts'

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
})
