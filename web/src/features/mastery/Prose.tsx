import type { ReactNode } from 'react'

const INLINE = /(\*\*[^*]+\*\*|`[^`]+`)/g

/** `**bold**` and `` `code` `` inside one paragraph, as React nodes (never as HTML). Each piece is
 * keyed by where it starts in the text, which never changes for the same content. */
function inline(text: string): ReactNode[] {
  const nodes: ReactNode[] = []
  let at = 0
  for (const part of text.split(INLINE)) {
    const key = `${at}`
    at += part.length
    if (part.length > 4 && part.startsWith('**') && part.endsWith('**'))
      nodes.push(<strong key={key}>{part.slice(2, -2)}</strong>)
    else if (part.length > 2 && part.startsWith('`') && part.endsWith('`'))
      nodes.push(<code key={key}>{part.slice(1, -1)}</code>)
    else if (part) nodes.push(part)
  }
  return nodes
}

/**
 * A segment's Markdown body as paragraphs, with bold and inline code: the subset the review
 * content uses. Built as React nodes, so nothing in the content is ever run as HTML. Swap for a
 * full Markdown renderer when the module player (#15) brings one.
 */
export function Prose({ markdown }: { markdown: string }) {
  const paragraphs: ReactNode[] = []
  let at = 0
  for (const block of markdown.split(/(\n\s*\n)/)) {
    const key = `${at}`
    at += block.length
    if (block.trim() && !/^\n\s*\n$/.test(block))
      paragraphs.push(<p key={key}>{inline(block.trim())}</p>)
  }
  return <>{paragraphs}</>
}
