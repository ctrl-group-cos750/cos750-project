import { api, ApiError } from '../api/client.ts'
import type { AvatarId } from '../components/avatars.ts'

export type User = {
  id: number
  email: string
  displayName: string
  isStaff: boolean
  /** The profile picture they chose (FR-1.6), or null for their initial. */
  avatar: AvatarId | null
}

export type Credentials = { email: string; password: string }
export type Registration = Credentials & { displayName: string }

export const register = (body: Registration) =>
  api<User>('/api/auth/register', { method: 'POST', body })

export const login = (body: Credentials) => api<User>('/api/auth/login', { method: 'POST', body })

export const logout = () => api<void>('/api/auth/logout', { method: 'POST' })

/** The logged-in user, or null when there is no session. */
export async function fetchMe(): Promise<User | null> {
  try {
    return await api<User>('/api/auth/me')
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null
    throw error
  }
}
