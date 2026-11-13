import { useSyncExternalStore } from 'react'

/**
 * The student's switches for what they see while they learn (#214), kept on this device
 * (localStorage), all on by default. Points and badges (with the module medals) are the one
 * switch kept on the account instead (`hideRewards`, FR-9.5).
 *
 * - `confetti`: a short confetti burst for a right answer, a bigger one for a finished module or
 *   being ready for the lecture (confetti.ts).
 * - `comments`: encouraging comments: the varied line under a right answer and the progress
 *   remark ("You've practised 3 of 8 objectives so far"). Off, a right answer shows only its own
 *   explanation.
 * - `skillProfile`: the skill profile on the home page (the radar chart) and in the progress panel.
 *   The mastery report keeps its profile: the report is never hidden (FR-7.3).
 * - `progressPanel`: the progress panel beside a lesson, and its strip under it on a phone. Off,
 *   the lesson takes the full width.
 *
 * Kept on this device rather than on the account (storing them would need a migration), but per
 * student: the key carries the signed-in student's id (`setPreferenceOwner`, from the signed-in
 * layout), so on a shared lab computer one student turning confetti off doesn't turn it off for
 * the next (#215 review). The profile says they are kept on this device.
 */
export type Preference = 'confetti' | 'comments' | 'skillProfile' | 'progressPanel'

const PREFIX = 'ctrl-academy.'
const CHANGED = 'ctrl-academy:preference-changed'
const listeners = new Set<(name: Preference, on: boolean) => void>()

// The signed-in student, whose switches are read and written; null before sign-in.
let owner: number | null = null

function key(name: Preference): string {
  return owner === null ? PREFIX + name : `${PREFIX}${owner}.${name}`
}

/** Whose switches these are: the signed-in student's id. Safe to call on every render; when it
 * changes, every switch on the page is read again. */
export function setPreferenceOwner(id: number | null): void {
  if (id === owner) return
  owner = id
  // After the render that set it: other components re-read their switches then.
  queueMicrotask(() => window.dispatchEvent(new Event(CHANGED)))
}

export function preference(name: Preference): boolean {
  try {
    return localStorage.getItem(key(name)) !== 'off'
  } catch {
    return true // storage blocked: the default
  }
}

export function setPreference(name: Preference, on: boolean): void {
  try {
    localStorage.setItem(key(name), on ? 'on' : 'off')
  } catch {
    // storage blocked: nothing to keep it in
  }
  for (const listener of listeners) listener(name, on)
  window.dispatchEvent(new Event(CHANGED))
}

/** Called whenever a switch changes on this page, e.g. to stop confetti already falling. */
export function onPreferenceChange(listener: (name: Preference, on: boolean) => void): void {
  listeners.add(listener)
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener(CHANGED, onChange)
  window.addEventListener('storage', onChange)
  return () => {
    window.removeEventListener(CHANGED, onChange)
    window.removeEventListener('storage', onChange)
  }
}

/** A switch, kept in step across the page (and other tabs). */
export function usePreference(name: Preference): [boolean, (on: boolean) => void] {
  const on = useSyncExternalStore(
    subscribe,
    () => preference(name),
    () => true,
  )
  return [on, (next: boolean) => setPreference(name, next)]
}

/**
 * Panels a student can minimise (#214), separate from switching a feature off: a minimised panel
 * is still there, as its header (the progress panel as a narrow rail), and opens again with one
 * press. Kept per student on this device like the switches, until reopened. Minimising changes
 * nothing that is recorded or earned.
 *
 * - `skillProfile`: the skill profile card on the home page.
 * - `progressPanel`: the progress panel beside a lesson (a rail when minimised).
 * - `moduleGoals`: a module's "By the end of this module you can" box: minimised, it stays
 *   closed on every segment until opened again.
 */
export type Panel = 'skillProfile' | 'progressPanel' | 'moduleGoals'

function panelKey(name: Panel): string {
  return owner === null ? `${PREFIX}minimised.${name}` : `${PREFIX}${owner}.minimised.${name}`
}

export function panelMinimised(name: Panel): boolean {
  try {
    return localStorage.getItem(panelKey(name)) === 'yes'
  } catch {
    return false
  }
}

export function setPanelMinimised(name: Panel, minimised: boolean): void {
  try {
    if (minimised) localStorage.setItem(panelKey(name), 'yes')
    else localStorage.removeItem(panelKey(name))
  } catch {
    // storage blocked: it lasts as long as the page
  }
  window.dispatchEvent(new Event(CHANGED))
}

/** Whether a panel is minimised, kept in step across the page. */
export function usePanelMinimised(name: Panel): [boolean, (minimised: boolean) => void] {
  const minimised = useSyncExternalStore(
    subscribe,
    () => panelMinimised(name),
    () => false,
  )
  return [minimised, (next: boolean) => setPanelMinimised(name, next)]
}

/**
 * The page background (#214): soft corner glows (the default), the doodle wallpaper with gentler
 * glows behind it, or the plain page. Kept per student on this device like the switches above,
 * and applied as <html data-bg> by theme/background.ts (styles/backgrounds.css paints it).
 */
export type Background = 'glow' | 'doodles' | 'plain'

export const BACKGROUNDS: readonly Background[] = ['glow', 'doodles', 'plain']

function backgroundKey(): string {
  return owner === null ? `${PREFIX}background` : `${PREFIX}${owner}.background`
}

export function storedBackground(): Background {
  try {
    const value = localStorage.getItem(backgroundKey())
    return BACKGROUNDS.includes(value as Background) ? (value as Background) : 'glow'
  } catch {
    return 'glow'
  }
}

export function setStoredBackground(background: Background): void {
  try {
    localStorage.setItem(backgroundKey(), background)
  } catch {
    // storage blocked: it lasts as long as the page
  }
  window.dispatchEvent(new Event(CHANGED))
}

/** The student's background, kept in step across the page (the profile and the header menu). */
export function useBackground(): [Background, (background: Background) => void] {
  const background = useSyncExternalStore(subscribe, storedBackground, () => 'glow' as Background)
  return [background, setStoredBackground]
}

/** A value kept for the signed-in student on this device (null if none, or storage is blocked):
 * for small records such as which module medals have been announced (#214). */
export function deviceValue(name: string): string | null {
  try {
    return localStorage.getItem(owner === null ? `${PREFIX}${name}` : `${PREFIX}${owner}.${name}`)
  } catch {
    return null
  }
}

export function setDeviceValue(name: string, value: string): void {
  try {
    localStorage.setItem(owner === null ? `${PREFIX}${name}` : `${PREFIX}${owner}.${name}`, value)
  } catch {
    // storage blocked: it lasts as long as the page
  }
}

/** The signed-in student this device's switches belong to, or null before sign-in. */
export function preferenceOwner(): number | null {
  return owner
}
