import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchMe, login, logout, register, type User } from './api.ts'

export const meKey = ['auth', 'me'] as const

/** The logged-in user (null when logged out). Asked once, then kept until login or logout. */
export function useCurrentUser() {
  return useQuery({ queryKey: meKey, queryFn: fetchMe, staleTime: Infinity, retry: false })
}

export function useLogin() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: login,
    onSuccess: (user) => queryClient.setQueryData<User | null>(meKey, user),
  })
}

export function useRegister() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: register,
    onSuccess: (user) => queryClient.setQueryData<User | null>(meKey, user),
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: logout,
    onSuccess: () => {
      // Forget everything cached for this student before anyone else uses the browser.
      queryClient.clear()
      queryClient.setQueryData<User | null>(meKey, null)
    },
  })
}
