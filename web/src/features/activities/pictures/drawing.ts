/**
 * The student's answer to a graph-shaped question, as a drawing (#155).
 *
 * Judged graph against map, not row by row: an edge the student drew that is not on the map is
 * wrong ("✗ no such walkway"); an edge that is on the map is drawn normally even if it was chosen
 * for the wrong row (the row's own feedback names that). A bus stop chosen for a road, or a road
 * chosen for a stop, is marked with what it was chosen for. The map is what the student already
 * sees; the stored solution never reaches the browser.
 *
 * Wrong is never shown by colour alone (WCAG 1.4.1): red plus a dashed line plus a "✗" label;
 * missed is green plus a "✓" label. The text alternative says exactly what the picture shows
 * (WCAG 1.1.1): the walkways the student left out are named only in the comparison, which is
 * offered only after a right answer or once hint 4 is open.
 */
import type { MatchingActivity } from '../activities.types.ts'
import { linkKey, placeById, type Situation } from './situations.ts'

export type EdgeMark = 'plain' | 'wrong' | 'missed'

export type DrawnEdge = {
  from: string
  to: string
  mark: EdgeMark
  label?: string
  directed: boolean
}

export type DrawnVertex = { id: string; mark?: 'wrong' | 'missed'; label?: string }

export type Drawing = {
  situation: Situation
  title: string
  edges: DrawnEdge[]
  vertices: DrawnVertex[]
  /** The text alternative: exactly what the picture shows. */
  description: string
}

/** What a right item names: "Edge A–C" is an edge, "Vertex P" a vertex. */
export function parsePart(label: string): { edge: [string, string] } | { vertex: string } | null {
  const edge = /^Edge\s+(\w+)\s*[–-]\s*(\w+)$/u.exec(label.trim())
  if (edge) return { edge: [edge[1], edge[2]] }
  const vertex = /^Vertex\s+(\w+)$/u.exec(label.trim())
  if (vertex) return { vertex: vertex[1] }
  return null
}

/** The places a left item names, in the order it names them, e.g. "Walkway: Dining hall –
 * Engineering" names D and E; "The Park bus stop" names P. */
export function placesNamed(situation: Situation, label: string): string[] {
  return situation.places
    .filter((place) => place.name && label.includes(place.name))
    .sort((a, b) => label.indexOf(a.name) - label.indexOf(b.name))
    .map((place) => place.id)
}

/** A short quote of a left item for a label: "Park bus stop", "road Quad – Residence". */
function quote(situation: Situation, label: string): string {
  const named = placesNamed(situation, label).map((id) => placeById(situation, id)?.name ?? id)
  return named.length === 1
    ? `${named[0]} ${situation.place}`
    : `${situation.link} ${named.join(' – ')}`
}

const edgeName = (a: string, b: string) => `${a}–${b}`

function list(items: readonly string[]): string {
  if (items.length <= 1) return items.join('')
  return `${items.slice(0, -1).join(', ')} and ${items[items.length - 1]}`
}

/**
 * The student's graph from their submitted pairs (left item id → right item id). `compare`
 * adds the map's links they left out, in green: only after a right answer or hint 4.
 */
