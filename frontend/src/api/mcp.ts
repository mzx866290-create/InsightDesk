import {
  BASE,
  authFetch,
  fetchWithApiToken,
} from './auth'
import {
  readString,
  readNumber,
  readStringArray,
  normalizeMcpConfigPayload,
  normalizeMcpApprovalsPayload,
  normalizeIntegratorConnectorsResponse,
  normalizeIntegratorConnectorTestResult,
  normalizeIntegratorAuditEventsResponse,
  normalizeIntegratorCredentialsRotationResponse,
  normalizeIntegratorConnectorProbeResponse,
  normalizeIntegratorSchedulesResponse,
  readRecord,
  normalizeMcpRuntimeHealthSummary,
  normalizeMcpRuntimeHealthHistoryItem,
} from './normalizers'
import type {
  McpConnector,
  McpConnectorApprovalsResponse,
  McpConfigResponse,
  InstallMcpConnectorPayload,
  InstallMcpConnectorResponse,
  SaveMcpConfigPayload,
  McpRuntimeHealthHistoryResponse,
  McpRuntimeHealthResponse,
  IntegratorConnector,
  IntegratorConnectorsResponse,
  IntegratorConnectorTestResult,
  IntegratorConnectorCredentialsRotationResponse,
  IntegratorConnectorProbeMode,
  IntegratorConnectorProbeOptions,
  IntegratorConnectorProbeResponse,
  IntegratorAuditEventsResponse,
  IntegratorSchedule,
  IntegratorSchedulesResponse,
  IntegratorScheduleTriggerResponse,
  IntegratorScheduleTickResponse,
} from './types'

const fetch: typeof globalThis.fetch = fetchWithApiToken

function formatApiErrorDetail(detail: unknown, fallback: string): string {
  if (typeof detail === 'string' && detail.trim()) return detail
  if (!detail || typeof detail !== 'object') return fallback

  const payload = detail as Record<string, unknown>
  const message = typeof payload.message === 'string' && payload.message.trim()
    ? payload.message.trim()
    : fallback
  const field = typeof payload.field === 'string' && payload.field.trim()
    ? payload.field.trim()
    : ''
  const code = typeof payload.code === 'string' && payload.code.trim()
    ? payload.code.trim()
    : ''
  const prefix = field ? `${field}: ` : ''
  const suffix = code ? ` (${code})` : ''
  return `${prefix}${message}${suffix}`
}

export async function getMcpConnectors(): Promise<{
  connectors: McpConnector[]
  default_enabled: string[]
}> {
  const res = await fetch(`${BASE}/connectors/mcp`)
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    connectors?: McpConnector[]
    default_enabled?: string[]
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return {
    connectors: Array.isArray(data.connectors) ? data.connectors : [],
    default_enabled: Array.isArray(data.default_enabled)
      ? data.default_enabled.filter(
          (item): item is string => typeof item === 'string' && item.trim().length > 0,
        )
      : [],
  }
}

