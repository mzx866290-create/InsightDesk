import type { Page, Route } from '@playwright/test'

interface MockSession {
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
}

interface MockMessagesPayload {
  messages: Array<Record<string, unknown>>
  context_limit: number
  total_messages: number
  panels: Array<Record<string, unknown>>
  panel_messages: Record<string, Array<Record<string, unknown>>>
}

interface MockTask {
  task_id: string
  task_type: string
  status: 'pending' | 'running' | 'waiting_approval' | 'completed' | 'failed'
  progress: number
  result?: string
  error?: string
  params?: Record<string, unknown>
  session_id?: string | null
  created_at: number
  updated_at?: number
}

interface MockApprovalPolicy {
  enabled: boolean
  required_task_types: string[]
  high_risk_requires_approval: boolean
  default_reviewer_role: string
  updated_at: number | null
}

type MockApprovalDecision = 'approved' | 'rejected'

interface MockIdentityOrg {
  org_id: string
  name: string
  description: string
  created_at: number
  updated_at: number
}

interface MockIdentityUser {
  user_id: string
  display_name: string
  email: string
  created_at: number
  updated_at: number
}

interface MockIdentityMembership {
  org_id: string
  user_id: string
  role: 'viewer' | 'editor' | 'admin' | 'owner'
  created_at: number
  updated_at: number
}

interface MockResourceGrant {
  resource_type: string
  resource_id: string
  org_id?: string
  user_id?: string
  role: 'viewer' | 'editor' | 'admin' | 'owner'
  created_at: number
  updated_at: number
}

