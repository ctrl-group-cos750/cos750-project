import { api } from '../../api/client.ts'
import type { User } from '../../auth/api.ts'
import type { AvatarId } from '../../components'

/** Choose a profile picture from the team's set, or null for the initial (FR-1.6). */
export const setAvatar = (avatar: AvatarId | null) =>
  api<User>('/api/me/avatar', { method: 'PUT', body: { avatar } })

/** Change the password (FR-1.5). Every other session ends; this one carries on. */
export const changePassword = (body: { currentPassword: string; newPassword: string }) =>
  api<void>('/api/me/password', { method: 'POST', body })

/** Upload a picture of their own (FR-1.6): a small square image as a data URL. */
export const uploadPicture = (image: string) =>
  api<User>('/api/me/picture', { method: 'PUT', body: { image } })

/** Delete the uploaded picture. */
export const deletePicture = () => api<User>('/api/me/picture', { method: 'DELETE' })
