import type { WorkflowNode } from '../../stores/workflowStore'



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
  config_schema?: McpConnectorConfigSchema
  template?: boolean
}

export interface McpConnectorConfigSchema {
  transport?: string
  required?: string[]
  optional?: string[]
  sensitive?: string[]
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
  installed?: InstalledMcpConnectorSummary
}

export interface McpConnectorManifest {
  name: string
  version?: string
  label?: string
  description?: string
  category?: string
  transport?: string
  command?: string
  args?: string[]
  install_command?: string | string[]
  url?: string
  headers?: Record<string, string>
  env?: Record<string, string>
  cwd?: string
  encoding?: string
  scopes?: string[]
  capability_scopes?: string[]
  risk_level?: 'low' | 'medium' | 'high' | 'critical' | string
  requires_approval?: boolean
  metadata?: Record<string, unknown>
  config_schema?: McpConnectorConfigSchema
}

export interface InstallMcpConnectorPayload {
  manifest: McpConnectorManifest
}

export interface InstalledMcpConnectorSummary {
  name: string
  connector?: McpConnector
  executed_install_command: boolean
}

export interface InstallMcpConnectorResponse extends McpConfigResponse {
  installed?: InstalledMcpConnectorSummary
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

export interface SecurityStatusResponse {
  allow_remote_clients: boolean
  local_only_mode: boolean
  remote_auth_ready: boolean
  admin_token_configured: boolean
  remote_admin_ready: boolean
  auth_token_count: number
  configured_roles: string[]
  auth_token_hygiene_healthy: boolean
  weak_auth_token_count: number
  legacy_auth_token_count: number
  share_link_secret_healthy: boolean
  share_link_secret_uses_default: boolean
  share_link_secret_min_length: number
  remote_share_ready: boolean
  remote_management_rate_limit_enabled: boolean
  remote_management_rate_limit_window_seconds: number
  remote_management_rate_limit_window_seconds_source: string
  remote_management_rate_limit_max_requests: number
  remote_management_rate_limit_max_requests_source: string
  remote_management_rate_limit_scope: string
  remote_management_rate_limit_storage: string
  remote_management_rate_limit_path_prefixes: string[]
  remote_management_rate_limit_response_headers: string[]
  remote_management_rate_limit_tracked_principal_count: number
  remote_management_rate_limit_active_request_count: number
  remote_management_rate_limit_blocked_count: number
  remote_management_rate_limit_last_blocked_at: number | null
  remote_management_rate_limit_next_reset_after_seconds: number
  share_link_ttl_seconds: number
  share_link_ttl_hours: number
  cors_allow_credentials: boolean
  cors_allowed_origins: string[]
  request_id_header: string
  process_time_header: string
  security_audit_storage: string
  security_audit_history_limit: number
  security_audit_history_limit_source: string
  security_audit_persisted_count: number
  security_audit_memory_window_limit: number
  chat_file_limits: Record<string, number>
  document_upload_limits: Record<string, number>
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
  parent_span_id?: string | null
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
  token_usage?: AnswerGroupTokenUsage
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

export type ConnectionType =
  | 'ollama'
  | 'openai_compatible'
  | 'deepseek'
  | 'anthropic'
  | 'google'

export interface ProviderCatalogItem {
  id: string
  connection_type: ConnectionType | string
  aliases: string[]
  capabilities: string[]
  default_base_url: string
  default_model: string
  base_url_env_keys: string[]
  model_env_keys: string[]
}

export interface ProviderCatalogResponse {
  providers: ProviderCatalogItem[]
  default_provider: ConnectionType | string
  total: number
}

export interface AgentCatalogItem {
  name: string
  description: string
  capabilities: string[]
  metadata: Record<string, unknown>
}

export interface AgentPluginManifest {
  enabled?: boolean
  name: string
  version?: string
  runtime?: 'static_manifest' | 'workflow_manifest' | string
  description: string
  capabilities: string[]
  output_prefix?: string
  risk_level?: 'low' | 'medium' | 'high' | 'critical' | string
  requires_approval?: boolean
  approval_reason?: string
  workflow?: Array<{
    id: string
    title: string
    prompt: string
    artifact_type?: string
  }>
  metadata?: Record<string, unknown>
}

export interface InstallAgentPluginPayload {
  manifest: AgentPluginManifest
}

export interface InstalledAgentPluginSummary {
  name: string
  agent?: AgentCatalogItem
  manifest_path: string
  executed_entrypoint: boolean
}

export interface UninstalledAgentPluginSummary {
  name: string
  manifest_path: string
  deleted_manifest: boolean
  existed: boolean
}

export interface AgentPluginMarketplaceTemplate {
  name: string
  description: string
  capabilities: string[]
  category: string
  risk_level: 'low' | 'medium' | 'high' | 'critical' | string
  requires_approval: boolean
  approval_reason: string
  source: string
  installed: boolean
  template: boolean
  manifest: AgentPluginManifest
}

export interface AgentPluginMarketplaceResponse {
  templates: AgentPluginMarketplaceTemplate[]
  summary: {
    total: number
    installed: number
    available: number
    categories: number
    issue_count: number
  }
  issues: Array<{
    file: string
    code: string
    message: string
  }>
}

export interface AgentCatalogResponse {
  agents: AgentCatalogItem[]
  summary: {
    total: number
    builtin: number
    plugin: number
  }
  plugin_manifests: {
    enabled: boolean
    directory_count: number
    scanned_count?: number
    loaded_count?: number
    issue_count?: number
    issues?: Array<{
      file: string
      code: string
      message: string
    }>
  }
  marketplace?: AgentPluginMarketplaceResponse
  installed?: InstalledAgentPluginSummary
  uninstalled?: UninstalledAgentPluginSummary
}

export type DeliveryTemplateArtifactType = 'report' | 'deck'

export interface DeliveryTemplateItem {
  id: string
  name: string
  description: string
  artifact_type: DeliveryTemplateArtifactType
  category: string
  tags: string[]
  target_format: string
  preview: string
  suggested_options: Record<string, unknown>
  metadata: Record<string, unknown>
}

export interface DeliveryTemplateManifest {
  enabled?: boolean
  id: string
  version?: string
  name: string
  description: string
  artifact_type: DeliveryTemplateArtifactType
  category?: string
  tags: string[]
  target_format: string
  preview?: string
  suggested_options?: Record<string, unknown>
  metadata?: Record<string, unknown>
}

export interface InstallDeliveryTemplatePayload {
  manifest: DeliveryTemplateManifest
}

export interface InstalledDeliveryTemplateSummary {
  id: string
  template?: DeliveryTemplateItem
  manifest_path: string
  executed_template_code: boolean
}

export interface UninstalledDeliveryTemplateSummary {
  id: string
  manifest_path: string
  deleted_manifest: boolean
  existed: boolean
}

export interface DeliveryTemplateCatalogResponse {
  templates: DeliveryTemplateItem[]
  summary: {
    total: number
    builtin: number
    manifest: number
    report: number
    deck: number
  }
  manifests: {
    enabled: boolean
    directory_count: number
    scanned_count: number
    loaded_count: number
    issue_count: number
    issues: Array<{
      file: string
      code: string
      message: string
    }>
  }
  installed?: InstalledDeliveryTemplateSummary
  uninstalled?: UninstalledDeliveryTemplateSummary
}

export interface AssistantPresetToolConfig {
  web_search_enabled: boolean
  knowledge_base_enabled: boolean
  mcp_servers_enabled: string[]
}

export interface AssistantPreset {
  id: string
  name: string
  avatar: string
  system_prompt_id: string
  default_model_config: ModelConfig
  tool_config: AssistantPresetToolConfig
  starters: string[]
  is_default: boolean
  is_active: boolean
  created_at: number
  updated_at: number
}

export interface AssistantPresetListResponse {
  presets: AssistantPreset[]
}

export type AssistantPresetPayload = Pick<
  AssistantPreset,
  'name' | 'avatar' | 'system_prompt_id' | 'default_model_config' | 'tool_config' | 'starters'
>

export interface ModelConfig {
  panel_id: string
  connection_type?: ConnectionType
  provider?:
    | ConnectionType
    | 'local'
    | 'cloud'
    | 'openai'
    | 'openrouter'
    | 'claude'
    | 'gemini'
  model: string
  base_url: string
  api_key: string
  api_key_ref?: string
  temperature: number
  agent_mode: 'auto' | 'langgraph' | 'function_calling' | 'plain_chat'
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
  type: 'chunk' | 'done' | 'error' | 'sources' | 'all_done' | 'task_created' | 'workflow_state' | 'token_usage'
  content?: string
  error_code?: string
  suggestion?: string
  sources?: SourceItem[]
  token_usage?: AnswerGroupTokenUsage
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
  call_count?: number
  real_count?: number
  estimated_count?: number
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
  token_usage?: AnswerGroupTokenUsage
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

export interface GeneratedReport {
  markdown: string
  title: string
  artifact_id?: string
}

export interface ReportScopeOptions {
  answer_group_id?: string
  panel_id?: string
  template_id?: string
  template_options?: Record<string, unknown>
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
