import type { ModuleSummary } from './module.types.ts'

/** What a locked module waits for (FR-2.1, #214): the mastery check, the last module, opens once
 * every module between the first and it is complete or tested out. A module with no content yet
 * doesn't hold it back. The same rule as `_statuses` in api/app/services/modules.py, worked out
 * here from the module list, which already carries every status. */
export type UnlockNeeds = {
  /** The modules that count, first and last by number: "modules 1 to 5". */
  from: number
  to: number
  /** Those still to finish or test out of, in order. */
  remaining: ModuleSummary[]
}

/** Why `module` is locked, or null if it isn't (or isn't the one the rule locks). */
export function unlockNeeds(modules: ModuleSummary[], module: ModuleSummary): UnlockNeeds | null {
  if (module.status !== 'locked' || modules.length < 2) return null
  const ordered = [...modules].sort((a, b) => a.number - b.number)
  if (ordered[ordered.length - 1].id !== module.id) return null
  const between = ordered.slice(1, -1).filter((m) => m.segmentCount > 0)
  if (between.length === 0) return null
  return {
    from: between[0].number,
    to: between[between.length - 1].number,
    remaining: between.filter((m) => m.status !== 'complete' && m.status !== 'tested_out'),
  }
}
