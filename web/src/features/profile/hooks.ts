import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { User } from '../../auth/api.ts'
import { meKey } from '../../auth/hooks.ts'
import { changePassword, deletePicture, setAvatar, uploadPicture } from './profile.api.ts'

export function useSetAvatar() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: setAvatar,
    onSuccess: (user) => queryClient.setQueryData<User | null>(meKey, user),
  })
}

export function useUploadPicture() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: uploadPicture,
    onSuccess: (user) => queryClient.setQueryData<User | null>(meKey, user),
  })
}

export function useDeletePicture() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deletePicture,
    onSuccess: (user) => queryClient.setQueryData<User | null>(meKey, user),
  })
}

export function useChangePassword() {
  return useMutation({ mutationFn: changePassword })
}
