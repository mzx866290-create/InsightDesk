import { afterEach, describe, expect, it, vi } from 'vitest'

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

async function importAuthWithFetch(fetchMock: typeof globalThis.fetch) {
  vi.resetModules()
  vi.stubGlobal('fetch', fetchMock)
  return import('./auth')
}

describe('api base configuration', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    vi.unstubAllGlobals()
    vi.resetModules()
    window.sessionStorage.clear()
    window.localStorage.clear()
  })

  it('uses the local Vite proxy by default', async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ ok: true })) as unknown as typeof globalThis.fetch
    const auth = await importAuthWithFetch(fetchMock)

    await auth.authFetch('/sessions')

    const [url] = vi.mocked(fetchMock).mock.calls[0]
    expect(auth.BASE).toBe('/api')
    expect(url).toBe('/api/sessions')
  })

  it('uses VITE_API_BASE_URL for hosted frontend deployments', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://demo.example.com/api/')
    const fetchMock = vi.fn(async () => jsonResponse({ ok: true })) as unknown as typeof globalThis.fetch
    const auth = await importAuthWithFetch(fetchMock)

    auth.saveApiToken('demo-token')
    await auth.authFetch('/sessions')

    const [url, init] = vi.mocked(fetchMock).mock.calls[0]
    const headers = init?.headers as Headers
    expect(auth.BASE).toBe('https://demo.example.com/api')
    expect(url).toBe('https://demo.example.com/api/sessions')
    expect(headers.get('Authorization')).toBe('Bearer demo-token')
  })
})
