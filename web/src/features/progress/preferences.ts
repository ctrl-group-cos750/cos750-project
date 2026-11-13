import { useSyncExternalStore } from 'react'

/**
 * The student's feedback switches (#214), kept on this device (localStorage), both on by default:
 *
 * - `confetti`: a short confetti burst for a right answer, a bigger one for a finished module or
 *   being ready for the lecture (confetti.ts).
 * - `comments`: encouraging comments: the varied line under a right answer and the progress
 *   remark ("You've practised 3 of 8 objectives so far"). Off, a right answer shows only its own
 *   explanation.
 *
 * Kept on this device rather than on the account (storing them would need a migration), but per
 * student: the key carries the signed-in student's id (`setPreferenceOwner`, from the signed-in
 * layout), so on a shared lab computer one student turning confetti off doesn't turn it off for
 * the next (#215 review). The profile says they are kept on this device.
 */
export type Preference = 'confetti' | 'comments'

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