export async function getMcpConfig(): Promise<McpConfigResponse> {
  const res = await authFetch('/connectors/mcp/config')
  const data = await res.json().catch(() => ({ detail: res.statusText })) as Partial<McpConfigResponse> & {
    detail?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return normalizeMcpConfigPayload(data)
}

export async function saveMcpConfig(payload: SaveMcpConfigPayload): Promise<McpConfigResponse> {
  const res = await authFetch('/connectors/mcp/config', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as Partial<McpConfigResponse> & {
    detail?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return normalizeMcpConfigPayload(data)
}

export async function installMcpConnectorManifest(
  payload: InstallMcpConnectorPayload,
): Promise<InstallMcpConnectorResponse> {
  const res = await authFetch('/connectors/mcp/marketplace/install', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as Partial<InstallMcpConnectorResponse> & {
    detail?: unknown
  }
  if (!res.ok) {
    throw new Error(formatApiErrorDetail(data.detail, res.statusText))
  }

  const installed = readRecord(data.installed)
  const installedConnector = readRecord(installed.connector)
  const connector = Object.keys(installedConnector).length > 0
    ? {
        ...installedConnector,
        name: readString(installedConnector.name),
        label: readString(installedConnector.label),
        description: readString(installedConnector.description),
        category: readString(installedConnector.category),
        builtin: installedConnector.builtin === true,
        transport: readString(installedConnector.transport),
        source: readString(installedConnector.source),
      } as McpConnector
    : undefined
  return {
    ...normalizeMcpConfigPayload(data),
    ...(readString(installed.name)
      ? {
          installed: {
            name: readString(installed.name),
            connector,
            executed_install_command: installed.executed_install_command === true,
          },
        }
      : {}),
  }
}

export async function getMcpConnectorApprovals(): Promise<McpConnectorApprovalsResponse> {
  const res = await authFetch('/connectors/mcp/approvals')
  const data = await res.json().catch(() => ({ detail: res.statusText })) as Partial<McpConnectorApprovalsResponse> & {
    detail?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return normalizeMcpApprovalsPayload(data)
}

export async function approveMcpConnector(name: string): Promise<McpConnectorApprovalsResponse> {
  const res = await authFetch('/connectors/mcp/approvals', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as Partial<McpConnectorApprovalsResponse> & {
    detail?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return normalizeMcpApprovalsPayload(data)
}

export async function revokeMcpConnectorApproval(name: string): Promise<McpConnectorApprovalsResponse> {
  const res = await authFetch(`/connectors/mcp/approvals/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as Partial<McpConnectorApprovalsResponse> & {
    detail?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return normalizeMcpApprovalsPayload(data)
}

export async function getIntegratorConnectors(): Promise<IntegratorConnectorsResponse> {
  const res = await authFetch('/integrations/connectors')
  const data = await res.json().catch(() => ({ detail: res.statusText })) as Partial<IntegratorConnectorsResponse> & {
    detail?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return normalizeIntegratorConnectorsResponse(data)
}

export async function saveIntegratorConnectors(
  connectors: IntegratorConnector[],
): Promise<IntegratorConnectorsResponse> {
  const res = await authFetch('/integrations/connectors', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ connectors }),
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as Partial<IntegratorConnectorsResponse> & {
    detail?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return normalizeIntegratorConnectorsResponse(data)
}

export async function testIntegratorConnector(
  connector: IntegratorConnector,
): Promise<IntegratorConnectorTestResult> {
  const res = await authFetch('/integrations/connectors/test', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ connector }),
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as Partial<IntegratorConnectorTestResult> & {
    detail?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return normalizeIntegratorConnectorTestResult(data)
}

export async function rotateIntegratorConnectorCredentials(
  connectorId: string,
  payload: { settings?: Record<string, unknown>; credentials?: Record<string, unknown> },
): Promise<IntegratorConnectorCredentialsRotationResponse> {
  const res = await authFetch(`/integrations/connectors/${encodeURIComponent(connectorId)}/credentials/rotate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as Partial<IntegratorConnectorCredentialsRotationResponse> & {
    detail?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return normalizeIntegratorCredentialsRotationResponse(data)
}

export async function probeIntegratorConnector(
  connectorId: string,
  options: IntegratorConnectorProbeOptions = {},
): Promise<IntegratorConnectorProbeResponse> {
  const mode: IntegratorConnectorProbeMode = options.mode ?? (options.external ? 'external' : 'static')
  const body = {
    dry_run: mode === 'static',
    mode,
    ...(mode === 'external' && typeof options.timeout_seconds === 'number'
      ? { timeout_seconds: options.timeout_seconds }
      : {}),
  }
  const res = await authFetch(`/integrations/connectors/${encodeURIComponent(connectorId)}/probe`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as Partial<IntegratorConnectorProbeResponse> & {
    detail?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return normalizeIntegratorConnectorProbeResponse(data)
}

export async function getIntegratorAuditEvents(limit = 20): Promise<IntegratorAuditEventsResponse> {
  const safeLimit = Math.max(1, Math.min(100, Math.floor(limit)))
  const res = await authFetch(`/integrations/audit?limit=${encodeURIComponent(String(safeLimit))}`)
  const data = await res.json().catch(() => ({ detail: res.statusText })) as Partial<IntegratorAuditEventsResponse> & {
    detail?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return normalizeIntegratorAuditEventsResponse(data)
}

export async function getIntegratorSchedules(): Promise<IntegratorSchedulesResponse> {
  const res = await authFetch('/integrations/schedules')
  const data = await res.json().catch(() => ({ detail: res.statusText })) as Partial<IntegratorSchedulesResponse> & {
    detail?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return normalizeIntegratorSchedulesResponse(data)
}

export async function saveIntegratorSchedules(
  schedules: IntegratorSchedule[],
): Promise<IntegratorSchedulesResponse> {
  const res = await authFetch('/integrations/schedules', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ schedules }),
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as Partial<IntegratorSchedulesResponse> & {
    detail?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return normalizeIntegratorSchedulesResponse(data)
}

export async function triggerIntegratorSchedule(
  scheduleId: string,
  dryRun = false,
): Promise<IntegratorScheduleTriggerResponse> {
  const res = await authFetch(`/integrations/schedules/${encodeURIComponent(scheduleId)}/trigger`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dry_run: dryRun }),
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as Partial<IntegratorScheduleTriggerResponse> & {
    detail?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return {
    ok: data.ok === true,
    schedule_id: readString(data.schedule_id) || scheduleId,
    status: readString(data.status) || 'triggered',
    triggered_at: readNumber(data.triggered_at),
  }
}

export async function triggerIntegratorScheduleTick(
  dryRun = true,
): Promise<IntegratorScheduleTickResponse> {
  const res = await authFetch('/integrations/schedules/tick', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dry_run: dryRun }),
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as Partial<IntegratorScheduleTickResponse> & {
    detail?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  const skipped = readRecord(data.skipped)
  return {
    dry_run: data.dry_run !== false,
    executed: data.executed === true,
    checked: readNumber(data.checked),
    due_count: readNumber(data.due_count),
    skipped: {
      disabled: readNumber(skipped.disabled),
      not_due: readNumber(skipped.not_due),
    },
    now: readNumber(data.now),
  }
}

export async function getMcpRuntimeHealth(): Promise<McpRuntimeHealthResponse> {
  const res = await authFetch('/connectors/mcp/runtime-health')
  const data = await res.json().catch(() => ({ detail: res.statusText })) as Partial<McpRuntimeHealthResponse> & {
    detail?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return {
    status: readString(data.status) || 'unknown',
    servers: Array.isArray(data.servers)
      ? data.servers.map((server) => ({
          name: readString(server.name),
          status: readString(server.status) || 'unknown',
          healthy: server.healthy === true,
          tool_count: readNumber(server.tool_count),
          tools: readStringArray(server.tools),
          duration_ms: readNumber(server.duration_ms),
          error: typeof server.error === 'string' && server.error.trim() ? server.error : null,
        }))
      : [],
    summary: normalizeMcpRuntimeHealthSummary(data.summary),
    history: Array.isArray(data.history)
      ? data.history.map(normalizeMcpRuntimeHealthHistoryItem)
      : [],
    history_limit: readNumber(data.history_limit),
  }
}

export async function getMcpRuntimeHealthHistory(limit = 10): Promise<McpRuntimeHealthHistoryResponse> {
  const safeLimit = Math.max(1, Math.min(100, Math.floor(limit)))
  const res = await authFetch(`/connectors/mcp/runtime-health/history?limit=${encodeURIComponent(String(safeLimit))}`)
  const data = await res.json().catch(() => ({ detail: res.statusText })) as Partial<McpRuntimeHealthHistoryResponse> & {
    detail?: string
    history_limit?: number
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return {
    history: Array.isArray(data.history)
      ? data.history.map(normalizeMcpRuntimeHealthHistoryItem)
      : [],
    limit: readNumber(data.limit ?? data.history_limit) || safeLimit,
  }
}
