import { ApiError } from './client.ts'

/**
 * React Query's `retry` for a page's main request: try again on a network error or a 5xx (up to
 * three times), but never when the API refused (any 4xx: 403 locked, 404 missing, 429 too many).
 * Asking again gets the same answer, so the page should say why at once instead of spinning for
 * several seconds while it retries (#162 review).
 */
export function retryUnlessRefused(failures: number, error: Error): boolean {
  const refused = error instanceof ApiError && error.status >= 400 && error.status < 500
  return !refused && failures < 3
}
