/** A failed API call. `status` is 0 when the request never reached the server. */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export const OFFLINE_MESSAGE = "Can't reach Ctrl Academy. Check your connection and try again."
const FALLBACK_MESSAGE = 'Something went wrong. Try again in a moment.'

/**
 * Calls the API on the same origin. The session cookie travels with every request; bodies are
 * always JSON, which the API requires for anything that changes state (SE document NFR-S6).
 */
export async function api<T>(path: string, options: { method?: string; body?: unknown } = {}) {
  const { method = 'GET', body } = options
  let res: Response
  try {
    res = await fetch(path, {
      method,
      credentials: 'same-origin',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, OFFLINE_MESSAGE)
  }
  if (!res.ok) throw new ApiError(res.status, await errorMessage(res))
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

/** The API's own message when it sent one (FastAPI's `detail` string), else a general one. */
async function errorMessage(res: Response): Promise<string> {
  try {
    const body: unknown = await res.json()
    if (
      typeof body === 'object' &&
      body !== null &&
      'detail' in body &&
      typeof body.detail === 'string'
    ) {
      return body.detail
    }
  } catch {
    // Not JSON: fall through.
  }
  return FALLBACK_MESSAGE
}
