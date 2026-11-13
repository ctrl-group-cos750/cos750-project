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
 * Kept per device rather than on the account: they are about how this screen behaves, and storing
 * them would need a migration for no gain.
 */
export type Preference = 'confetti' | 'comments'

const PREFIX = 'ctrl-academy.'
const CHANGED = 'ctrl-academy:preference-changed'
const listeners = new Set<(name: Preference, on: boolean) => void>()

export function preference(name: Preference): boolean {
  try {
    return localStorage.getItem(PREFIX + name) !== 'off'
  } catch {
    return true // storage blocked: the default
  }
}

export function setPreference(name: Preference, on: boolean): void {
  try {
    localStorage.setItem(PREFIX + name, on ? 'on' : 'off')
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
