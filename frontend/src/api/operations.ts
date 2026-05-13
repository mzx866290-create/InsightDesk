import {
  authFetch,
  fetchWithApiToken,
  readErrorDetail,
} from './auth'
import {
  normalizeSecurityStatusPayload,
  normalizeSecurityAuditSummaryCategory,
  normalizeSecurityAuditSummaryPayload,
} from './normalizers'
import type {
  AuthWhoAmI,
  SsoConfig,
  SaveSsoConfigPayload,
  SsoLoginResponse,
  SecurityStatusResponse,
  SecurityAuditSummaryCategory,
  SecurityAuditSummary,
  SecurityAuditEventsResponse,
  SecurityAuditEventFilters,
  SecurityAuditCleanupPayload,
  SecurityAuditCleanupResponse,
  TraceFilters,
  TraceEvent,
  TraceEventsResponse,
  ClearTracesResponse,
  IngestTraceEventsResponse,
  ObservabilitySnapshotResponse,
  ResourceGrantRole,
  ResourceGrant,
  ResourceGrantListQuery,
  ResourceGrantListResponse,
  ResourceGrantMutationPayload,
  IdentityOrganization,
  IdentityUser,
  IdentityMembership,
  IdentityCatalog,
  UpsertOrganizationPayload,
  UpsertUserPayload,
  SetMembershipPayload,
} from './types'

const fetch: typeof globalThis.fetch = fetchWithApiToken
export async function getAuthWhoAmI(): Promise<AuthWhoAmI> {
  const res = await authFetch('/auth/whoami')
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to load auth profile'))
  return res.json()
}

export async function getAuthSsoConfig(): Promise<SsoConfig> {
  const res = await authFetch('/auth/sso/config')
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to load SSO config'))
  return res.json()
}

