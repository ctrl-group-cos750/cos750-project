/** A failed API call. `status` is 0 when the request never reached the server. */
export class ApiError extends Error {
  readonly status: number
  /** For 422: what's wrong with each field, by field name ("password", "email"). */
  readonly fields: Record<string, string>

  constructor(status: number, message: string, fields: Record<string, string> = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.fields = fields
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
  if (!res.ok) {
    const answer = await readJson(res)
    throw new ApiError(res.status, errorMessage(answer), fieldErrors(answer))
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

async function readJson(res: Response): Promise<unknown> {
  try {
    return await res.json()
  } catch {
    return null // not JSON
  }
}

function detail(body: unknown): unknown {
  return typeof body === 'object' && body !== null && 'detail' in body ? body.detail : undefined
}

/** The API's own message when it sent one (FastAPI's `detail` string), else a general one. */
function errorMessage(body: unknown): string {
  const d = detail(body)
  return typeof d === 'string' ? d : FALLBACK_MESSAGE
}

/** A validation error's message per field: {"loc": ["body", "password"], "msg": "…"} → password. */
function fieldErrors(body: unknown): Record<string, string> {
  const d = detail(body)
  const fields: Record<string, string> = {}
  if (!Array.isArray(d)) return fields
  for (const item of d as unknown[]) {
    if (typeof item !== 'object' || item === null) continue
    const { loc, msg } = item as { loc?: unknown; msg?: unknown }
    const field = Array.isArray(loc) ? loc.at(-1) : undefined
    if (typeof field === 'string' && typeof msg === 'string' && !(field in fields)) {
      fields[field] = msg
    }
  }
  return fields
}
