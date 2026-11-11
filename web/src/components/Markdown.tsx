import type { ComponentPropsWithoutRef } from 'react'
import ReactMarkdown, { type Components, type ExtraProps } from 'react-markdown'
import { gfmTableFromMarkdown } from 'mdast-util-gfm-table'
import { gfmTable } from 'micromark-extension-gfm-table'
import styles from './Markdown.module.css'
import { ScrollRegion } from './ScrollRegion.tsx'

export interface MarkdownProps {
  children: string
}

/**
 * GitHub-flavoured Markdown tables, and nothing else from GFM.
 *
 * The worked examples teach tracing with pipe tables (#140). The full remark-gfm would also turn
 * on footnotes (fixed ids that collide when two segments use them, plus an injected "Footnotes"
 * h2), task-list checkboxes and autolinks, which staff could then author through the content
 * editor without anyone designing for them. This is what remark-gfm does, for tables only.
 */
type ParserData = { micromarkExtensions?: unknown[]; fromMarkdownExtensions?: unknown[] }

// `this` is unified's Processor. It is typed loosely so this file needn't depend on unified's and
// remark-parse's types directly (both come in through react-markdown).
function remarkGfmTables(this: unknown) {
  const data = (this as { data(): ParserData }).data()
  ;(data.micromarkExtensions ??= []).push(gfmTable())
  ;(data.fromMarkdownExtensions ??= []).push(gfmTableFromMarkdown())
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

/** "Code: class Graph:" from the block's first non-empty line, so two code blocks on one page
 * have different names. */
function codeLabel(pre: HastNode | undefined): string {
  const first = textOf(pre)
    .split('\n')
    .map((line) => line.trim())
    .find(Boolean)
  if (!first) return 'Code'
  return `Code: ${first.length > 40 ? `${first.slice(0, 40)}…` : first}`
}

/** A table scrolls sideways in its own region when it is too wide (ScrollRegion). */
function ScrollableTable({ node, ...props }: ComponentPropsWithoutRef<'table'> & ExtraProps) {
  return (
    <ScrollRegion label={tableLabel(node as HastNode | undefined)} className={styles.tableScroll}>
      <table {...props} />
    </ScrollRegion>
  )
}

/** A code block keeps its indentation and scrolls sideways in its own region when a line is too
 * long (ScrollRegion). */
function ScrollableCode({ node, ...props }: ComponentPropsWithoutRef<'pre'> & ExtraProps) {
  return (
    <ScrollRegion label={codeLabel(node as HastNode | undefined)} className={styles.codeScroll}>
      <pre {...props} />
    </ScrollRegion>
  )
}

const components: Components = { table: ScrollableTable, pre: ScrollableCode }

/**
 * Renders a markdown string as React elements, with GFM tables (remarkGfmTables), so the
 * worked-example tables render as tables (FR-2.2, #140).
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
      <ReactMarkdown remarkPlugins={[remarkGfmTables]} components={components}>
        {children}
      </ReactMarkdown>
    </div>
  )
}