export async function saveAuthSsoConfig(payload: SaveSsoConfigPayload): Promise<SsoConfig> {
  const res = await authFetch('/auth/sso/config', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to save SSO config'))
  return res.json()
}

export async function startAuthSsoLogin(): Promise<SsoLoginResponse> {
  const res = await authFetch('/auth/sso/login?response_mode=fragment')
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to start SSO login'))
  return res.json()
}

export async function getSecurityStatus(): Promise<SecurityStatusResponse> {
  const res = await authFetch('/security/status')
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to load security status'))
  const data = await res.json() as Partial<SecurityStatusResponse>
  return normalizeSecurityStatusPayload(data)
}

export async function getSecurityAuditSummary(
  category: SecurityAuditSummaryCategory = 'all',
  limit = 200,
): Promise<SecurityAuditSummary> {
  const numericLimit = Number.isFinite(limit) ? limit : 200
  const safeLimit = Math.max(1, Math.min(500, Math.floor(numericLimit)))
  const normalizedCategory = normalizeSecurityAuditSummaryCategory(category)
  const params = new URLSearchParams({ limit: String(safeLimit) })
  if (normalizedCategory) params.set('category', normalizedCategory)

  const res = await authFetch(`/security/audit-summary?${params.toString()}`)
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to load security audit summary'))
  const data = await res.json() as Partial<SecurityAuditSummary>
  return normalizeSecurityAuditSummaryPayload(data)
}

export async function getSecurityAuditEvents(
  limit = 100,
  filters: SecurityAuditEventFilters = {},
): Promise<SecurityAuditEventsResponse> {
  const numericLimit = Number.isFinite(limit) ? limit : 100
  const safeLimit = Math.max(1, Math.min(500, Math.floor(numericLimit)))
  const params = new URLSearchParams({ limit: String(safeLimit) })
  if (filters.action?.trim()) params.set('action', filters.action.trim())
  if (filters.result?.trim()) params.set('result', filters.result.trim())
  if (filters.category?.trim()) params.set('category', filters.category.trim())
  if (filters.user_id?.trim()) params.set('user_id', filters.user_id.trim())
  if (typeof filters.since === 'number' && Number.isFinite(filters.since)) {
    params.set('since', String(Math.floor(filters.since)))
  }
  if (typeof filters.until === 'number' && Number.isFinite(filters.until)) {
    params.set('until', String(Math.floor(filters.until)))
  }

  const res = await authFetch(`/security/audit-events?${params.toString()}`)
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to load security audit events'))
  return res.json()
}

export async function cleanupSecurityAuditEvents(
  payload: SecurityAuditCleanupPayload,
): Promise<SecurityAuditCleanupResponse> {
  const keepLatest = Number.isFinite(payload.keep_latest)
    ? Math.max(0, Math.floor(payload.keep_latest))
    : 0
  const params = new URLSearchParams({ keep_latest: String(keepLatest) })
  if (payload.dry_run === true) params.set('dry_run', 'true')

  const res = await authFetch(`/security/audit-events/cleanup?${params.toString()}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ keep_latest: keepLatest, dry_run: payload.dry_run === true }),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to cleanup security audit events'))
  return res.json()
}

export async function getTraceEvents(limit = 100, filters: TraceFilters = {}): Promise<TraceEventsResponse> {
  const safeLimit = Math.max(1, Math.min(500, Math.floor(limit)))
  const params = new URLSearchParams({ limit: String(safeLimit) })
  if (filters.event) params.set('event', filters.event)
  if (filters.name?.trim()) params.set('name', filters.name.trim())
  if (filters.trace_id?.trim()) params.set('trace_id', filters.trace_id.trim())
  if (filters.span_id?.trim()) params.set('span_id', filters.span_id.trim())
  const res = await authFetch(`/operations/traces?${params.toString()}`)
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to load trace events'))
  return res.json()
}

export async function ingestTraceEvents(payload: {
  source?: string
  process_id?: string
  events: TraceEvent[]
}): Promise<IngestTraceEventsResponse> {
  const res = await authFetch('/operations/traces/ingest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to ingest trace events'))
  return res.json()
}

export async function getObservabilitySnapshot(traceLimit = 50): Promise<ObservabilitySnapshotResponse> {
  const safeLimit = Math.max(1, Math.min(200, Math.floor(traceLimit)))
  const res = await authFetch(`/operations/observability?trace_limit=${encodeURIComponent(String(safeLimit))}`)
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to load observability snapshot'))
  return res.json()
}

export async function clearTraceEvents(): Promise<ClearTracesResponse> {
  const res = await authFetch('/operations/traces', { method: 'DELETE' })
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to clear trace events'))
  return res.json()
}

export async function getResourceGrants(
  query: ResourceGrantListQuery = {},
): Promise<ResourceGrantListResponse> {
  const params = new URLSearchParams()
  const textFields: Array<keyof Pick<ResourceGrantListQuery, 'resource_type' | 'resource_id' | 'org_id' | 'user_id' | 'role' | 'subject_type'>> = [
    'resource_type',
    'resource_id',
    'org_id',
    'user_id',
    'role',
    'subject_type',
  ]
  for (const field of textFields) {
    const value = query[field]
    if (typeof value === 'string' && value.trim()) params.set(field, value.trim())
  }
  if (typeof query.limit === 'number' && Number.isFinite(query.limit)) {
    params.set('limit', String(Math.max(1, Math.min(200, Math.floor(query.limit)))))
  }
  if (typeof query.offset === 'number' && Number.isFinite(query.offset)) {
    params.set('offset', String(Math.max(0, Math.floor(query.offset))))
  }

  const suffix = params.toString()
  const res = await authFetch(`/access/resource-grants${suffix ? `?${suffix}` : ''}`)
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to load resource grants'))
  return res.json()
}

export async function upsertResourceGrant(
  payload: ResourceGrantMutationPayload & { role: ResourceGrantRole },
): Promise<ResourceGrant> {
  const res = await authFetch('/access/resource-grants', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to save resource grant'))
  return res.json()
}

export async function deleteResourceGrant(payload: ResourceGrantMutationPayload): Promise<void> {
  const res = await authFetch('/access/resource-grants', {
    method: 'DELETE',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to delete resource grant'))
}

export async function getIdentityCatalog(limit = 100): Promise<IdentityCatalog> {
  const safeLimit = Math.max(1, Math.min(500, Math.floor(limit)))
  const res = await authFetch(`/identity?limit=${encodeURIComponent(String(safeLimit))}`)
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to load identity catalog'))
  return res.json()
}

export async function upsertIdentityOrganization(
  payload: UpsertOrganizationPayload,
): Promise<IdentityOrganization> {
  const res = await authFetch('/identity/orgs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to save organization'))
  return res.json()
}

export async function upsertIdentityUser(payload: UpsertUserPayload): Promise<IdentityUser> {
  const res = await authFetch('/identity/users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to save user'))
  return res.json()
}

export async function setIdentityMembership(
  payload: SetMembershipPayload,
): Promise<IdentityMembership> {
  const res = await authFetch('/identity/memberships', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to save membership'))
  return res.json()
}
