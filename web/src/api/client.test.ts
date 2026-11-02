import { describe, expect, it, vi } from 'vitest'
import { api, ApiError } from './client.ts'

function respondWith(response: Response) {
  const fetch = vi.fn<typeof globalThis.fetch>(() => Promise.resolve(response))
  vi.stubGlobal('fetch', fetch)
  return fetch
}

describe('api', () => {
  it('sends JSON bodies with a JSON content type and the session cookie', async () => {
    const fetch = respondWith(Response.json({ ok: true }))
    await expect(api('/api/x', { method: 'POST', body: { a: 1 } })).resolves.toEqual({ ok: true })
    expect(fetch).toHaveBeenCalledWith('/api/x', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: '{"a":1}',
    })
  })

  it('sends GETs without a body or content type', async () => {
    const fetch = respondWith(Response.json([]))
    await api('/api/x')
    expect(fetch.mock.calls[0][1]).toMatchObject({
      method: 'GET',
      headers: undefined,
      body: undefined,
    })
  })

  it('returns nothing for 204 No Content', async () => {
    respondWith(new Response(null, { status: 204 }))
    await expect(api('/api/x', { method: 'POST' })).resolves.toBeUndefined()
  })

  it("uses the API's message and status for an error", async () => {
    respondWith(Response.json({ detail: 'Nope.' }, { status: 403 }))
    const error = await api('/api/x').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 403, message: 'Nope.' })
  })

  it.each([
    ['plain text', new Response('Bad gateway', { status: 502 })],
    ['a validation list', Response.json({ detail: [{ msg: 'x' }] }, { status: 422 })],
  ])('falls back to a general message for %s', async (_case, response) => {
    respondWith(response)
    await expect(api('/api/x')).rejects.toMatchObject({
      message: 'Something went wrong. Try again in a moment.',
    })
  })

  it('collects validation errors by field', async () => {
    respondWith(
      Response.json(
        {
          detail: [
            { loc: ['body', 'password'], msg: 'Too common.' },
            { loc: ['body', 'password'], msg: 'A second complaint.' },
            { loc: ['body', 'email'], msg: 'Not an email.' },
            { loc: 'not a list', msg: 'ignored' },
            'not an object',
          ],
        },
        { status: 422 },
      ),
    )
    await expect(api('/api/x')).rejects.toMatchObject({
      status: 422,
      fields: { password: 'Too common.', email: 'Not an email.' },
    })
  })

  it('has no field errors for other failures', async () => {
    respondWith(Response.json({ detail: 'Nope.' }, { status: 403 }))
    await expect(api('/api/x')).rejects.toMatchObject({ fields: {} })
  })

  it('reports status 0 when the request never arrives', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof globalThis.fetch>(() => Promise.reject(new TypeError())),
    )
    await expect(api('/api/x')).rejects.toMatchObject({ status: 0 })
  })
})
