import { deviceValue, preferenceOwner, setDeviceValue } from '../progress/preferences.ts'
import type { Medal, ModuleMedal } from '../progress/skills.api.ts'

const RANK: Record<Medal, number> = { finished: 1, silver: 2, gold: 3 }
const KEY = 'medals-announced'

/** A module medal to announce: "Module 2: silver medal" (#214). */
export type MedalNote = { key: string; moduleId: number; tier: Medal }

/**
 * Which module medals are new since the student last saw them, announced once (#214). Medals are
 * worked out from answers (api/app/services/skills.py), so there is no server record of them
 * being shown: the ones already announced are kept per student on this device. The first time a
 * device sees a student, their medals so far are recorded without a note (they were earned
 * before), so only a medal earned (or raised) from then on is announced. `quiet` (points and
 * badges hidden) records them without notes too, so turning badges back on brings no burst.
 */
export function newMedals(modules: readonly ModuleMedal[], quiet = false): MedalNote[] {
  if (preferenceOwner() === null) return []
  const stored = deviceValue(KEY)
  let known: Record<string, Medal> = {}
  try {
    known = stored ? (JSON.parse(stored) as Record<string, Medal>) : {}
  } catch {
    known = {}
  }
  const fresh: MedalNote[] = []
  const next = { ...known }
  for (const m of modules) {
    if (!m.complete || m.medal === null) continue
    const before = known[String(m.moduleId)]
    if (before !== undefined && (RANK[before] ?? 0) >= RANK[m.medal]) continue
    next[String(m.moduleId)] = m.medal
    if (stored !== null && !quiet)
      fresh.push({ key: `medal:${m.moduleId}:${m.medal}`, moduleId: m.moduleId, tier: m.medal })
  }
  if (stored === null || fresh.length > 0 || JSON.stringify(next) !== JSON.stringify(known))
    setDeviceValue(KEY, JSON.stringify(next))
  return fresh
}
