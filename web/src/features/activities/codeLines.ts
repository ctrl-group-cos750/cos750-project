/** How a Parsons line's indentation is put into words (#142 review). */

/** "indent level 2" for a line with 8 leading spaces (4 per level, as in the fixtures), or
 * "indented 3 spaces" when the spaces don't make whole levels; empty for a line at the margin. */
export function indentLabel(text: string): string {
  const indent = text.length - text.trimStart().length
  if (indent === 0) return ''
  return indent % 4 === 0 ? `indent level ${indent / 4}` : `indented ${indent} spaces`
}

/** How a line is named to a screen reader: its code, then its indentation, e.g.
 * "“if n not in visited:” (indent level 3)". Two lines that differ only by indentation get
 * different names. */
export function lineName(text: string): string {
  const level = indentLabel(text)
  return `“${text.trim()}”${level ? ` (${level})` : ''}`
}
