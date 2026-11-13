/** A short name for each learning objective (ID document §3.1), for the skill profile, where
 * the full sentence would not fit. The full text is always shown with it on request. */
const LABELS: Record<number, string> = {
  1: 'Key terms',
  2: 'Vertices and edges',
  3: 'Modelling a problem',
  4: 'Why BFS',
  5: 'Tracing BFS',
  6: 'Coding BFS',
  7: 'Testing BFS',
  8: 'Shortest routes',
}

export function objectiveLabel(id: number): string {
  return LABELS[id] ?? `Objective ${id}`
}
