import type { WorkflowNode } from '../stores/workflowStore'

const BASE = '/api'
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

async function authFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${BASE}${path}`, {
    ...init,
    headers: withApiTokenHeaders(init?.headers),
  })
}

async function readErrorDetail(res: Response, fallback: string): Promise<string> {
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

function requestNeedsApiToken(path: string): boolean {
  return (
    path.startsWith(`${BASE}/auth/`) ||
    path.startsWith(`${BASE}/security/`) ||
    path.startsWith(`${BASE}/access`) ||
    path.startsWith(`${BASE}/identity`) ||
    path.startsWith(`${BASE}/sessions`) ||
    path.startsWith(`${BASE}/tasks`) ||
    path.startsWith(`${BASE}/workspaces`) ||
    path.startsWith(`${BASE}/decks`) ||
    path.startsWith(`${BASE}/artifacts`) ||
    path.startsWith(`${BASE}/operations/observability`) ||
    path.startsWith(`${BASE}/operations/runtime`) ||
    path.startsWith(`${BASE}/operations/traces`) ||
    path.startsWith(`${BASE}/connectors`) ||
    path.startsWith(`${BASE}/config`) ||
    path.startsWith(`${BASE}/agents/reset`) ||
    path.startsWith(`${BASE}/documents/upload`) ||
    path.startsWith(`${BASE}/documents/stats`) ||
    path.startsWith(`${BASE}/prompts`) ||
    path.startsWith(`${BASE}/research`) ||
    path.startsWith(`${BASE}/knowledge-bases`) ||
    path.startsWith(`${BASE}/knowledge-base/health`) ||
    path.startsWith(`${BASE}/knowledge-base/chunks`) ||
    path.startsWith(`${BASE}/knowledge-base/test-retrieval`) ||
    path.startsWith(`${BASE}/knowledge-base/by-path`) ||
    path === `${BASE}/knowledge-base`
  )
}

const nativeFetch: typeof globalThis.fetch = globalThis.fetch.bind(globalThis)
const fetch: typeof globalThis.fetch = (input, init) => {
  const path = normalizeRequestPath(input)
  if (!requestNeedsApiToken(path)) {
    return nativeFetch(input, init)
  }
  return nativeFetch(input, {
    ...init,
    headers: withApiTokenHeaders(init?.headers),
  })
}

export interface Session {
  session_id: string
  title: string
  created_at: number
  updated_at: number
  message_count: number
  is_archived: boolean
  is_favorite: boolean
  is_pinned: boolean
  session_order: number
  tags: string[]
  workspace_id: string
  search_preview?: string
  search_source?: 'title' | 'message'
}

export interface Workspace {
  workspace_id: string
  name: string
  description: string
  color: 'slate' | 'blue' | 'green' | 'amber' | 'rose'
  preset?: WorkspacePreset
  is_active: boolean
  created_at: number
  updated_at: number
  session_count: number
}

export interface WorkspaceToolConfig {
  web_search_enabled: boolean
  knowledge_base_enabled: boolean
  mcp_servers_enabled: string[]
}

export interface WorkspaceOutputPreset {
  deck_theme: 'default' | 'midnight' | 'sunrise'
  target_slide_count: number
}

export interface WorkspacePreset {
  default_panels: ModelConfig[]
  tool_config: WorkspaceToolConfig
  output_preset: WorkspaceOutputPreset
}

export interface McpConnector {
  name: string
  label: string
  description: string
  category: string
  builtin: boolean
  transport: string
  source: string
  capability_scopes?: string[]
  risk_level?: 'low' | 'medium' | 'high' | 'critical' | string
  requires_approval?: boolean
  enabled?: boolean
  configured?: boolean
  healthy?: boolean
  status?: string
  status_reasons?: string[]
  policy?: McpConnectorPolicy
}

export interface McpConnectorPolicy {
  allowed: boolean
  requires_approval: boolean
  missing_scopes: string[]
  reasons: string[]
  connector_approved: boolean
  risk_level: string
  capability_scopes: string[]
}

export interface McpConnectorApprovalDetail {
  name: string
  changed?: boolean
  removed?: boolean
  runtime_approved?: boolean
  effective_approved?: boolean
}

export interface McpConnectorApprovalsResponse {
  approved_connectors: string[]
  env_connectors: string[]
  runtime_connectors: string[]
  persisted_connectors: string[]
  sources: Record<string, string[]>
  persistence: {
    enabled: boolean
    config_key: string
  }
  total: number
  connector?: McpConnectorApprovalDetail
}

export interface McpConfigPersistence {
  enabled: boolean
  config_key: string
}

export interface McpMarketplaceSummary {
  total: number
  builtin: number
  custom: number
  enabled: number
  healthy: number
  requires_approval: number
  categories: number
}

export interface McpMarketplaceCategory {
  id: string
  label: string
  total: number
  enabled: number
  healthy: number
  requires_approval: number
  connectors: string[]
}

export interface McpMarketplace {
  summary: McpMarketplaceSummary
  categories: McpMarketplaceCategory[]
}

export interface McpConfigResponse {
  connectors: McpConnector[]
  config: Record<string, unknown>
  servers: Record<string, Record<string, unknown>>
  default_enabled: string[]
  persistence: McpConfigPersistence
  marketplace?: McpMarketplace
  sensitive_fields_redacted: boolean
  source?: string
  path?: string
  total?: number
}

export type SaveMcpConfigPayload = Record<string, unknown> & {
  connectors?: McpConnector[]
  config?: Record<string, unknown>
  default_enabled?: string[]
}

export interface McpRuntimeServerHealth {
  name: string
  status: string
  healthy: boolean
  tool_count: number
  tools: string[]
  duration_ms: number
  error: string | null
}

export interface McpRuntimeHealthSummary {
  total: number
  healthy: number
  unhealthy: number
  tool_count: number
  status_counts: Record<string, number>
  alert_count: number
  unhealthy_connectors: string[]
  slow_connectors: string[]
}

export interface McpRuntimeHealthHistoryServer {
  name: string
  status: string
  healthy: boolean
  tool_count: number
  duration_ms: number
  error: string | null
}

export interface McpRuntimeHealthHistoryItem {
  timestamp: number
  status: string
  summary: McpRuntimeHealthSummary
  servers: McpRuntimeHealthHistoryServer[]
}

export interface McpRuntimeHealthHistoryResponse {
  history: McpRuntimeHealthHistoryItem[]
  limit: number
}

export interface McpRuntimeHealthResponse {
  status: string
  servers: McpRuntimeServerHealth[]
  summary: McpRuntimeHealthSummary
  history: McpRuntimeHealthHistoryItem[]
  history_limit: number
}

export type IntegratorConnectorType = 'webhook' | 'email' | 'feishu' | 'dingtalk' | string

export interface IntegratorConnector {
  id?: string
  type: IntegratorConnectorType
  name?: string
  description?: string
  enabled: boolean
  approved: boolean
  settings: Record<string, unknown>
}

export interface IntegratorConnectorsResponse {
  connectors: IntegratorConnector[]
  total: number
  supported_types: string[]
  persistence: {
    enabled: boolean
    config_key: string
    sensitive_fields_redacted: boolean
  }
}

export interface IntegratorConnectorTestCheck {
  name: string
  ok: boolean
  severity: string
  message: string
}

export interface IntegratorConnectorTestResult {
  ok: boolean
  status: string
  dry_run: boolean
  executed: boolean
  connector: IntegratorConnector
  checks: IntegratorConnectorTestCheck[]
  summary: {
    check_count: number
    failed_count: number
    blocking_failure_count: number
    warning_count: number
  }
}

export interface IntegratorConnectorCredentialsRotationResponse {
  ok: boolean
  status: string
  connector: IntegratorConnector
  rotated_fields: string[]
  preserved_fields: string[]
  summary: {
    rotated_count: number
    preserved_count: number
  }
}

export type IntegratorConnectorProbeMode = 'static' | 'external'

export interface IntegratorConnectorProbeOptions {
  mode?: IntegratorConnectorProbeMode
  external?: boolean
  timeout_seconds?: number
}

export interface IntegratorConnectorProbeDetails {
  mode: string
  outbound_request_sent: boolean
  timeout_seconds?: number
  endpoint?: Record<string, unknown>
  response?: Record<string, unknown>
}

export interface IntegratorConnectorProbeResponse {
  ok: boolean
  status: string
  dry_run: boolean
  executed: boolean
  connector: IntegratorConnector
  checks: IntegratorConnectorTestCheck[]
  probe: IntegratorConnectorProbeDetails
  summary: {
    check_count: number
    failed_count: number
    blocking_failure_count: number
    warning_count: number
    probe_mode?: string
  }
}

export interface IntegratorAuditEvent {
  timestamp: number
  action: string
  result: string
  connector_id: string
  connector_type: string
  actor: string
  request_id: string
  details: Record<string, unknown>
}

export interface IntegratorAuditEventsResponse {
  events: IntegratorAuditEvent[]
  total: number
  limit: number
}

export interface IntegratorSchedule {
  schedule_id?: string
  name: string
  connector_id: string
  cron: string
  timezone?: string
  interval_minutes: number
  enabled: boolean
  settings: Record<string, unknown>
  last_run_at?: number | null
  next_run_at?: number | null
}

export interface IntegratorSchedulesResponse {
  schedules: IntegratorSchedule[]
  total: number
  persistence?: {
    enabled: boolean
    config_key: string
    sensitive_fields_redacted: boolean
  }
  scheduler?: {
    mode: string
    automatic_dispatch: boolean
    manual_trigger_supported: boolean
  }
}

export interface IntegratorScheduleTriggerResponse {
  ok: boolean
  schedule_id: string
  status: string
  triggered_at: number
}

export interface IntegratorScheduleTickResponse {
  dry_run: boolean
  executed: boolean
  checked: number
  due_count: number
  skipped: {
    disabled: number
    not_due: number
  }
  now: number
}

export type SessionMemoryKind = 'summary' | 'fact' | 'decision' | 'todo'
export type MessageFeedbackValue = -1 | 0 | 1
export type RetrievalFeedbackValue = -1 | 0 | 1

export interface SessionMemory {
  id: string
  session_id: string
  kind: SessionMemoryKind
  content: string
  meta?: Record<string, unknown>
  created_at: number
  updated_at: number
}

export interface AuthWhoAmI {
  user_id: string
  role: 'viewer' | 'editor' | 'admin' | string
  auth_mode: string
  auth_source: string
  is_local: boolean
  capabilities: string[]
}

export interface SsoConfig {
  enabled: boolean
  provider: string
  issuer_url: string
  authorization_endpoint: string
  token_endpoint: string
  jwks_url: string
  authorization_endpoint_configured: boolean
  token_endpoint_configured: boolean
  jwks_url_configured: boolean
  client_id: string
  client_id_configured: boolean
  client_secret_configured: boolean
  allowed_domains: string[]
  scopes: string[]
  default_role: string
  session_ttl_seconds: number
  callback_path: string
  ready: boolean
  mode: string
  claim_mapping: Record<string, string>
}

export interface SaveSsoConfigPayload {
  provider?: string
  issuer_url?: string
  authorization_endpoint?: string
  token_endpoint?: string
  jwks_url?: string
  client_id?: string
  client_secret?: string
  clear_client_secret?: boolean
  allowed_domains?: string
  scopes?: string
  default_role?: string
  session_ttl_seconds?: number
}

export interface SsoLoginResponse {
  authorization_url: string
  state: string
  nonce: string
  code_challenge_method: string
  redirect_uri: string
  scopes: string[]
}

export type SecurityAuditSummaryCategory = 'all' | 'access' | 'identity' | 'auth' | 'audit'
export type SecurityAuditSummaryApiCategory = Exclude<SecurityAuditSummaryCategory, 'all'>

export interface SecurityAuditSummary {
  category: SecurityAuditSummaryApiCategory | ''
  categories: SecurityAuditSummaryApiCategory[]
  total: number
  recent_count: number
  window_limit: number
  action_counts: Record<string, number>
  result_counts: Record<string, number>
  category_counts: Record<string, number>
  unknown_action_count: number
}

export interface SecurityAuditEvent {
  timestamp: number
  request_id: string
  action: string
  result: string
  ip: string
  is_local: boolean
  auth_mode: string
  auth_source: string
  user_id: string
  user_role: string
  details: string | Record<string, unknown>
}

export interface SecurityAuditEventsResponse {
  events: SecurityAuditEvent[]
  total: number
  limit: number
}

export interface SecurityAuditEventFilters {
  action?: string
  result?: string
  category?: string
  user_id?: string
  since?: number
  until?: number
}

export interface SecurityAuditCleanupPayload {
  keep_latest: number
  dry_run?: boolean
}

export interface SecurityAuditCleanupResponse {
  keep_latest: number
  deleted_count?: number
  would_delete_count?: number
  remaining_count?: number
  memory_deleted_count?: number
  memory_remaining_count?: number
  history_limit?: number
  includes_cleanup_event?: boolean
  dry_run?: boolean
}

export type TraceEventKind = 'start' | 'end' | 'error'

export interface TraceFilters {
  event?: TraceEventKind | ''
  name?: string
  trace_id?: string
  span_id?: string
}

export interface TraceEvent {
  event: TraceEventKind
  name: string
  trace_id: string
  span_id: string
  parent_span_id: string | null
  timestamp: number
  duration_ms: number | null
  attributes: Record<string, unknown>
  error_type: string | null
  error_message: string | null
  process_id?: string | null
  source?: string | null
}

export interface TraceSummary {
  returned: number
  limit: number
  error_events: number
  filters?: TraceFilters
  source_nodes?: Record<string, number>
  process_nodes?: Record<string, number>
}

export interface TraceDashboardCard {
  id: string
  title: string
  value: number | string
  unit?: string
  severity?: 'ok' | 'warning' | 'error' | string
}

export interface TracePanelTemplate {
  id: string
  title: string
  kind: string
  source: string
  fields: string[]
}

export interface TraceExportPreview {
  service_name: string
  span_count: number
  log_record_count: number
  source_nodes: Record<string, number>
  process_nodes: Record<string, number>
  avg_duration_ms: number
  sample_spans: Array<Record<string, unknown>>
}

export interface TraceExportPayload {
  format: string
  resource_spans: Array<Record<string, unknown>>
  resource_logs: Array<Record<string, unknown>>
  summary: {
    service_name: string
    event_count: number
    span_count: number
    log_record_count: number
    source_nodes: Record<string, number>
    process_nodes: Record<string, number>
  }
}

export interface TraceEventsResponse {
  events: TraceEvent[]
  summary: TraceSummary
  export?: TraceExportPayload
  export_preview?: TraceExportPreview
  dashboard_cards?: TraceDashboardCard[]
  panel_templates?: TracePanelTemplate[]
}

export interface ClearTracesResponse {
  ok: boolean
  cleared: boolean
}

export interface IngestTraceEventsResponse {
  ok: boolean
  accepted: number
  rejected: number
  source: string
  process_id: string
}

export interface ObservabilitySnapshotResponse {
  runtime: Record<string, unknown>
  traces: {
    summary: TraceSummary
    export_preview: TraceExportPreview
  }
  metrics_aggregation: Record<string, unknown>
  dashboard_cards: TraceDashboardCard[]
  panel_templates: TracePanelTemplate[]
}

export type ResourceGrantRole = 'viewer' | 'editor' | 'admin' | 'owner'
export type ResourceGrantSubjectType = 'user' | 'org'

export interface ResourceGrant {
  resource_type: string
  resource_id: string
  org_id?: string
  user_id?: string
  role: ResourceGrantRole
  created_at: number
  updated_at: number
}

export interface ResourceGrantListQuery {
  resource_type?: string
  resource_id?: string
  org_id?: string
  user_id?: string
  role?: ResourceGrantRole | ''
  subject_type?: ResourceGrantSubjectType | ''
  limit?: number
  offset?: number
}

export interface ResourceGrantListResponse {
  grants: ResourceGrant[]
  total: number
  limit: number
  offset: number
  returned: number
}

export interface ResourceGrantMutationPayload {
  resource_type: string
  resource_id: string
  org_id?: string
  user_id?: string
  role?: ResourceGrantRole
}

export type IdentityRole = ResourceGrantRole

export interface IdentityOrganization {
  org_id: string
  name: string
  description: string
  created_at: number
  updated_at: number
}

export interface IdentityUser {
  user_id: string
  display_name: string
  email: string
  created_at: number
  updated_at: number
}

export interface IdentityMembership {
  org_id: string
  user_id: string
  role: IdentityRole
  created_at: number
  updated_at: number
}

export interface IdentityCatalog {
  organizations: IdentityOrganization[]
  users: IdentityUser[]
  memberships: IdentityMembership[]
}

export interface UpsertOrganizationPayload {
  org_id: string
  name: string
  description?: string
}

export interface UpsertUserPayload {
  user_id: string
  display_name?: string
  email?: string
}

export interface SetMembershipPayload {
  org_id: string
  user_id: string
  role: IdentityRole
}

function normalizeSession(raw: Partial<Session> & Pick<Session, 'session_id' | 'title' | 'created_at' | 'updated_at' | 'message_count'>): Session {
  return {
    session_id: raw.session_id,
    title: raw.title,
    created_at: raw.created_at,
    updated_at: raw.updated_at,
    message_count: raw.message_count,
    is_archived: raw.is_archived === true,
    is_favorite: raw.is_favorite === true,
    is_pinned: raw.is_pinned === true,
    session_order: Number(raw.session_order ?? 0) || 0,
    tags: Array.isArray(raw.tags)
      ? raw.tags.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
      : [],
    workspace_id: typeof raw.workspace_id === 'string' && raw.workspace_id.trim()
      ? raw.workspace_id.trim()
      : 'workspace-default',
    search_preview:
      typeof raw.search_preview === 'string' && raw.search_preview.trim()
        ? raw.search_preview
        : undefined,
    search_source: raw.search_source === 'message' ? 'message' : raw.search_source === 'title' ? 'title' : undefined,
  }
}

function normalizeWorkspace(raw: Partial<Workspace> & Pick<Workspace, 'workspace_id' | 'name' | 'created_at' | 'updated_at' | 'session_count'>): Workspace {
  const color = typeof raw.color === 'string' ? raw.color.trim().toLowerCase() : 'blue'
  const rawPreset = (raw as Partial<Workspace> & { preset?: Partial<WorkspacePreset> }).preset
  const rawToolConfig = rawPreset?.tool_config
  const rawOutputPreset = rawPreset?.output_preset
  return {
    workspace_id: raw.workspace_id,
    name: raw.name,
    description: typeof raw.description === 'string' ? raw.description : '',
    color: (['slate', 'blue', 'green', 'amber', 'rose'].includes(color) ? color : 'blue') as Workspace['color'],
    preset: {
      default_panels: Array.isArray(rawPreset?.default_panels)
        ? rawPreset!.default_panels
          .filter(
            (item) =>
              Boolean(
                item &&
                typeof item === 'object' &&
                typeof (item as { panel_id?: string }).panel_id === 'string' &&
                (item as { panel_id?: string }).panel_id?.trim(),
              ),
          )
          .map((item) => normalizeModelConfig(item as Partial<ModelConfig> & { panel_id: string }))
        : [],
      tool_config: {
        web_search_enabled: rawToolConfig?.web_search_enabled === true,
        knowledge_base_enabled: rawToolConfig?.knowledge_base_enabled !== false,
        mcp_servers_enabled: Array.isArray(rawToolConfig?.mcp_servers_enabled)
          ? rawToolConfig.mcp_servers_enabled.filter(
              (item): item is string => typeof item === 'string' && item.trim().length > 0,
            )
          : ['knowledge-base', 'web-search'],
      },
      output_preset: {
        deck_theme:
          rawOutputPreset?.deck_theme === 'midnight' || rawOutputPreset?.deck_theme === 'sunrise'
            ? rawOutputPreset.deck_theme
            : 'default',
        target_slide_count: Math.max(
          4,
          Math.min(10, Number(rawOutputPreset?.target_slide_count ?? 8) || 8),
        ),
      },
    },
    is_active: raw.is_active === true,
    created_at: raw.created_at,
    updated_at: raw.updated_at,
    session_count: Number(raw.session_count ?? 0),
  }
}

function normalizeBookmark(raw: Partial<Bookmark> & { id: string }): Bookmark {
  const rawBookmark = raw as Partial<Bookmark> & {
    session_id?: string
    session_title?: string
    message_id?: number
    panel_id?: string
    answer_group_id?: string
    model_id?: string
    created_at?: number
    updated_at?: number
  }

  return {
    id: raw.id,
    sessionId:
      typeof rawBookmark.sessionId === 'string' && rawBookmark.sessionId.trim()
        ? rawBookmark.sessionId.trim()
        : typeof rawBookmark.session_id === 'string' && rawBookmark.session_id.trim()
          ? rawBookmark.session_id.trim()
          : '',
    sessionTitle:
      typeof rawBookmark.sessionTitle === 'string'
        ? rawBookmark.sessionTitle
        : typeof rawBookmark.session_title === 'string'
          ? rawBookmark.session_title
          : '',
    messageId:
      typeof rawBookmark.messageId === 'number'
        ? rawBookmark.messageId
        : typeof rawBookmark.message_id === 'number'
          ? rawBookmark.message_id
          : undefined,
    panelId:
      typeof rawBookmark.panelId === 'string'
        ? rawBookmark.panelId
        : typeof rawBookmark.panel_id === 'string'
          ? rawBookmark.panel_id
          : '',
    answerGroupId:
      typeof rawBookmark.answerGroupId === 'string'
        ? rawBookmark.answerGroupId
        : typeof rawBookmark.answer_group_id === 'string'
          ? rawBookmark.answer_group_id
          : '',
    role: rawBookmark.role === 'user' ? 'user' : 'assistant',
    content: typeof rawBookmark.content === 'string' ? rawBookmark.content : '',
    modelId:
      typeof rawBookmark.modelId === 'string'
        ? rawBookmark.modelId
        : typeof rawBookmark.model_id === 'string'
          ? rawBookmark.model_id
          : undefined,
    createdAt:
      typeof rawBookmark.createdAt === 'number'
        ? rawBookmark.createdAt
        : typeof rawBookmark.created_at === 'number'
          ? rawBookmark.created_at
          : Date.now() / 1000,
    updatedAt:
      typeof rawBookmark.updatedAt === 'number'
        ? rawBookmark.updatedAt
        : typeof rawBookmark.updated_at === 'number'
          ? rawBookmark.updated_at
          : Date.now() / 1000,
    source: rawBookmark.source === 'local' ? 'local' : 'remote',
  }
}

export interface Message {
  id?: number
  role: 'user' | 'assistant'
  content: string
  images?: ChatImage[]
  files?: ChatFile[]
  sources?: SourceItem[]
  model_id?: string
  panel_id?: string
  answer_group_id?: string
  workflow_nodes?: WorkflowNode[]
  task_id?: string
  task_type?: string
  timestamp?: number
  feedback_value?: MessageFeedbackValue
}

export interface SessionPanel {
  panel_id: string
  is_primary: boolean
  display_order: number
  model_config: ModelConfig
}

export type ConnectionType = 'ollama' | 'openai_compatible'

export interface ModelConfig {
  panel_id: string
  connection_type?: ConnectionType
  provider?: ConnectionType | 'local' | 'cloud' | 'openai' | 'openrouter'
  model: string
  base_url: string
  api_key: string
  api_key_ref?: string
  temperature: number
  agent_mode: 'auto' | 'langgraph' | 'function_calling' | 'plain_chat'
}

export function normalizeConnectionType(
  connectionType?: string,
  baseUrl?: string,
): ConnectionType {
  const rawType = (connectionType ?? '').trim().toLowerCase()
  const rawBaseUrl = (baseUrl ?? '').trim().toLowerCase()

  if (rawType === 'ollama' || rawType === 'local') return 'ollama'
  if (
    rawType === 'openai_compatible' ||
    rawType === 'cloud' ||
    rawType === 'openai' ||
    rawType === 'openrouter'
  ) {
    return 'openai_compatible'
  }

  if (rawBaseUrl.includes('11434')) return 'ollama'
  return 'openai_compatible'
}

export function defaultBaseUrlForConnectionType(connectionType: ConnectionType): string {
  return connectionType === 'ollama'
    ? 'http://localhost:11434'
    : 'https://openrouter.ai/api/v1'
}

export function defaultModelForConnectionType(connectionType: ConnectionType): string {
  return connectionType === 'ollama' ? 'qwen3.5-2B:latest' : 'gpt-4o-mini'
}

export function normalizeModelConfig(config: Partial<ModelConfig> & { panel_id: string }): ModelConfig {
  const connectionType = normalizeConnectionType(
    config.connection_type ?? config.provider,
    config.base_url,
  )
  return {
    panel_id: config.panel_id,
    connection_type: connectionType,
    provider: connectionType,
    model: (config.model ?? defaultModelForConnectionType(connectionType)).trim(),
    base_url: (config.base_url ?? defaultBaseUrlForConnectionType(connectionType)).trim(),
    api_key: config.api_key ?? '',
    api_key_ref: (config.api_key_ref ?? '').trim(),
    temperature: config.temperature ?? 0.3,
    agent_mode: config.agent_mode ?? 'auto',
  }
}

export function getConnectionTypeLabel(modelConfig: ModelConfig): string {
  const connectionType = normalizeConnectionType(
    modelConfig.connection_type ?? modelConfig.provider,
    modelConfig.base_url,
  )
  return connectionType === 'ollama' ? '本地 Ollama' : 'OpenAI 兼容'
}

export interface SourceItem {
  type: 'doc' | 'web' | 'attachment'
  title: string
  url?: string
  snippet: string
  index?: number
  provider?: string
  domain?: string
  published_at?: string
  retrieval_mode?: string
  search_channel?: string
  score?: number
  provider_score?: number
  confidence?: number
  trust_score?: number
  freshness_score?: number
  source_quality?: string
  matched_terms?: string[]
  evidence_tags?: string[]
  retrieval_query?: string
  feedback_boost?: number
  feedback_net?: number
  feedback_positive_count?: number
  feedback_negative_count?: number
  answer_group_id?: string
  attachment_kind?: 'file' | 'image'
  media_type?: string
  data_url?: string
}

export interface ChatImage {
  name: string
  media_type: string
  data_url: string
}

export interface ChatFile {
  name: string
  media_type: string
  data_url?: string
  size_bytes: number
  extracted_text?: string
}

export interface SessionAttachment {
  attachment_id: string
  kind: 'file' | 'image'
  name: string
  media_type: string
  data_url?: string
  size_bytes: number
  extracted_text?: string
  preview_text?: string
  text_char_count: number
  occurrence_count: number
  turn_count: number
  first_seen_at: number
  last_seen_at: number
  latest_answer_group_id?: string
  current_vector_store_path?: string
  promotion_status?: 'idle' | TaskStatus
  promotion_task_id?: string | null
  promotion_updated_at?: number | null
  is_in_current_kb?: boolean
}

export interface SessionAttachmentSummary {
  total_attachments: number
  file_count: number
  image_count: number
  text_ready_count: number
  reusable_count: number
  total_size_bytes: number
  indexed_in_current_kb_count?: number
  indexing_in_current_kb_count?: number
}

export interface SSEChunk {
  panel_id: string
  type: 'chunk' | 'done' | 'error' | 'sources' | 'all_done' | 'task_created' | 'workflow_state'
  content?: string
  error_code?: string
  suggestion?: string
  sources?: SourceItem[]
  task_id?: string
  task_type?: string
  node_name?: string
  status?: 'running' | 'completed' | 'failed'
  duration_ms?: number
  tool_name?: string
  tool_params?: Record<string, unknown>
  tool_result_summary?: string
  retrieval_meta?: {
    primary_mode?: string
    modes?: string[]
    channels?: string[]
    source_count?: number
    source_titles?: string[]
    matched_terms?: string[]
    top_score?: number | null
  }
  error?: string
  timestamp?: number
}

export interface DocStats {
  status: string
  total_docs?: number
  store_path?: string
}

export interface UploadDocumentsResponse {
  ok: boolean
  task_id: string
  task_type: string
  status: string
  message: string
}

export type TaskStatus = 'pending' | 'running' | 'waiting_approval' | 'completed' | 'failed'

export type TaskApprovalDecision = 'approved' | 'rejected'

export interface TaskApprovalPolicy {
  enabled: boolean
  required_task_types: string[]
  high_risk_requires_approval: boolean
  default_reviewer_role: string
  updated_at: number | null
}

export interface BatchTaskApproval {
  task_ids: string[]
  decision: TaskApprovalDecision
  reviewer?: string
  comment?: string
}

export interface BatchTaskApprovalResult {
  task_id: string
  ok?: boolean
  succeeded?: boolean
  success?: boolean
  status?: TaskStatus | string
  task?: TaskRecord
  error?: string
}

export interface BatchTaskApprovalResponse {
  total: number
  succeeded: number
  failed: number
  results: BatchTaskApprovalResult[]
}

export interface CreateMultiAgentWorkflowTaskPayload {
  user_request: string
  session_id?: string
  panel_id?: string
  answer_group_id?: string
  model_id?: string
  context?: Record<string, unknown>
  data_files?: ChatFile[]
  plan?: Array<Record<string, unknown>>
  panel_config?: ModelConfig | Record<string, unknown>
  research_mode?: 'quick' | 'deep'
  providers?: string[]
  max_rounds?: number
  max_results_per_query?: number
  max_fetch_pages?: number
  time_range?: string
  use_kb_context?: boolean
  vector_store_path?: string
  allow_quick_fallback?: boolean
}

export interface TaskRecord {
  task_id: string
  task_type: string
  status: TaskStatus
  progress: number
  result?: string
  error?: string
  params?: Record<string, unknown>
  session_id?: string | null
  created_at: number
  updated_at?: number
}

export interface SystemPrompt {
  id: string
  name: string
  content: string
  is_default: boolean
  is_active: boolean
  created_at: number
  updated_at: number
  vector_store_id?: string
  dashboard_template?: DashboardTemplateConfig
}

export interface DashboardTemplateConfig {
  enabled: boolean
  title_hint: string
  focus_metrics: string[]
  preferred_charts: Array<'bar' | 'line' | 'pie'>
  section_order: Array<'summary' | 'metrics' | 'charts' | 'table' | 'evidence' | 'warnings'>
  audience_tone: string
}

export interface KnowledgeBase {
  id: string
  name: string
  path: string
  doc_count: number
  has_index: boolean
}

export interface KBHealthData {
  index_status: 'healthy' | 'empty' | 'not_found' | 'error'
  total_chunks: number
  store_path: string
  store_size_mb: number
  documents: { name: string; chunks: number }[]
  embedding_model: string
  last_updated: number | null
}

export interface KnowledgeBaseChunk {
  chunk_id: string
  position: number
  source: string
  content: string
  preview: string
  char_count: number
  metadata: Record<string, unknown>
}

export interface KnowledgeBaseChunksResponse {
  items: KnowledgeBaseChunk[]
  total: number
  offset: number
  limit: number
  has_more: boolean
  store_path: string
}

export interface RetrievalTestResult {
  results_count: number
  latency_ms: number
  retrieval_mode?: 'semantic' | 'keyword' | 'hybrid'
  search_mode?: 'semantic' | 'semantic_rerank' | 'keyword' | 'hybrid' | 'hybrid_rerank'
  search_k?: number
  top_k?: number
  fetch_k?: number
  rewrite_query?: string
  rewrite_applied?: boolean
  query_terms?: string[]
  coverage?: {
    unique_sources: number
    source_ratio: number
    matched_terms: string[]
    matched_term_count: number
  }
  top_results?: RetrievalDebugItem[]
  semantic_candidates?: RetrievalDebugItem[]
  keyword_candidates?: RetrievalDebugItem[]
  fused_candidates?: RetrievalDebugItem[]
  error?: string
}

export interface RetrievalDebugItem {
  rank: number
  source: string
  snippet: string
  score: number
  channel: string
  matched_terms?: string[]
  feedback_boost?: number
  feedback_net?: number
  feedback_positive_count?: number
  feedback_negative_count?: number
  score_breakdown?: Record<string, number>
}

export interface MessagesResponse {
  messages: Message[]
  context_limit: number
  total_messages: number
  panels?: SessionPanel[]
  panel_messages?: Record<string, Message[]>
}

export interface ImportSessionMessagesPayload {
  panels: ModelConfig[]
  messages: Message[]
}

export interface Bookmark {
  id: string
  sessionId: string
  sessionTitle: string
  messageId?: number
  panelId: string
  answerGroupId: string
  role: 'user' | 'assistant'
  content: string
  modelId?: string
  createdAt: number
  updatedAt: number
  source?: 'remote' | 'local'
}

export interface SessionAttachmentsResponse {
  session_id: string
  attachments: SessionAttachment[]
  summary: SessionAttachmentSummary
  current_vector_store_path?: string
}

export interface AnswerGroupReviewFactor {
  factor: string
  winner_panel_id: string
  detail: string
}

export interface AnswerGroupReviewComparisonFactorDelta {
  factor: string
  delta: number
  detail: string
}

export interface AnswerGroupReviewComparison {
  against_panel_id: string
  against_model_id: string
  score_gap: number
  recommended_advantages: string[]
  tradeoffs: string[]
  factor_deltas: AnswerGroupReviewComparisonFactorDelta[]
}

export interface AnswerGroupReviewConsensusPoint {
  term: string
  support_count: number
  panel_ids: string[]
}

export interface AnswerGroupReviewDifferencePoint {
  panel_id: string
  model_id: string
  unique_terms: string[]
  note: string
}

export interface AnswerGroupModelPerformance {
  panel_id: string
  model_id: string
  latency_seconds: number | null
  chars_per_second: number | null
  content_length: number
  source_count: number
  completed_workflow_count: number
  token_usage?: AnswerGroupTokenUsage
  score: number
}

export interface AnswerGroupTokenUsage {
  panel_id?: string
  model_id?: string
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  estimated: boolean
  estimation_method?: string
}

export interface AnswerGroupTokenSummary {
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  estimated: boolean
  estimated_count: number
  real_count: number
  by_panel: AnswerGroupTokenUsage[]
}

export interface AnswerGroupSynthesis {
  answer: string
  source_panel_id: string
  source_model_id: string
  strategy: string
  consensus_terms: string[]
  difference_notes: string[]
  tradeoffs: string[]
  estimated: boolean
}

export interface AnswerGroupPreferenceSignal {
  kind: string
  session_id: string
  answer_group_id: string
  selected_panel_id: string
  selected_model_id: string
  recommended_panel_id: string
  recommended_model_id: string
  accepted_recommendation: boolean
  alternative_panel_ids: string[]
  confidence: number
  persisted: boolean
  persistence?: {
    store: string
    value: number
  }
}

export interface AnswerGroupReviewResponseItem {
  panel_id: string
  model_id: string
  content: string
  excerpt: string
  source_count: number
  workflow_node_count: number
  completed_workflow_count: number
  content_length: number
  token_usage?: AnswerGroupTokenUsage
  score: number
  score_breakdown: Record<string, number>
  strengths: string[]
  concerns: string[]
  is_primary_panel: boolean
}

export interface AnswerGroupReviewResponse {
  session_id: string
  answer_group_id: string
  review_mode: string
  reviewer_label: string
  recommended_panel_id: string
  recommended_model_id: string
  confidence: number
  confidence_label: string
  summary: string
  why_recommended: string
  decision_factors: AnswerGroupReviewFactor[]
  comparisons: AnswerGroupReviewComparison[]
  consensus_points?: AnswerGroupReviewConsensusPoint[]
  difference_points?: AnswerGroupReviewDifferencePoint[]
  token_usage?: AnswerGroupTokenUsage[]
  token_summary?: AnswerGroupTokenSummary
  synthesis?: AnswerGroupSynthesis
  synthesized_answer?: string
  preference_signal?: AnswerGroupPreferenceSignal
  model_performance?: AnswerGroupModelPerformance[]
  responses: AnswerGroupReviewResponseItem[]
}

export interface PromoteAnswerResponse {
  ok: boolean
  target_panel_id: string
  source_panel_id: string
  answer_group_id: string
  content: string
  model_id: string
  sources?: SourceItem[]
  workflow_nodes?: WorkflowNode[]
  task_id?: string
  task_type?: string
  review?: AnswerGroupReviewResponse
  preference_signal?: AnswerGroupPreferenceSignal
}

export interface ShareLinkResponse {
  resource_type: 'session' | 'deck'
  resource_id: string
  share_token: string
  share_url: string
}

export interface DeckWarning {
  code: string
  message: string
}

export type DeckQualityState = 'supported' | 'weak_support' | 'manual'

export interface DeckSlideEvidenceCoverage {
  slide_id: string
  slide_type: string
  evidence_ref_count: number
  has_evidence: boolean
  is_coverable: boolean
  quality_state: DeckQualityState
}

export interface DeckEvidenceCoverage {
  total_slides: number
  coverable_slide_count: number
  slides_with_evidence: number
  total_evidence_refs: number
  coverage_ratio: number
  unsupported_slide_ids: string[]
  slides: DeckSlideEvidenceCoverage[]
}

export type DeckEvidenceReviewStatus = 'supported' | 'needs_review' | 'not_applicable'
export type DeckEvidenceReviewSeverity = 'info' | 'warning' | 'error'

export interface DeckEvidenceReviewActionItem {
  code: string
  severity: DeckEvidenceReviewSeverity
  message: string
  slide_ids: string[]
}

export type DeckCitationValidationStatus = 'passed' | 'failed'

export interface DeckCitationValidationIssue {
  code: string
  message: string
  slide_id: string
  block_id: string
  evidence_ref_id: string
  source_id: string
}

export interface DeckCitationValidation {
  status: DeckCitationValidationStatus
  can_export: boolean
  issue_count: number
  missing_source_ids: string[]
  missing_block_evidence_ref_ids: string[]
  issues: DeckCitationValidationIssue[]
}

export interface DeckEvidenceReviewSlide {
  slide_id: string
  title: string
  slide_type: string
  is_coverable: boolean
  has_evidence: boolean
  evidence_ref_count: number
  quality_state: DeckQualityState
  needs_review: boolean
  source_ids: string[]
  source_titles: string[]
}

export interface DeckEvidenceReview {
  status: DeckEvidenceReviewStatus
  coverage_ratio: number
  coverable_slide_count: number
  slides_with_evidence: number
  unsupported_slide_ids: string[]
  needs_review_slide_ids: string[]
  action_count: number
  action_items: DeckEvidenceReviewActionItem[]
  slides: DeckEvidenceReviewSlide[]
  citation_validation?: DeckCitationValidation
}

export interface DeckMeta {
  title: string
  subtitle: string
  language: string
  audience: string
  purpose: string
  author: string
  theme: 'default' | 'midnight' | 'sunrise'
  created_at: string
  session_id: string
  source_mode: 'kb_plus_chat' | 'chat_only'
  generator_panel_id: string
  source_answer_group_id?: string
  source_panel_id?: string
}

export interface DeckGeneration {
  source: 'kb_plus_chat' | 'chat_only'
  target_slide_count: number
  actual_slide_count: number
  warnings: DeckWarning[]
  evidence_coverage?: DeckEvidenceCoverage
  evidence_review?: DeckEvidenceReview
  citation_validation?: DeckCitationValidation
}

export interface DeckChartDataset {
  label: string
  data: number[]
}

export interface DeckBlock {
  id: string
  kind: string
  role: string
  content: {
    text?: string
    items?: string[]
    title?: string
    description?: string
    chart_type?: 'bar' | 'line' | 'pie'
    labels?: string[]
    datasets?: DeckChartDataset[]
    evidence_ref_ids?: string[]
    evidence_source_ids?: string[]
    evidence_excerpt_ids?: string[]
  }
  editable: boolean
}

export interface DeckEvidenceRef {
  id: string
  source_id: string
  source_title: string
  excerpt_id?: string | null
  snippet: string
  confidence: number
}

export interface DeckSlideStatus {
  locked: boolean
  dirty: boolean
  review_state: string
}

export interface DeckSlide {
  id: string
  type: string
  title: string
  subtitle: string
  layout: string
  intent: string
  speaker_notes: string
  blocks: DeckBlock[]
  evidence_refs: DeckEvidenceRef[]
  quality_state: DeckQualityState
  status: DeckSlideStatus
}

export interface DeckSourceItem {
  id: string
  type: string
  title: string
  document_id?: string | null
  uri?: string | null
  metadata: Record<string, unknown>
}

export interface DeckSpec {
  version: string
  deck_id: string
  status: string
  meta: DeckMeta
  generation: DeckGeneration
  slides: DeckSlide[]
  source_registry: DeckSourceItem[]
  citation_validation?: DeckCitationValidation
}

export type ArtifactType = 'report' | 'deck'
export type ArtifactExportFormat = 'md' | 'docx' | 'xlsx' | 'pptx'

export interface ReportArtifactQA {
  question: string
  answer: string
}

export interface ClaimEvidenceSource {
  source_index: number
  title: string
  url?: string
  domain?: string
  source_tier?: string
  source_family?: string
  freshness_band?: string
  published_at?: string
  selection_reason?: string
  provider_caveat?: string
}

export interface ClaimEvidenceChain {
  claim_id: string
  claim_text: string
  facet?: string
  claim_type?: string
  date?: string
  status: string
  evidence_strength: string
  verification_note?: string
  candidate_sources: string[]
  supporting_source_count: number
  independent_source_families: string[]
  has_primary_source: boolean
  needs_attention: boolean
  sources: ClaimEvidenceSource[]
}

export interface ClaimVerificationSummary {
  total_claims: number
  verified_claims: number
  partial_claims: number
  unverified_claims: number
  high_strength_claims: number
  medium_strength_claims: number
  low_strength_claims: number
  claims_needing_attention: string[]
  contradiction_count: number
  resolution_actions: Record<string, number>
}

export type ResearchParagraphCitation = Record<string, unknown>

export interface ResearchNavigationIndex {
  paragraph_to_claims: Record<string, string[]>
  paragraph_to_sources: Record<string, string[]>
  claim_to_paragraphs: Record<string, string[]>
  source_to_paragraphs: Record<string, string[]>
  links: Array<Record<string, unknown>>
}

export interface ResearchCitationGraph {
  nodes: Array<Record<string, unknown>>
  edges: Array<Record<string, unknown>>
}

export interface ResearchConflictSummary {
  conflict_count: number
  conflicts: Array<Record<string, unknown>>
  details?: Record<string, unknown>
}

export interface ResearchConflictGroup {
  group_id: string
  normalized_claim: string
  normalized_source: string
  normalized_conflict_text: string
  conflict_text: string
  claim_ids: string[]
  source_ids: string[]
  review_statuses: string[]
  total: number
  archives: Array<Record<string, unknown>>
}

export interface ResearchConflictResolutionPayload {
  conflict_id?: string
  claim_id?: string
  status: 'resolved' | 'dismissed' | 'needs_followup' | 'reviewed'
  resolution?: string
  note?: string
  reviewer?: string
}

export interface ResearchArchive {
  archive_id: string
  title: string
  session_id?: string
  task_id?: string
  artifact_id?: string
  claim_count: number
  source_count: number
  verification_summary?: ClaimVerificationSummary
  claim_evidence_chains: ClaimEvidenceChain[]
  paragraph_citations: ResearchParagraphCitation[]
  paragraph_claim_links: Array<Record<string, unknown>>
  navigation_index?: ResearchNavigationIndex
  citation_graph?: ResearchCitationGraph
  conflict_summary?: ResearchConflictSummary
  conflict_review_resolutions: Array<Record<string, unknown>>
  provider_capabilities?: Record<string, unknown>
  delivery_quality?: Record<string, unknown>
  preview_claims?: Array<Record<string, unknown>>
  preview_sources?: Array<Record<string, unknown>>
  created_at?: number
  updated_at?: number
}

export interface ResearchArchiveListResponse {
  archives: ResearchArchive[]
  conflict_groups: ResearchConflictGroup[]
  total: number
  limit: number
}

export interface ReportArtifactContent {
  markdown: string
  qa_pairs: ReportArtifactQA[]
  answer_group_id?: string | null
  panel_id?: string | null
  claim_evidence_chains: ClaimEvidenceChain[]
  claim_verification_summary?: ClaimVerificationSummary
}

export interface DeckArtifactContent {
  deck_id: string
  theme: string
  slide_count: number
  answer_group_id?: string | null
  panel_id?: string | null
  evidence_coverage?: DeckEvidenceCoverage
  evidence_review?: DeckEvidenceReview
  citation_validation?: DeckCitationValidation
}

export interface ArtifactRecord {
  artifact_id: string
  session_id: string
  artifact_type: ArtifactType
  title: string
  status: string
  linked_resource_type?: string | null
  linked_resource_id?: string | null
  content: ReportArtifactContent | DeckArtifactContent | Record<string, unknown>
  available_formats: ArtifactExportFormat[]
  created_at: number
  updated_at: number
}

function readString(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function readNumber(value: unknown): number {
  return typeof value === 'number' ? value : Number(value ?? 0) || 0
}

function readStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === 'string')
    : []
}

function readOptionalRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === 'object' && value !== null ? (value as Record<string, unknown>) : undefined
}

function readRecordCollection(value: unknown): Array<Record<string, unknown>> {
  if (Array.isArray(value)) {
    return value
      .map((item, index): Record<string, unknown> | undefined => {
        if (typeof item === 'object' && item !== null) return item as Record<string, unknown>
        if (item === undefined || item === null) return undefined
        return { index, value: item }
      })
      .filter((item): item is Record<string, unknown> => item !== undefined)
  }

  const data = readOptionalRecord(value)
  if (!data) return []
  return Object.entries(data).map(([key, item]) => {
    if (typeof item === 'object' && item !== null) {
      return { key, ...(item as Record<string, unknown>) }
    }
    return { key, value: item }
  })
}

function readStringArrayRecord(value: unknown): Record<string, string[]> {
  const data = readOptionalRecord(value)
  if (!data) return {}
  return Object.fromEntries(
    Object.entries(data).map(([key, item]) => [key, readStringArray(item)]),
  )
}

function readFirstField(
  primary: Record<string, unknown>,
  fallback: Record<string, unknown>,
  keys: string[],
): unknown {
  for (const key of keys) {
    if (primary[key] !== undefined) return primary[key]
    if (fallback[key] !== undefined) return fallback[key]
  }
  return undefined
}

function normalizeDeckQualityState(value: unknown): DeckQualityState {
  return value === 'supported' || value === 'manual' ? value : 'weak_support'
}

function normalizeDeckSlideEvidenceCoverage(value: unknown): DeckSlideEvidenceCoverage[] {
  if (!Array.isArray(value)) return []
  return value
    .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    .map((item) => ({
      slide_id: readString(item.slide_id),
      slide_type: readString(item.slide_type),
      evidence_ref_count: readNumber(item.evidence_ref_count),
      has_evidence: item.has_evidence === true,
      is_coverable: item.is_coverable !== false,
      quality_state: normalizeDeckQualityState(item.quality_state),
    }))
}

function normalizeDeckEvidenceCoverage(value: unknown): DeckEvidenceCoverage | undefined {
  if (typeof value !== 'object' || value === null) return undefined
  const data = value as Record<string, unknown>
  return {
    total_slides: readNumber(data.total_slides),
    coverable_slide_count: readNumber(data.coverable_slide_count),
    slides_with_evidence: readNumber(data.slides_with_evidence),
    total_evidence_refs: readNumber(data.total_evidence_refs),
    coverage_ratio: readNumber(data.coverage_ratio),
    unsupported_slide_ids: readStringArray(data.unsupported_slide_ids),
    slides: normalizeDeckSlideEvidenceCoverage(data.slides),
  }
}

function normalizeDeckEvidenceReviewStatus(value: unknown): DeckEvidenceReviewStatus {
  if (value === 'supported' || value === 'not_applicable') return value
  return 'needs_review'
}

function normalizeDeckEvidenceReviewSeverity(value: unknown): DeckEvidenceReviewSeverity {
  if (value === 'error' || value === 'info') return value
  return 'warning'
}

function normalizeDeckEvidenceReviewActionItems(value: unknown): DeckEvidenceReviewActionItem[] {
  if (!Array.isArray(value)) return []
  return value
    .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    .map((item) => ({
      code: readString(item.code),
      severity: normalizeDeckEvidenceReviewSeverity(item.severity),
      message: readString(item.message),
      slide_ids: readStringArray(item.slide_ids),
    }))
}

function normalizeDeckCitationValidationStatus(value: unknown): DeckCitationValidationStatus {
  return value === 'failed' ? 'failed' : 'passed'
}

function normalizeDeckCitationValidationIssues(value: unknown): DeckCitationValidationIssue[] {
  if (!Array.isArray(value)) return []
  return value
    .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    .map((item) => ({
      code: readString(item.code),
      message: readString(item.message),
      slide_id: readString(item.slide_id),
      block_id: readString(item.block_id),
      evidence_ref_id: readString(item.evidence_ref_id),
      source_id: readString(item.source_id),
    }))
}

function normalizeDeckCitationValidation(value: unknown): DeckCitationValidation | undefined {
  if (typeof value !== 'object' || value === null) return undefined
  const data = value as Record<string, unknown>
  const issues = normalizeDeckCitationValidationIssues(data.issues)
  return {
    status: normalizeDeckCitationValidationStatus(data.status),
    can_export: data.can_export !== false,
    issue_count: readNumber(data.issue_count) || issues.length,
    missing_source_ids: readStringArray(data.missing_source_ids),
    missing_block_evidence_ref_ids: readStringArray(data.missing_block_evidence_ref_ids),
    issues,
  }
}

function normalizeDeckEvidenceReviewSlides(value: unknown): DeckEvidenceReviewSlide[] {
  if (!Array.isArray(value)) return []
  return value
    .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    .map((item) => ({
      slide_id: readString(item.slide_id),
      title: readString(item.title),
      slide_type: readString(item.slide_type),
      is_coverable: item.is_coverable !== false,
      has_evidence: item.has_evidence === true,
      evidence_ref_count: readNumber(item.evidence_ref_count),
      quality_state: normalizeDeckQualityState(item.quality_state),
      needs_review: item.needs_review === true,
      source_ids: readStringArray(item.source_ids),
      source_titles: readStringArray(item.source_titles),
    }))
}

function normalizeDeckEvidenceReview(value: unknown): DeckEvidenceReview | undefined {
  if (typeof value !== 'object' || value === null) return undefined
  const data = value as Record<string, unknown>
  const actionItems = normalizeDeckEvidenceReviewActionItems(data.action_items)
  return {
    status: normalizeDeckEvidenceReviewStatus(data.status),
    coverage_ratio: readNumber(data.coverage_ratio),
    coverable_slide_count: readNumber(data.coverable_slide_count),
    slides_with_evidence: readNumber(data.slides_with_evidence),
    unsupported_slide_ids: readStringArray(data.unsupported_slide_ids),
    needs_review_slide_ids: readStringArray(data.needs_review_slide_ids),
    action_count: readNumber(data.action_count) || actionItems.length,
    action_items: actionItems,
    slides: normalizeDeckEvidenceReviewSlides(data.slides),
    citation_validation: normalizeDeckCitationValidation(data.citation_validation),
  }
}

function defaultDeckCitationValidation(): DeckCitationValidation {
  return {
    status: 'passed',
    can_export: true,
    issue_count: 0,
    missing_source_ids: [],
    missing_block_evidence_ref_ids: [],
    issues: [],
  }
}

function defaultDeckEvidenceReview(): DeckEvidenceReview {
  return {
    status: 'not_applicable',
    coverage_ratio: 0,
    coverable_slide_count: 0,
    slides_with_evidence: 0,
    unsupported_slide_ids: [],
    needs_review_slide_ids: [],
    action_count: 0,
    action_items: [],
    slides: [],
  }
}

function normalizeDeckBlock(raw: unknown, index: number): DeckBlock {
  const data = typeof raw === 'object' && raw !== null ? (raw as Record<string, unknown>) : {}
  const content = typeof data.content === 'object' && data.content !== null
    ? (data.content as Record<string, unknown>)
    : {}
  return {
    id: readString(data.id) || `block-${index + 1}`,
    kind: readString(data.kind),
    role: readString(data.role),
    content: {
      ...content,
      text: readString(content.text) || undefined,
      items: readStringArray(content.items),
      title: readString(content.title) || undefined,
      description: readString(content.description) || undefined,
      chart_type:
        content.chart_type === 'bar' || content.chart_type === 'line' || content.chart_type === 'pie'
          ? content.chart_type
          : undefined,
      labels: readStringArray(content.labels),
      datasets: Array.isArray(content.datasets) ? (content.datasets as DeckChartDataset[]) : [],
      evidence_ref_ids: readStringArray(content.evidence_ref_ids),
      evidence_source_ids: readStringArray(content.evidence_source_ids),
      evidence_excerpt_ids: readStringArray(content.evidence_excerpt_ids),
    },
    editable: data.editable !== false,
  }
}

function normalizeDeckEvidenceRef(raw: unknown): DeckEvidenceRef {
  const data = typeof raw === 'object' && raw !== null ? (raw as Record<string, unknown>) : {}
  return {
    id: readString(data.id),
    source_id: readString(data.source_id),
    source_title: readString(data.source_title),
    excerpt_id: data.excerpt_id === null ? null : readString(data.excerpt_id) || undefined,
    snippet: readString(data.snippet),
    confidence: readNumber(data.confidence),
  }
}

function normalizeDeckSlide(raw: unknown, index: number): DeckSlide {
  const data = typeof raw === 'object' && raw !== null ? (raw as Record<string, unknown>) : {}
  const status = typeof data.status === 'object' && data.status !== null
    ? (data.status as Record<string, unknown>)
    : {}
  return {
    id: readString(data.id) || `slide-${index + 1}`,
    type: readString(data.type),
    title: readString(data.title),
    subtitle: readString(data.subtitle),
    layout: readString(data.layout),
    intent: readString(data.intent),
    speaker_notes: readString(data.speaker_notes),
    blocks: Array.isArray(data.blocks) ? data.blocks.map(normalizeDeckBlock) : [],
    evidence_refs: Array.isArray(data.evidence_refs) ? data.evidence_refs.map(normalizeDeckEvidenceRef) : [],
    quality_state: normalizeDeckQualityState(data.quality_state),
    status: {
      locked: status.locked === true,
      dirty: status.dirty === true,
      review_state: readString(status.review_state) || 'draft',
    },
  }
}

function normalizeDeckSourceItem(raw: unknown): DeckSourceItem {
  const data = typeof raw === 'object' && raw !== null ? (raw as Record<string, unknown>) : {}
  return {
    id: readString(data.id),
    type: readString(data.type),
    title: readString(data.title),
    document_id: data.document_id === null ? null : readString(data.document_id) || undefined,
    uri: data.uri === null ? null : readString(data.uri) || undefined,
    metadata: typeof data.metadata === 'object' && data.metadata !== null
      ? (data.metadata as Record<string, unknown>)
      : {},
  }
}

function normalizeDeckSpec(raw: unknown): DeckSpec {
  const data = typeof raw === 'object' && raw !== null ? (raw as Record<string, unknown>) : {}
  const meta = typeof data.meta === 'object' && data.meta !== null ? (data.meta as Record<string, unknown>) : {}
  const generation = typeof data.generation === 'object' && data.generation !== null
    ? (data.generation as Record<string, unknown>)
    : {}
  const evidenceReview = normalizeDeckEvidenceReview(generation.evidence_review)
  const generationCitationValidation = normalizeDeckCitationValidation(generation.citation_validation)
  const topLevelCitationValidation = normalizeDeckCitationValidation(data.citation_validation)
  return {
    version: readString(data.version),
    deck_id: readString(data.deck_id),
    status: readString(data.status),
    meta: {
      title: readString(meta.title),
      subtitle: readString(meta.subtitle),
      language: readString(meta.language),
      audience: readString(meta.audience),
      purpose: readString(meta.purpose),
      author: readString(meta.author),
      theme: meta.theme === 'midnight' || meta.theme === 'sunrise' ? meta.theme : 'default',
      created_at: readString(meta.created_at),
      session_id: readString(meta.session_id),
      source_mode: meta.source_mode === 'chat_only' ? 'chat_only' : 'kb_plus_chat',
      generator_panel_id: readString(meta.generator_panel_id),
      source_answer_group_id: readString(meta.source_answer_group_id) || undefined,
      source_panel_id: readString(meta.source_panel_id) || undefined,
    },
    generation: {
      source: generation.source === 'chat_only' ? 'chat_only' : 'kb_plus_chat',
      target_slide_count: readNumber(generation.target_slide_count),
      actual_slide_count: readNumber(generation.actual_slide_count),
      warnings: Array.isArray(generation.warnings)
        ? generation.warnings
            .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
            .map((item) => ({
              code: readString(item.code),
              message: readString(item.message),
            }))
        : [],
      evidence_coverage: normalizeDeckEvidenceCoverage(generation.evidence_coverage),
      evidence_review: evidenceReview,
      citation_validation: generationCitationValidation ?? evidenceReview?.citation_validation,
    },
    slides: Array.isArray(data.slides) ? data.slides.map(normalizeDeckSlide) : [],
    source_registry: Array.isArray(data.source_registry) ? data.source_registry.map(normalizeDeckSourceItem) : [],
    citation_validation: topLevelCitationValidation ?? generationCitationValidation ?? evidenceReview?.citation_validation,
  }
}

function normalizeClaimEvidenceSources(value: unknown): ClaimEvidenceSource[] {
  if (!Array.isArray(value)) return []
  return value
    .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    .map((item) => ({
      source_index: readNumber(item.source_index),
      title: readString(item.title),
      url: readString(item.url) || undefined,
      domain: readString(item.domain) || undefined,
      source_tier: readString(item.source_tier) || undefined,
      source_family: readString(item.source_family) || undefined,
      freshness_band: readString(item.freshness_band) || undefined,
      published_at: readString(item.published_at) || undefined,
      selection_reason: readString(item.selection_reason) || undefined,
      provider_caveat: readString(item.provider_caveat) || undefined,
    }))
}

function normalizeClaimEvidenceChains(value: unknown): ClaimEvidenceChain[] {
  if (!Array.isArray(value)) return []
  return value
    .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    .map((item) => ({
      claim_id: readString(item.claim_id),
      claim_text: readString(item.claim_text),
      facet: readString(item.facet) || undefined,
      claim_type: readString(item.claim_type) || undefined,
      date: readString(item.date) || undefined,
      status: readString(item.status) || 'unverified',
      evidence_strength: readString(item.evidence_strength) || 'low',
      verification_note: readString(item.verification_note) || undefined,
      candidate_sources: readStringArray(item.candidate_sources),
      supporting_source_count: readNumber(item.supporting_source_count),
      independent_source_families: readStringArray(item.independent_source_families),
      has_primary_source: item.has_primary_source === true,
      needs_attention: item.needs_attention === true,
      sources: normalizeClaimEvidenceSources(item.sources),
    }))
}

function normalizeClaimVerificationSummary(value: unknown): ClaimVerificationSummary | undefined {
  if (typeof value !== 'object' || value === null) return undefined
  const data = value as Record<string, unknown>
  const resolutionActions =
    typeof data.resolution_actions === 'object' && data.resolution_actions !== null
      ? Object.fromEntries(
          Object.entries(data.resolution_actions as Record<string, unknown>).map(([key, count]) => [
            key,
            readNumber(count),
          ]),
        )
      : {}

  return {
    total_claims: readNumber(data.total_claims),
    verified_claims: readNumber(data.verified_claims),
    partial_claims: readNumber(data.partial_claims),
    unverified_claims: readNumber(data.unverified_claims),
    high_strength_claims: readNumber(data.high_strength_claims),
    medium_strength_claims: readNumber(data.medium_strength_claims),
    low_strength_claims: readNumber(data.low_strength_claims),
    claims_needing_attention: readStringArray(data.claims_needing_attention),
    contradiction_count: readNumber(data.contradiction_count),
    resolution_actions: resolutionActions,
  }
}

function normalizeResearchCitationGraph(value: unknown): ResearchCitationGraph | undefined {
  const data = readOptionalRecord(value)
  if (!data) return undefined
  const nodes = readRecordCollection(data.nodes ?? data.vertices)
  const edges = readRecordCollection(data.edges ?? data.links)
  if (nodes.length === 0 && edges.length === 0) return undefined
  return { nodes, edges }
}

function normalizeResearchNavigationIndex(value: unknown): ResearchNavigationIndex | undefined {
  const data = readOptionalRecord(value)
  if (!data) return undefined
  const links = readRecordCollection(data.links)
  return {
    paragraph_to_claims: readStringArrayRecord(data.paragraph_to_claims),
    paragraph_to_sources: readStringArrayRecord(data.paragraph_to_sources),
    claim_to_paragraphs: readStringArrayRecord(data.claim_to_paragraphs),
    source_to_paragraphs: readStringArrayRecord(data.source_to_paragraphs),
    links,
  }
}

function normalizeResearchConflictSummary(value: unknown): ResearchConflictSummary | undefined {
  const data = readOptionalRecord(value)
  if (!data) {
    const conflicts = readRecordCollection(value)
    return conflicts.length > 0 ? { conflict_count: conflicts.length, conflicts } : undefined
  }
  const conflicts = readRecordCollection(data.conflicts ?? data.items ?? data.claim_conflicts)
  const conflictCount =
    readNumber(data.conflict_count) ||
    readNumber(data.conflicts_count) ||
    readNumber(data.total_conflicts) ||
    readNumber(data.contradiction_count) ||
    conflicts.length
  return {
    conflict_count: conflictCount,
    conflicts,
    details: data,
  }
}

function normalizeResearchConflictGroups(value: unknown): ResearchConflictGroup[] {
  return readRecordCollection(value).map((item, index) => ({
    group_id: readString(item.group_id) || `conflict-group-${index + 1}`,
    normalized_claim: readString(item.normalized_claim),
    normalized_source: readString(item.normalized_source),
    normalized_conflict_text: readString(item.normalized_conflict_text),
    conflict_text: readString(item.conflict_text),
    claim_ids: readStringArray(item.claim_ids),
    source_ids: readStringArray(item.source_ids),
    review_statuses: readStringArray(item.review_statuses),
    total: readNumber(item.total),
    archives: readRecordCollection(item.archives),
  }))
}

function normalizeResearchArchive(raw: unknown): ResearchArchive {
  const data = (raw ?? {}) as Record<string, unknown>
  const content = readOptionalRecord(data.content) ?? {}
  const previewClaims = Array.isArray(data.preview_claims) ? data.preview_claims : []
  const chains = normalizeClaimEvidenceChains(
    data.claim_evidence_chains ?? content.claim_evidence_chains ?? previewClaims,
  )
  const previewSources = Array.isArray(data.preview_sources)
    ? data.preview_sources
    : Array.isArray(data.sources)
      ? data.sources
      : []
  const paragraphCitations = readRecordCollection(
    readFirstField(data, content, [
      'paragraph_citations',
      'paragraphCitations',
      'paragraph_links',
      'paragraphLinks',
      'paragraph_citation_map',
      'paragraphCitationMap',
    ]),
  )
  const citationGraph = normalizeResearchCitationGraph(
    readFirstField(data, content, ['citation_graph', 'citationGraph', 'graph']),
  )
  const navigationIndex = normalizeResearchNavigationIndex(
    readFirstField(data, content, ['navigation_index', 'navigationIndex']),
  )
  const conflictSummary = normalizeResearchConflictSummary(
    readFirstField(data, content, ['conflict_summary', 'conflictSummary', 'conflicts']),
  )
  const sourceCount =
    readNumber(data.source_count) ||
    chains.reduce((total, chain) => total + (chain.sources.length || chain.supporting_source_count), 0) ||
    previewSources.length
  return {
    archive_id: readString(data.archive_id) || readString(data.artifact_id) || readString(data.id),
    title: readString(data.title) || 'Untitled research archive',
    session_id: readString(data.session_id) || undefined,
    task_id: readString(data.task_id) || undefined,
    artifact_id: readString(data.artifact_id) || undefined,
    claim_count: readNumber(data.claim_count) || chains.length,
    source_count: sourceCount,
    verification_summary: normalizeClaimVerificationSummary(
      data.verification_summary ?? data.claim_verification_summary ?? content.claim_verification_summary,
    ),
    claim_evidence_chains: chains,
    paragraph_citations: paragraphCitations,
    paragraph_claim_links: readRecordCollection(
      readFirstField(data, content, ['paragraph_claim_links', 'paragraphClaimLinks']),
    ),
    navigation_index: navigationIndex,
    citation_graph: citationGraph,
    conflict_summary: conflictSummary,
    conflict_review_resolutions: readRecordCollection(
      readFirstField(data, content, [
        'conflict_review_resolutions',
        'conflictReviewResolutions',
      ]),
    ),
    provider_capabilities: readOptionalRecord(
      readFirstField(data, content, ['provider_capabilities', 'providerCapabilities']),
    ),
    delivery_quality:
      typeof data.delivery_quality === 'object' && data.delivery_quality !== null
        ? (data.delivery_quality as Record<string, unknown>)
        : undefined,
    preview_claims: previewClaims.filter(
      (item): item is Record<string, unknown> => typeof item === 'object' && item !== null,
    ),
    preview_sources: previewSources.filter(
      (item): item is Record<string, unknown> => typeof item === 'object' && item !== null,
    ),
    created_at: readNumber(data.created_at) || undefined,
    updated_at: readNumber(data.updated_at) || undefined,
  }
}

function normalizeArtifact(raw: unknown): ArtifactRecord {
  const data = (raw ?? {}) as Record<string, unknown>
  const artifactType = data.artifact_type === 'deck' ? 'deck' : 'report'
  const rawContent =
    typeof data.content === 'object' && data.content !== null
      ? (data.content as Record<string, unknown>)
      : {}

  const content =
    artifactType === 'deck'
      ? {
          deck_id: typeof rawContent.deck_id === 'string' ? rawContent.deck_id : '',
          theme: typeof rawContent.theme === 'string' ? rawContent.theme : 'default',
          slide_count:
            typeof rawContent.slide_count === 'number'
              ? rawContent.slide_count
              : Number(rawContent.slide_count ?? 0) || 0,
          answer_group_id:
            typeof rawContent.answer_group_id === 'string' ? rawContent.answer_group_id : null,
          panel_id: typeof rawContent.panel_id === 'string' ? rawContent.panel_id : null,
          evidence_coverage: normalizeDeckEvidenceCoverage(rawContent.evidence_coverage),
          evidence_review: normalizeDeckEvidenceReview(rawContent.evidence_review),
          citation_validation: normalizeDeckCitationValidation(rawContent.citation_validation),
        }
      : {
          markdown: typeof rawContent.markdown === 'string' ? rawContent.markdown : '',
          qa_pairs: Array.isArray(rawContent.qa_pairs)
            ? rawContent.qa_pairs
                .filter(
                  (item): item is Record<string, unknown> =>
                    typeof item === 'object' && item !== null,
                )
                .map((item) => ({
                  question: typeof item.question === 'string' ? item.question : '',
                  answer: typeof item.answer === 'string' ? item.answer : '',
                }))
            : [],
          answer_group_id:
            typeof rawContent.answer_group_id === 'string' ? rawContent.answer_group_id : null,
          panel_id: typeof rawContent.panel_id === 'string' ? rawContent.panel_id : null,
          claim_evidence_chains: normalizeClaimEvidenceChains(rawContent.claim_evidence_chains),
          claim_verification_summary: normalizeClaimVerificationSummary(
            rawContent.claim_verification_summary,
          ),
        }

  return {
    artifact_id: typeof data.artifact_id === 'string' ? data.artifact_id : '',
    session_id: typeof data.session_id === 'string' ? data.session_id : '',
    artifact_type: artifactType,
    title: typeof data.title === 'string' ? data.title : 'Untitled Artifact',
    status: typeof data.status === 'string' ? data.status : 'ready',
    linked_resource_type:
      typeof data.linked_resource_type === 'string' ? data.linked_resource_type : null,
    linked_resource_id:
      typeof data.linked_resource_id === 'string' ? data.linked_resource_id : null,
    content,
    available_formats: Array.isArray(data.available_formats)
      ? data.available_formats.filter(
          (item): item is ArtifactExportFormat =>
            item === 'md' || item === 'docx' || item === 'xlsx' || item === 'pptx',
        )
      : artifactType === 'report'
        ? ['md', 'docx', 'xlsx', 'pptx']
        : ['pptx'],
    created_at:
      typeof data.created_at === 'number' ? data.created_at : Number(data.created_at ?? 0) || 0,
    updated_at:
      typeof data.updated_at === 'number' ? data.updated_at : Number(data.updated_at ?? 0) || 0,
  }
}

// ── Sessions ─────────────────────────────────

export async function getSessions(params?: {
  query?: string
  archived?: boolean
  favorite?: boolean
  tag?: string
  workspace_id?: string
}): Promise<Session[]> {
  const searchParams = new URLSearchParams()
  if (params?.query?.trim()) searchParams.set('query', params.query.trim())
  if (params?.archived !== undefined) searchParams.set('archived', String(params.archived))
  if (params?.favorite !== undefined) searchParams.set('favorite', String(params.favorite))
  if (params?.tag?.trim()) searchParams.set('tag', params.tag.trim())
  if (params?.workspace_id?.trim()) searchParams.set('workspace_id', params.workspace_id.trim())

  const query = searchParams.toString()
  const res = await fetch(`${BASE}/sessions${query ? `?${query}` : ''}`)
  const data = await res.json()
  return (data.sessions as Session[]).map((session) => normalizeSession(session))
}

export async function getWorkspaces(): Promise<{ workspaces: Workspace[]; active_workspace_id: string | null }> {
  const res = await fetch(`${BASE}/workspaces`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json() as {
    workspaces?: Workspace[]
    active_workspace_id?: string | null
  }
  return {
    workspaces: (data.workspaces ?? []).map((workspace) => normalizeWorkspace(workspace)),
    active_workspace_id: typeof data.active_workspace_id === 'string' && data.active_workspace_id.trim()
      ? data.active_workspace_id
      : null,
  }
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
      : ['knowledge-base', 'web-search'],
  }
}

function normalizeMcpMarketplace(value: unknown): McpMarketplace | undefined {
  const data = readRecord(value)
  const rawSummary = readRecord(data.summary)
  const rawCategories = Array.isArray(data.categories) ? data.categories : []
  if (Object.keys(rawSummary).length === 0 && rawCategories.length === 0) return undefined
  return {
    summary: {
      total: readNumber(rawSummary.total),
      builtin: readNumber(rawSummary.builtin),
      custom: readNumber(rawSummary.custom),
      enabled: readNumber(rawSummary.enabled),
      healthy: readNumber(rawSummary.healthy),
      requires_approval: readNumber(rawSummary.requires_approval),
      categories: readNumber(rawSummary.categories),
    },
    categories: rawCategories
      .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
      .map((item) => ({
        id: readString(item.id),
        label: readString(item.label),
        total: readNumber(item.total),
        enabled: readNumber(item.enabled),
        healthy: readNumber(item.healthy),
        requires_approval: readNumber(item.requires_approval),
        connectors: readStringArray(item.connectors),
      })),
  }
}

function normalizeMcpConfigPayload(data: Partial<McpConfigResponse>): McpConfigResponse {
  const persistence =
    typeof data.persistence === 'object' && data.persistence !== null
      ? data.persistence
      : { enabled: false, config_key: '' }
  const servers = readRecord(data.servers) as Record<string, Record<string, unknown>>
  const config = readRecord(data.config)
  const marketplace = normalizeMcpMarketplace(data.marketplace)
  return {
    connectors: Array.isArray(data.connectors) ? data.connectors : [],
    config: Object.keys(config).length > 0 ? config : { servers },
    servers,
    default_enabled: readStringArray(data.default_enabled),
    persistence: {
      enabled: persistence.enabled === true,
      config_key: readString(persistence.config_key) || readString(data.path),
    },
    sensitive_fields_redacted:
      data.sensitive_fields_redacted === true ||
      (readRecord(data.persistence).sensitive_fields_redacted === true),
    source: readString(data.source),
    path: readString(data.path),
    total: readNumber(data.total),
    marketplace,
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

function normalizeMcpApprovalsPayload(data: Partial<McpConnectorApprovalsResponse>): McpConnectorApprovalsResponse {
  const approved = readStringArray(data.approved_connectors)
  const env = readStringArray(data.env_connectors)
  const runtime = readStringArray(data.runtime_connectors)
  const persisted = readStringArray(data.persisted_connectors)
  const sources =
    typeof data.sources === 'object' && data.sources !== null
      ? Object.fromEntries(
          Object.entries(data.sources).map(([name, value]) => [name, readStringArray(value)]),
        )
      : {}
  const persistence =
    typeof data.persistence === 'object' && data.persistence !== null
      ? data.persistence
      : { enabled: false, config_key: '' }

  return {
    approved_connectors: approved,
    env_connectors: env,
    runtime_connectors: runtime,
    persisted_connectors: persisted,
    sources,
    persistence: {
      enabled: persistence.enabled === true,
      config_key: readString(persistence.config_key),
    },
    total: readNumber(data.total ?? approved.length),
    connector: data.connector,
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

function normalizeIntegratorConnector(value: unknown): IntegratorConnector {
  const record = readRecord(value)
  return {
    id: readString(record.id) || undefined,
    type: readString(record.type) || 'webhook',
    name: readString(record.name) || undefined,
    description: readString(record.description) || undefined,
    enabled: record.enabled !== false,
    approved: record.approved === true,
    settings: normalizeIntegratorSafeSettings(record.settings),
  }
}

function normalizeIntegratorConnectorsResponse(
  data: Partial<IntegratorConnectorsResponse>,
): IntegratorConnectorsResponse {
  const connectors = Array.isArray(data.connectors)
    ? data.connectors.map((item) => normalizeIntegratorConnector(item))
    : []
  const persistence = readRecord(data.persistence)
  return {
    connectors,
    total: readNumber(data.total ?? connectors.length),
    supported_types: readStringArray(data.supported_types),
    persistence: {
      enabled: persistence.enabled === true,
      config_key: readString(persistence.config_key),
      sensitive_fields_redacted: persistence.sensitive_fields_redacted === true,
    },
  }
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

function normalizeIntegratorConnectorTestResult(
  data: Partial<IntegratorConnectorTestResult>,
): IntegratorConnectorTestResult {
  const summary = readRecord(data.summary)
  return {
    ok: data.ok === true,
    status: readString(data.status) || 'unknown',
    dry_run: data.dry_run !== false,
    executed: data.executed === true,
    connector: normalizeIntegratorConnector(data.connector),
    checks: normalizeIntegratorConnectorChecks(data.checks),
    summary: {
      check_count: readNumber(summary.check_count),
      failed_count: readNumber(summary.failed_count),
      blocking_failure_count: readNumber(summary.blocking_failure_count),
      warning_count: readNumber(summary.warning_count),
    },
  }
}

function normalizeIntegratorAuditEvent(value: unknown): IntegratorAuditEvent {
  const record = readRecord(value)
  const connector = readRecord(record.connector)
  const endpoint = readRecord(record.endpoint)
  const response = readRecord(record.response)
  const details = readRecord(record.details)
  return {
    timestamp: readNumber(record.timestamp),
    action: readString(record.action || record.event),
    result: readString(record.result || record.status),
    connector_id: readString(record.connector_id || connector.id),
    connector_type: readString(record.connector_type || connector.type),
    actor: readString(record.actor || record.user_id),
    request_id: readString(record.request_id || record.id),
    details: {
      ...details,
      connector_name: readString(connector.name || details.connector_name),
      endpoint_host: readString(endpoint.host || details.endpoint_host),
      endpoint_fingerprint: readString(endpoint.fingerprint || details.endpoint_fingerprint),
      status_code: readNumber(response.status_code || details.status_code),
    },
  }
}

function normalizeIntegratorAuditEventsResponse(
  data: Partial<IntegratorAuditEventsResponse>,
): IntegratorAuditEventsResponse {
  const events = Array.isArray(data.events)
    ? data.events.map((item) => normalizeIntegratorAuditEvent(item))
    : []
  return {
    events,
    total: readNumber(data.total ?? events.length),
    limit: readNumber(data.limit ?? events.length),
  }
}

function normalizeIntegratorConnectorChecks(value: unknown): IntegratorConnectorTestCheck[] {
  return Array.isArray(value)
    ? value.map((item) => {
        const check = readRecord(item)
        return {
          name: readString(check.name),
          ok: check.ok === true,
          severity: readString(check.severity),
          message: readString(check.message),
        }
      })
    : []
}

function normalizeIntegratorCredentialsRotationResponse(
  data: Partial<IntegratorConnectorCredentialsRotationResponse>,
): IntegratorConnectorCredentialsRotationResponse {
  const summary = readRecord(data.summary)
  const rotatedFields = readStringArray(data.rotated_fields)
  const preservedFields = readStringArray(data.preserved_fields)
  return {
    ok: data.ok !== false,
    status: readString(data.status) || 'rotated',
    connector: normalizeIntegratorConnector(data.connector),
    rotated_fields: rotatedFields,
    preserved_fields: preservedFields,
    summary: {
      rotated_count: readNumber(summary.rotated_count ?? rotatedFields.length),
      preserved_count: readNumber(summary.preserved_count ?? preservedFields.length),
    },
  }
}

function normalizeIntegratorConnectorProbeResponse(
  data: Partial<IntegratorConnectorProbeResponse>,
): IntegratorConnectorProbeResponse {
  const summary = readRecord(data.summary)
  const probe = readRecord(data.probe)
  const timeoutSeconds = probe.timeout_seconds === undefined
    ? undefined
    : readNumber(probe.timeout_seconds)
  return {
    ok: data.ok === true,
    status: readString(data.status) || 'unknown',
    dry_run: data.dry_run !== false,
    executed: data.executed === true,
    connector: normalizeIntegratorConnector(data.connector),
    checks: normalizeIntegratorConnectorChecks(data.checks),
    probe: {
      mode: readString(probe.mode) || readString(summary.probe_mode) || (data.dry_run === false ? 'external' : 'static'),
      outbound_request_sent: probe.outbound_request_sent === true,
      ...(timeoutSeconds !== undefined ? { timeout_seconds: timeoutSeconds } : {}),
      ...(Object.keys(readRecord(probe.endpoint)).length > 0 ? { endpoint: readRecord(probe.endpoint) } : {}),
      ...(Object.keys(readRecord(probe.response)).length > 0 ? { response: readRecord(probe.response) } : {}),
    },
    summary: {
      check_count: readNumber(summary.check_count),
      failed_count: readNumber(summary.failed_count),
      blocking_failure_count: readNumber(summary.blocking_failure_count),
      warning_count: readNumber(summary.warning_count),
      probe_mode: readString(summary.probe_mode) || undefined,
    },
  }
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

function normalizeIntegratorSchedule(value: unknown): IntegratorSchedule {
  const record = readRecord(value)
  const rawLastRunAt = record.last_run_at
  const rawNextRunAt = record.next_run_at
    return {
      schedule_id: readString(record.schedule_id || record.id) || undefined,
      name: readString(record.name) || 'Integrator schedule',
      connector_id: readString(record.connector_id),
      cron: readString(record.cron || record.cron_expression) || '0 * * * *',
      timezone: readString(record.timezone) || 'UTC',
      interval_minutes: readNumber(record.interval_minutes) || 60,
      enabled: record.enabled !== false,
      settings: readRecord(record.settings),
      last_run_at: rawLastRunAt === null ? null : readNumber(rawLastRunAt),
      next_run_at: rawNextRunAt === null ? null : readNumber(rawNextRunAt),
    }
}

function normalizeIntegratorSchedulesResponse(
  data: Partial<IntegratorSchedulesResponse>,
): IntegratorSchedulesResponse {
  const schedules = Array.isArray(data.schedules)
    ? data.schedules.map((item) => normalizeIntegratorSchedule(item))
    : []
  const persistence = readRecord(data.persistence)
  const scheduler = readRecord(data.scheduler)
  return {
    schedules,
    total: readNumber(data.total ?? schedules.length),
    persistence: {
      enabled: persistence.enabled === true,
      config_key: readString(persistence.config_key),
      sensitive_fields_redacted: persistence.sensitive_fields_redacted === true,
    },
    scheduler: {
      mode: readString(scheduler.mode) || 'unknown',
      automatic_dispatch: scheduler.automatic_dispatch === true,
      manual_trigger_supported: scheduler.manual_trigger_supported === true,
    },
  }
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

function readRecord(value: unknown): Record<string, unknown> {
  return typeof value === 'object' && value !== null ? value as Record<string, unknown> : {}
}

const INTEGRATOR_SENSITIVE_SETTING_PATTERN = /(url|token|secret|client_secret|password|credential|authorization|auth|key)/i
const INTEGRATOR_REDACTED_VALUE = '***redacted***'

function normalizeIntegratorSafeSettings(value: unknown): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(readRecord(value)).map(([key, item]) => {
      if (INTEGRATOR_SENSITIVE_SETTING_PATTERN.test(key)) {
        return [key, INTEGRATOR_REDACTED_VALUE]
      }
      if (item && typeof item === 'object' && !Array.isArray(item)) {
        return [key, normalizeIntegratorSafeSettings(item)]
      }
      return [key, item]
    }),
  )
}

function readNumberRecord(value: unknown): Record<string, number> {
  const record = readRecord(value)
  return Object.fromEntries(
    Object.entries(record).map(([key, item]) => [key, readNumber(item)]),
  )
}

function normalizeMcpRuntimeHealthSummary(value: unknown): McpRuntimeHealthSummary {
  const summary = readRecord(value)
  return {
    total: readNumber(summary.total),
    healthy: readNumber(summary.healthy),
    unhealthy: readNumber(summary.unhealthy),
    tool_count: readNumber(summary.tool_count),
    status_counts: readNumberRecord(summary.status_counts),
    alert_count: readNumber(summary.alert_count),
    unhealthy_connectors: readStringArray(summary.unhealthy_connectors),
    slow_connectors: readStringArray(summary.slow_connectors),
  }
}

function normalizeMcpRuntimeHealthHistoryServer(value: unknown): McpRuntimeHealthHistoryServer {
  const server = readRecord(value)
  return {
    name: readString(server.name),
    status: readString(server.status) || 'unknown',
    healthy: server.healthy === true,
    tool_count: readNumber(server.tool_count),
    duration_ms: readNumber(server.duration_ms),
    error: typeof server.error === 'string' && server.error.trim() ? server.error : null,
  }
}

function normalizeMcpRuntimeHealthHistoryItem(value: unknown): McpRuntimeHealthHistoryItem {
  const item = readRecord(value)
  return {
    timestamp: readNumber(item.timestamp),
    status: readString(item.status) || 'unknown',
    summary: normalizeMcpRuntimeHealthSummary(item.summary),
    servers: Array.isArray(item.servers)
      ? item.servers.map(normalizeMcpRuntimeHealthHistoryServer)
      : [],
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

export async function createWorkspace(payload: {
  name: string
  description?: string
  color?: Workspace['color']
  activate?: boolean
  preset?: Partial<WorkspacePreset>
}): Promise<Workspace> {
  const res = await fetch(`${BASE}/workspaces`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: payload.name,
      description: payload.description ?? '',
      color: payload.color ?? 'blue',
      activate: payload.activate ?? true,
      preset: payload.preset
        ? {
            default_panels: payload.preset.default_panels ?? [],
            tool_config: payload.preset.tool_config ?? {
              web_search_enabled: false,
              knowledge_base_enabled: true,
              mcp_servers_enabled: ['knowledge-base', 'web-search'],
            },
            output_preset: payload.preset.output_preset ?? {
              deck_theme: 'default',
              target_slide_count: 8,
            },
          }
        : undefined,
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json() as { workspace: Workspace }
  return normalizeWorkspace(data.workspace)
}

export async function updateWorkspace(
  workspaceId: string,
  patch: {
    name?: string
    description?: string
    color?: Workspace['color']
    preset?: Partial<WorkspacePreset>
  },
): Promise<Workspace> {
  const res = await fetch(`${BASE}/workspaces/${encodeURIComponent(workspaceId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      ...patch,
      preset: patch.preset
        ? {
            default_panels: patch.preset.default_panels ?? [],
            tool_config: patch.preset.tool_config ?? {
              web_search_enabled: false,
              knowledge_base_enabled: true,
              mcp_servers_enabled: ['knowledge-base', 'web-search'],
            },
            output_preset: patch.preset.output_preset ?? {
              deck_theme: 'default',
              target_slide_count: 8,
            },
          }
        : undefined,
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json() as { workspace: Workspace }
  return normalizeWorkspace(data.workspace)
}

export async function activateWorkspace(workspaceId: string): Promise<Workspace> {
  const res = await fetch(`${BASE}/workspaces/${encodeURIComponent(workspaceId)}/activate`, {
    method: 'POST',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json() as { workspace: Workspace }
  return normalizeWorkspace(data.workspace)
}

export async function deleteWorkspace(
  workspaceId: string,
  options?: { target_workspace_id?: string },
): Promise<{
  deleted_workspace_id: string
  target_workspace_id: string
  target_workspace?: Workspace
}> {
  const searchParams = new URLSearchParams()
  if (options?.target_workspace_id?.trim()) {
    searchParams.set('target_workspace_id', options.target_workspace_id.trim())
  }
  const suffix = searchParams.toString() ? `?${searchParams.toString()}` : ''
  const res = await fetch(`${BASE}/workspaces/${encodeURIComponent(workspaceId)}${suffix}`, {
    method: 'DELETE',
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    deleted_workspace_id?: string
    target_workspace_id?: string
    target_workspace?: Workspace
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  if (!data.deleted_workspace_id || !data.target_workspace_id) {
    throw new Error('删除工作区返回的数据无效。')
  }
  return {
    deleted_workspace_id: data.deleted_workspace_id,
    target_workspace_id: data.target_workspace_id,
    target_workspace: data.target_workspace
      ? normalizeWorkspace(data.target_workspace)
      : undefined,
  }
}

export async function createSession(
  title = '',
  options?: { workspace_id?: string },
): Promise<{ session_id: string; title: string; workspace_id?: string }> {
  const res = await fetch(`${BASE}/sessions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      title,
      workspace_id: options?.workspace_id,
    }),
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    session_id?: string
    title?: string
    workspace_id?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  if (!data.session_id || typeof data.session_id !== 'string') {
    throw new Error('创建会话返回的数据无效。')
  }
  return {
    session_id: data.session_id,
    title: typeof data.title === 'string' && data.title.trim() ? data.title : '新建对话',
    workspace_id:
      typeof data.workspace_id === 'string' && data.workspace_id.trim()
        ? data.workspace_id.trim()
        : undefined,
  }
}

export async function deleteSession(sessionId: string): Promise<void> {
  await fetch(`${BASE}/sessions/${sessionId}`, { method: 'DELETE' })
}

export async function getBookmarks(params?: {
  session_id?: string
}): Promise<Bookmark[]> {
  const searchParams = new URLSearchParams()
  if (params?.session_id?.trim()) searchParams.set('session_id', params.session_id.trim())
  const query = searchParams.toString()
  const res = await fetch(`${BASE}/bookmarks${query ? `?${query}` : ''}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json() as {
    bookmarks?: Array<Partial<Bookmark> & { id: string }>
  }
  return (data.bookmarks ?? []).map((bookmark) => normalizeBookmark(bookmark))
}

export async function createBookmark(payload: {
  session_id: string
  role: 'user' | 'assistant'
  message_id?: number
  panel_id?: string
  answer_group_id?: string
  content?: string
  model_id?: string
  session_title?: string
}): Promise<Bookmark> {
  const res = await fetch(`${BASE}/bookmarks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: payload.session_id,
      role: payload.role,
      message_id: payload.message_id,
      panel_id: payload.panel_id ?? '',
      answer_group_id: payload.answer_group_id ?? '',
      content: payload.content ?? '',
      model_id: payload.model_id ?? '',
      session_title: payload.session_title ?? '',
    }),
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    bookmark?: Partial<Bookmark> & { id: string }
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  if (!data.bookmark) {
    throw new Error('创建书签返回的数据无效。')
  }
  return normalizeBookmark(data.bookmark)
}

export async function deleteBookmark(bookmarkId: string): Promise<void> {
  const res = await fetch(`${BASE}/bookmarks/${encodeURIComponent(bookmarkId)}`, {
    method: 'DELETE',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
}

export async function updateSessionMeta(
  sessionId: string,
  patch: {
    title?: string
    is_archived?: boolean
    is_favorite?: boolean
    is_pinned?: boolean
    tags?: string[]
    workspace_id?: string
  },
): Promise<Session> {
  const res = await fetch(`${BASE}/sessions/${encodeURIComponent(sessionId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json()
  return normalizeSession(data.session as Session)
}

export async function reorderSessions(
  sessionIds: string[],
  options?: {
    workspace_id?: string
  },
): Promise<Session[]> {
  const normalizedIds = sessionIds
    .map((id) => id.trim())
    .filter((id) => id.length > 0)

  if (normalizedIds.length < 2) {
    throw new Error('至少需要两个对话才能重新排序。')
  }

  const res = await fetch(`${BASE}/sessions/reorder`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_ids: normalizedIds,
      workspace_id: options?.workspace_id,
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json() as {
    sessions?: Session[]
  }
  return (data.sessions ?? []).map((session) => normalizeSession(session))
}

export async function getSessionMessages(sessionId: string): Promise<MessagesResponse> {
  const res = await fetch(`${BASE}/sessions/${sessionId}/messages`)
  const data = await res.json()
  return {
    messages: data.messages as Message[],
    context_limit: data.context_limit ?? 16,
    total_messages: data.total_messages ?? (data.messages as Message[]).length,
    panels: (data.panels ?? []) as SessionPanel[],
    panel_messages: (data.panel_messages ?? {}) as Record<string, Message[]>,
  }
}

export async function importSessionMessages(
  sessionId: string,
  payload: ImportSessionMessagesPayload,
): Promise<MessagesResponse> {
  const res = await fetch(`${BASE}/sessions/${encodeURIComponent(sessionId)}/messages/import`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    messages?: Message[]
    context_limit?: number
    total_messages?: number
    panels?: SessionPanel[]
    panel_messages?: Record<string, Message[]>
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return {
    messages: (data.messages ?? []) as Message[],
    context_limit: data.context_limit ?? 16,
    total_messages: data.total_messages ?? (data.messages ?? []).length,
    panels: (data.panels ?? []) as SessionPanel[],
    panel_messages: (data.panel_messages ?? {}) as Record<string, Message[]>,
  }
}

export interface GeneratedReport {
  markdown: string
  title: string
  artifact_id?: string
}

export interface ReportScopeOptions {
  answer_group_id?: string
  panel_id?: string
}

export async function generateSessionReport(
  sessionId: string,
  options?: ReportScopeOptions,
): Promise<GeneratedReport> {
  const res = await fetch(`${BASE}/reports/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      answer_group_id: options?.answer_group_id,
      panel_id: options?.panel_id,
    }),
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    markdown?: string
    title?: string
    artifact_id?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  if (typeof data.markdown !== 'string' || typeof data.title !== 'string') {
    throw new Error('报告生成返回的数据无效。')
  }
  return {
    markdown: data.markdown,
    title: data.title,
    artifact_id: typeof data.artifact_id === 'string' ? data.artifact_id : undefined,
  }
}

export async function getSessionArtifacts(
  sessionId: string,
  options?: { artifact_type?: ArtifactType },
): Promise<ArtifactRecord[]> {
  const params = new URLSearchParams()
  if (options?.artifact_type) params.set('artifact_type', options.artifact_type)
  const query = params.toString()
  const res = await fetch(
    `${BASE}/sessions/${encodeURIComponent(sessionId)}/artifacts${query ? `?${query}` : ''}`,
  )
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    artifacts?: unknown[]
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return Array.isArray(data.artifacts) ? data.artifacts.map((item) => normalizeArtifact(item)) : []
}

export async function getArtifacts(options?: { artifact_type?: ArtifactType; limit?: number }): Promise<ArtifactRecord[]> {
  const params = new URLSearchParams()
  if (options?.artifact_type) params.set('artifact_type', options.artifact_type)
  if (typeof options?.limit === 'number' && Number.isFinite(options.limit)) {
    params.set('limit', String(Math.max(1, Math.min(500, Math.floor(options.limit)))))
  }
  const query = params.toString()
  const res = await fetch(`${BASE}/artifacts${query ? `?${query}` : ''}`)
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    artifacts?: unknown[]
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return Array.isArray(data.artifacts) ? data.artifacts.map((item) => normalizeArtifact(item)) : []
}

export async function getResearchArchiveList(options?: {
  q?: string
  session_id?: string
  task_id?: string
  limit?: number
}): Promise<ResearchArchiveListResponse> {
  const params = new URLSearchParams()
  if (options?.q?.trim()) params.set('q', options.q.trim())
  if (options?.session_id?.trim()) params.set('session_id', options.session_id.trim())
  if (options?.task_id?.trim()) params.set('task_id', options.task_id.trim())
  if (typeof options?.limit === 'number' && Number.isFinite(options.limit)) {
    params.set('limit', String(Math.max(1, Math.min(100, Math.floor(options.limit)))))
  }
  const query = params.toString()
  const res = await authFetch(`/research/archives${query ? `?${query}` : ''}`)
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    archives?: unknown[]
    items?: unknown[]
    conflict_groups?: unknown[]
    total?: unknown
    limit?: unknown
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  const archives = Array.isArray(data.archives) ? data.archives : data.items
  return {
    archives: Array.isArray(archives) ? archives.map((item) => normalizeResearchArchive(item)) : [],
    conflict_groups: normalizeResearchConflictGroups(data.conflict_groups),
    total: readNumber(data.total),
    limit: readNumber(data.limit),
  }
}

export async function getResearchArchives(options?: {
  q?: string
  session_id?: string
  task_id?: string
  limit?: number
}): Promise<ResearchArchive[]> {
  const payload = await getResearchArchiveList(options)
  return payload.archives
}

export async function upsertResearchConflictResolution(
  artifactId: string,
  payload: ResearchConflictResolutionPayload,
): Promise<ResearchArchive> {
  const res = await authFetch(
    `/research/archives/${encodeURIComponent(artifactId)}/conflict-resolutions`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    archive?: unknown
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return normalizeResearchArchive(data.archive)
}

export async function getArtifact(artifactId: string): Promise<ArtifactRecord> {
  const res = await fetch(`${BASE}/artifacts/${encodeURIComponent(artifactId)}`)
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return normalizeArtifact(data)
}

export async function exportArtifact(
  artifactId: string,
  format: ArtifactExportFormat,
): Promise<Blob> {
  const res = await fetch(
    `${BASE}/artifacts/${encodeURIComponent(artifactId)}/export?format=${encodeURIComponent(format)}`,
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.blob()
}

export async function setMessageFeedback(
  sessionId: string,
  payload: {
    value: MessageFeedbackValue
    message_id?: number
    panel_id?: string
    answer_group_id?: string
  },
): Promise<{
  message_id: number
  panel_id: string
  answer_group_id: string
  feedback_value: MessageFeedbackValue
}> {
  const res = await fetch(`${BASE}/sessions/${encodeURIComponent(sessionId)}/messages/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      value: payload.value,
      message_id: payload.message_id,
      panel_id: payload.panel_id ?? '',
      answer_group_id: payload.answer_group_id ?? '',
    }),
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    feedback?: {
      message_id: number
      panel_id: string
      answer_group_id: string
      feedback_value: MessageFeedbackValue
    }
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  if (!data.feedback) {
    throw new Error('消息反馈返回的数据无效。')
  }
  return data.feedback
}

export async function truncateSessionMessagesFromAnswerGroup(
  sessionId: string,
  payload: {
    answer_group_id: string
    content: string
    images?: ChatImage[]
    files?: ChatFile[]
  },
): Promise<{
  session_id: string
  answer_group_id: string
  anchor_message_id: number
  deleted_count: number
}> {
  const res = await fetch(`${BASE}/sessions/${encodeURIComponent(sessionId)}/messages/truncate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      answer_group_id: payload.answer_group_id,
      content: payload.content,
      images: payload.images ?? [],
      files: payload.files ?? [],
    }),
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    result?: {
      session_id: string
      answer_group_id: string
      anchor_message_id: number
      deleted_count: number
    }
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  if (!data.result) {
    throw new Error('截断请求返回的数据无效。')
  }
  return data.result
}

const normalizeRetrievalSourceText = (value: unknown): string =>
  String(value ?? '')
    .trim()
    .replace(/\s+/g, ' ')

export function buildRetrievalSourceKey(source: SourceItem): string {
  const normalizedType = normalizeRetrievalSourceText(source.type).toLowerCase()
  const normalizedTitle = normalizeRetrievalSourceText(source.title)
  const normalizedUrl = normalizeRetrievalSourceText(source.url)
  const normalizedSnippet = normalizeRetrievalSourceText(source.snippet).slice(0, 200)
  const normalizedIndex = source.index === undefined || source.index === null
    ? ''
    : normalizeRetrievalSourceText(source.index)
  return [
    normalizedType,
    normalizedTitle,
    normalizedUrl,
    normalizedSnippet,
    normalizedIndex,
  ].join('||')
}

export async function setRetrievalFeedback(
  sessionId: string,
  payload: {
    panel_id: string
    answer_group_id: string
    source: SourceItem
    value: RetrievalFeedbackValue
  },
): Promise<{
  source_key: string
  feedback_value: RetrievalFeedbackValue
  updated_at: number
}> {
  const res = await fetch(`${BASE}/sessions/${encodeURIComponent(sessionId)}/retrieval-feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    feedback?: {
      source_key: string
      feedback_value: RetrievalFeedbackValue
      updated_at: number
    }
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  if (!data.feedback) {
    throw new Error('检索反馈返回的数据无效。')
  }
  return data.feedback
}

export async function getRetrievalFeedback(
  sessionId: string,
  panelId: string,
  answerGroupId: string,
): Promise<Array<{
  source_key: string
  feedback_value: RetrievalFeedbackValue
  updated_at: number
}>> {
  const params = new URLSearchParams({
    panel_id: panelId,
    answer_group_id: answerGroupId,
  })
  const res = await fetch(`${BASE}/sessions/${encodeURIComponent(sessionId)}/retrieval-feedback?${params.toString()}`)
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    feedback?: Array<{
      source_key: string
      feedback_value: RetrievalFeedbackValue
      updated_at: number
    }>
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return data.feedback ?? []
}

export async function getSessionMemory(
  sessionId: string,
  kind?: SessionMemoryKind,
): Promise<SessionMemory[]> {
  const query = kind ? `?kind=${encodeURIComponent(kind)}` : ''
  const res = await fetch(`${BASE}/sessions/${encodeURIComponent(sessionId)}/memory${query}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json() as { memories?: SessionMemory[] }
  return data.memories ?? []
}

export async function pinSessionMemory(
  sessionId: string,
  payload: {
    content: string
    kind?: SessionMemoryKind
  },
): Promise<{ created: boolean; memory: SessionMemory }> {
  const res = await fetch(`${BASE}/sessions/${encodeURIComponent(sessionId)}/memory/pin`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      content: payload.content,
      kind: payload.kind ?? 'fact',
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json() as { created: boolean; memory: SessionMemory }
  return {
    created: data.created,
    memory: data.memory,
  }
}

export async function deleteSessionMemory(
  sessionId: string,
  memoryId: string,
): Promise<void> {
  const res = await fetch(
    `${BASE}/sessions/${encodeURIComponent(sessionId)}/memory/${encodeURIComponent(memoryId)}`,
    { method: 'DELETE' },
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
}

export async function updateSessionMemory(
  sessionId: string,
  memoryId: string,
  payload: {
    content?: string
    kind?: SessionMemoryKind
  },
): Promise<SessionMemory> {
  const body: {
    content?: string
    kind?: SessionMemoryKind
  } = {}
  if (typeof payload.content === 'string') body.content = payload.content
  if (payload.kind) body.kind = payload.kind

  const res = await fetch(
    `${BASE}/sessions/${encodeURIComponent(sessionId)}/memory/${encodeURIComponent(memoryId)}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    },
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json() as { memory: SessionMemory }
  return data.memory
}

export async function summarizeSessionMemory(
  sessionId: string,
  options?: { force?: boolean },
): Promise<{ created: boolean; memory: SessionMemory; reason?: string }> {
  const query = options?.force ? '?force=true' : ''
  const res = await fetch(
    `${BASE}/sessions/${encodeURIComponent(sessionId)}/memory/summarize${query}`,
    { method: 'POST' },
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json() as {
    created: boolean
    memory: SessionMemory
    reason?: string
  }
  return {
    created: data.created,
    memory: data.memory,
    reason: data.reason,
  }
}

export async function getSessionAttachments(
  sessionId: string,
  vectorStorePath?: string,
  workspaceId?: string,
): Promise<SessionAttachmentsResponse> {
  const searchParams = new URLSearchParams()
  if (vectorStorePath?.trim()) searchParams.set('vector_store_path', vectorStorePath.trim())
  if (workspaceId?.trim()) searchParams.set('workspace_id', workspaceId.trim())
  const query = searchParams.toString() ? `?${searchParams.toString()}` : ''
  const res = await fetch(`${BASE}/sessions/${sessionId}/attachments${query}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json()
  return {
    session_id: data.session_id as string,
    attachments: (data.attachments ?? []) as SessionAttachment[],
    summary: (data.summary ?? {
      total_attachments: 0,
      file_count: 0,
      image_count: 0,
      text_ready_count: 0,
      reusable_count: 0,
      total_size_bytes: 0,
    }) as SessionAttachmentSummary,
    current_vector_store_path: (data.current_vector_store_path as string | undefined) ?? '',
  }
}

export async function promoteSessionAttachmentToKnowledgeBase(
  sessionId: string,
  attachmentId: string,
  vectorStorePath?: string,
  workspaceId?: string,
): Promise<TaskRecord> {
  const searchParams = new URLSearchParams()
  if (vectorStorePath?.trim()) searchParams.set('vector_store_path', vectorStorePath.trim())
  if (workspaceId?.trim()) searchParams.set('workspace_id', workspaceId.trim())
  const query = searchParams.toString() ? `?${searchParams.toString()}` : ''
  const res = await fetch(
    `${BASE}/sessions/${encodeURIComponent(sessionId)}/attachments/${encodeURIComponent(attachmentId)}/promote${query}`,
    { method: 'POST' },
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json() as Promise<TaskRecord>
}

export async function clearSessionMessages(sessionId: string): Promise<void> {
  await fetch(`${BASE}/sessions/${sessionId}/messages`, { method: 'DELETE' })
}

export async function promotePanelAnswer(
  sessionId: string,
  answerGroupId: string,
  panelId: string,
): Promise<PromoteAnswerResponse> {
  const res = await fetch(
    `${BASE}/sessions/${encodeURIComponent(sessionId)}/answer-groups/${encodeURIComponent(answerGroupId)}/promote?panel_id=${encodeURIComponent(panelId)}`,
    { method: 'POST' },
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json()
}

export async function getAnswerGroupReview(
  sessionId: string,
  answerGroupId: string,
): Promise<AnswerGroupReviewResponse> {
  const res = await fetch(
    `${BASE}/sessions/${encodeURIComponent(sessionId)}/answer-groups/${encodeURIComponent(answerGroupId)}/review`,
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json() as Promise<AnswerGroupReviewResponse>
}

export async function promoteRecommendedAnswerGroup(
  sessionId: string,
  answerGroupId: string,
): Promise<PromoteAnswerResponse> {
  const res = await fetch(
    `${BASE}/sessions/${encodeURIComponent(sessionId)}/answer-groups/${encodeURIComponent(answerGroupId)}/promote/recommended`,
    { method: 'POST' },
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json() as Promise<PromoteAnswerResponse>
}

// ── Chat ─────────────────────────────────────

async function readSSEStream(
  res: Response,
  onChunk: (chunk: SSEChunk) => void,
  onDone: () => void,
): Promise<void> {
  if (!res.body) {
    throw new Error('后端返回了空响应。')
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const chunk = JSON.parse(line.slice(6)) as SSEChunk
          if (chunk.type === 'all_done') {
            onDone()
          } else {
            onChunk(chunk)
          }
        } catch {
          // skip malformed
        }
      }
    }
  }
}

export function streamChat(
  sessionId: string,
  message: string,
  models: ModelConfig[],
  webSearchEnabled: boolean,
  knowledgeBaseEnabled: boolean,
  enabledMcpServers: string[],
  images: ChatImage[],
  files: ChatFile[],
  answerGroupId: string,
  onChunk: (chunk: SSEChunk) => void,
  onDone: () => void,
  onError: (err: string) => void,
): AbortController {
  const controller = new AbortController()

  const run = async () => {
    try {
      const res = await fetch(`${BASE}/chat/parallel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message,
          images,
          files,
          models,
          web_search_enabled: webSearchEnabled,
          knowledge_base_enabled: knowledgeBaseEnabled,
          enabled_mcp_servers: enabledMcpServers,
          answer_group_id: answerGroupId,
        }),
        signal: controller.signal,
      })

      if (!res.ok) {
        const errorPayload = await res.json().catch(() => null) as
          | { detail?: string; message?: string; code?: string }
          | null
        const errorMessage =
          errorPayload?.detail ??
          errorPayload?.message ??
          `请求失败（HTTP ${res.status}）`
        throw new Error(errorMessage)
      }

      await readSSEStream(res, onChunk, onDone)
    } catch (err: unknown) {
      if ((err as Error).name !== 'AbortError') {
        onError((err as Error).message ?? String(err))
      }
    }
  }

  run()
  return controller
}

export function streamSingleChat(
  sessionId: string,
  message: string,
  panelConfig: ModelConfig,
  webSearchEnabled: boolean,
  knowledgeBaseEnabled: boolean,
  enabledMcpServers: string[],
  images: ChatImage[],
  files: ChatFile[],
  answerGroupId: string,
  replaceAiHistory: boolean,
  onChunk: (chunk: SSEChunk) => void,
  onDone: () => void,
  onError: (err: string) => void,
): AbortController {
  const controller = new AbortController()

  const run = async () => {
    try {
      const res = await fetch(`${BASE}/chat/single`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message,
          images,
          files,
          panel_config: panelConfig,
          web_search_enabled: webSearchEnabled,
          knowledge_base_enabled: knowledgeBaseEnabled,
          enabled_mcp_servers: enabledMcpServers,
          answer_group_id: answerGroupId,
          persist_user_history: false,
          persist_ai_history: true,
          replace_ai_history: replaceAiHistory,
          exclude_ai_answer_group_id: answerGroupId,
        }),
        signal: controller.signal,
      })

      if (!res.ok) {
        const errorPayload = await res.json().catch(() => null) as
          | { detail?: string; message?: string; code?: string }
          | null
        const errorMessage =
          errorPayload?.detail ??
          errorPayload?.message ??
          `请求失败（HTTP ${res.status}）`
        throw new Error(errorMessage)
      }

      await readSSEStream(res, onChunk, onDone)
    } catch (err: unknown) {
      if ((err as Error).name !== 'AbortError') {
        onError((err as Error).message ?? String(err))
      }
    }
  }

  run()
  return controller
}

// ── Models ───────────────────────────────────

export async function getOllamaModels(baseUrl = 'http://localhost:11434'): Promise<string[]> {
  try {
    const res = await fetch(`${BASE}/models/ollama?base_url=${encodeURIComponent(baseUrl)}`)
    const data = await res.json()
    return (data.models as string[]) ?? []
  } catch {
    return []
  }
}

// ── Config ───────────────────────────────────

export async function getConfig() {
  const res = await authFetch('/config')
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to load config'))
  return res.json()
}

export async function saveConfig(payload: { tavily_api_key?: string }): Promise<void> {
  const res = await authFetch('/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to save config'))
}

export async function saveCloudModelApiKey(payload: {
  api_key: string
  api_key_ref?: string
}): Promise<{ api_key_ref: string; api_key_set: boolean }> {
  const res = await authFetch('/config/cloud-model-api-key', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to save cloud model API key'))
  return res.json()
}

export async function deleteCloudModelApiKey(apiKeyRef: string): Promise<void> {
  const res = await authFetch(`/config/cloud-model-api-key/${encodeURIComponent(apiKeyRef)}`, {
    method: 'DELETE',
  })
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to delete cloud model API key'))
}

export async function resetAgents(): Promise<void> {
  const res = await authFetch('/agents/reset', { method: 'POST' })
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to reset agents'))
}

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

function normalizeSecurityAuditSummaryCategory(
  category: SecurityAuditSummaryCategory | string = 'all',
): SecurityAuditSummaryApiCategory | '' {
  if (
    category === 'access' ||
    category === 'identity' ||
    category === 'auth' ||
    category === 'audit'
  ) {
    return category
  }
  return ''
}

function normalizeSecurityAuditSummaryPayload(
  data: Partial<SecurityAuditSummary> & { category?: unknown },
): SecurityAuditSummary {
  const category = normalizeSecurityAuditSummaryCategory(
    typeof data.category === 'string' ? data.category : 'all',
  )
  const categories = readStringArray(data.categories).filter(
    (item): item is SecurityAuditSummaryApiCategory =>
      item === 'access' || item === 'identity' || item === 'auth' || item === 'audit',
  )

  return {
    category,
    categories,
    total: readNumber(data.total),
    recent_count: readNumber(data.recent_count),
    window_limit: readNumber(data.window_limit),
    action_counts: readNumberRecord(data.action_counts),
    result_counts: readNumberRecord(data.result_counts),
    category_counts: readNumberRecord(data.category_counts),
    unknown_action_count: readNumber(data.unknown_action_count),
  }
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

// ── Documents ────────────────────────────────

export async function uploadDocuments(files: File[]): Promise<UploadDocumentsResponse> {
  const form = new FormData()
  for (const f of files) form.append('files', f)
  const res = await authFetch('/documents/upload', { method: 'POST', body: form })
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, res.statusText))
  }
  return res.json()
}

export async function getTask(taskId: string): Promise<TaskRecord> {
  const res = await fetch(`${BASE}/tasks/${taskId}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json()
}

export async function listTasks(limit = 20, status?: TaskStatus): Promise<TaskRecord[]> {
  const searchParams = new URLSearchParams()
  searchParams.set('limit', String(limit))
  if (status) {
    searchParams.set('status', status)
  }
  const res = await fetch(`${BASE}/tasks?${searchParams.toString()}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  const data = await res.json() as { tasks?: TaskRecord[] }
  return data.tasks ?? []
}

export async function createMultiAgentWorkflowTask(
  payload: CreateMultiAgentWorkflowTaskPayload,
): Promise<TaskRecord> {
  const res = await authFetch('/tasks/multi-agent-workflow', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, 'Failed to create multi-agent workflow task'))
  }
  return res.json()
}

export async function getTaskApprovalPolicy(): Promise<TaskApprovalPolicy> {
  const res = await authFetch('/tasks/approval-policy')
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, 'Failed to load approval policy'))
  }
  return res.json()
}

