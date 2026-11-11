const EN_DASH = '\u2013'

/** A list of vertices as the student typed it: the graph's labels it names, and anything else. */
export type ParsedVertexList = { values: string[]; unknown: string[] }

const EMPTY_WORDS = new Set(['empty', 'none', '-', EN_DASH])
// Brackets and quotes a student may copy from Python or the worked example; they carry nothing.
const DECORATION = /[[\](){}"']/g

/** Reads "A, D" (or "A D", "[a, d]") as a list of the graph's vertex labels. A label is matched
 * exactly first, then ignoring case, so a lower-case "a" is A. Anything that is not a vertex is
 * returned in `unknown`, so it can be named as an input error (WCAG 3.3.1) instead of being sent
 * as a wrong answer. "empty", "none" or a dash on its own is the empty list. */
export function parseVertexList(text: string, vertices: readonly string[]): ParsedVertexList {
  const exact = new Set(vertices)
  const folded = new Map<string, string | null>()
  for (const vertex of vertices) {
    const key = vertex.toLowerCase()
    folded.set(key, folded.has(key) ? null : vertex) // null: two labels differ only by case
  }
  const match = (token: string) =>
    exact.has(token) ? token : (folded.get(token.toLowerCase()) ?? null)

  const tokens = text
    .replace(DECORATION, ' ')
    .split(',')
    .map((token) => token.trim())
    .filter(Boolean)
  if (tokens.length === 1 && !match(tokens[0]) && EMPTY_WORDS.has(tokens[0].toLowerCase()))
    return { values: [], unknown: [] }

  const values: string[] = []
  const unknown: string[] = []
  for (const token of tokens) {
    const whole = match(token)
    if (whole) {
      values.push(whole)
      continue
    }
    // "A D" without commas: accept it when every word is a vertex.
    const words = token.split(/\s+/).map(match)
    if (words.length > 1 && words.every((word) => word !== null))
      values.push(...(words as string[]))
    else unknown.push(token)
  }
  return { values, unknown }
}