export function answerDrawing(
  activity: MatchingActivity,
  situation: Situation,
  pairs: Readonly<Record<string, string>>,
  compare: boolean,
): Drawing {
  const right = new Map(activity.config.right.map((item) => [item.id, item.label]))
  const onMap = new Set(situation.links.map(([a, b]) => linkKey(situation, a, b)))
  const edges = new Map<string, DrawnEdge>()
  const vertices = new Map<string, DrawnVertex>()
  const notOnMap: string[] = []
  const misplaced: string[] = []

  for (const item of activity.config.left) {
    const chosen = pairs[item.id]
    const part = chosen ? parsePart(right.get(chosen) ?? '') : null
    if (!part) continue
    const named = placesNamed(situation, item.label)
    const forStop = named.length === 1
    if ('edge' in part) {
      const [a, b] = part.edge
      const key = linkKey(situation, a, b)
      const existing = edges.get(key)
      if (forStop) {
        const label = `✗ your "${quote(situation, item.label)}"`
        edges.set(key, { from: a, to: b, mark: 'wrong', label, directed: situation.directed })
        misplaced.push(
          `For the ${quote(situation, item.label)} you chose edge ${edgeName(a, b)}, which is a ${situation.link}.`,
        )
      } else if (!onMap.has(key)) {
        if (!existing) notOnMap.push(edgeName(a, b))
        edges.set(key, {
          from: a,
          to: b,
          mark: 'wrong',
          label: `✗ no such ${situation.link}`,
          directed: situation.directed,
        })
      } else if (!existing) {
        edges.set(key, { from: a, to: b, mark: 'plain', directed: situation.directed })
      }
    } else {
      const wrongVertex = !forStop || named[0] !== part.vertex
      if (wrongVertex) {
        vertices.set(part.vertex, {
          id: part.vertex,
          mark: 'wrong',
          label: `✗ your "${quote(situation, item.label)}"`,
        })
        misplaced.push(
          forStop
            ? `For the ${quote(situation, item.label)} you chose vertex ${part.vertex}, which is the ${placeById(situation, part.vertex)?.name ?? part.vertex} ${situation.place}.`
            : `For the ${quote(situation, item.label)} you chose vertex ${part.vertex}, which is a ${situation.place}.`,
        )
      }
    }
  }

  // The map's own links: on the student's graph only once they may see the comparison.
  const missed: string[] = []
  const graphShaped = activity.config.left.every(
    (item) => placesNamed(situation, item.label).length === 2,
  )
  if (compare) {
    for (const [a, b] of situation.links) {
      const key = linkKey(situation, a, b)
      // Only the links the question asked about count as missed.
      const asked = activity.config.left.some((item) => {
        const named = placesNamed(situation, item.label)
        return named.length === 2 && linkKey(situation, named[0], named[1]) === key
      })
      if (edges.has(key) || !asked) continue
      missed.push(edgeName(a, b))
      edges.set(key, {
        from: a,
        to: b,
        mark: 'missed',
        label: `✓ ${situation.link} on the map`,
        directed: situation.directed,
      })
    }
  }

  const drawnEdges = [...edges.values()]
  const plainCount = drawnEdges.filter((edge) => edge.mark !== 'missed').length
  const sentences: string[] = []
  if (graphShaped) {
    sentences.push(
      `Your graph has ${plainCount} ${plainCount === 1 ? 'edge' : 'edges'}, drawn from your answer.`,
    )
    sentences.push(
      notOnMap.length
        ? `Not on the map: ${list(notOnMap)}.`
        : `Every edge you drew is a ${situation.link} on the map.`,
    )
  } else {
    sentences.push('Your answers drawn on the graph.')
    sentences.push(...misplaced)
    if (misplaced.length === 0) sentences.push('Each answer is the right kind of part.')
  }
  if (compare) {
    sentences.push(
      missed.length
        ? `${situation.link[0].toUpperCase()}${situation.link.slice(1)}s on the map that you missed, marked in green: ${list(missed)}.`
        : `You missed no ${situation.link}s.`,
    )
  } else {
    sentences.push(`Compare it with the map.`)
  }

  return {
    situation,
    title: compare ? 'Your graph and the map' : 'Your graph',
    edges: drawnEdges,
    vertices: [...vertices.values()],
    description: sentences.join(' '),
  }
}

/** The map itself as a graph: the correct graph for a question that asks for the whole map. */
export function mapDrawing(situation: Situation, title: string, description: string): Drawing {
  return {
    situation,
    title,
    description,
    vertices: [],
    edges: situation.links.map(([from, to]) => ({
      from,
      to,
      mark: 'plain',
      directed: situation.directed,
    })),
  }
}

/** "Directed or undirected?": the situation redrawn as the student classified it, with what that
 * would mean. Only drawn for a row the student got wrong. */
export function classificationDrawing(
  situation: Situation,
  answer: 'directed' | 'undirected',
  name: string,
  meaning: string,
): Drawing {
  const seen = new Set<string>()
  const edges: DrawnEdge[] = []
  for (const [from, to] of situation.links) {
    const key = answer === 'directed' ? `${from}>${to}` : [from, to].sort().join('-')
    if (seen.has(key)) continue
    seen.add(key)
    edges.push({ from, to, mark: 'wrong', directed: answer === 'directed' })
  }
  return {
    situation,
    title: `${name}: if it were ${answer}`,
    edges,
    vertices: [],
    description: `${name}, drawn as your answer, ${answer}. ${meaning}`,
  }
}

/** The correct graph beside the student's (only after a right answer or hint 4): the map's links
 * the question asked about, with the ones the student left out in green and labelled. */
export function correctDrawing(
  activity: MatchingActivity,
  situation: Situation,
  pairs: Readonly<Record<string, string>>,
): Drawing {
  const theirs = answerDrawing(activity, situation, pairs, true)
  const missed = theirs.edges.filter((edge) => edge.mark === 'missed')
  const missedKeys = new Set(missed.map((edge) => linkKey(situation, edge.from, edge.to)))
  const edges: DrawnEdge[] = situation.links.map(([from, to]) =>
    missedKeys.has(linkKey(situation, from, to))
      ? {
          from,
          to,
          mark: 'missed',
          label: `✓ ${situation.link} on the map`,
          directed: situation.directed,
        }
      : { from, to, mark: 'plain', directed: situation.directed },
  )
  const all = list(situation.links.map(([a, b]) => edgeName(a, b)))
  const names = list(missed.map((edge) => edgeName(edge.from, edge.to)))
  return {
    situation,
    title: 'Correct graph',
    edges,
    vertices: [],
    description: `The correct graph: ${all}. ${
      missed.length
        ? `The ${situation.link}s you missed, ${names}, are marked in green.`
        : `You missed none of them.`
    }`,
  }
}
