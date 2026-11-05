import { Clapperboard, ShieldCheck, UsersRound, type LucideIcon } from 'lucide-react'

/**
 * Every setup area in the staff portal. The portal's side menu and its overview page are both
 * built from this list, so a new staff page needs one entry here plus its route in App.tsx.
 */
export type StaffSection = {
  /** Path under /staff, e.g. "videos" for /staff/videos. */
  path: string
  title: string
  /** One sentence on the overview page: what a team member sets up here. */
  description: string
  icon: LucideIcon
}

export const STAFF_SECTIONS: StaffSection[] = [
  {
    path: 'videos',
    title: 'Videos',
    description:
      'Upload narrated videos and set up their checkpoints, questions, feedback and hints.',
    icon: Clapperboard,
  },
  {
    path: 'accounts',
    title: 'Accounts',
    description: 'Every account that has been created: progress and stats, and deleting one.',
    icon: UsersRound,
  },
  {
    path: 'members',
    title: 'Staff members',
    description: 'Give a registered account access to the staff portal, or take it away.',
    icon: ShieldCheck,
  },
]