export async function updateTaskApprovalPolicy(
  payload: TaskApprovalPolicy,
): Promise<TaskApprovalPolicy> {
  const res = await authFetch('/tasks/approval-policy', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, 'Failed to save approval policy'))
  }
  return res.json()
}

export async function decideTaskApproval(
  taskId: string,
  payload: {
    decision: TaskApprovalDecision
    reviewer?: string
    comment?: string
  },
): Promise<TaskRecord> {
  const res = await authFetch(`/tasks/${encodeURIComponent(taskId)}/approval`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, 'Failed to submit approval decision'))
  }
  return res.json()
}

export async function decideTaskApprovalsBatch(
  payload: BatchTaskApproval,
): Promise<BatchTaskApprovalResponse> {
  const res = await authFetch('/tasks/approvals/batch', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, 'Failed to submit batch approval decision'))
  }
  return res.json()
}

export async function getDocStats(): Promise<DocStats> {
  const res = await fetch(`${BASE}/documents/stats`)
  if (!res.ok) throw new Error(await readErrorDetail(res, '获取统计信息失败'))
  return res.json()
}

// ── System Prompts ────────────────────────────

export async function getSystemPrompts(): Promise<SystemPrompt[]> {
  const res = await fetch(`${BASE}/prompts`)
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to load prompts'))
  const data = await res.json()
  return data.prompts as SystemPrompt[]
}

