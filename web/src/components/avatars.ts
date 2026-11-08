/** The profile pictures a student can choose from (FR-1.6). The same ids as `Avatar` in
 * api/app/schemas/profile.py; change both together. */
export const AVATARS = ['vertex', 'edge', 'path', 'cycle', 'tree', 'star', 'grid', 'queue'] as const
export type AvatarId = (typeof AVATARS)[number]

const NAMES: Record<AvatarId, string> = {
  vertex: 'A single vertex',
  edge: 'Two vertices and an edge',
  path: 'A path',
  cycle: 'A cycle',
  tree: 'A tree',
  star: 'A star',
  grid: 'A grid',
  queue: 'A queue',
}

/** A picture's description, for the picker's labels. */
export const avatarName = (avatar: AvatarId) => NAMES[avatar]
