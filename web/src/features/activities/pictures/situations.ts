/**
 * The situations behind module 1's graph questions (#155): each place on a map, where it sits in
 * the drawing, and the map's own links (walkways, roads). This is what the student is shown
 * anyway (the map and the module's text name every walkway), so it is not the answer key: the
 * answer key stays on the server. A drawing of the student's answer is judged against this map,
 * never against the stored solution.
 *
 * A graph uses the same layout as its map (the approved mock-ups in the workspace,
 * vault/analysis/cos750-2026-11-11/mockups/module-1/).
 */
import busMap from './assets/bus-map.svg'
import campusMap from './assets/campus-map.svg'
import deliveryRoute from './assets/delivery-route.svg'
import friendships from './assets/friendships.svg'
import roadsBetweenTowns from './assets/roads-between-towns.svg'
import whoFollowsWhom from './assets/who-follows-whom.svg'

export type Place = { id: string; name: string; x: number; y: number }

/** A map as a graph: its places, and the links between them as pairs of place ids. */
export type Situation = {
  /** What a link is called on this map, e.g. "walkway" or "road". */
  link: string
  /** What a place is called on this map, e.g. "place" or "bus stop". */
  place: string
  width: number
  height: number
  places: readonly Place[]
  links: readonly (readonly [string, string])[]
  directed: boolean
}

/** A picture of the situation itself: an illustration, with its text alternative. */
export type MapPicture = {
  src: string
  /** The tab and caption name, e.g. "Campus map". */
  name: string
  alt: string
  width: number
  height: number
}

export const CAMPUS: Situation = {
  link: 'walkway',
  place: 'place',
  width: 900,
  height: 620,
  directed: false,
  places: [
    { id: 'A', name: 'Admin block', x: 370, y: 308 },
    { id: 'B', name: 'Bookshop', x: 150, y: 140 },
    { id: 'C', name: 'Computer Science', x: 460, y: 128 },
    { id: 'D', name: 'Dining hall', x: 767, y: 505 },
    { id: 'E', name: 'Engineering', x: 485, y: 497 },
    { id: 'F', name: 'Fountain', x: 640, y: 282 },
    { id: 'G', name: 'Green', x: 150, y: 390 },
  ],
  links: [
    ['A', 'C'],
    ['A', 'E'],
    ['B', 'C'],
    ['B', 'G'],
    ['C', 'F'],
    ['D', 'E'],
    ['E', 'F'],
  ],
}

export const BUS: Situation = {
  link: 'road',
  place: 'bus stop',
  width: 880,
  height: 580,
  directed: false,
  places: [
    { id: 'P', name: 'Park', x: 170, y: 150 },
    { id: 'Q', name: 'Quad', x: 470, y: 170 },
    { id: 'R', name: 'Residence', x: 300, y: 440 },
    { id: 'S', name: 'Station', x: 690, y: 420 },
  ],
  links: [
    ['P', 'Q'],
    ['Q', 'R'],
    ['Q', 'S'],
    ['R', 'S'],
  ],
}

const triangle = (ids: readonly [string, string, string], names: readonly string[]) =>
  [
    { id: ids[0], name: names[0], x: 220, y: 100 },
    { id: ids[1], name: names[1], x: 100, y: 215 },
    { id: ids[2], name: names[2], x: 340, y: 215 },
  ] satisfies Place[]

/** The four graphs in "Directed or undirected?" (activity 106), keyed by its row ids. */
export const CLASSIFY: Record<
  string,
  { situation: Situation; picture: MapPicture; meaning: { directed: string; undirected: string } }
