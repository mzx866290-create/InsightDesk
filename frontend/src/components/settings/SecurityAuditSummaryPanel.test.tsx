import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  cleanupSecurityAuditEvents,
  getSecurityAuditEvents,
  getSecurityAuditSummary,
  getSecurityStatus,
} from '../../api/client'
import type {
  SecurityAuditSummary,
  SecurityStatusResponse,
} from '../../api/client'
import { SecurityAuditSummaryPanel } from './SecurityAuditSummaryPanel'

vi.mock('../../api/client', () => ({
  cleanupSecurityAuditEvents: vi.fn(),
  getSecurityAuditEvents: vi.fn(),
  getSecurityAuditSummary: vi.fn(),
  getSecurityStatus: vi.fn(),
}))

const securityStatusPayload: SecurityStatusResponse = {
  allow_remote_clients: true,
  local_only_mode: false,
  remote_auth_ready: true,
  admin_token_configured: true,
  remote_admin_ready: true,
  auth_token_count: 1,
  configured_roles: ['admin'],
  auth_token_hygiene_healthy: true,
  weak_auth_token_count: 0,
  legacy_auth_token_count: 0,
  share_link_secret_healthy: false,
  share_link_secret_uses_default: true,
  share_link_secret_min_length: 16,
  remote_share_ready: false,
  remote_management_rate_limit_enabled: true,
  remote_management_rate_limit_window_seconds: 60,
  remote_management_rate_limit_window_seconds_source: 'default',
  remote_management_rate_limit_max_requests: 120,
  remote_management_rate_limit_max_requests_source: 'default',
  remote_management_rate_limit_scope: 'remote-management',
  remote_management_rate_limit_storage: 'memory',
  remote_management_rate_limit_path_prefixes: ['/api/security/', '/api/auth/'],
  remote_management_rate_limit_response_headers: [
    'X-RateLimit-Limit',
    'X-RateLimit-Remaining',
    'X-RateLimit-Reset',
    'X-RateLimit-Scope',
    'Retry-After',
  ],
  remote_management_rate_limit_tracked_principal_count: 2,
  remote_management_rate_limit_active_request_count: 5,
  remote_management_rate_limit_blocked_count: 1,
  remote_management_rate_limit_last_blocked_at: 1715000123,
  remote_management_rate_limit_next_reset_after_seconds: 42,
  share_link_ttl_seconds: 604800,
  share_link_ttl_hours: 168,
  cors_allow_credentials: false,
  cors_allowed_origins: [],
  request_id_header: 'X-Request-ID',
  process_time_header: 'X-Process-Time-Ms',
  security_audit_storage: 'sqlite',
  security_audit_history_limit: 1000,
  security_audit_history_limit_source: 'default',
  security_audit_persisted_count: 9,
  security_audit_memory_window_limit: 500,
  chat_file_limits: {
    max_count: 6,
    max_bytes: 10485760,
    max_chars_per_file: 8000,
    max_total_chars: 24000,
    preview_chars: 4000,
  },
  document_upload_limits: {
    max_count: 12,
    max_file_bytes: 52428800,
    max_total_bytes: 209715200,
  },
}

const securityAuditSummaryPayload: SecurityAuditSummary = {
  category: '',
  categories: ['auth'],
  total: 1,
  recent_count: 1,
  window_limit: 200,
  action_counts: {
    remote_auth_guard: 1,
  },
  result_counts: {
    blocked: 1,
  },
  category_counts: {
    auth: 1,
  },
  unknown_action_count: 0,
}

describe('SecurityAuditSummaryPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getSecurityStatus).mockResolvedValue(securityStatusPayload)
    vi.mocked(getSecurityAuditSummary).mockResolvedValue(securityAuditSummaryPayload)
    vi.mocked(getSecurityAuditEvents).mockResolvedValue({
      events: [],
      total: 0,
      limit: 200,
    })
    vi.mocked(cleanupSecurityAuditEvents).mockResolvedValue({
      keep_latest: 200,
      deleted_count: 0,
      remaining_count: 0,
      dry_run: false,
    })
  })

  afterEach(() => {
    cleanup()
  })

  it('shows share-link security status from the security status endpoint', async () => {
    render(<SecurityAuditSummaryPanel />)

    const statusPanel = await screen.findByTestId('settings-security-status')

    expect(within(statusPanel).getByText('Remote sharing')).toBeInTheDocument()
    expect(within(statusPanel).getByText('Blocked')).toBeInTheDocument()
    expect(within(statusPanel).getByText('Share secret')).toBeInTheDocument()
    expect(within(statusPanel).getByText('Weak')).toBeInTheDocument()
    expect(within(statusPanel).getByText('Default secret')).toBeInTheDocument()
    expect(within(statusPanel).getByText('Yes')).toBeInTheDocument()
    expect(within(statusPanel).getByText('Minimum length')).toBeInTheDocument()
    expect(within(statusPanel).getByText('16')).toBeInTheDocument()
  })

  it('shows an isolated security status error while audit data still loads', async () => {
    vi.mocked(getSecurityStatus).mockRejectedValue(new Error('Mock security status failed'))

    render(<SecurityAuditSummaryPanel />)

    await expect(screen.findByTestId('settings-security-status-error')).resolves.toHaveTextContent(
      'Mock security status failed',
    )
    await waitFor(() => {
      expect(getSecurityAuditSummary).toHaveBeenCalled()
      expect(getSecurityAuditEvents).toHaveBeenCalled()
    })
  })

  it('reloads security status and summary from the top refresh button', async () => {
    render(<SecurityAuditSummaryPanel />)

    await screen.findByTestId('settings-security-status')
    expect(getSecurityStatus).toHaveBeenCalledTimes(1)
    expect(getSecurityAuditSummary).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByTestId('settings-security-audit-refresh'))

    await waitFor(() => {
      expect(getSecurityStatus).toHaveBeenCalledTimes(2)
      expect(getSecurityAuditSummary).toHaveBeenCalledTimes(2)
    })
  })

  it('clears an event reload error after a later successful refresh', async () => {
    vi.mocked(getSecurityAuditEvents)
      .mockResolvedValueOnce({
        events: [],
        total: 0,
        limit: 200,
      })
      .mockRejectedValueOnce(new Error('Mock event reload failed'))
      .mockResolvedValueOnce({
        events: [
          {
            timestamp: 1_715_000_000,
            action: 'remote_auth_guard',
            result: 'blocked',
            user_id: 'user-1',
            user_role: 'admin',
            auth_mode: 'token',
            auth_source: 'header',
            is_local: false,
            request_id: 'req-1',
            ip: '203.0.113.10',
            details: { reason: 'missing_token' },
          },
        ],
        total: 1,
        limit: 200,
      })

    render(<SecurityAuditSummaryPanel />)

    await screen.findByTestId('settings-security-audit-empty')

    fireEvent.click(screen.getByTestId('settings-security-audit-event-refresh'))

    await expect(screen.findByTestId('settings-security-audit-event-error')).resolves.toHaveTextContent(
      'Mock event reload failed',
    )

    fireEvent.click(screen.getByTestId('settings-security-audit-event-refresh'))

    await waitFor(() => {
      expect(screen.queryByTestId('settings-security-audit-event-error')).not.toBeInTheDocument()
    })
    const rows = await screen.findAllByTestId('settings-security-audit-event-row')
    expect(rows).toHaveLength(1)
    expect(within(rows[0]).getByText('remote_auth_guard')).toBeInTheDocument()
    expect(within(rows[0]).getByText('blocked')).toBeInTheDocument()
  })
})
