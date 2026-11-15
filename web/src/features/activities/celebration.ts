import { createContext } from 'react'

/** Whether a right answer here gets the success moment (and the companion). False for every
 * question in module 6, the mastery check (ModulePage provides it), withheld or not: its recall
 * questions too, so the check stays calm throughout (#215 review). False too for any question
 * whose purpose is "mastery", such as a review path's fresh items (ActivityView, #222 review). */
export const CelebrationAllowed = createContext(true)