export async function createSystemPrompt(
  name: string,
  content: string,
  dashboard_template?: DashboardTemplateConfig,
): Promise<SystemPrompt> {
  const res = await fetch(`${BASE}/prompts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, content, dashboard_template: dashboard_template ?? {} }),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res, '创建角色失败'))
  return res.json()
}

export async function updateSystemPrompt(
  id: string,
  name: string,
  content: string,
  dashboard_template?: DashboardTemplateConfig,
): Promise<SystemPrompt> {
  const res = await fetch(`${BASE}/prompts/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, content, dashboard_template: dashboard_template ?? {} }),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res, '更新角色失败'))
  return res.json()
}

export async function deleteSystemPrompt(id: string): Promise<void> {
  const res = await fetch(`${BASE}/prompts/${id}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(await readErrorDetail(res, '删除角色失败'))
}

export async function activateSystemPrompt(id: string): Promise<{ ok: boolean; kb_status?: string }> {
  const res = await fetch(`${BASE}/prompts/${id}/activate`, { method: 'POST' })
  if (!res.ok) throw new Error(await readErrorDetail(res, '启用角色失败'))
  return res.json()
}

export async function createSystemPromptWithKB(
  name: string,
  content: string,
  vectorStoreId?: string,
  dashboardTemplate?: DashboardTemplateConfig,
): Promise<SystemPrompt> {
  const res = await fetch(`${BASE}/prompts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name,
      content,
      vector_store_id: vectorStoreId ?? '',
      dashboard_template: dashboardTemplate ?? {},
    }),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res, '创建角色失败'))
  return res.json()
}

