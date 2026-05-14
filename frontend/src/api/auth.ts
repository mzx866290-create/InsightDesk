const runtimeEnv =
  typeof import.meta !== 'undefined' && typeof import.meta.env !== 'undefined'
    ? import.meta.env
    : undefined

const rawApiBase = (runtimeEnv?.VITE_API_BASE_URL ?? '').trim()

export const BASE = (rawApiBase || '/api').replace(/\/+$/, '')

const API_TOKEN_STORAGE_KEY = 'api_token'
const ADMIN_API_TOKEN_STORAGE_KEY = 'admin_api_token'

function getBrowserStorage(kind: 'session' | 'local'): Storage | null {
  if (typeof window === 'undefined') return null
  try {
    return kind === 'session' ? window.sessionStorage : window.localStorage
  } catch {
    return null
  }
}

function cleanupLegacyApiTokenStorage(): void {
  const legacyStorage = getBrowserStorage('local')
  if (!legacyStorage) return
  try {
    legacyStorage.removeItem(API_TOKEN_STORAGE_KEY)
    legacyStorage.removeItem(ADMIN_API_TOKEN_STORAGE_KEY)
  } catch {
    // Ignore legacy storage cleanup failures.
  }
}

function readStoredApiToken(storage: Storage | null): string {
  if (!storage) return ''
  try {
    return (
      storage.getItem(API_TOKEN_STORAGE_KEY) ??
      storage.getItem(ADMIN_API_TOKEN_STORAGE_KEY) ??
      ''
    ).trim()
  } catch {
    return ''
  }
}

export function getApiToken(): string {
  const sessionStorage = getBrowserStorage('session')
  const sessionToken = readStoredApiToken(sessionStorage)
  if (sessionToken) return sessionToken

  const legacyToken = readStoredApiToken(getBrowserStorage('local'))
  if (!legacyToken || !sessionStorage) {
    cleanupLegacyApiTokenStorage()
    return legacyToken
  }

  try {
    sessionStorage.setItem(API_TOKEN_STORAGE_KEY, legacyToken)
    sessionStorage.setItem(ADMIN_API_TOKEN_STORAGE_KEY, legacyToken)
  } catch {
    return legacyToken
  }
  cleanupLegacyApiTokenStorage()
  return legacyToken
}

export function getAdminApiToken(): string {
  return getApiToken()
}

export function hasApiToken(): boolean {
  return getApiToken().length > 0
}

export function hasAdminApiToken(): boolean {
  return hasApiToken()
}

export function saveApiToken(token: string): void {
  const storage = getBrowserStorage('session')
  const normalized = token.trim()
  try {
    if (normalized && storage) {
      storage.setItem(API_TOKEN_STORAGE_KEY, normalized)
      storage.setItem(ADMIN_API_TOKEN_STORAGE_KEY, normalized)
    } else if (storage) {
      storage.removeItem(API_TOKEN_STORAGE_KEY)
      storage.removeItem(ADMIN_API_TOKEN_STORAGE_KEY)
    }
  } catch {
    // Ignore storage failures and let requests fall back to local-mode access.
  }
  cleanupLegacyApiTokenStorage()
}

export function saveAdminApiToken(token: string): void {
  saveApiToken(token)
}

function withApiTokenHeaders(headers?: HeadersInit): Headers {
  const next = new Headers(headers)
  const token = getApiToken()
  if (token && !next.has('Authorization')) {
    next.set('Authorization', `Bearer ${token}`)
  }
  if (token && !next.has('X-API-Token')) {
    next.set('X-API-Token', token)
  }
  return next
}

export async function readErrorDetail(res: Response, fallback: string): Promise<string> {
  try {
    const payload = await res.json() as { detail?: string }
    if (typeof payload.detail === 'string' && payload.detail.trim()) {
      return payload.detail
    }
  } catch {
    // Ignore JSON parsing failures and use the fallback message.
  }
  return fallback
}

function normalizeRequestPath(input: RequestInfo | URL): string {
  const raw =
    typeof input === 'string'
      ? input
      : input instanceof URL
        ? input.toString()
        : input.url

  try {
    const base = typeof window !== 'undefined' ? window.location.origin : 'http://localhost'
    const url = new URL(raw, base)
    return `${url.pathname}${url.search}`
  } catch {
    return raw
  }
}

function normalizeApiPathPrefix(base: string): string {
  try {
    const origin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost'
    const url = new URL(base, origin)
    return url.pathname.replace(/\/+$/, '') || '/api'
  } catch {
    return base.startsWith('/') ? base.replace(/\/+$/, '') || '/api' : '/api'
  }
}

const API_PATH_PREFIX = normalizeApiPathPrefix(BASE)

function requestNeedsApiToken(path: string): boolean {
  const protectedPrefixes = [
    '/auth/',
    '/security/',
    '/access',
    '/identity',
    '/sessions',
    '/tasks',
    '/assistant-presets',
    '/workspaces',
    '/decks',
    '/artifacts',
    '/operations/observability',
    '/operations/runtime',
    '/operations/traces',
    '/connectors',
    '/config',
    '/agents',
    '/delivery-templates',
    '/documents/upload',
    '/documents/stats',
    '/prompts',
    '/reports',
    '/research',
    '/knowledge-bases',
    '/knowledge-base/health',
    '/knowledge-base/chunks',
    '/knowledge-base/test-retrieval',
    '/knowledge-base/by-path',
  ]

  return (
    protectedPrefixes.some((prefix) => path.startsWith(`${API_PATH_PREFIX}${prefix}`)) ||
    path === `${API_PATH_PREFIX}/knowledge-base`
  )
}

const nativeFetch: typeof globalThis.fetch = globalThis.fetch.bind(globalThis)

export const fetchWithApiToken: typeof globalThis.fetch = (input, init) => {
  const path = normalizeRequestPath(input)
  if (!requestNeedsApiToken(path)) {
    return nativeFetch(input, init)
  }
  return nativeFetch(input, {
    ...init,
    headers: withApiTokenHeaders(init?.headers),
  })
}

export async function authFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetchWithApiToken(`${BASE}${path}`, {
    ...init,
    headers: withApiTokenHeaders(init?.headers),
  })
}
