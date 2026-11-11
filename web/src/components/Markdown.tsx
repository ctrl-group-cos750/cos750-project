import type { ComponentPropsWithoutRef } from 'react'
import ReactMarkdown, { type Components, type ExtraProps } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import styles from './Markdown.module.css'

export interface MarkdownProps {
  children: string
}

type HastNode = { type: string; value?: string; tagName?: string; children?: HastNode[] }

/** The text of a hast node and everything below it. */
function textOf(node: HastNode | undefined): string {
  if (!node) return ''
  if (node.type === 'text') return node.value ?? ''
  return (node.children ?? []).map(textOf).join('')
}

/** "Table: Step, Current vertex, Queue" from the header row, so each table region has a name
 * that tells it apart from the others on the page. GFM tables have no caption to use instead. */
function tableLabel(table: HastNode | undefined): string {
  const head = table?.children?.find((child) => child.tagName === 'thead')
  const row = head?.children?.find((child) => child.tagName === 'tr')
  const headers = (row?.children ?? [])
    .filter((cell) => cell.tagName === 'th')
    .map((cell) => textOf(cell).trim())
    .filter(Boolean)
  return headers.length > 0 ? `Table: ${headers.join(', ')}` : 'Table'
}

/**
 * A wide table scrolls inside its own region, so the page never scrolls sideways at 320 px
 * (WCAG 1.4.10 allows two-dimensional content such as a data table to scroll). The region is
 * focusable, so a keyboard user can scroll it with the arrow keys, and named, so a screen reader
 * says what it holds (the scrollable-region pattern from WAI's Tables tutorial).
 */
function ScrollableTable({ node, ...props }: ComponentPropsWithoutRef<'table'> & ExtraProps) {
  return (
    <section
      className={styles.tableScroll}
      aria-label={tableLabel(node as HastNode | undefined)}
      // oxlint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- a scroll container must be reachable by keyboard (WCAG 2.1.1)
      tabIndex={0}
    >
      <table {...props} />
    </section>
  )
}

/** A code block keeps its indentation and scrolls sideways when a line is too long, so like a
 * table it sits in a focusable, named region a keyboard user can scroll. */
function ScrollableCode({ node: _node, ...props }: ComponentPropsWithoutRef<'pre'> & ExtraProps) {
  return (
    <section
      className={styles.codeScroll}
      aria-label="Code"
      // oxlint-disable-next-line jsx-a11y/no-noninteractive-tabindex -- a scroll container must be reachable by keyboard (WCAG 2.1.1)
      tabIndex={0}
    >
      <pre {...props} />
    </section>
  )
}

const components: Components = { table: ScrollableTable, pre: ScrollableCode }

/**
 * Renders a markdown string as React elements, with GitHub-flavoured Markdown (tables,
 * strikethrough, autolinks, task lists) through remark-gfm, so the worked-example tables render
 * as tables (FR-5.3).
 *
 * - Uses react-markdown which builds a virtual DOM — no dangerouslySetInnerHTML,
 *   no raw HTML injection, safe under a strict CSP.
 * - Raw HTML in the markdown source (e.g. <script>) is dropped by the remark/rehype
 *   pipeline by default. Do NOT add rehype-raw — that would re-enable raw HTML
 *   parsing and break CSP safety.
 */
export function Markdown({ children }: MarkdownProps) {
  return (
    <div className={styles.prose}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  )
}