export async function updateSystemPromptWithKB(
  id: string,
  name: string,
  content: string,
  vectorStoreId?: string,
  dashboardTemplate?: DashboardTemplateConfig,
): Promise<SystemPrompt> {
  const res = await fetch(`${BASE}/prompts/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name,
      content,
      vector_store_id: vectorStoreId ?? '',
      dashboard_template: dashboardTemplate ?? {},
    }),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res, '更新角色失败'))
  return res.json()
}

// ── Session Reset ─────────────────────────────

export async function resetSession(sessionId: string): Promise<void> {
  await fetch(`${BASE}/sessions/${sessionId}/reset`, { method: 'POST' })
}

export async function createSessionShareLink(sessionId: string): Promise<ShareLinkResponse> {
  const res = await fetch(`${BASE}/sessions/${sessionId}/share`, {
    method: 'POST',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json() as Promise<ShareLinkResponse>
}

// ── Reports ──────────────────────────────────

export async function createDeckDraft(payload: {
  session_id: string
  panel_config: ModelConfig
  knowledge_base_enabled: boolean
  target_slide_count: number
  theme?: 'default' | 'midnight' | 'sunrise'
  answer_group_id?: string
  panel_id?: string
}): Promise<DeckSpec> {
  const res = await fetch(`${BASE}/decks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return normalizeDeckSpec(await res.json())
}

export async function getDecks(limit = 100): Promise<DeckSpec[]> {
  const safeLimit = Math.max(1, Math.min(500, Math.floor(limit)))
  const res = await fetch(`${BASE}/decks?limit=${encodeURIComponent(String(safeLimit))}`)
  const data = await res.json().catch(() => ({ detail: res.statusText })) as {
    detail?: string
    decks?: DeckSpec[]
  }
  if (!res.ok) {
    throw new Error(data.detail ?? res.statusText)
  }
  return Array.isArray(data.decks) ? data.decks.map(normalizeDeckSpec) : []
}

export async function getDeck(deckId: string): Promise<DeckSpec> {
  const res = await fetch(`${BASE}/decks/${deckId}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return normalizeDeckSpec(await res.json())
}

export async function updateDeck(deckId: string, payload: {
  title?: string
  theme?: 'default' | 'midnight' | 'sunrise'
  slides?: DeckSlide[]
}): Promise<DeckSpec> {
  const res = await fetch(`${BASE}/decks/${deckId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return normalizeDeckSpec(await res.json())
}

export interface ExportDeckOptions {
  allowUnsafeExport?: boolean
  overrideReason?: string
}

export interface DeckExportGate {
  blocked: boolean
  overridden: boolean
  can_export: boolean
  reason: string
  message: string
}

export interface UpdateDeckBlockRefsPayload {
  evidence_ref_ids?: string[]
  evidence_refs?: string[]
  source_ref_ids?: string[]
  evidence_source_ids?: string[]
  evidence_excerpt_ids?: string[]
}

export interface UpdateDeckBlockRefsResponse {
  deck: DeckSpec
  slide_id: string
  block_id: string
  block: DeckBlock
  citation_validation: DeckCitationValidation
  evidence_review: DeckEvidenceReview
  export_gate: DeckExportGate
}

export async function exportDeck(
  deckId: string,
  format: 'pptx' = 'pptx',
  options: ExportDeckOptions = {},
): Promise<Blob> {
  const params = new URLSearchParams({ format })
  if (options.allowUnsafeExport) {
    params.set('allow_unsafe_export', 'true')
  }
  if (options.overrideReason?.trim()) {
    params.set('override_reason', options.overrideReason.trim())
  }

  const res = await fetch(`${BASE}/decks/${deckId}/export?${params.toString()}`)
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, res.statusText))
  }
  return res.blob()
}

