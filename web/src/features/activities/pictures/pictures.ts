/**
 * Which module 1 question or text segment shows which picture (#155). Keyed by the fixture ids
 * in api/app/seed/module-1.json, which never change. Only practice items are listed: a mastery
 * item never gets the correct graph (#144), and a test checks that every activity here is a
 * practice item. The closing task (activity 107) has no picture on purpose: one would hint that
 * stations are vertices.
 */
import { mapDrawing, type Drawing } from './drawing.ts'
import {
  BUS,
  BUS_MAP,
  CAMPUS,
  CAMPUS_MAP,
  CLASSIFY,
  PQRS,
  type MapPicture,
  type Situation,
} from './situations.ts'

export type Picture =
  | { kind: 'map'; map: MapPicture }
  | { kind: 'drawing'; drawing: Drawing; name: string }
  | { kind: 'grid'; name: string; items: readonly { caption: string; picture: Picture }[] }

export type ActivityPictures = {
  /** The situation picture beside the question. */
  picture: Picture
  /** For a matching question about a map: the map its answers are drawn and judged on. */
  situation?: Situation
  /** "Directed or undirected?": each row's graph, redrawn as the student classified it. */
  classify?: boolean
}

const campusGraph = mapDrawing(
  CAMPUS,
  'The campus graph',
  'The campus as a graph. Vertices A to G, one for each place: A Admin block, B Bookshop, C Computer Science, D Dining hall, E Engineering, F Fountain, G Green. Edges A–C, A–E, B–C, B–G, C–F, D–E and E–F.',
)

const pqrs = mapDrawing(
  PQRS,
  'The graph in this question',
  'A graph with vertices P, Q, R and S, and edges P–Q, Q–R and Q–S.',
)

const ACTIVITIES: Record<number, ActivityPictures> = {
  101: { picture: { kind: 'map', map: CAMPUS_MAP } },
  103: { picture: { kind: 'drawing', drawing: pqrs, name: 'The graph' } },
  104: { picture: { kind: 'map', map: BUS_MAP }, situation: BUS },
  105: { picture: { kind: 'map', map: CAMPUS_MAP }, situation: CAMPUS },
  106: {
    classify: true,
    picture: {
      kind: 'grid',
      name: 'The four graphs',
      items: (['friends', 'follows', 'route', 'roads'] as const).map((row) => ({
        caption: CLASSIFY[row].picture.name,
        picture: { kind: 'map', map: CLASSIFY[row].picture },
      })),
    },
  },
}

const SEGMENTS: Record<number, Picture> = {
  101: { kind: 'map', map: CAMPUS_MAP },
  105: { kind: 'drawing', drawing: campusGraph, name: 'The campus graph' },
}

export const picturesForActivity = (id: number): ActivityPictures | undefined => ACTIVITIES[id]
export const pictureForSegment = (id: number): Picture | undefined => SEGMENTS[id]
export const PICTURED_ACTIVITY_IDS = Object.keys(ACTIVITIES).map(Number)

export const pictureName = (picture: Picture): string =>
  picture.kind === 'map' ? picture.map.name : picture.name
