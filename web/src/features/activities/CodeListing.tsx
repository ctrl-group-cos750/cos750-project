type CodeListingProps = {
  /** The program, lines separated by newlines. Indentation is kept exactly as given. */
  code: string
  /** The accessible name of the listing, e.g. "The faulty BFS". */
  label: string
}

/** Read-only Python with line numbers. Every line keeps its indentation (`white-space: pre`),
 * because in Python the indentation is the program's structure. A long line scrolls inside the
 * listing, never the page (WCAG 1.4.10); the listing is focusable so a keyboard user can scroll
 * it too. */
export function CodeListing({ code, label }: CodeListingProps) {
  return (
    <figure
      className="m-0 overflow-x-auto rounded border bg-muted/40 py-3 font-mono text-sm leading-6"
      aria-label={label}
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
            <code className="whitespace-pre">{line || ' '}</code>
          </li>
        ))}
      </ol>
    </figure>
  )
}
