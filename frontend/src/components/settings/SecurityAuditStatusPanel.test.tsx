import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { SecurityStatusResponse } from '../../api/client'
import { SecurityAuditStatusPanel } from './SecurityAuditStatusPanel'

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

describe('SecurityAuditStatusPanel', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders security status KPI copy and abnormal tones', () => {
    render(<SecurityAuditStatusPanel securityStatus={securityStatusPayload} />)

    const statusPanel = screen.getByTestId('settings-security-status')

    expect(within(statusPanel).getByText('Remote sharing')).toBeInTheDocument()
    expect(within(statusPanel).getByText('Blocked')).toHaveClass('text-accent-red')
    expect(within(statusPanel).getByText('Share secret')).toBeInTheDocument()
    expect(within(statusPanel).getByText('Weak')).toHaveClass('text-accent-red')
    expect(within(statusPanel).getByText('Default secret')).toBeInTheDocument()
    expect(within(statusPanel).getByText('Yes')).toHaveClass('text-accent-red')
    expect(within(statusPanel).getByText('Rate blocks')).toBeInTheDocument()
    expect(within(statusPanel).getByText('1')).toHaveClass('text-accent-red')
  })

  it('renders empty placeholders when security status is missing', () => {
    render(<SecurityAuditStatusPanel securityStatus={null} />)

    const statusPanel = screen.getByTestId('settings-security-status')

    expect(within(statusPanel).getByText('Remote sharing')).toBeInTheDocument()
    expect(within(statusPanel).getByText('Share secret')).toBeInTheDocument()
    expect(within(statusPanel).getByText('Next reset')).toBeInTheDocument()
    expect(within(statusPanel).getAllByText('-')).toHaveLength(8)
  })
})