export async function createDeckShareLink(deckId: string): Promise<ShareLinkResponse> {
  const res = await fetch(`${BASE}/decks/${deckId}/share`, {
    method: 'POST',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json() as Promise<ShareLinkResponse>
}

export async function updateDeckBlockRefs(
  deckId: string,
  slideId: string,
  blockId: string,
  payload: UpdateDeckBlockRefsPayload,
): Promise<UpdateDeckBlockRefsResponse> {
  const res = await fetch(
    `${BASE}/decks/${encodeURIComponent(deckId)}/slides/${encodeURIComponent(slideId)}/blocks/${encodeURIComponent(blockId)}/refs`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    },
  )
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, 'Failed to update deck block references'))
  }
  const data = await res.json().catch(() => ({})) as Record<string, unknown>
  return {
    deck: normalizeDeckSpec(data.deck),
    slide_id: readString(data.slide_id),
    block_id: readString(data.block_id),
    block: normalizeDeckBlock(data.block, 0),
    citation_validation: normalizeDeckCitationValidation(data.citation_validation) ?? defaultDeckCitationValidation(),
    evidence_review: normalizeDeckEvidenceReview(data.evidence_review) ?? defaultDeckEvidenceReview(),
    export_gate: (typeof data.export_gate === 'object' && data.export_gate !== null
      ? data.export_gate
      : {
          blocked: false,
          overridden: false,
          can_export: true,
          reason: '',
          message: '',
        }) as DeckExportGate,
  }
}

