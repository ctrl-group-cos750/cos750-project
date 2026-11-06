import { api } from '../../api/client.ts'

/** A badge the student holds, as `GET /api/rewards` sends it (api/app/schemas/rewards.py). */
export type EarnedBadge = {
  /** A catalogue id: see `ACHIEVEMENTS` in components/achievements.ts. */
  badge: string
  /** Tells repeatable badges apart (the bonus quest's id); "" otherwise. */
  ref: string
  tier: 'bronze' | 'gold' | null
  awardedAt: string
  upgradedAt: string | null
  /** False until the app has announced it. */
  seen: boolean
}

export type Rewards = {
  hideRewards: boolean
  points: number
  badges: EarnedBadge[]
}

/** The logged-in student's own points and badges (FR-9.4). */
export function fetchRewards(): Promise<Rewards> {
  return api<Rewards>('/api/rewards')
}

/** Every badge so far has been announced. */
export function markRewardsSeen(): Promise<Rewards> {
  return api<Rewards>('/api/rewards/seen', { method: 'POST' })
}

/** Hide or show points and badges (FR-9.5). They are still earned while hidden. */
export function updateRewardsSettings(input: { hideRewards: boolean }): Promise<Rewards> {
  return api<Rewards>('/api/rewards/settings', { method: 'PUT', body: input })
}
