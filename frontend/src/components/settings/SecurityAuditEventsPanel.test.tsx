import React from 'react'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { SecurityAuditEvent } from '../../api/client'
import { SecurityAuditEventsPanel } from './SecurityAuditEventsPanel'

vi.mock('../ui/Button', () => ({
  Button: ({
    children,
    loading: _loading,
    variant: _variant,
    size: _size,
    ...props
  }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
    loading?: boolean
    variant?: string
    size?: string
  }) => (
    <button {...props}>{children}</button>
  ),
}))

const auditEvent: SecurityAuditEvent = {
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
}

function renderPanel(overrides: Partial<React.ComponentProps<typeof SecurityAuditEventsPanel>> = {}) {
  const props: React.ComponentProps<typeof SecurityAuditEventsPanel> = {
    events: [auditEvent],
    eventsTotal: 10,
    eventsLimit: 200,
    eventsLoading: false,
    eventsError: null,
    actionFilter: '',
    resultFilter: '',
    categoryFilter: '',
    userFilter: '',
    sinceFilter: '',
    untilFilter: '',
    resultOptions: ['blocked'],
    resetDisabled: false,
    retentionKeepLatest: '200',
    retentionLoading: null,
    retentionResult: null,
    retentionError: null,
    onActionFilterChange: vi.fn(),
    onResultFilterChange: vi.fn(),
    onCategoryFilterChange: vi.fn(),
    onUserFilterChange: vi.fn(),
    onSinceFilterChange: vi.fn(),
    onUntilFilterChange: vi.fn(),
    onApplyFilters: vi.fn(),
    onResetFilters: vi.fn(),
    onRefresh: vi.fn(),
    onKeepLatestChange: vi.fn(),
    onPreviewRetention: vi.fn(),
    onCleanupRetention: vi.fn(),
    ...overrides,
  }

  return {
    props,
    ...render(<SecurityAuditEventsPanel {...props} />),
  }
}

describe('SecurityAuditEventsPanel', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('renders filters, event table, and retention controls', () => {
    vi.spyOn(Date.prototype, 'toLocaleString').mockReturnValue('2024-05-06 12:00:00')

    renderPanel()

    expect(screen.getByTestId('settings-security-audit-events')).toHaveTextContent('Events (1 / 10, limit 200)')
    expect(screen.getByTestId('settings-security-audit-event-row')).toHaveTextContent('remote_auth_guard')
    expect(screen.getByTestId('settings-security-audit-retention-keep-latest')).toHaveValue(200)
  })

  it('forwards filter, refresh, and retention actions', () => {
    const onActionFilterChange = vi.fn()
    const onRefresh = vi.fn()
    const onPreviewRetention = vi.fn()
    const onCleanupRetention = vi.fn()

    renderPanel({
      onActionFilterChange,
      onRefresh,
      onPreviewRetention,
      onCleanupRetention,
    })

    fireEvent.change(screen.getByTestId('settings-security-audit-event-action-filter'), {
      target: { value: 'remote_auth_guard' },
    })
    fireEvent.click(screen.getByTestId('settings-security-audit-event-refresh'))
    fireEvent.click(screen.getByTestId('settings-security-audit-retention-preview'))
    fireEvent.click(screen.getByTestId('settings-security-audit-retention-cleanup'))

    expect(onActionFilterChange).toHaveBeenCalledWith('remote_auth_guard')
    expect(onRefresh).toHaveBeenCalledTimes(1)
    expect(onPreviewRetention).toHaveBeenCalledTimes(1)
    expect(onCleanupRetention).toHaveBeenCalledTimes(1)
  })

  it('renders event and retention errors', () => {
    renderPanel({
      eventsError: 'Event reload failed',
      retentionError: 'Cleanup failed',
    })

    expect(screen.getByTestId('settings-security-audit-event-error')).toHaveTextContent('Event reload failed')
    expect(screen.getByTestId('settings-security-audit-retention-error')).toHaveTextContent('Cleanup failed')
  })
})