export async function regenerateDeckSlide(
  deckId: string,
  slideId: string,
  payload: {
    panel_config: ModelConfig
    knowledge_base_enabled?: boolean
  },
): Promise<DeckSpec> {
  const res = await fetch(`${BASE}/decks/${deckId}/slides/${slideId}/regenerate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return normalizeDeckSpec(await res.json())
}

// ── Knowledge Bases ───────────────────────────

export async function getKnowledgeBases(): Promise<KnowledgeBase[]> {
  const res = await fetch(`${BASE}/knowledge-bases`)
  if (!res.ok) throw new Error(await readErrorDetail(res, 'Failed to load knowledge bases'))
  const data = await res.json()
  return data.knowledge_bases as KnowledgeBase[]
}

export async function getKBHealth(): Promise<KBHealthData> {
  const res = await fetch(`${BASE}/knowledge-base/health`)
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, '获取知识库健康状态失败'))
  }
  return res.json()
}

export async function getKnowledgeBaseChunks(params?: {
  path?: string
  query?: string
  source?: string
  offset?: number
  limit?: number
}): Promise<KnowledgeBaseChunksResponse> {
  const searchParams = new URLSearchParams()
  if (params?.path?.trim()) searchParams.set('path', params.path.trim())
  if (params?.query?.trim()) searchParams.set('query', params.query.trim())
  if (params?.source?.trim()) searchParams.set('source', params.source.trim())
  if (typeof params?.offset === 'number' && Number.isFinite(params.offset)) {
    searchParams.set('offset', String(Math.max(0, Math.floor(params.offset))))
  }
  if (typeof params?.limit === 'number' && Number.isFinite(params.limit)) {
    const safeLimit = Math.max(1, Math.min(200, Math.floor(params.limit)))
    searchParams.set('limit', String(safeLimit))
  }

  const query = searchParams.toString()
  const res = await fetch(`${BASE}/knowledge-base/chunks${query ? `?${query}` : ''}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json()
}

export async function updateKnowledgeBaseChunk(
  chunkId: string,
  payload: {
    content?: string
    source?: string
    path?: string
  },
): Promise<{ ok: boolean; chunk_id: string; reindexed: boolean }> {
  const searchParams = new URLSearchParams()
  if (payload.path?.trim()) searchParams.set('path', payload.path.trim())
  const query = searchParams.toString()
  const res = await fetch(
    `${BASE}/knowledge-base/chunks/${encodeURIComponent(chunkId)}${query ? `?${query}` : ''}`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...(payload.content !== undefined ? { content: payload.content } : {}),
        ...(payload.source !== undefined ? { source: payload.source } : {}),
      }),
    },
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
  return res.json()
}

