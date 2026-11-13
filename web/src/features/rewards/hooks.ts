import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { skillsKey } from '../progress/hooks.ts'
import {
  fetchRewards,
  markRewardsSeen,
  updateRewardsSettings,
  type Rewards,
} from './rewards.api.ts'

export const rewardsKey = ['rewards'] as const

/** The student's points and badges. Refreshed when they come back to the tab, and by
 * `useRefreshRewards` after anything that can earn them (an attempt, a finished module). */
export function useRewards() {
  return useQuery({ queryKey: rewardsKey, queryFn: fetchRewards, staleTime: 30_000 })
}

/** Call after something that can earn points or badges, so they show up straight away, with the
 * skill profile and medals. */
export function useRefreshRewards() {
  const queryClient = useQueryClient()
  return () => {
    void queryClient.invalidateQueries({ queryKey: rewardsKey })
    // The skill profile and the medals follow the same answers (#214).
    void queryClient.invalidateQueries({ queryKey: skillsKey })
  }
}

export function useMarkRewardsSeen() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: markRewardsSeen,
    onSuccess: (rewards) => queryClient.setQueryData<Rewards>(rewardsKey, rewards),
  })
}

export function useRewardsSettings() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: updateRewardsSettings,
    onSuccess: (rewards) => queryClient.setQueryData<Rewards>(rewardsKey, rewards),
  })
}
