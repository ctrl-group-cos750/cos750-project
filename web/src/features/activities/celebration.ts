import { createContext } from 'react'

/** Whether a right answer here gets the success moment. False for every question in module 6,
 * the mastery check (ModulePage provides it), withheld or not: its recall questions too, so the
 * check stays calm throughout (#215 review). */
export const CelebrationAllowed = createContext(true)