interface MockSsoConfig {
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

interface MockTraceEvent {
  event: 'start' | 'end' | 'error'
  name: string
  trace_id: string
  span_id: string
  parent_span_id: string | null
  timestamp: number
  duration_ms: number | null
  attributes: Record<string, unknown>
  error_type: string | null
  error_message: string | null
}

interface MockSecurityAuditEvent {
  action: string
  result: string
  timestamp: number
  request_id: string
  ip: string
  is_local: boolean
  auth: {
    role: string
    user_id: string
  }
  user: {
    user_id: string
    display_name: string
    email: string
  } | null
  details: Record<string, unknown>
}

interface MockMcpConnector {
  name: string
  label: string
  description: string
  category: string
  builtin: boolean
  transport: string
  source: string
  capability_scopes: string[]
  risk_level: 'low' | 'medium' | 'high' | 'critical'
  requires_approval: boolean
  enabled: boolean
  configured: boolean
  healthy: boolean
  status: string
  status_reasons: string[]
  policy: {
    allowed: boolean
    requires_approval: boolean
    missing_scopes: string[]
    reasons: string[]
    connector_approved: boolean
    risk_level: string
    capability_scopes: string[]
  }
}

interface MockIntegratorConnector {
  id?: string
  type: 'webhook' | 'email' | 'feishu' | 'dingtalk'
  name: string
  description: string
  enabled: boolean
  approved: boolean
  settings: Record<string, unknown>
}

interface MockIntegratorConnectorTestCheck {
  name: string
  ok: boolean
  status: 'passed' | 'failed'
  severity: 'info' | 'error'
  message: string
}

interface MockIntegratorAuditEvent {
  timestamp: number
  action: string
  result: string
  connector_id: string
  connector_type: string
  actor: string
  request_id: string
  details: Record<string, unknown>
}

interface MockIntegratorSchedule {
  schedule_id?: string
  name: string
  connector_id: string
  cron: string
  timezone: string
  interval_minutes: number
  enabled: boolean
  settings: Record<string, unknown>
  last_run_at: number | null
  next_run_at: number | null
}

interface MockDeck {
  version: string
  deck_id: string
  status: string
  meta: {
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
  generation: {
    source: 'kb_plus_chat' | 'chat_only'
    target_slide_count: number
    actual_slide_count: number
    warnings: Array<{ code: string; message: string }>
    evidence_coverage: {
      total_slides: number
      coverable_slide_count: number
      slides_with_evidence: number
      total_evidence_refs: number
      coverage_ratio: number
      unsupported_slide_ids: string[]
      slides: Array<{
        slide_id: string
        slide_type: string
        evidence_ref_count: number
        has_evidence: boolean
        is_coverable: boolean
        quality_state: 'supported' | 'weak_support' | 'manual'
      }>
    }
    evidence_review: {
      status: 'supported' | 'needs_review' | 'not_applicable'
      coverage_ratio: number
      coverable_slide_count: number
      slides_with_evidence: number
      unsupported_slide_ids: string[]
      needs_review_slide_ids: string[]
      action_count: number
      action_items: Array<{
        code: string
        severity: 'info' | 'warning' | 'error'
        message: string
        slide_ids: string[]
      }>
      slides: Array<{
        slide_id: string
        title: string
        slide_type: string
        is_coverable: boolean
        has_evidence: boolean
        evidence_ref_count: number
        quality_state: 'supported' | 'weak_support' | 'manual'
        needs_review: boolean
        source_ids: string[]
        source_titles: string[]
      }>
      citation_validation: MockDeckCitationValidation
    }
    citation_validation: MockDeckCitationValidation
  }
  slides: Array<{
    id: string
    type: string
    title: string
    subtitle: string
    layout: string
    intent: string
    speaker_notes: string
    blocks: Array<{
      id: string
      kind: string
      role: string
      content: {
        text?: string
        items?: string[]
        evidence_ref_ids?: string[]
        evidence_source_ids?: string[]
        evidence_excerpt_ids?: string[]
      }
      editable: boolean
    }>
    evidence_refs: Array<{
      id: string
      source_id: string
      source_title: string
      excerpt_id?: string | null
      snippet: string
      confidence: number
    }>
    quality_state: 'supported' | 'weak_support' | 'manual'
    status: {
      locked: boolean
      dirty: boolean
      review_state: string
    }
  }>
  source_registry: Array<{
    id: string
    type: string
    title: string
    document_id?: string | null
    uri?: string | null
    metadata: Record<string, unknown>
  }>
  citation_validation: MockDeckCitationValidation
}

interface MockDeckCitationValidation {
  status: 'passed' | 'failed'
  can_export: boolean
  issue_count: number
  missing_source_ids: string[]
  missing_block_evidence_ref_ids: string[]
  issues: Array<{
    code: string
    message: string
    slide_id: string
    block_id: string
    evidence_ref_id: string
    source_id: string
  }>
}

interface MockResearchArchive {
  archive_id: string
  title: string
  session_id?: string
  task_id?: string
  artifact_id?: string
  query: string
  claim_count: number
  source_count: number
  claim_evidence_chains: Array<Record<string, unknown>>
  paragraph_citations: Array<Record<string, unknown>>
  paragraph_claim_links: Array<Record<string, unknown>>
  navigation_index: Record<string, unknown>
  citation_graph: Record<string, unknown>
  conflict_summary: Record<string, unknown>
  conflict_review_resolutions: Array<Record<string, unknown>>
  claim_verification_summary: Record<string, unknown>
  verification_summary: Record<string, unknown>
  sources: Array<Record<string, unknown>>
  preview_claims: Array<Record<string, unknown>>
  preview_sources: Array<Record<string, unknown>>
  provider_capabilities: Record<string, unknown>
  delivery_quality: Record<string, unknown>
  created_at: number
  updated_at: number
}

const now = 1_710_000_000
const defaultWorkspace = {
  workspace_id: 'workspace-default',
  name: 'Default Workspace',
  description: '',
  color: 'blue',
  is_active: true,
  created_at: now,
  updated_at: now,
  session_count: 0,
}

const defaultPrompt = {
  id: 'prompt-default',
  name: 'AI Assistant',
  content: 'You are a helpful assistant.',
  is_default: true,
  is_active: true,
  created_at: now,
  updated_at: now,
}

const defaultMcpConnectors: MockMcpConnector[] = [
  {
    name: 'knowledge-base',
    label: 'Knowledge Base',
    description: 'Query internal knowledge chunks and diagnostics.',
    category: 'knowledge',
    builtin: true,
    transport: 'stdio',
    source: 'default',
    capability_scopes: ['knowledge:read', 'knowledge:diagnostics'],
    risk_level: 'low',
    requires_approval: false,
    enabled: true,
    configured: true,
    healthy: true,
    status: 'healthy',
    status_reasons: [],
    policy: {
      allowed: true,
      requires_approval: false,
      missing_scopes: [],
      reasons: [],
      connector_approved: false,
      risk_level: 'low',
      capability_scopes: ['knowledge:read', 'knowledge:diagnostics'],
    },
  },
  {
    name: 'custom-crm',
    label: 'Custom CRM',
    description: 'Sync customer records through a high-risk external connector.',
    category: 'integration',
    builtin: false,
    transport: 'streamable_http',
    source: 'config',
    capability_scopes: ['crm:read', 'crm:write'],
    risk_level: 'high',
    requires_approval: true,
    enabled: false,
    configured: true,
    healthy: false,
    status: 'disabled',
    status_reasons: ['connector_not_approved'],
    policy: {
      allowed: false,
      requires_approval: true,
      missing_scopes: [],
      reasons: ['connector_requires_approval', 'connector_not_approved'],
      connector_approved: false,
      risk_level: 'high',
      capability_scopes: ['crm:read', 'crm:write'],
    },
  },
]

const redactedValue = '***redacted***'
const sensitiveIntegratorSettingKeywords = [
  'secret',
  'token',
  'password',
  'credential',
  'key',
  'webhook_url',
  'url',
  'authorization',
  'auth',
  'username',
]
const supportedIntegratorConnectorTypes: MockIntegratorConnector['type'][] = [
  'webhook',
  'email',
  'feishu',
  'dingtalk',
]

const defaultIntegratorConnectors: MockIntegratorConnector[] = [
  {
    id: 'ops-webhook',
    type: 'webhook',
    name: 'Ops Webhook',
    description: 'Post incident updates to the operations webhook endpoint.',
    enabled: true,
    approved: false,
    settings: {
      url: 'https://hooks.example.test/ops',
      token: 'ops-webhook-token',
      channel: 'ops-alerts',
      nested: {
        client_secret: 'nested-client-secret',
        safe_label: 'incident-review',
      },
    },
  },
  {
    id: 'finance-email',
    type: 'email',
    name: 'Finance Email',
    description: 'Send finance review summaries by email.',
    enabled: false,
    approved: true,
    settings: {
      to: ['finance@example.test'],
      subject_prefix: '[Finance]',
    },
  },
]

const defaultIntegratorAuditEvents: MockIntegratorAuditEvent[] = [
  {
    timestamp: now + 20,
    action: 'integrator_connector_test',
    result: 'success',
    connector_id: 'ops-webhook',
    connector_type: 'webhook',
    actor: 'playwright-local',
    request_id: 'req-integrator-audit-test-1',
    details: {
      dry_run: true,
      check_count: 3,
      channel: 'ops-alerts',
      url: 'https://hooks.example.test/ops',
      token: 'ops-webhook-token',
      nested: {
        client_secret: 'nested-client-secret',
      },
    },
  },
  {
    timestamp: now + 19,
    action: 'integrator_connector_save',
    result: 'success',
    connector_id: 'finance-email',
    connector_type: 'email',
    actor: 'playwright-local',
    request_id: 'req-integrator-audit-save-1',
    details: {
      enabled: false,
      approved: true,
      recipient_count: 1,
      client_secret: 'top-level-client-secret',
    },
  },
]

const defaultIntegratorSchedules: MockIntegratorSchedule[] = [
  {
    schedule_id: 'schedule-ops-hourly',
    name: 'Ops hourly sync',
    connector_id: 'ops-webhook',
    cron: '0 * * * *',
    timezone: 'UTC',
    interval_minutes: 60,
    enabled: true,
    settings: {
      url: 'https://hooks.example.test/schedules',
      token: 'schedule-token',
      batch_size: 25,
      nested: {
        secret: 'nested-schedule-secret',
        mode: 'delta',
      },
    },
    last_run_at: now + 15,
    next_run_at: now + 3600,
  },
]

const defaultTraceEvents: MockTraceEvent[] = [
  {
    event: 'start',
    name: 'agent.workflow',
    trace_id: 'trace-smoke-1',
    span_id: 'span-smoke-1',
    parent_span_id: null,
    timestamp: now + 10,
    duration_ms: null,
    attributes: {
      session_id: 'session-1',
      panel_id: 'panel-1',
      mode: 'quick',
    },
    error_type: null,
    error_message: null,
  },
  {
    event: 'end',
    name: 'agent.workflow',
    trace_id: 'trace-smoke-1',
    span_id: 'span-smoke-1',
    parent_span_id: null,
    timestamp: now + 11,
    duration_ms: 142.35,
    attributes: {
      session_id: 'session-1',
      panel_id: 'panel-1',
      mode: 'quick',
    },
    error_type: null,
    error_message: null,
  },
  {
    event: 'error',
    name: 'tool.retrieval',
    trace_id: 'trace-smoke-2',
    span_id: 'span-smoke-2',
    parent_span_id: 'span-smoke-1',
    timestamp: now + 12,
    duration_ms: 18.4,
    attributes: {
      tool_name: 'knowledge_base',
      query: 'missing index',
    },
    error_type: 'RuntimeError',
    error_message: 'Mock retrieval failed',
  },
]

const securityAuditActionCategories: Record<string, string> = {
  remote_auth_guard: 'auth',
  remote_management_rate_limit: 'auth',
  remote_share_guard: 'auth',
  get_security_status: 'auth',
  get_auth_whoami: 'auth',
  get_auth_tokens: 'auth',
  get_auth_sso_config: 'auth',
  update_auth_sso_config: 'auth',
  start_auth_sso_login: 'auth',
  complete_auth_sso_callback: 'auth',
  get_identity_catalog: 'identity',
  upsert_identity_org: 'identity',
  upsert_identity_user: 'identity',
  set_identity_membership: 'identity',
  sync_external_identity: 'identity',
  list_resource_grants: 'access',
  get_resource_access: 'access',
  upsert_resource_grant: 'access',
  delete_resource_grant: 'access',
  resource_access_denied: 'access',
  resource_owner_granted: 'access',
  resource_grants_inherited: 'access',
  get_access_role_matrix: 'access',
  get_security_audit_actions: 'audit',
  get_security_audit_events: 'audit',
  get_security_audit_summary: 'audit',
  cleanup_security_audit_events: 'audit',
  task_approval_decision: 'audit',
  task_approval_batch_decision: 'audit',
}

const defaultSecurityAuditEvents: MockSecurityAuditEvent[] = [
  {
    action: 'remote_auth_guard',
    result: 'allowed',
    timestamp: now + 1,
    request_id: 'req-audit-remote-auth-1',
    ip: '127.0.0.1',
    is_local: true,
    auth: { role: 'admin', user_id: 'playwright-local' },
    user: {
      user_id: 'playwright-local',
      display_name: 'Playwright Admin',
      email: 'playwright@example.com',
    },
    details: { path: '/api/auth/whoami', method: 'GET' },
  },
  {
    action: 'get_auth_whoami',
    result: 'success',
    timestamp: now + 2,
    request_id: 'req-audit-whoami-1',
    ip: '127.0.0.1',
    is_local: true,
    auth: { role: 'admin', user_id: 'playwright-local' },
    user: {
      user_id: 'playwright-local',
      display_name: 'Playwright Admin',
      email: 'playwright@example.com',
    },
    details: { endpoint: '/api/auth/whoami' },
  },
  {
    action: 'upsert_identity_user',
    result: 'success',
    timestamp: now + 3,
    request_id: 'req-audit-identity-user-1',
    ip: '127.0.0.1',
    is_local: true,
    auth: { role: 'admin', user_id: 'playwright-local' },
    user: {
      user_id: 'playwright-local',
      display_name: 'Playwright Admin',
      email: 'playwright@example.com',
    },
    details: { target_user_id: 'user-demo', target_email_domain: 'example.com' },
  },
  {
    action: 'list_resource_grants',
    result: 'success',
    timestamp: now + 4,
    request_id: 'req-audit-resource-grants-1',
    ip: '127.0.0.1',
    is_local: true,
    auth: { role: 'admin', user_id: 'playwright-local' },
    user: {
      user_id: 'playwright-local',
      display_name: 'Playwright Admin',
      email: 'playwright@example.com',
    },
    details: { resource_type: 'workspace', limit: 20 },
  },
  {
    action: 'resource_access_denied',
    result: 'denied',
    timestamp: now + 5,
    request_id: 'req-audit-resource-denied-1',
    ip: '127.0.0.1',
    is_local: true,
    auth: { role: 'viewer', user_id: 'playwright-viewer' },
    user: {
      user_id: 'playwright-viewer',
      display_name: 'Playwright Viewer',
      email: 'viewer@example.com',
    },
    details: { resource_type: 'deck', resource_id: 'deck-private', required_role: 'viewer' },
  },
  {
    action: 'task_approval_decision',
    result: 'approved',
    timestamp: now + 6,
    request_id: 'req-audit-approval-decision-1',
    ip: '127.0.0.1',
    is_local: true,
    auth: { role: 'admin', user_id: 'playwright-local' },
    user: {
      user_id: 'playwright-local',
      display_name: 'Playwright Admin',
      email: 'playwright@example.com',
    },
    details: {
      task_id: 'task-approval-smoke-1',
      task_type: 'multi_agent_workflow',
      decision: 'approved',
      reviewer: 'playwright-local',
    },
  },
  {
    action: 'task_approval_batch_decision',
    result: 'approved',
    timestamp: now + 7,
    request_id: 'req-audit-approval-batch-1',
    ip: '127.0.0.1',
    is_local: true,
    auth: { role: 'admin', user_id: 'playwright-local' },
    user: {
      user_id: 'playwright-local',
      display_name: 'Playwright Admin',
      email: 'playwright@example.com',
    },
    details: {
      total: 2,
      task_ids: ['task-approval-smoke-1', 'task-approval-smoke-2'],
      decision: 'approved',
      succeeded: 2,
      failed: 0,
      reviewer: 'playwright-local',
    },
  },
  {
    action: 'get_security_audit_summary',
    result: 'success',
    timestamp: now + 8,
    request_id: 'req-audit-summary-1',
    ip: '127.0.0.1',
    is_local: true,
    auth: { role: 'admin', user_id: 'playwright-local' },
    user: {
      user_id: 'playwright-local',
      display_name: 'Playwright Admin',
      email: 'playwright@example.com',
    },
    details: { category: 'audit', limit: 100 },
  },
  {
    action: 'legacy_unmapped_guard',
    result: 'blocked',
    timestamp: now + 9,
    request_id: 'req-audit-legacy-1',
    ip: '127.0.0.1',
    is_local: true,
    auth: { role: 'admin', user_id: 'playwright-local' },
    user: null,
    details: { reason: 'legacy action is intentionally uncategorized' },
  },
]

function applyMockApproval(
  task: MockTask,
  decision: MockApprovalDecision,
  updatedAt: number,
  reviewer?: string,
  comment?: string,
): MockTask {
  const approvalParams = {
    ...(task.params ?? {}),
    approval_decision: decision,
    ...(reviewer ? { approval_reviewer: reviewer } : {}),
    ...(comment ? { approval_comment: comment } : {}),
  }

  return decision === 'approved'
    ? {
        ...task,
        status: 'completed',
        progress: 100,
        result: 'Mock workflow resumed after manual approval.',
        params: approvalParams,
        updated_at: updatedAt,
      }
    : {
        ...task,
        status: 'failed',
        progress: task.progress,
        error: 'Mock workflow rejected at manual approval gate.',
        params: approvalParams,
        updated_at: updatedAt,
      }
}

function createMockDeck({
  deckId = 'deck-mock-1',
  title = 'Mock Deck',
  sessionId = 'session-1',
  answerGroupId = 'answer-group-1',
  panelId = 'panel-1',
}: {
  deckId?: string
  title?: string
  sessionId?: string
  answerGroupId?: string
  panelId?: string
} = {}): MockDeck {
  const citationValidation: MockDeckCitationValidation = {
    status: 'failed',
    can_export: false,
    issue_count: 2,
    missing_source_ids: ['missing-source-1'],
    missing_block_evidence_ref_ids: ['ev-missing'],
    issues: [
      {
        code: 'missing_source_registry_entry',
        message: 'Evidence reference points to a source_id missing from source_registry.',
        slide_id: 'slide-content',
        block_id: '',
        evidence_ref_id: 'evidence-missing-source',
        source_id: 'missing-source-1',
      },
      {
        code: 'missing_slide_evidence_ref',
        message: 'Block evidence_ref_id is not present in the parent slide evidence_refs.',
        slide_id: 'slide-content',
        block_id: 'block-content-list',
        evidence_ref_id: 'ev-missing',
        source_id: '',
      },
    ],
  }

  return {
    version: '1.0.0',
    deck_id: deckId,
    status: 'ready',
    meta: {
      title,
      subtitle: 'Generated from the research report',
      language: 'zh-CN',
      audience: 'project team',
      purpose: 'demo',
      author: 'Playwright Mock',
      theme: 'default',
      created_at: '2026-04-15T00:00:00.000Z',
      session_id: sessionId,
      source_mode: 'chat_only',
      generator_panel_id: panelId,
      source_answer_group_id: answerGroupId,
      source_panel_id: panelId,
    },
    generation: {
      source: 'chat_only',
      target_slide_count: 8,
      actual_slide_count: 2,
      warnings: [],
      evidence_coverage: {
        total_slides: 2,
        coverable_slide_count: 2,
        slides_with_evidence: 1,
        total_evidence_refs: 1,
        coverage_ratio: 0.5,
        unsupported_slide_ids: ['slide-content'],
        slides: [
          {
            slide_id: 'slide-cover',
            slide_type: 'cover',
            evidence_ref_count: 1,
            has_evidence: true,
            is_coverable: true,
            quality_state: 'supported',
          },
          {
            slide_id: 'slide-content',
            slide_type: 'content',
            evidence_ref_count: 0,
            has_evidence: false,
            is_coverable: true,
            quality_state: 'manual',
          },
        ],
      },
      evidence_review: {
        status: 'needs_review',
        coverage_ratio: 0.5,
        coverable_slide_count: 2,
        slides_with_evidence: 1,
        unsupported_slide_ids: ['slide-content'],
        needs_review_slide_ids: ['slide-content'],
        action_count: 1,
        action_items: [
          {
            code: 'add_missing_slide_evidence',
            severity: 'warning',
            message: 'Add evidence references to unsupported slides.',
            slide_ids: ['slide-content'],
          },
        ],
        slides: [
          {
            slide_id: 'slide-cover',
            title,
            slide_type: 'cover',
            is_coverable: true,
            has_evidence: true,
            evidence_ref_count: 1,
            quality_state: 'supported',
            needs_review: false,
            source_ids: ['source-1'],
            source_titles: ['Research source for smoke test'],
          },
          {
            slide_id: 'slide-content',
            title: 'Mock deck overview',
            slide_type: 'content',
            is_coverable: true,
            has_evidence: false,
            evidence_ref_count: 0,
            quality_state: 'manual',
            needs_review: true,
            source_ids: [],
            source_titles: [],
          },
        ],
        citation_validation: citationValidation,
      },
      citation_validation: citationValidation,
    },
    slides: [
      {
        id: 'slide-cover',
        type: 'cover',
        title,
        subtitle: 'Deck editor smoke coverage',
        layout: 'cover',
        intent: 'overview',
        speaker_notes: 'Opening slide for the generated deck.',
        blocks: [
          {
            id: 'block-cover-summary',
            kind: 'paragraph',
            role: 'summary',
            content: {
              text: 'This deck was generated from the mock report preview flow.',
              evidence_ref_ids: ['evidence-1'],
              evidence_source_ids: ['source-1'],
            },
            editable: true,
          },
        ],
        evidence_refs: [
          {
            id: 'evidence-1',
            source_id: 'source-1',
            source_title: 'Research source for smoke test',
            snippet: 'Evidence collected for the deck smoke test.',
            confidence: 0.91,
          },
        ],
        quality_state: 'supported',
        status: {
          locked: false,
          dirty: false,
          review_state: 'draft',
        },
      },
      {
        id: 'slide-content',
        type: 'content',
        title: 'Mock deck overview',
        subtitle: 'Key validation points',
        layout: 'content',
        intent: 'details',
        speaker_notes: 'Second slide for editor verification.',
        blocks: [
          {
            id: 'block-content-list',
            kind: 'bullet_list',
            role: 'main_points',
            content: {
              items: [
                'Deck generation task completes successfully.',
                'Deck details are fetched through the mocked API.',
                'The deck editor opens with renderable content.',
              ],
              evidence_ref_ids: ['ev-missing'],
            },
            editable: true,
          },
        ],
        evidence_refs: [],
        quality_state: 'manual',
        status: {
          locked: false,
          dirty: false,
          review_state: 'draft',
        },
      },
    ],
    source_registry: [
      {
        id: 'source-1',
        type: 'web',
        title: 'Research source for smoke test',
        uri: 'https://example.com/research-source',
        metadata: {},
      },
    ],
    citation_validation: citationValidation,
  }
}

function emptyMessagesPayload(): MockMessagesPayload {
  return {
    messages: [],
    context_limit: 16,
    total_messages: 0,
    panels: [],
    panel_messages: {},
  }
}

function buildResearchSources(query: string, answerGroupId?: string): Array<Record<string, unknown>> {
  return [
    {
      type: 'web',
      title: `Research source for ${query}`,
      url: 'https://example.com/research-source',
      snippet: `Evidence collected for ${query}.`,
      index: 1,
      answer_group_id: answerGroupId,
    },
  ]
}

function createMockResearchArchive({
  archiveId = 'research-archive-smoke-1',
  title = 'Research archive for agent QA',
  query = 'Find the latest AI agent testing patterns',
  sessionId = 'session-archive-smoke',
  taskId = 'task-research-archive-smoke',
  artifactId = 'artifact-research-archive-smoke',
}: {
  archiveId?: string
  title?: string
  query?: string
  sessionId?: string
  taskId?: string
  artifactId?: string
} = {}): MockResearchArchive {
  const sources = [
    {
      source_index: 1,
      type: 'web',
      title: 'Primary source for AI agent testing',
      url: 'https://example.com/agent-testing-primary',
      domain: 'example.com',
      provider: 'mock-web',
      capabilities: ['web_search', 'freshness_filter'],
      source_tier: 'primary',
      source_family: 'example-research',
      freshness_band: 'recent',
      published_at: '2026-04-15',
      selection_reason: 'Directly supports the main testing-pattern claim.',
      snippet: 'Agent QA teams combine smoke checks with evidence-backed regression gates.',
    },
    {
      source_index: 2,
      type: 'web',
      title: 'Independent QA benchmark notes',
      url: 'https://example.org/qa-benchmark-notes',
      domain: 'example.org',
      provider: 'mock-web',
      capabilities: ['web_search'],
      source_tier: 'secondary',
      source_family: 'independent-notes',
      freshness_band: 'recent',
      published_at: '2026-04-10',
      selection_reason: 'Independent corroboration for regression and citation review.',
      snippet: 'Benchmark notes recommend preserving traceable sources for generated claims.',
    },
  ]
  const claimEvidenceChains = [
    {
      claim_id: 'claim-agent-qa-1',
      claim_text:
        'Agent QA flows should pair smoke checks with traceable citation evidence before delivery.',
      facet: 'quality',
      claim_type: 'recommendation',
      date: '2026-04-15',
      status: 'verified',
      evidence_strength: 'high',
      verification_note:
        'Both primary and independent sources support the claim and no contradiction was found.',
      candidate_sources: ['Primary source for AI agent testing', 'Independent QA benchmark notes'],
      supporting_source_count: 2,
      independent_source_families: ['example-research', 'independent-notes'],
      has_primary_source: true,
      needs_attention: false,
      sources,
    },
  ]
  const claimVerificationSummary = {
    total_claims: 1,
    verified_claims: 1,
    partial_claims: 0,
    unverified_claims: 0,
    high_strength_claims: 1,
    medium_strength_claims: 0,
    low_strength_claims: 0,
    claims_needing_attention: [],
    contradiction_count: 0,
    resolution_actions: {},
  }
  const paragraphCitations = [
    {
      paragraph_id: 'paragraph-key-findings-1',
      paragraph_label: 'Paragraph P1',
      heading: 'Key Findings',
      text:
        'The async task flow completed successfully with agent QA evidence linked back to primary and independent sources.',
      claim_ids: ['claim-agent-qa-1'],
      citation_ids: ['citation-primary-agent-testing', 'citation-independent-qa-notes'],
      source_indices: [1, 2],
      source_ids: ['source-primary-agent-testing', 'source-independent-qa-notes'],
    },
  ]
  const paragraphClaimLinks = [
    {
      paragraph_id: 'paragraph-key-findings-1',
      anchor_id: 'paragraph-key-findings-1',
      claim_id: 'claim-agent-qa-1',
      link_type: 'claim',
    },
    {
      paragraph_id: 'paragraph-key-findings-1',
      anchor_id: 'paragraph-key-findings-1',
      source_id: 'source-primary-agent-testing',
      link_type: 'source',
    },
  ]
  const navigationIndex = {
    paragraph_to_claims: {
      'paragraph-key-findings-1': ['claim-agent-qa-1'],
    },
    paragraph_to_sources: {
      'paragraph-key-findings-1': ['source-primary-agent-testing', 'source-independent-qa-notes'],
    },
    claim_to_paragraphs: {
      'claim-agent-qa-1': ['paragraph-key-findings-1'],
    },
    source_to_paragraphs: {
      'source-primary-agent-testing': ['paragraph-key-findings-1'],
      'source-independent-qa-notes': ['paragraph-key-findings-1'],
    },
    links: paragraphClaimLinks,
  }
  const citationGraph = {
    summary: '1 verified claim links 1 report paragraph to 2 sources across 2 source families.',
    nodes: [
      {
        id: 'claim-agent-qa-1',
        type: 'claim',
        label: 'Agent QA evidence claim',
      },
      {
        id: 'paragraph-key-findings-1',
        type: 'paragraph',
        label: 'Paragraph P1',
      },
      {
        id: 'source-primary-agent-testing',
        type: 'source',
        label: 'Primary source for AI agent testing',
      },
      {
        id: 'source-independent-qa-notes',
        type: 'source',
        label: 'Independent QA benchmark notes',
      },
    ],
    edges: [
      {
        from: 'paragraph-key-findings-1',
        to: 'claim-agent-qa-1',
        relation: 'states',
      },
      {
        from: 'claim-agent-qa-1',
        to: 'source-primary-agent-testing',
        relation: 'supported_by',
      },
      {
        from: 'claim-agent-qa-1',
        to: 'source-independent-qa-notes',
        relation: 'corroborated_by',
      },
    ],
  }
  const conflictSummary = {
    status: 'needs_review',
    summary: 'One unresolved conflicts group needs human review for the agent QA claim.',
    conflict_count: 1,
    conflicts: [
      {
        conflict_id: 'conflict-agent-qa-1',
        claim_id: 'claim-agent-qa-1',
        claim_text:
          'Agent QA flows should pair smoke checks with traceable citation evidence before delivery.',
        status: 'needs_attention',
        text: 'Unresolved conflicts require human review for agent QA release gates.',
        source_ids: ['source-primary-agent-testing'],
        review_status: 'unreviewed',
      },
    ],
    review_actions: [],
  }

  return {
    archive_id: archiveId,
    title,
    session_id: sessionId,
    task_id: taskId,
    artifact_id: artifactId,
    query,
    claim_count: claimEvidenceChains.length,
    source_count: sources.length,
    claim_evidence_chains: claimEvidenceChains,
    paragraph_citations: paragraphCitations,
    paragraph_claim_links: paragraphClaimLinks,
    navigation_index: navigationIndex,
    citation_graph: citationGraph,
    conflict_summary: conflictSummary,
    conflict_review_resolutions: [],
    claim_verification_summary: claimVerificationSummary,
    verification_summary: claimVerificationSummary,
    sources,
    preview_claims: claimEvidenceChains,
    preview_sources: sources,
    provider_capabilities: {
      total_sources: sources.length,
      declared_sources: sources.length,
      providers: ['mock-web'],
      items: sources.map((source) => ({
        source_id: source.url,
        provider: source.provider,
        capabilities: source.capabilities,
        declared: true,
      })),
    },
    delivery_quality: {
      coverage: {
        source_coverage_ratio: 1,
        verification_ratio: 1,
      },
      source_quality: {
        primary_source_count: 1,
        independent_source_family_count: 2,
        freshness_bands: { recent: 2 },
        source_tiers: { primary: 1, secondary: 1 },
      },
      action_items: [],
    },
    created_at: now + 20,
    updated_at: now + 20,
  }
}

function buildSecurityAuditSummary(
  events: MockSecurityAuditEvent[],
  category: string,
  windowLimit: number,
): Record<string, unknown> {
  const categories = Array.from(new Set(Object.values(securityAuditActionCategories))).sort()
  const normalizedCategory = category.trim().toLowerCase()
  const windowEvents = events.slice(-windowLimit)
  const filteredEvents = windowEvents.filter((event) => {
    const eventCategory = securityAuditActionCategories[event.action] ?? 'uncategorized'
    return !normalizedCategory || eventCategory === normalizedCategory
  })
  const actionCounts: Record<string, number> = {}
  const resultCounts: Record<string, number> = {}
  const categoryCounts: Record<string, number> = {}
  let unknownActionCount = 0

  for (const event of filteredEvents) {
    const action = event.action.trim() || 'unknown'
    const result = event.result.trim() || 'unknown'
    const eventCategory = securityAuditActionCategories[action] ?? 'uncategorized'
    actionCounts[action] = (actionCounts[action] ?? 0) + 1
    resultCounts[result] = (resultCounts[result] ?? 0) + 1
    categoryCounts[eventCategory] = (categoryCounts[eventCategory] ?? 0) + 1
    if (eventCategory === 'uncategorized') {
      unknownActionCount += 1
    }
  }

  const sortCounts = (counts: Record<string, number>) =>
    Object.fromEntries(Object.entries(counts).sort(([left], [right]) => left.localeCompare(right)))

  return {
    category: normalizedCategory,
    categories,
    total: filteredEvents.length,
    recent_count: filteredEvents.length,
    window_limit: windowLimit,
    action_counts: sortCounts(actionCounts),
    result_counts: sortCounts(resultCounts),
    category_counts: sortCounts(categoryCounts),
    unknown_action_count: unknownActionCount,
  }
}

function buildSecurityAuditEvents({
  events,
  action,
  category,
  result,
  userId,
  since,
  until,
  limit,
}: {
  events: MockSecurityAuditEvent[]
  action: string
  category: string
  result: string
  userId: string
  since: number | null
  until: number | null
  limit: number
}): Record<string, unknown> {
  const normalizedAction = action.trim()
  const normalizedCategory = category.trim().toLowerCase()
  const normalizedResult = result.trim()
  const normalizedUserId = userId.trim()
  const filteredEvents = events.filter((event) => {
    const eventCategory = securityAuditActionCategories[event.action] ?? 'uncategorized'
    if (normalizedAction && event.action !== normalizedAction) return false
    if (normalizedCategory && eventCategory !== normalizedCategory) return false
    if (normalizedResult && event.result !== normalizedResult) return false
    if (normalizedUserId && event.auth.user_id !== normalizedUserId && event.user?.user_id !== normalizedUserId) {
      return false
    }
    if (since !== null && event.timestamp < since) return false
    if (until !== null && event.timestamp > until) return false
    return true
  })

  return {
    events: [...filteredEvents]
      .sort((left, right) => right.timestamp - left.timestamp)
      .slice(0, limit)
      .map((event) => ({
        timestamp: event.timestamp,
        request_id: event.request_id,
        action: event.action,
        result: event.result,
        ip: event.ip,
        is_local: event.is_local,
        auth_mode: event.is_local ? 'local' : 'bearer',
        auth_source: 'mock',
        user_id: event.auth.user_id || event.user?.user_id || '',
        user_role: event.auth.role,
        details: Object.entries(event.details)
          .map(([key, value]) => `${key}=${String(value)}`)
          .join(' '),
      })),
    total: filteredEvents.length,
    limit,
  }
}

function parseAuditTimestampFilter(value: string | null): number | null {
  if (!value?.trim()) return null
  const timestamp = Number(value)
  return Number.isFinite(timestamp) ? timestamp : null
}

function isSensitiveIntegratorSetting(key: string): boolean {
  const normalizedKey = key.toLowerCase()
  return sensitiveIntegratorSettingKeywords.some((keyword) => normalizedKey.includes(keyword))
}

function redactIntegratorSettings(settings: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(settings).map(([key, value]) => {
      if (isSensitiveIntegratorSetting(key)) {
        return [key, redactedValue]
      }
      if (value && typeof value === 'object' && !Array.isArray(value)) {
        return [key, redactIntegratorSettings(value as Record<string, unknown>)]
      }
      return [key, value]
    }),
  )
}

function mergeRedactedIntegratorSettings(
  incoming: Record<string, unknown>,
  previous: Record<string, unknown>,
): Record<string, unknown> {
  return Object.fromEntries(
    Object.entries(incoming).map(([key, value]) => {
      const previousValue = previous[key]
      if (value === redactedValue && previousValue !== undefined) {
        return [key, previousValue]
      }
      if (
        value &&
        typeof value === 'object' &&
        !Array.isArray(value) &&
        previousValue &&
        typeof previousValue === 'object' &&
        !Array.isArray(previousValue)
      ) {
        return [
          key,
          mergeRedactedIntegratorSettings(
            value as Record<string, unknown>,
            previousValue as Record<string, unknown>,
          ),
        ]
      }
      return [key, value]
    }),
  )
}

function normalizeIntegratorConnector(
  rawConnector: unknown,
  previous?: MockIntegratorConnector,
): MockIntegratorConnector {
  const connector = rawConnector && typeof rawConnector === 'object'
    ? rawConnector as Record<string, unknown>
    : {}
  const rawType = String(connector.type ?? '').trim().toLowerCase().replace('-', '_')
  const typeAliasMap: Record<string, MockIntegratorConnector['type']> = {
    ding_talk: 'dingtalk',
    dingding: 'dingtalk',
    lark: 'feishu',
    mail: 'email',
    http: 'webhook',
  }
  const type = typeAliasMap[rawType] ?? rawType
  if (!supportedIntegratorConnectorTypes.includes(type as MockIntegratorConnector['type'])) {
    throw new Error(`unsupported connector type: ${String(connector.type ?? '')}`)
  }

  const name = String(connector.name ?? '').trim()
  const id = String(connector.id ?? (name || type)).trim()
  if (!id) {
    throw new Error('connector id is required')
  }

  const rawSettings =
    connector.settings && typeof connector.settings === 'object' && !Array.isArray(connector.settings)
      ? connector.settings as Record<string, unknown>
      : Object.fromEntries(
          Object.entries(connector).filter(
            ([key]) =>
              !['id', 'type', 'name', 'description', 'enabled', 'approved', 'settings'].includes(key),
          ),
        )

  return {
    id,
    type: type as MockIntegratorConnector['type'],
    name,
    description: String(connector.description ?? '').trim(),
    enabled: typeof connector.enabled === 'boolean' ? connector.enabled : true,
    approved: typeof connector.approved === 'boolean' ? connector.approved : false,
    settings: mergeRedactedIntegratorSettings(rawSettings, previous?.settings ?? {}),
  }
}

function buildIntegratorConnectorsPayload(connectors: MockIntegratorConnector[]): Record<string, unknown> {
  const publicConnectors = connectors.map((connector) => ({
    ...connector,
    settings: redactIntegratorSettings(connector.settings),
  }))
  return {
    connectors: publicConnectors,
    total: publicConnectors.length,
    supported_types: supportedIntegratorConnectorTypes,
    persistence: {
      enabled: true,
      config_key: 'integrator_connectors',
      sensitive_fields_redacted: true,
    },
  }
}

function hasIntegratorEndpoint(connector: MockIntegratorConnector): boolean {
  const settings = connector.settings
  return Boolean(
    settings.url ||
      settings.webhook_url ||
      settings.endpoint ||
      (Array.isArray(settings.to) ? settings.to.length > 0 : settings.to),
  )
}

function buildIntegratorConnectorTestPayload(connector: MockIntegratorConnector): Record<string, unknown> {
  const checks: MockIntegratorConnectorTestCheck[] = [
    {
      name: 'enabled',
      ok: connector.enabled,
      status: connector.enabled ? 'passed' : 'failed',
      severity: connector.enabled ? 'info' : 'error',
      message: connector.enabled ? 'Connector is enabled.' : 'Connector is disabled.',
    },
    {
      name: 'approved',
      ok: connector.approved,
      status: connector.approved ? 'passed' : 'failed',
      severity: connector.approved ? 'info' : 'error',
      message: connector.approved ? 'Connector is approved for execution.' : 'Connector is not approved.',
    },
    {
      name: 'endpoint',
      ok: hasIntegratorEndpoint(connector),
      status: hasIntegratorEndpoint(connector) ? 'passed' : 'failed',
      severity: hasIntegratorEndpoint(connector) ? 'info' : 'error',
      message: hasIntegratorEndpoint(connector) ? 'Delivery endpoint is configured.' : 'Delivery endpoint is missing.',
    },
  ]
  const status = checks.every((check) => check.status === 'passed') ? 'success' : 'failed'
  const failedCount = checks.filter((check) => !check.ok).length

  return {
    ok: failedCount === 0,
    status,
    dry_run: true,
    executed: false,
    checks,
    summary: {
      check_count: checks.length,
      failed_count: failedCount,
      blocking_failure_count: failedCount,
      warning_count: 0,
    },
    connector: {
      id: connector.id,
      type: connector.type,
      name: connector.name,
      description: connector.description,
      enabled: connector.enabled,
      approved: connector.approved,
      settings: redactIntegratorSettings(connector.settings),
    },
  }
}

function credentialPatchFields(patch: Record<string, unknown>, prefix = ''): string[] {
  return Object.entries(patch).flatMap(([key, value]) => {
    const field = prefix ? `${prefix}.${key}` : key
    if (value && typeof value === 'object' && !Array.isArray(value)) {
      return credentialPatchFields(value as Record<string, unknown>, field)
    }
    return [field]
  })
}

function buildIntegratorCredentialRotationPayload(
  connector: MockIntegratorConnector,
  patch: Record<string, unknown>,
  previous: MockIntegratorConnector,
): Record<string, unknown> {
  const rotatedFields = credentialPatchFields(patch)
  const preservedFields = Object.keys(previous.settings).filter((field) => !(field in patch))
  return {
    ok: true,
    status: 'rotated',
    rotated_fields: rotatedFields,
    preserved_fields: preservedFields,
    summary: {
      rotated_count: rotatedFields.length,
      preserved_count: preservedFields.length,
    },
    connector: {
      ...connector,
      settings: redactIntegratorSettings(connector.settings),
    },
  }
}

function normalizeIntegratorProbeOptions(rawOptions: unknown): { mode: 'static' | 'external'; timeout_seconds: number } {
  const options = rawOptions && typeof rawOptions === 'object' && !Array.isArray(rawOptions)
    ? rawOptions as Record<string, unknown>
    : {}
  const rawMode = options.mode ?? (options.external === true ? 'external' : 'static')
  const mode = rawMode === 'external' ? 'external' : 'static'
  const rawTimeout = Number(options.timeout_seconds ?? 3)
  return {
    mode,
    timeout_seconds: Number.isFinite(rawTimeout) ? Math.max(0.1, Math.min(10, rawTimeout)) : 3,
  }
}

function mockIntegratorEndpointSummary(connector: MockIntegratorConnector): Record<string, unknown> {
  const rawEndpoint = String(connector.settings.url ?? connector.settings.webhook_url ?? connector.settings.endpoint ?? '')
  try {
    const endpoint = new URL(rawEndpoint)
    return {
      scheme: endpoint.protocol.replace(':', ''),
      host: endpoint.hostname,
      fingerprint: 'mock-endpoint-fp',
    }
  } catch {
    return {
      scheme: '',
      host: '',
      fingerprint: 'mock-endpoint-fp',
    }
  }
}

function buildIntegratorConnectorProbePayload(
  connector: MockIntegratorConnector,
  options: { mode: 'static' | 'external'; timeout_seconds: number },
): Record<string, unknown> {
  const external = options.mode === 'external'
  const outboundRequestSent = external && hasIntegratorEndpoint(connector)
  return {
    ...buildIntegratorConnectorTestPayload(connector),
    status: outboundRequestSent ? 'ready' : hasIntegratorEndpoint(connector) ? 'healthy' : 'warning',
    dry_run: !external,
    executed: outboundRequestSent,
    probe: {
      mode: options.mode,
      outbound_request_sent: outboundRequestSent,
      timeout_seconds: options.timeout_seconds,
      ...(external
        ? {
            endpoint: mockIntegratorEndpointSummary(connector),
            response: {
              ok: true,
              status_code: 204,
              elapsed_ms: 42,
              content_type: 'application/json',
            },
          }
        : {}),
    },
    summary: {
      ...(buildIntegratorConnectorTestPayload(connector).summary as Record<string, unknown>),
      probe_mode: options.mode,
    },
  }
}

function buildIntegratorAuditPayload(events: MockIntegratorAuditEvent[], limitRaw: string | null): Record<string, unknown> {
  const parsedLimit = Number(limitRaw ?? '20')
  const limit = Number.isFinite(parsedLimit) ? Math.max(1, Math.min(100, Math.floor(parsedLimit))) : 20
  const sortedEvents = [...events].sort((left, right) => right.timestamp - left.timestamp)
  return {
    events: sortedEvents.slice(0, limit).map((event) => ({
      ...event,
      details: redactIntegratorSettings(event.details),
    })),
    total: sortedEvents.length,
    limit,
  }
}

function normalizeIntegratorSchedule(
  rawSchedule: unknown,
  previous?: MockIntegratorSchedule,
): MockIntegratorSchedule {
  const schedule = rawSchedule && typeof rawSchedule === 'object'
    ? rawSchedule as Record<string, unknown>
    : {}
  const name = String(schedule.name ?? '').trim()
  const scheduleId = String(schedule.schedule_id ?? schedule.id ?? (name || 'schedule')).trim()
  const rawSettings =
    schedule.settings && typeof schedule.settings === 'object' && !Array.isArray(schedule.settings)
      ? schedule.settings as Record<string, unknown>
      : {}

  return {
    schedule_id: scheduleId,
    name: name || 'Integrator schedule',
      connector_id: String(schedule.connector_id ?? '').trim(),
      cron: String(schedule.cron ?? schedule.cron_expression ?? '0 * * * *').trim() || '0 * * * *',
      timezone: String(schedule.timezone ?? previous?.timezone ?? 'UTC').trim() || 'UTC',
      interval_minutes: Math.trunc(Number(schedule.interval_minutes ?? previous?.interval_minutes ?? 60) || 60),
      enabled: typeof schedule.enabled === 'boolean' ? schedule.enabled : true,
      settings: mergeRedactedIntegratorSettings(rawSettings, previous?.settings ?? {}),
    last_run_at: typeof schedule.last_run_at === 'number' ? schedule.last_run_at : previous?.last_run_at ?? null,
    next_run_at: typeof schedule.next_run_at === 'number' ? schedule.next_run_at : previous?.next_run_at ?? null,
  }
}

function buildIntegratorSchedulesPayload(schedules: MockIntegratorSchedule[]): Record<string, unknown> {
  const publicSchedules = schedules.map((schedule) => ({
    ...schedule,
    settings: redactIntegratorSettings(schedule.settings),
  }))
  return {
    schedules: publicSchedules,
    total: publicSchedules.length,
      persistence: {
        enabled: true,
        config_key: 'integrator_schedules',
        sensitive_fields_redacted: true,
      },
      scheduler: {
        mode: 'configured',
        automatic_dispatch: false,
        manual_trigger_supported: true,
      },
    }
  }

function buildIntegratorScheduleTickPayload(
  schedules: MockIntegratorSchedule[],
  dryRun: boolean,
): Record<string, unknown> {
  const tickNow = now + 7200
  const dueSchedules = schedules.filter(
    (schedule) => schedule.enabled && (schedule.next_run_at === null || schedule.next_run_at <= tickNow),
  )
  return {
    dry_run: dryRun,
    executed: !dryRun && dueSchedules.length > 0,
    checked: schedules.length,
    due_count: dueSchedules.length,
    due: dueSchedules.map((schedule) => ({
      schedule_id: schedule.schedule_id,
      schedule: {
        ...schedule,
        settings: redactIntegratorSettings(schedule.settings),
      },
      would_create_task: {
        task_type: 'multi_agent_workflow',
        params: {
          schedule_id: schedule.schedule_id,
          connector_id: schedule.connector_id,
        },
      },
    })),
    skipped: {
      disabled: schedules.filter((schedule) => !schedule.enabled).length,
      not_due: schedules.filter((schedule) => schedule.enabled && schedule.next_run_at !== null && schedule.next_run_at > tickNow).length,
    },
    now: tickNow,
  }
}

async function fulfillJson(route: Route, payload: unknown, status = 200): Promise<void> {
  await route.fulfill({
    status,
    contentType: 'application/json; charset=utf-8',
    body: JSON.stringify(payload),
  })
}

async function fulfillSse(route: Route, body: string): Promise<void> {
  await route.fulfill({
    status: 200,
    contentType: 'text/event-stream; charset=utf-8',
    headers: {
      'cache-control': 'no-cache',
      connection: 'keep-alive',
    },
    body,
  })
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

export async function installAppApiMocks(page: Page): Promise<void> {
  let sessionCounter = 1
  let taskCounter = 1
  let cloudModelApiKeyCounter = 1
  let tavilyApiKey = ''
  const sessions: MockSession[] = []
  const sessionMessages = new Map<string, MockMessagesPayload>()
  const tasks = new Map<string, MockTask>()
  let approvalPolicy: MockApprovalPolicy = {
    enabled: true,
    required_task_types: ['multi_agent_workflow'],
    high_risk_requires_approval: true,
    default_reviewer_role: 'admin',
    updated_at: null,
  }
  const taskPollCounts = new Map<string, number>()
  const decks = new Map<string, MockDeck>([['deck-mock-1', createMockDeck()]])
  const cloudModelApiKeys = new Map<string, string>()
  const identityOrgs: MockIdentityOrg[] = []
  const identityUsers: MockIdentityUser[] = []
  const identityMemberships: MockIdentityMembership[] = []
  const resourceGrants: MockResourceGrant[] = []
  const researchArchives: MockResearchArchive[] = [createMockResearchArchive()]
  let traceEvents: MockTraceEvent[] = [...defaultTraceEvents]
  let auditEvents: MockSecurityAuditEvent[] = [...defaultSecurityAuditEvents]
  const mcpEnvApproved = ['knowledge-base']
  let mcpRuntimeApproved: string[] = []
  let mcpConfig: Record<string, unknown> = {
    connectors: defaultMcpConnectors,
    default_enabled: ['knowledge-base', 'web-search'],
  }
  let integratorConnectors: MockIntegratorConnector[] = [...defaultIntegratorConnectors]
  let integratorAuditEvents: MockIntegratorAuditEvent[] = [...defaultIntegratorAuditEvents]
  let integratorSchedules: MockIntegratorSchedule[] = [...defaultIntegratorSchedules]
  let ssoConfig: MockSsoConfig = {
    enabled: false,
    provider: 'none',
    issuer_url: '',
    authorization_endpoint: '',
    token_endpoint: '',
    jwks_url: '',
    authorization_endpoint_configured: false,
    token_endpoint_configured: false,
    jwks_url_configured: false,
    client_id: '',
    client_id_configured: false,
    client_secret_configured: false,
    allowed_domains: [],
    scopes: ['openid', 'email', 'profile'],
    default_role: 'viewer',
    session_ttl_seconds: 28800,
    callback_path: '/api/auth/sso/callback',
    ready: false,
    mode: 'disabled',
    claim_mapping: {
      user_id: 'sub',
      email: 'email',
      display_name: 'name',
      groups: 'groups',
    },
  }

  const buildMcpApprovalsPayload = (connector?: Record<string, unknown>) => {
    const approved = Array.from(new Set([...mcpEnvApproved, ...mcpRuntimeApproved]))
    const sources = Object.fromEntries(
      approved.map((name) => [
        name,
        [
          ...(mcpEnvApproved.includes(name) ? ['env'] : []),
          ...(mcpRuntimeApproved.includes(name) ? ['runtime'] : []),
        ],
      ]),
    )
    return {
      approved_connectors: approved,
      env_connectors: mcpEnvApproved,
      runtime_connectors: mcpRuntimeApproved,
      persisted_connectors: mcpRuntimeApproved,
      sources,
      persistence: {
        enabled: true,
        config_key: 'mcp_approved_connectors',
      },
      total: approved.length,
      ...(connector ? { connector } : {}),
    }
  }

  const getMcpConfigConnectors = (): MockMcpConnector[] =>
    Array.isArray(mcpConfig.connectors)
      ? mcpConfig.connectors as MockMcpConnector[]
      : defaultMcpConnectors

  const getMcpConfigDefaultEnabled = (): string[] =>
    Array.isArray(mcpConfig.default_enabled)
      ? mcpConfig.default_enabled.filter((item): item is string => typeof item === 'string')
      : ['knowledge-base', 'web-search']

  const buildMcpMarketplacePayload = () => {
    const connectors = getMcpConfigConnectors()
    const grouped = new Map<string, {
      id: string
      label: string
      total: number
      enabled: number
      healthy: number
      requires_approval: number
      connectors: string[]
    }>()
    for (const connector of connectors) {
      const id = connector.category || 'custom'
      const label = id.replace(/[-_]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
      const entry = grouped.get(id) ?? {
        id,
        label,
        total: 0,
        enabled: 0,
        healthy: 0,
        requires_approval: 0,
        connectors: [],
      }
      entry.total += 1
      entry.enabled += connector.enabled ? 1 : 0
      entry.healthy += connector.healthy ? 1 : 0
      entry.requires_approval += connector.requires_approval ? 1 : 0
      entry.connectors.push(connector.name)
      grouped.set(id, entry)
    }
    const categories = Array.from(grouped.values()).sort((a, b) => a.label.localeCompare(b.label))
    return {
      summary: {
        total: connectors.length,
        builtin: connectors.filter((connector) => connector.builtin).length,
        custom: connectors.filter((connector) => !connector.builtin).length,
        enabled: connectors.filter((connector) => connector.enabled).length,
        healthy: connectors.filter((connector) => connector.healthy).length,
        requires_approval: connectors.filter((connector) => connector.requires_approval).length,
        categories: categories.length,
      },
      categories,
    }
  }

  const buildMcpConfigPayload = () => ({
    connectors: getMcpConfigConnectors(),
    config: mcpConfig,
    default_enabled: getMcpConfigDefaultEnabled(),
    persistence: {
      enabled: true,
      config_key: 'mcp_connectors',
    },
    marketplace: buildMcpMarketplacePayload(),
    sensitive_fields_redacted: true,
  })

  const buildMcpRuntimeHealthServers = () => [
    {
      name: 'knowledge-base',
      status: 'healthy',
      healthy: true,
      tool_count: 2,
      tools: ['knowledge_lookup', 'knowledge_diagnostics'],
      duration_ms: 24.5,
      error: null,
    },
    ...(mcpRuntimeApproved.includes('custom-crm')
      ? [
          {
            name: 'custom-crm',
            status: 'healthy',
            healthy: true,
            tool_count: 1,
            tools: ['crm_sync_preview'],
            duration_ms: 51.2,
            error: null,
          },
        ]
      : []),
  ]

  const buildMcpRuntimeHealthSummary = (servers: ReturnType<typeof buildMcpRuntimeHealthServers>) => ({
    total: servers.length,
    healthy: servers.filter((server) => server.healthy).length,
    unhealthy: servers.filter((server) => !server.healthy).length,
    tool_count: servers.reduce((sum, server) => sum + server.tool_count, 0),
    status_counts: {
      healthy: servers.filter((server) => server.status === 'healthy').length,
    },
    alert_count: 0,
    unhealthy_connectors: [],
    slow_connectors: [],
  })

  const buildMcpRuntimeHealthHistory = () => {
    const servers = buildMcpRuntimeHealthServers()
    const summary = buildMcpRuntimeHealthSummary(servers)
    return [
      {
        timestamp: now + 120,
        status: 'ok',
        summary,
        servers: servers.map((server) => ({
          name: server.name,
          status: server.status,
          healthy: server.healthy,
          tool_count: server.tool_count,
          duration_ms: server.duration_ms,
          error: server.error,
        })),
      },
      {
        timestamp: now + 60,
        status: 'degraded',
        summary: {
          total: 2,
          healthy: 1,
          unhealthy: 1,
          tool_count: 2,
          status_counts: { healthy: 1, error: 1 },
          alert_count: 1,
          unhealthy_connectors: ['custom-crm'],
          slow_connectors: [],
        },
        servers: [
          {
            name: 'knowledge-base',
            status: 'healthy',
            healthy: true,
            tool_count: 2,
            duration_ms: 24.5,
            error: null,
          },
          {
            name: 'custom-crm',
            status: 'error',
            healthy: false,
            tool_count: 0,
            duration_ms: 250.4,
            error: 'Mock CRM handshake failed',
          },
        ],
      },
      {
        timestamp: now,
        status: 'ok',
        summary: {
          total: 1,
          healthy: 1,
          unhealthy: 0,
          tool_count: 2,
          status_counts: { healthy: 1 },
          alert_count: 0,
          unhealthy_connectors: [],
          slow_connectors: [],
        },
        servers: [
          {
            name: 'knowledge-base',
            status: 'healthy',
            healthy: true,
            tool_count: 2,
            duration_ms: 20.1,
            error: null,
          },
        ],
      },
    ]
  }

  const recomputeSsoConfig = (patch: Partial<MockSsoConfig>): void => {
    ssoConfig = {
      ...ssoConfig,
      ...patch,
    }
    ssoConfig.authorization_endpoint_configured = ssoConfig.authorization_endpoint.trim().length > 0
    ssoConfig.token_endpoint_configured = ssoConfig.token_endpoint.trim().length > 0
    ssoConfig.jwks_url_configured = ssoConfig.jwks_url.trim().length > 0
    ssoConfig.client_id_configured = ssoConfig.client_id.trim().length > 0
    ssoConfig.enabled = ssoConfig.provider === 'oidc'
    ssoConfig.ready =
      ssoConfig.enabled &&
      ssoConfig.issuer_url.trim().length > 0 &&
      ssoConfig.authorization_endpoint_configured &&
      ssoConfig.token_endpoint_configured &&
      ssoConfig.jwks_url_configured &&
      ssoConfig.client_id_configured
    ssoConfig.mode = ssoConfig.enabled
      ? ssoConfig.ready
        ? 'oidc_configured'
        : 'incomplete'
      : 'disabled'
  }

  const ensureSessionMessages = (sessionId: string): MockMessagesPayload => {
    const existing = sessionMessages.get(sessionId)
    if (existing) return existing
    const next = emptyMessagesPayload()
    sessionMessages.set(sessionId, next)
    return next
  }

  const upsertResearchArchiveForTask = (task: MockTask, query: string): MockResearchArchive => {
    const existingIndex = researchArchives.findIndex((archive) => archive.task_id === task.task_id)
    const archive = createMockResearchArchive({
      archiveId: `research-archive-${task.task_id}`,
      title: `Research archive for ${query}`,
      query,
      sessionId: task.session_id ?? 'session-archive-smoke',
      taskId: task.task_id,
      artifactId: `artifact-research-archive-${task.task_id}`,
    })
    if (existingIndex >= 0) {
      researchArchives[existingIndex] = archive
    } else {
      researchArchives.unshift(archive)
    }
    return archive
  }

  const finalizeTask = (task: MockTask): MockTask => {
    const params = task.params ?? {}

    if (task.task_type === 'web_research') {
      const query = typeof params.query === 'string' ? params.query : 'Untitled research'
      const answerGroupId =
        typeof params.answer_group_id === 'string' ? params.answer_group_id : undefined
      const archive = upsertResearchArchiveForTask(task, query)
      return {
        ...task,
        status: 'completed',
        progress: 100,
        result: `Research summary for: ${query}`,
        params: {
          ...params,
          research_sources: buildResearchSources(query, answerGroupId),
          research_archive_artifact_id: archive.artifact_id,
        },
        updated_at: now + taskCounter,
      }
    }

    if (task.task_type === 'multi_agent_workflow') {
      const query = typeof params.user_request === 'string' ? params.user_request : 'Untitled workflow'
      const dataFiles = Array.isArray(params.data_files)
        ? params.data_files
            .map((item) =>
              item && typeof item === 'object' && 'name' in item
                ? String((item as { name?: unknown }).name ?? '')
                : '',
            )
            .filter(Boolean)
        : []
      const result =
        dataFiles.length > 0
          ? `Mock data workflow completed for: ${query}\n\nFiles: ${dataFiles.join(', ')}`
          : `Mock workflow completed for: ${query}`
      return {
        ...task,
        status: 'completed',
        progress: 100,
        result,
        updated_at: now + taskCounter,
      }
    }

    if (task.task_type === 'generate_report') {
      const answerGroupId =
        typeof params.answer_group_id === 'string' ? params.answer_group_id : 'unknown-answer-group'
      const panelId = typeof params.panel_id === 'string' ? params.panel_id : 'panel-1'
      const reportArtifactId = `artifact-report-${task.task_id}`
      const archive = researchArchives[0]
      return {
        ...task,
        status: 'completed',
        progress: 100,
        result: 'Report preview generated successfully.',
        params: {
          ...params,
          answer_group_id: answerGroupId,
          panel_id: panelId,
          artifact_id: reportArtifactId,
          report_title: 'Mock Research Report',
          report_markdown: [
            '# Mock Research Report',
            '',
            '## Key Findings',
            '- The async task flow completed successfully.',
            '- The report preview can be opened from the assistant message.',
          ].join('\n'),
          claim_evidence_chains: archive?.claim_evidence_chains ?? [],
          paragraph_citations: archive?.paragraph_citations ?? [],
          paragraph_claim_links: archive?.paragraph_claim_links ?? [],
          navigation_index: archive?.navigation_index ?? {},
          citation_graph: archive?.citation_graph,
          conflict_summary: archive?.conflict_summary,
          conflict_review_resolutions: archive?.conflict_review_resolutions ?? [],
          claim_verification_summary: archive?.claim_verification_summary,
        },
        updated_at: now + taskCounter,
      }
    }

    if (task.task_type === 'generate_deck') {
      const deckId = typeof params.deck_id === 'string' ? params.deck_id : 'deck-mock-1'
      const deckTitle = typeof params.deck_title === 'string' ? params.deck_title : 'Mock Deck'
      const answerGroupId =
        typeof params.answer_group_id === 'string' ? params.answer_group_id : 'answer-group-1'
      const panelId = typeof params.panel_id === 'string' ? params.panel_id : 'panel-1'
      decks.set(
        deckId,
        createMockDeck({
          deckId,
          title: deckTitle,
          sessionId: task.session_id ?? 'session-1',
          answerGroupId,
          panelId,
        }),
      )
      return {
        ...task,
        status: 'completed',
        progress: 100,
        result: 'Deck generated successfully.',
        params: {
          ...params,
          deck_id: deckId,
          deck_title: deckTitle,
        },
        updated_at: now + taskCounter,
      }
    }

    return {
      ...task,
      status: 'completed',
      progress: 100,
      result: task.result ?? `${task.task_type} completed successfully.`,
      updated_at: now + taskCounter,
    }
  }

  await page.route('**://*/api/**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname
    const method = request.method()

    if (method === 'GET' && path === '/api/integrations/connectors') {
      await fulfillJson(route, buildIntegratorConnectorsPayload(integratorConnectors))
      return
    }

    if (method === 'GET' && path === '/api/integrations/audit') {
      await fulfillJson(route, buildIntegratorAuditPayload(integratorAuditEvents, url.searchParams.get('limit')))
      return
    }

    if (method === 'GET' && path === '/api/integrations/schedules') {
      await fulfillJson(route, buildIntegratorSchedulesPayload(integratorSchedules))
      return
    }

    if (method === 'PUT' && path === '/api/integrations/schedules') {
      const body = (request.postDataJSON() ?? {}) as { schedules?: unknown }
      if (!Array.isArray(body.schedules)) {
        await fulfillJson(route, { detail: 'schedules must be a list' }, 422)
        return
      }

      const previousById = new Map(integratorSchedules.map((schedule) => [schedule.schedule_id ?? '', schedule]))
      integratorSchedules = body.schedules.map((schedule) => {
        const rawSchedule = schedule && typeof schedule === 'object'
          ? schedule as Record<string, unknown>
          : {}
        const id = String(rawSchedule.schedule_id ?? rawSchedule.id ?? rawSchedule.name ?? '').trim()
        return normalizeIntegratorSchedule(schedule, previousById.get(id))
      })
      await fulfillJson(route, buildIntegratorSchedulesPayload(integratorSchedules))
      return
    }

    if (method === 'POST' && path === '/api/integrations/schedules/tick') {
      const body = (request.postDataJSON() ?? {}) as { dry_run?: unknown }
      const dryRun = body.dry_run !== false
      await fulfillJson(route, buildIntegratorScheduleTickPayload(integratorSchedules, dryRun))
      return
    }

    const scheduleTriggerMatch = path.match(/^\/api\/integrations\/schedules\/([^/]+)\/trigger$/)
    if (method === 'POST' && scheduleTriggerMatch) {
      const scheduleId = decodeURIComponent(scheduleTriggerMatch[1])
      const scheduleIndex = integratorSchedules.findIndex((schedule) => schedule.schedule_id === scheduleId)
      if (scheduleIndex < 0) {
        await fulfillJson(route, { detail: `Unknown schedule: ${scheduleId}` }, 404)
        return
      }
      const triggeredAt = now + integratorAuditEvents.length + 30
        integratorSchedules[scheduleIndex] = {
          ...integratorSchedules[scheduleIndex],
          last_run_at: triggeredAt,
          next_run_at: triggeredAt + (integratorSchedules[scheduleIndex].interval_minutes * 60),
        }
      await fulfillJson(route, {
        ok: true,
        schedule_id: scheduleId,
        status: 'triggered',
        triggered_at: triggeredAt,
        dry_run: false,
        executed: true,
        task: {
          task_id: `mock-task-${scheduleId}`,
          status: 'pending',
          task_type: 'multi_agent_workflow',
        },
      })
      return
    }

    if (method === 'PUT' && path === '/api/integrations/connectors') {
      const body = (request.postDataJSON() ?? {}) as { connectors?: unknown }
      if (!Array.isArray(body.connectors)) {
        await fulfillJson(route, { detail: 'connectors must be a list' }, 422)
        return
      }

      const previousById = new Map(integratorConnectors.map((connector) => [connector.id ?? '', connector]))
      try {
        integratorConnectors = body.connectors.map((connector) => {
          const rawConnector = connector && typeof connector === 'object'
            ? connector as Record<string, unknown>
            : {}
          const id = String(rawConnector.id ?? rawConnector.name ?? rawConnector.type ?? '').trim()
          return normalizeIntegratorConnector(connector, previousById.get(id))
        })
        integratorAuditEvents = [
          {
            timestamp: now + integratorAuditEvents.length + 21,
            action: 'integrator_connector_save',
            result: 'success',
            connector_id: integratorConnectors[0]?.id ?? '',
            connector_type: integratorConnectors[0]?.type ?? '',
            actor: 'playwright-local',
            request_id: `req-integrator-audit-save-${integratorAuditEvents.length + 1}`,
            details: {
              connector_count: integratorConnectors.length,
              approved_count: integratorConnectors.filter((connector) => connector.approved).length,
              token: 'mock-save-token',
            },
          },
          ...integratorAuditEvents,
        ]
      } catch (error) {
        await fulfillJson(
          route,
          { detail: error instanceof Error ? error.message : 'invalid connector config' },
          400,
        )
        return
      }

      await fulfillJson(route, buildIntegratorConnectorsPayload(integratorConnectors))
      return
    }

    const connectorRotateMatch = path.match(/^\/api\/integrations\/connectors\/([^/]+)\/credentials\/rotate$/)
    if (method === 'POST' && connectorRotateMatch) {
      const connectorId = decodeURIComponent(connectorRotateMatch[1])
      const connectorIndex = integratorConnectors.findIndex((connector) => connector.id === connectorId)
      if (connectorIndex < 0) {
        await fulfillJson(route, { detail: `Unknown connector: ${connectorId}` }, 404)
        return
      }
      const body = (request.postDataJSON() ?? {}) as { settings?: unknown; credentials?: unknown }
      const patchSource = body.settings ?? body.credentials ?? {}
      if (!patchSource || typeof patchSource !== 'object' || Array.isArray(patchSource)) {
        await fulfillJson(route, { detail: 'credentials patch must be an object' }, 422)
        return
      }
      const patch = patchSource as Record<string, unknown>
      const previous = integratorConnectors[connectorIndex]
      integratorConnectors[connectorIndex] = {
        ...previous,
        settings: mergeRedactedIntegratorSettings(
          {
            ...previous.settings,
            ...patch,
          },
          previous.settings,
        ),
      }
      integratorAuditEvents = [
        {
          timestamp: now + integratorAuditEvents.length + 21,
          action: 'integrator_connector_credentials_rotate',
          result: 'success',
          connector_id: previous.id ?? '',
          connector_type: previous.type,
          actor: 'playwright-local',
          request_id: `req-integrator-audit-rotate-${integratorAuditEvents.length + 1}`,
          details: {
            rotated_fields: credentialPatchFields(patch),
            token: 'mock-rotation-token',
            url: 'https://hooks.example.test/rotated',
          },
        },
        ...integratorAuditEvents,
      ]
      await fulfillJson(
        route,
        buildIntegratorCredentialRotationPayload(integratorConnectors[connectorIndex], patch, previous),
      )
      return
    }

    const connectorProbeMatch = path.match(/^\/api\/integrations\/connectors\/([^/]+)\/probe$/)
    if (method === 'POST' && connectorProbeMatch) {
      const connectorId = decodeURIComponent(connectorProbeMatch[1])
      const connector = integratorConnectors.find((item) => item.id === connectorId)
      if (!connector) {
        await fulfillJson(route, { detail: `Unknown connector: ${connectorId}` }, 404)
        return
      }
      const probeOptions = normalizeIntegratorProbeOptions(request.postDataJSON())
      integratorAuditEvents = [
        {
          timestamp: now + integratorAuditEvents.length + 21,
          action: 'integrator_connector_probe',
          result: hasIntegratorEndpoint(connector) ? 'success' : 'warning',
          connector_id: connector.id ?? '',
          connector_type: connector.type,
          actor: 'playwright-local',
          request_id: `req-integrator-audit-probe-${integratorAuditEvents.length + 1}`,
          details: {
            dry_run: probeOptions.mode === 'static',
            probe_mode: probeOptions.mode,
            outbound_request_sent: probeOptions.mode === 'external' && hasIntegratorEndpoint(connector),
            token: 'mock-probe-token',
            url: connector.settings.url ?? '',
          },
        },
        ...integratorAuditEvents,
      ]
      await fulfillJson(route, buildIntegratorConnectorProbePayload(connector, probeOptions))
      return
    }

    if (method === 'POST' && path === '/api/integrations/connectors/test') {
      const body = (request.postDataJSON() ?? {}) as { connector?: unknown } | MockIntegratorConnector
      const rawConnector =
        body && typeof body === 'object' && 'connector' in body ? body.connector : body
      try {
        const connector = normalizeIntegratorConnector(rawConnector)
        integratorAuditEvents = [
          {
            timestamp: now + integratorAuditEvents.length + 21,
            action: 'integrator_connector_test',
            result: hasIntegratorEndpoint(connector) && connector.enabled && connector.approved ? 'success' : 'failed',
            connector_id: connector.id ?? '',
            connector_type: connector.type,
            actor: 'playwright-local',
            request_id: `req-integrator-audit-test-${integratorAuditEvents.length + 1}`,
            details: {
              dry_run: true,
              channel: connector.settings.channel ?? '',
              url: connector.settings.url ?? connector.settings.webhook_url ?? '',
              token: connector.settings.token ?? '',
              client_secret: 'mock-test-client-secret',
            },
          },
          ...integratorAuditEvents,
        ]
        await fulfillJson(route, buildIntegratorConnectorTestPayload(connector))
      } catch (error) {
        await fulfillJson(
          route,
          { detail: error instanceof Error ? error.message : 'invalid connector config' },
          400,
        )
      }
      return
    }

    if (method === 'GET' && path === '/api/connectors/mcp/config') {
      await fulfillJson(route, buildMcpConfigPayload())
      return
    }

    if (method === 'PUT' && path === '/api/connectors/mcp/config') {
      const body = asRecord(request.postDataJSON() ?? {})
      const nextConfig = asRecord(body.config)
      mcpConfig = Object.keys(nextConfig).length > 0 ? nextConfig : body
      await fulfillJson(route, buildMcpConfigPayload())
      return
    }

    if (method === 'GET' && path === '/api/connectors/mcp') {
      await fulfillJson(route, {
        connectors: getMcpConfigConnectors(),
        default_enabled: getMcpConfigDefaultEnabled(),
      })
      return
    }

    if (method === 'GET' && path === '/api/connectors/mcp/approvals') {
      await fulfillJson(route, buildMcpApprovalsPayload())
      return
    }

    if (method === 'GET' && path === '/api/connectors/mcp/runtime-health/history') {
      const limit = Math.min(100, Math.max(1, Number(url.searchParams.get('limit') ?? '10') || 10))
      await fulfillJson(route, {
        history: buildMcpRuntimeHealthHistory().slice(0, limit),
        limit,
      })
      return
    }

    if (method === 'GET' && path === '/api/connectors/mcp/runtime-health') {
      const servers = [
        {
          name: 'knowledge-base',
          status: 'healthy',
          healthy: true,
          tool_count: 2,
          tools: ['knowledge_lookup', 'knowledge_diagnostics'],
          duration_ms: 24.5,
          error: null,
        },
        ...(mcpRuntimeApproved.includes('custom-crm')
          ? [
              {
                name: 'custom-crm',
                status: 'healthy',
                healthy: true,
                tool_count: 1,
                tools: ['crm_sync_preview'],
                duration_ms: 51.2,
                error: null,
              },
            ]
          : []),
      ]
      const summary = {
        total: servers.length,
        healthy: servers.filter((server) => server.healthy).length,
        unhealthy: servers.filter((server) => !server.healthy).length,
        tool_count: servers.reduce((sum, server) => sum + server.tool_count, 0),
        status_counts: {
          healthy: servers.filter((server) => server.status === 'healthy').length,
        },
        alert_count: 0,
        unhealthy_connectors: [],
        slow_connectors: [],
      }
      await fulfillJson(route, {
        status: 'ok',
        servers,
        summary,
        history: [
          {
            timestamp: now + 120,
            status: 'ok',
            summary,
            servers: servers.map((server) => ({
              name: server.name,
              status: server.status,
              healthy: server.healthy,
              tool_count: server.tool_count,
              duration_ms: server.duration_ms,
              error: server.error,
            })),
          },
          {
            timestamp: now + 60,
            status: 'degraded',
            summary: {
              total: 2,
              healthy: 1,
              unhealthy: 1,
              tool_count: 2,
              status_counts: { healthy: 1, error: 1 },
              alert_count: 1,
              unhealthy_connectors: ['custom-crm'],
              slow_connectors: [],
            },
            servers: [
              {
                name: 'knowledge-base',
                status: 'healthy',
                healthy: true,
                tool_count: 2,
                duration_ms: 24.5,
                error: null,
              },
              {
                name: 'custom-crm',
                status: 'error',
                healthy: false,
                tool_count: 0,
                duration_ms: 250.4,
                error: 'Mock CRM handshake failed',
              },
            ],
          },
          {
            timestamp: now,
            status: 'ok',
            summary: {
              total: 1,
              healthy: 1,
              unhealthy: 0,
              tool_count: 2,
              status_counts: { healthy: 1 },
              alert_count: 0,
              unhealthy_connectors: [],
              slow_connectors: [],
            },
            servers: [
              {
                name: 'knowledge-base',
                status: 'healthy',
                healthy: true,
                tool_count: 2,
                duration_ms: 20.1,
                error: null,
              },
            ],
          },
        ],
        history_limit: 20,
      })
      return
    }

    if (method === 'POST' && path === '/api/connectors/mcp/approvals') {
      const body = (request.postDataJSON() ?? {}) as { name?: string }
      const name = typeof body.name === 'string' ? body.name.trim() : ''
      if (!name) {
        await fulfillJson(route, { detail: 'connector name is required' }, 400)
        return
      }
      const before = [...mcpRuntimeApproved]
      if (!mcpRuntimeApproved.includes(name)) {
        mcpRuntimeApproved = [...mcpRuntimeApproved, name]
      }
      await fulfillJson(
        route,
        buildMcpApprovalsPayload({
          name,
          changed: before.join(',') !== mcpRuntimeApproved.join(','),
          runtime_approved: true,
          effective_approved: true,
        }),
      )
      return
    }

    const mcpApprovalMatch = path.match(/^\/api\/connectors\/mcp\/approvals\/([^/]+)$/)
    if (method === 'DELETE' && mcpApprovalMatch) {
      const name = decodeURIComponent(mcpApprovalMatch[1])
      const before = [...mcpRuntimeApproved]
      mcpRuntimeApproved = mcpRuntimeApproved.filter((item) => item !== name)
      await fulfillJson(
        route,
        buildMcpApprovalsPayload({
          name,
          removed: before.join(',') !== mcpRuntimeApproved.join(','),
          runtime_approved: mcpRuntimeApproved.includes(name),
          effective_approved: mcpEnvApproved.includes(name),
        }),
      )
      return
    }

    if (method === 'GET' && path === '/api/workspaces') {
      await fulfillJson(route, {
        workspaces: [{ ...defaultWorkspace, session_count: sessions.length }],
        active_workspace_id: defaultWorkspace.workspace_id,
      })
      return
    }

    if (method === 'GET' && path === '/api/sessions') {
      await fulfillJson(route, { sessions })
      return
    }

    if (method === 'POST' && path === '/api/sessions') {
      const body = (request.postDataJSON() ?? {}) as {
        title?: string
        workspace_id?: string
      }
      const title =
        typeof body.title === 'string' && body.title.trim()
          ? body.title.trim()
          : '新建对话'
      const sessionId = `session-${sessionCounter}`
      sessionCounter += 1
      const session: MockSession = {
        session_id: sessionId,
        title,
        created_at: now + sessionCounter,
        updated_at: now + sessionCounter,
        message_count: 0,
        is_archived: false,
        is_favorite: false,
        is_pinned: false,
        session_order: 0,
        tags: [],
        workspace_id:
          typeof body.workspace_id === 'string' && body.workspace_id.trim()
            ? body.workspace_id.trim()
            : defaultWorkspace.workspace_id,
      }
      sessions.unshift(session)
      ensureSessionMessages(sessionId)
      await fulfillJson(route, {
        session_id: session.session_id,
        title: session.title,
        workspace_id: session.workspace_id,
      })
      return
    }

    if (method === 'GET' && path === '/api/bookmarks') {
      await fulfillJson(route, { bookmarks: [] })
      return
    }

    if (method === 'GET' && path === '/api/prompts') {
      await fulfillJson(route, { prompts: [defaultPrompt] })
      return
    }

    if (method === 'GET' && path === '/api/config') {
      await fulfillJson(route, {
        tavily_api_key_set: tavilyApiKey.trim().length > 0,
      })
      return
    }

    if (method === 'POST' && path === '/api/config') {
      const body = (request.postDataJSON() ?? {}) as {
        tavily_api_key?: string
      }
      if (typeof body.tavily_api_key === 'string') {
        tavilyApiKey = body.tavily_api_key.trim()
      }
      await fulfillJson(route, { ok: true })
      return
    }

    if (method === 'GET' && path === '/api/auth/whoami') {
      await fulfillJson(route, {
        role: 'admin',
        user_id: 'playwright-local',
        is_local: true,
      })
      return
    }

    if (method === 'GET' && path === '/api/security/audit-summary') {
      const limitValue = Number(url.searchParams.get('limit') ?? '100')
      const windowLimit = Math.min(
        500,
        Math.max(1, Number.isFinite(limitValue) && limitValue > 0 ? Math.trunc(limitValue) : 100),
      )
      await fulfillJson(
        route,
        buildSecurityAuditSummary(auditEvents, url.searchParams.get('category') ?? '', windowLimit),
      )
      return
    }

    if (method === 'GET' && path === '/api/security/audit-events') {
      const limitValue = Number(url.searchParams.get('limit') ?? '100')
      const limit = Math.min(
        500,
        Math.max(1, Number.isFinite(limitValue) && limitValue > 0 ? Math.trunc(limitValue) : 100),
      )
      await fulfillJson(
        route,
        buildSecurityAuditEvents({
          events: auditEvents,
          action: url.searchParams.get('action') ?? '',
          category: url.searchParams.get('category') ?? '',
          result: url.searchParams.get('result') ?? '',
          userId: url.searchParams.get('user_id') ?? '',
          since: parseAuditTimestampFilter(url.searchParams.get('since')),
          until: parseAuditTimestampFilter(url.searchParams.get('until')),
          limit,
        }),
      )
      return
    }

    if (method === 'POST' && path === '/api/security/audit-events/cleanup') {
      const body = (request.postDataJSON() ?? {}) as {
        keep_latest?: number
        dry_run?: boolean
      }
      const keepLatestValue = Number(url.searchParams.get('keep_latest') ?? body.keep_latest ?? '0')
      const keepLatest = Math.min(
        500,
        Math.max(0, Number.isFinite(keepLatestValue) ? Math.trunc(keepLatestValue) : 0),
      )
      const dryRun = url.searchParams.get('dry_run') === 'true' || body.dry_run === true
      const beforeCount = auditEvents.length
      const remainingEvents = keepLatest <= 0 ? [] : auditEvents.slice(-keepLatest)
      const deletedCount = Math.max(0, beforeCount - remainingEvents.length)
      if (!dryRun) {
        auditEvents = remainingEvents
      }
      await fulfillJson(route, {
        keep_latest: keepLatest,
        dry_run: dryRun,
        deleted_count: deletedCount,
        remaining_count: dryRun ? beforeCount : auditEvents.length,
        memory_deleted_count: deletedCount,
        memory_remaining_count: dryRun ? beforeCount : auditEvents.length,
        history_limit: 500,
        includes_cleanup_event: false,
      })
      return
    }

    if (method === 'GET' && path === '/api/operations/traces') {
      const limit = Math.min(500, Math.max(1, Number(url.searchParams.get('limit') ?? '100') || 100))
      const filters = {
        event: url.searchParams.get('event')?.trim() ?? '',
        name: url.searchParams.get('name')?.trim() ?? '',
        trace_id: url.searchParams.get('trace_id')?.trim() ?? '',
        span_id: url.searchParams.get('span_id')?.trim() ?? '',
      }
      const events = traceEvents
        .filter((event) => !filters.event || event.event === filters.event)
        .filter((event) => !filters.name || event.name === filters.name)
        .filter((event) => !filters.trace_id || event.trace_id === filters.trace_id)
        .filter((event) => !filters.span_id || event.span_id === filters.span_id)
        .slice(-limit)
      await fulfillJson(route, {
        events,
        summary: {
          returned: events.length,
          limit,
          error_events: events.filter((event) => event.event === 'error').length,
          filters: Object.fromEntries(Object.entries(filters).filter(([, value]) => value)),
        },
      })
      return
    }

    if (method === 'DELETE' && path === '/api/operations/traces') {
      traceEvents = []
      await fulfillJson(route, { ok: true, cleared: true })
      return
    }

    if (method === 'GET' && path === '/api/auth/sso/config') {
      await fulfillJson(route, ssoConfig)
      return
    }

    if (method === 'PUT' && path === '/api/auth/sso/config') {
      const body = (request.postDataJSON() ?? {}) as {
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
      recomputeSsoConfig({
        provider: typeof body.provider === 'string' ? body.provider.trim() || 'none' : ssoConfig.provider,
        issuer_url: typeof body.issuer_url === 'string' ? body.issuer_url.trim() : ssoConfig.issuer_url,
        authorization_endpoint:
          typeof body.authorization_endpoint === 'string'
            ? body.authorization_endpoint.trim()
            : ssoConfig.authorization_endpoint,
        token_endpoint:
          typeof body.token_endpoint === 'string'
            ? body.token_endpoint.trim()
            : ssoConfig.token_endpoint,
        jwks_url: typeof body.jwks_url === 'string' ? body.jwks_url.trim() : ssoConfig.jwks_url,
        client_id: typeof body.client_id === 'string' ? body.client_id.trim() : ssoConfig.client_id,
        allowed_domains:
          typeof body.allowed_domains === 'string'
            ? body.allowed_domains
                .split(',')
                .map((item) => item.trim().toLowerCase())
                .filter(Boolean)
            : ssoConfig.allowed_domains,
        scopes:
          typeof body.scopes === 'string'
            ? body.scopes
                .replaceAll(',', ' ')
                .split(/\s+/)
                .map((item) => item.trim())
                .filter(Boolean)
            : ssoConfig.scopes,
        default_role:
          typeof body.default_role === 'string' ? body.default_role.trim() || 'viewer' : ssoConfig.default_role,
        session_ttl_seconds:
          typeof body.session_ttl_seconds === 'number'
            ? body.session_ttl_seconds
            : ssoConfig.session_ttl_seconds,
        client_secret_configured:
          body.clear_client_secret === true
            ? false
            : typeof body.client_secret === 'string' && body.client_secret.trim().length > 0
              ? true
              : ssoConfig.client_secret_configured,
      })
      await fulfillJson(route, ssoConfig)
      return
    }

    if (method === 'GET' && path === '/api/auth/sso/login') {
      const authUrl = new URL(ssoConfig.authorization_endpoint || 'https://idp.example.com/oauth2/v1/authorize')
      authUrl.searchParams.set('client_id', ssoConfig.client_id || 'insightdesk')
      authUrl.searchParams.set('response_type', 'code')
      authUrl.searchParams.set('scope', ssoConfig.scopes.join(' '))
      authUrl.searchParams.set('state', 'playwright-state')
      authUrl.searchParams.set('nonce', 'playwright-nonce')
      authUrl.searchParams.set('code_challenge', 'playwright-challenge')
      authUrl.searchParams.set('code_challenge_method', 'S256')
      authUrl.searchParams.set(
        'redirect_uri',
        'http://127.0.0.1:4173/api/auth/sso/callback?response_mode=fragment',
      )
      await fulfillJson(route, {
        authorization_url: authUrl.toString(),
        state: 'playwright-state',
        nonce: 'playwright-nonce',
        code_challenge_method: 'S256',
        redirect_uri: 'http://127.0.0.1:4173/api/auth/sso/callback?response_mode=fragment',
        scopes: ssoConfig.scopes,
      })
      return
    }

    if (method === 'GET' && path === '/api/identity') {
      await fulfillJson(route, {
        organizations: identityOrgs,
        users: identityUsers,
        memberships: identityMemberships,
      })
      return
    }

    if (method === 'POST' && path === '/api/identity/orgs') {
      const body = (request.postDataJSON() ?? {}) as {
        org_id?: string
        name?: string
        description?: string
      }
      const orgId = typeof body.org_id === 'string' ? body.org_id.trim() : ''
      const existing = identityOrgs.find((item) => item.org_id === orgId)
      const nextOrg: MockIdentityOrg = {
        org_id: orgId,
        name: typeof body.name === 'string' ? body.name.trim() : '',
        description: typeof body.description === 'string' ? body.description.trim() : '',
        created_at: existing?.created_at ?? now + identityOrgs.length + 1,
        updated_at: now + identityOrgs.length + 1,
      }
      if (existing) {
        Object.assign(existing, nextOrg)
      } else {
        identityOrgs.unshift(nextOrg)
      }
      await fulfillJson(route, nextOrg)
      return
    }

    if (method === 'POST' && path === '/api/identity/users') {
      const body = (request.postDataJSON() ?? {}) as {
        user_id?: string
        display_name?: string
        email?: string
      }
      const userId = typeof body.user_id === 'string' ? body.user_id.trim() : ''
      const existing = identityUsers.find((item) => item.user_id === userId)
      const nextUser: MockIdentityUser = {
        user_id: userId,
        display_name: typeof body.display_name === 'string' ? body.display_name.trim() : '',
        email: typeof body.email === 'string' ? body.email.trim() : '',
        created_at: existing?.created_at ?? now + identityUsers.length + 1,
        updated_at: now + identityUsers.length + 1,
      }
      if (existing) {
        Object.assign(existing, nextUser)
      } else {
        identityUsers.unshift(nextUser)
      }
      await fulfillJson(route, nextUser)
      return
    }

    if (method === 'POST' && path === '/api/identity/memberships') {
      const body = (request.postDataJSON() ?? {}) as {
        org_id?: string
        user_id?: string
        role?: MockIdentityMembership['role']
      }
      const orgId = typeof body.org_id === 'string' ? body.org_id.trim() : ''
      const userId = typeof body.user_id === 'string' ? body.user_id.trim() : ''
      const existing = identityMemberships.find(
        (item) => item.org_id === orgId && item.user_id === userId,
      )
      const nextMembership: MockIdentityMembership = {
        org_id: orgId,
        user_id: userId,
        role: body.role ?? 'viewer',
        created_at: existing?.created_at ?? now + identityMemberships.length + 1,
        updated_at: now + identityMemberships.length + 1,
      }
      if (existing) {
        Object.assign(existing, nextMembership)
      } else {
        identityMemberships.unshift(nextMembership)
      }
      await fulfillJson(route, nextMembership)
      return
    }

    if (method === 'GET' && path === '/api/access/resource-grants') {
      const resourceType = url.searchParams.get('resource_type')?.trim() ?? ''
      const resourceId = url.searchParams.get('resource_id')?.trim() ?? ''
      const role = url.searchParams.get('role')?.trim() ?? ''
      const subjectType = url.searchParams.get('subject_type')?.trim() ?? ''
      const userId = url.searchParams.get('user_id')?.trim() ?? ''
      const orgId = url.searchParams.get('org_id')?.trim() ?? ''
      const limit = Number(url.searchParams.get('limit') ?? '20')
      const offset = Number(url.searchParams.get('offset') ?? '0')
      const filtered = resourceGrants.filter((item) => {
        if (resourceType && item.resource_type !== resourceType) return false
        if (resourceId && item.resource_id !== resourceId) return false
        if (role && item.role !== role) return false
        if (subjectType === 'user' && !item.user_id) return false
        if (subjectType === 'org' && !item.org_id) return false
        if (userId && item.user_id !== userId) return false
        if (orgId && item.org_id !== orgId) return false
        return true
      })
      const pageItems = filtered.slice(offset, offset + limit)
      await fulfillJson(route, {
        grants: pageItems,
        total: filtered.length,
        limit,
        offset,
        returned: pageItems.length,
      })
      return
    }

    if (method === 'POST' && path === '/api/access/resource-grants') {
      const body = (request.postDataJSON() ?? {}) as {
        resource_type?: string
        resource_id?: string
        org_id?: string
        user_id?: string
        role?: MockResourceGrant['role']
      }
      const keyMatch = (item: MockResourceGrant) =>
        item.resource_type === (body.resource_type ?? '') &&
        item.resource_id === (body.resource_id ?? '') &&
        (item.user_id ?? '') === (body.user_id ?? '') &&
        (item.org_id ?? '') === (body.org_id ?? '')
      const existing = resourceGrants.find(keyMatch)
      const nextGrant: MockResourceGrant = {
        resource_type: typeof body.resource_type === 'string' ? body.resource_type.trim() : '',
        resource_id: typeof body.resource_id === 'string' ? body.resource_id.trim() : '',
        ...(typeof body.user_id === 'string' && body.user_id.trim() ? { user_id: body.user_id.trim() } : {}),
        ...(typeof body.org_id === 'string' && body.org_id.trim() ? { org_id: body.org_id.trim() } : {}),
        role: body.role ?? 'viewer',
        created_at: existing?.created_at ?? now + resourceGrants.length + 1,
        updated_at: now + resourceGrants.length + 1,
      }
      if (existing) {
        Object.assign(existing, nextGrant)
      } else {
        resourceGrants.unshift(nextGrant)
      }
      await fulfillJson(route, nextGrant)
      return
    }

    if (method === 'DELETE' && path === '/api/access/resource-grants') {
      const body = (request.postDataJSON() ?? {}) as {
        resource_type?: string
        resource_id?: string
        org_id?: string
        user_id?: string
      }
      const index = resourceGrants.findIndex((item) =>
        item.resource_type === (body.resource_type ?? '') &&
        item.resource_id === (body.resource_id ?? '') &&
        (item.user_id ?? '') === (body.user_id ?? '') &&
        (item.org_id ?? '') === (body.org_id ?? '')
      )
      if (index >= 0) {
        resourceGrants.splice(index, 1)
      }
      await fulfillJson(route, { ok: true })
      return
    }

    if (method === 'POST' && path === '/api/config/cloud-model-api-key') {
      const body = (request.postDataJSON() ?? {}) as {
        api_key?: string
        api_key_ref?: string
      }
      const apiKey = typeof body.api_key === 'string' ? body.api_key.trim() : ''
      if (!apiKey) {
        await fulfillJson(route, { detail: 'API key is required' }, 400)
        return
      }
      const apiKeyRef =
        typeof body.api_key_ref === 'string' && body.api_key_ref.trim()
          ? body.api_key_ref.trim()
          : `cloud-key-${cloudModelApiKeyCounter++}`
      cloudModelApiKeys.set(apiKeyRef, apiKey)
      await fulfillJson(route, {
        api_key_ref: apiKeyRef,
        api_key_set: true,
      })
      return
    }

    const cloudModelApiKeyMatch = path.match(/^\/api\/config\/cloud-model-api-key\/([^/]+)$/)
    if (method === 'DELETE' && cloudModelApiKeyMatch) {
      const apiKeyRef = decodeURIComponent(cloudModelApiKeyMatch[1])
      cloudModelApiKeys.delete(apiKeyRef)
      await route.fulfill({
        status: 204,
        body: '',
      })
      return
    }

    if (method === 'GET' && path === '/api/models/ollama') {
      await fulfillJson(route, { models: ['qwen3.5-2B:latest'] })
      return
    }

    if (method === 'GET' && path === '/api/research/archives') {
      const q = url.searchParams.get('q')?.trim().toLowerCase() ?? ''
      const sessionId = url.searchParams.get('session_id')?.trim() ?? ''
      const taskId = url.searchParams.get('task_id')?.trim() ?? ''
      const limitRaw = Number(url.searchParams.get('limit') ?? '20')
      const limit = Number.isFinite(limitRaw) ? Math.max(1, Math.min(100, Math.floor(limitRaw))) : 20
      const filtered = researchArchives.filter((archive) => {
        if (sessionId && archive.session_id !== sessionId) return false
        if (taskId && archive.task_id !== taskId) return false
        if (!q) return true

        const haystack = [
          archive.title,
          archive.query,
          archive.archive_id,
          archive.artifact_id ?? '',
          ...archive.claim_evidence_chains.map((chain) => String(chain.claim_text ?? '')),
          JSON.stringify(archive.paragraph_citations),
          JSON.stringify(archive.citation_graph),
          JSON.stringify(archive.conflict_summary),
          ...archive.sources.flatMap((source) => [
            String(source.title ?? ''),
            String(source.url ?? ''),
            String(source.domain ?? ''),
          ]),
        ]
          .join(' ')
          .toLowerCase()

        return haystack.includes(q)
      })

      await fulfillJson(route, {
        archives: filtered.slice(0, limit),
        conflict_groups: filtered.flatMap((archive) => {
          const summary = archive.conflict_summary as { conflicts?: Array<Record<string, unknown>> }
          return (summary.conflicts ?? []).map((conflict, index) => ({
            group_id: `mock-conflict-group-${archive.archive_id}-${index + 1}`,
            normalized_claim: String(conflict.claim_text ?? conflict.claim_id ?? '').toLowerCase(),
            normalized_source: Array.isArray(conflict.source_ids)
              ? conflict.source_ids.join(' ').toLowerCase()
              : '',
            normalized_conflict_text: String(conflict.text ?? '').toLowerCase(),
            conflict_text: String(conflict.text ?? ''),
            claim_ids: [String(conflict.claim_id ?? '')].filter(Boolean),
            source_ids: Array.isArray(conflict.source_ids)
              ? conflict.source_ids.filter((item): item is string => typeof item === 'string')
              : [],
            review_statuses: [String(conflict.review_status ?? 'unreviewed')],
            total: 1,
            archives: [
              {
                archive_id: archive.archive_id,
                artifact_id: archive.artifact_id,
                title: archive.title,
                claim_id: conflict.claim_id,
                conflict_id: conflict.conflict_id,
                review_status: conflict.review_status ?? 'unreviewed',
              },
            ],
          }))
        }),
        total: filtered.length,
        limit,
      })
      return
    }

    const reportDownloadMatch = path.match(/^\/api\/reports\/download\/([^/]+)$/)
    if (method === 'GET' && reportDownloadMatch) {
      const sessionId = decodeURIComponent(reportDownloadMatch[1])
      const session = sessions.find((item) => item.session_id === sessionId)
      if (!session) {
        await fulfillJson(route, { detail: `Unknown session: ${sessionId}` }, 404)
        return
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        body: 'mock report export',
      })
      return
    }

    const messagesMatch = path.match(/^\/api\/sessions\/([^/]+)\/messages$/)
    if (method === 'GET' && messagesMatch) {
      const sessionId = decodeURIComponent(messagesMatch[1])
      await fulfillJson(route, ensureSessionMessages(sessionId))
      return
    }

    if (method === 'POST' && path === '/api/chat/parallel') {
      const body = (request.postDataJSON() ?? {}) as {
        session_id?: string
        message?: string
        answer_group_id?: string
        models?: Array<{ panel_id?: string; model?: string }>
      }
      const prompt =
        typeof body.message === 'string' && body.message.trim()
          ? body.message.trim()
          : 'Empty prompt'
      const models =
        Array.isArray(body.models) && body.models.length > 0
          ? body.models
          : [{ panel_id: 'panel-1', model: 'qwen3.5-2B:latest' }]

      if (typeof body.session_id === 'string' && body.session_id.trim()) {
        const session = sessions.find((item) => item.session_id === body.session_id)
        if (session) {
          session.message_count = 2
          session.updated_at = now + sessionCounter
        }
        ensureSessionMessages(body.session_id)
      }

      const stream = [
        ...models.flatMap((model, index) => {
          const panelId =
            typeof model.panel_id === 'string' && model.panel_id.trim()
              ? model.panel_id
              : `panel-${index + 1}`
          return [
            `data: ${JSON.stringify({
              type: 'chunk',
              panel_id: panelId,
              answer_group_id: body.answer_group_id,
              content: `Mock answer for: ${prompt}`,
            })}`,
            `data: ${JSON.stringify({
              type: 'done',
              panel_id: panelId,
              answer_group_id: body.answer_group_id,
            })}`,
          ]
        }),
        `data: ${JSON.stringify({ type: 'all_done' })}`,
      ].join('\n\n') + '\n\n'

      await fulfillSse(route, stream)
      return
    }

    if (method === 'POST' && path === '/api/tasks') {
      const body = (request.postDataJSON() ?? {}) as {
        task_type?: string
        params?: Record<string, unknown>
        session_id?: string
      }
      const taskId = `task-${taskCounter}`
      taskCounter += 1
      const task: MockTask = {
        task_id: taskId,
        task_type:
          typeof body.task_type === 'string' && body.task_type.trim()
            ? body.task_type.trim()
            : 'task',
        status: 'pending',
        progress: 5,
        params: body.params ?? {},
        session_id:
          typeof body.session_id === 'string' && body.session_id.trim()
            ? body.session_id.trim()
            : null,
        created_at: now + taskCounter,
        updated_at: now + taskCounter,
      }
      tasks.set(taskId, task)
      taskPollCounts.set(taskId, 0)
      await fulfillJson(route, task)
      return
    }

    if (method === 'POST' && path === '/api/tasks/multi-agent-workflow') {
      const body = (request.postDataJSON() ?? {}) as {
        user_request?: string
        session_id?: string
      } & Record<string, unknown>
      const userRequest = typeof body.user_request === 'string' ? body.user_request.trim() : ''
      const startsAtApprovalGate = userRequest.toLowerCase().includes('approval')
      const taskId = `task-${taskCounter}`
      taskCounter += 1
      const task: MockTask = {
        task_id: taskId,
        task_type: 'multi_agent_workflow',
        status: startsAtApprovalGate ? 'waiting_approval' : 'pending',
        progress: startsAtApprovalGate ? 55 : 5,
        params: startsAtApprovalGate
          ? {
              ...body,
              approval_title: 'Review agent execution plan',
              approval_reason: 'The workflow is ready to run a high-impact multi-agent plan.',
              approval_step_id: 'plan_review',
            }
          : body,
        session_id:
          typeof body.session_id === 'string' && body.session_id.trim()
            ? body.session_id.trim()
            : null,
        created_at: now + taskCounter,
        updated_at: now + taskCounter,
      }
      tasks.set(taskId, task)
      taskPollCounts.set(taskId, 0)
      await fulfillJson(route, task)
      return
    }

    if (method === 'POST' && path === '/api/tasks/approvals/batch') {
      const body = (request.postDataJSON() ?? {}) as {
        task_ids?: unknown
        decision?: string
        reviewer?: string
        comment?: string
      }
      if (body.decision !== 'approved' && body.decision !== 'rejected') {
        await fulfillJson(route, { detail: 'Decision must be approved or rejected.' }, 400)
        return
      }
      if (!Array.isArray(body.task_ids) || body.task_ids.length === 0) {
        await fulfillJson(route, { detail: 'task_ids must be a non-empty array.' }, 400)
        return
      }

      const decision: MockApprovalDecision = body.decision
      const reviewer = typeof body.reviewer === 'string' ? body.reviewer.trim() : ''
      const comment = typeof body.comment === 'string' ? body.comment.trim() : ''
      const results = body.task_ids.map((rawTaskId) => {
        const taskId = typeof rawTaskId === 'string' ? rawTaskId.trim() : ''
        const existing = taskId ? tasks.get(taskId) : undefined
        if (!taskId || !existing) {
          return {
            task_id: taskId,
            ok: false,
            succeeded: false,
            success: false,
            error: `Unknown task: ${taskId}`,
          }
        }
        if (existing.task_type !== 'multi_agent_workflow') {
          return {
            task_id: taskId,
            ok: false,
            succeeded: false,
            success: false,
            error: 'Only multi_agent_workflow tasks can be approved in batch.',
          }
        }
        if (existing.status !== 'waiting_approval') {
          return {
            task_id: taskId,
            ok: false,
            succeeded: false,
            success: false,
            status: existing.status,
            error: 'Task is not waiting for approval.',
          }
        }

        taskCounter += 1
        const nextTask = applyMockApproval(existing, decision, now + taskCounter, reviewer, comment)
        tasks.set(taskId, nextTask)
        return {
          task_id: taskId,
          ok: true,
          succeeded: true,
          success: true,
          status: nextTask.status,
          task: nextTask,
        }
      })
      const succeeded = results.filter((result) => result.ok).length
      await fulfillJson(route, {
        total: results.length,
        succeeded,
        failed: results.length - succeeded,
        results,
      })
      return
    }

    if (method === 'GET' && path === '/api/tasks/approval-policy') {
      await fulfillJson(route, approvalPolicy)
      return
    }

    if (method === 'PUT' && path === '/api/tasks/approval-policy') {
      const body = (request.postDataJSON() ?? {}) as Partial<MockApprovalPolicy>
      taskCounter += 1
      approvalPolicy = {
        enabled:
          typeof body.enabled === 'boolean' ? body.enabled : approvalPolicy.enabled,
        required_task_types: Array.isArray(body.required_task_types)
          ? body.required_task_types.filter(
              (taskType): taskType is string =>
                typeof taskType === 'string' && taskType.trim().length > 0,
            )
          : approvalPolicy.required_task_types,
        high_risk_requires_approval:
          typeof body.high_risk_requires_approval === 'boolean'
            ? body.high_risk_requires_approval
            : approvalPolicy.high_risk_requires_approval,
        default_reviewer_role:
          typeof body.default_reviewer_role === 'string' && body.default_reviewer_role.trim()
            ? body.default_reviewer_role.trim()
            : approvalPolicy.default_reviewer_role,
        updated_at: now + taskCounter,
      }
      await fulfillJson(route, approvalPolicy)
      return
    }

    const approvalMatch = path.match(/^\/api\/tasks\/([^/]+)\/approval$/)
    if (method === 'POST' && approvalMatch) {
      const taskId = decodeURIComponent(approvalMatch[1])
      const existing = tasks.get(taskId)
      if (!existing) {
        await fulfillJson(route, { detail: `Unknown task: ${taskId}` }, 404)
        return
      }

      const body = (request.postDataJSON() ?? {}) as {
        decision?: string
        reviewer?: string
        comment?: string
      }
      if (body.decision !== 'approved' && body.decision !== 'rejected') {
        await fulfillJson(route, { detail: 'Decision must be approved or rejected.' }, 400)
        return
      }

      const reviewer = typeof body.reviewer === 'string' ? body.reviewer.trim() : ''
      const comment = typeof body.comment === 'string' ? body.comment.trim() : ''
      taskCounter += 1
      const nextTask = applyMockApproval(existing, body.decision, now + taskCounter, reviewer, comment)
      tasks.set(taskId, nextTask)
      await fulfillJson(route, nextTask)
      return
    }

    const taskMatch = path.match(/^\/api\/tasks\/([^/]+)$/)
    if (method === 'GET' && taskMatch) {
      const taskId = decodeURIComponent(taskMatch[1])
      const existing = tasks.get(taskId)
      if (!existing) {
        await fulfillJson(route, { detail: `Unknown task: ${taskId}` }, 404)
        return
      }

      const pollCount = (taskPollCounts.get(taskId) ?? 0) + 1
      taskPollCounts.set(taskId, pollCount)

      const nextTask =
        existing.status === 'pending' || existing.status === 'running'
          ? finalizeTask(existing)
          : existing
      tasks.set(taskId, nextTask)
      await fulfillJson(route, nextTask)
      return
    }

    const regenerateDeckSlideMatch = path.match(/^\/api\/decks\/([^/]+)\/slides\/([^/]+)\/regenerate$/)
    if (method === 'POST' && regenerateDeckSlideMatch) {
      const deckId = decodeURIComponent(regenerateDeckSlideMatch[1])
      const slideId = decodeURIComponent(regenerateDeckSlideMatch[2])
      const existing = decks.get(deckId)
      if (!existing) {
        await fulfillJson(route, { detail: `Unknown deck: ${deckId}` }, 404)
        return
      }

      const nextDeck: MockDeck = {
        ...existing,
        slides: existing.slides.map((slide) =>
          slide.id === slideId
            ? {
                ...slide,
                title: `${slide.title} (Regenerated)`,
                blocks: slide.blocks.map((block, index) =>
                  index === 0 && block.kind === 'paragraph'
                    ? {
                        ...block,
                        content: {
                          ...block.content,
                          text: 'This slide was regenerated by the mock API.',
                        },
                      }
                    : block,
                ),
                status: {
                  ...slide.status,
                  dirty: false,
                },
              }
            : slide,
        ),
      }
      decks.set(deckId, nextDeck)
      await fulfillJson(route, nextDeck)
      return
    }

    const exportDeckMatch = path.match(/^\/api\/decks\/([^/]+)\/export$/)
    if (method === 'GET' && exportDeckMatch) {
      const deckId = decodeURIComponent(exportDeckMatch[1])
      const deck = decks.get(deckId)
      if (!deck) {
        await fulfillJson(route, { detail: `Unknown deck: ${deckId}` }, 404)
        return
      }
      const allowUnsafeExport = url.searchParams.get('allow_unsafe_export') === 'true'
      if (!deck.citation_validation.can_export && !allowUnsafeExport) {
        await fulfillJson(
          route,
          {
            detail: 'Deck export is blocked until citation validation issues are resolved.',
            citation_validation: deck.citation_validation,
            evidence_review: deck.generation.evidence_review,
            export_gate: {
              status: 'blocked',
              reason: 'citation_validation_failed',
              can_export: false,
              allow_unsafe_export: false,
              override_param: 'allow_unsafe_export=true',
            },
          },
          409,
        )
        return
      }
      await route.fulfill({
        status: 200,
        contentType: 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        body: 'mock deck export',
      })
      return
    }

    const deckShareMatch = path.match(/^\/api\/decks\/([^/]+)\/share$/)
    if (method === 'POST' && deckShareMatch) {
      const deckId = decodeURIComponent(deckShareMatch[1])
      if (!decks.has(deckId)) {
        await fulfillJson(route, { detail: `Unknown deck: ${deckId}` }, 404)
        return
      }
      await fulfillJson(route, {
        resource_type: 'deck',
        resource_id: deckId,
        share_token: 'share-token-mock',
        share_url: `https://example.com/shared/decks/${deckId}`,
      })
      return
    }

    const deckMatch = path.match(/^\/api\/decks\/([^/]+)$/)
    if (deckMatch) {
      const deckId = decodeURIComponent(deckMatch[1])
      const existing = decks.get(deckId)
      if (!existing) {
        await fulfillJson(route, { detail: `Unknown deck: ${deckId}` }, 404)
        return
      }

      if (method === 'GET') {
        await fulfillJson(route, existing)
        return
      }

      if (method === 'PATCH') {
        const body = (request.postDataJSON() ?? {}) as {
          title?: string
          theme?: 'default' | 'midnight' | 'sunrise'
          slides?: MockDeck['slides']
        }
        const nextDeck: MockDeck = {
          ...existing,
          meta: {
            ...existing.meta,
            title: typeof body.title === 'string' ? body.title : existing.meta.title,
            theme: body.theme ?? existing.meta.theme,
          },
          slides: Array.isArray(body.slides) ? body.slides : existing.slides,
        }
        decks.set(deckId, nextDeck)
        await fulfillJson(route, nextDeck)
        return
      }
    }

    if (method === 'GET' && path === '/api/tasks') {
      const limitRaw = url.searchParams.get('limit')
      const limit = limitRaw ? Number(limitRaw) : 20
      const status = url.searchParams.get('status')
      const taskList = [...tasks.values()]
        .filter((task) => !status || task.status === status)
        .sort((a, b) => (b.updated_at ?? b.created_at) - (a.updated_at ?? a.created_at))
        .slice(0, Number.isFinite(limit) ? limit : 20)
      await fulfillJson(route, { tasks: taskList })
      return
    }

    if (method === 'GET' && path === '/api/decks') {
      await fulfillJson(route, {
        decks: [...decks.values()],
        total: decks.size,
        limit: Number(url.searchParams.get('limit') ?? '100'),
      })
      return
    }

    if (method === 'GET' && path.startsWith('/api/artifacts/')) {
      const artifactId = decodeURIComponent(path.replace('/api/artifacts/', ''))
      const archive = [...researchArchives].reverse().find((item) => item.artifact_id) ?? researchArchives[0]
      await fulfillJson(route, {
        artifact_id: artifactId,
        session_id: archive?.session_id ?? 'session-archive-smoke',
        artifact_type: 'report',
        title: 'Mock Research Report',
        content: {
          markdown: [
            '# Mock Research Report',
            '',
            '## Key Findings',
            '- The async task flow completed successfully.',
            '- The report preview can be opened from the assistant message.',
          ].join('\n'),
          qa_pairs: [],
          answer_group_id: 'answer-group-1',
          panel_id: 'panel-1',
          claim_evidence_chains: archive?.claim_evidence_chains ?? [],
          paragraph_citations: archive?.paragraph_citations ?? [],
          paragraph_claim_links: archive?.paragraph_claim_links ?? [],
          navigation_index: archive?.navigation_index ?? {},
          citation_graph: archive?.citation_graph,
          conflict_summary: archive?.conflict_summary,
          conflict_review_resolutions: archive?.conflict_review_resolutions ?? [],
          claim_verification_summary: archive?.claim_verification_summary,
        },
        created_at: now + 40,
        updated_at: now + 40,
      })
      return
    }

    if (method === 'GET' && path === '/api/artifacts') {
      const artifactType = url.searchParams.get('artifact_type')?.trim() ?? ''
      const artifacts = resourceGrants
      void artifactType
      await fulfillJson(route, {
        artifacts: [],
        total: 0,
        limit: Number(url.searchParams.get('limit') ?? '100'),
      })
      return
    }

    await fulfillJson(
      route,
      { detail: `Unhandled mock route: ${method} ${path}` },
      404,
    )
  })
}
