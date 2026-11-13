import {
  BookOpenText,
  ChartColumn,
  GraduationCap,
  Clapperboard,
  ShieldCheck,
  UsersRound,
  type LucideIcon,
} from 'lucide-react'

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
    path: 'content',
    title: 'Content',
    description:
      'Edit the modules and their steps, activities and hints, objectives, review paths and graphs.',
    icon: BookOpenText,
  },
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
    path: 'readiness',
    title: 'Before the lecture',
    description:
      'For the lecturer: who is ready, each objective across the class, and the wrong answers to address first.',
    icon: GraduationCap,
  },
  {
    path: 'pilot',
    title: 'Pilot data',
    description:
      'Where students struggle and stop, and the attempts and hints as CSV for the evaluation.',
    icon: ChartColumn,
  },
  {
    path: 'members',
    title: 'Staff members',
    description: 'Give a registered account access to the staff portal, or take it away.',
    icon: ShieldCheck,
  },
]