> = {
  friends: {
    situation: {
      link: 'friendship',
      place: 'person',
      width: 440,
      height: 300,
      directed: false,
      places: triangle(['T', 'S', 'L'], ['Thandi', 'Sipho', 'Lerato']),
      links: [
        ['L', 'S'],
        ['S', 'T'],
        ['T', 'L'],
      ],
    },
    picture: {
      src: friendships,
      name: 'Friendships',
      alt: 'Friendships at a residence: Thandi, Sipho and Lerato are all friends with each other.',
      width: 440,
      height: 300,
    },
    meaning: {
      directed:
        "Each friendship would go one way only, so Thandi could be Sipho's friend without Sipho being Thandi's.",
      undirected: 'Each friendship goes both ways.',
    },
  },
  follows: {
    situation: {
      link: 'follow',
      place: 'person',
      width: 440,
      height: 300,
      directed: true,
      places: triangle(['B', 'A', 'C'], ['Ben', 'Ana', 'Cara']),
      links: [
        ['A', 'B'],
        ['B', 'A'],
        ['B', 'C'],
      ],
    },
    picture: {
      src: whoFollowsWhom,
      name: 'Who follows whom',
      alt: 'Who follows whom online: Ana follows Ben, Ben follows Ana, and Ben follows Cara.',
      width: 440,
      height: 300,
    },
    meaning: {
      directed: 'Each follow goes one way: Ben follows Cara, but Cara does not follow Ben.',
      undirected:
        'Every follow would go both ways, so Cara would follow Ben back. She does not: the edges are arrows.',
    },
  },
  route: {
    situation: {
      link: 'stretch of the route',
      place: 'stop',
      width: 440,
      height: 340,
      directed: true,
      places: [
        { id: 'Y', name: 'Shop Y', x: 220, y: 110 },
        { id: 'W', name: 'Warehouse', x: 100, y: 240 },
        { id: 'X', name: 'Shop X', x: 340, y: 240 },
      ],
      links: [
        ['W', 'X'],
        ['X', 'Y'],
        ['Y', 'W'],
      ],
    },
    picture: {
      src: deliveryRoute,
      name: 'Delivery route',
      alt: 'A delivery route: a van drives from the Warehouse to Shop X, from Shop X to Shop Y, and from Shop Y back to the Warehouse, always in that direction.',
      width: 440,
      height: 340,
    },
    meaning: {
      directed: 'The van drives each stretch in one direction only.',
      undirected:
        'The van could drive each road either way, for example from Shop X back to the Warehouse. The route only goes Warehouse to Shop X to Shop Y and back to the Warehouse.',
    },
  },
  roads: {
    situation: {
      link: 'road',
      place: 'town',
      width: 440,
      height: 300,
      directed: false,
      places: [
        { id: 'J', name: 'Johannesburg', x: 240, y: 170 },
        { id: 'P', name: 'Pretoria', x: 330, y: 70 },
        { id: 'S', name: 'Soweto', x: 100, y: 200 },
      ],
      links: [
        ['J', 'P'],
        ['J', 'S'],
      ],
    },
    picture: {
      src: roadsBetweenTowns,
      name: 'Roads between towns',
      alt: 'Roads join Johannesburg to Pretoria and Johannesburg to Soweto. Cars drive both ways.',
      width: 440,
      height: 300,
    },
    meaning: {
      directed:
        'Each road would be one-way, so you could drive from Johannesburg to Pretoria but not back.',
      undirected: 'Each road can be driven both ways.',
    },
  },
}

export const CAMPUS_MAP: MapPicture = {
  src: campusMap,
  name: 'Campus map',
  alt: 'A campus map with seven places and seven walkways: Admin block to Computer Science, Admin block to Engineering, Bookshop to Computer Science, Bookshop to the Green, Computer Science to the Fountain, Dining hall to Engineering, and Engineering to the Fountain.',
  width: 900,
  height: 620,
}

export const BUS_MAP: MapPicture = {
  src: busMap,
  name: 'Bus map',
  alt: 'A bus map with four bus stops: the Park, the Quad, the Residence and the Station. Roads join the Park to the Quad, the Quad to the Residence, the Quad to the Station, and the Residence to the Station. Buses drive every road both ways.',
  width: 880,
  height: 580,
}

export const placeById = (situation: Situation, id: string) =>
  situation.places.find((place) => place.id === id)

/** The same link, either way round, in an undirected situation. */
export const linkKey = (situation: Situation, a: string, b: string) =>
  situation.directed ? `${a}>${b}` : [a, b].sort().join('-')