export async function deleteKnowledgeBaseChunk(chunkId: string, path?: string): Promise<void> {
  const searchParams = new URLSearchParams()
  if (path?.trim()) searchParams.set('path', path.trim())
  const query = searchParams.toString()
  const res = await fetch(
    `${BASE}/knowledge-base/chunks/${encodeURIComponent(chunkId)}${query ? `?${query}` : ''}`,
    { method: 'DELETE' },
  )
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? res.statusText)
  }
}

export async function testKBRetrieval(
  query: string,
  options?: {
    search_k?: number
    fetch_k?: number
    use_rerank?: boolean
    retrieval_mode?: 'semantic' | 'keyword' | 'hybrid'
  },
): Promise<RetrievalTestResult> {
  const res = await fetch(`${BASE}/knowledge-base/test-retrieval`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, ...options }),
  })
  if (!res.ok) throw new Error(await readErrorDetail(res, '检索测试失败'))
  return res.json()
}

export async function deleteKnowledgeBase(path?: string): Promise<void> {
  const url = path
    ? `${BASE}/knowledge-base/by-path?path=${encodeURIComponent(path)}`
    : `${BASE}/knowledge-base`
  const res = await fetch(url, { method: 'DELETE' })
  if (!res.ok) {
    throw new Error(await readErrorDetail(res, res.statusText))
  }
}
