/**
 * The badge catalogue (SE document FR-9.3, issue #32). Names and wording are working copy for the
 * ID team to confirm; the rules that award each badge live on the server.
 *
 * Every badge names a skill the student now has, not an action they did, and none marks a failure
 * (research note: vault/cos750/research/points-badges.md). There are no streak, speed, "perfect"
 * or rank badges on purpose.
 */

/** Which picture a badge shows. */
export type AchievementGlyph =
  | 'word-smith'
  | 'edge-spotter'
  | 'map-maker'
  | 'right-tool'
  | 'queue-tracer'
  | 'bfs-builder'
  | 'bug-hunter'
  | 'shortcut-finder'
  | 'ready-for-lecture'
  | 'came-back-stronger'
  | 'solo-run'
  | 'quest'
  | 'all-quests'
  | 'first-module'

/**
 * The badge's shape. Objective badges are hexagons with two tiers; milestones are medals; quest
 * badges are shields; the hidden badge is a diamond.
 */
export type AchievementKind = 'objective' | 'milestone' | 'quest' | 'hidden'

export type Achievement = {
  id: string
  name: string
  kind: AchievementKind
  glyph: AchievementGlyph
  /** The learning objective an objective badge stands for (ID document §3.1). */
  objective?: number
  /** What the badge means, in words that praise the skill or the strategy, not the student. */
  description: string
  /**
   * False while the course has nothing that earns it, so the shelf doesn't ask for it.
   */
  offered?: boolean
}

export const ACHIEVEMENTS: readonly Achievement[] = [
  {
    id: 'lo1',
    name: 'Word Smith',
    kind: 'objective',
    glyph: 'word-smith',
    objective: 1,
    description: 'You can tell a data structure, an algorithm, a graph and a traversal apart.',
  },
  {
    id: 'lo2',
    name: 'Edge Spotter',
    kind: 'objective',
    glyph: 'edge-spotter',
    objective: 2,
    description:
      'You can pick out vertices and edges, and tell a directed graph from an undirected one.',
  },
  {
    id: 'lo3',
    name: 'Map Maker',
    kind: 'objective',
    glyph: 'map-maker',
    objective: 3,
    description: 'You can turn a real network, like the campus, into a graph.',
  },
  {
    id: 'lo4',
    name: 'Right Tool',
    kind: 'objective',
    glyph: 'right-tool',
    objective: 4,
    description: 'You can say when breadth-first search is the right way to explore a graph.',
  },
  {
    id: 'lo5',
    name: 'Queue Tracer',
    kind: 'objective',
    glyph: 'queue-tracer',
    objective: 5,
    description:
      'You traced BFS by hand, level by level: the queue, the visited set and the order.',
  },
  {
    id: 'lo6',
    name: 'BFS Builder',
    kind: 'objective',
    glyph: 'bfs-builder',
    objective: 6,
    description: 'You put BFS together in Python, with a queue and a visited set.',
  },
  {
    id: 'lo7',
    name: 'Bug Hunter',
    kind: 'objective',
    glyph: 'bug-hunter',
    objective: 7,
    description: 'You found the bugs in a faulty BFS and chose the tests that expose them.',
  },
  {
    id: 'lo8',
    name: 'Shortcut Finder',
    kind: 'objective',
    glyph: 'shortcut-finder',
    objective: 8,
    description: 'You used BFS to find the shortest route, and can say why it is the shortest.',
  },
  {
    id: 'ready-for-lecture',
    name: 'Ready for the Lecture',
    kind: 'milestone',
    glyph: 'ready-for-lecture',
    description: 'Every objective is met. You are ready for the graphs lecture.',
  },
  {
    id: 'came-back-stronger',
    name: 'Came Back Stronger',
    kind: 'milestone',
    glyph: 'came-back-stronger',
    description: 'You went back over an objective in the review path and met it.',
  },
  {
    id: 'first-module',
    name: 'First Module',
    kind: 'milestone',
    glyph: 'first-module',
    description: 'You worked all the way through your first module.',
  },
  {
    id: 'solo-run',
    name: 'Solo Run',
    kind: 'milestone',
    glyph: 'solo-run',
    description: 'You met every objective on your own, without the worked solution.',
  },
  {
    id: 'quest',
    name: 'Quest',
    kind: 'quest',
    glyph: 'quest',
    description: 'You finished a bonus quest. One of these for every quest you complete.',
  },
  {
    id: 'all-quests',
    name: 'All Quests',
    kind: 'quest',
    glyph: 'all-quests',
    description: 'You finished every bonus quest.',
  },
]
