import { indentLabel } from './codeLines.ts'

type CodeListingProps = {
  /** The program, lines separated by newlines. Indentation is kept exactly as given. */
  code: string
  /** The accessible name of the listing, e.g. "The faulty BFS". */
  label: string
}

/** The indentation in words, visually hidden, after a line's code: a screen reader skips leading
 * spaces, and in Python the indentation is the program's structure. The same words as the Parsons
 * lines use (`codeLines.ts`, #142). */
function IndentWords({ text }: { text: string }) {
  const level = indentLabel(text)
  if (!level) return null
  return (
    <>
      {/* The space is a text node of its own, so a screen reader keeps it. */}{' '}
      <span className="visually-hidden">({level})</span>
    </>
  )
}

/** One line of code whose indentation survives a narrow screen: the leading spaces become padding
 * of one character each (half a character below 30rem), so a line that wraps keeps a hanging
 * indent at its own level and never reads as a line at a shallower level (WCAG 1.4.10). The level
 * is also given in words for a screen reader. The same technique as the Parsons lines (#140). */
export function IndentedCode({ text, className = '' }: { text: string; className?: string }) {
  const code = text.trimStart()
  const indent = text.length - code.length
  return (
    <code
      data-indent={indent}
      className={`block whitespace-pre-wrap font-mono [overflow-wrap:anywhere] [padding-inline-start:calc(var(--indent)*1ch)] max-[30rem]:[padding-inline-start:calc(var(--indent)*0.5ch)] ${className}`}
      style={{ '--indent': indent } as React.CSSProperties}
    >
      {code}
      <IndentWords text={text} />
    </code>
  )
}

/** Read-only Python with line numbers. Every line keeps its indentation (`white-space: pre`),
 * because in Python the indentation is the program's structure, and says it in words for a screen
 * reader. A long line scrolls inside the listing, never the page (WCAG 1.4.10); the listing is
 * focusable so a keyboard user can scroll it too. */
export function CodeListing({ code, label }: CodeListingProps) {
  return (
    <figure
      className="relative m-0 overflow-x-auto rounded border bg-muted/40 py-3 font-mono text-sm leading-6"
      aria-label={label}
      // `relative` keeps the visually hidden indent words inside the scrolling box: positioned
      // against the page, they would widen it at 320 px.
      // It scrolls, and holds nothing focusable, so it takes focus itself for keyboard users
      // (axe: scrollable-region-focusable).
      // oxlint-disable-next-line jsx-a11y/no-noninteractive-tabindex
      tabIndex={0}
    >
      <ol className="m-0 list-none p-0">
        {code.split('\n').map((line, index) => (
          // Lines never move, so their position is a stable key.
          // oxlint-disable-next-line react/no-array-index-key
          <li key={index} className="grid grid-cols-[2.5rem_max-content] pr-3">
            <span aria-hidden="true" className="select-none pr-3 text-right text-muted-foreground">
              {index + 1}
            </span>
            <code className="whitespace-pre">
              {line || ' '}
              <IndentWords text={line} />
            </code>
          </li>
        ))}
      </ol>
    </figure>
  )
}
