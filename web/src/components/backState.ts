/** Where a page was opened from, carried in the router's location state, so the page it opens
 * can lead back there (#146): a review path's step, or the BFS visualiser opened from module 3. */
export type BackState = { backTo: string; backLabel: string }

/** The state to pass to a `<Link>` so the page it opens offers a way back to `pathname`. A module
 * page reads "Back to module 3"; anything else uses `label`. */
export function backState(pathname: string, label = 'Back'): BackState {
  const module = /^\/modules\/(\d+)$/.exec(pathname)
  return { backTo: pathname, backLabel: module ? `Back to module ${module[1]}` : label }
}
