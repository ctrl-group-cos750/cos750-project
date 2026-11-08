import ReactMarkdown from 'react-markdown'
import styles from './Markdown.module.css'

export interface MarkdownProps {
  children: string
}

/**
 * Renders a markdown string as React elements.
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
      <ReactMarkdown>{children}</ReactMarkdown>
    </div>
  )
}
