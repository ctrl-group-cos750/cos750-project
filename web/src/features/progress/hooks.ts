import { useQuery } from '@tanstack/react-query'
import { fetchSkills } from './skills.api.ts'

export const skillsKey = ['skills'] as const

/** The skill profile and medals. Refreshed after every answer with the rewards
 * (`useRefreshRewards`), and when a module is finished. */
export function useSkills() {
  return useQuery({ queryKey: skillsKey, queryFn: fetchSkills, staleTime: 30_000 })
}
